"""F005-K fail-closed producer for immutable live GitHub repository observations."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Callable, Protocol, Sequence

from cyber_lion.contracts.fleet_repository_observation_source import (
    DEFAULT_BRANCH,
    AncestryEvidence,
    LiveBranch,
    ObservationConfig,
    ObservationReceipt,
    OwnershipEvidence,
    RepositoryObservationContractError,
    canonical_json,
)


class RepositoryObservationSourceError(RuntimeError):
    pass


class GitHubReadSource(Protocol):
    """Read-only GitHub source. Implementations must not expose mutation methods."""

    def default_head(self, repository: str, default_branch: str) -> tuple[str, str]:
        ...

    def list_branches_page(self, repository: str, cursor: str | None) -> tuple[Sequence[LiveBranch], str | None]:
        ...

    def compare_to_default(self, repository: str, default_head: str, branch_head: str, branch: str) -> AncestryEvidence:
        ...


class AuthoritativeOwnershipProvider(Protocol):
    """Independent authoritative ownership provenance provider."""

    def resolve(self, repository: str, branch: str, branch_head: str) -> OwnershipEvidence:
        ...


def _utc(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None:
        raise RepositoryObservationSourceError("observation clock must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _enumerate_all(source: GitHubReadSource, repository: str) -> tuple[LiveBranch, ...]:
    cursor: str | None = None
    values: list[LiveBranch] = []
    seen_cursors: set[str] = set()
    seen_names: set[str] = set()
    while True:
        if cursor is not None:
            if cursor in seen_cursors:
                raise RepositoryObservationSourceError("pagination cursor replay denied")
            seen_cursors.add(cursor)
        page, next_cursor = source.list_branches_page(repository, cursor)
        if not isinstance(page, Sequence):
            raise RepositoryObservationSourceError("branch page invalid")
        for item in page:
            if type(item) is not LiveBranch:
                raise RepositoryObservationSourceError("branch source returned invalid type")
            item.validate()
            if item.branch in seen_names:
                raise RepositoryObservationSourceError("duplicate live branch denied")
            seen_names.add(item.branch)
            values.append(item)
        if next_cursor is None:
            break
        if not isinstance(next_cursor, str) or not next_cursor:
            raise RepositoryObservationSourceError("pagination cursor invalid")
        cursor = next_cursor
    if not values:
        raise RepositoryObservationSourceError("empty live branch set denied")
    return tuple(sorted(values, key=lambda item: item.branch))


def _snapshot_fingerprint(branches: Sequence[LiveBranch]) -> tuple[tuple[str, str], ...]:
    return tuple((item.branch, item.head_sha) for item in branches)


def produce_observation_bytes(
    config: ObservationConfig,
    *,
    github: GitHubReadSource,
    ownership: AuthoritativeOwnershipProvider,
    clock: Callable[[], datetime],
) -> tuple[bytes, ObservationReceipt]:
    config.validate()
    before_master, before_tree = github.default_head(config.repository, config.default_branch)
    if before_master != config.expected_master or before_tree != config.expected_master_tree:
        raise RepositoryObservationSourceError("master or tree drift denied")

    before = _enumerate_all(github, config.repository)
    default_matches = [item for item in before if item.branch == config.default_branch]
    if len(default_matches) != 1 or default_matches[0].head_sha != config.expected_master:
        raise RepositoryObservationSourceError("default branch observation mismatch")

    epoch = _utc(clock)
    branch_values: list[dict[str, object]] = []
    for branch in before:
        if branch.branch == config.default_branch:
            continue
        own = ownership.resolve(config.repository, branch.branch, branch.head_sha)
        if type(own) is not OwnershipEvidence or own.branch != branch.branch:
            raise RepositoryObservationSourceError("ownership provider binding mismatch")
        try:
            own.validate()
        except RepositoryObservationContractError as exc:
            raise RepositoryObservationSourceError(str(exc)) from exc

        ancestry = github.compare_to_default(
            config.repository,
            config.expected_master,
            branch.head_sha,
            branch.branch,
        )
        if type(ancestry) is not AncestryEvidence or ancestry.branch != branch.branch:
            raise RepositoryObservationSourceError("ancestry provider binding mismatch")
        try:
            ancestry.validate()
        except RepositoryObservationContractError as exc:
            raise RepositoryObservationSourceError(str(exc)) from exc

        branch_values.append({
            "branch": branch.branch,
            "branch_head_sha": branch.head_sha,
            "mission_id": own.mission_id,
            "baseline_sha": own.baseline_sha,
            "ownership_state": own.ownership_state,
            "ancestry_state": ancestry.ancestry_state,
            "ahead_by": ancestry.ahead_by,
            "behind_by": ancestry.behind_by,
            "superseded_by_branch": own.superseded_by_branch,
            "supersession_provenance_ref": own.supersession_provenance_ref,
            "source_provenance_ref": own.source_provenance_ref,
            "epistemic_class": own.epistemic_class,
            "observed_at": epoch,
        })

    if not branch_values:
        raise RepositoryObservationSourceError("no non-default branches observed")

    after = _enumerate_all(github, config.repository)
    after_master, after_tree = github.default_head(config.repository, config.default_branch)
    if after_master != before_master or after_tree != before_tree:
        raise RepositoryObservationSourceError("master changed during observation")
    if _snapshot_fingerprint(after) != _snapshot_fingerprint(before):
        raise RepositoryObservationSourceError("branch set changed during observation")

    payload = {
        "schema_version": "1.0.0",
        "repository": config.repository,
        "inventory_revision": config.inventory_revision,
        "default_branch": config.default_branch,
        "default_head_sha": config.expected_master,
        "observed_at": epoch,
        "branches": sorted(branch_values, key=lambda item: str(item["branch"])),
    }
    raw = canonical_json(payload)
    digest = sha256(raw).hexdigest()
    receipt = ObservationReceipt(
        repository=config.repository,
        observed_master=config.expected_master,
        observed_master_tree=config.expected_master_tree,
        inventory_revision=config.inventory_revision,
        branch_count=len(branch_values),
        output_sha256=digest,
        materialized=False,
        asserts_fleet_close=False,
    ).validate()
    return raw, receipt


def materialize_observation(
    config: ObservationConfig,
    *,
    github: GitHubReadSource,
    ownership: AuthoritativeOwnershipProvider,
    clock: Callable[[], datetime],
    physical_output: Path | None = None,
) -> ObservationReceipt:
    raw, receipt = produce_observation_bytes(config, github=github, ownership=ownership, clock=clock)
    target = Path(config.output_path) if physical_output is None else Path(physical_output)
    if not target.is_absolute():
        raise RepositoryObservationSourceError("physical output path must be absolute")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise RepositoryObservationSourceError("immutable observation output already exists") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        raise
    if target.read_bytes() != raw:
        raise RepositoryObservationSourceError("materialized observation bytes mismatch")
    return ObservationReceipt(**{**asdict(receipt), "materialized": True}).validate()

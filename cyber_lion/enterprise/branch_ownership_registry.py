"""F005-L concrete read-only authoritative branch-ownership registry provider."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Mapping

from cyber_lion.contracts.branch_ownership_registry import (
    BranchOwnershipProviderConfig,
    BranchOwnershipRecord,
    BranchOwnershipRegistryContractError,
    BranchOwnershipRegistrySnapshot,
)
from cyber_lion.contracts.fleet_repository_observation_source import OwnershipEvidence


class BranchOwnershipRegistryError(RuntimeError):
    pass


_MAX_BYTES = 4 * 1024 * 1024


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BranchOwnershipRegistryError("duplicate JSON key denied")
        result[key] = value
    return result


def _stable_read(path: Path) -> bytes:
    if not path.is_absolute() or not path.is_file():
        raise BranchOwnershipRegistryError("authoritative ownership registry unavailable")
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ):
        raise BranchOwnershipRegistryError("ownership registry changed during read")
    if not raw or len(raw) > _MAX_BYTES:
        raise BranchOwnershipRegistryError("ownership registry size invalid")
    return raw


def _exact_keys(value: Mapping[str, Any], required: set[str], name: str) -> None:
    if set(value) != required:
        raise BranchOwnershipRegistryError(f"{name} keys do not match canonical contract")


def load_registry_snapshot(raw: bytes) -> BranchOwnershipRegistrySnapshot:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError, BranchOwnershipRegistryError) as exc:
        raise BranchOwnershipRegistryError("ownership registry JSON invalid") from exc
    if not isinstance(value, dict):
        raise BranchOwnershipRegistryError("ownership registry must be object")
    _exact_keys(
        value,
        {"schema_version", "repository", "source_instance_id", "registry_revision", "observed_at", "records", "registry_digest"},
        "ownership registry",
    )
    records_raw = value["records"]
    if not isinstance(records_raw, list):
        raise BranchOwnershipRegistryError("ownership records must be list")
    records: list[BranchOwnershipRecord] = []
    required_record = {
        "repository", "branch", "branch_head_sha", "ownership_state", "mission_id",
        "baseline_sha", "superseded_by_branch", "supersession_provenance_ref",
        "source_provenance_ref", "epistemic_class", "record_revision",
    }
    for item in records_raw:
        if not isinstance(item, dict):
            raise BranchOwnershipRegistryError("ownership record must be object")
        _exact_keys(item, required_record, "ownership record")
        try:
            records.append(BranchOwnershipRecord(**item).validate())
        except (TypeError, BranchOwnershipRegistryContractError) as exc:
            raise BranchOwnershipRegistryError(str(exc)) from exc
    try:
        return BranchOwnershipRegistrySnapshot(
            schema_version=value["schema_version"],
            repository=value["repository"],
            source_instance_id=value["source_instance_id"],
            registry_revision=value["registry_revision"],
            observed_at=value["observed_at"],
            records=tuple(records),
            registry_digest=value["registry_digest"],
        ).validate()
    except (TypeError, BranchOwnershipRegistryContractError) as exc:
        raise BranchOwnershipRegistryError(str(exc)) from exc


class FileBranchOwnershipRegistryProvider:
    """Concrete AuthoritativeOwnershipProvider over a durable immutable JSON registry."""

    def __init__(
        self,
        config: BranchOwnershipProviderConfig,
        *,
        physical_registry_path: Path | None = None,
    ) -> None:
        self._config = config.validate()
        self._path = Path(config.registry_path) if physical_registry_path is None else Path(physical_registry_path)
        if not self._path.is_absolute():
            raise BranchOwnershipRegistryError("physical registry path must be absolute")
        self._last_revision = 0
        self._last_digest: str | None = None

    def _snapshot(self) -> BranchOwnershipRegistrySnapshot:
        snapshot = load_registry_snapshot(_stable_read(self._path))
        if snapshot.repository != self._config.repository:
            raise BranchOwnershipRegistryError("registry repository mismatch")
        if snapshot.source_instance_id != self._config.source_instance_id:
            raise BranchOwnershipRegistryError("registry source instance mismatch")
        if snapshot.registry_revision < self._config.minimum_registry_revision:
            raise BranchOwnershipRegistryError("registry revision below configured minimum")
        if snapshot.registry_revision < self._last_revision:
            raise BranchOwnershipRegistryError("registry revision rollback denied")
        if snapshot.registry_revision == self._last_revision and self._last_digest not in {None, snapshot.registry_digest}:
            raise BranchOwnershipRegistryError("registry revision collision denied")
        self._last_revision = snapshot.registry_revision
        self._last_digest = snapshot.registry_digest
        return snapshot

    def resolve(self, repository: str, branch: str, branch_head: str) -> OwnershipEvidence:
        if repository != self._config.repository:
            raise BranchOwnershipRegistryError("repository substitution denied")
        snapshot = self._snapshot()
        matches = [record for record in snapshot.records if record.branch == branch]
        if not matches:
            raise BranchOwnershipRegistryError("unknown branch ownership denied")
        if len(matches) != 1:
            raise BranchOwnershipRegistryError("conflicting ownership records denied")
        record = matches[0]
        if record.branch_head_sha != branch_head:
            raise BranchOwnershipRegistryError("stale branch ownership head denied")
        try:
            evidence = OwnershipEvidence(
                branch=record.branch,
                ownership_state=record.ownership_state,
                mission_id=record.mission_id,
                baseline_sha=record.baseline_sha,
                superseded_by_branch=record.superseded_by_branch,
                supersession_provenance_ref=record.supersession_provenance_ref,
                source_provenance_ref=record.source_provenance_ref,
                epistemic_class=record.epistemic_class,
            ).validate()
        except Exception as exc:
            raise BranchOwnershipRegistryError("ownership evidence contract mismatch") from exc
        return evidence

    def registry_state(self) -> dict[str, Any]:
        """Read-only diagnostics; returns no mutation capability or authority."""
        snapshot = self._snapshot()
        return {
            "repository": snapshot.repository,
            "source_instance_id": snapshot.source_instance_id,
            "registry_revision": snapshot.registry_revision,
            "registry_digest": snapshot.registry_digest,
            "record_count": len(snapshot.records),
        }


def canonical_registry_bytes(snapshot: BranchOwnershipRegistrySnapshot) -> bytes:
    """Pure serializer for external tooling; does not persist or mutate runtime state."""
    snapshot.validate()
    return json.dumps(
        snapshot.canonical_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")

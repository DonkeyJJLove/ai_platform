"""Canonical F005-L branch ownership registry refresh executor."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from cyber_lion.contracts.branch_ownership_registry import (
    BranchOwnershipProviderConfig,
    BranchOwnershipRecord,
    BranchOwnershipRegistrySnapshot,
)
from cyber_lion.contracts.branch_ownership_registry_refresh import (
    BranchOwnershipRefreshManifest,
    BranchOwnershipRegistryRefreshContractError,
)
from cyber_lion.contracts.fleet_runtime_paths import resolve_fleet_runtime_paths
from cyber_lion.enterprise.branch_ownership_registry import (
    BranchOwnershipRegistryError,
    FileBranchOwnershipRegistryProvider,
    canonical_registry_bytes,
    load_registry_snapshot,
)
from cyber_lion.enterprise.github_repository_read_source import GitHubRepositoryReadSource


class BranchOwnershipRegistryRefreshError(RuntimeError):
    pass


_MAX_BYTES = 4 * 1024 * 1024


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise BranchOwnershipRegistryRefreshError("duplicate JSON key denied")
        value[key] = item
    return value


def _stable_bytes(path: Path, name: str) -> bytes:
    if not path.is_absolute() or not path.is_file():
        raise BranchOwnershipRegistryRefreshError(f"{name} unavailable")
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ):
        raise BranchOwnershipRegistryRefreshError(f"{name} changed during read")
    if not raw or len(raw) > _MAX_BYTES:
        raise BranchOwnershipRegistryRefreshError(f"{name} size invalid")
    return raw


def load_refresh_manifest(raw: bytes) -> BranchOwnershipRefreshManifest:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError, BranchOwnershipRegistryRefreshError) as exc:
        raise BranchOwnershipRegistryRefreshError("ownership refresh manifest JSON invalid") from exc
    if not isinstance(value, dict):
        raise BranchOwnershipRegistryRefreshError("ownership refresh manifest must be object")
    required = {
        "schema_version", "repository", "source_instance_id",
        "previous_registry_revision", "previous_registry_digest",
        "target_registry_revision", "expected_master", "expected_master_tree",
        "observed_at", "records", "manifest_digest",
    }
    if set(value) != required or not isinstance(value.get("records"), list):
        raise BranchOwnershipRegistryRefreshError("ownership refresh manifest schema invalid")
    try:
        records = tuple(BranchOwnershipRecord(**item).validate() for item in value["records"] if isinstance(item, dict))
        if len(records) != len(value["records"]):
            raise BranchOwnershipRegistryRefreshError("ownership refresh record invalid")
        return BranchOwnershipRefreshManifest(
            schema_version=value["schema_version"],
            repository=value["repository"],
            source_instance_id=value["source_instance_id"],
            previous_registry_revision=value["previous_registry_revision"],
            previous_registry_digest=value["previous_registry_digest"],
            target_registry_revision=value["target_registry_revision"],
            expected_master=value["expected_master"],
            expected_master_tree=value["expected_master_tree"],
            observed_at=value["observed_at"],
            records=records,
            manifest_digest=value["manifest_digest"],
        ).validate()
    except (TypeError, BranchOwnershipRegistryRefreshContractError, ValueError) as exc:
        raise BranchOwnershipRegistryRefreshError(str(exc)) from exc


def _branch_map(github: Any, repository: str) -> dict[str, str]:
    branches = github.list_branches(repository)
    result: dict[str, str] = {}
    for branch in branches:
        name = str(branch.branch)
        head = str(branch.head_sha)
        if name in result:
            raise BranchOwnershipRegistryRefreshError("duplicate live branch denied")
        result[name] = head
    return result


def _verify_baseline_ancestry(github: Any, repository: str, record: BranchOwnershipRecord) -> None:
    if record.ownership_state not in {"ACTIVE", "TERMINAL"}:
        return
    assert record.baseline_sha is not None
    comparison = github.compare(repository, record.baseline_sha, record.branch_head_sha)
    status = getattr(comparison, "status", None)
    if status not in {"ahead", "identical"}:
        raise BranchOwnershipRegistryRefreshError("mission baseline is not ancestral to branch head")


def refresh_branch_ownership_registry(
    *,
    expected_master: str,
    expected_master_tree: str,
    manifest_sha256: str,
    github: Any | None = None,
    manifest_path: Path | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    paths = resolve_fleet_runtime_paths()
    manifest = Path(paths.branch_ownership_manifest_path) if manifest_path is None else Path(manifest_path)
    registry = Path(paths.branch_ownership_registry_path) if registry_path is None else Path(registry_path)
    if str(manifest) != paths.branch_ownership_manifest_path or str(registry) != paths.branch_ownership_registry_path:
        raise BranchOwnershipRegistryRefreshError("runtime path substitution denied")

    manifest_raw = _stable_bytes(manifest, "ownership refresh manifest")
    if sha256(manifest_raw).hexdigest() != manifest_sha256:
        raise BranchOwnershipRegistryRefreshError("ownership refresh manifest byte digest mismatch")
    parsed = load_refresh_manifest(manifest_raw)
    if parsed.expected_master != expected_master or parsed.expected_master_tree != expected_master_tree:
        raise BranchOwnershipRegistryRefreshError("manifest master binding mismatch")

    registry_raw = _stable_bytes(registry, "current ownership registry")
    try:
        current = load_registry_snapshot(registry_raw)
    except BranchOwnershipRegistryError as exc:
        raise BranchOwnershipRegistryRefreshError("current ownership registry invalid") from exc
    if current.registry_revision != parsed.previous_registry_revision:
        raise BranchOwnershipRegistryRefreshError("previous registry revision mismatch")
    if current.registry_digest != parsed.previous_registry_digest:
        raise BranchOwnershipRegistryRefreshError("previous registry digest mismatch")

    source = github if github is not None else GitHubRepositoryReadSource.from_environment()
    default = source.get_default_branch(parsed.repository)
    if default.branch != "master" or default.head_sha != expected_master or default.tree_sha != expected_master_tree:
        raise BranchOwnershipRegistryRefreshError("live master binding mismatch")

    before = _branch_map(source, parsed.repository)
    manifest_heads = {record.branch: record.branch_head_sha for record in parsed.records}
    if manifest_heads != before:
        raise BranchOwnershipRegistryRefreshError("manifest branch set/head binding mismatch")
    for record in parsed.records:
        _verify_baseline_ancestry(source, parsed.repository, record)
    after = _branch_map(source, parsed.repository)
    if before != after:
        raise BranchOwnershipRegistryRefreshError("live branch set changed during refresh")

    next_snapshot = BranchOwnershipRegistrySnapshot.build(
        schema_version="1.0.0",
        repository=parsed.repository,
        source_instance_id=parsed.source_instance_id,
        registry_revision=parsed.target_registry_revision,
        observed_at=parsed.observed_at,
        records=parsed.records,
    )
    next_bytes = canonical_registry_bytes(next_snapshot)

    if _stable_bytes(registry, "current ownership registry") != registry_raw:
        raise BranchOwnershipRegistryRefreshError("current ownership registry changed before effect")

    registry.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{registry.name}.", suffix=".tmp", dir=str(registry.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(next_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        if temp.read_bytes() != next_bytes:
            raise BranchOwnershipRegistryRefreshError("temporary registry bytes mismatch")
        load_registry_snapshot(temp.read_bytes())
        os.replace(temp, registry)
    finally:
        if temp.exists():
            temp.unlink()

    provider = FileBranchOwnershipRegistryProvider(
        BranchOwnershipProviderConfig(repository=parsed.repository, source_instance_id=parsed.source_instance_id),
        physical_registry_path=registry,
    )
    state = provider.registry_state()
    for record in parsed.records:
        provider.resolve(parsed.repository, record.branch, record.branch_head_sha)
    if state["registry_revision"] != parsed.target_registry_revision or state["registry_digest"] != next_snapshot.registry_digest:
        raise BranchOwnershipRegistryRefreshError("post-effect registry verification failed")

    return {
        "schema_version": "1.0.0",
        "repository": parsed.repository,
        "expected_master": expected_master,
        "expected_master_tree": expected_master_tree,
        "previous_registry_revision": current.registry_revision,
        "previous_registry_digest": current.registry_digest,
        "registry_revision": next_snapshot.registry_revision,
        "registry_digest": next_snapshot.registry_digest,
        "record_count": len(next_snapshot.records),
        "manifest_digest": parsed.manifest_digest,
        "manifest_sha256": manifest_sha256,
        "registry_path": str(registry),
        "runtime_effect": "BRANCH_OWNERSHIP_REGISTRY_REPLACED_ONCE",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F005-L canonical branch ownership registry refresh")
    parser.add_argument("--expected-master", required=True)
    parser.add_argument("--expected-master-tree", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(argv)
    result = refresh_branch_ownership_registry(
        expected_master=args.expected_master,
        expected_master_tree=args.expected_master_tree,
        manifest_sha256=args.manifest_sha256,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

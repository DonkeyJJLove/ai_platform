"""F005-J runtime repository-inventory ingestion into the canonical reconciliation store."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path, PureWindowsPath
import sqlite3
from typing import Any, Mapping

from cyber_lion.contracts.fleet_reconciliation import BranchEvidence, ReconciliationTrustPins, RepositoryInventory
from cyber_lion.contracts.fleet_runtime_reconciliation_ingestion import (
    RECONCILIATION_DB_PATH,
    RECONCILIATION_TRUST_PATH,
    REPOSITORY,
    RUNTIME_SOURCE_INSTANCE_ID,
    OBSERVATION_PATH,
    ObservedBranch,
    RuntimeReconciliationIngestionConfig,
    RuntimeReconciliationIngestionReceipt,
    RuntimeRepositoryObservation,
)
from cyber_lion.enterprise.fleet_reconciliation import ReconciliationStore


class RuntimeReconciliationIngestionError(RuntimeError):
    pass


_MAX_BYTES = 1024 * 1024


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise RuntimeReconciliationIngestionError("duplicate JSON key denied")
        value[key] = item
    return value


def _stable_read(path: Path, *, expected_sha256: str, name: str) -> bytes:
    if not path.is_absolute() or not path.is_file():
        raise RuntimeReconciliationIngestionError(f"{name} must be an existing absolute file")
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise RuntimeReconciliationIngestionError(f"{name} changed during observation")
    if not raw or len(raw) > _MAX_BYTES:
        raise RuntimeReconciliationIngestionError(f"{name} size invalid")
    if sha256(raw).hexdigest() != expected_sha256:
        raise RuntimeReconciliationIngestionError(f"{name} digest mismatch")
    return raw


def _json_object(raw: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError, RuntimeReconciliationIngestionError) as exc:
        raise RuntimeReconciliationIngestionError(f"{name} JSON invalid") from exc
    if not isinstance(value, dict):
        raise RuntimeReconciliationIngestionError(f"{name} must be a JSON object")
    return value


def _exact_keys(value: Mapping[str, Any], required: set[str], name: str) -> None:
    if set(value) != required:
        raise RuntimeReconciliationIngestionError(f"{name} keys do not match canonical contract")


def _load_trust(raw: bytes, *, source_instance_id: str) -> ReconciliationTrustPins:
    value = _json_object(raw, "reconciliation trust")
    _exact_keys(value, {"source_id", "source_instance_id", "source_implementation_digest", "trust_anchor_id"}, "reconciliation trust")
    try:
        pins = ReconciliationTrustPins(**value).validate()
    except (TypeError, ValueError) as exc:
        raise RuntimeReconciliationIngestionError("reconciliation trust contract mismatch") from exc
    if pins.source_instance_id != source_instance_id:
        raise RuntimeReconciliationIngestionError("reconciliation source instance substitution denied")
    return pins


def _parse_utc(value: object, name: str) -> datetime:
    if not isinstance(value, str):
        raise RuntimeReconciliationIngestionError(f"{name} invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeReconciliationIngestionError(f"{name} invalid") from exc
    if parsed.tzinfo is None:
        raise RuntimeReconciliationIngestionError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _load_observation(raw: bytes, *, repository: str, current_master: str) -> RuntimeRepositoryObservation:
    value = _json_object(raw, "repository observation")
    _exact_keys(value, {"schema_version", "repository", "inventory_revision", "default_branch", "default_head_sha", "observed_at", "branches"}, "repository observation")
    if value["schema_version"] != "1.0.0":
        raise RuntimeReconciliationIngestionError("repository observation schema mismatch")
    if value["repository"] != repository:
        raise RuntimeReconciliationIngestionError("repository observation substitution denied")
    if value["default_head_sha"] != current_master:
        raise RuntimeReconciliationIngestionError("repository observation master drift denied")
    if isinstance(value["inventory_revision"], bool) or not isinstance(value["inventory_revision"], int) or value["inventory_revision"] < 1:
        raise RuntimeReconciliationIngestionError("inventory revision invalid")
    observed_at = _parse_utc(value["observed_at"], "observation observed_at")
    branches_raw = value["branches"]
    if not isinstance(branches_raw, list) or not branches_raw:
        raise RuntimeReconciliationIngestionError("empty repository observation denied")
    branches: list[ObservedBranch] = []
    names: set[str] = set()
    required = {"branch", "branch_head_sha", "mission_id", "baseline_sha", "ownership_state", "ancestry_state", "ahead_by", "behind_by", "superseded_by_branch", "supersession_provenance_ref", "source_provenance_ref", "epistemic_class", "observed_at"}
    for item in branches_raw:
        if not isinstance(item, dict):
            raise RuntimeReconciliationIngestionError("branch observation must be an object")
        _exact_keys(item, required, "branch observation")
        branch = ObservedBranch(**item)
        if branch.branch in names:
            raise RuntimeReconciliationIngestionError("duplicate branch observation denied")
        names.add(branch.branch)
        if branch.branch == value["default_branch"]:
            raise RuntimeReconciliationIngestionError("default branch must not appear as mission branch")
        if _parse_utc(branch.observed_at, "branch observed_at") > observed_at:
            raise RuntimeReconciliationIngestionError("branch observation newer than inventory denied")
        branches.append(branch)
    branches.sort(key=lambda item: item.branch)
    return RuntimeRepositoryObservation("1.0.0", repository, value["inventory_revision"], value["default_branch"], current_master, value["observed_at"], tuple(branches))


def _build_inventory(observation: RuntimeRepositoryObservation, pins: ReconciliationTrustPins) -> RepositoryInventory:
    evidence = tuple(BranchEvidence.build(
        repository=observation.repository,
        branch=item.branch,
        branch_head_sha=item.branch_head_sha,
        mission_id=item.mission_id,
        baseline_sha=item.baseline_sha,
        ownership_state=item.ownership_state,
        ancestry_state=item.ancestry_state,
        ahead_by=item.ahead_by,
        behind_by=item.behind_by,
        superseded_by_branch=item.superseded_by_branch,
        supersession_provenance_ref=item.supersession_provenance_ref,
        source_provenance_ref=item.source_provenance_ref,
        epistemic_class=item.epistemic_class,
        observed_at=item.observed_at,
    ) for item in observation.branches)
    return RepositoryInventory.build(
        schema_version="1.0.0",
        inventory_id=observation.deterministic_inventory_id(pins),
        inventory_revision=observation.inventory_revision,
        repository=observation.repository,
        default_branch=observation.default_branch,
        default_head_sha=observation.default_head_sha,
        source_id=pins.source_id,
        source_instance_id=pins.source_instance_id,
        source_implementation_digest=pins.source_implementation_digest,
        trust_anchor_id=pins.trust_anchor_id,
        observed_at=observation.observed_at,
        branches=evidence,
    ).validate()


def _ro(path: Path) -> sqlite3.Connection:
    if not path.is_absolute() or not path.is_file():
        raise RuntimeReconciliationIngestionError("canonical reconciliation store unavailable")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _read_state(path: Path, repository: str) -> dict[str, Any]:
    conn = _ro(path)
    try:
        head = conn.execute("SELECT repository,inventory_id,inventory_revision,inventory_digest,default_head_sha,observed_at FROM reconciliation_inventory_head WHERE repository=?", (repository,)).fetchone()
        return {
            "head": dict(head) if head is not None else None,
            "reports": int(conn.execute("SELECT COUNT(*) FROM reconciliation_report").fetchone()[0]),
            "receipts": int(conn.execute("SELECT COUNT(*) FROM convergence_receipt").fetchone()[0]),
            "consumed": int(conn.execute("SELECT COUNT(*) FROM convergence_receipt WHERE consumed<>0").fetchone()[0]),
        }
    finally:
        conn.close()


def _production_paths(config: RuntimeReconciliationIngestionConfig) -> dict[str, Path]:
    return {
        "observation": Path(config.observation_path),
        "trust": Path(config.reconciliation_trust_path),
        "reconciliation": Path(config.reconciliation_db_path),
    }


def _resolve_physical_paths(config: RuntimeReconciliationIngestionConfig, physical_paths: Mapping[str, Path] | None) -> dict[str, Path]:
    if physical_paths is None:
        return _production_paths(config)
    if set(physical_paths) != {"observation", "trust", "reconciliation"}:
        raise RuntimeReconciliationIngestionError("physical path mapping incomplete")
    result = {name: Path(path) for name, path in physical_paths.items()}
    if any(not path.is_absolute() for path in result.values()):
        raise RuntimeReconciliationIngestionError("physical paths must be absolute")
    return result


def ingest_repository_inventory(
    config: RuntimeReconciliationIngestionConfig,
    *,
    observation_file: str,
    reconciliation_trust_file: str,
    repository_root: str,
    physical_paths: Mapping[str, Path] | None = None,
) -> RuntimeReconciliationIngestionReceipt:
    config.validate()
    repo_root = Path(repository_root).resolve(strict=True)
    if not repo_root.is_dir():
        raise RuntimeReconciliationIngestionError("repository root must be a directory")
    logical_observation = PureWindowsPath(observation_file)
    logical_trust = PureWindowsPath(reconciliation_trust_file)
    if logical_observation != PureWindowsPath(config.observation_path):
        raise RuntimeReconciliationIngestionError("observation file path substitution denied")
    if logical_trust != PureWindowsPath(config.reconciliation_trust_path):
        raise RuntimeReconciliationIngestionError("reconciliation trust file path substitution denied")

    paths = _resolve_physical_paths(config, physical_paths)
    for name in ("observation", "trust"):
        resolved = paths[name].resolve(strict=True)
        if resolved == repo_root or repo_root in resolved.parents:
            raise RuntimeReconciliationIngestionError(f"{name} file must remain outside repository")
        paths[name] = resolved
    paths["reconciliation"] = paths["reconciliation"].resolve(strict=True)

    observation_raw = _stable_read(paths["observation"], expected_sha256=config.observation_sha256, name="observation file")
    trust_raw = _stable_read(paths["trust"], expected_sha256=config.trust_sha256, name="reconciliation trust file")
    pins = _load_trust(trust_raw, source_instance_id=config.source_instance_id)
    observation = _load_observation(observation_raw, repository=config.repository, current_master=config.current_master)
    inventory = _build_inventory(observation, pins)

    before = _read_state(paths["reconciliation"], config.repository)
    current = before["head"]
    if current is None:
        if inventory.inventory_revision != 1:
            raise RuntimeReconciliationIngestionError("first inventory revision must equal 1")
    else:
        if inventory.inventory_revision != int(current["inventory_revision"]) + 1:
            raise RuntimeReconciliationIngestionError("inventory revision must advance exactly once")
        if _parse_utc(inventory.observed_at, "inventory observed_at") <= _parse_utc(current["observed_at"], "stored observed_at"):
            raise RuntimeReconciliationIngestionError("inventory observation time replay denied")

    store = ReconciliationStore(paths["reconciliation"], trust_pins=pins, clock=lambda: datetime.now(timezone.utc))
    try:
        store.record_inventory(inventory)
    finally:
        store.close()

    after = _read_state(paths["reconciliation"], config.repository)
    expected_head = {
        "repository": inventory.repository,
        "inventory_id": inventory.inventory_id,
        "inventory_revision": inventory.inventory_revision,
        "inventory_digest": inventory.inventory_digest,
        "default_head_sha": inventory.default_head_sha,
        "observed_at": inventory.observed_at,
    }
    if after["head"] != expected_head:
        raise RuntimeReconciliationIngestionError("inventory head postcondition mismatch")
    for name in ("reports", "receipts", "consumed"):
        if after[name] != before[name]:
            raise RuntimeReconciliationIngestionError(f"forbidden reconciliation side effect: {name}")

    return RuntimeReconciliationIngestionReceipt(
        schema_version="1.0.0",
        repository=config.repository,
        current_master=config.current_master,
        current_master_tree=config.current_master_tree,
        source_instance_id=config.source_instance_id,
        config_digest=config.digest(),
        observation_sha256=config.observation_sha256,
        trust_sha256=config.trust_sha256,
        inventory_id=inventory.inventory_id,
        inventory_revision=inventory.inventory_revision,
        inventory_digest=inventory.inventory_digest,
        branch_count=len(inventory.branches),
        report_generated=False,
        convergence_receipt_generated=False,
        convergence_receipt_consumed=False,
        fleet_close_asserted=False,
    ).validate()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--expected-master", required=True)
    parser.add_argument("--expected-master-tree", required=True)
    parser.add_argument("--source-instance", required=True)
    parser.add_argument("--observation-file", required=True)
    parser.add_argument("--observation-sha256", required=True)
    parser.add_argument("--reconciliation-trust-file", required=True)
    parser.add_argument("--reconciliation-trust-sha256", required=True)
    parser.add_argument("--reconciliation-db", required=True)
    parser.add_argument("--repository-root", required=True)
    args = parser.parse_args(argv)
    config = RuntimeReconciliationIngestionConfig(
        repository=args.repository,
        current_master=args.expected_master,
        current_master_tree=args.expected_master_tree,
        source_instance_id=args.source_instance,
        observation_sha256=args.observation_sha256,
        trust_sha256=args.reconciliation_trust_sha256,
        reconciliation_db_path=args.reconciliation_db,
        observation_path=args.observation_file,
        reconciliation_trust_path=args.reconciliation_trust_file,
    ).validate()
    receipt = ingest_repository_inventory(config, observation_file=args.observation_file, reconciliation_trust_file=args.reconciliation_trust_file, repository_root=args.repository_root)
    print(json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

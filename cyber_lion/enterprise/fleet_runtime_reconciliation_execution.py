"""F005-Q production runtime entrypoint for one post-ingest reconciliation execution."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Mapping

from cyber_lion.contracts.fleet_runtime_paths import resolve_fleet_runtime_paths
from cyber_lion.contracts.fleet_runtime_reconciliation_execution import (
    REPOSITORY,
    RuntimeReconciliationExecutionConfig,
    RuntimeReconciliationExecutionReceipt,
)
from cyber_lion.enterprise.fleet_closure_preconditions_provider import RuntimeClosurePreconditionsProvider
from cyber_lion.enterprise.fleet_recorded_inventory_reconciliation import RecordedInventoryReconciliationRunner
from cyber_lion.enterprise.fleet_reconciliation import BranchReconciliationClassifier, ReconciliationStore
from cyber_lion.enterprise.fleet_runtime_reconciliation_ingestion import (
    RuntimeReconciliationIngestionError,
    _build_inventory,
    _load_observation,
    _load_trust,
)


class RuntimeReconciliationExecutionError(RuntimeError):
    pass


_MAX_BYTES = 1024 * 1024


def _stable_bytes(path: Path, name: str) -> bytes:
    if not path.is_absolute() or not path.is_file():
        raise RuntimeReconciliationExecutionError(f"{name} unavailable")
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise RuntimeReconciliationExecutionError(f"{name} changed during observation")
    if not raw or len(raw) > _MAX_BYTES:
        raise RuntimeReconciliationExecutionError(f"{name} size invalid")
    return raw


def _ro_state(path: Path, repository: str) -> tuple[dict[str, object], int, int]:
    if not path.is_absolute() or not path.is_file():
        raise RuntimeReconciliationExecutionError("canonical reconciliation store unavailable")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    try:
        row = conn.execute(
            "SELECT repository,inventory_id,inventory_revision,inventory_digest,default_head_sha,observed_at "
            "FROM reconciliation_inventory_head WHERE repository=?",
            (repository,),
        ).fetchone()
        if row is None:
            raise RuntimeReconciliationExecutionError("recorded repository inventory missing")
        reports = int(conn.execute(
            "SELECT COUNT(*) FROM reconciliation_report WHERE repository=? AND inventory_digest=?",
            (repository, row["inventory_digest"]),
        ).fetchone()[0])
        receipts = int(conn.execute(
            "SELECT COUNT(*) FROM convergence_receipt WHERE repository=? AND inventory_digest=?",
            (repository, row["inventory_digest"]),
        ).fetchone()[0])
        return dict(row), reports, receipts
    finally:
        conn.close()


def _paths(config: RuntimeReconciliationExecutionConfig, physical_paths: Mapping[str, Path] | None) -> dict[str, Path]:
    logical = resolve_fleet_runtime_paths()
    if physical_paths is None:
        if os.name != "nt":
            raise RuntimeReconciliationExecutionError("production execution requires Windows lion-runtime")
        reconciliation = Path(logical.reconciliation_db_path)
        return {
            "status": Path(logical.status_db_path),
            "coordination": Path(logical.coordination_db_path),
            "reconciliation": reconciliation,
            "trust": Path(logical.reconciliation_trust_path),
            "inventory": Path(logical.repository_inventory_path),
            "receipt": reconciliation.with_name("reconciliation-execution-receipt.json"),
        }
    required = {"status", "coordination", "reconciliation", "trust", "inventory", "receipt"}
    if set(physical_paths) != required:
        raise RuntimeReconciliationExecutionError("physical path mapping incomplete")
    result = {name: Path(value) for name, value in physical_paths.items()}
    if any(not value.is_absolute() for value in result.values()):
        raise RuntimeReconciliationExecutionError("physical paths must be absolute")
    return result


def execute_runtime_reconciliation(
    config: RuntimeReconciliationExecutionConfig,
    *,
    repository_root: str,
    physical_paths: Mapping[str, Path] | None = None,
) -> RuntimeReconciliationExecutionReceipt:
    config.validate()
    repo_root = Path(repository_root).resolve(strict=True)
    if not repo_root.is_dir():
        raise RuntimeReconciliationExecutionError("repository root must be directory")
    paths = _paths(config, physical_paths)
    for name in ("status", "coordination", "reconciliation", "trust", "inventory"):
        paths[name] = paths[name].resolve(strict=True)
    receipt_path = paths["receipt"].resolve(strict=False)
    if receipt_path == repo_root or repo_root in receipt_path.parents:
        raise RuntimeReconciliationExecutionError("execution receipt must remain outside repository")
    if receipt_path.exists():
        raise RuntimeReconciliationExecutionError("immutable execution receipt already exists")

    try:
        trust_raw = _stable_bytes(paths["trust"], "reconciliation trust")
        trust = _load_trust(trust_raw, source_instance_id=config.source_instance)
        inventory_raw = _stable_bytes(paths["inventory"], "repository inventory")
        observation = _load_observation(inventory_raw, repository=config.repository, current_master=config.current_master)
        inventory = _build_inventory(observation, trust)
    except RuntimeReconciliationIngestionError as exc:
        raise RuntimeReconciliationExecutionError("trusted inventory evidence invalid") from exc

    if inventory.default_head_sha != config.current_master:
        raise RuntimeReconciliationExecutionError("inventory master drift denied")
    head_before, existing_reports, existing_receipts = _ro_state(paths["reconciliation"], config.repository)
    expected_head = {
        "repository": inventory.repository,
        "inventory_id": inventory.inventory_id,
        "inventory_revision": inventory.inventory_revision,
        "inventory_digest": inventory.inventory_digest,
        "default_head_sha": inventory.default_head_sha,
        "observed_at": inventory.observed_at,
    }
    if head_before != expected_head:
        raise RuntimeReconciliationExecutionError("recorded inventory binding mismatch")
    if existing_reports or existing_receipts:
        raise RuntimeReconciliationExecutionError("reconciliation execution replay denied")

    closure_provider = RuntimeClosurePreconditionsProvider(
        current_master=config.current_master,
        current_master_tree=config.current_master_tree,
        source_instance=config.source_instance,
        status_db_path=str(paths["status"]),
        coordination_db_path=str(paths["coordination"]),
        reconciliation_db_path=str(paths["reconciliation"]),
    )
    store = ReconciliationStore(paths["reconciliation"], trust_pins=trust, clock=lambda: datetime.now(timezone.utc))
    try:
        runner = RecordedInventoryReconciliationRunner(
            closure_provider=closure_provider,
            classifier=BranchReconciliationClassifier(),
            store=store,
        )
        run = runner.reconcile(config.repository, inventory)
    finally:
        store.close()

    head_after, reports_after, receipts_after = _ro_state(paths["reconciliation"], config.repository)
    if head_after != expected_head:
        raise RuntimeReconciliationExecutionError("inventory changed during reconciliation execution")
    if reports_after != 1:
        raise RuntimeReconciliationExecutionError("reconciliation report postcondition mismatch")
    expected_receipts = 1 if run.report.disposition == "CONVERGED" else 0
    if receipts_after != expected_receipts:
        raise RuntimeReconciliationExecutionError("convergence receipt postcondition mismatch")

    convergence_digest = None if run.convergence_receipt is None else run.convergence_receipt.receipt_digest
    receipt = RuntimeReconciliationExecutionReceipt.build(
        schema_version="1.0.0",
        repository=config.repository,
        current_master=config.current_master,
        current_master_tree=config.current_master_tree,
        inventory_id=inventory.inventory_id,
        inventory_revision=inventory.inventory_revision,
        inventory_digest=inventory.inventory_digest,
        closure_preconditions_digest=run.closure_preconditions_digest,
        report_id=run.report.report_id,
        report_digest=run.report.report_digest,
        disposition=run.report.disposition,
        convergence_receipt_digest=convergence_digest,
        execution_config_digest=config.digest(),
        receipt_consumed=False,
        mission_closed=False,
        fleet_closed=False,
        release_performed=False,
        deploy_performed=False,
    )
    payload = json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with receipt_path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise RuntimeReconciliationExecutionError("execution receipt race denied") from exc
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F005-Q runtime reconciliation execution")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--expected-master", required=True)
    parser.add_argument("--expected-master-tree", required=True)
    parser.add_argument("--repository-root", required=True)
    args = parser.parse_args(argv)
    config = RuntimeReconciliationExecutionConfig(
        repository=args.repository,
        current_master=args.expected_master,
        current_master_tree=args.expected_master_tree,
    ).validate()
    receipt = execute_runtime_reconciliation(config, repository_root=args.repository_root)
    print(json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

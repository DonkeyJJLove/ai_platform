"""Strictly read-only F005-Q runtime reconciliation preflight observer."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
from typing import Mapping

from cyber_lion.contracts.fleet_runtime_paths import resolve_fleet_runtime_paths
from cyber_lion.contracts.fleet_runtime_reconciliation_preflight import (
    REPOSITORY,
    RuntimeReconciliationPreflightConfig,
    RuntimeReconciliationPreflightResult,
)
from cyber_lion.enterprise.fleet_runtime_reconciliation_ingestion import (
    RuntimeReconciliationIngestionError,
    _build_inventory,
    _load_observation,
    _load_trust,
    _read_state,
    _ro,
)
from cyber_lion.enterprise.fleet_runtime_snapshot_source import (
    RuntimeSnapshotSourceError,
    _read_coordination,
    _read_reconciliation,
    _read_status,
)


class RuntimeReconciliationPreflightError(RuntimeError):
    pass


_MAX_BYTES = 1024 * 1024
_REQUIRED_PHYSICAL_KEYS = frozenset({
    "status",
    "coordination",
    "reconciliation",
    "trust",
    "inventory",
    "execution_receipt",
})


def _stable_bytes(path: Path, name: str) -> bytes:
    if not path.is_absolute() or not path.is_file():
        raise RuntimeReconciliationPreflightError(f"{name} unavailable")
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise RuntimeReconciliationPreflightError(f"{name} changed during observation")
    if not raw or len(raw) > _MAX_BYTES:
        raise RuntimeReconciliationPreflightError(f"{name} size invalid")
    return raw


def _execution_receipt_state(path: Path) -> tuple[bool, bool]:
    """Return (present, stable); never creates or modifies the target."""
    if not path.is_absolute():
        raise RuntimeReconciliationPreflightError("execution receipt path must be absolute")
    before_present = path.is_file()
    if before_present:
        try:
            _stable_bytes(path, "runtime execution receipt")
        except RuntimeReconciliationPreflightError:
            return True, False
    after_present = path.is_file()
    return before_present, before_present == after_present


def _production_paths() -> dict[str, Path]:
    logical = resolve_fleet_runtime_paths()
    reconciliation = Path(logical.reconciliation_db_path)
    return {
        "status": Path(logical.status_db_path),
        "coordination": Path(logical.coordination_db_path),
        "reconciliation": reconciliation,
        "trust": Path(logical.reconciliation_trust_path),
        "inventory": Path(logical.repository_inventory_path),
        "execution_receipt": reconciliation.with_name("reconciliation-execution-receipt.json"),
    }


def _resolve_paths(physical_paths: Mapping[str, Path] | None) -> dict[str, Path]:
    if physical_paths is None:
        if os.name != "nt":
            raise RuntimeReconciliationPreflightError("production preflight requires Windows lion-runtime")
        return _production_paths()
    if set(physical_paths) != _REQUIRED_PHYSICAL_KEYS:
        raise RuntimeReconciliationPreflightError("physical path mapping incomplete")
    result = {name: Path(value) for name, value in physical_paths.items()}
    if any(not path.is_absolute() for path in result.values()):
        raise RuntimeReconciliationPreflightError("physical paths must be absolute")
    return result


def _current_counts(path: Path, repository: str, inventory_digest: str) -> tuple[int, int, int]:
    """Query-only counts for the exact recorded inventory digest."""
    conn = _ro(path)
    try:
        reports = int(conn.execute(
            "SELECT COUNT(*) FROM reconciliation_report WHERE repository=? AND inventory_digest=?",
            (repository, inventory_digest),
        ).fetchone()[0])
        receipts = int(conn.execute(
            "SELECT COUNT(*) FROM convergence_receipt WHERE repository=? AND inventory_digest=?",
            (repository, inventory_digest),
        ).fetchone()[0])
        consumed = int(conn.execute(
            "SELECT COUNT(*) FROM convergence_receipt WHERE repository=? AND inventory_digest=? AND consumed<>0",
            (repository, inventory_digest),
        ).fetchone()[0])
        return reports, receipts, consumed
    finally:
        conn.close()


def observe_runtime_reconciliation_preflight(
    config: RuntimeReconciliationPreflightConfig,
    *,
    physical_paths: Mapping[str, Path] | None = None,
) -> RuntimeReconciliationPreflightResult:
    config.validate()
    paths = _resolve_paths(physical_paths)
    runtime_root = str(paths["reconciliation"].parent)

    required_names = ("status", "coordination", "reconciliation", "trust", "inventory")
    present = {name: paths[name].is_file() for name in required_names}
    required_sources_present = all(present.values())
    execution_present, execution_stable = _execution_receipt_state(paths["execution_receipt"])

    inventory_state = "CONFLICTING"
    reconciliation_state = "CONFLICTING"
    runtime_source_healthy = False

    inventory_id = None
    inventory_revision = None
    inventory_digest = None
    inventory_default_head = None
    inventory_observed_at = None
    recorded_head_digest = None
    report_count = None
    receipt_count = None
    receipt_consumed_count = None
    source_instance = None
    source_id = None
    source_impl = None
    trust_anchor = None
    status_stable = None
    status_event_chain = None
    status_receipt_chain = None
    coordination_stable = None
    coordination_event_chain = None
    reconciliation_stable = None

    if not present["inventory"]:
        inventory_state = "MISSING"

    inventory = None
    trust = None
    observation_master = None
    trust_valid = False
    inventory_valid = False
    try:
        if present["trust"]:
            trust_raw = _stable_bytes(paths["trust"], "reconciliation trust")
            trust = _load_trust(trust_raw, source_instance_id=config.source_instance)
            source_instance = trust.source_instance_id
            source_id = trust.source_id
            source_impl = trust.source_implementation_digest
            trust_anchor = trust.trust_anchor_id
            trust_valid = True
        if present["inventory"] and trust_valid:
            inventory_raw = _stable_bytes(paths["inventory"], "repository inventory")
            try:
                raw_value = json.loads(inventory_raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeReconciliationPreflightError("repository inventory JSON invalid") from exc
            if not isinstance(raw_value, dict):
                raise RuntimeReconciliationPreflightError("repository inventory must be object")
            observation_master = raw_value.get("default_head_sha")
            if not isinstance(observation_master, str):
                raise RuntimeReconciliationPreflightError("repository inventory default head missing")
            observation = _load_observation(
                inventory_raw,
                repository=config.repository,
                current_master=observation_master,
            )
            inventory = _build_inventory(observation, trust)
            inventory_id = inventory.inventory_id
            inventory_revision = inventory.inventory_revision
            inventory_digest = inventory.inventory_digest
            inventory_default_head = inventory.default_head_sha
            inventory_observed_at = inventory.observed_at
            inventory_valid = True
            inventory_state = "CURRENT" if observation_master == config.current_master else "STALE"
    except (RuntimeReconciliationIngestionError, RuntimeReconciliationPreflightError, ValueError):
        if inventory_state != "MISSING":
            inventory_state = "CONFLICTING"

    status_ok = False
    coordination_ok = False
    reconciliation_ok = False
    head = None

    try:
        if present["status"]:
            status = _read_status(str(paths["status"]))
            status_stable = bool(status.get("stable"))
            status_event_chain = bool(status.get("event_chain"))
            status_receipt_chain = bool(status.get("receipt_chain"))
            status_ok = bool(status_stable and status_event_chain and status_receipt_chain)
        if present["coordination"]:
            coordination = _read_coordination(str(paths["coordination"]))
            coordination_stable = bool(coordination.get("stable"))
            coordination_event_chain = bool(coordination.get("event_chain"))
            coordination_ok = bool(coordination_stable and coordination_event_chain)
        if present["reconciliation"]:
            raw_state = _read_state(paths["reconciliation"], config.repository)
            head = raw_state.get("head")
            if head is not None:
                recorded_head_digest = str(head.get("inventory_digest"))
                report_count, receipt_count, receipt_consumed_count = _current_counts(
                    paths["reconciliation"],
                    config.repository,
                    recorded_head_digest,
                )
                recon = _read_reconciliation(
                    str(paths["reconciliation"]),
                    config.repository,
                    str(head.get("default_head_sha")),
                )
                reconciliation_stable = bool(recon.get("stable"))
                reconciliation_ok = bool(reconciliation_stable)
            else:
                reconciliation_stable = True
                reconciliation_ok = True
    except (RuntimeSnapshotSourceError, RuntimeReconciliationIngestionError, sqlite3.Error, ValueError, TypeError):
        reconciliation_ok = False

    runtime_source_healthy = bool(
        required_sources_present
        and trust_valid
        and inventory_valid
        and status_ok
        and coordination_ok
        and reconciliation_ok
        and execution_stable
    )

    if inventory_state == "CURRENT":
        if not runtime_source_healthy:
            inventory_state = "CONFLICTING"
        elif head is None:
            inventory_state = "MISSING"
        else:
            expected_head = {
                "repository": inventory.repository,
                "inventory_id": inventory.inventory_id,
                "inventory_revision": inventory.inventory_revision,
                "inventory_digest": inventory.inventory_digest,
                "default_head_sha": inventory.default_head_sha,
                "observed_at": inventory.observed_at,
            }
            actual_head = {key: head.get(key) for key in expected_head}
            if actual_head != expected_head:
                inventory_state = "CONFLICTING"

    if execution_present:
        reconciliation_state = "EXECUTION_ALREADY_RECORDED" if execution_stable else "CONFLICTING"
    elif not present["reconciliation"] or not reconciliation_ok:
        reconciliation_state = "CONFLICTING"
    elif head is None:
        reconciliation_state = "CLEAN_PRE_EXECUTION"
    elif report_count is None or receipt_count is None or receipt_consumed_count is None:
        reconciliation_state = "CONFLICTING"
    elif receipt_count > 0:
        reconciliation_state = "RECEIPT_ALREADY_PRESENT"
    elif report_count > 0:
        reconciliation_state = "REPORT_ALREADY_PRESENT"
    elif report_count == 0 and receipt_count == 0 and receipt_consumed_count == 0:
        reconciliation_state = "CLEAN_PRE_EXECUTION"
    else:
        reconciliation_state = "CONFLICTING"

    # A receipt without a report, multiple reports/receipts for one exact inventory,
    # or consumed-count exceeding receipt-count is structurally conflicting.
    if (
        report_count is not None
        and receipt_count is not None
        and receipt_consumed_count is not None
        and (receipt_count > report_count or report_count > 1 or receipt_count > 1 or receipt_consumed_count > receipt_count)
    ):
        reconciliation_state = "CONFLICTING"

    f005_q_admissible = bool(
        required_sources_present
        and runtime_source_healthy
        and inventory_state == "CURRENT"
        and reconciliation_state == "CLEAN_PRE_EXECUTION"
        and execution_present is False
    )
    next_step = (
        "RUN_F005_Q" if f005_q_admissible
        else "REFRESH_F005_J" if inventory_state in {"STALE", "MISSING"}
        else "DENY"
    )

    return RuntimeReconciliationPreflightResult.build(
        schema_version="1.0.0",
        repository=config.repository,
        current_master=config.current_master,
        current_master_tree=config.current_master_tree,
        runtime_root=runtime_root,
        required_sources_present=required_sources_present,
        runtime_source_healthy=runtime_source_healthy,
        inventory_state=inventory_state,
        reconciliation_state=reconciliation_state,
        f005_q_admissible=f005_q_admissible,
        next_step=next_step,
        inventory_id=inventory_id,
        inventory_revision=inventory_revision,
        inventory_digest=inventory_digest,
        inventory_default_head=inventory_default_head,
        inventory_observed_at=inventory_observed_at,
        recorded_head_digest=recorded_head_digest,
        report_count=report_count,
        receipt_count=receipt_count,
        receipt_consumed_count=receipt_consumed_count,
        execution_receipt_present=execution_present,
        reconciliation_source_instance=source_instance,
        reconciliation_source_id=source_id,
        reconciliation_source_implementation_digest=source_impl,
        reconciliation_trust_anchor_id=trust_anchor,
        status_stable=status_stable,
        status_event_chain_valid=status_event_chain,
        status_receipt_chain_valid=status_receipt_chain,
        coordination_stable=coordination_stable,
        coordination_event_chain_valid=coordination_event_chain,
        reconciliation_stable=reconciliation_stable,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F005-Q read-only runtime reconciliation preflight")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--expected-master", required=True)
    parser.add_argument("--expected-master-tree", required=True)
    args = parser.parse_args(argv)
    config = RuntimeReconciliationPreflightConfig(
        repository=args.repository,
        current_master=args.expected_master,
        current_master_tree=args.expected_master_tree,
    ).validate()
    result = observe_runtime_reconciliation_preflight(config)
    print(json.dumps(asdict(result), sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Strictly read-only F005-Q runtime reconciliation preflight observer."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
import stat
from typing import Any, Mapping

from cyber_lion.contracts.fleet_reconciliation import RECEIPT_PURPOSE
from cyber_lion.contracts.fleet_runtime_paths import resolve_fleet_runtime_paths
from cyber_lion.contracts.fleet_runtime_reconciliation_execution import (
    LEGACY_EXECUTION_RECEIPT_FILENAME,
    RuntimeReconciliationExecutionReceipt,
    execution_epoch_receipt_filename,
)
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
    "status", "coordination", "reconciliation", "trust", "inventory", "execution_receipt"
})
_HEAD_COLUMNS = (
    "repository", "inventory_id", "inventory_revision", "inventory_digest", "default_head_sha", "observed_at"
)
_EPOCH_RECEIPT_PREFIX = "reconciliation-execution-receipt."
_EPOCH_RECEIPT_SUFFIX = ".json"


def _file_present(path: Path, name: str) -> bool:
    if not path.is_absolute():
        raise RuntimeReconciliationPreflightError(f"{name} path must be absolute")
    try:
        info = path.stat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise RuntimeReconciliationPreflightError(f"{name} observation failed") from exc
    return stat.S_ISREG(info.st_mode)


def _presence_map(paths: Mapping[str, Path], names: tuple[str, ...]) -> dict[str, bool | None]:
    result: dict[str, bool | None] = {}
    for name in names:
        try:
            result[name] = _file_present(paths[name], name)
        except RuntimeReconciliationPreflightError:
            result[name] = None
    return result


def _stable_bytes(path: Path, name: str) -> bytes:
    if not path.is_absolute():
        raise RuntimeReconciliationPreflightError(f"{name} path must be absolute")
    try:
        before = path.stat()
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeReconciliationPreflightError(f"{name} unavailable")
        raw_first = path.read_bytes()
        middle = path.stat()
        raw_second = path.read_bytes()
        after = path.stat()
    except FileNotFoundError as exc:
        raise RuntimeReconciliationPreflightError(f"{name} changed during observation") from exc
    except OSError as exc:
        raise RuntimeReconciliationPreflightError(f"{name} observation failed") from exc

    def identity(info: os.stat_result) -> tuple[int, int, int, int]:
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)

    if identity(before) != identity(middle) or identity(middle) != identity(after) or raw_first != raw_second:
        raise RuntimeReconciliationPreflightError(f"{name} changed during observation")
    if not raw_first or len(raw_first) > _MAX_BYTES:
        raise RuntimeReconciliationPreflightError(f"{name} size invalid")
    return raw_first


def _load_execution_receipt(path: Path, name: str) -> RuntimeReconciliationExecutionReceipt:
    try:
        raw = _stable_bytes(path, name)
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("execution receipt must be object")
        return RuntimeReconciliationExecutionReceipt(**value).validate()
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise RuntimeReconciliationPreflightError(f"{name} invalid") from exc


def _receipt_binds_inventory(receipt: RuntimeReconciliationExecutionReceipt, inventory: object) -> bool:
    return bool(
        receipt.repository == getattr(inventory, "repository", None)
        and receipt.inventory_id == getattr(inventory, "inventory_id", None)
        and receipt.inventory_revision == getattr(inventory, "inventory_revision", None)
        and receipt.inventory_digest == getattr(inventory, "inventory_digest", None)
    )


def _execution_receipt_snapshot(runtime_root: Path, legacy_path: Path) -> tuple[tuple[str, bytes], ...]:
    if not runtime_root.is_absolute() or not runtime_root.is_dir():
        raise RuntimeReconciliationPreflightError("runtime root unavailable")
    entries: list[tuple[str, bytes]] = []
    if legacy_path.exists():
        entries.append((LEGACY_EXECUTION_RECEIPT_FILENAME, _stable_bytes(legacy_path, "legacy runtime execution receipt")))
    try:
        candidates = sorted(runtime_root.glob(f"{_EPOCH_RECEIPT_PREFIX}*{_EPOCH_RECEIPT_SUFFIX}"), key=lambda item: item.name)
    except OSError as exc:
        raise RuntimeReconciliationPreflightError("execution receipt set observation failed") from exc
    for path in candidates:
        if path.name == LEGACY_EXECUTION_RECEIPT_FILENAME:
            continue
        entries.append((path.name, _stable_bytes(path, f"epoch execution receipt {path.name}")))
    return tuple(entries)


def _classify_execution_receipts(
    snapshot: tuple[tuple[str, bytes], ...],
    inventory: object,
) -> tuple[bool, bool]:
    """Return (current_epoch_present, conflict). All receipts are validated."""
    current_count = 0
    for filename, raw in snapshot:
        try:
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("execution receipt must be object")
            receipt = RuntimeReconciliationExecutionReceipt(**value).validate()
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            return False, True
        if filename != LEGACY_EXECUTION_RECEIPT_FILENAME:
            expected_name = execution_epoch_receipt_filename(
                repository=receipt.repository,
                inventory_id=receipt.inventory_id,
                inventory_revision=receipt.inventory_revision,
                inventory_digest=receipt.inventory_digest,
            )
            if filename != expected_name:
                return False, True
        if _receipt_binds_inventory(receipt, inventory):
            current_count += 1
    if current_count > 1:
        return False, True
    return current_count == 1, False


def _production_paths() -> dict[str, Path]:
    logical = resolve_fleet_runtime_paths()
    reconciliation = Path(logical.reconciliation_db_path)
    return {
        "status": Path(logical.status_db_path),
        "coordination": Path(logical.coordination_db_path),
        "reconciliation": reconciliation,
        "trust": Path(logical.reconciliation_trust_path),
        "inventory": Path(logical.repository_inventory_path),
        "execution_receipt": reconciliation.with_name(LEGACY_EXECUTION_RECEIPT_FILENAME),
    }


def _resolve_paths(physical_paths: Mapping[str, Path] | None) -> dict[str, Path]:
    if physical_paths is None:
        if os.name != "nt":
            raise RuntimeReconciliationPreflightError("production preflight requires Windows lion-runtime")
        return _production_paths()
    if set(physical_paths) != _REQUIRED_PHYSICAL_KEYS:
        raise RuntimeReconciliationPreflightError("physical path mapping incomplete")
    result = {name: Path(path) for name, path in physical_paths.items()}
    if any(not path.is_absolute() for path in result.values()):
        raise RuntimeReconciliationPreflightError("physical paths must be absolute")
    return result


def _row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if row is None else dict(row)


def _bounded_reconciliation_state(path: Path, repository: str) -> dict[str, Any]:
    conn = _ro(path)
    try:
        head = _row_dict(conn.execute(
            "SELECT repository,inventory_id,inventory_revision,inventory_digest,default_head_sha,observed_at "
            "FROM reconciliation_inventory_head WHERE repository=?", (repository,)
        ).fetchone())
        if head is None:
            report_rows = conn.execute(
                "SELECT report_digest,report_id,repository,inventory_id,inventory_revision,inventory_digest,"
                "closure_preconditions_digest,default_head_sha,disposition,observed_at "
                "FROM reconciliation_report WHERE repository=? ORDER BY report_digest,report_id", (repository,)
            ).fetchall()
            receipt_rows = conn.execute(
                "SELECT receipt_digest,receipt_id,report_digest,repository,inventory_id,inventory_revision,"
                "inventory_digest,closure_preconditions_digest,default_head_sha,issued_at,purpose,consumed "
                "FROM convergence_receipt WHERE repository=? ORDER BY receipt_digest,receipt_id", (repository,)
            ).fetchall()
        else:
            digest = str(head["inventory_digest"])
            report_rows = conn.execute(
                "SELECT report_digest,report_id,repository,inventory_id,inventory_revision,inventory_digest,"
                "closure_preconditions_digest,default_head_sha,disposition,observed_at "
                "FROM reconciliation_report WHERE repository=? AND inventory_digest=? ORDER BY report_digest,report_id",
                (repository, digest),
            ).fetchall()
            receipt_rows = conn.execute(
                "SELECT receipt_digest,receipt_id,report_digest,repository,inventory_id,inventory_revision,"
                "inventory_digest,closure_preconditions_digest,default_head_sha,issued_at,purpose,consumed "
                "FROM convergence_receipt WHERE repository=? AND inventory_digest=? ORDER BY receipt_digest,receipt_id",
                (repository, digest),
            ).fetchall()
        reports = tuple(dict(row) for row in report_rows)
        receipts = tuple(dict(row) for row in receipt_rows)
        consumed_count = sum(int(row.get("consumed", 0)) != 0 for row in receipts)
        return {
            "head": head,
            "reports": reports,
            "receipts": receipts,
            "report_count": len(reports),
            "receipt_count": len(receipts),
            "receipt_consumed_count": consumed_count,
        }
    finally:
        conn.close()


def _head_equal(left: object, right: object) -> bool:
    return isinstance(left, dict) and isinstance(right, dict) and all(left.get(name) == right.get(name) for name in _HEAD_COLUMNS)


def _report_matches_head(report: Mapping[str, Any], head: Mapping[str, Any]) -> bool:
    return bool(
        report.get("repository") == head.get("repository")
        and report.get("inventory_id") == head.get("inventory_id")
        and int(report.get("inventory_revision", -1)) == int(head.get("inventory_revision", -2))
        and report.get("inventory_digest") == head.get("inventory_digest")
        and report.get("default_head_sha") == head.get("default_head_sha")
        and isinstance(report.get("closure_preconditions_digest"), str)
        and report.get("disposition") in {"CONVERGED", "RECONCILIATION_REQUIRED"}
    )


def _receipt_matches_head(receipt: Mapping[str, Any], head: Mapping[str, Any], reports: tuple[dict[str, Any], ...]) -> bool:
    report_by_digest = {str(report.get("report_digest")): report for report in reports}
    report = report_by_digest.get(str(receipt.get("report_digest")))
    if report is None:
        return False
    consumed = receipt.get("consumed")
    return bool(
        consumed in {0, 1}
        and receipt.get("repository") == head.get("repository")
        and receipt.get("inventory_id") == head.get("inventory_id")
        and int(receipt.get("inventory_revision", -1)) == int(head.get("inventory_revision", -2))
        and receipt.get("inventory_digest") == head.get("inventory_digest")
        and receipt.get("default_head_sha") == head.get("default_head_sha")
        and receipt.get("closure_preconditions_digest") == report.get("closure_preconditions_digest")
        and receipt.get("purpose") == RECEIPT_PURPOSE
    )


def _structural_reconciliation_conflict(state: Mapping[str, Any], canonical: Mapping[str, Any] | None) -> bool:
    head = state.get("head")
    reports = state.get("reports")
    receipts = state.get("receipts")
    if not isinstance(reports, tuple) or not isinstance(receipts, tuple):
        return True
    report_count = int(state.get("report_count", -1))
    receipt_count = int(state.get("receipt_count", -1))
    consumed_count = int(state.get("receipt_consumed_count", -1))
    if report_count != len(reports) or receipt_count != len(receipts):
        return True
    if report_count > 1 or receipt_count > 1 or receipt_count > report_count or consumed_count > receipt_count:
        return True
    if head is None:
        return bool(reports or receipts)
    if not isinstance(head, dict):
        return True
    if any(not _report_matches_head(report, head) for report in reports):
        return True
    if any(not _receipt_matches_head(receipt, head, reports) for receipt in receipts):
        return True
    if canonical is None or not _head_equal(canonical.get("head"), head):
        return True
    canonical_report = canonical.get("report")
    canonical_receipt = canonical.get("receipt")
    if report_count == 0 and canonical_report is not None:
        return True
    if report_count == 1:
        if not isinstance(canonical_report, dict) or canonical_report.get("report_digest") != reports[0].get("report_digest") or not canonical.get("report_bound"):
            return True
    if receipt_count == 0 and canonical_receipt is not None:
        return True
    if receipt_count == 1:
        if not isinstance(canonical_receipt, dict) or canonical_receipt.get("receipt_digest") != receipts[0].get("receipt_digest"):
            return True
        if int(receipts[0].get("consumed", 0)) == 0 and not canonical.get("receipt_bound"):
            return True
    return False


def observe_runtime_reconciliation_preflight(
    config: RuntimeReconciliationPreflightConfig,
    *,
    physical_paths: Mapping[str, Path] | None = None,
) -> RuntimeReconciliationPreflightResult:
    config.validate()
    paths = _resolve_paths(physical_paths)
    runtime_root_path = paths["reconciliation"].parent
    runtime_root = str(runtime_root_path)
    required_names = ("status", "coordination", "reconciliation", "trust", "inventory")
    presence_before = _presence_map(paths, required_names)

    inventory_id = inventory_revision = inventory_digest = inventory_default_head = inventory_observed_at = None
    recorded_head_digest = report_count = receipt_count = receipt_consumed_count = None
    source_instance = source_id = source_impl = trust_anchor = None
    status_stable = status_event_chain = status_receipt_chain = None
    coordination_stable = coordination_event_chain = None
    reconciliation_stable = None
    trust_valid = inventory_valid = False
    inventory = trust = None
    trust_read_conflict = inventory_read_conflict = False

    if presence_before.get("trust") is True:
        try:
            trust = _load_trust(_stable_bytes(paths["trust"], "reconciliation trust"), source_instance_id=config.source_instance)
            source_instance, source_id = trust.source_instance_id, trust.source_id
            source_impl, trust_anchor = trust.source_implementation_digest, trust.trust_anchor_id
            trust_valid = True
        except (RuntimeReconciliationIngestionError, RuntimeReconciliationPreflightError, ValueError):
            trust_read_conflict = True

    if presence_before.get("inventory") is True and trust_valid:
        try:
            inventory_raw = _stable_bytes(paths["inventory"], "repository inventory")
            raw_value = json.loads(inventory_raw.decode("utf-8"))
            if not isinstance(raw_value, dict) or not isinstance(raw_value.get("default_head_sha"), str):
                raise RuntimeReconciliationPreflightError("repository inventory invalid")
            observation = _load_observation(inventory_raw, repository=config.repository, current_master=raw_value["default_head_sha"])
            inventory = _build_inventory(observation, trust)
            inventory_id = inventory.inventory_id
            inventory_revision = inventory.inventory_revision
            inventory_digest = inventory.inventory_digest
            inventory_default_head = inventory.default_head_sha
            inventory_observed_at = inventory.observed_at
            inventory_valid = True
        except (UnicodeDecodeError, json.JSONDecodeError, RuntimeReconciliationIngestionError, RuntimeReconciliationPreflightError, ValueError):
            inventory_read_conflict = True

    receipt_snapshot_before: tuple[tuple[str, bytes], ...] | None = None
    receipt_snapshot_after: tuple[tuple[str, bytes], ...] | None = None
    execution_present: bool | None = None
    execution_stable = False
    execution_conflict = False
    if inventory_valid and inventory is not None:
        try:
            receipt_snapshot_before = _execution_receipt_snapshot(runtime_root_path, paths["execution_receipt"])
            execution_present, execution_conflict = _classify_execution_receipts(receipt_snapshot_before, inventory)
        except RuntimeReconciliationPreflightError:
            execution_conflict = True

    status_ok = coordination_ok = reconciliation_ok = False
    structural_conflict = reconciliation_race = False
    head: dict[str, Any] | None = None
    canonical_reconciliation = before_reconciliation = after_reconciliation = None
    try:
        if presence_before.get("status") is True:
            status = _read_status(str(paths["status"]))
            status_stable = bool(status.get("stable"))
            status_event_chain = bool(status.get("event_chain"))
            status_receipt_chain = bool(status.get("receipt_chain"))
            status_ok = bool(status_stable and status_event_chain and status_receipt_chain)
        if presence_before.get("coordination") is True:
            coordination = _read_coordination(str(paths["coordination"]))
            coordination_stable = bool(coordination.get("stable"))
            coordination_event_chain = bool(coordination.get("event_chain"))
            coordination_ok = bool(coordination_stable and coordination_event_chain)
        if presence_before.get("reconciliation") is True:
            before_reconciliation = _bounded_reconciliation_state(paths["reconciliation"], config.repository)
            before_head = before_reconciliation.get("head")
            if isinstance(before_head, dict):
                canonical_reconciliation = _read_reconciliation(str(paths["reconciliation"]), config.repository, str(before_head.get("default_head_sha")))
                reconciliation_stable = bool(canonical_reconciliation.get("stable"))
            else:
                reconciliation_stable = True
            after_reconciliation = _bounded_reconciliation_state(paths["reconciliation"], config.repository)
            reconciliation_race = before_reconciliation != after_reconciliation
            if canonical_reconciliation is not None and isinstance(before_head, dict):
                reconciliation_race = reconciliation_race or not _head_equal(canonical_reconciliation.get("head"), before_head)
            reconciliation_ok = bool(reconciliation_stable and not reconciliation_race)
            if reconciliation_ok:
                head = before_head if isinstance(before_head, dict) else None
                report_count = int(before_reconciliation["report_count"])
                receipt_count = int(before_reconciliation["receipt_count"])
                receipt_consumed_count = int(before_reconciliation["receipt_consumed_count"])
                recorded_head_digest = None if head is None else str(head.get("inventory_digest"))
                structural_conflict = _structural_reconciliation_conflict(before_reconciliation, canonical_reconciliation)
    except (RuntimeSnapshotSourceError, RuntimeReconciliationIngestionError, RuntimeReconciliationPreflightError, sqlite3.Error, ValueError, TypeError):
        reconciliation_ok = False
        reconciliation_race = True

    if inventory_valid and inventory is not None and receipt_snapshot_before is not None:
        try:
            receipt_snapshot_after = _execution_receipt_snapshot(runtime_root_path, paths["execution_receipt"])
            execution_stable = receipt_snapshot_before == receipt_snapshot_after
        except RuntimeReconciliationPreflightError:
            execution_stable = False
    else:
        execution_stable = False

    presence_after = _presence_map(paths, required_names)
    presence_error = any(value is None for value in presence_before.values()) or any(value is None for value in presence_after.values())
    presence_race = any(presence_before.get(name) != presence_after.get(name) for name in required_names)
    required_sources_present = all(presence_before.get(name) is True and presence_after.get(name) is True for name in required_names)

    source_conflict = bool(
        presence_error or presence_race or not execution_stable or execution_conflict
        or presence_before.get("trust") is not True or not trust_valid or trust_read_conflict
        or presence_before.get("status") is not True or not status_ok
        or presence_before.get("coordination") is not True or not coordination_ok
        or presence_before.get("reconciliation") is not True or not reconciliation_ok
        or reconciliation_race or structural_conflict
        or (presence_before.get("inventory") is True and (not inventory_valid or inventory_read_conflict))
    )

    expected_head = actual_head = None
    if inventory_valid and inventory is not None:
        expected_head = {
            "repository": inventory.repository,
            "inventory_id": inventory.inventory_id,
            "inventory_revision": inventory.inventory_revision,
            "inventory_digest": inventory.inventory_digest,
            "default_head_sha": inventory.default_head_sha,
            "observed_at": inventory.observed_at,
        }
    if isinstance(head, dict) and expected_head is not None:
        actual_head = {key: head.get(key) for key in expected_head}

    canonical_inventory_missing = presence_before.get("inventory") is False and presence_after.get("inventory") is False
    recorded_head_missing = reconciliation_ok and head is None
    if source_conflict:
        inventory_state = "CONFLICTING"
    elif canonical_inventory_missing or recorded_head_missing:
        inventory_state = "MISSING"
    elif not required_sources_present or not inventory_valid or expected_head is None or actual_head != expected_head:
        inventory_state = "CONFLICTING"
    elif inventory.default_head_sha == config.current_master:
        inventory_state = "CURRENT"
    else:
        inventory_state = "STALE"

    runtime_source_healthy = bool(
        required_sources_present and trust_valid and inventory_valid and status_ok and coordination_ok
        and reconciliation_ok and execution_stable and not execution_conflict
        and not presence_error and not presence_race and not structural_conflict
    )

    if source_conflict or execution_present is None or not execution_stable:
        reconciliation_state = "CONFLICTING"
    elif execution_present:
        reconciliation_state = "EXECUTION_ALREADY_RECORDED"
    elif head is None:
        reconciliation_state = "CLEAN_PRE_EXECUTION"
    elif report_count == 0 and receipt_count == 0 and receipt_consumed_count == 0:
        reconciliation_state = "CLEAN_PRE_EXECUTION"
    elif report_count == 1 and receipt_count == 0 and receipt_consumed_count == 0:
        reconciliation_state = "REPORT_ALREADY_PRESENT"
    elif report_count == 1 and receipt_count == 1 and receipt_consumed_count in {0, 1}:
        reconciliation_state = "RECEIPT_ALREADY_PRESENT"
    else:
        reconciliation_state = "CONFLICTING"

    f005_q_admissible = bool(
        required_sources_present and runtime_source_healthy and inventory_state == "CURRENT"
        and reconciliation_state == "CLEAN_PRE_EXECUTION" and execution_present is False
    )
    next_step = "RUN_F005_Q" if f005_q_admissible else "REFRESH_F005_J" if inventory_state in {"STALE", "MISSING"} else "DENY"

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

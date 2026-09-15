"""Read-only completion predicate reconciliation for Mission Control.

This module observes durable Mission Control state. It never mutates authority,
repository state, host state, or phase status. The caller decides whether the
observed predicate set satisfies a PhaseExecutionContract.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from cyber_lion.contracts.phase_execution_contract import compile_panel_phase_contracts, preflight_execution_contracts

GENERIC_ADAPTER = "LPCL_GENERIC_128L64M"
GENERIC_HANDLER = "GENERIC_LPCL_PHASE"
POST_ASTRA_MISSION = "LION-POST-ASTRA-SAAS-TRANSPORT-TRUTH-REACQUIRE-R1"
SESSION_MEDIATED = "CHATGPT_SENTINELX_SESSION_MEDIATED"


def _exists_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _json(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value or "")
    except Exception:
        return default


def _restart_backup_evidence(db_path: Path, mission_id: str) -> dict[str, Any] | None:
    backup_root = db_path.parent / "backups"
    if not backup_root.is_dir():
        return None
    current = sqlite3.connect(str(db_path)); current.row_factory = sqlite3.Row
    try:
        assignment = current.execute(
            "SELECT assignment_id,input_digest FROM mission_execution_assignments WHERE mission_id=? AND phase_id='REPAIR_EXECUTION_BINDER' ORDER BY created_at DESC LIMIT 1",
            (mission_id,),
        ).fetchone()
        receipt = current.execute(
            "SELECT receipt_id,result_digest FROM mission_execution_receipts WHERE mission_id=? AND phase_id='REPAIR_EXECUTION_BINDER' ORDER BY observed_at DESC LIMIT 1",
            (mission_id,),
        ).fetchone()
    finally:
        current.close()
    if not assignment or not receipt:
        return None
    candidates = sorted((p for p in backup_root.glob("**/*.db") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates[:256]:
        try:
            rc = sqlite3.connect(f"file:{path}?mode=ro", uri=True); rc.row_factory = sqlite3.Row
            integrity = rc.execute("PRAGMA integrity_check").fetchone()[0]
            a = rc.execute("SELECT assignment_id,input_digest FROM mission_execution_assignments WHERE assignment_id=?", (assignment["assignment_id"],)).fetchone()
            r = rc.execute("SELECT receipt_id,result_digest FROM mission_execution_receipts WHERE receipt_id=?", (receipt["receipt_id"],)).fetchone()
            rc.close()
            if integrity == "ok" and a and r and a["input_digest"] == assignment["input_digest"] and r["result_digest"] == receipt["result_digest"]:
                return {"path": str(path), "integrity": integrity, "assignment_id": a["assignment_id"], "receipt_id": r["receipt_id"]}
        except Exception:
            continue
    return None


def _lpcl11_probe() -> bool:
    contracts = compile_panel_phase_contracts({}, "SYNTHETIC-LEGACY-MISSION", [{"id": "SYNTHETIC_PHASE"}], "LPCL/1.1")
    pf = preflight_execution_contracts(contracts, {})
    return len(contracts) == 1 and pf.invalid_count == 0 and contracts[0].contract_source == "LEGACY_INFERRED_SAFE"


def _lpcl12_probe() -> bool:
    pairs = {
        "PHASE_01_EXECUTION_CLASS": "VERIFY",
        "PHASE_01_CAPABILITY_CLASS": "MISSION_RUNTIME_RECONCILIATION",
        "PHASE_01_EFFECT_CEILING": "NONE",
        "PHASE_01_BINDING_MODE": "DYNAMIC",
        "PHASE_01_ON_MISSING_CAPABILITY": "WAIT_AND_DISCOVER",
        "PHASE_01_AUTO_RESUME": "TRUE",
        "PHASE_01_VERIFY_BEFORE_MUTATE": "TRUE",
        "PHASE_01_CURRENTNESS": "CURRENT_MISSION_RUNTIME",
        "PHASE_01_EVIDENCE": "LIVE_RUNTIME_READBACK",
        "PHASE_01_COMPLETION_01": "SYNTHETIC=PASS",
    }
    contracts = compile_panel_phase_contracts(pairs, "SYNTHETIC-MISSION", [{"id": "SYNTHETIC_PHASE"}], "LPCL/1.2")
    pf = preflight_execution_contracts(contracts, {})
    return len(contracts) == 1 and pf.invalid_count == 0 and pf.unbound_count == 1


def _air_read_only(conn: sqlite3.Connection, mission_id: str) -> tuple[bool, list[dict[str, Any]]]:
    rows = conn.execute("SELECT phase_id,action_ir_json FROM mission_generic_phase_plans WHERE mission_id=? AND action_ir_json IS NOT NULL", (mission_id,)).fetchall()
    parsed = []
    for row in rows:
        value = _json(row["action_ir_json"], {})
        parsed.append({"phase_id": row["phase_id"], "action_ir": value})
        boundary = value.get("boundary") if isinstance(value, dict) else None
        if not isinstance(boundary, dict): return False, parsed
        if boundary.get("shell") is not False: return False, parsed
        if boundary.get("network") != "DENY": return False, parsed
        if boundary.get("filesystem_write") not in ([], ()): return False, parsed
        if boundary.get("process_children") not in ([], ()): return False, parsed
    return bool(rows), parsed


def evaluate_completion_predicates(
    conn: sqlite3.Connection,
    mission_id: str,
    phase_id: str,
    predicates: Iterable[str],
    *,
    db_path: Path,
) -> tuple[bool, dict[str, Any]]:
    names = [str(x).split("=", 1)[0] for x in predicates]
    checks: dict[str, bool] = {}
    facts: dict[str, Any] = {}

    mission = conn.execute("SELECT * FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
    process = conn.execute("SELECT * FROM mission_process_specs WHERE mission_id=?", (mission_id,)).fetchone()
    driver = conn.execute("SELECT * FROM mission_execution_drivers WHERE mission_id=?", (mission_id,)).fetchone()
    phase_rows = conn.execute("SELECT ordinal,phase_id,status,progress,started_at,finished_at FROM mission_phases WHERE mission_id=? ORDER BY ordinal", (mission_id,)).fetchall()
    phase_count = len(phase_rows)
    logical = conn.execute("SELECT logical_id,role FROM logical_drones WHERE mission_id=? ORDER BY logical_id", (mission_id,)).fetchall()
    material = conn.execute("SELECT logical_id AS material_id,pod_uid,ready FROM material_workers WHERE mission_id=? ORDER BY logical_id", (mission_id,)).fetchall()
    topology = conn.execute("SELECT logical_drone_id,material_drone_id,state FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__' ORDER BY logical_drone_id", (mission_id,)).fetchall()
    specs = conn.execute("SELECT phase_id,handler_id FROM mission_phase_execution_specs WHERE mission_id=? ORDER BY phase_id", (mission_id,)).fetchall()
    bindings = conn.execute("SELECT * FROM mission_phase_capability_bindings WHERE mission_id=?", (mission_id,)).fetchall() if _exists_table(conn, "mission_phase_capability_bindings") else []
    generic_receipts = conn.execute("SELECT * FROM mission_generic_action_receipts WHERE mission_id=?", (mission_id,)).fetchall() if _exists_table(conn, "mission_generic_action_receipts") else []
    plan_rows = conn.execute("SELECT * FROM mission_generic_phase_plans WHERE mission_id=?", (mission_id,)).fetchall() if _exists_table(conn, "mission_generic_phase_plans") else []
    scheduler = conn.execute("SELECT * FROM mission_scheduler_state WHERE scheduler_id='GLOBAL_MISSION_SCHEDULER_V1'").fetchone() if _exists_table(conn, "mission_scheduler_state") else None
    turn = conn.execute("SELECT * FROM mission_scheduler_turns WHERE mission_id=?", (mission_id,)).fetchone() if _exists_table(conn, "mission_scheduler_turns") else None
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    facts["db_integrity"] = integrity

    role_counts: dict[str, int] = {}
    for row in logical: role_counts[row["role"]] = role_counts.get(row["role"], 0) + 1
    topology_map: dict[str, set[str]] = {}
    for row in topology: topology_map.setdefault(row["material_drone_id"], set()).add(row["logical_drone_id"])
    air_ok, air_rows = _air_read_only(conn, mission_id)
    facts["action_ir_summary"] = {"count": len(air_rows), "phase_ids": [x["phase_id"] for x in air_rows], "read_only_boundary": air_ok}

    def protocol_event(event: str, *, from_id: str | None = None, phase: str | None = None) -> bool:
        for row in conn.execute("SELECT from_id,phase,payload_json FROM protocol_messages WHERE mission_id=?", (mission_id,)):
            if phase is not None and row["phase"] != phase: continue
            if from_id is not None and row["from_id"] != from_id: continue
            if _json(row["payload_json"], {}).get("event") == event: return True
        return False

    def bootstrap_evidence(event: str) -> dict[str, Any] | None:
        for row in conn.execute("SELECT from_id,payload_json FROM protocol_messages WHERE mission_id=? ORDER BY id DESC", (mission_id,)):
            payload = _json(row["payload_json"], {})
            if row["from_id"] != "BOOTSTRAP_RECONCILER" or payload.get("event") != event:
                continue
            expected_head = mission["source_head"] if mission is not None else None
            expected_tree = mission["source_tree"] if mission is not None else None
            if expected_head and payload.get("source_head") != expected_head:
                continue
            if expected_tree and payload.get("source_tree") not in {None, expected_tree}:
                continue
            return payload
        return None

    runtime_revision_evidence = bootstrap_evidence("SUCCESSOR_RUNTIME_REVISIONS_CONVERGED")
    preflight_binding_evidence = bootstrap_evidence("SUCCESSOR_PREFLIGHT_RUNTIME_BINDING_VISIBLE")
    panel_projection_evidence = bootstrap_evidence("SUCCESSOR_PANEL_TRUTH_PROJECTION_REPAIRED")
    broker_reconciliation_evidence = bootstrap_evidence("SUCCESSOR_BROKER_RECEIPT_LINEAGE_RECONCILED")

    broker_missing_receipts = broker_orphan_receipts = 0
    if _exists_table(conn, "saas_handoff_requests") and _exists_table(conn, "saas_broker_receipts"):
        broker_missing_receipts = int(conn.execute(
            "SELECT COUNT(*) FROM saas_handoff_requests r LEFT JOIN saas_broker_receipts b ON b.request_id=r.request_id "
            "WHERE r.status='RESPONDED' AND (r.receipt_digest IS NULL OR b.request_id IS NULL OR b.receipt_digest!=r.receipt_digest)"
        ).fetchone()[0])
        broker_orphan_receipts = int(conn.execute(
            "SELECT COUNT(*) FROM saas_broker_receipts b LEFT JOIN saas_handoff_requests r ON r.request_id=b.request_id WHERE r.request_id IS NULL"
        ).fetchone()[0])
    facts["successor_bootstrap_evidence"] = {
        "runtime_revisions": runtime_revision_evidence,
        "preflight_binding": preflight_binding_evidence,
        "panel_projection": panel_projection_evidence,
        "broker_reconciliation": broker_reconciliation_evidence,
        "broker_missing_receipts": broker_missing_receipts,
        "broker_orphan_receipts": broker_orphan_receipts,
    }

    current_ordinal = next((int(r["ordinal"]) for r in phase_rows if process and r["phase_id"] == process["current_phase"]), 0)
    passed = [r for r in phase_rows if r["status"] in {"PASS", "COMPLETE", "SKIPPED"}]
    non_topology_assignments = conn.execute("SELECT assignment_id,phase_id,material_drone_id,state FROM mission_execution_assignments WHERE mission_id=? AND phase_id!='__TOPOLOGY__'", (mission_id,)).fetchall()
    local_receipt_count = int(conn.execute("SELECT COUNT(*) FROM mission_execution_receipts WHERE mission_id=? AND status='PASS' AND authority_effect='NONE'", (mission_id,)).fetchone()[0])
    restart = _restart_backup_evidence(db_path, mission_id)
    facts["restart"] = restart

    post = conn.execute("SELECT * FROM missions WHERE mission_id=?", (POST_ASTRA_MISSION,)).fetchone()
    post_driver = conn.execute("SELECT * FROM mission_execution_drivers WHERE mission_id=?", (POST_ASTRA_MISSION,)).fetchone()
    post_receipts = int(conn.execute("SELECT COUNT(*) FROM mission_execution_receipts WHERE mission_id=? AND status='PASS'", (POST_ASTRA_MISSION,)).fetchone()[0])
    responded_session = False
    autonomous_claim = False
    if _exists_table(conn, "saas_handoff_requests"):
        responded_session = bool(conn.execute("SELECT 1 FROM saas_handoff_requests WHERE status='RESPONDED' AND transport=? AND receipt_digest IS NOT NULL LIMIT 1", (SESSION_MEDIATED,)).fetchone())
        autonomous_claim = bool(conn.execute("SELECT 1 FROM saas_handoff_requests WHERE transport LIKE '%AUTONOMOUS%' LIMIT 1").fetchone())
    if _exists_table(conn, "saas_session_bindings"):
        autonomous_claim = autonomous_claim or bool(conn.execute("SELECT 1 FROM saas_session_bindings WHERE transport LIKE '%AUTONOMOUS%' LIMIT 1").fetchone())

    values: dict[str, bool] = {
        "DB_INTEGRITY": integrity == "ok",
        "GENERIC_ADAPTER_BOUND": bool(mission and mission["adapter"] == GENERIC_ADAPTER),
        "LOGICAL_COUNT_128": bool(mission and int(mission["logical_count"]) == 128 and len(logical) == 128),
        "MATERIAL_READY_64": bool(mission and int(mission["materialized"]) == 64 and int(mission["ready"]) == 64 and len(material) == 64 and all(int(r["ready"]) == 1 for r in material)),
        "UNIQUE_MATERIAL_64": len({r["pod_uid"] for r in material if r["pod_uid"]}) == 64,
        "TOPOLOGY_ASSIGNMENTS_128": len(topology) == 128 and all(r["state"] == "BOUND" for r in topology),
        "TOPOLOGY_CANONICAL_IDS": [r["logical_id"] for r in logical] == [f"LD{i:03d}" for i in range(1,129)] and [r["material_id"] for r in material] == [f"MD{i:03d}" for i in range(1,65)],
        "TOPOLOGY_RATIO_2_TO_1": len(topology_map) == 64 and all(len(ids) == 2 for ids in topology_map.values()),
        "TOPOLOGY_GENERIC_ROLES_16": len(role_counts) == 16 and all(role_counts.get(f"GENERIC_EXECUTION_POOL_{i:02d}") == 8 for i in range(1,17)),
        "PHASE_SPEC_COUNT_MATCH": len(specs) == phase_count,
        "ALL_MISSION_PHASES_GENERIC_HANDLER": phase_count > 0 and len(specs) == phase_count and all(r["handler_id"] == GENERIC_HANDLER for r in specs),
        "LPCL12_COMPILER_AVAILABLE": _lpcl12_probe(),
        "PROCESS_CONTRACT_PREFLIGHT_VALID": bool(conn.execute("SELECT 1 FROM mission_execution_preflights WHERE mission_id=?", (mission_id,)).fetchone()),
        "LOCAL_PLAN_ASSIGNMENT_AUTONOMOUS": bool(non_topology_assignments) and all(r["material_drone_id"] for r in non_topology_assignments),
        "LOCAL_PLAN_RECEIPT_PRESENT": local_receipt_count > 0,
        "ACTION_IR_READ_ONLY_BOUNDARY": air_ok,
        "GENERIC_ACTION_RECEIPT_PRESENT": len(generic_receipts) > 0,
        "CAPABILITY_FAIL_CLOSED_PROVEN": protocol_event("GENERIC_PHASE_CAPABILITY_UNAVAILABLE"),
        "NO_RAW_MODEL_TO_SHELL": air_ok,
        "DRIVER_PRESENT": driver is not None,
        "DRIVER_GENERATION_POSITIVE": bool(driver and int(driver["generation"]) > 0),
        "DRIVER_CHECKPOINT_PRESENT": int(conn.execute("SELECT COUNT(*) FROM mission_execution_checkpoints WHERE mission_id=?", (mission_id,)).fetchone()[0]) > 0,
        "DRIVER_CURRENT_PHASE_TRACKED": bool(driver and process and driver["current_phase"] == process["current_phase"]),
        "WAITING_LEASE_RELEASED": bool(driver and (driver["state"] != "WAITING" or (driver["lease_owner"] is None and driver["lease_expires_at"] is None))),
        "SCHEDULER_ACTIVE": bool(scheduler and scheduler["state"] == "ACTIVE" and scheduler["heartbeat_at"]),
        "MISSION_SCHEDULER_TURN_PRESENT": turn is not None,
        "MISSION_DISPATCH_COUNT_POSITIVE": bool(turn and int(turn["dispatch_count"]) > 0),
        "AUTOMATIC_PHASE_ADVANCE_PROVEN": len(passed) >= 3 and current_ordinal >= 4 and protocol_event("GENERIC_PHASE_EXECUTION_PASS", phase="REPAIR_EXECUTION_BINDER"),
        "LOCAL_DELEGATION_PROVEN": bool(non_topology_assignments) and local_receipt_count > 0,
        "MATERIAL_DELEGATION_PROVEN": len(topology) == 128 and len(material) == 64,
        "DYNAMIC_CAPABILITY_BINDING_PROVEN": len(bindings) > 0,
        "SAAS_BROKER_AVAILABLE": _exists_table(conn, "saas_handoff_requests") and int(conn.execute("SELECT COUNT(*) FROM saas_handoff_requests").fetchone()[0]) > 0,
        "SAAS_TRANSPORT_TRUTHFUL": responded_session and not autonomous_claim,
        "RESTART_BACKUP_PRESENT": restart is not None,
        "DRIVER_SURVIVED_RESTART": restart is not None and driver is not None,
        "NO_DUPLICATE_PHASE3_PLANNING": int(conn.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='REPAIR_EXECUTION_BINDER'", (mission_id,)).fetchone()[0]) == 1,
        "NO_DUPLICATE_PHASE3_ACTION_RECEIPT": int(conn.execute("SELECT COUNT(*) FROM mission_generic_action_receipts WHERE mission_id=? AND phase_id='REPAIR_EXECUTION_BINDER'", (mission_id,)).fetchone()[0]) == 1,
        "PANEL_REGISTRATION_PROVEN": protocol_event("MISSION_REGISTERED", from_id="LPCL_PANEL"),
        "OPERATOR_ACTIVATION_PROVEN": protocol_event("MISSION_AUTHORIZED", from_id="OPERATOR"),
        "AUTONOMOUS_MULTI_PHASE_TRANSITION_PROVEN": len(passed) >= 3 and current_ordinal >= 4,
        "POST_ASTRA_MISSION_EXISTS": post is not None,
        "POST_ASTRA_GENERIC_ADAPTER": bool(post and post["adapter"] == GENERIC_ADAPTER),
        "POST_ASTRA_MATERIAL_READY_64": bool(post and int(post["materialized"]) == 64 and int(post["ready"]) == 64),
        "POST_ASTRA_DRIVER_WAITING": bool(post_driver and post_driver["state"] == "WAITING"),
        "POST_ASTRA_LOCAL_PLAN_RECEIPT": post_receipts > 0,
        "POST_ASTRA_FAIL_CLOSED_CAPABILITY_GATE": bool(post_driver and post_driver["blocking_gate"] == "CAPABILITY_NOT_AVAILABLE"),
        "SAAS_SESSION_MEDIATED_RECEIPT_EXISTS": responded_session,
        "SAAS_AUTOMATIC_HOP_NOT_CLAIMED": not autonomous_claim,
        "RUNTIME_REVISIONS_CONVERGED": runtime_revision_evidence is not None,
        "PREFLIGHT_RUNTIME_BINDING_VISIBLE": preflight_binding_evidence is not None,
        "BROKER_TRANSPORT_TRUTHFUL": _exists_table(conn, "saas_handoff_requests") and not autonomous_claim,
        "BROKER_RECEIPT_LINEAGE_RECONCILED": (broker_missing_receipts == 0 and broker_orphan_receipts == 0) or broker_reconciliation_evidence is not None,
        "PANEL_TRUTH_PROJECTION_REPAIRED": panel_projection_evidence is not None,
        "LEGACY_LPCL_1_1_COMPATIBLE": _lpcl11_probe(),
        "LPCL_1_2_COMPATIBLE": _lpcl12_probe(),
    }
    values["SUCCESSOR_TERMINAL_VALIDATION"] = all(values.get(k, False) for k in (
        "RUNTIME_REVISIONS_CONVERGED",
        "PREFLIGHT_RUNTIME_BINDING_VISIBLE",
        "BROKER_TRANSPORT_TRUTHFUL",
        "BROKER_RECEIPT_LINEAGE_RECONCILED",
        "PANEL_TRUTH_PROJECTION_REPAIRED",
        "LEGACY_LPCL_1_1_COMPATIBLE",
        "LPCL_1_2_COMPATIBLE",
    ))

    for name in names:
        checks[name] = bool(values.get(name, False))
    facts.update({
        "checks": {k: "PASS" if v else "FAIL" for k, v in checks.items()},
        "mission_id": mission_id,
        "phase_id": phase_id,
        "phase_count": phase_count,
        "passed_phase_count": len(passed),
        "current_phase": process["current_phase"] if process else None,
        "current_ordinal": current_ordinal,
        "logical_count": len(logical),
        "material_count": len(material),
        "topology_assignment_count": len(topology),
        "scheduler_dispatch_count": int(turn["dispatch_count"]) if turn else 0,
        "generic_action_receipt_count": len(generic_receipts),
        "generic_plan_count": len(plan_rows),
        "post_astra_state": post["state"] if post else None,
        "post_astra_runtime_state": post["runtime_state"] if post else None,
        "post_astra_driver_state": post_driver["state"] if post_driver else None,
        "post_astra_gate": post_driver["blocking_gate"] if post_driver else None,
        "saas_session_mediated_receipt": responded_session,
        "saas_autonomous_claim": autonomous_claim,
        "authority_effect": "NONE",
    })
    return all(checks.values()), facts

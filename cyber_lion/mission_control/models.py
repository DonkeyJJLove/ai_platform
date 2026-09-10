from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
RUN_STATUSES = {
    "DISCOVERED", "STARTING", "RUNNING", "PASS", "FAIL", "DEFER", "UNKNOWN", "CLEANING", "CLEANED"
}
VERIFICATION_STATUSES = {
    "DECLARED", "OBSERVED", "CORROBORATED", "VERIFIED", "DEGRADED", "CONTRADICTED", "UNKNOWN"
}

DEFAULT_RUN: dict[str, Any] = {
    "process_language": "LPCL-1_0",
    "process_class": "UNKNOWN",
    "adapter_type": "UNKNOWN",
    "status": "UNKNOWN",
    "verification_status": "UNKNOWN",
    "phase": None,
    "started_at": None,
    "finished_at": None,
    "duration": None,
    "host": None,
    "runtime": None,
    "namespace": None,
    "source": {},
    "target": {},
    "workload": {},
    "authority": {},
    "participants": {},
    "metrics": {},
    "artifacts": [],
    "receipts": [],
    "cleanup": {},
    "evidence": {},
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def require_run_id(value: Any) -> str:
    if not isinstance(value, str) or not RUN_ID_RE.fullmatch(value):
        raise ValueError("invalid run_id")
    return value


def normalize_run(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("run must be an object")
    run_id = require_run_id(value.get("run_id"))
    out = deepcopy(DEFAULT_RUN)
    out.update({k: deepcopy(v) for k, v in value.items() if k in out or k == "run_id"})
    out["run_id"] = run_id
    status = str(out.get("status") or "UNKNOWN").upper()
    verification = str(out.get("verification_status") or "UNKNOWN").upper()
    if status not in RUN_STATUSES:
        raise ValueError("invalid run status")
    if verification not in VERIFICATION_STATUSES:
        raise ValueError("invalid verification status")
    out["status"] = status
    out["verification_status"] = verification
    for field in ("source", "target", "workload", "authority", "participants", "metrics", "cleanup", "evidence"):
        if out[field] is None:
            out[field] = {}
        if not isinstance(out[field], dict):
            raise TypeError(f"{field} must be an object")
    for field in ("artifacts", "receipts"):
        if out[field] is None:
            out[field] = []
        if not isinstance(out[field], list):
            raise TypeError(f"{field} must be an array")
    return out


def summary_from_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = {name: 0 for name in RUN_STATUSES}
    hosts: set[str] = set()
    workloads = 0
    artifacts = 0
    events = 0
    for run in runs:
        status_counts[str(run.get("status") or "UNKNOWN").upper()] = status_counts.get(str(run.get("status") or "UNKNOWN").upper(), 0) + 1
        if run.get("host"):
            hosts.add(str(run["host"]))
        if run.get("workload"):
            workloads += 1
        artifacts += int(run.get("artifact_count") or len(run.get("artifacts") or []))
        events += int(run.get("event_count") or 0)
    return {
        "active_runs": status_counts.get("STARTING", 0) + status_counts.get("RUNNING", 0) + status_counts.get("CLEANING", 0),
        "completed_runs": status_counts.get("PASS", 0) + status_counts.get("CLEANED", 0),
        "failed_runs": status_counts.get("FAIL", 0),
        "deferred_runs": status_counts.get("DEFER", 0),
        "hosts": len(hosts),
        "workloads": workloads,
        "events": events,
        "artifacts": artifacts,
        "run_count": len(runs),
    }

def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float) and value.is_integer():
        return max(0, int(value))
    return 0


def fleet_summary_from_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    organizations_total: dict[str, int] = {}
    organizations_active: dict[str, int] = {}
    run_ids: list[str] = []
    fleet_total = 0
    working_drones = 0
    for run in runs:
        metrics = run.get("metrics") or {}
        if not isinstance(metrics, dict):
            continue
        total_map = metrics.get("fleet_organizations") or {}
        active_map = metrics.get("active_by_organization") or {}
        if not isinstance(total_map, dict) or not isinstance(active_map, dict):
            continue
        if not total_map and not active_map:
            continue
        run_id = run.get("run_id")
        if isinstance(run_id, str) and run_id:
            run_ids.append(run_id)
        normalized_total = {str(name): _nonnegative_int(value) for name, value in total_map.items()}
        normalized_active = {str(name): _nonnegative_int(value) for name, value in active_map.items()}
        run_total = _nonnegative_int(metrics.get("pods")) or sum(normalized_total.values())
        run_active = _nonnegative_int(metrics.get("fresh_drones")) or sum(normalized_active.values())
        fleet_total += run_total
        working_drones += min(run_total, run_active) if run_total else run_active
        for name, value in normalized_total.items():
            organizations_total[name] = organizations_total.get(name, 0) + value
        for name, value in normalized_active.items():
            organizations_active[name] = organizations_active.get(name, 0) + value
    names = sorted(set(organizations_total) | set(organizations_active))
    organizations = {
        name: {
            "total": organizations_total.get(name, 0),
            "active": organizations_active.get(name, 0),
            "idle": max(0, organizations_total.get(name, 0) - organizations_active.get(name, 0)),
        }
        for name in names
    }
    return {
        "fleet_total": fleet_total,
        "working_drones": working_drones,
        "idle_drones": max(0, fleet_total - working_drones),
        "organization_count": len(names),
        "organizations": organizations,
        "run_ids": sorted(set(run_ids)),
    }

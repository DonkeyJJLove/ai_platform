"""Read-only mission-scoped material-fleet lifecycle projection.

This is an extension of the existing Mission Control scheduler, NOT a second
scheduler, Docker executor, authority engine or registration path. It produces
a bounded cardinality/transition *proposal*. Only the existing LPCL, operator
control, source-currentness, RuntimeAdmission and canonical runtime providers
can authorize and perform an effect. No function in this module starts, stops,
recreates or claims a worker.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from cyber_lion.contracts.phase_execution_contract import (
    PhaseExecutionContract, PhaseExecutionContractError,
)

SCHEMA = "lion.mission-scoped-material-fleet-lifecycle/v1"
CARRIER_SCHEMA = "lion.docker-local-model-fleet-currentness/v1"
AUTHORITY_EFFECT = "NONE"
EXECUTION_EFFECT = "NONE"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")

# Exact PhaseExecutionContract class, expected execution class and ceiling.
# This is a demand mapping, not a capability binding or action permit.
DEMAND = {
    "CONTROL_PLANE_RECONNAISSANCE": ("COGNITIVE", "NONE", 0),
    "COOPERATIVE_WORKER_PREACTIVATION": ("VALIDATE", "NONE", 1),
    "COOPERATIVE_ARTIFACT_BOOTSTRAP": ("VERIFY", "NONE", 32),
    "COOPERATIVE_ARTIFACT_PRODUCTION": ("MUTATE", "BOUNDED_MATERIAL", 32),
    "COOPERATIVE_ARTIFACT_VERIFY": ("VERIFY", "NONE", 32),
}
FINAL_PHASE_STATES = frozenset({"PASS", "COMPLETE", "SKIPPED", "CANCELLED"})
TERMINAL_MISSION_STATES = frozenset({"COMPLETE", "STOPPED", "SUPERSEDED", "FAILED"})
BUSY_ASSIGNMENT_STATES = ("HELD", "READY", "CLAIMED", "RUNNING")
ALLOWED_STAGES = (0, 1, 32)


class FleetLifecycleProjectionError(ValueError):
    pass


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_canon(value)).hexdigest()


def _check_id(value: str, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise FleetLifecycleProjectionError(label)
    return value


def _as_dict(row: Any) -> dict | None:
    return dict(row) if row is not None else None


def _now(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise FleetLifecycleProjectionError("timezone-aware currentness required")
    return value.astimezone(timezone.utc)


def _age(timestamp: Any, at: datetime) -> float | None:
    try:
        stamp = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return None
        return (at - stamp.astimezone(timezone.utc)).total_seconds()
    except (TypeError, ValueError):
        return None


def observe_carrier(value: Any, *, at: datetime) -> dict[str, Any]:
    """Validate a stored projection, not a live Docker attestation.

    'PARKED_OBSERVED' means only that a fresh, internally consistent
    projection recorded 32 exited container IDs. It does NOT prove
    the containers are still stopped or belong to an activated mission.
    """
    result = {
        "state": "UNAVAILABLE", "materialized": None, "ready": None,
        "source_head": None, "source_tree": None, "currentness_digest": None,
        "age_seconds": None, "unique_container_ids": None,
    }
    if value is None:
        return result
    if type(value) is not dict or value.get("schema") != CARRIER_SCHEMA:
        return {**result, "state": "INVALID"}
    supplied = value.get("currentness_digest")
    payload = dict(value)
    payload.pop("currentness_digest", None)
    if type(supplied) is not str or _SHA64.fullmatch(supplied) is None or _digest(payload) != supplied:
        return {**result, "state": "INVALID"}
    head, tree = value.get("source_head"), value.get("source_tree")
    age = _age(value.get("observed_at"), at)
    workers = value.get("workers")
    if (
        type(head) is not str or _SHA40.fullmatch(head) is None
        or type(tree) is not str or _SHA40.fullmatch(tree) is None
        or type(workers) is not list or len(workers) != 32
        or any(type(w) is not dict for w in workers)
        or type(value.get("materialized")) is not int
        or type(value.get("ready")) is not int
        or value["materialized"] != 32
        or not 0 <= value["ready"] <= 32
        or value.get("physical_host") != "MOON"
    ):
        return {**result, "state": "INVALID"}
    ids = [w.get("material_worker_id") for w in workers]
    cids = [w.get("container_id") for w in workers]
    if (
        any(type(wid) is not str for wid in ids)
        or sorted(ids) != [f"MD{i:03d}" for i in range(1, 33)]
        or any(type(c) is not str or not c for c in cids)
        or len(set(cids)) != 32
    ):
        return {**result, "state": "INVALID"}
    common = {
        **result, "materialized": 32, "ready": value["ready"],
        "source_head": head, "source_tree": tree,
        "currentness_digest": supplied, "age_seconds": round(age, 3) if age is not None else None,
        "unique_container_ids": 32,
    }
    if age is None or not -3 <= age <= 20:
        return {**common, "state": "STALE"}
    all_stopped = (
        value.get("state") == "DEGRADED" and value["ready"] == 0
        and all(w.get("container_state") == "exited" and w.get("ready") is False for w in workers)
    )
    if all_stopped:
        return {**common, "state": "PARKED_OBSERVED"}
    all_ready = (
        value.get("state") == "READY" and value["ready"] == 32
        and all(w.get("container_state") == "running" and w.get("ready") is True
                and w.get("model") == "gpt-oss-20b-MXFP4" for w in workers)
    )
    if all_ready:
        return {**common, "state": "READY_OBSERVED"}
    return {**common, "state": "DEGRADED"}


def _canonical_contract(row: Mapping[str, Any], *, mission_id: str, phase_id: str,
                        ordinal: int) -> tuple[str, int] | None:
    """Reconstruct the *whole* canonical compiled contract and verify its digest."""
    try:
        raw = {}
        for field in (
            "capability_classes", "currentness_requirements",
            "evidence_requirements", "completion_predicates",
        ):
            value = json.loads(row[field + "_json"])
            if type(value) is not list or any(type(x) is not str for x in value):
                return None
            raw[field] = tuple(value)
        if (
            row["mission_id"] != mission_id or row["phase_id"] != phase_id
            or row["ordinal"] != ordinal
            or row["contract_source"] != "DECLARED"
            or type(row["verify_before_mutate"]) is not int
            or row["verify_before_mutate"] != 1
        ):
            return None
        contract = PhaseExecutionContract(
            mission_id=row["mission_id"],
            phase_id=row["phase_id"],
            ordinal=row["ordinal"],
            execution_class=row["execution_class"],
            capability_classes=raw["capability_classes"],
            effect_ceiling=row["effect_ceiling"],
            binding_mode=row["binding_mode"],
            on_missing_capability=row["on_missing_capability"],
            auto_resume=bool(row["auto_resume"]),
            verify_before_mutate=bool(row["verify_before_mutate"]),
            currentness_requirements=raw["currentness_requirements"],
            evidence_requirements=raw["evidence_requirements"],
            completion_predicates=raw["completion_predicates"],
            contract_source=row["contract_source"],
            contract_version=row["contract_version"],
            compiler_version=row["compiler_version"],
        ).validate()
        if contract.as_dict()["contract_digest"] != row["contract_digest"]:
            return None
        classes = contract.capability_classes
        if len(classes) != 1 or classes[0] not in DEMAND:
            return ("UNKNOWN", -1)
        descriptor = DEMAND[classes[0]]
        if (contract.execution_class, contract.effect_ceiling) != descriptor[:2]:
            return None
        return contract.execution_class, descriptor[2]
    except (TypeError, ValueError, KeyError, PhaseExecutionContractError, AttributeError):
        return None


def _one(conn, query: str, arguments: tuple[Any, ...]) -> dict | None:
    return _as_dict(conn.execute(query, arguments).fetchone())


def project_lifecycle(
    conn,
    mission_id: str,
    *,
    fleet_carrier: Mapping[str, Any] | None = None,
    current_source: Mapping[str, str] | None = None,
    at: datetime,
) -> dict[str, Any]:
    """Read the canonical mission/phase/driver/assignment state without mutation.

    current_source must be independently reacquired by the trusted caller.
    Even with exact source evidence this function NEVER grants RuntimeAdmission.
    A material effect requires a separate admission and effect-time recheck.
    """
    mission_id = _check_id(mission_id, "mission_id")
    at = _now(at)
    observed = observe_carrier(fleet_carrier, at=at)
    result: dict[str, Any] = {
        "schema": SCHEMA, "mission_id": mission_id,
        "state": "UNREGISTERED", "phase_id": None,
        "phase_execution_class": None, "desired_workers": None,
        "observed_fleet": observed, "candidate_transition": "NONE",
        "effect_admitted": False, "authority_effect": AUTHORITY_EFFECT,
        "execution_effect": EXECUTION_EFFECT, "blockers": [],
        "registered_source_head": None, "registered_source_tree": None,
        "driver_generation": None, "control_epoch": None,
        "lpcl_digest": None, "phase_contract_digest": None,
    }
    m = _one(conn, "SELECT * FROM missions WHERE mission_id=?", (mission_id,))
    if m is None:
        result["blockers"] = ["MISSION_NOT_REGISTERED"]
        return _seal(result)
    result["registered_source_head"] = m.get("source_head")
    result["registered_source_tree"] = m.get("source_tree")
    result["lpcl_digest"] = m.get("spec_digest")

    p = _one(conn, "SELECT * FROM mission_process_specs WHERE mission_id=?", (mission_id,))
    phases = [
        dict(row) for row in conn.execute(
            "SELECT phase_id,status,ordinal FROM mission_phases WHERE mission_id=? ORDER BY ordinal",
            (mission_id,),
        ).fetchall()
    ]
    pending = [x for x in phases if x["status"] not in FINAL_PHASE_STATES]
    blockers: list[str] = []
    def block(reason: str) -> None:
        if reason not in blockers:
            blockers.append(reason)

    if not p or not phases:
        block("MISSION_PROCESS_OR_PHASES_MISSING")
    else:
        if type(p.get("lpcl_text")) is not str or sha256(p["lpcl_text"].encode()).hexdigest() != m.get("spec_digest"):
            block("LPCL_SOURCE_DIGEST_MISMATCH")
        if p.get("authority_state") != "EXPLICIT_USER_ACTIVATION":
            block("LPCL_NOT_EXPLICITLY_ACTIVATED")
    if m.get("state") not in TERMINAL_MISSION_STATES and m.get("state") not in {
        "AUTHORIZED", "RUNNING", "WAITING", "BLOCKED",
    }:
        block("MISSION_NOT_AUTHORIZED")
    if m.get("material_target") != 32:
        block("MISSION_MATERIAL_TARGET_MISMATCH")
    if m.get("source_head") is None or m.get("source_tree") is None or (
        _SHA40.fullmatch(str(m["source_head"])) is None
        or _SHA40.fullmatch(str(m["source_tree"])) is None
    ):
        block("REGISTERED_SOURCE_MALFORMED")
    if (
        not isinstance(current_source, Mapping)
        or current_source.get("head") != m.get("source_head")
        or current_source.get("tree") != m.get("source_tree")
        or not all(_SHA40.fullmatch(str(current_source.get(key) or "")) for key in ("head", "tree"))
    ):
        block("CURRENT_RUNTIME_SOURCE_UNVERIFIED_OR_DRIFT")

    if m.get("state") in TERMINAL_MISSION_STATES:
        result["desired_workers"] = 0
        result["phase_id"] = "TERMINAL"
        if m["state"] != "COMPLETE" or any(x["status"] not in {"PASS", "COMPLETE"} for x in phases):
            block("TERMINAL_PHASES_NOT_RECONCILED")
    elif pending:
        phase_id = pending[0]["phase_id"]
        result["phase_id"] = phase_id
        contract = _one(
            conn, "SELECT * FROM mission_phase_execution_contracts WHERE mission_id=? AND phase_id=?",
            (mission_id, phase_id),
        )
        if contract is None:
            block("PHASE_EXECUTION_CONTRACT_MISSING")
        else:
            result["phase_contract_digest"] = contract.get("contract_digest")
            descriptor = _canonical_contract(
                contract, mission_id=mission_id, phase_id=phase_id,
                ordinal=pending[0]["ordinal"],
            )
            if descriptor is None:
                block("PHASE_CONTRACT_SEMANTIC_DRIFT")
            elif descriptor[0] == "UNKNOWN":
                block("PHASE_CAPABILITY_NOT_MAPPED")
            else:
                result["phase_execution_class"] = descriptor[0]
                result["desired_workers"] = descriptor[1]
    else:
        block("NO_CURRENT_PHASE_BUT_MISSION_NOT_TERMINAL")
    desired = result["desired_workers"]

    d = _one(conn, "SELECT * FROM mission_execution_drivers WHERE mission_id=?", (mission_id,))
    ctl = _one(conn, "SELECT * FROM mission_operator_control WHERE mission_id=?", (mission_id,))
    sch = _one(conn, "SELECT * FROM mission_scheduler_state LIMIT 1", ())
    if d:
        result["driver_generation"] = d.get("generation")
    if ctl:
        result["control_epoch"] = ctl.get("control_epoch")
        if ctl.get("pause_latch") or ctl.get("stop_latch"):
            block("OPERATOR_PAUSE_OR_STOP_LATCH")
    else:
        block("OPERATOR_CONTROL_CURRENTNESS_UNKNOWN")
    if m.get("state") not in TERMINAL_MISSION_STATES:
        if (
            not d or d.get("state") != "ACTIVE"
            or type(d.get("generation")) is not int or d["generation"] < 1
            or not d.get("lease_owner")
            or (lease_age := _age(d.get("lease_expires_at"), at)) is None
            or lease_age > 0
        ):
            block("MISSION_DRIVER_NOT_DISPATCHABLE")
        elif d.get("current_phase") != result["phase_id"]:
            block("MISSION_DRIVER_PHASE_DRIFT")
        if not sch or sch.get("state") != "ACTIVE":
            block("GLOBAL_SCHEDULER_NOT_ACTIVE")
        elif (age := _age(sch.get("heartbeat_at"), at)) is None or age < -3 or age > 30:
            block("GLOBAL_SCHEDULER_HEARTBEAT_STALE")
    elif (
        not d or d.get("state") != "COMPLETE"
        or _SHA64.fullmatch(str(d.get("checkpoint_digest") or "")) is None
    ):
        block("TERMINAL_RECONCILIATION_NOT_ATTESTED")
    active_assignments = conn.execute(
        "SELECT COUNT(*) FROM mission_execution_assignments "
        "WHERE mission_id=? AND state IN ('HELD','READY','CLAIMED','RUNNING') AND phase_id!='__TOPOLOGY__'",
        (mission_id,),
    ).fetchone()[0]
    active_leases = conn.execute(
        "SELECT COUNT(*) FROM mission_recon_material_leases WHERE mission_id=? AND state='ACTIVE'",
        (mission_id,),
    ).fetchone()[0]
    if desired == 0 and (active_assignments or active_leases):
        block("INFLIGHT_ASSIGNMENTS_OR_LEASES_NOT_RECONCILED")
    if desired == 0 and observed["state"] == "READY_OBSERVED":
        # A fleet may be shared by multiple missions. No mission may propose
        # parking it while another nonterminal mission has active work.
        foreign_assignments = conn.execute(
            "SELECT COUNT(*) FROM mission_execution_assignments a "
            "JOIN missions m ON m.mission_id=a.mission_id "
            "WHERE a.mission_id!=? AND m.state NOT IN ('COMPLETE','STOPPED','SUPERSEDED','FAILED') "
            "AND a.state IN ('HELD','READY','CLAIMED','RUNNING') AND a.phase_id!='__TOPOLOGY__'",
            (mission_id,),
        ).fetchone()[0]
        foreign_leases = conn.execute(
            "SELECT COUNT(*) FROM mission_recon_material_leases l "
            "JOIN missions m ON m.mission_id=l.mission_id "
            "WHERE l.mission_id!=? AND m.state NOT IN ('COMPLETE','STOPPED','SUPERSEDED','FAILED') "
            "AND l.state='ACTIVE'",
            (mission_id,),
        ).fetchone()[0]
        if foreign_assignments or foreign_leases:
            block("SHARED_FLEET_FOREIGN_MISSION_WORK_INFLIGHT")
    if desired in (1, 32) and observed["state"] in {"INVALID", "STALE", "UNAVAILABLE"}:
        block("FLEET_OBSERVATION_UNAVAILABLE_OR_INVALID")
    if desired in ALLOWED_STAGES and observed["state"] in {"READY_OBSERVED", "PARKED_OBSERVED"} and (
        observed["source_head"] != m.get("source_head") or observed["source_tree"] != m.get("source_tree")
    ):
        # A historical source is neither a worker of the current mission
        # nor an exact target for an automated mission-scoped park.
        block("FLEET_WORKER_SOURCE_DRIFT")

    # Projection is never authority. In particular READY_OBSERVED is not the
    # cooperative provider, RuntimeAdmission, activated LPCL or effect-time gate.
    result["blockers"] = sorted(blockers)
    if blockers:
        result["state"] = "BLOCKED"
    elif desired == 0:
        result["state"] = "NO_MATERIAL_EXECUTION_REQUIRED"
        if observed["state"] == "READY_OBSERVED":
            result["candidate_transition"] = "PARK_AFTER_INDEPENDENT_ADMISSION"
    elif desired == 1:
        result["state"] = "AWAIT_SINGLE_WORKER_QUALIFICATION"
        result["candidate_transition"] = "PREACTIVATE_ONE_AFTER_INDEPENDENT_ADMISSION"
    elif desired == 32:
        result["state"] = "AWAIT_FULL_FLEET_PROVIDER_READINESS"
        result["candidate_transition"] = "DEPLOY_32_AFTER_INDEPENDENT_ADMISSION"
    else:
        result["state"] = "BLOCKED"
        result["blockers"] = ["UNRECOGNIZED_CARDINALITY"]
    return _seal(result)


def _seal(result: dict[str, Any]) -> dict[str, Any]:
    result["projection_digest"] = _digest(result)
    return result

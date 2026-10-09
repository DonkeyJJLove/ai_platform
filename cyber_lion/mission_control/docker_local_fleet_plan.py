"""Deterministic, non-effectful R24 Docker fleet plan for an exact LPCL mission.

The 32 Docker workers are material executors, not 32 independent authority
principals. The existing Mission Control scheduler owns all assignments and
phase progression. This module cannot start containers; its plan must be
consumed by an admitted runtime executor after the operator launches LPCL.
"""
from __future__ import annotations

from hashlib import sha256
from datetime import datetime, timezone
import json
import re
from typing import Any, Mapping

from cyber_lion.mission_control.lpcl_runtime_selection import runtime_selection

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED = tuple(f"MD{i:03d}" for i in range(1, 33))
_PROFILE = "LION_MATERIAL_EXECUTOR_V2"
_PROJECT = "lion-r24-autonomy"


class DockerFleetPlanError(ValueError):
    pass


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise DockerFleetPlanError(reason)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _pairs(text: str) -> dict[str, str]:
    """Read only top-level scalars required to resolve the current runtime.

    This is not another LPCL compiler. Mission Control remains the sole source
    of validated phases, capabilities, admission and progress.
    """
    found: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("PHASE_"):
            break
        candidate = re.fullmatch(r"([A-Z][A-Z0-9_]*)=([^=\n]+)", line.strip())
        if candidate is None:
            continue
        key, value = candidate.groups()
        if key in found:
            raise DockerFleetPlanError("DUPLICATE_LPCL_GLOBAL:" + key)
        found[key] = value.strip()
    return found


def _compose_workers(compose: Mapping[str, Any]) -> tuple[dict[str, str], ...]:
    _require(isinstance(compose, Mapping), "COMPOSE_CONFIG_REQUIRED")
    services = compose.get("services")
    _require(isinstance(services, Mapping) and len(services) == 32,
             "EXACT_32_SERVICES_REQUIRED")
    rows: list[dict[str, str]] = []
    for i, wid in enumerate(_EXPECTED, 1):
        service = f"worker-{i:02d}"
        expected_name = f"lion-r24-md{i:03d}"
        value = services.get(service)
        _require(isinstance(value, Mapping), "WORKER_SERVICE_MISSING:" + service)
        _require(value.get("container_name") == expected_name,
                 "WORKER_CONTAINER_IDENTITY_DRIFT:" + service)
        labels = value.get("labels") or {}
        _require(isinstance(labels, Mapping)
                 and labels.get("LION_WORKER_PROFILE") == _PROFILE
                 and labels.get("LION_MATERIAL_WORKER_ID") == wid,
                 "WORKER_PROFILE_DRIFT:" + service)
        _require(value.get("read_only") is True, "WORKER_NOT_READONLY:" + service)
        rows.append({
            "material_worker_id": wid,
            "compose_service": service,
            "container_name": expected_name,
        })
    return tuple(rows)


def deterministic_fleet_plan(
    mission: Mapping[str, Any],
    compose_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile desired Docker topology without activation or a Docker effect."""
    _require(isinstance(mission, Mapping), "MISSION_READBACK_REQUIRED")
    mid = mission.get("mission_id")
    _require(isinstance(mid, str) and mid, "MISSION_ID_REQUIRED")
    source_head, source_tree = mission.get("source_head"), mission.get("source_tree")
    digest = mission.get("spec_digest")
    _require(isinstance(source_head, str) and _SHA40.fullmatch(source_head) is not None,
             "SOURCE_HEAD_INVALID")
    _require(isinstance(source_tree, str) and _SHA40.fullmatch(source_tree) is not None,
             "SOURCE_TREE_INVALID")
    _require(isinstance(digest, str) and _SHA64.fullmatch(digest) is not None,
             "LPCL_DIGEST_INVALID")
    process = mission.get("process") or {}
    _require(isinstance(process, Mapping), "MISSION_PROCESS_REQUIRED")
    source_text = process.get("lpcl_text")
    _require(isinstance(source_text, str)
             and sha256(source_text.encode("utf-8")).hexdigest() == digest,
             "LPCL_SOURCE_BYTES_DRIFT")
    logical_count, material_target = mission.get("logical_count"), mission.get("material_target")
    _require(type(logical_count) is int and 1 <= logical_count <= 512, "LOGICAL_COUNT_INVALID")
    _require(material_target == 32 and type(material_target) is int, "MATERIAL_COUNT_MUST_BE_32")
    picked = runtime_selection(_pairs(source_text), logical_count, material_target)
    _require(picked.get("selected_adapter") == "LPCL_DOCKER_LOCAL_MODEL"
             and picked.get("declaration_supported") is True,
             "LPCL_RUNTIME_DISCRIMINATOR_REQUIRED")
    _require(mission.get("state") in {"REGISTERED", "AUTHORIZED", "RUNNING"},
             "MISSION_STATE_NOT_ELIGIBLE")
    rows = _compose_workers(compose_config)

    # The original binder uses deterministic, round-robin logical assignment.
    # With eight logical drones, MD001..MD008 receive one role each. Others are
    # eligible material capacity but not fake logical workers.
    assignments = [
        {"logical_drone_id": f"LD{i:03d}",
         "material_worker_id": _EXPECTED[(i-1) % 32]}
        for i in range(1, logical_count+1)
    ]
    payload = {
        "schema": "lion.r24-docker-fleet-bootstrap-plan/v1",
        "mission_id": mid,
        "lpcl_digest": digest,
        "source_head": source_head,
        "source_tree": source_tree,
        "host": "MOON",
        "docker_engine": "docker-desktop",
        "compose_project": _PROJECT,
        "worker_profile": _PROFILE,
        "material_runtime": "DOCKER_LOCAL_MODEL",
        "logical_count": logical_count,
        "material_count": 32,
        "workers": list(rows),
        "logical_to_material": assignments,
        "existing_scheduler": "GLOBAL_MISSION_SCHEDULER_V1",
        "worker_source_identity": "REACQUIRE_AT_EFFECT_TIME",
        "docker_image_digest": "REACQUIRE_AT_EFFECT_TIME",
        "admission": "REQUIRED_BEFORE_EXECUTION",
        "authority_effect": "NONE",
    }
    payload["plan_digest"] = sha256(_canonical(payload)).hexdigest()
    return payload


def inspect_observed_fleet(plan: Mapping[str, Any], observed: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless exactly 32 source-proven Docker workers are observed."""
    _require(isinstance(plan, Mapping) and isinstance(observed, Mapping),
             "FLEET_EVIDENCE_REQUIRED")
    _require(plan.get("schema") == "lion.r24-docker-fleet-bootstrap-plan/v1",
             "PLAN_SCHEMA_INVALID")
    expected = dict(plan)
    claimed = expected.pop("plan_digest", None)
    _require(sha256(_canonical(expected)).hexdigest() == claimed,
             "FLEET_PLAN_DIGEST_DRIFT")
    _require(observed.get("host") == "MOON"
             and observed.get("docker_engine") == "docker-desktop",
             "WRONG_DOCKER_ENGINE")
    # The existing fleet-currentness.py uses physical_host and a sealed
    # currentness_digest; keep those original producer bytes intact. Host/engine
    # transport facts belong in an independent observation envelope.
    snapshot = observed.get("currentness")
    _require(isinstance(snapshot, Mapping), "R24_CURRENTNESS_PRODUCER_REQUIRED")
    rows = snapshot.get("workers")
    _require(isinstance(rows, list), "FLEET_OBSERVATION_NOT_A_LIST")
    if not rows:
        state = "ABSENT"
    elif len(rows) != 32:
        state = "PARTIAL"
    else:
        identities = {r.get("material_worker_id"): r for r in rows
                      if isinstance(r, Mapping)}
        valid = (
            len(identities) == 32
            and set(identities) == set(_EXPECTED)
            and all(
                identities[item["material_worker_id"]].get("container_name")
                == item["container_name"]
                and identities[item["material_worker_id"]].get("container_id")
                and identities[item["material_worker_id"]].get("ready") is True
                and identities[item["material_worker_id"]].get("worker_profile") == _PROFILE
                for item in plan["workers"]
            )
        )
        state = "STRUCTURAL_MATCH_CURRENTNESS_UNVERIFIED" if valid else "DRIFT"
        raw = dict(snapshot)
        digest = raw.pop("currentness_digest", None)
        try:
            stamp = datetime.fromisoformat(str(raw.get("observed_at") or "").replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
            timestamp_fresh = stamp.tzinfo is not None and 0 <= age <= 20
        except (ValueError, TypeError, OverflowError):
            timestamp_fresh = False
        fresh = (
            timestamp_fresh
            and raw.get("schema") == "lion.docker-local-model-fleet-currentness/v1"
            and raw.get("physical_host") == "MOON"
            and raw.get("state") == "READY"
            and raw.get("materialized") == 32
            and raw.get("ready") == 32
            and raw.get("worker_profile") == _PROFILE
            and raw.get("source_head") == plan["source_head"]
            and raw.get("source_tree") == plan["source_tree"]
            and isinstance(digest, str)
            and sha256(_canonical(raw)).hexdigest() == digest
        )
        if valid and fresh:
            state = "SOURCE_BOUND_READY"
    return {
        "schema": "lion.r24-fleet-bootstrap-observation/v1",
        "plan_digest": claimed,
        "state": state,
        "observed_workers": len(rows),
        "requested_workers": 32,
        "admission": "NOT_INFERRED_FROM_OBSERVATION",
        "authority_effect": "NONE",
    }


def classify_existing_docker_runtime(
    plan: Mapping[str, Any],
    containers: list[Mapping[str, Any]],
    identity: Mapping[str, Any] | None,
    receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Determine the next bounded state; deliberately never launch/recreate.

    The independent Docker host observer supplies raw inspect projections and
    pinned runtime identity/receipt readback. Container existence is not fleet
    currentness, and a historic receipt must not silently supersede runtime
    source identity.
    """
    _require(plan.get("schema") == "lion.r24-docker-fleet-bootstrap-plan/v1",
             "PLAN_REQUIRED")
    raw_plan = dict(plan)
    digest = raw_plan.pop("plan_digest", None)
    _require(sha256(_canonical(raw_plan)).hexdigest() == digest,
             "PLAN_DIGEST_MISMATCH")
    _require(isinstance(containers, list), "CONTAINER_INSPECTION_REQUIRED")
    status = "BLOCKED_MIXED_OR_UNKNOWN"
    reason = "UNCLASSIFIED_INVENTORY"
    if not containers:
        status, reason = "ABSENT", "REQUIRES_NEW_ADMITTED_MATERIALIZATION"
    elif len(containers) == 32:
        observed = {}
        for x in containers:
            _require(isinstance(x, Mapping), "DOCKER_CONTAINER_INVALID")
            labels = x.get("labels")
            _require(isinstance(labels, Mapping), "DOCKER_LABELS_REQUIRED")
            wid = labels.get("LION_MATERIAL_WORKER_ID")
            if wid in observed:
                return {"state":"BLOCKED", "reason":"DUPLICATE_WORKER_ID",
                        "plan_digest":digest,"authority_effect":"NONE"}
            observed[wid] = x
        by_id = {worker["material_worker_id"]: worker for worker in plan["workers"]}
        profiles_match = (
            set(observed) == set(by_id)
            and all(
                str(observed[wid].get("name") or "").lstrip("/")
                == by_id[wid]["container_name"]
                and observed[wid].get("labels", {}).get("LION_WORKER_PROFILE") == _PROFILE
                and observed[wid].get("labels", {}).get("com.docker.compose.project") == _PROJECT
                and isinstance(observed[wid].get("container_id"), str)
                and bool(observed[wid]["container_id"])
                for wid in by_id
            )
        )
        states = {str(x.get("state") or "").lower() for x in observed.values()}
        if not profiles_match:
            status, reason = "BLOCKED", "CONTAINER_IDENTITY_OR_PROJECT_DRIFT"
        elif states == {"running"}:
            status, reason = "OBSERVED_RUNNING", "FRESH_CURRENTNESS_READBACK_REQUIRED"
        elif states == {"exited"}:
            status, reason = "STOPPED_COHORT", "EXACT_SOURCE_AND_ADMISSION_REQUIRED"
        else:
            status, reason = "BLOCKED", "MIXED_CONTAINER_STATES"

        if status in {"OBSERVED_RUNNING", "STOPPED_COHORT"}:
            if not isinstance(identity, Mapping) or not isinstance(receipt, Mapping):
                status, reason = "BLOCKED", "RUNTIME_SOURCE_EVIDENCE_REQUIRED"
            elif (identity.get("schema") != "lion.material-worker-source-identity/v1"
                  or receipt.get("schema") != "lion.r24-material-fleet-materialization/v1"):
                status, reason = "BLOCKED", "RUNTIME_PROVENANCE_SCHEMA_DRIFT"
            elif (identity.get("source_head") != plan["source_head"]
                  or identity.get("source_tree") != plan["source_tree"]
                  or receipt.get("source_head") != identity.get("source_head")
                  or receipt.get("source_tree") != identity.get("source_tree")
                  or receipt.get("identity_digest") != identity.get("identity_digest")
                  or receipt.get("compose_sha256") != identity.get("compose_sha256")):
                status, reason = "BLOCKED", "RUNTIME_SOURCE_OR_RECEIPT_DRIFT"
            elif status == "STOPPED_COHORT":
                status, reason = "RESTART_CANDIDATE", "REQUIRES_OPERATOR_LPCL_AND_RUNTIME_ADMISSION"
            else:
                status, reason = "OBSERVED_RUNNING", "MUST_VERIFY_CURRENTNESS_AND_BINDING"
    return {"schema":"lion.r24-docker-deployment-classification/v1",
            "state":status,"reason":reason,
            "requested_workers":len(plan["workers"]),
            "observed_workers":len(containers),
            "plan_digest":digest,
            "effect_requested":False,"authority_effect":"NONE"}

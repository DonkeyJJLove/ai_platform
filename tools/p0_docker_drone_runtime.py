"""Deterministic TEST_ONLY runtime for LION Docker P0 and bounded scale soak tests."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping

from tools.p0_docker_fleet_contract import (
    DroneResult,
    DockerFleetPolygonContractError,
    MissionCapsule,
    canonical_json,
    digest_domain,
)

CAPSULE_PATH = Path("/mission/capsule.json")
CONTROL_KEY = "__lion_control__"
MAX_HOLD_SECONDS = 600
MIN_HEARTBEAT_SECONDS = 5
MAX_HEARTBEAT_SECONDS = 60


def capsule_from_mapping(value: Mapping[str, Any]) -> MissionCapsule:
    required = {
        "schema_version", "mission_id", "fleet_id", "drone_id", "role",
        "generation", "work_unit_id", "issued_at", "expires_at", "operation",
        "input_payload", "input_digest", "policy_digest", "capsule_digest",
    }
    if set(value) != required:
        raise DockerFleetPolygonContractError("capsule keys mismatch")
    if not isinstance(value["input_payload"], Mapping):
        raise DockerFleetPolygonContractError("input_payload must be object")
    return MissionCapsule(**value).validate(now=datetime.now(timezone.utc))


def _split_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    operation_payload = dict(payload)
    raw_control = operation_payload.pop(CONTROL_KEY, None)
    if raw_control is None:
        return operation_payload, {}
    if not isinstance(raw_control, Mapping):
        raise DockerFleetPolygonContractError("scale control must be object")
    control = dict(raw_control)
    if set(control) != {"mode", "hold_seconds", "heartbeat_seconds", "scale_run_id"}:
        raise DockerFleetPolygonContractError("scale control keys mismatch")
    if control["mode"] != "hold_after_result":
        raise DockerFleetPolygonContractError("scale control mode invalid")
    hold = control["hold_seconds"]
    heartbeat = control["heartbeat_seconds"]
    if isinstance(hold, bool) or not isinstance(hold, int) or not 1 <= hold <= MAX_HOLD_SECONDS:
        raise DockerFleetPolygonContractError("hold_seconds outside bound")
    if isinstance(heartbeat, bool) or not isinstance(heartbeat, int) or not MIN_HEARTBEAT_SECONDS <= heartbeat <= MAX_HEARTBEAT_SECONDS:
        raise DockerFleetPolygonContractError("heartbeat_seconds outside bound")
    scale_run_id = control["scale_run_id"]
    if not isinstance(scale_run_id, str) or not scale_run_id or len(scale_run_id) > 128:
        raise DockerFleetPolygonContractError("scale_run_id invalid")
    return operation_payload, control


def _architecture(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"architecture_digest": digest_domain(b"LION/P0/ARCHITECTURE", dict(payload)), "object_count": len(payload)}


def _security(payload: Mapping[str, Any]) -> dict[str, Any]:
    invariants = payload.get("invariants")
    if not isinstance(invariants, Mapping) or not invariants or any(not isinstance(v, bool) for v in invariants.values()):
        raise DockerFleetPolygonContractError("security invariants invalid")
    failed = sorted(str(k) for k, v in invariants.items() if not v)
    return {"all_hold": not failed, "failed": failed}


def _runtime_bindings(payload: Mapping[str, Any]) -> dict[str, Any]:
    expected, observed = payload.get("expected"), payload.get("observed")
    if not isinstance(expected, Mapping) or not isinstance(observed, Mapping):
        raise DockerFleetPolygonContractError("runtime binding maps missing")
    mismatches = sorted(key for key in set(expected) | set(observed) if expected.get(key) != observed.get(key))
    return {"matched": not mismatches, "mismatches": mismatches}


def _provenance(payload: Mapping[str, Any]) -> dict[str, Any]:
    objects, relationships = payload.get("objects"), payload.get("relationships")
    if not isinstance(objects, Mapping) or not isinstance(relationships, list):
        raise DockerFleetPolygonContractError("provenance payload invalid")
    object_digests = {str(name): digest_domain(b"LION/P0/PROVENANCE-OBJECT", value) for name, value in objects.items()}
    invalid = []
    for index, relation in enumerate(relationships):
        if not isinstance(relation, Mapping) or relation.get("source") not in object_digests or relation.get("target") not in object_digests:
            invalid.append(index)
    return {"valid": not invalid, "invalid_relationship_indexes": invalid, "object_digests": object_digests}


def _falsify(payload: Mapping[str, Any]) -> dict[str, Any]:
    if set(payload) != {"claim", "evidence"} or not isinstance(payload["claim"], bool) or not isinstance(payload["evidence"], bool):
        raise DockerFleetPolygonContractError("claim/evidence invalid")
    return {"falsified": payload["claim"] != payload["evidence"], "claim": payload["claim"], "evidence": payload["evidence"]}


OPERATIONS = {
    "ARCHITECTURE_DIGEST": _architecture,
    "SECURITY_INVARIANTS": _security,
    "RUNTIME_BINDINGS": _runtime_bindings,
    "PROVENANCE_RELATIONSHIPS": _provenance,
    "FALSIFY_CLAIM": _falsify,
}


def execute_capsule(capsule: MissionCapsule) -> DroneResult:
    capsule.validate(now=datetime.now(timezone.utc))
    operation_payload, _ = _split_payload(capsule.input_payload)
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result_body = OPERATIONS[capsule.operation](operation_payload)
    result_digest = digest_domain(b"LION/DRONE-RESULT-BODY/P0", result_body)
    completed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    identity = {
        "mission_id": capsule.mission_id, "fleet_id": capsule.fleet_id,
        "drone_id": capsule.drone_id, "generation": capsule.generation,
        "work_unit_id": capsule.work_unit_id, "input_digest": capsule.input_digest,
        "result_digest": result_digest,
    }
    result = DroneResult(
        result_id=digest_domain(b"LION/DRONE-RESULT/P0", identity),
        mission_id=capsule.mission_id, fleet_id=capsule.fleet_id,
        drone_id=capsule.drone_id, role=capsule.role, generation=capsule.generation,
        work_unit_id=capsule.work_unit_id, status="SUCCEEDED", result=result_body,
        input_digest=capsule.input_digest, result_digest=result_digest,
        started_at=started, completed_at=completed,
        evidence=(f"capsule:sha256:{capsule.capsule_digest}",),
    )
    return result.validate()


def _emit(value: Mapping[str, Any]) -> None:
    sys.stdout.buffer.write(canonical_json(dict(value)) + b"\n")
    sys.stdout.buffer.flush()


def _hold(capsule: MissionCapsule, control: Mapping[str, Any]) -> None:
    if not control:
        return
    hold_seconds = int(control["hold_seconds"])
    heartbeat_seconds = int(control["heartbeat_seconds"])
    deadline = time.monotonic() + hold_seconds
    sequence = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        sequence += 1
        _emit({
            "schema_version": "1.0.0",
            "kind": "HEARTBEAT",
            "mission_id": capsule.mission_id,
            "fleet_id": capsule.fleet_id,
            "drone_id": capsule.drone_id,
            "role": capsule.role,
            "generation": capsule.generation,
            "scale_run_id": control["scale_run_id"],
            "sequence": sequence,
            "remaining_seconds": max(0, int(remaining)),
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
        time.sleep(min(float(heartbeat_seconds), remaining))


def main() -> int:
    try:
        raw = json.loads(CAPSULE_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise DockerFleetPolygonContractError("capsule root must be object")
        capsule = capsule_from_mapping(raw)
        _, control = _split_payload(capsule.input_payload)
        result = execute_capsule(capsule)
        _emit({"kind": "WORK_RESULT", **result.canonical_dict()})
        _hold(capsule, control)
        if control:
            _emit({
                "schema_version": "1.0.0",
                "kind": "HOLD_COMPLETE",
                "mission_id": capsule.mission_id,
                "fleet_id": capsule.fleet_id,
                "drone_id": capsule.drone_id,
                "scale_run_id": control["scale_run_id"],
                "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            })
        return 0
    except Exception as exc:
        denied = {"schema_version": "1.0.0", "status": "DENIED", "error_type": type(exc).__name__, "error": str(exc)[:512]}
        _emit(denied)
        return 23


if __name__ == "__main__":
    raise SystemExit(main())

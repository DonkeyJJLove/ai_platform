"""Deterministic one-shot runtime for the first local Docker fleet.

The process receives one immutable MissionCapsule, performs one D0 operation,
emits one canonical terminal result on stdout and exits.  It has no Docker,
GitHub, model, package-management or authority surface.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from cyber_lion.contracts.docker_fleet_polygon import (
    DroneResult,
    DockerFleetPolygonContractError,
    MissionCapsule,
    canonical_json,
    digest_domain,
)

CAPSULE_PATH = Path("/mission/capsule.json")


def _capsule_from_mapping(value: Mapping[str, Any]) -> MissionCapsule:
    required = {
        "schema_version",
        "mission_id",
        "fleet_id",
        "drone_id",
        "role",
        "generation",
        "work_unit_id",
        "issued_at",
        "expires_at",
        "operation",
        "input_payload",
        "input_digest",
        "policy_digest",
        "capsule_digest",
    }
    if set(value) != required:
        raise DockerFleetPolygonContractError("capsule keys mismatch")
    if not isinstance(value["input_payload"], Mapping):
        raise DockerFleetPolygonContractError("input_payload must be object")
    return MissionCapsule(**value).validate(now=datetime.now(timezone.utc))


def _architecture(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "architecture_digest": digest_domain(b"LION/P0/ARCHITECTURE", dict(payload)),
        "object_count": len(payload),
    }


def _security(payload: Mapping[str, Any]) -> dict[str, Any]:
    invariants = payload.get("invariants")
    if not isinstance(invariants, Mapping) or not invariants:
        raise DockerFleetPolygonContractError("security invariants missing")
    if any(not isinstance(v, bool) for v in invariants.values()):
        raise DockerFleetPolygonContractError("security invariants must be boolean")
    failed = sorted(str(k) for k, v in invariants.items() if not v)
    return {"all_hold": not failed, "failed": failed}


def _runtime_bindings(payload: Mapping[str, Any]) -> dict[str, Any]:
    expected = payload.get("expected")
    observed = payload.get("observed")
    if not isinstance(expected, Mapping) or not isinstance(observed, Mapping):
        raise DockerFleetPolygonContractError("runtime binding maps missing")
    mismatches = sorted(
        key
        for key in set(expected) | set(observed)
        if expected.get(key) != observed.get(key)
    )
    return {"matched": not mismatches, "mismatches": mismatches}


def _provenance(payload: Mapping[str, Any]) -> dict[str, Any]:
    objects = payload.get("objects")
    relationships = payload.get("relationships")
    if not isinstance(objects, Mapping) or not isinstance(relationships, list):
        raise DockerFleetPolygonContractError("provenance payload invalid")
    object_digests = {
        str(name): digest_domain(b"LION/P0/PROVENANCE-OBJECT", value)
        for name, value in objects.items()
    }
    invalid: list[int] = []
    for index, relation in enumerate(relationships):
        if not isinstance(relation, Mapping):
            invalid.append(index)
            continue
        source = relation.get("source")
        target = relation.get("target")
        if source not in object_digests or target not in object_digests:
            invalid.append(index)
    return {
        "valid": not invalid,
        "invalid_relationship_indexes": invalid,
        "object_digests": object_digests,
    }


def _falsify(payload: Mapping[str, Any]) -> dict[str, Any]:
    if set(payload) != {"claim", "evidence"}:
        raise DockerFleetPolygonContractError("falsifier payload keys invalid")
    claim = payload["claim"]
    evidence = payload["evidence"]
    if not isinstance(claim, bool) or not isinstance(evidence, bool):
        raise DockerFleetPolygonContractError("claim/evidence must be boolean")
    return {"falsified": claim != evidence, "claim": claim, "evidence": evidence}


OPERATIONS = {
    "ARCHITECTURE_DIGEST": _architecture,
    "SECURITY_INVARIANTS": _security,
    "RUNTIME_BINDINGS": _runtime_bindings,
    "PROVENANCE_RELATIONSHIPS": _provenance,
    "FALSIFY_CLAIM": _falsify,
}


def execute_capsule(capsule: MissionCapsule) -> DroneResult:
    capsule.validate(now=datetime.now(timezone.utc))
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result_body = OPERATIONS[capsule.operation](capsule.input_payload)
    result_digest = digest_domain(b"LION/DRONE-RESULT-BODY/P0", result_body)
    completed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    identity = {
        "mission_id": capsule.mission_id,
        "fleet_id": capsule.fleet_id,
        "drone_id": capsule.drone_id,
        "generation": capsule.generation,
        "work_unit_id": capsule.work_unit_id,
        "input_digest": capsule.input_digest,
        "result_digest": result_digest,
    }
    result = DroneResult(
        result_id=digest_domain(b"LION/DRONE-RESULT/P0", identity),
        mission_id=capsule.mission_id,
        fleet_id=capsule.fleet_id,
        drone_id=capsule.drone_id,
        role=capsule.role,
        generation=capsule.generation,
        work_unit_id=capsule.work_unit_id,
        status="SUCCEEDED",
        result=result_body,
        input_digest=capsule.input_digest,
        result_digest=result_digest,
        started_at=started,
        completed_at=completed,
        evidence=(f"capsule:sha256:{capsule.capsule_digest}",),
    )
    result.validate()
    return result


def main() -> int:
    try:
        raw = json.loads(CAPSULE_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise DockerFleetPolygonContractError("capsule root must be object")
        capsule = _capsule_from_mapping(raw)
        result = execute_capsule(capsule)
        sys.stdout.buffer.write(canonical_json(result.canonical_dict()) + b"\n")
        return 0
    except Exception as exc:
        denied = {
            "schema_version": "1.0.0",
            "status": "DENIED",
            "error_type": type(exc).__name__,
            "error": str(exc)[:512],
        }
        sys.stdout.buffer.write(canonical_json(denied) + b"\n")
        return 23


if __name__ == "__main__":
    raise SystemExit(main())

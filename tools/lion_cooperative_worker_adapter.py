"""Mission Control assignment consumer; never turn a claim into write authority.

An admitted_writer is a trusted composition dependency, never a payload field.
Without a canonical runtime writer the write branch fails before touching the
filesystem. Readback remains a read-only operation with a validated claim.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from cyber_lion.mission_control.cooperative_artifacts import (
    WRITE_KIND, VERIFY_KIND, CooperativeArtifactError,
    validate_write_payload, verify_text,
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def assignment_input(row: Mapping[str, Any]) -> dict[str, Any]:
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise CooperativeArtifactError("duplicate input key")
            out[key] = value
        return out
    value = row.get("input")
    raw = row.get("input_json")
    parsed = None
    if raw is not None:
        if type(raw) is not str or len(raw.encode("utf-8")) > 800000:
            raise CooperativeArtifactError("assignment input JSON limit/type")
        parsed = json.loads(raw, object_pairs_hook=unique,
                            parse_constant=lambda _: (_ for _ in ()).throw(CooperativeArtifactError("nonfinite JSON")))
        if type(parsed) is not dict:
            raise CooperativeArtifactError("assignment input object required")
    if value is not None:
        if type(value) is not dict or (parsed is not None and _canonical(parsed) != _canonical(value)):
            raise CooperativeArtifactError("ambiguous assignment input")
        parsed = dict(value)
    if parsed is None:
        raise CooperativeArtifactError("claimed input missing")
    dg = row.get("input_digest")
    if dg is not None and sha256(_canonical(parsed)).hexdigest() != dg:
        raise CooperativeArtifactError("assignment input digest mismatch")
    return parsed


def _claim_payload(row, claimed, worker, kind, now_fn):
    for key in ("assignment_id", "mission_id", "material_drone_id", "lease_generation"):
        if key not in row or claimed.get(key) != row[key]:
            raise CooperativeArtifactError("claim binding mismatch: " + key)
    if claimed.get("material_drone_id") != worker or claimed.get("state") != "CLAIMED":
        raise CooperativeArtifactError("claim worker/state mismatch")
    generation = claimed.get("lease_generation")
    if type(generation) is not int or generation < 1:
        raise CooperativeArtifactError("claim generation invalid")
    expires = claimed.get("lease_expires_at")
    if type(expires) is not str:
        raise CooperativeArtifactError("claim expiry missing")
    deadline = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    now = now_fn()
    if deadline.tzinfo is None or now.tzinfo is None or now >= deadline:
        raise CooperativeArtifactError("claim lease expired or unzoned")
    payload = assignment_input(claimed)
    if payload.get("kind") != kind or payload.get("mission_id") != claimed["mission_id"]:
        raise CooperativeArtifactError("claimed payload kind/mission mismatch")
    if type(payload.get("generation")) is not int or payload["generation"] != generation:
        raise CooperativeArtifactError("payload generation mismatch")
    if "assignment_id" in payload and payload["assignment_id"] != claimed["assignment_id"]:
        raise CooperativeArtifactError("payload assignment substitution")
    payload["assignment_id"] = claimed["assignment_id"]
    return payload


def cooperative_assignment_once(
    control: Callable[[str, dict[str, Any]], dict[str, Any]], *,
    material_drone_id: str, artifact_root: str | Path,
    pending: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    admitted_writer: Callable[..., dict[str, Any]] | None = None,
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any] | None:
    for row in pending:
        if row.get("material_drone_id") != material_drone_id:
            continue
        try:
            kind = assignment_input(row).get("kind")
        except (ValueError, TypeError, UnicodeError):
            continue
        if kind not in {WRITE_KIND, VERIFY_KIND}:
            continue
        assignment_id = row.get("assignment_id")
        if type(assignment_id) is not str or not assignment_id:
            continue
        try:
            claimed = control("local_assignment_claim", {"assignment_id": assignment_id, "material_drone_id": material_drone_id})
        except Exception:
            continue
        effect_digest = None
        try:
            payload = _claim_payload(row, claimed, material_drone_id, kind, now_fn)
            if kind == WRITE_KIND:
                expected, _ = validate_write_payload(payload, material_drone_id)
                if not callable(admitted_writer):
                    raise CooperativeArtifactError("RUNTIME_ADMISSION_WRITER_NOT_BOUND")
                # The bound writer MUST perform live admission, fencing and
                # single-use consumption through RuntimeExecutionEngine.
                result = admitted_writer(claimed=claimed, payload=payload,
                                         artifact_root=artifact_root, worker_id=material_drone_id)
                if type(result) is not dict or any(result.get(k) != v for k,v in expected.items()) or result.get("readback_match") is not True:
                    raise CooperativeArtifactError("admitted writer result mismatch")
                effect_digest = result.get("effect_receipt_digest")
                if type(effect_digest) is not str or len(effect_digest) != 64 or any(c not in "0123456789abcdef" for c in effect_digest):
                    raise CooperativeArtifactError("admitted runtime receipt missing")
            else:
                result = verify_text(artifact_root, payload, worker_id=material_drone_id)
            status = "PASS"
        except Exception as exc:
            result = {"kind": str(kind), "error": type(exc).__name__ + ":" + str(exc)[:600],
                      "material_worker_id": material_drone_id, "authority_effect": "NONE"}
            status = "FAIL"
        # A receipt transmission failure is not converted into a second receipt
        # or a replay of the operation. The existing ledger must reconcile it.
        return control("local_assignment_receipt", {
            "assignment_id": assignment_id, "material_drone_id": material_drone_id,
            "lease_generation": claimed.get("lease_generation"), "status": status,
            "result": result, "effect_receipt_digest": effect_digest,
        })
    return None

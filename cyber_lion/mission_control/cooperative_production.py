"""Durable cooperative-production stepper built on the existing scheduler ledger.

This module is not a scheduler daemon. It is a bounded provider invoked by the
existing Mission Control driver. Each call advances at most one idempotent edge
of MODEL -> WRITE -> VERIFY and otherwise returns the current wait state.
"""
from __future__ import annotations

from hashlib import sha256
from datetime import datetime, timezone
from cyber_lion.mission_control.cooperative_readiness import observation_ready
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from cyber_lion.mission_control import global_scheduler
from cyber_lion.mission_control.cooperative_artifacts import WRITE_KIND, VERIFY_KIND

CAPABILITY_BOOTSTRAP = "COOPERATIVE_ARTIFACT_BOOTSTRAP"
CAPABILITY_PRODUCTION = "COOPERATIVE_ARTIFACT_PRODUCTION"
CAPABILITY_VERIFY = "COOPERATIVE_ARTIFACT_VERIFY"
CAPABILITY_ID_BOOTSTRAP = "COOPERATIVE_ARTIFACT_BOOTSTRAP_R1"
CAPABILITY_ID_PRODUCTION = "COOPERATIVE_ARTIFACT_PRODUCTION_R1"
CAPABILITY_ID_VERIFY = "COOPERATIVE_ARTIFACT_VERIFY_R1"
EXECUTOR_ID = "MISSION_CONTROL_COOPERATIVE_PRODUCTION_PROVIDER"

MODEL_SUFFIX = "__COOP_MODEL"
WRITE_SUFFIX = "__COOP_WRITE"
VERIFY_SUFFIX = "__COOP_VERIFY"
WRITE_MATERIALIZATION_KIND = "RUNTIME_CONTEXT"
WRITE_PROVIDER_ID = "COOPERATIVE_RUNTIME_WRITER_R5"
VERIFY_MATERIALIZATION_KIND = "VERIFIER_TRANSFER"
VERIFY_PROVIDER_ID = "COOPERATIVE_ARTIFACT_TRANSFER_R1"
_MATERIALIZER_RESULT_FIELDS = frozenset({"materialization_kind","provider_id","evidence_digest","authority_effect"})


class CooperativeProductionError(RuntimeError):
    pass


def capability_registry_entries() -> dict[str, tuple[dict[str, str], ...]]:
    return {
        CAPABILITY_BOOTSTRAP: ({
            "capability_id": CAPABILITY_ID_BOOTSTRAP,
            "executor_id": EXECUTOR_ID,
            "effect_ceiling": "NONE",
            "mode": "VERIFY_INSTALLED_WORKER_PROVIDER",
        },),
        CAPABILITY_PRODUCTION: ({
            "capability_id": CAPABILITY_ID_PRODUCTION,
            "executor_id": EXECUTOR_ID,
            "effect_ceiling": "BOUNDED_MATERIAL",
            "mode": "MODEL_TO_ARTIFACT_LEDGER_PIPELINE",
        },),
        CAPABILITY_VERIFY: ({
            "capability_id": CAPABILITY_ID_VERIFY,
            "executor_id": EXECUTOR_ID,
            "effect_ceiling": "NONE",
            "mode": "INDEPENDENT_ARTIFACT_READBACK",
        },),
    }


def _assignment(conn, mission_id: str, phase_id: str):
    row = conn.execute(
        """SELECT * FROM mission_execution_assignments
           WHERE mission_id=? AND phase_id=?
           ORDER BY created_at DESC, assignment_id DESC LIMIT 1""",
        (mission_id, phase_id),
    ).fetchone()
    return dict(row) if row else None


def _payload(conn, assignment_id: str) -> dict[str, Any] | None:
    row = global_scheduler.assignment_payload(conn, assignment_id)
    if not row:
        return None
    result = row.get("result")
    return dict(result) if isinstance(result, Mapping) else {}


def _receipt(conn, assignment_id: str):
    row = conn.execute(
        """SELECT receipt_id,result_digest,status,observed_at
           FROM mission_execution_receipts
           WHERE assignment_id=?
           ORDER BY observed_at DESC, receipt_id DESC LIMIT 1""",
        (assignment_id,),
    ).fetchone()
    return dict(row) if row else None


def _create(
    conn,
    *,
    mission_id: str,
    phase_id: str,
    logical_drone_id: str,
    material_drone_id: str,
    payload: dict[str, Any],
    generation: int,
    now_fn,
    held: bool = False,
) -> str:
    creator = global_scheduler.create_held_assignment if held else global_scheduler.create_assignment
    return creator(
        conn,
        mission_id,
        phase_id,
        logical_drone_id,
        material_drone_id,
        payload,
        now_fn,
        lease_generation=int(generation),
    )


def _materialize_and_release(
    conn,
    assignment_id: str,
    *,
    materializer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None,
    expected_kind: str,
    expected_provider: str,
    now_fn,
) -> dict[str, Any] | None:
    """Run a trusted non-authorizing materializer once for a newly HELD assignment."""
    if materializer is None:
        return None
    row = conn.execute(
        "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
        (assignment_id,),
    ).fetchone()
    if row is None or row["state"] != "HELD":
        raise CooperativeProductionError("held assignment unavailable for materialization")
    try:
        payload = json.loads(row["input_json"] or "{}")
    except Exception as exc:
        raise CooperativeProductionError("held assignment input unavailable") from exc
    presented = {"assignment": dict(row), "input": payload}
    result = materializer(presented)
    if not isinstance(result, Mapping) or set(result) != _MATERIALIZER_RESULT_FIELDS:
        raise CooperativeProductionError("materializer result schema")
    value = dict(result)
    if (
        value.get("materialization_kind") != expected_kind
        or value.get("provider_id") != expected_provider
        or value.get("authority_effect") != "NONE"
    ):
        raise CooperativeProductionError("materializer identity/authority mismatch")
    evidence_digest = value.get("evidence_digest")
    if (
        type(evidence_digest) is not str
        or len(evidence_digest) != 64
        or any(ch not in "0123456789abcdef" for ch in evidence_digest)
    ):
        raise CooperativeProductionError("materializer evidence digest")
    release = {
        "schema": global_scheduler.ASSIGNMENT_RELEASE_EVIDENCE_SCHEMA,
        "assignment_id": row["assignment_id"],
        "mission_id": row["mission_id"],
        "material_drone_id": row["material_drone_id"],
        "lease_generation": int(row["lease_generation"]),
        "control_epoch": int(row["control_epoch"]),
        "context_revision": int(row["context_revision"]),
        "plan_revision": int(row["plan_revision"]),
        "capability": payload.get("capability"),
        "materialization_kind": expected_kind,
        "provider_id": expected_provider,
        "evidence_digest": evidence_digest,
        "authority_effect": "NONE",
    }
    global_scheduler.release_held_assignment(conn, assignment_id, release, now_fn)
    return value


def bootstrap_readiness(status_dir: str | Path, *, expected_workers: int = 32, now_fn=lambda: datetime.now(timezone.utc)) -> dict[str, Any]:
    root = Path(status_dir)
    if not root.is_dir():
        raise CooperativeProductionError("status directory unavailable")
    required_kinds = {"COOPERATIVE_ARTIFACT_WRITE", "COOPERATIVE_ARTIFACT_VERIFY"}
    required_caps = {"COOPERATIVE_ARTIFACT_MATERIALIZATION", "COOPERATIVE_ARTIFACT_INDEPENDENT_VERIFY"}
    if type(expected_workers) is not int or not 1 <= expected_workers <= 32:
        raise CooperativeProductionError("invalid worker count")
    workers = []
    seen_runtime_ids = set()
    observed_now = now_fn()
    if observed_now.tzinfo is None:
        raise CooperativeProductionError("timezone-aware observation required")
    for idx in range(1, expected_workers + 1):
        path = root / f"MD{idx:03d}.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise CooperativeProductionError(f"worker status unavailable MD{idx:03d}") from exc
        if value.get("material_worker_id") != f"MD{idx:03d}":
            raise CooperativeProductionError("worker status identity mismatch")
        try:
            at = datetime.fromisoformat(value["observed_at"].replace("Z", "+00:00"))
            if at.tzinfo is None:
                raise ValueError("unqualified timestamp")
            age = (observed_now - at).total_seconds()
        except (KeyError, TypeError, ValueError) as exc:
            raise CooperativeProductionError("worker observation timestamp invalid") from exc
        if not observation_ready({**value, "age_seconds": age}):
            raise CooperativeProductionError(f"worker observation stale or unavailable MD{idx:03d}")
        runtime_id = (value.get("architecture") or {}).get("runtime_instance_id")
        if type(runtime_id) is not str or not runtime_id or runtime_id in seen_runtime_ids:
            raise CooperativeProductionError("missing or duplicate runtime identity")
        seen_runtime_ids.add(runtime_id)
        direct = set(value.get("direct_assignment_kinds") or ())
        arch = set(((value.get("architecture") or {}).get("architecture_capabilities") or ()))
        provider = value.get("cooperative_runtime_provider")
        if value.get("state") != "READY" or value.get("self_test") != "PASS":
            raise CooperativeProductionError(f"worker not ready MD{idx:03d}")
        if not required_kinds.issubset(direct):
            raise CooperativeProductionError(f"worker assignment capability missing MD{idx:03d}")
        if not required_caps.issubset(arch):
            raise CooperativeProductionError(f"worker architecture capability missing MD{idx:03d}")
        if type(provider) is not dict or provider != {
            "state": "READY",
            "provider_id": "COOPERATIVE_RUNTIME_WRITER_R5",
            "context_resolver": "PINNED_COOPERATIVE_CONTEXT_RESOLVER",
            "execution_engine": "RUNTIME_EXECUTION_ENGINE",
            "authority_effect": "NONE",
        }:
            raise CooperativeProductionError(f"canonical cooperative runtime provider unavailable MD{idx:03d}")
        workers.append({
            "material_worker_id": f"MD{idx:03d}",
            "runtime_instance_id": runtime_id,
            "state": value.get("state"),
        })
    return {
        "status": "PASS",
        "worker_count": len(workers),
        "workers": workers,
        "authority_effect": "NONE",
    }


def advance_production(
    conn,
    *,
    mission_id: str,
    phase_id: str,
    generation: int,
    now_fn,
    logical_drone_id: str = "LD001",
    builder_worker_id: str = "MD001",
    verifier_worker_id: str = "MD002",
    artifact_name: str = "lion-pilot-artifact.txt",
    write_materializer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    verify_materializer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Advance one cooperative production edge for one mission generation."""
    model_phase = phase_id + MODEL_SUFFIX
    write_phase = phase_id + WRITE_SUFFIX
    verify_phase = phase_id + VERIFY_SUFFIX

    model = _assignment(conn, mission_id, model_phase)
    if model is None:
        prompt = (
            "Create one small UTF-8 text artifact for a LION cooperative-production canary. "
            "Return plain text only, no markdown fences. Include exactly three lines: "
            "purpose=cooperative-production, mission=" + mission_id + ", status=generated-by-local-model."
        )
        aid = _create(
            conn,
            mission_id=mission_id,
            phase_id=model_phase,
            logical_drone_id=logical_drone_id,
            material_drone_id=builder_worker_id,
            payload={
                "kind": "LOCAL_MODEL_INFERENCE",
                "capability": CAPABILITY_PRODUCTION,
                "model_capability": CAPABILITY_PRODUCTION,
                "purpose": "COOPERATIVE_ARTIFACT_SOURCE_GENERATION",
                "trajectory_role": "BUILDER",
                "task_id": mission_id + ":artifact-source",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 256,
                "lease_scope": "MISSION_DRIVER",
                "authority_effect": "NONE",
            },
            generation=generation,
            now_fn=now_fn,
        )
        return {"state": "WAITING", "gate": "MODEL_ASSIGNMENT", "assignment_id": aid, "authority_effect": "NONE"}

    if model["state"] in {"READY", "CLAIMED"}:
        return {"state": "WAITING", "gate": "MODEL_ASSIGNMENT", "assignment_id": model["assignment_id"], "authority_effect": "NONE"}
    if model["state"] != "PASS":
        return {"state": "FAILED", "gate": "MODEL_ASSIGNMENT_FAILED", "assignment_id": model["assignment_id"], "authority_effect": "NONE"}

    model_result = _payload(conn, model["assignment_id"])
    model_receipt = _receipt(conn, model["assignment_id"])
    if not model_result or not model_receipt:
        return {"state": "WAITING", "gate": "MODEL_PAYLOAD_RETENTION", "assignment_id": model["assignment_id"], "authority_effect": "NONE"}
    content = model_result.get("response_text")
    response_digest = model_result.get("response_digest")
    model_call_id = model_result.get("model_call_id")
    if not isinstance(content, str) or not content.strip():
        raise CooperativeProductionError("model response text missing")
    content = content.strip() + "\n"
    content_digest = sha256(content.encode("utf-8")).hexdigest()
    if not isinstance(response_digest, str) or len(response_digest) != 64 or not isinstance(model_call_id, str):
        raise CooperativeProductionError("model provenance missing")

    write = _assignment(conn, mission_id, write_phase)
    if write is None:
        aid = _create(
            conn,
            mission_id=mission_id,
            phase_id=write_phase,
            logical_drone_id=logical_drone_id,
            material_drone_id=builder_worker_id,
            payload={
                "kind": WRITE_KIND,
                "mission_id": mission_id,
                "generation": int(generation),
                "artifact_name": artifact_name,
                "content": content,
                "expected_sha256": content_digest,
                "producer_model_call_id": model_call_id,
                "parent_response_digest": response_digest,
                "capability": CAPABILITY_PRODUCTION,
                "lease_scope": "MISSION_DRIVER",
                "authority_effect": "NONE",
            },
            generation=generation,
            now_fn=now_fn,
            held=True,
        )
        if write_materializer is None:
            return {"state": "WAITING", "gate": "RUNTIME_CONTEXT_PROVIDER_REQUIRED", "assignment_id": aid, "authority_effect": "NONE"}
        try:
            materialized = _materialize_and_release(
                conn, aid, materializer=write_materializer,
                expected_kind=WRITE_MATERIALIZATION_KIND,
                expected_provider=WRITE_PROVIDER_ID, now_fn=now_fn,
            )
        except Exception as exc:
            return {"state": "FAILED", "gate": "RUNTIME_CONTEXT_MATERIALIZATION_FAILED",
                    "assignment_id": aid, "error_class": type(exc).__name__, "authority_effect": "NONE"}
        return {"state": "WAITING", "gate": "ARTIFACT_WRITE", "assignment_id": aid,
                "materialization": materialized, "authority_effect": "NONE"}
    if write["state"] == "HELD":
        return {"state": "WAITING", "gate": "RUNTIME_CONTEXT_PROVIDER_REQUIRED", "assignment_id": write["assignment_id"], "authority_effect": "NONE"}
    if write["state"] in {"READY", "CLAIMED"}:
        return {"state": "WAITING", "gate": "ARTIFACT_WRITE", "assignment_id": write["assignment_id"], "authority_effect": "NONE"}
    if write["state"] != "PASS":
        return {"state": "FAILED", "gate": "ARTIFACT_WRITE_FAILED", "assignment_id": write["assignment_id"], "authority_effect": "NONE"}

    write_result = _payload(conn, write["assignment_id"])
    write_receipt = _receipt(conn, write["assignment_id"])
    if not write_result or not write_receipt:
        return {"state": "WAITING", "gate": "ARTIFACT_WRITE_PAYLOAD", "assignment_id": write["assignment_id"], "authority_effect": "NONE"}
    artifact_digest = write_result.get("artifact_sha256")
    if artifact_digest != content_digest or write_result.get("producer_worker_id") != builder_worker_id:
        raise CooperativeProductionError("artifact write provenance mismatch")

    verify = _assignment(conn, mission_id, verify_phase)
    if verify is None:
        aid = _create(
            conn,
            mission_id=mission_id,
            phase_id=verify_phase,
            logical_drone_id="LD002" if logical_drone_id == "LD001" else logical_drone_id,
            material_drone_id=verifier_worker_id,
            payload={
                "kind": VERIFY_KIND,
                "mission_id": mission_id,
                "source_assignment_id": write["assignment_id"],
                "generation": int(generation),
                "artifact_name": artifact_name,
                "expected_sha256": artifact_digest,
                "expected_producer_worker_id": builder_worker_id,
                "capability": CAPABILITY_VERIFY,
                "lease_scope": "MISSION_DRIVER",
                "authority_effect": "NONE",
            },
            generation=generation,
            now_fn=now_fn,
            held=True,
        )
        if verify_materializer is None:
            return {"state": "WAITING", "gate": "VERIFIER_TRANSFER_REQUIRED", "assignment_id": aid, "authority_effect": "NONE"}
        try:
            materialized = _materialize_and_release(
                conn, aid, materializer=verify_materializer,
                expected_kind=VERIFY_MATERIALIZATION_KIND,
                expected_provider=VERIFY_PROVIDER_ID, now_fn=now_fn,
            )
        except Exception as exc:
            return {"state": "FAILED", "gate": "VERIFIER_TRANSFER_MATERIALIZATION_FAILED",
                    "assignment_id": aid, "error_class": type(exc).__name__, "authority_effect": "NONE"}
        return {"state": "WAITING", "gate": "ARTIFACT_VERIFY", "assignment_id": aid,
                "materialization": materialized, "authority_effect": "NONE"}
    if verify["state"] == "HELD":
        return {"state": "WAITING", "gate": "VERIFIER_TRANSFER_REQUIRED", "assignment_id": verify["assignment_id"], "authority_effect": "NONE"}
    if verify["state"] in {"READY", "CLAIMED"}:
        return {"state": "WAITING", "gate": "ARTIFACT_VERIFY", "assignment_id": verify["assignment_id"], "authority_effect": "NONE"}
    if verify["state"] != "PASS":
        return {"state": "FAILED", "gate": "ARTIFACT_VERIFY_FAILED", "assignment_id": verify["assignment_id"], "authority_effect": "NONE"}

    verify_result = _payload(conn, verify["assignment_id"])
    verify_receipt = _receipt(conn, verify["assignment_id"])
    if not verify_result or not verify_receipt:
        return {"state": "WAITING", "gate": "ARTIFACT_VERIFY_PAYLOAD", "assignment_id": verify["assignment_id"], "authority_effect": "NONE"}
    if verify_result.get("artifact_sha256") != artifact_digest or verify_result.get("digest_match") is not True:
        raise CooperativeProductionError("artifact verification mismatch")

    return {
        "state": "PASS",
        "mission_id": mission_id,
        "generation": int(generation),
        "model_assignment_id": model["assignment_id"],
        "model_receipt_id": model_receipt["receipt_id"],
        "model_call_id": model_call_id,
        "write_assignment_id": write["assignment_id"],
        "write_receipt_id": write_receipt["receipt_id"],
        "verify_assignment_id": verify["assignment_id"],
        "verify_receipt_id": verify_receipt["receipt_id"],
        "artifact_name": artifact_name,
        "artifact_sha256": artifact_digest,
        "artifact_path": write_result.get("artifact_path"),
        "builder_worker_id": builder_worker_id,
        "verifier_worker_id": verifier_worker_id,
        "authority_effect": "NONE",
    }


def advance_build(
    conn,
    *,
    mission_id: str,
    phase_id: str,
    generation: int,
    now_fn,
    logical_drone_id: str = "LD001",
    builder_worker_id: str = "MD001",
    artifact_name: str = "lion-pilot-artifact.txt",
    write_materializer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Advance MODEL -> WRITE and stop once the artifact is materially observed."""
    model_phase = phase_id + MODEL_SUFFIX
    write_phase = phase_id + WRITE_SUFFIX
    model = _assignment(conn, mission_id, model_phase)
    if model is None:
        prompt = (
            "Create one small UTF-8 text artifact for a LION cooperative-production canary. "
            "Return plain text only, no markdown fences. Include exactly three lines: "
            "purpose=cooperative-production, mission=" + mission_id + ", status=generated-by-local-model."
        )
        aid = _create(
            conn, mission_id=mission_id, phase_id=model_phase,
            logical_drone_id=logical_drone_id, material_drone_id=builder_worker_id,
            payload={
                "kind": "LOCAL_MODEL_INFERENCE",
                "capability": CAPABILITY_PRODUCTION,
                "model_capability": CAPABILITY_PRODUCTION,
                "purpose": "COOPERATIVE_ARTIFACT_SOURCE_GENERATION",
                "trajectory_role": "BUILDER",
                "task_id": mission_id + ":artifact-source",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 256,
                "lease_scope": "MISSION_DRIVER",
                "authority_effect": "NONE",
            },
            generation=generation, now_fn=now_fn,
        )
        return {"state": "WAITING", "gate": "MODEL_ASSIGNMENT", "assignment_id": aid, "authority_effect": "NONE"}
    if model["state"] in {"READY", "CLAIMED"}:
        return {"state": "WAITING", "gate": "MODEL_ASSIGNMENT", "assignment_id": model["assignment_id"], "authority_effect": "NONE"}
    if model["state"] != "PASS":
        return {"state": "FAILED", "gate": "MODEL_ASSIGNMENT_FAILED", "assignment_id": model["assignment_id"], "authority_effect": "NONE"}
    model_result = _payload(conn, model["assignment_id"])
    model_receipt = _receipt(conn, model["assignment_id"])
    if not model_result or not model_receipt:
        return {"state": "WAITING", "gate": "MODEL_PAYLOAD_RETENTION", "assignment_id": model["assignment_id"], "authority_effect": "NONE"}
    content = model_result.get("response_text")
    response_digest = model_result.get("response_digest")
    model_call_id = model_result.get("model_call_id")
    if not isinstance(content, str) or not content.strip():
        raise CooperativeProductionError("model response text missing")
    content = content.strip() + "\n"
    content_digest = sha256(content.encode("utf-8")).hexdigest()
    if not isinstance(response_digest, str) or len(response_digest) != 64 or not isinstance(model_call_id, str):
        raise CooperativeProductionError("model provenance missing")
    write = _assignment(conn, mission_id, write_phase)
    if write is None:
        aid = _create(
            conn, mission_id=mission_id, phase_id=write_phase,
            logical_drone_id=logical_drone_id, material_drone_id=builder_worker_id,
            payload={
                "kind": WRITE_KIND,
                "mission_id": mission_id,
                "generation": int(generation),
                "artifact_name": artifact_name,
                "content": content,
                "expected_sha256": content_digest,
                "producer_model_call_id": model_call_id,
                "parent_response_digest": response_digest,
                "capability": CAPABILITY_PRODUCTION,
                "lease_scope": "MISSION_DRIVER",
                "authority_effect": "NONE",
            },
            generation=generation, now_fn=now_fn, held=True,
        )
        if write_materializer is None:
            return {"state": "WAITING", "gate": "RUNTIME_CONTEXT_PROVIDER_REQUIRED", "assignment_id": aid, "authority_effect": "NONE"}
        try:
            materialized = _materialize_and_release(
                conn, aid, materializer=write_materializer,
                expected_kind=WRITE_MATERIALIZATION_KIND,
                expected_provider=WRITE_PROVIDER_ID, now_fn=now_fn,
            )
        except Exception as exc:
            return {"state": "FAILED", "gate": "RUNTIME_CONTEXT_MATERIALIZATION_FAILED",
                    "assignment_id": aid, "error_class": type(exc).__name__, "authority_effect": "NONE"}
        return {"state": "WAITING", "gate": "ARTIFACT_WRITE", "assignment_id": aid,
                "materialization": materialized, "authority_effect": "NONE"}
    if write["state"] == "HELD":
        return {"state": "WAITING", "gate": "RUNTIME_CONTEXT_PROVIDER_REQUIRED", "assignment_id": write["assignment_id"], "authority_effect": "NONE"}
    if write["state"] in {"READY", "CLAIMED"}:
        return {"state": "WAITING", "gate": "ARTIFACT_WRITE", "assignment_id": write["assignment_id"], "authority_effect": "NONE"}
    if write["state"] != "PASS":
        return {"state": "FAILED", "gate": "ARTIFACT_WRITE_FAILED", "assignment_id": write["assignment_id"], "authority_effect": "NONE"}
    write_result = _payload(conn, write["assignment_id"])
    write_receipt = _receipt(conn, write["assignment_id"])
    if not write_result or not write_receipt:
        return {"state": "WAITING", "gate": "ARTIFACT_WRITE_PAYLOAD", "assignment_id": write["assignment_id"], "authority_effect": "NONE"}
    if write_result.get("artifact_sha256") != content_digest or write_result.get("producer_worker_id") != builder_worker_id:
        raise CooperativeProductionError("artifact write provenance mismatch")
    return {
        "state": "PASS",
        "mission_id": mission_id,
        "generation": int(generation),
        "model_assignment_id": model["assignment_id"],
        "model_receipt_id": model_receipt["receipt_id"],
        "model_call_id": model_call_id,
        "write_assignment_id": write["assignment_id"],
        "write_receipt_id": write_receipt["receipt_id"],
        "artifact_name": artifact_name,
        "artifact_sha256": content_digest,
        "artifact_path": write_result.get("artifact_path"),
        "builder_worker_id": builder_worker_id,
        "authority_effect": "NONE",
    }


def advance_verify(
    conn,
    *,
    mission_id: str,
    build_phase_id: str,
    verify_phase_id: str,
    generation: int,
    now_fn,
    verifier_worker_id: str = "MD002",
    verify_materializer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify the artifact created by advance_build with a distinct worker."""
    write = _assignment(conn, mission_id, build_phase_id + WRITE_SUFFIX)
    if not write or write["state"] != "PASS":
        return {"state": "WAITING", "gate": "BUILD_ARTIFACT_REQUIRED", "authority_effect": "NONE"}
    write_result = _payload(conn, write["assignment_id"])
    if not write_result:
        return {"state": "WAITING", "gate": "BUILD_ARTIFACT_PAYLOAD", "authority_effect": "NONE"}
    artifact_digest = write_result.get("artifact_sha256")
    artifact_name = write_result.get("artifact_name")
    builder_worker_id = write_result.get("producer_worker_id")
    if not isinstance(artifact_digest, str) or len(artifact_digest) != 64:
        raise CooperativeProductionError("artifact digest missing")
    if not isinstance(artifact_name, str) or not artifact_name:
        raise CooperativeProductionError("artifact name missing")
    if not isinstance(builder_worker_id, str) or not builder_worker_id or builder_worker_id == verifier_worker_id:
        raise CooperativeProductionError("independent verifier binding invalid")

    verify_phase = verify_phase_id + VERIFY_SUFFIX
    verify = _assignment(conn, mission_id, verify_phase)
    if verify is None:
        aid = _create(
            conn, mission_id=mission_id, phase_id=verify_phase,
            logical_drone_id="LD002", material_drone_id=verifier_worker_id,
            payload={
                "kind": VERIFY_KIND,
                "mission_id": mission_id,
                "source_assignment_id": write["assignment_id"],
                "generation": int(generation),
                "artifact_name": artifact_name,
                "expected_sha256": artifact_digest,
                "expected_producer_worker_id": builder_worker_id,
                "capability": CAPABILITY_VERIFY,
                "lease_scope": "MISSION_DRIVER",
                "authority_effect": "NONE",
            },
            generation=generation, now_fn=now_fn, held=True,
        )
        if verify_materializer is None:
            return {"state": "WAITING", "gate": "VERIFIER_TRANSFER_REQUIRED", "assignment_id": aid, "authority_effect": "NONE"}
        try:
            materialized = _materialize_and_release(
                conn, aid, materializer=verify_materializer,
                expected_kind=VERIFY_MATERIALIZATION_KIND,
                expected_provider=VERIFY_PROVIDER_ID, now_fn=now_fn,
            )
        except Exception as exc:
            return {"state": "FAILED", "gate": "VERIFIER_TRANSFER_MATERIALIZATION_FAILED",
                    "assignment_id": aid, "error_class": type(exc).__name__, "authority_effect": "NONE"}
        return {"state": "WAITING", "gate": "ARTIFACT_VERIFY", "assignment_id": aid,
                "materialization": materialized, "authority_effect": "NONE"}
    if verify["state"] == "HELD":
        return {"state": "WAITING", "gate": "VERIFIER_TRANSFER_REQUIRED", "assignment_id": verify["assignment_id"], "authority_effect": "NONE"}
    if verify["state"] in {"READY", "CLAIMED"}:
        return {"state": "WAITING", "gate": "ARTIFACT_VERIFY", "assignment_id": verify["assignment_id"], "authority_effect": "NONE"}
    if verify["state"] != "PASS":
        return {"state": "FAILED", "gate": "ARTIFACT_VERIFY_FAILED", "assignment_id": verify["assignment_id"], "authority_effect": "NONE"}
    verify_result = _payload(conn, verify["assignment_id"])
    verify_receipt = _receipt(conn, verify["assignment_id"])
    if not verify_result or not verify_receipt:
        return {"state": "WAITING", "gate": "ARTIFACT_VERIFY_PAYLOAD", "assignment_id": verify["assignment_id"], "authority_effect": "NONE"}
    if verify_result.get("artifact_sha256") != artifact_digest or verify_result.get("digest_match") is not True:
        raise CooperativeProductionError("artifact verification mismatch")
    return {
        "state": "PASS",
        "mission_id": mission_id,
        "generation": int(generation),
        "source_assignment_id": write["assignment_id"],
        "verify_assignment_id": verify["assignment_id"],
        "verify_receipt_id": verify_receipt["receipt_id"],
        "artifact_name": artifact_name,
        "artifact_sha256": artifact_digest,
        "artifact_path": write_result.get("artifact_path"),
        "builder_worker_id": builder_worker_id,
        "verifier_worker_id": verifier_worker_id,
        "authority_effect": "NONE",
    }

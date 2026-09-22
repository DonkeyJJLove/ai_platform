"""R24 material-worker contract surface.

A material worker is a bounded executor endpoint, not an authority source.
This module gives Docker workers contract literacy for the current LION
Action/Runtime plane while keeping host/repository effects outside the worker.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from cyber_lion.contracts.action_ir import CanonicalActionIR
from cyber_lion.contracts.runtime_enforcement import (
    RequestedRuntimeEffect,
    RuntimeAdmission,
    RuntimeIdentityBinding,
)
from cyber_lion.contracts.runtime_execution import RuntimeExecutionRequest

PROFILE = "LION_MATERIAL_EXECUTOR_V2"
STATUS_SCHEMA = "lion.docker-material-worker.status/v2"
IDENTITY_SCHEMA = "lion.material-worker-source-identity/v1"
MODEL_NAME = "gpt-oss-20b-MXFP4"
AUTHORITY_CEILING = "NONE"
INDEPENDENCE_STATE = "NOT_PROVEN_SHARED_MOON_DOMAIN"

DIRECT_ASSIGNMENT_KINDS = (
    "LOCAL_MODEL_INFERENCE",
    "MATERIAL_SANDBOX_CANARY",
    "CANONICAL_ACTION_IR_VALIDATE",
    "RUNTIME_EXECUTION_ENVELOPE_VALIDATE",
    "MATERIAL_PAYLOAD_DIGEST",
    "MATERIAL_CURRENTNESS_PROBE",
)
ARCHITECTURE_CAPABILITIES = (
    "LPCL_PHASE_ASSIGNMENT_CONSUMPTION",
    "OPERATOR_CONTEXT_CONSUMPTION",
    "LEASE_AND_FENCING_BINDING",
    "LOCAL_MODEL_PROPOSAL",
    "CANONICAL_ACTION_IR_VALIDATION",
    "RUNTIME_ENVELOPE_VALIDATION",
    "BOUNDED_TMPFS_CANARY",
    "DETERMINISTIC_PAYLOAD_DIGEST",
    "CURRENTNESS_AND_IDENTITY_REPORT",
    "RECEIPT_RECONCILIATION",
)
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class MaterialWorkerContractError(ValueError):
    pass


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def file_sha256(path: str | Path) -> str:
    h = sha256()
    with Path(path).open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_worker_identity(identity_path: str | Path, worker_path: str | Path, runtime_contract_path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(identity_path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise MaterialWorkerContractError("worker identity unavailable") from exc
    if type(value) is not dict or value.get("schema") != IDENTITY_SCHEMA:
        raise MaterialWorkerContractError("worker identity schema")
    claimed = value.get("identity_digest")
    body = dict(value)
    body.pop("identity_digest", None)
    if not isinstance(claimed, str) or not _SHA256.fullmatch(claimed) or sha256(canonical_json(body)).hexdigest() != claimed:
        raise MaterialWorkerContractError("worker identity digest")
    if value.get("profile") != PROFILE or value.get("authority_ceiling") != AUTHORITY_CEILING:
        raise MaterialWorkerContractError("worker identity profile")
    if value.get("material_executor_independence") != INDEPENDENCE_STATE:
        raise MaterialWorkerContractError("worker independence truth")
    if not _SHA40.fullmatch(str(value.get("source_head") or "")) or not _SHA40.fullmatch(str(value.get("source_tree") or "")):
        raise MaterialWorkerContractError("worker source identity")
    worker_sha = file_sha256(worker_path)
    contract_sha = file_sha256(runtime_contract_path)
    if value.get("worker_source_sha256") != worker_sha:
        raise MaterialWorkerContractError("worker source sha mismatch")
    if value.get("runtime_contract_sha256") != contract_sha:
        raise MaterialWorkerContractError("worker contract sha mismatch")
    required = tuple(value.get("direct_assignment_kinds") or ())
    if required != DIRECT_ASSIGNMENT_KINDS:
        raise MaterialWorkerContractError("worker assignment capability drift")
    architecture = tuple(value.get("architecture_capabilities") or ())
    if architecture != ARCHITECTURE_CAPABILITIES:
        raise MaterialWorkerContractError("worker architecture capability drift")
    return value


def validate_action_ir_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    action = payload.get("action_ir")
    if type(action) is not dict:
        raise MaterialWorkerContractError("action_ir must be an object")
    ir = CanonicalActionIR.from_mapping(action)
    expected = payload.get("expected_action_ir_digest")
    if expected is not None and expected != ir.payload_digest:
        raise MaterialWorkerContractError("action ir expected digest mismatch")
    value = ir.as_dict()
    return {
        "kind": "CANONICAL_ACTION_IR_VALIDATE",
        "action_ir_digest": ir.payload_digest,
        "action_id": value.get("action_id"),
        "action_kind": value.get("kind"),
        "mission_ref": value.get("mission_ref"),
        "authority_effect": "NONE",
    }


def _runtime_obj(cls, value: Any, name: str):
    if type(value) is not dict:
        raise MaterialWorkerContractError(name + " must be an object")
    try:
        return cls(**value).validate()
    except Exception as exc:
        raise MaterialWorkerContractError(name + " invalid") from exc


def validate_runtime_envelope_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    identity = _runtime_obj(RuntimeIdentityBinding, payload.get("runtime_identity"), "runtime_identity")
    effect = _runtime_obj(RequestedRuntimeEffect, payload.get("requested_effect"), "requested_effect")
    request_value = payload.get("execution_request")
    if type(request_value) is not dict:
        raise MaterialWorkerContractError("execution_request must be an object")
    request_value = dict(request_value)
    if isinstance(request_value.get("command"), list):
        request_value["command"] = tuple(request_value["command"])
    request = _runtime_obj(RuntimeExecutionRequest, request_value, "execution_request")
    admission = None
    if payload.get("runtime_admission") is not None:
        admission = _runtime_obj(RuntimeAdmission, payload.get("runtime_admission"), "runtime_admission")
        if request.admission_digest != admission.admission_digest:
            raise MaterialWorkerContractError("runtime admission binding mismatch")
        if admission.requested_effect_digest != effect.digest():
            raise MaterialWorkerContractError("runtime admission effect mismatch")
        if admission.runtime_identity_digest != identity.digest():
            raise MaterialWorkerContractError("runtime admission identity mismatch")
        if admission.provisioned_executor_digest != identity.provisioned_executor_digest:
            raise MaterialWorkerContractError("runtime admission executor mismatch")
    if request.requested_effect_digest != effect.digest():
        raise MaterialWorkerContractError("runtime request effect mismatch")
    if request.runtime_identity_digest != identity.digest():
        raise MaterialWorkerContractError("runtime request identity mismatch")
    if request.provisioned_executor_digest != identity.provisioned_executor_digest:
        raise MaterialWorkerContractError("runtime request executor mismatch")
    if request.mission_id != effect.mission_id:
        raise MaterialWorkerContractError("runtime mission mismatch")
    if request.executor_id != identity.execution_subject:
        raise MaterialWorkerContractError("runtime execution subject mismatch")
    if (request.runtime_instance_id, request.sandbox_id, request.workspace_id) != (
        identity.runtime_instance_id, identity.sandbox_id, identity.workspace_id
    ):
        raise MaterialWorkerContractError("runtime identity coordinates mismatch")
    if (request.action, request.resource) != (effect.action_class, effect.resource):
        raise MaterialWorkerContractError("runtime action/resource mismatch")
    if request.payload_digest != effect.payload_digest:
        raise MaterialWorkerContractError("runtime payload mismatch")
    return {
        "kind": "RUNTIME_EXECUTION_ENVELOPE_VALIDATE",
        "execution_request_digest": request.digest(),
        "requested_effect_digest": effect.digest(),
        "runtime_identity_digest": identity.digest(),
        "runtime_admission_digest": admission.admission_digest if admission else None,
        "mission_id": request.mission_id,
        "executor_id": request.executor_id,
        "action": request.action,
        "resource": request.resource,
        "authority_effect": "NONE",
        "execution_performed": False,
    }


def digest_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    text = payload.get("text")
    if not isinstance(text, str):
        raise MaterialWorkerContractError("digest text must be a string")
    raw = text.encode("utf-8")
    if len(raw) > 131072:
        raise MaterialWorkerContractError("digest text too large")
    return {
        "kind": "MATERIAL_PAYLOAD_DIGEST",
        "payload_sha256": sha256(raw).hexdigest(),
        "payload_bytes": len(raw),
        "authority_effect": "NONE",
    }


def identity_probe(identity: Mapping[str, Any], *, worker_id: str, runtime_instance_id: str, boot_id: str) -> dict[str, Any]:
    return {
        "kind": "MATERIAL_CURRENTNESS_PROBE",
        "worker_profile": PROFILE,
        "material_worker_id": worker_id,
        "runtime_instance_id": runtime_instance_id,
        "boot_id": boot_id,
        "source_head": identity["source_head"],
        "source_tree": identity["source_tree"],
        "worker_source_sha256": identity["worker_source_sha256"],
        "runtime_contract_sha256": identity["runtime_contract_sha256"],
        "direct_assignment_kinds": list(DIRECT_ASSIGNMENT_KINDS),
        "architecture_capabilities": list(ARCHITECTURE_CAPABILITIES),
        "material_executor_independence": INDEPENDENCE_STATE,
        "authority_effect": "NONE",
    }


def architecture_profile(identity: Mapping[str, Any], *, runtime_instance_id: str, boot_id: str) -> dict[str, Any]:
    return {
        "profile": PROFILE,
        "status_schema": STATUS_SCHEMA,
        "source_head": identity["source_head"],
        "source_tree": identity["source_tree"],
        "worker_source_sha256": identity["worker_source_sha256"],
        "runtime_contract_sha256": identity["runtime_contract_sha256"],
        "identity_digest": identity["identity_digest"],
        "runtime_instance_id": runtime_instance_id,
        "boot_id": boot_id,
        "authority_ceiling": AUTHORITY_CEILING,
        "material_executor_independence": INDEPENDENCE_STATE,
        "direct_assignment_kinds": list(DIRECT_ASSIGNMENT_KINDS),
        "architecture_capabilities": list(ARCHITECTURE_CAPABILITIES),
        "model_is_authority": False,
        "tool_availability_is_authority": False,
        "logical_drone_is_material_executor": False,
        "external_effects_require_admission": True,
    }

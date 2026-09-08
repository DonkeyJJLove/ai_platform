"""Provider-independent, non-effectful Model Plane adapter contracts for architecture 1.4.

ASTRA is represented only as a compatibility target. This module contains no endpoint,
secret, model invocation, deployment, authority grant, or runtime-effect implementation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Protocol, Tuple

ASTRA_COMPATIBILITY_TARGET = "ASTRA"
ASTRA_RUNTIME_STATUS = "NOT_OBSERVED"
AUTHORITY_OWNERSHIP = "NONE"
RUNTIME_EFFECT = "NONE"
_SCHEMA = "1.0.0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ModelPlaneAdapterContractError(ValueError):
    pass


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip() or "\x00" in value:
        raise ModelPlaneAdapterContractError(f"{name} invalid")
    return value


def _digest(value: object, name: str) -> str:
    if type(value) is not str or not _SHA256.fullmatch(value):
        raise ModelPlaneAdapterContractError(f"{name} must be sha256 hex")
    return value


def _canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class ModelPlaneIdentity:
    provider_id: str
    model_id: str
    model_contract_digest: str
    compatibility_target: str = ASTRA_COMPATIBILITY_TARGET
    runtime_status: str = ASTRA_RUNTIME_STATUS
    authority_ownership: str = AUTHORITY_OWNERSHIP
    schema_version: str = _SCHEMA

    def validate(self) -> "ModelPlaneIdentity":
        if self.schema_version != _SCHEMA:
            raise ModelPlaneAdapterContractError("unsupported model identity schema")
        _text(self.provider_id, "provider_id")
        _text(self.model_id, "model_id")
        _digest(self.model_contract_digest, "model_contract_digest")
        if self.compatibility_target != ASTRA_COMPATIBILITY_TARGET:
            raise ModelPlaneAdapterContractError("unsupported compatibility target")
        if self.runtime_status != ASTRA_RUNTIME_STATUS:
            raise ModelPlaneAdapterContractError("ASTRA runtime must remain NOT_OBSERVED without runtime evidence")
        if self.authority_ownership != AUTHORITY_OWNERSHIP:
            raise ModelPlaneAdapterContractError("model identity cannot own authority")
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(b"LION/MODEL-PLANE-IDENTITY/1\0" + _canon(asdict(self))).hexdigest()


@dataclass(frozen=True)
class ModelPlaneRequest:
    request_id: str
    model_identity_digest: str
    input_digest: str
    scaffolding_digest: str
    requested_output_kind: str
    deterministic_boundary: str
    inference_boundary: str
    allowed_output_kinds: Tuple[str, ...]
    authority_effect: str = AUTHORITY_OWNERSHIP
    runtime_effect: str = RUNTIME_EFFECT
    schema_version: str = _SCHEMA

    def validate(self) -> "ModelPlaneRequest":
        if self.schema_version != _SCHEMA:
            raise ModelPlaneAdapterContractError("unsupported model request schema")
        for name in ("request_id", "requested_output_kind", "deterministic_boundary", "inference_boundary"):
            _text(getattr(self, name), name)
        for name in ("model_identity_digest", "input_digest", "scaffolding_digest"):
            _digest(getattr(self, name), name)
        if type(self.allowed_output_kinds) is not tuple or not self.allowed_output_kinds:
            raise ModelPlaneAdapterContractError("allowed_output_kinds must be a non-empty tuple")
        if any(type(item) is not str or not item.strip() for item in self.allowed_output_kinds):
            raise ModelPlaneAdapterContractError("allowed_output_kinds invalid")
        if len(self.allowed_output_kinds) != len(set(self.allowed_output_kinds)):
            raise ModelPlaneAdapterContractError("allowed_output_kinds duplicates")
        if self.requested_output_kind not in self.allowed_output_kinds:
            raise ModelPlaneAdapterContractError("requested output kind not allowed")
        if self.authority_effect != AUTHORITY_OWNERSHIP or self.runtime_effect != RUNTIME_EFFECT:
            raise ModelPlaneAdapterContractError("model request may not carry authority or runtime effect")
        return self

    def digest(self) -> str:
        self.validate()
        value = asdict(self)
        value["allowed_output_kinds"] = list(self.allowed_output_kinds)
        return sha256(b"LION/MODEL-PLANE-REQUEST/1\0" + _canon(value)).hexdigest()


@dataclass(frozen=True)
class ModelPlaneCandidate:
    request_id: str
    request_digest: str
    model_identity_digest: str
    output_kind: str
    payload_digest: str
    authority_effect: str = AUTHORITY_OWNERSHIP
    runtime_effect: str = RUNTIME_EFFECT
    schema_version: str = _SCHEMA

    def validate(self) -> "ModelPlaneCandidate":
        if self.schema_version != _SCHEMA:
            raise ModelPlaneAdapterContractError("unsupported model candidate schema")
        _text(self.request_id, "request_id")
        _text(self.output_kind, "output_kind")
        for name in ("request_digest", "model_identity_digest", "payload_digest"):
            _digest(getattr(self, name), name)
        if self.authority_effect != AUTHORITY_OWNERSHIP or self.runtime_effect != RUNTIME_EFFECT:
            raise ModelPlaneAdapterContractError("model candidate may not carry authority or runtime effect")
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(b"LION/MODEL-PLANE-CANDIDATE/1\0" + _canon(asdict(self))).hexdigest()


class ModelProviderAdapter(Protocol):
    """Interface only. Implementations remain outside this non-effectful contract module."""

    def infer(self, request: ModelPlaneRequest) -> ModelPlaneCandidate: ...


def validate_model_candidate(
    identity: ModelPlaneIdentity,
    request: ModelPlaneRequest,
    candidate: ModelPlaneCandidate,
) -> ModelPlaneCandidate:
    """Bind provider/model identity to a proposal-only candidate without granting authority."""

    if type(identity) is not ModelPlaneIdentity:
        raise ModelPlaneAdapterContractError("exact ModelPlaneIdentity required")
    if type(request) is not ModelPlaneRequest:
        raise ModelPlaneAdapterContractError("exact ModelPlaneRequest required")
    if type(candidate) is not ModelPlaneCandidate:
        raise ModelPlaneAdapterContractError("exact ModelPlaneCandidate required")
    identity.validate()
    request.validate()
    candidate.validate()
    identity_digest = identity.digest()
    if request.model_identity_digest != identity_digest:
        raise ModelPlaneAdapterContractError("request/model identity substitution denied")
    if (
        candidate.request_id,
        candidate.request_digest,
        candidate.model_identity_digest,
        candidate.output_kind,
    ) != (
        request.request_id,
        request.digest(),
        identity_digest,
        request.requested_output_kind,
    ):
        raise ModelPlaneAdapterContractError("candidate/request/model substitution denied")
    return candidate

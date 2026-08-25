"""Canonical non-effectful admission request derived from GovernedChangeProposal."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Tuple

SCHEMA_VERSION = "1.0.0"
_DOMAIN = b"LION/E004-GOVERNED-CHANGE-ADMISSION/1\0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_ALLOWED_ACTIONS = frozenset({"BUILD_CANDIDATE", "RUN_TEST", "REQUEST_PR"})
_LANES = frozenset({"GREEN", "AMBER", "RED"})
_AUTHORITIES = frozenset({"none", "read", "local_write", "external_write", "financial", "deploy", "privileged"})


class GovernedChangeAdmissionContractError(ValueError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: Any, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise GovernedChangeAdmissionContractError(f"{name} invalid")
    return value


def _id(value: Any, name: str) -> str:
    value = _text(value, name, 256)
    if not _SAFE_ID.fullmatch(value):
        raise GovernedChangeAdmissionContractError(f"{name} invalid")
    return value


def _digest(value: Any, name: str) -> str:
    value = _text(value, name, 64)
    if not _SHA256.fullmatch(value):
        raise GovernedChangeAdmissionContractError(f"{name} must be sha256 hex")
    return value


def _refs(value: Any, name: str, *, nonempty: bool = False) -> Tuple[str, ...]:
    if type(value) is not tuple or (nonempty and not value):
        raise GovernedChangeAdmissionContractError(f"{name} must be tuple")
    for item in value:
        _text(item, name, 2048)
    if len(set(value)) != len(value):
        raise GovernedChangeAdmissionContractError(f"{name} must be unique")
    return value


def _candidate_scope(value: Any) -> Tuple[str, ...]:
    _refs(value, "candidate_scope", nonempty=True)
    for path in value:
        if path.startswith("/") or "\\" in path or ".." in path.split("/") or "*" in path:
            raise GovernedChangeAdmissionContractError("candidate_scope invalid")
    return value


def _resource_scope(value: Any) -> Tuple[str, ...]:
    _refs(value, "requested_resource_scope", nonempty=True)
    for resource in value:
        if not resource.startswith("repo-path:") or "*" in resource or ".." in resource.split("/"):
            raise GovernedChangeAdmissionContractError("requested_resource_scope invalid")
    return value


@dataclass(frozen=True)
class GovernedChangeAdmissionRequest:
    schema_version: str
    request_id: str
    proposal_id: str
    proposal_digest: str
    epoch_id: str
    source_delta_digest: str
    source_epoch_transition_digest: str
    source_memory_head: str
    source_promotion_digest: str
    repository: str
    target_component: str
    candidate_scope: Tuple[str, ...]
    requested_action: str
    requested_resource_scope: Tuple[str, ...]
    risk_class: str
    lane: str
    requested_authority: str
    evidence_refs: Tuple[str, ...]
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    admission_request_digest: str = ""

    def canonical_payload(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("admission_request_digest")
        for name in ("candidate_scope", "requested_resource_scope", "evidence_refs"):
            value[name] = list(value[name])
        return value

    def compute_digest(self) -> str:
        return sha256(_DOMAIN + canonical_json(self.canonical_payload())).hexdigest()

    def validate(self) -> "GovernedChangeAdmissionRequest":
        if self.schema_version != SCHEMA_VERSION:
            raise GovernedChangeAdmissionContractError("unsupported admission schema")
        for name in ("request_id", "proposal_id", "epoch_id"):
            _id(getattr(self, name), name)
        for name in (
            "proposal_digest", "source_delta_digest", "source_epoch_transition_digest",
            "source_memory_head", "source_promotion_digest",
        ):
            _digest(getattr(self, name), name)
        _text(self.repository, "repository", 512)
        _text(self.target_component, "target_component")
        _candidate_scope(self.candidate_scope)
        if self.requested_action not in _ALLOWED_ACTIONS:
            raise GovernedChangeAdmissionContractError("unsupported requested_action")
        _resource_scope(self.requested_resource_scope)
        if self.risk_class not in _LANES:
            raise GovernedChangeAdmissionContractError("invalid risk_class")
        if self.lane not in _LANES:
            raise GovernedChangeAdmissionContractError("invalid lane")
        if self.requested_authority not in _AUTHORITIES:
            raise GovernedChangeAdmissionContractError("invalid requested_authority")
        _refs(self.evidence_refs, "evidence_refs", nonempty=True)
        if self.authority_effect != "NONE" or self.execution_effect != "NONE":
            raise GovernedChangeAdmissionContractError("admission request cannot carry effect authority")
        if self.admission_request_digest:
            _digest(self.admission_request_digest, "admission_request_digest")
            if self.admission_request_digest != self.compute_digest():
                raise GovernedChangeAdmissionContractError("admission_request_digest mismatch")
        return self

    def sealed(self) -> "GovernedChangeAdmissionRequest":
        self.validate()
        return GovernedChangeAdmissionRequest(**{**asdict(self), "admission_request_digest": self.compute_digest()}).validate()

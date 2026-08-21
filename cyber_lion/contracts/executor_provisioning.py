"""Immutable contracts for bounded executor provisioning (F005-D).

Provisioning materializes an execution context. It does not grant repository authority,
attach merge authority, carry credential material, execute a repository mutation, or
promote fleet scale. Credential access is represented only by opaque broker handles.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from typing import Any, Mapping, Tuple

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPO = re.compile(r"^[^/\s]+/[^/\s]+$")
_BRANCH = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.?(?:/|$))(?!.*\.lock(?:/|$))[A-Za-z0-9._/-]+$")
PROVISIONING_STATES = frozenset({"READY", "FAILED"})
SCHEMA_VERSION = "1.0.0"


class ExecutorProvisioningContractError(ValueError):
    """Raised when executor provisioning data is malformed, unsafe, or ambiguous."""


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: Any, name: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise ExecutorProvisioningContractError(f"{name} is invalid")
    return value


def _sha40(value: Any, name: str) -> str:
    value = _text(value, name, limit=40)
    if not _SHA40.fullmatch(value):
        raise ExecutorProvisioningContractError(f"{name} must be a full lowercase git SHA")
    return value


def _sha256(value: Any, name: str) -> str:
    value = _text(value, name, limit=64)
    if not _SHA256.fullmatch(value):
        raise ExecutorProvisioningContractError(f"{name} must be sha256 hex")
    return value


def _utc(value: Any, name: str) -> datetime:
    value = _text(value, name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExecutorProvisioningContractError(f"{name} is invalid") from exc
    if parsed.tzinfo is None:
        raise ExecutorProvisioningContractError(f"{name} must be timezone-aware")
    return parsed


def _branch(value: Any) -> str:
    value = _text(value, "branch", limit=255)
    if value.startswith("refs/") or value.endswith("/") or value.endswith(".") or "//" in value:
        raise ExecutorProvisioningContractError("branch is invalid")
    if any(ch in value for ch in " ~^:?*[\\"):
        raise ExecutorProvisioningContractError("branch contains unsafe git ref characters")
    if not _BRANCH.fullmatch(value):
        raise ExecutorProvisioningContractError("branch is invalid")
    return value


def _scope(value: Any, name: str) -> Tuple[str, ...]:
    if type(value) is not tuple or not value:
        raise ExecutorProvisioningContractError(f"{name} must be a non-empty tuple")
    if len(set(value)) != len(value):
        raise ExecutorProvisioningContractError(f"{name} entries must be unique")
    for raw in value:
        raw = _text(raw, name, limit=1024)
        if "\\" in raw:
            raise ExecutorProvisioningContractError(f"{name} must use POSIX repository paths")
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
            raise ExecutorProvisioningContractError(f"{name} contains unsafe path: {raw!r}")
    return value


def _string_tuple(value: Any, name: str, *, allow_empty: bool = False) -> Tuple[str, ...]:
    if type(value) is not tuple or (not allow_empty and not value):
        raise ExecutorProvisioningContractError(f"{name} must be a tuple")
    for item in value:
        _text(item, name)
    if len(set(value)) != len(value):
        raise ExecutorProvisioningContractError(f"{name} entries must be unique")
    return value


@dataclass(frozen=True)
class CredentialHandle:
    """Opaque reference to externally brokered credentials; never credential material."""

    handle_id: str
    broker_id: str
    purpose: str

    def validate(self) -> "CredentialHandle":
        _text(self.handle_id, "credential handle_id", limit=512)
        _text(self.broker_id, "credential broker_id", limit=512)
        _text(self.purpose, "credential purpose", limit=512)
        return self

    def canonical_dict(self) -> dict[str, str]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class ProviderTrustBinding:
    """Composition-root pin for the externally configured provisioning provider."""

    provider_id: str
    provider_instance_id: str
    implementation_digest: str
    trust_anchor_id: str
    trust_anchor_digest: str

    def validate(self) -> "ProviderTrustBinding":
        for name in ("provider_id", "provider_instance_id", "trust_anchor_id"):
            _text(getattr(self, name), name)
        _sha256(self.implementation_digest, "implementation_digest")
        _sha256(self.trust_anchor_digest, "trust_anchor_digest")
        return self

    def binding(self) -> tuple[str, str, str, str, str]:
        self.validate()
        return (
            self.provider_id,
            self.provider_instance_id,
            self.implementation_digest,
            self.trust_anchor_id,
            self.trust_anchor_digest,
        )


@dataclass(frozen=True)
class ExecutorProvisioningRequest:
    """Exact desired executor context. This object carries no authority grant."""

    schema_version: str
    request_id: str
    idempotency_key: str
    drone_id: str
    executor_id: str
    mission_id: str
    parent_mission_id: str
    repository: str
    baseline_sha: str
    baseline_tree_sha: str
    branch: str
    read_scope: Tuple[str, ...]
    write_scope: Tuple[str, ...]
    runtime_class: str
    image_digest: str
    sandbox_profile_digest: str
    resource_profile_digest: str
    credential_handles: Tuple[CredentialHandle, ...]
    requested_at: str

    def validate(self) -> "ExecutorProvisioningRequest":
        if self.schema_version != SCHEMA_VERSION:
            raise ExecutorProvisioningContractError("unsupported provisioning request schema_version")
        for name in (
            "request_id", "idempotency_key", "drone_id", "executor_id", "mission_id",
            "parent_mission_id", "runtime_class",
        ):
            _text(getattr(self, name), name)
        if not _REPO.fullmatch(self.repository):
            raise ExecutorProvisioningContractError("repository must use owner/name form")
        _sha40(self.baseline_sha, "baseline_sha")
        _sha40(self.baseline_tree_sha, "baseline_tree_sha")
        _branch(self.branch)
        _scope(self.read_scope, "read_scope")
        _scope(self.write_scope, "write_scope")
        for name in ("image_digest", "sandbox_profile_digest", "resource_profile_digest"):
            _sha256(getattr(self, name), name)
        if type(self.credential_handles) is not tuple:
            raise ExecutorProvisioningContractError("credential_handles must be a tuple")
        handle_ids: list[str] = []
        for handle in self.credential_handles:
            if type(handle) is not CredentialHandle:
                raise ExecutorProvisioningContractError("credential handle type is invalid")
            handle.validate()
            handle_ids.append(handle.handle_id)
        if len(handle_ids) != len(set(handle_ids)):
            raise ExecutorProvisioningContractError("credential handle ids must be unique")
        _utc(self.requested_at, "requested_at")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["read_scope"] = list(self.read_scope)
        value["write_scope"] = list(self.write_scope)
        value["credential_handles"] = [handle.canonical_dict() for handle in self.credential_handles]
        return value

    def digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict())).hexdigest()

    def credential_handle_ids(self) -> Tuple[str, ...]:
        self.validate()
        return tuple(handle.handle_id for handle in self.credential_handles)


@dataclass(frozen=True)
class ProvisioningMaterialization:
    """Provider output. It is untrusted until exact request/provider binding is checked."""

    request_digest: str
    provider_id: str
    provider_instance_id: str
    runtime_instance_id: str
    sandbox_id: str
    workspace_id: str
    runtime_class: str
    image_digest: str
    sandbox_profile_digest: str
    resource_profile_digest: str
    repository: str
    baseline_sha: str
    baseline_tree_sha: str
    branch: str
    read_scope: Tuple[str, ...]
    write_scope: Tuple[str, ...]
    credential_handle_ids: Tuple[str, ...]
    state: str
    runtime_attestation_digest: str | None
    evidence_ref: str
    failure_code: str | None
    observed_at: str

    def validate(self) -> "ProvisioningMaterialization":
        _sha256(self.request_digest, "request_digest")
        for name in (
            "provider_id", "provider_instance_id", "runtime_instance_id", "sandbox_id",
            "workspace_id", "runtime_class", "evidence_ref",
        ):
            _text(getattr(self, name), name)
        for name in ("image_digest", "sandbox_profile_digest", "resource_profile_digest"):
            _sha256(getattr(self, name), name)
        if not _REPO.fullmatch(self.repository):
            raise ExecutorProvisioningContractError("repository must use owner/name form")
        _sha40(self.baseline_sha, "baseline_sha")
        _sha40(self.baseline_tree_sha, "baseline_tree_sha")
        _branch(self.branch)
        _scope(self.read_scope, "read_scope")
        _scope(self.write_scope, "write_scope")
        _string_tuple(self.credential_handle_ids, "credential_handle_ids", allow_empty=True)
        if self.state not in PROVISIONING_STATES:
            raise ExecutorProvisioningContractError("provisioning state is invalid")
        if self.state == "READY":
            if self.runtime_attestation_digest is None:
                raise ExecutorProvisioningContractError("READY materialization requires runtime attestation")
            _sha256(self.runtime_attestation_digest, "runtime_attestation_digest")
            if self.failure_code is not None:
                raise ExecutorProvisioningContractError("READY materialization cannot contain failure_code")
        else:
            if self.runtime_attestation_digest is not None:
                _sha256(self.runtime_attestation_digest, "runtime_attestation_digest")
            if self.failure_code is None:
                raise ExecutorProvisioningContractError("FAILED materialization requires failure_code")
            _text(self.failure_code, "failure_code")
        _utc(self.observed_at, "observed_at")
        return self


@dataclass(frozen=True)
class ProvisionedExecutor:
    """Trusted provisioning receipt. Evidence only; explicitly not runtime authority."""

    schema_version: str
    receipt_id: str
    request_id: str
    request_digest: str
    idempotency_key: str
    drone_id: str
    executor_id: str
    runtime_instance_id: str
    sandbox_id: str
    workspace_id: str
    mission_id: str
    parent_mission_id: str
    repository: str
    baseline_sha: str
    baseline_tree_sha: str
    branch: str
    read_scope: Tuple[str, ...]
    write_scope: Tuple[str, ...]
    runtime_class: str
    image_digest: str
    sandbox_profile_digest: str
    resource_profile_digest: str
    credential_handle_ids: Tuple[str, ...]
    provider_id: str
    provider_instance_id: str
    provider_implementation_digest: str
    provider_trust_anchor_id: str
    provider_trust_anchor_digest: str
    runtime_attestation_digest: str
    provider_evidence_ref: str
    provisioned_at: str

    def validate(self) -> "ProvisionedExecutor":
        if self.schema_version != SCHEMA_VERSION:
            raise ExecutorProvisioningContractError("unsupported provisioned executor schema_version")
        for name in (
            "receipt_id", "request_id", "idempotency_key", "drone_id", "executor_id",
            "runtime_instance_id", "sandbox_id", "workspace_id", "mission_id",
            "parent_mission_id", "runtime_class", "provider_id", "provider_instance_id",
            "provider_trust_anchor_id", "provider_evidence_ref",
        ):
            _text(getattr(self, name), name)
        if not _REPO.fullmatch(self.repository):
            raise ExecutorProvisioningContractError("repository must use owner/name form")
        _sha40(self.baseline_sha, "baseline_sha")
        _sha40(self.baseline_tree_sha, "baseline_tree_sha")
        _branch(self.branch)
        _scope(self.read_scope, "read_scope")
        _scope(self.write_scope, "write_scope")
        _string_tuple(self.credential_handle_ids, "credential_handle_ids", allow_empty=True)
        for name in (
            "request_digest", "image_digest", "sandbox_profile_digest",
            "resource_profile_digest", "provider_implementation_digest",
            "provider_trust_anchor_digest", "runtime_attestation_digest",
        ):
            _sha256(getattr(self, name), name)
        _utc(self.provisioned_at, "provisioned_at")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["read_scope"] = list(self.read_scope)
        value["write_scope"] = list(self.write_scope)
        value["credential_handle_ids"] = list(self.credential_handle_ids)
        return value

    def digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict())).hexdigest()

    def validate_for(
        self,
        request: ExecutorProvisioningRequest,
        trust: ProviderTrustBinding,
    ) -> "ProvisionedExecutor":
        self.validate()
        if type(request) is not ExecutorProvisioningRequest:
            raise ExecutorProvisioningContractError("exact provisioning request type is required")
        if type(trust) is not ProviderTrustBinding:
            raise ExecutorProvisioningContractError("exact provider trust binding type is required")
        request.validate()
        trust.validate()
        if self.request_digest != request.digest():
            raise ExecutorProvisioningContractError("receipt request digest mismatch")
        expected = (
            self.request_id,
            self.idempotency_key,
            self.drone_id,
            self.executor_id,
            self.mission_id,
            self.parent_mission_id,
            self.repository,
            self.baseline_sha,
            self.baseline_tree_sha,
            self.branch,
            self.read_scope,
            self.write_scope,
            self.runtime_class,
            self.image_digest,
            self.sandbox_profile_digest,
            self.resource_profile_digest,
            self.credential_handle_ids,
        )
        actual = (
            request.request_id,
            request.idempotency_key,
            request.drone_id,
            request.executor_id,
            request.mission_id,
            request.parent_mission_id,
            request.repository,
            request.baseline_sha,
            request.baseline_tree_sha,
            request.branch,
            request.read_scope,
            request.write_scope,
            request.runtime_class,
            request.image_digest,
            request.sandbox_profile_digest,
            request.resource_profile_digest,
            request.credential_handle_ids(),
        )
        if expected != actual:
            raise ExecutorProvisioningContractError("receipt does not bind exact provisioning request")
        receipt_trust = (
            self.provider_id,
            self.provider_instance_id,
            self.provider_implementation_digest,
            self.provider_trust_anchor_id,
            self.provider_trust_anchor_digest,
        )
        if receipt_trust != trust.binding():
            raise ExecutorProvisioningContractError("receipt provider trust binding mismatch")
        return self

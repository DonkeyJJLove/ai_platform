"""Fail-closed executor provisioning orchestration for F005-D.

The provisioner binds an externally configured runtime provider to an immutable request,
returns evidence for one materialized executor, and keeps credential material and authority
outside the provisioning boundary. The built-in ledger is process-local by design; durable
fleet coordination is a separate slice and can wrap/replace this orchestration later.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from threading import RLock
from typing import Protocol

from cyber_lion.contracts.executor_provisioning import (
    ExecutorProvisioningContractError,
    ExecutorProvisioningRequest,
    ProviderTrustBinding,
    ProvisionedExecutor,
    ProvisioningMaterialization,
    SCHEMA_VERSION,
    canonical_json,
)


class ExecutorProvisioningError(ExecutorProvisioningContractError):
    """Raised when executor provisioning cannot be admitted safely."""


class ExecutorRuntimeProvider(Protocol):
    """External side-effect boundary. Provider receives handles, never credential material."""

    provider_id: str
    provider_instance_id: str
    implementation_digest: str

    def provision(self, request: ExecutorProvisioningRequest) -> ProvisioningMaterialization:
        ...


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ExecutorProvisioningError("provisioning timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ExecutorProvisioningError("provisioning timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


class ExecutorProvisioningLedger:
    """Process-local idempotency and uniqueness ledger for a single provisioner runtime."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._receipts: dict[str, ProvisionedExecutor] = {}
        self._pending: set[str] = set()
        self._request_ids: dict[str, str] = {}
        self._idempotency_keys: dict[str, str] = {}
        self._drone_ids: dict[str, str] = {}
        self._executor_ids: dict[str, str] = {}
        self._runtime_ids: dict[str, str] = {}
        self._sandbox_ids: dict[str, str] = {}
        self._workspace_ids: dict[str, str] = {}

    @staticmethod
    def _check_claim(mapping: dict[str, str], key: str, digest: str, label: str) -> None:
        existing = mapping.get(key)
        if existing is not None and existing != digest:
            raise ExecutorProvisioningError(f"{label} is already bound to another provisioning request")

    @classmethod
    def _claim(cls, mapping: dict[str, str], key: str, digest: str, label: str) -> None:
        cls._check_claim(mapping, key, digest, label)
        mapping[key] = digest

    def begin(self, request: ExecutorProvisioningRequest) -> ProvisionedExecutor | None:
        if type(request) is not ExecutorProvisioningRequest:
            raise ExecutorProvisioningError("exact ExecutorProvisioningRequest is required")
        request.validate()
        digest = request.digest()
        with self._lock:
            existing = self._receipts.get(digest)
            if existing is not None:
                return existing
            if digest in self._pending:
                raise ExecutorProvisioningError("provisioning request is already in progress")
            self._claim(self._request_ids, request.request_id, digest, "request_id")
            self._claim(self._idempotency_keys, request.idempotency_key, digest, "idempotency_key")
            self._claim(self._drone_ids, request.drone_id, digest, "drone_id")
            self._claim(self._executor_ids, request.executor_id, digest, "executor_id")
            self._pending.add(digest)
            return None

    def commit(
        self,
        request: ExecutorProvisioningRequest,
        receipt: ProvisionedExecutor,
        trust: ProviderTrustBinding,
    ) -> ProvisionedExecutor:
        if type(receipt) is not ProvisionedExecutor:
            raise ExecutorProvisioningError("exact ProvisionedExecutor receipt is required")
        receipt.validate_for(request, trust)
        digest = request.digest()
        with self._lock:
            existing = self._receipts.get(digest)
            if existing is not None:
                if existing.digest() != receipt.digest():
                    raise ExecutorProvisioningError("idempotent provisioning receipt changed")
                return existing
            if digest not in self._pending:
                raise ExecutorProvisioningError("provisioning request was not reserved")
            runtime_claims = (
                (self._runtime_ids, receipt.runtime_instance_id, "runtime_instance_id"),
                (self._sandbox_ids, receipt.sandbox_id, "sandbox_id"),
                (self._workspace_ids, receipt.workspace_id, "workspace_id"),
            )
            for mapping, key, label in runtime_claims:
                self._check_claim(mapping, key, digest, label)
            for mapping, key, _ in runtime_claims:
                mapping[key] = digest
            self._receipts[digest] = receipt
            self._pending.remove(digest)
            return receipt

    def abort(self, request: ExecutorProvisioningRequest) -> None:
        if type(request) is not ExecutorProvisioningRequest:
            return
        try:
            digest = request.digest()
        except Exception:
            return
        with self._lock:
            if digest in self._receipts:
                return
            self._pending.discard(digest)
            for mapping, key in (
                (self._request_ids, request.request_id),
                (self._idempotency_keys, request.idempotency_key),
                (self._drone_ids, request.drone_id),
                (self._executor_ids, request.executor_id),
            ):
                if mapping.get(key) == digest:
                    mapping.pop(key, None)

    def lookup(self, request: ExecutorProvisioningRequest) -> ProvisionedExecutor | None:
        if type(request) is not ExecutorProvisioningRequest:
            raise ExecutorProvisioningError("exact ExecutorProvisioningRequest is required")
        request.validate()
        with self._lock:
            return self._receipts.get(request.digest())


class ExecutorProvisioner:
    """Materialize one inert executor and bind provider evidence to the exact request."""

    def __init__(
        self,
        *,
        provider: ExecutorRuntimeProvider,
        trust: ProviderTrustBinding,
        ledger: ExecutorProvisioningLedger | None = None,
    ) -> None:
        if type(trust) is not ProviderTrustBinding:
            raise ExecutorProvisioningError("exact ProviderTrustBinding is required")
        trust.validate()
        for attr, expected in (
            ("provider_id", trust.provider_id),
            ("provider_instance_id", trust.provider_instance_id),
            ("implementation_digest", trust.implementation_digest),
        ):
            if getattr(provider, attr, None) != expected:
                raise ExecutorProvisioningError(f"provisioning provider {attr} does not match trust binding")
        if not callable(getattr(provider, "provision", None)):
            raise ExecutorProvisioningError("provisioning provider lacks provision operation")
        if ledger is not None and type(ledger) is not ExecutorProvisioningLedger:
            raise ExecutorProvisioningError("ledger must be exact ExecutorProvisioningLedger")
        self._provider = provider
        self._trust = trust
        self._ledger = ledger or ExecutorProvisioningLedger()

    @property
    def trust_binding(self) -> ProviderTrustBinding:
        return self._trust

    def _validate_materialization(
        self,
        request: ExecutorProvisioningRequest,
        materialization: ProvisioningMaterialization,
    ) -> ProvisioningMaterialization:
        if type(materialization) is not ProvisioningMaterialization:
            raise ExecutorProvisioningError("provider returned invalid materialization type")
        materialization.validate()
        if materialization.state != "READY":
            raise ExecutorProvisioningError("provider did not produce a READY executor")
        if materialization.request_digest != request.digest():
            raise ExecutorProvisioningError("provider materialization request digest mismatch")
        if (
            materialization.provider_id != self._trust.provider_id
            or materialization.provider_instance_id != self._trust.provider_instance_id
        ):
            raise ExecutorProvisioningError("provider materialization identity mismatch")
        expected = (
            request.runtime_class,
            request.image_digest,
            request.sandbox_profile_digest,
            request.resource_profile_digest,
            request.repository,
            request.baseline_sha,
            request.baseline_tree_sha,
            request.branch,
            request.read_scope,
            request.write_scope,
            request.credential_handle_ids(),
        )
        actual = (
            materialization.runtime_class,
            materialization.image_digest,
            materialization.sandbox_profile_digest,
            materialization.resource_profile_digest,
            materialization.repository,
            materialization.baseline_sha,
            materialization.baseline_tree_sha,
            materialization.branch,
            materialization.read_scope,
            materialization.write_scope,
            materialization.credential_handle_ids,
        )
        if actual != expected:
            raise ExecutorProvisioningError("provider widened or changed requested executor context")
        if _utc(materialization.observed_at) < _utc(request.requested_at):
            raise ExecutorProvisioningError("provider evidence predates provisioning request")
        return materialization

    def _receipt(
        self,
        request: ExecutorProvisioningRequest,
        materialization: ProvisioningMaterialization,
    ) -> ProvisionedExecutor:
        receipt_basis = {
            "request_digest": request.digest(),
            "provider_binding": self._trust.binding(),
            "runtime_instance_id": materialization.runtime_instance_id,
            "sandbox_id": materialization.sandbox_id,
            "workspace_id": materialization.workspace_id,
            "runtime_attestation_digest": materialization.runtime_attestation_digest,
            "provider_evidence_ref": materialization.evidence_ref,
            "provisioned_at": materialization.observed_at,
        }
        receipt_id = "executor-provisioning:" + sha256(canonical_json(receipt_basis)).hexdigest()
        receipt = ProvisionedExecutor(
            schema_version=SCHEMA_VERSION,
            receipt_id=receipt_id,
            request_id=request.request_id,
            request_digest=request.digest(),
            idempotency_key=request.idempotency_key,
            drone_id=request.drone_id,
            executor_id=request.executor_id,
            runtime_instance_id=materialization.runtime_instance_id,
            sandbox_id=materialization.sandbox_id,
            workspace_id=materialization.workspace_id,
            mission_id=request.mission_id,
            parent_mission_id=request.parent_mission_id,
            repository=request.repository,
            baseline_sha=request.baseline_sha,
            baseline_tree_sha=request.baseline_tree_sha,
            branch=request.branch,
            read_scope=request.read_scope,
            write_scope=request.write_scope,
            runtime_class=request.runtime_class,
            image_digest=request.image_digest,
            sandbox_profile_digest=request.sandbox_profile_digest,
            resource_profile_digest=request.resource_profile_digest,
            credential_handle_ids=request.credential_handle_ids(),
            provider_id=self._trust.provider_id,
            provider_instance_id=self._trust.provider_instance_id,
            provider_implementation_digest=self._trust.implementation_digest,
            provider_trust_anchor_id=self._trust.trust_anchor_id,
            provider_trust_anchor_digest=self._trust.trust_anchor_digest,
            runtime_attestation_digest=materialization.runtime_attestation_digest or "",
            provider_evidence_ref=materialization.evidence_ref,
            provisioned_at=materialization.observed_at,
        )
        return receipt.validate_for(request, self._trust)

    def provision(self, request: ExecutorProvisioningRequest) -> ProvisionedExecutor:
        if type(request) is not ExecutorProvisioningRequest:
            raise ExecutorProvisioningError("exact ExecutorProvisioningRequest is required")
        request.validate()
        existing = self._ledger.begin(request)
        if existing is not None:
            try:
                return existing.validate_for(request, self._trust)
            except ExecutorProvisioningContractError as exc:
                raise ExecutorProvisioningError("stored provisioning receipt is invalid") from exc

        try:
            materialization = self._provider.provision(request)
            materialization = self._validate_materialization(request, materialization)
            receipt = self._receipt(request, materialization)
            return self._ledger.commit(request, receipt, self._trust)
        except ExecutorProvisioningError:
            self._ledger.abort(request)
            raise
        except ExecutorProvisioningContractError as exc:
            self._ledger.abort(request)
            raise ExecutorProvisioningError("provider evidence failed contract validation") from exc
        except Exception as exc:
            self._ledger.abort(request)
            raise ExecutorProvisioningError("executor provider failed closed") from exc

    def lookup(self, request: ExecutorProvisioningRequest) -> ProvisionedExecutor | None:
        receipt = self._ledger.lookup(request)
        if receipt is None:
            return None
        try:
            return receipt.validate_for(request, self._trust)
        except ExecutorProvisioningContractError as exc:
            raise ExecutorProvisioningError("stored provisioning receipt is invalid") from exc

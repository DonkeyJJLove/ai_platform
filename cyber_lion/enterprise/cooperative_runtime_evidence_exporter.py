"""Independent exporter from canonical cooperative runtime owners to R6.14 evidence DB.

The exporter is observation/copy only. It does not issue RuntimeAdmission, authority,
provisioning, dispatch, context pins or transfer bindings. Every object must already
exist in an independent source and must agree with the exact CooperativeRuntimeContext.

A snapshot is observed completely before the first provider-DB write. The provider DB
is therefore never used as a source for its own export decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Callable, Mapping

from cyber_lion.contracts.executor_sandbox import FleetDispatchBinding, ProvisioningBinding
from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding
from cyber_lion.contracts.runtime_enforcement import RuntimeAdmission, RuntimeIdentityBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.cooperative_context_resolver import CooperativeContextPin
from cyber_lion.enterprise.cooperative_runtime_composition import CooperativeRuntimeContext
from cyber_lion.enterprise.cooperative_runtime_evidence_sources import (
    SQLiteCooperativeRuntimeEvidencePublisher,
)
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority, LiveAuthorityAdmission
from cyber_lion.mission_control.artifact_transfer import _binding as canonical_transfer_binding

EXPORT_SCHEMA = "lion.cooperative-runtime-evidence-export/v1"
PROVENANCE_DOMAIN = b"LION/COOPERATIVE-RUNTIME-EVIDENCE-EXPORT/1\0"
MAX_TTL_SECONDS = 30


class CooperativeRuntimeEvidenceExportError(RuntimeError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CooperativeRuntimeEvidenceExportError(reason)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _zoned(value: datetime, label: str) -> datetime:
    _require(isinstance(value, datetime) and value.tzinfo is not None, label)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class CooperativeRuntimeEvidenceExportReceipt:
    assignment_id: str
    mission_id: str
    worker_id: str
    observed_at: str
    expires_at: str
    provenance_digest: str
    admission_digest: str
    context_pin_digest: str
    dispatch_digest: str
    provisioning_digest: str
    runtime_identity_digest: str
    live_authority_digest: str
    transfer_binding_digest: str
    authority_effect: str = "NONE"
    execution_performed: bool = False
    schema: str = EXPORT_SCHEMA

    def validate(self) -> "CooperativeRuntimeEvidenceExportReceipt":
        for name in ("assignment_id", "mission_id", "worker_id", "observed_at", "expires_at"):
            value = getattr(self, name)
            _require(type(value) is str and bool(value), "export receipt " + name)
        for name in (
            "provenance_digest", "admission_digest", "context_pin_digest",
            "dispatch_digest", "provisioning_digest", "runtime_identity_digest",
            "live_authority_digest", "transfer_binding_digest",
        ):
            value = getattr(self, name)
            _require(
                type(value) is str and len(value) == 64
                and all(ch in "0123456789abcdef" for ch in value),
                "export receipt " + name,
            )
        _require(self.authority_effect == "NONE" and self.execution_performed is False,
                 "export receipt authority/effect")
        _require(self.schema == EXPORT_SCHEMA, "export receipt schema")
        _require(datetime.fromisoformat(self.observed_at).tzinfo is not None, "export observed_at")
        _require(datetime.fromisoformat(self.expires_at).tzinfo is not None, "export expires_at")
        return self


class CooperativeRuntimeEvidenceExporter:
    """Observe one exact write assignment and copy bounded evidence into provider DB."""

    def __init__(
        self,
        *,
        publisher: SQLiteCooperativeRuntimeEvidencePublisher,
        context_source: Callable[[str], CooperativeRuntimeContext],
        admission_source,
        admission_trust: RuntimeAdmissionSourceTrustBinding,
        authority_admission: LiveAuthorityAdmission,
        currentness_source,
        currentness_trust: CurrentnessSourceTrustBinding,
        dispatch_source,
        runtime_identity_source: Callable[[str], RuntimeIdentityBinding],
        provisioning_binding_source: Callable[[str], ProvisioningBinding],
        context_pin_source: Callable[[str], CooperativeContextPin],
        transfer_binding_source: Callable[[str, str], Mapping[str, Any]],
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        max_ttl_seconds: int = MAX_TTL_SECONDS,
    ):
        _require(type(publisher) is SQLiteCooperativeRuntimeEvidencePublisher, "exact evidence publisher required")
        _require(callable(context_source), "context source")
        _require(type(admission_trust) is RuntimeAdmissionSourceTrustBinding, "admission trust")
        _require(type(currentness_trust) is CurrentnessSourceTrustBinding, "currentness trust")
        admission_trust.validate(); currentness_trust.validate()
        _require(isinstance(authority_admission, LiveAuthorityAdmission), "canonical LiveAuthorityAdmission required")
        for source, methods, label in (
            (admission_source, ("resolve", "is_current"), "admission source"),
            (currentness_source, ("resolve_authority", "current_policy_binding", "current_observability_state"), "currentness source"),
            (dispatch_source, ("current_dispatch",), "dispatch source"),
        ):
            _require(all(callable(getattr(source, name, None)) for name in methods), label)
        for callback, label in (
            (runtime_identity_source, "runtime identity source"),
            (provisioning_binding_source, "provisioning source"),
            (context_pin_source, "context pin source"),
            (transfer_binding_source, "transfer binding source"),
            (now_fn, "trusted clock"),
        ):
            _require(callable(callback), label)
        _require(type(max_ttl_seconds) is int and 1 <= max_ttl_seconds <= MAX_TTL_SECONDS, "export TTL bound")
        self.publisher = publisher
        self.context_source = context_source
        self.admission_source = admission_source
        self.admission_trust = admission_trust
        self.authority_admission = authority_admission
        self.currentness_source = currentness_source
        self.currentness_trust = currentness_trust
        self.dispatch_source = dispatch_source
        self.runtime_identity_source = runtime_identity_source
        self.provisioning_binding_source = provisioning_binding_source
        self.context_pin_source = context_pin_source
        self.transfer_binding_source = transfer_binding_source
        self.now_fn = now_fn
        self.max_ttl_seconds = max_ttl_seconds
        self._check_source_bindings()

    @staticmethod
    def _binding_tuple(source) -> tuple[Any, ...]:
        return tuple(getattr(source, name, None) for name in (
            "source_id", "source_instance_id", "implementation_digest",
            "trust_anchor_id", "trust_anchor_digest",
        ))

    def _check_source_bindings(self) -> None:
        _require(self._binding_tuple(self.admission_source) == self.admission_trust.binding(),
                 "admission source substitution")
        _require(self._binding_tuple(self.currentness_source) == self.currentness_trust.binding(),
                 "currentness source substitution")

    def _observe(self, assignment_id: str, *, ttl_seconds: int):
        _require(type(assignment_id) is str and bool(assignment_id) and "\x00" not in assignment_id,
                 "assignment identity")
        _require(type(ttl_seconds) is int and 1 <= ttl_seconds <= self.max_ttl_seconds,
                 "export TTL bound")
        self._check_source_bindings()
        now = _zoned(self.now_fn(), "trusted export clock")
        expires = now + timedelta(seconds=ttl_seconds)

        context = self.context_source(assignment_id)
        _require(type(context) is CooperativeRuntimeContext, "exact CooperativeRuntimeContext required")
        context.validate()
        execution = context.execution
        _require(execution.assignment_id == assignment_id, "context assignment substitution")

        admission = self.admission_source.resolve(execution.admission.admission_digest)
        _require(type(admission) is RuntimeAdmission and admission.validate() == execution.admission,
                 "admission substitution")
        _require(self.admission_source.is_current(admission.admission_digest) is True,
                 "runtime admission stale")

        dispatch = self.dispatch_source.current_dispatch(execution.request.mission_id)
        _require(type(dispatch) is FleetDispatchBinding and dispatch.validate() == context.dispatch,
                 "dispatch substitution")

        identity = self.runtime_identity_source(execution.identity.runtime_instance_id)
        _require(type(identity) is RuntimeIdentityBinding and identity.validate() == execution.identity,
                 "runtime identity substitution")

        provisioning = self.provisioning_binding_source(assignment_id)
        _require(type(provisioning) is ProvisioningBinding and provisioning.validate() == context.provisioning,
                 "provisioning substitution")

        authority = self.currentness_source.resolve_authority(admission.admission_digest)
        _require(type(authority) is LiveAdmittedAuthority, "live authority type")
        authority.validate()
        _require(
            authority.digest() == admission.live_authority_digest
            and authority.lineage_digest == admission.authority_lineage_digest,
            "live authority substitution",
        )
        revalidated = self.authority_admission.revalidate(authority, now=now)
        _require(revalidated.digest() == admission.live_authority_digest, "live authority changed")

        policy = self.currentness_source.current_policy_binding(admission.policy_binding)
        _require(policy == admission.policy_binding, "policy currentness changed")
        observability = self.currentness_source.current_observability_state(
            admission.runtime_identity_digest, admission.requested_effect_digest,
        )
        _require(observability == admission.observability_state, "observability currentness changed")

        pin = self.context_pin_source(assignment_id)
        _require(type(pin) is CooperativeContextPin and pin.validate().assignment_id == assignment_id,
                 "context pin substitution")

        transfer = canonical_transfer_binding(dict(self.transfer_binding_source(assignment_id, "CONTEXT")))
        _require(
            transfer["assignment_id"] == assignment_id
            and transfer["mission_id"] == execution.request.mission_id
            and transfer["generation"] == execution.request.generation
            and transfer["lease_generation"] == execution.request.generation,
            "transfer binding substitution",
        )

        basis = {
            "schema": EXPORT_SCHEMA,
            "assignment_id": assignment_id,
            "mission_id": execution.request.mission_id,
            "worker_id": execution.worker_id,
            "observed_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "admission_source": self.admission_trust.binding(),
            "currentness_source": self.currentness_trust.binding(),
            "admission_digest": admission.admission_digest,
            "context_pin_digest": pin.sha256,
            "dispatch_digest": dispatch.digest(),
            "provisioning_digest": provisioning.digest(),
            "runtime_identity_digest": identity.digest(),
            "live_authority_digest": authority.digest(),
            "transfer_binding_digest": sha256(_canonical(transfer)).hexdigest(),
        }
        provenance = sha256(PROVENANCE_DOMAIN + _canonical(basis)).hexdigest()
        return (
            now, expires, context, admission, dispatch, identity, provisioning,
            authority, policy, observability, pin, transfer, provenance,
        )

    def export_write_assignment(
        self, assignment_id: str, *, ttl_seconds: int = 10,
    ) -> CooperativeRuntimeEvidenceExportReceipt:
        """Copy one fully observed snapshot. No provider-DB value participates in observation."""
        (
            now, expires, context, admission, dispatch, identity, provisioning,
            authority, policy, observability, pin, transfer, provenance,
        ) = self._observe(assignment_id, ttl_seconds=ttl_seconds)

        # Writes begin only after every independent observation succeeded.
        self.publisher.publish_runtime_admission(
            admission, provenance_digest=provenance, observed_at=now, expires_at=expires,
        )
        self.publisher.publish_context_pin(
            pin, provenance_digest=provenance, observed_at=now, expires_at=expires,
        )
        self.publisher.publish_dispatch(
            dispatch, provenance_digest=provenance, observed_at=now, expires_at=expires,
        )
        self.publisher.publish_provisioning(
            assignment_id, provisioning, provenance_digest=provenance,
            observed_at=now, expires_at=expires,
        )
        self.publisher.publish_runtime_identity(
            identity, provenance_digest=provenance, observed_at=now, expires_at=expires,
        )
        self.publisher.publish_currentness(
            admission.admission_digest, authority,
            policy_binding=policy,
            runtime_identity_digest=admission.runtime_identity_digest,
            requested_effect_digest=admission.requested_effect_digest,
            observability_state=observability,
            provenance_digest=provenance,
            observed_at=now,
            expires_at=expires,
        )
        transfer_digest = self.publisher.publish_transfer_binding(
            assignment_id, "CONTEXT", transfer,
            provenance_digest=provenance, observed_at=now, expires_at=expires,
        )
        receipt = CooperativeRuntimeEvidenceExportReceipt(
            assignment_id=assignment_id,
            mission_id=context.execution.request.mission_id,
            worker_id=context.execution.worker_id,
            observed_at=now.isoformat(),
            expires_at=expires.isoformat(),
            provenance_digest=provenance,
            admission_digest=admission.admission_digest,
            context_pin_digest=pin.sha256,
            dispatch_digest=dispatch.digest(),
            provisioning_digest=provisioning.digest(),
            runtime_identity_digest=identity.digest(),
            live_authority_digest=authority.digest(),
            transfer_binding_digest=transfer_digest,
        )
        return receipt.validate()

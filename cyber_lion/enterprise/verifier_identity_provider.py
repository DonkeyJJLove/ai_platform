"""Real verifier identity adapters over external raw evidence.

The adapters in this module never mint trusted identities.  They accept raw evidence
only from composition-root-owned providers and route it through the existing
cryptographic workload/runtime verification boundaries.  They expose no repository
mutation, authority, lease, merge, release, deploy, or credential capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from cyber_lion.contracts.runtime_attestation import RuntimeAttestation, RuntimeAttestationContext
from cyber_lion.contracts.verifier_execution_attestation import (
    ExactVerificationTarget,
    FixedSourcePin,
    TrustedParticipationHistory,
)
from cyber_lion.contracts.workload_identity import (
    VerifiedWorkloadIdentity,
    WorkloadIdentityContext,
    WorkloadIdentityProof,
    verify_workload_identity,
)
from cyber_lion.enterprise.runtime_attestation import (
    RuntimeAttestationVerifier,
    VerifiedRuntimeAttestation,
)


class VerifierIdentityProviderError(ValueError):
    """Raised whenever real verifier identity cannot be proven exactly."""


Clock = Callable[[], datetime]
SignatureVerifier = Callable[[bytes, str, str, str], bool]


@dataclass(frozen=True)
class RawRuntimeEvidence:
    """Untrusted runtime claim plus the exact implementation bytes observed."""

    attestation: RuntimeAttestation
    artifact_bytes: bytes

    def validate(self) -> "RawRuntimeEvidence":
        if type(self.attestation) is not RuntimeAttestation:
            raise VerifierIdentityProviderError("raw runtime attestation is missing")
        self.attestation.validate()
        if not isinstance(self.artifact_bytes, bytes) or not self.artifact_bytes:
            raise VerifierIdentityProviderError("raw runtime artifact bytes are required")
        return self


class RawWorkloadIdentityProvider(Protocol):
    def resolve(self, target: ExactVerificationTarget) -> WorkloadIdentityProof: ...


class RawRuntimeEvidenceProvider(Protocol):
    def resolve(self, target: ExactVerificationTarget) -> RawRuntimeEvidence: ...


class RawParticipationHistoryProvider(Protocol):
    def resolve(self, target: ExactVerificationTarget) -> TrustedParticipationHistory: ...


def _now(clock: Clock) -> datetime:
    try:
        value = clock()
    except Exception as exc:
        raise VerifierIdentityProviderError("trusted clock failed closed") from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise VerifierIdentityProviderError("trusted clock must be timezone-aware")
    return value.astimezone(timezone.utc)


def _require_provider(provider: object) -> None:
    if not callable(getattr(provider, "resolve", None)):
        raise VerifierIdentityProviderError("external raw evidence provider is invalid")


class RealVerifierWorkloadIdentitySource:
    """TrustedWorkloadIdentitySource backed by signed external raw proof evidence."""

    def __init__(
        self,
        *,
        pin: FixedSourcePin,
        raw_provider: RawWorkloadIdentityProvider,
        signature_verifier: SignatureVerifier,
        clock: Clock,
        trust_domain: str,
        tenant_id: str,
        organization_id: str,
        audience: str,
        environment: str,
        issuer_id: str,
    ) -> None:
        self._pin = pin.validate()
        _require_provider(raw_provider)
        if not callable(signature_verifier) or not callable(clock):
            raise VerifierIdentityProviderError("workload verifier dependencies are invalid")
        for value in (trust_domain, tenant_id, organization_id, audience, environment, issuer_id):
            if not isinstance(value, str) or not value.strip():
                raise VerifierIdentityProviderError("workload trust policy is invalid")
        self._provider = raw_provider
        self._verifier = signature_verifier
        self._clock = clock
        self._policy = (trust_domain, tenant_id, organization_id, audience, environment, issuer_id)

    @property
    def source_id(self) -> str: return self._pin.source_id
    @property
    def source_instance_id(self) -> str: return self._pin.source_instance_id
    @property
    def source_implementation_digest(self) -> str: return self._pin.source_implementation_digest
    @property
    def trust_anchor_id(self) -> str: return self._pin.trust_anchor_id

    def resolve(self, target: ExactVerificationTarget) -> VerifiedWorkloadIdentity:
        target.validate()
        try:
            proof = self._provider.resolve(target)
        except Exception as exc:
            raise VerifierIdentityProviderError("workload proof provider failed closed") from exc
        if type(proof) is not WorkloadIdentityProof:
            raise VerifierIdentityProviderError("provider must return raw WorkloadIdentityProof")
        trust_domain, tenant, org, audience, environment, issuer = self._policy
        context = WorkloadIdentityContext(
            trust_domain=trust_domain,
            tenant_id=tenant,
            organization_id=org,
            audience=audience,
            environment=environment,
            repository=target.repository,
            vcs_ref=target.head_sha,
            issuer_id=issuer,
        )
        try:
            return verify_workload_identity(proof, self._verifier, now=_now(self._clock), context=context)
        except Exception as exc:
            raise VerifierIdentityProviderError("workload identity verification failed closed") from exc


class RealVerifierRuntimeAttestationSource:
    """TrustedRuntimeAttestationSource backed by externally attested raw runtime evidence."""

    def __init__(
        self,
        *,
        pin: FixedSourcePin,
        raw_provider: RawRuntimeEvidenceProvider,
        verifier: RuntimeAttestationVerifier,
        clock: Clock,
        expected_issuer: str,
    ) -> None:
        self._pin = pin.validate()
        _require_provider(raw_provider)
        if type(verifier) is not RuntimeAttestationVerifier or not callable(clock):
            raise VerifierIdentityProviderError("runtime verifier dependencies are invalid")
        if not isinstance(expected_issuer, str) or not expected_issuer.strip():
            raise VerifierIdentityProviderError("runtime issuer policy is invalid")
        self._provider = raw_provider
        self._verifier = verifier
        self._clock = clock
        self._issuer = expected_issuer

    @property
    def source_id(self) -> str: return self._pin.source_id
    @property
    def source_instance_id(self) -> str: return self._pin.source_instance_id
    @property
    def source_implementation_digest(self) -> str: return self._pin.source_implementation_digest
    @property
    def trust_anchor_id(self) -> str: return self._pin.trust_anchor_id

    def resolve(self, target: ExactVerificationTarget) -> VerifiedRuntimeAttestation:
        target.validate()
        try:
            raw = self._provider.resolve(target)
        except Exception as exc:
            raise VerifierIdentityProviderError("runtime evidence provider failed closed") from exc
        if type(raw) is not RawRuntimeEvidence:
            raise VerifierIdentityProviderError("provider must return RawRuntimeEvidence")
        raw.validate()
        att = raw.attestation
        if (
            att.repository != target.repository
            or att.commit_sha != target.head_sha
            or att.tree_sha != target.tree_sha
            or att.mission_id != target.mission_id
            or att.issuer != self._issuer
        ):
            raise VerifierIdentityProviderError("runtime evidence target binding mismatch")
        context = RuntimeAttestationContext(
            repository=att.repository,
            repository_id=att.repository_id,
            commit_sha=att.commit_sha,
            tree_sha=att.tree_sha,
            workflow_ref=att.workflow_ref,
            workflow_sha=att.workflow_sha,
            run_id=att.run_id,
            run_attempt=att.run_attempt,
            mission_id=att.mission_id,
            issuer=self._issuer,
        )
        try:
            return self._verifier.verify(att, artifact_bytes=raw.artifact_bytes, now=_now(self._clock), context=context)
        except Exception as exc:
            raise VerifierIdentityProviderError("runtime attestation verification failed closed") from exc


class RealVerifierParticipationSource:
    """Pinned external participation history with exact builder/attach cardinality."""

    def __init__(self, *, pin: FixedSourcePin, raw_provider: RawParticipationHistoryProvider) -> None:
        self._pin = pin.validate()
        _require_provider(raw_provider)
        self._provider = raw_provider

    @property
    def source_id(self) -> str: return self._pin.source_id
    @property
    def source_instance_id(self) -> str: return self._pin.source_instance_id
    @property
    def source_implementation_digest(self) -> str: return self._pin.source_implementation_digest
    @property
    def trust_anchor_id(self) -> str: return self._pin.trust_anchor_id

    def resolve(self, target: ExactVerificationTarget) -> TrustedParticipationHistory:
        target.validate()
        try:
            history = self._provider.resolve(target)
        except Exception as exc:
            raise VerifierIdentityProviderError("participation provider failed closed") from exc
        if type(history) is not TrustedParticipationHistory:
            raise VerifierIdentityProviderError("participation provider returned wrong type")
        history.validate()
        if history.source_binding() != self._pin.binding():
            raise VerifierIdentityProviderError("participation provider trust pin mismatch")
        relevant = tuple(
            r for r in history.records
            if r.repository == target.repository
            and r.mission_id == target.mission_id
            and r.target_head_sha == target.head_sha
            and r.target_tree_sha == target.tree_sha
        )
        builders = tuple(r for r in relevant if r.participation_role == "BUILDER")
        attaches = tuple(r for r in relevant if r.participation_role == "VERIFICATION_ATTACH")
        if len(builders) != 1 or len(attaches) != 1:
            raise VerifierIdentityProviderError("builder/attach participation history is missing or ambiguous")
        return history

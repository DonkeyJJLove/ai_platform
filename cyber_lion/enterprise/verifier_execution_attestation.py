"""Fail-closed B1 verifier-execution independence admission.

Trusted identity, runtime, participation, CI and semantic results are resolved only
through composition-root-owned fixed sources. The public admission call accepts no
caller-supplied trusted evidence and exposes no effect or authority capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Protocol

from cyber_lion.contracts.verifier_execution_attestation import (
    ExactVerificationTarget,
    FixedSourcePin,
    TrustedCIEvidence,
    TrustedParticipationHistory,
    TrustedSemanticVerificationResult,
    VerifierExecutionAttestation,
    VerifierExecutionAttestationError,
    evidence_bundle_digest,
)
from cyber_lion.contracts.workload_identity import VerifiedWorkloadIdentity
from cyber_lion.enterprise.runtime_attestation import VerifiedRuntimeAttestation


class VerifierExecutionAdmissionError(ValueError):
    """Raised when verifier independence cannot be proven exactly."""


class TrustedWorkloadIdentitySource(Protocol):
    @property
    def source_id(self) -> str: ...
    @property
    def source_instance_id(self) -> str: ...
    @property
    def source_implementation_digest(self) -> str: ...
    @property
    def trust_anchor_id(self) -> str: ...
    def resolve(self, target: ExactVerificationTarget) -> VerifiedWorkloadIdentity: ...


class TrustedRuntimeAttestationSource(Protocol):
    @property
    def source_id(self) -> str: ...
    @property
    def source_instance_id(self) -> str: ...
    @property
    def source_implementation_digest(self) -> str: ...
    @property
    def trust_anchor_id(self) -> str: ...
    def resolve(self, target: ExactVerificationTarget) -> VerifiedRuntimeAttestation: ...


class TrustedExecutionParticipationSource(Protocol):
    @property
    def source_id(self) -> str: ...
    @property
    def source_instance_id(self) -> str: ...
    @property
    def source_implementation_digest(self) -> str: ...
    @property
    def trust_anchor_id(self) -> str: ...
    def resolve(self, target: ExactVerificationTarget) -> TrustedParticipationHistory: ...


class TrustedCIEvidenceSource(Protocol):
    @property
    def source_id(self) -> str: ...
    @property
    def source_instance_id(self) -> str: ...
    @property
    def source_implementation_digest(self) -> str: ...
    @property
    def trust_anchor_id(self) -> str: ...
    def resolve(self, target: ExactVerificationTarget) -> TrustedCIEvidence: ...


class TrustedSemanticVerificationSource(Protocol):
    @property
    def source_id(self) -> str: ...
    @property
    def source_instance_id(self) -> str: ...
    @property
    def source_implementation_digest(self) -> str: ...
    @property
    def trust_anchor_id(self) -> str: ...
    def resolve(self, target: ExactVerificationTarget) -> TrustedSemanticVerificationResult: ...


class VerifierExecutionReplayGuard(Protocol):
    def consume(self, attestation_digest: str) -> bool: ...


class InMemoryVerifierExecutionReplayGuard:
    """Atomic process-local reference guard. Durable deployment is external."""
    def __init__(self) -> None:
        self._lock = Lock()
        self._seen: set[str] = set()

    def consume(self, attestation_digest: str) -> bool:
        with self._lock:
            if attestation_digest in self._seen:
                return False
            self._seen.add(attestation_digest)
            return True


@dataclass(frozen=True)
class VerifierExecutionAdmissionResult:
    attestation_digest: str
    target_digest: str
    verifier_subject_id: str
    verifier_runtime_instance_id: str
    participation_history_digest: str
    ci_evidence_digest: str
    semantic_verification_result_digest: str
    evidence_bundle_digest: str
    verification_result: str


@dataclass(frozen=True)
class _PinnedSource:
    provider: object
    pin: FixedSourcePin

    def validate_provider(self) -> None:
        self.pin.validate()
        actual = (
            getattr(self.provider, "source_id", None),
            getattr(self.provider, "source_instance_id", None),
            getattr(self.provider, "source_implementation_digest", None),
            getattr(self.provider, "trust_anchor_id", None),
        )
        if actual != self.pin.binding():
            raise VerifierExecutionAdmissionError("trusted source identity substitution denied")
        if not callable(getattr(self.provider, "resolve", None)):
            raise VerifierExecutionAdmissionError("trusted source has no resolve capability")


class VerifierExecutionAdmission:
    """Composition-root-pinned B1 gate for one exact verification target."""

    def __init__(
        self, *, expected_target: ExactVerificationTarget,
        workload_source: TrustedWorkloadIdentitySource, workload_source_pin: FixedSourcePin,
        runtime_source: TrustedRuntimeAttestationSource, runtime_source_pin: FixedSourcePin,
        participation_source: TrustedExecutionParticipationSource, participation_source_pin: FixedSourcePin,
        ci_source: TrustedCIEvidenceSource, ci_source_pin: FixedSourcePin,
        semantic_source: TrustedSemanticVerificationSource, semantic_source_pin: FixedSourcePin,
        replay_guard: VerifierExecutionReplayGuard,
    ) -> None:
        expected_target.validate()
        if not callable(getattr(replay_guard, "consume", None)):
            raise VerifierExecutionAdmissionError("replay guard is required")
        self._target = expected_target
        self._workload = _PinnedSource(workload_source, workload_source_pin)
        self._runtime = _PinnedSource(runtime_source, runtime_source_pin)
        self._participation = _PinnedSource(participation_source, participation_source_pin)
        self._ci = _PinnedSource(ci_source, ci_source_pin)
        self._semantic = _PinnedSource(semantic_source, semantic_source_pin)
        for source in (self._workload, self._runtime, self._participation, self._ci, self._semantic):
            source.validate_provider()
        self._replay = replay_guard

    @staticmethod
    def _utc(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise VerifierExecutionAdmissionError("evidence timestamp is invalid") from exc
        if parsed.tzinfo is None:
            raise VerifierExecutionAdmissionError("evidence timestamp must be timezone-aware")
        return parsed.astimezone(timezone.utc)

    def _resolve(self, pinned: _PinnedSource, expected_type: type, label: str):
        pinned.validate_provider()
        try:
            value = pinned.provider.resolve(self._target)
        except Exception as exc:
            raise VerifierExecutionAdmissionError(f"{label} source failed closed") from exc
        if type(value) is not expected_type:
            raise VerifierExecutionAdmissionError(f"{label} source returned wrong type")
        if hasattr(value, "validate"):
            try:
                value.validate()
            except Exception as exc:
                raise VerifierExecutionAdmissionError(f"{label} evidence validation failed") from exc
        if hasattr(value, "source_binding") and value.source_binding() != pinned.pin.binding():
            raise VerifierExecutionAdmissionError(f"{label} evidence source pin mismatch")
        return value

    def admit(self, attestation: VerifierExecutionAttestation, *, now: datetime) -> VerifierExecutionAdmissionResult:
        if type(attestation) is not VerifierExecutionAttestation:
            raise VerifierExecutionAdmissionError("exact verifier attestation type required")
        try:
            attestation.validate()
        except VerifierExecutionAttestationError as exc:
            raise VerifierExecutionAdmissionError("verifier execution attestation invalid") from exc
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise VerifierExecutionAdmissionError("trusted current time must be timezone-aware")
        current = now.astimezone(timezone.utc)
        if current < self._utc(attestation.issued_at) or current >= self._utc(attestation.expires_at):
            raise VerifierExecutionAdmissionError("verifier execution attestation is not currently valid")
        if attestation.target != self._target:
            raise VerifierExecutionAdmissionError("verification target mismatch")

        workload = self._resolve(self._workload, VerifiedWorkloadIdentity, "workload identity")
        if current < self._utc(workload.issued_at) or current >= self._utc(workload.expires_at):
            raise VerifierExecutionAdmissionError("verified workload identity is not currently valid")
        if workload.subject_id != attestation.verifier_subject_id:
            raise VerifierExecutionAdmissionError("workload subject binding mismatch")
        if workload.proof_digest != attestation.workload_identity_proof_digest:
            raise VerifierExecutionAdmissionError("workload proof digest binding mismatch")

        runtime = self._resolve(self._runtime, VerifiedRuntimeAttestation, "runtime attestation")
        runtime_binding = (
            runtime.subject_id, runtime.runtime_instance_id, runtime.implementation_digest,
            runtime.attestation_digest, runtime.repository, runtime.commit_sha, runtime.mission_id,
        )
        expected_runtime = (
            attestation.verifier_subject_id, attestation.verifier_runtime_instance_id,
            attestation.verifier_implementation_digest, attestation.runtime_attestation_digest,
            self._target.repository, self._target.head_sha, self._target.mission_id,
        )
        if runtime_binding != expected_runtime:
            raise VerifierExecutionAdmissionError("runtime attestation binding mismatch")

        history = self._resolve(self._participation, TrustedParticipationHistory, "participation history")
        if history.history_digest != attestation.participation_history_digest:
            raise VerifierExecutionAdmissionError("participation history digest mismatch")
        relevant = tuple(
            record for record in history.records
            if record.repository == self._target.repository
            and record.mission_id == self._target.mission_id
            and record.target_head_sha == self._target.head_sha
            and record.target_tree_sha == self._target.tree_sha
        )
        if not relevant:
            raise VerifierExecutionAdmissionError("participation history does not cover exact target")
        forbidden_roles = {"BUILDER", "VERIFICATION_ATTACH"}
        roles = {record.participation_role for record in relevant}
        if not forbidden_roles.issubset(roles):
            raise VerifierExecutionAdmissionError("participation history is incomplete or ambiguous")
        for record in relevant:
            if record.participation_role not in forbidden_roles:
                continue
            if record.subject_id == attestation.verifier_subject_id:
                raise VerifierExecutionAdmissionError("verifier subject participated in builder/attach role")
            if record.runtime_instance_id == attestation.verifier_runtime_instance_id:
                raise VerifierExecutionAdmissionError("verifier runtime participated in builder/attach role")

        ci = self._resolve(self._ci, TrustedCIEvidence, "CI evidence")
        expected_ci = (
            self._target.repository, self._target.pr_number, self._target.base_sha,
            self._target.head_sha, self._target.tree_sha, self._target.ci_run_id,
        )
        if ci.target_binding() != expected_ci:
            raise VerifierExecutionAdmissionError("CI evidence target mismatch")
        if ci.conclusion != "SUCCESS":
            raise VerifierExecutionAdmissionError("CI evidence is not successful")
        if ci.digest() != attestation.ci_evidence_digest:
            raise VerifierExecutionAdmissionError("CI evidence digest binding mismatch")

        semantic = self._resolve(self._semantic, TrustedSemanticVerificationResult, "semantic verification")
        if semantic.target_digest != self._target.digest():
            raise VerifierExecutionAdmissionError("semantic verification target mismatch")
        semantic_binding = (
            semantic.verifier_subject_id,
            semantic.verifier_runtime_instance_id,
            semantic.verifier_implementation_digest,
        )
        if semantic_binding != (
            attestation.verifier_subject_id,
            attestation.verifier_runtime_instance_id,
            attestation.verifier_implementation_digest,
        ):
            raise VerifierExecutionAdmissionError("semantic verifier identity binding mismatch")
        if semantic.result != "PASS":
            raise VerifierExecutionAdmissionError("trusted semantic verification did not PASS")
        if semantic.digest() != attestation.semantic_verification_result_digest:
            raise VerifierExecutionAdmissionError("semantic verification digest binding mismatch")

        expected_bundle = evidence_bundle_digest(
            target=self._target,
            workload_identity_proof_digest=workload.proof_digest,
            runtime_attestation_digest=runtime.attestation_digest,
            verifier_implementation_digest=runtime.implementation_digest,
            participation_history_digest=history.history_digest,
            ci_evidence_digest=ci.digest(),
            semantic_verification_result_digest=semantic.digest(),
        )
        if attestation.evidence_bundle_digest != expected_bundle:
            raise VerifierExecutionAdmissionError("evidence bundle digest mismatch")

        digest = attestation.digest()
        try:
            consumed = self._replay.consume(digest)
        except Exception as exc:
            raise VerifierExecutionAdmissionError("verifier replay guard failed closed") from exc
        if consumed is not True:
            raise VerifierExecutionAdmissionError("verifier execution attestation replay denied")

        return VerifierExecutionAdmissionResult(
            attestation_digest=digest,
            target_digest=self._target.digest(),
            verifier_subject_id=attestation.verifier_subject_id,
            verifier_runtime_instance_id=attestation.verifier_runtime_instance_id,
            participation_history_digest=history.history_digest,
            ci_evidence_digest=ci.digest(),
            semantic_verification_result_digest=semantic.digest(),
            evidence_bundle_digest=expected_bundle,
            verification_result="PASS",
        )

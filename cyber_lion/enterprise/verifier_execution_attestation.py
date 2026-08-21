"""Fail-closed verifier execution independence admission.

This module evaluates evidence only. It exposes no repository mutation, merge,
release, deployment, authority-consumption, lease, or credential capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Protocol

from cyber_lion.contracts.verifier_execution_attestation import (
    ExactVerificationTarget,
    TrustedParticipationHistory,
    VerifierExecutionAttestation,
    VerifierExecutionAttestationError,
    evidence_bundle_digest,
)
from cyber_lion.contracts.workload_identity import VerifiedWorkloadIdentity
from cyber_lion.enterprise.runtime_attestation import VerifiedRuntimeAttestation


class VerifierExecutionAdmissionError(ValueError):
    """Raised when verifier independence cannot be proven exactly."""


class TrustedExecutionParticipationSource(Protocol):
    @property
    def source_id(self) -> str: ...

    @property
    def trust_anchor_id(self) -> str: ...

    @property
    def source_implementation_digest(self) -> str: ...

    def resolve(self, target: ExactVerificationTarget) -> TrustedParticipationHistory: ...


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
    evidence_bundle_digest: str
    verification_result: str


class VerifierExecutionAdmission:
    """Composition-root-pinned independence gate for one exact verification target."""

    def __init__(
        self,
        *,
        expected_target: ExactVerificationTarget,
        participation_source: TrustedExecutionParticipationSource,
        expected_participation_source_id: str,
        expected_participation_trust_anchor_id: str,
        expected_participation_implementation_digest: str,
        replay_guard: VerifierExecutionReplayGuard,
    ) -> None:
        expected_target.validate()
        if not expected_participation_source_id or not expected_participation_trust_anchor_id:
            raise VerifierExecutionAdmissionError("participation source pins are required")
        if len(expected_participation_implementation_digest) != 64:
            raise VerifierExecutionAdmissionError("participation implementation digest pin is invalid")
        if not callable(getattr(participation_source, "resolve", None)):
            raise VerifierExecutionAdmissionError("trusted participation source is required")
        if not callable(getattr(replay_guard, "consume", None)):
            raise VerifierExecutionAdmissionError("replay guard is required")
        self._target = expected_target
        self._source = participation_source
        self._source_id = expected_participation_source_id
        self._source_anchor = expected_participation_trust_anchor_id
        self._source_impl = expected_participation_implementation_digest
        self._replay = replay_guard

    def _history(self) -> TrustedParticipationHistory:
        actual = (
            getattr(self._source, "source_id", None),
            getattr(self._source, "trust_anchor_id", None),
            getattr(self._source, "source_implementation_digest", None),
        )
        expected = (self._source_id, self._source_anchor, self._source_impl)
        if actual != expected:
            raise VerifierExecutionAdmissionError("participation source identity substitution denied")
        try:
            history = self._source.resolve(self._target)
        except Exception as exc:
            raise VerifierExecutionAdmissionError("participation history source failed closed") from exc
        if type(history) is not TrustedParticipationHistory:
            raise VerifierExecutionAdmissionError("participation source returned wrong type")
        try:
            history.validate()
        except Exception as exc:
            raise VerifierExecutionAdmissionError("participation history validation failed") from exc
        history_binding = (
            history.source_id,
            history.trust_anchor_id,
            history.source_implementation_digest,
        )
        if history_binding != expected:
            raise VerifierExecutionAdmissionError("participation history pin mismatch")
        if not history.records:
            raise VerifierExecutionAdmissionError("participation history is missing")
        return history

    @staticmethod
    def _utc(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise VerifierExecutionAdmissionError("attestation time is invalid") from exc
        if parsed.tzinfo is None:
            raise VerifierExecutionAdmissionError("attestation time must be timezone-aware")
        return parsed.astimezone(timezone.utc)

    def admit(
        self,
        attestation: VerifierExecutionAttestation,
        *,
        workload_identity: VerifiedWorkloadIdentity,
        runtime_attestation: VerifiedRuntimeAttestation,
        semantic_evidence_digest: str,
        now: datetime,
    ) -> VerifierExecutionAdmissionResult:
        if type(attestation) is not VerifierExecutionAttestation:
            raise VerifierExecutionAdmissionError("exact verifier attestation type required")
        try:
            attestation.validate()
        except VerifierExecutionAttestationError as exc:
            raise VerifierExecutionAdmissionError("verifier execution attestation invalid") from exc
        if type(workload_identity) is not VerifiedWorkloadIdentity:
            raise VerifierExecutionAdmissionError("verified workload identity required")
        if type(runtime_attestation) is not VerifiedRuntimeAttestation:
            raise VerifierExecutionAdmissionError("verified runtime attestation required")
        if now.tzinfo is None:
            raise VerifierExecutionAdmissionError("trusted current time must be timezone-aware")
        current = now.astimezone(timezone.utc)
        if current < self._utc(attestation.issued_at) or current >= self._utc(attestation.expires_at):
            raise VerifierExecutionAdmissionError("verifier execution attestation is not currently valid")
        if attestation.target != self._target:
            raise VerifierExecutionAdmissionError("verification target mismatch")

        if workload_identity.subject_id != attestation.verifier_subject_id:
            raise VerifierExecutionAdmissionError("workload subject binding mismatch")
        if workload_identity.proof_digest != attestation.workload_identity_proof_digest:
            raise VerifierExecutionAdmissionError("workload proof digest binding mismatch")

        runtime_binding = (
            runtime_attestation.subject_id,
            runtime_attestation.runtime_instance_id,
            runtime_attestation.implementation_digest,
            runtime_attestation.attestation_digest,
            runtime_attestation.repository,
            runtime_attestation.commit_sha,
            runtime_attestation.mission_id,
        )
        expected_runtime = (
            attestation.verifier_subject_id,
            attestation.verifier_runtime_instance_id,
            attestation.verifier_implementation_digest,
            attestation.runtime_attestation_digest,
            self._target.repository,
            self._target.head_sha,
            self._target.mission_id,
        )
        if runtime_binding != expected_runtime:
            raise VerifierExecutionAdmissionError("runtime attestation binding mismatch")

        history = self._history()
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
        for record in relevant:
            if record.participation_role not in forbidden_roles:
                continue
            if record.subject_id == attestation.verifier_subject_id:
                raise VerifierExecutionAdmissionError("verifier subject participated in builder/attach role")
            if record.runtime_instance_id == attestation.verifier_runtime_instance_id:
                raise VerifierExecutionAdmissionError("verifier runtime participated in builder/attach role")

        # Require both builder and verification-attach history for the exact target.
        roles = {record.participation_role for record in relevant}
        if not forbidden_roles.issubset(roles):
            raise VerifierExecutionAdmissionError("participation history is incomplete or ambiguous")

        expected_bundle = evidence_bundle_digest(
            target=self._target,
            workload_identity_proof_digest=workload_identity.proof_digest,
            runtime_attestation_digest=runtime_attestation.attestation_digest,
            verifier_implementation_digest=runtime_attestation.implementation_digest,
            participation_history_digest=history.history_digest,
            semantic_evidence_digest=semantic_evidence_digest,
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
            evidence_bundle_digest=expected_bundle,
            verification_result=attestation.verification_result,
        )

"""Trusted admission boundary for externally attested pure runtime observations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from threading import Lock
from typing import Protocol

from cyber_lion.contracts.runtime_attestation import (
    RuntimeAttestation,
    RuntimeAttestationContext,
    RuntimeAttestationError,
)


class RuntimeAttestationVerificationError(ValueError):
    """Raised when external runtime provenance cannot be proven exactly."""


@dataclass(frozen=True)
class ExternalAttestationEvidence:
    """Result returned by a trusted external attestation verifier/provider."""

    attestation_digest: str
    subject_id: str
    runtime_instance_id: str
    repository: str
    commit_sha: str
    workflow_sha: str
    run_id: str
    run_attempt: int
    mission_id: str
    artifact_digest: str
    issuer: str
    provenance_ref: str
    trust_anchor_id: str


class ExternalAttestationVerifier(Protocol):
    def verify_external(self, attestation: RuntimeAttestation) -> ExternalAttestationEvidence:
        """Verify provenance without trusting the attested workload itself."""
        ...


@dataclass(frozen=True)
class RuntimeReplayKey:
    attestation_id: str
    subject_id: str
    runtime_instance_id: str
    run_id: str
    run_attempt: int
    artifact_digest: str


class RuntimeReplayGuard(Protocol):
    def consume(self, key: RuntimeReplayKey) -> bool: ...


class InMemoryRuntimeReplayGuard:
    """Atomic process-local reference guard for the N=2 experiment."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._seen: set[RuntimeReplayKey] = set()

    def consume(self, key: RuntimeReplayKey) -> bool:
        with self._lock:
            if key in self._seen:
                return False
            self._seen.add(key)
            return True


@dataclass(frozen=True)
class VerifiedRuntimeAttestation:
    subject_id: str
    runtime_instance_id: str
    repository: str
    commit_sha: str
    workflow_sha: str
    run_id: str
    run_attempt: int
    mission_id: str
    artifact_digest: str
    implementation_digest: str
    attestation_digest: str
    provenance_ref: str
    trust_anchor_id: str


class RuntimeAttestationVerifier:
    """Fail-closed verifier over external provenance plus exact runtime bytes."""

    def __init__(
        self,
        *,
        external_verifier: ExternalAttestationVerifier,
        replay_guard: RuntimeReplayGuard,
    ) -> None:
        self._external_verifier = external_verifier
        self._replay_guard = replay_guard

    def verify(
        self,
        attestation: RuntimeAttestation,
        *,
        artifact_bytes: bytes,
        now: datetime,
        context: RuntimeAttestationContext,
    ) -> VerifiedRuntimeAttestation:
        if not isinstance(attestation, RuntimeAttestation):
            raise RuntimeAttestationVerificationError("runtime attestation is missing")
        try:
            attestation.validate()
        except RuntimeAttestationError as exc:
            raise RuntimeAttestationVerificationError("runtime attestation is invalid") from exc
        if not isinstance(artifact_bytes, bytes) or not artifact_bytes:
            raise RuntimeAttestationVerificationError("artifact bytes are required")
        if now.tzinfo is None:
            raise RuntimeAttestationVerificationError("verification time must be timezone-aware")
        current = now.astimezone(timezone.utc)
        issued = datetime.fromisoformat(attestation.issued_at.replace("Z", "+00:00")).astimezone(timezone.utc)
        expires = datetime.fromisoformat(attestation.expires_at.replace("Z", "+00:00")).astimezone(timezone.utc)
        if current < issued or current >= expires:
            raise RuntimeAttestationVerificationError("runtime attestation is not currently valid")

        actual_binding = (
            attestation.repository, attestation.repository_id, attestation.commit_sha,
            attestation.tree_sha, attestation.workflow_ref, attestation.workflow_sha,
            attestation.run_id, attestation.run_attempt, attestation.mission_id,
            attestation.issuer,
        )
        if actual_binding != context.binding():
            raise RuntimeAttestationVerificationError("runtime attestation context mismatch")

        computed_digest = hashlib.sha256(artifact_bytes).hexdigest()
        if computed_digest != attestation.artifact_digest:
            raise RuntimeAttestationVerificationError("artifact digest does not match runtime bytes")

        try:
            evidence = self._external_verifier.verify_external(attestation)
        except Exception as exc:
            raise RuntimeAttestationVerificationError("external attestation verifier failed closed") from exc
        if not isinstance(evidence, ExternalAttestationEvidence):
            raise RuntimeAttestationVerificationError("external attestation result is invalid")

        expected_external = (
            attestation.digest(), attestation.subject_id, attestation.runtime_instance_id,
            attestation.repository, attestation.commit_sha, attestation.workflow_sha,
            attestation.run_id, attestation.run_attempt, attestation.mission_id,
            computed_digest, attestation.issuer, attestation.provenance_ref,
        )
        actual_external = (
            evidence.attestation_digest, evidence.subject_id, evidence.runtime_instance_id,
            evidence.repository, evidence.commit_sha, evidence.workflow_sha,
            evidence.run_id, evidence.run_attempt, evidence.mission_id,
            evidence.artifact_digest, evidence.issuer, evidence.provenance_ref,
        )
        if actual_external != expected_external or not evidence.trust_anchor_id:
            raise RuntimeAttestationVerificationError("external provenance binding mismatch")

        key = RuntimeReplayKey(
            attestation.attestation_id,
            attestation.subject_id,
            attestation.runtime_instance_id,
            attestation.run_id,
            attestation.run_attempt,
            computed_digest,
        )
        try:
            accepted = self._replay_guard.consume(key)
        except Exception as exc:
            raise RuntimeAttestationVerificationError("runtime replay guard failed closed") from exc
        if accepted is not True:
            raise RuntimeAttestationVerificationError("runtime attestation replay rejected")

        return VerifiedRuntimeAttestation(
            subject_id=attestation.subject_id,
            runtime_instance_id=attestation.runtime_instance_id,
            repository=attestation.repository,
            commit_sha=attestation.commit_sha,
            workflow_sha=attestation.workflow_sha,
            run_id=attestation.run_id,
            run_attempt=attestation.run_attempt,
            mission_id=attestation.mission_id,
            artifact_digest=computed_digest,
            implementation_digest=computed_digest,
            attestation_digest=attestation.digest(),
            provenance_ref=attestation.provenance_ref,
            trust_anchor_id=evidence.trust_anchor_id,
        )


def verify_n2_pair(
    first: VerifiedRuntimeAttestation,
    second: VerifiedRuntimeAttestation,
) -> tuple[VerifiedRuntimeAttestation, VerifiedRuntimeAttestation]:
    """Prove two distinct runtime observations without claiming L2 by itself."""
    if not isinstance(first, VerifiedRuntimeAttestation) or not isinstance(second, VerifiedRuntimeAttestation):
        raise RuntimeAttestationVerificationError("N2 evidence must be verified runtime evidence")
    if first.mission_id != second.mission_id:
        raise RuntimeAttestationVerificationError("N2 evidence must share one mission root")
    if first.repository != second.repository or first.commit_sha != second.commit_sha:
        raise RuntimeAttestationVerificationError("N2 evidence repository/commit mismatch")
    if first.runtime_instance_id == second.runtime_instance_id:
        raise RuntimeAttestationVerificationError("one runtime instance cannot satisfy N2")
    if first.attestation_digest == second.attestation_digest:
        raise RuntimeAttestationVerificationError("duplicate runtime evidence cannot satisfy N2")
    if first.provenance_ref == second.provenance_ref:
        raise RuntimeAttestationVerificationError("duplicate provenance reference cannot satisfy N2")
    return (first, second)

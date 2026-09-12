"""External APP_SESSION attestation verification candidate for E02.

This module composes externally verified APP_SESSION evidence. It owns no
private key, does not mint attestations, does not grant authority, does not
activate runtime, and treats process-local replay/sequence guards as TEST_ONLY
reference implementations rather than durable production evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Protocol

from cyber_lion.app_coordination.e02_trust_primitives import (
    AppSessionAttestationCandidate,
    TrustedTimeCandidate,
)
from cyber_lion.app_coordination.source_candidates import SourceRejected, digest, text


class AppSessionAttestationVerificationError(ValueError):
    """Raised when APP_SESSION external provenance cannot be proven exactly."""


@dataclass(frozen=True)
class ExternalAppSessionEvidence:
    candidate_digest: str
    session_id: str
    app_instance_id: str
    subject_digest: str
    provider_id: str
    provider_instance_id: str
    provider_implementation_digest: str
    trust_anchor_digest: str
    attestation_digest: str
    evidence_digest: str
    issuer_id: str
    provenance_ref: str
    sequence: int
    durable_sequence_digest: str

    def validate(self):
        for value in (
            self.candidate_digest, self.subject_digest, self.provider_implementation_digest,
            self.trust_anchor_digest, self.attestation_digest, self.evidence_digest,
            self.durable_sequence_digest,
        ):
            digest(value)
        for value in (
            self.session_id, self.app_instance_id, self.provider_id,
            self.provider_instance_id, self.issuer_id, self.provenance_ref,
        ):
            text(value)
        if type(self.sequence) is not int or self.sequence < 1:
            raise AppSessionAttestationVerificationError("positive external sequence required")
        return self


class ExternalAppSessionVerifier(Protocol):
    def verify_external(self, candidate: AppSessionAttestationCandidate) -> ExternalAppSessionEvidence:
        """Verify candidate provenance outside the attested application/session."""
        ...


@dataclass(frozen=True)
class AppSessionReplayKey:
    candidate_digest: str
    session_id: str
    app_instance_id: str
    subject_digest: str
    attestation_digest: str
    issuer_id: str
    sequence: int


class AppSessionReplayGuard(Protocol):
    def consume(self, key: AppSessionReplayKey) -> bool: ...


class AppSessionSequenceGuard(Protocol):
    def consume(self, provider_id: str, session_id: str, sequence: int, durable_sequence_digest: str) -> bool: ...


class AppSessionAtomicConsumptionGuard(Protocol):
    def consume(self, *, key: AppSessionReplayKey, provider_id: str, session_id: str,
                sequence: int, durable_sequence_digest: str, consumed_at: str) -> str:
        """Atomically consume replay + monotonic sequence and return a receipt digest."""
        ...


class InMemoryAppSessionReplayGuard:
    """TEST_ONLY process-local replay reference; not durable production proof."""
    def __init__(self) -> None:
        self._lock = Lock()
        self._seen: set[AppSessionReplayKey] = set()

    def consume(self, key: AppSessionReplayKey) -> bool:
        with self._lock:
            if key in self._seen:
                return False
            self._seen.add(key)
            return True


class InMemoryAppSessionSequenceGuard:
    """TEST_ONLY monotonic reference; production requires a durable provider."""
    def __init__(self) -> None:
        self._lock = Lock()
        self._last: dict[tuple[str, str], int] = {}

    def consume(self, provider_id: str, session_id: str, sequence: int, durable_sequence_digest: str) -> bool:
        digest(durable_sequence_digest)
        key = (provider_id, session_id)
        with self._lock:
            previous = self._last.get(key, 0)
            if sequence <= previous:
                return False
            self._last[key] = sequence
            return True


@dataclass(frozen=True)
class VerifiedAppSessionAttestationCandidate:
    session_id: str
    app_instance_id: str
    subject_digest: str
    provider_id: str
    provider_instance_id: str
    provider_implementation_digest: str
    trust_anchor_digest: str
    attestation_digest: str
    evidence_digest: str
    issuer_id: str
    provenance_ref: str
    sequence: int
    durable_sequence_digest: str
    trusted_time_digest: str
    candidate_digest: str
    durable_consumption_receipt_digest: str | None = None
    attestation_state: str = "EXTERNAL_ATTESTATION_VERIFIED_CANDIDATE"
    durable_sequence_state: str = "EXTERNAL_DURABLE_PROVIDER_REQUIRED"
    replay_state: str = "REPLAY_GUARD_CONSUMED"
    replay_result_atomicity: str = "PROCESS_LOCAL_NON_ATOMIC_REFERENCE"
    runtime_ready: bool = False
    authority_effect: str = "NONE"
    runtime_effect: str = "NONE"

    def validate(self):
        for value in (
            self.subject_digest, self.provider_implementation_digest, self.trust_anchor_digest,
            self.attestation_digest, self.evidence_digest, self.durable_sequence_digest,
            self.trusted_time_digest, self.candidate_digest,
        ):
            digest(value)
        for value in (
            self.session_id, self.app_instance_id, self.provider_id,
            self.provider_instance_id, self.issuer_id, self.provenance_ref,
        ):
            text(value)
        if type(self.sequence) is not int or self.sequence < 1:
            raise AppSessionAttestationVerificationError("positive verified sequence required")
        if self.attestation_state != "EXTERNAL_ATTESTATION_VERIFIED_CANDIDATE":
            raise AppSessionAttestationVerificationError("attestation state promotion")
        durable_mode = self.durable_consumption_receipt_digest is not None
        if durable_mode:
            digest(self.durable_consumption_receipt_digest)
            if self.durable_sequence_state != "DURABLE_ATOMIC_CANDIDATE_CONSUMED":
                raise AppSessionAttestationVerificationError("durable sequence state promotion")
            if self.replay_state != "DURABLE_REPLAY_CANDIDATE_CONSUMED":
                raise AppSessionAttestationVerificationError("replay state promotion")
            if self.replay_result_atomicity != "DURABLE_ATOMIC_CANDIDATE_NOT_RUNTIME_ADMISSION":
                raise AppSessionAttestationVerificationError("durable atomicity state promotion")
        else:
            if self.durable_sequence_state != "EXTERNAL_DURABLE_PROVIDER_REQUIRED":
                raise AppSessionAttestationVerificationError("durable sequence state promotion")
            if self.replay_state != "REPLAY_GUARD_CONSUMED":
                raise AppSessionAttestationVerificationError("replay state promotion")
            if self.replay_result_atomicity != "PROCESS_LOCAL_NON_ATOMIC_REFERENCE":
                raise AppSessionAttestationVerificationError("reference atomicity state promotion")
        if self.runtime_ready is not False or self.authority_effect != "NONE" or self.runtime_effect != "NONE":
            raise AppSessionAttestationVerificationError("verified app session candidate cannot activate runtime or authority")
        return self


class AppSessionAttestationVerifier:
    """Fail-closed external-verifier boundary for APP_SESSION candidate evidence."""
    def __init__(self, *, external_verifier: ExternalAppSessionVerifier,
                 replay_guard: AppSessionReplayGuard | None = None, sequence_guard: AppSessionSequenceGuard | None = None,
                 atomic_guard: AppSessionAtomicConsumptionGuard | None = None) -> None:
        if atomic_guard is None:
            if replay_guard is None or sequence_guard is None:
                raise AppSessionAttestationVerificationError("replay and sequence guards required without atomic durable guard")
        elif replay_guard is not None or sequence_guard is not None:
            raise AppSessionAttestationVerificationError("atomic durable guard cannot be mixed with split replay/sequence guards")
        self._external_verifier = external_verifier
        self._replay_guard = replay_guard
        self._sequence_guard = sequence_guard
        self._atomic_guard = atomic_guard

    def verify(self, candidate: AppSessionAttestationCandidate, *, trusted_time: TrustedTimeCandidate,
               trusted_now: datetime, expected_session_id: str, expected_app_instance_id: str,
               expected_subject_digest: str, expected_trust_anchor_digest: str,
               expected_issuer_id: str) -> VerifiedAppSessionAttestationCandidate:
        if type(candidate) is not AppSessionAttestationCandidate:
            raise AppSessionAttestationVerificationError("exact APP_SESSION candidate required")
        if type(trusted_time) is not TrustedTimeCandidate:
            raise AppSessionAttestationVerificationError("trusted time candidate required")
        if type(trusted_now) is not datetime or trusted_now.utcoffset() is None:
            raise AppSessionAttestationVerificationError("aware trusted time required")
        for value in (expected_session_id, expected_app_instance_id, expected_issuer_id):
            text(value)
        for value in (expected_subject_digest, expected_trust_anchor_digest):
            digest(value)
        try:
            candidate.validate_at(trusted_now)
            trusted_time.validate_at(trusted_now)
        except SourceRejected as exc:
            raise AppSessionAttestationVerificationError("APP_SESSION candidate or trusted time invalid") from exc
        if (candidate.session_id, candidate.app_instance_id, candidate.subject_digest) != (
                expected_session_id, expected_app_instance_id, expected_subject_digest):
            raise AppSessionAttestationVerificationError("APP_SESSION subject/session substitution")
        if candidate.trust_anchor_digest != expected_trust_anchor_digest:
            raise AppSessionAttestationVerificationError("APP_SESSION trust-anchor substitution")
        try:
            evidence = self._external_verifier.verify_external(candidate)
        except Exception as exc:
            raise AppSessionAttestationVerificationError("external APP_SESSION verifier failed closed") from exc
        if type(evidence) is not ExternalAppSessionEvidence:
            raise AppSessionAttestationVerificationError("external APP_SESSION evidence type invalid")
        try:
            evidence.validate()
        except Exception as exc:
            raise AppSessionAttestationVerificationError("external APP_SESSION evidence invalid") from exc
        expected = (
            candidate.digest(), candidate.session_id, candidate.app_instance_id, candidate.subject_digest,
            candidate.provider_id, candidate.provider_instance_id, candidate.provider_implementation_digest,
            candidate.trust_anchor_digest, candidate.attestation_digest, candidate.evidence_digest,
            expected_issuer_id,
        )
        actual = (
            evidence.candidate_digest, evidence.session_id, evidence.app_instance_id, evidence.subject_digest,
            evidence.provider_id, evidence.provider_instance_id, evidence.provider_implementation_digest,
            evidence.trust_anchor_digest, evidence.attestation_digest, evidence.evidence_digest,
            evidence.issuer_id,
        )
        if actual != expected:
            raise AppSessionAttestationVerificationError("external APP_SESSION provenance binding mismatch")
        key = AppSessionReplayKey(
            evidence.candidate_digest, evidence.session_id, evidence.app_instance_id,
            evidence.subject_digest, evidence.attestation_digest, evidence.issuer_id, evidence.sequence)
        durable_receipt = None
        if self._atomic_guard is not None:
            try:
                durable_receipt = self._atomic_guard.consume(
                    key=key, provider_id=evidence.provider_id, session_id=evidence.session_id,
                    sequence=evidence.sequence, durable_sequence_digest=evidence.durable_sequence_digest,
                    consumed_at=trusted_now.isoformat())
                digest(durable_receipt)
            except Exception as exc:
                raise AppSessionAttestationVerificationError("APP_SESSION durable atomic guard failed closed") from exc
        else:
            try:
                monotonic = self._sequence_guard.consume(
                    evidence.provider_id, evidence.session_id, evidence.sequence, evidence.durable_sequence_digest)
            except Exception as exc:
                raise AppSessionAttestationVerificationError("APP_SESSION sequence guard failed closed") from exc
            if monotonic is not True:
                raise AppSessionAttestationVerificationError("APP_SESSION sequence rollback or replay rejected")
            try:
                fresh = self._replay_guard.consume(key)
            except Exception as exc:
                raise AppSessionAttestationVerificationError("APP_SESSION replay guard failed closed") from exc
            if fresh is not True:
                raise AppSessionAttestationVerificationError("APP_SESSION attestation replay rejected")
        return VerifiedAppSessionAttestationCandidate(
            session_id=evidence.session_id,
            app_instance_id=evidence.app_instance_id,
            subject_digest=evidence.subject_digest,
            provider_id=evidence.provider_id,
            provider_instance_id=evidence.provider_instance_id,
            provider_implementation_digest=evidence.provider_implementation_digest,
            trust_anchor_digest=evidence.trust_anchor_digest,
            attestation_digest=evidence.attestation_digest,
            evidence_digest=evidence.evidence_digest,
            issuer_id=evidence.issuer_id,
            provenance_ref=evidence.provenance_ref,
            sequence=evidence.sequence,
            durable_sequence_digest=evidence.durable_sequence_digest,
            trusted_time_digest=trusted_time.digest(),
            candidate_digest=evidence.candidate_digest,
            durable_consumption_receipt_digest=durable_receipt,
            durable_sequence_state=("DURABLE_ATOMIC_CANDIDATE_CONSUMED" if durable_receipt else "EXTERNAL_DURABLE_PROVIDER_REQUIRED"),
            replay_state=("DURABLE_REPLAY_CANDIDATE_CONSUMED" if durable_receipt else "REPLAY_GUARD_CONSUMED"),
            replay_result_atomicity=("DURABLE_ATOMIC_CANDIDATE_NOT_RUNTIME_ADMISSION" if durable_receipt else "PROCESS_LOCAL_NON_ATOMIC_REFERENCE"),
        ).validate()

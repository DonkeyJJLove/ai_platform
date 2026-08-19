"""Authenticated signed-event envelope with bounded replay admission."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from threading import Lock
from typing import Callable, Protocol

from .events import EventEnvelope
from .workload_identity import VerifiedWorkloadIdentity

Verifier = Callable[[bytes, str, str, str], bool]
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class SignedEventError(ValueError):
    pass


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise SignedEventError("invalid signed-event timestamp") from exc
    if parsed.tzinfo is None:
        raise SignedEventError("signed-event timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ReplayKey:
    tenant_id: str
    signer_subject_id: str
    correlation_id: str
    sequence: int
    nonce: str
    event_id: str


class ReplayGuard(Protocol):
    def consume(self, key: ReplayKey) -> bool: ...


class InMemoryReplayGuard:
    """Atomic process-local reference guard; deliberately not durable."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._last_sequence: dict[tuple[str, str, str], int] = {}
        self._nonces: set[tuple[str, str, str]] = set()
        self._event_ids: set[tuple[str, str, str]] = set()

    def consume(self, key: ReplayKey) -> bool:
        stream = (key.tenant_id, key.signer_subject_id, key.correlation_id)
        principal = (key.tenant_id, key.signer_subject_id)
        nonce_key = (*principal, key.nonce)
        event_key = (*principal, key.event_id)
        with self._lock:
            if key.sequence <= self._last_sequence.get(stream, 0):
                return False
            if nonce_key in self._nonces or event_key in self._event_ids:
                return False
            self._last_sequence[stream] = key.sequence
            self._nonces.add(nonce_key)
            self._event_ids.add(event_key)
            return True


@dataclass(frozen=True)
class SignedEventEnvelope:
    schema_version: str
    tenant_id: str
    organization_id: str
    trust_domain: str
    audience: str
    signer_subject_id: str
    signer_proof_digest: str
    key_id: str
    algorithm: str
    sequence: int
    nonce: str
    event: EventEnvelope
    signature: str

    def validate(self) -> "SignedEventEnvelope":
        limits = {
            "tenant_id": 256, "organization_id": 256, "trust_domain": 256,
            "audience": 256, "signer_subject_id": 256, "key_id": 256,
            "algorithm": 128, "nonce": 256, "signature": 8192,
        }
        if self.schema_version != "1.0.0":
            raise SignedEventError("unsupported signed-event schema_version")
        for name, limit in limits.items():
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise SignedEventError("invalid signed-event field")
        if not isinstance(self.signer_proof_digest, str) or not _HEX64.fullmatch(self.signer_proof_digest):
            raise SignedEventError("signer_proof_digest must be sha256 hex")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 1:
            raise SignedEventError("sequence must be a positive integer")
        if not isinstance(self.event, EventEnvelope):
            raise SignedEventError("event must be EventEnvelope v1")
        self.event.validate()
        return self

    def canonical_payload(self) -> bytes:
        self.validate()
        payload = {
            "algorithm": self.algorithm, "audience": self.audience, "event": self.event.to_dict(),
            "key_id": self.key_id, "nonce": self.nonce, "organization_id": self.organization_id,
            "schema_version": self.schema_version, "sequence": self.sequence,
            "signer_proof_digest": self.signer_proof_digest,
            "signer_subject_id": self.signer_subject_id, "tenant_id": self.tenant_id,
            "trust_domain": self.trust_domain,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class VerifiedEventEnvelope:
    signer_subject_id: str
    signer_proof_digest: str
    event_id: str
    correlation_id: str
    sequence: int
    nonce: str
    event: EventEnvelope


def verify_signed_event(
    signed: SignedEventEnvelope,
    identity: VerifiedWorkloadIdentity,
    verifier: Verifier,
    replay_guard: ReplayGuard,
) -> VerifiedEventEnvelope:
    signed.validate()
    actual = (
        signed.signer_subject_id, signed.signer_proof_digest, signed.key_id,
        signed.trust_domain, signed.tenant_id, signed.organization_id, signed.audience,
    )
    expected = (
        identity.subject_id, identity.proof_digest, identity.key_id,
        identity.trust_domain, identity.tenant_id, identity.organization_id, identity.audience,
    )
    if actual != expected:
        raise SignedEventError("signed event does not bind to verified workload identity")
    occurred = _utc(signed.event.occurred_at)
    if occurred < _utc(identity.issued_at) or occurred >= _utc(identity.expires_at):
        raise SignedEventError("event occurred outside workload identity validity")
    try:
        accepted = verifier(signed.canonical_payload(), signed.signature, signed.key_id, signed.algorithm)
    except Exception as exc:
        raise SignedEventError("signed-event verifier failed closed") from exc
    if accepted is not True:
        raise SignedEventError("signed-event signature verification failed")
    key = ReplayKey(
        signed.tenant_id, signed.signer_subject_id, signed.event.correlation_id,
        signed.sequence, signed.nonce, signed.event.event_id,
    )
    try:
        admitted = replay_guard.consume(key)
    except Exception as exc:
        raise SignedEventError("replay guard failed closed") from exc
    if admitted is not True:
        raise SignedEventError("signed event rejected as replay")
    return VerifiedEventEnvelope(
        signed.signer_subject_id, signed.signer_proof_digest, signed.event.event_id,
        signed.event.correlation_id, signed.sequence, signed.nonce, signed.event,
    )

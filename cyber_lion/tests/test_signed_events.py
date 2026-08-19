from __future__ import annotations
import dataclasses
import hashlib
import hmac
import unittest

from cyber_lion.contracts.events import Authority, EventEnvelope, Provenance
from cyber_lion.contracts.signed_events import (
    InMemoryReplayGuard, SignedEventEnvelope, SignedEventError, VerifiedEventEnvelope,
    verify_signed_event,
)
from cyber_lion.contracts.workload_identity import VerifiedWorkloadIdentity

SECRET = b"test-only-signed-event-key"
IDENTITY = VerifiedWorkloadIdentity(
    "workload:builder", "cyber-lion.test", "tenant:a", "org:a",
    "cyber-lion-control-plane", "a" * 64, "key:test",
    "2026-08-19T13:00:00Z", "2026-08-19T15:00:00Z",
)
def event(event_id="event:1", *, occurred_at="2026-08-19T14:00:00Z", payload=None):
    return EventEnvelope(
        "1.0.0", event_id, "ObservationCreated", occurred_at, "corr:1",
        {"entity_id": "service:test"}, {"kind": "unit-test"}, Provenance("OBSERVED"),
        Authority(), "UNDERSTOOD", payload or {"value": 1},
    ).validate()

def unsigned(*, sequence=1, nonce="nonce:1", wrapped=None):
    return SignedEventEnvelope(
        "1.0.0", "tenant:a", "org:a", "cyber-lion.test", "cyber-lion-control-plane",
        "workload:builder", "a" * 64, "key:test", "TEST-HMAC-SHA256",
        sequence, nonce, wrapped or event(), "pending",
    )

def signed(value=None):
    value = value or unsigned()
    signature = hmac.new(SECRET, value.canonical_payload(), hashlib.sha256).hexdigest()
    return dataclasses.replace(value, signature=signature)

def verifier(payload, signature, key_id, algorithm):
    if (key_id, algorithm) != ("key:test", "TEST-HMAC-SHA256"):
        return False
    return hmac.compare_digest(signature, hmac.new(SECRET, payload, hashlib.sha256).hexdigest())

def verify(value, guard=None, identity=IDENTITY, checker=verifier):
    return verify_signed_event(value, identity, checker, guard or InMemoryReplayGuard())
class SignedEventTests(unittest.TestCase):
    def test_valid_event_is_verified_without_authority_grant(self):
        result = verify(signed())
        self.assertIsInstance(result, VerifiedEventEnvelope)
        self.assertEqual(result.event_id, "event:1")
        self.assertFalse(hasattr(result, "authority"))
        self.assertFalse(hasattr(result, "capabilities"))

    def test_valid_wrong_identity_context_is_rejected(self):
        mutations = {
            "tenant_id": "tenant:b", "organization_id": "org:b", "trust_domain": "other.test",
            "audience": "other", "signer_subject_id": "workload:other",
            "signer_proof_digest": "b" * 64,
        }
        for field, value in mutations.items():
            with self.subTest(field=field), self.assertRaises(SignedEventError):
                verify(signed(dataclasses.replace(unsigned(), **{field: value})))

    def test_nested_event_tampering_is_rejected(self):
        base = signed()
        changed = dataclasses.replace(base.event, payload={"value": 2})
        with self.assertRaises(SignedEventError):
            verify(dataclasses.replace(base, event=changed))

    def test_verified_result_keeps_exact_immutable_signed_payload(self):
        value = signed(); expected = value.canonical_payload(); result = verify(value)
        value.event.payload["value"] = 999
        self.assertEqual(result.signed_payload, expected)
        self.assertFalse(hasattr(result, "event"))

    def test_event_time_must_fit_verified_identity_window(self):
        for when in ("2026-08-19T12:59:59Z", "2026-08-19T15:00:00Z"):
            with self.subTest(when=when), self.assertRaises(SignedEventError):
                verify(signed(unsigned(wrapped=event(occurred_at=when))))

    def test_forgery_does_not_consume_replay_key_and_exact_replay_fails(self):
        guard = InMemoryReplayGuard()
        value = signed()
        with self.assertRaises(SignedEventError):
            verify(dataclasses.replace(value, signature="0" * 64), guard)
        verify(value, guard)
        with self.assertRaises(SignedEventError):
            verify(value, guard)

    def test_nonce_event_id_and_sequence_replay_rules(self):
        guard = InMemoryReplayGuard()
        verify(signed(), guard)
        with self.assertRaises(SignedEventError):
            verify(signed(unsigned(sequence=2, nonce="nonce:1", wrapped=event("event:2"))), guard)
        guard = InMemoryReplayGuard()
        verify(signed(), guard)
        with self.assertRaises(SignedEventError):
            verify(signed(unsigned(sequence=2, nonce="nonce:2")), guard)
        guard = InMemoryReplayGuard()
        verify(signed(unsigned(sequence=2, nonce="nonce:2", wrapped=event("event:2"))), guard)
        with self.assertRaises(SignedEventError):
            verify(signed(), guard)

    def test_verifier_and_replay_guard_fail_closed(self):
        with self.assertRaises(SignedEventError):
            verify(signed(), checker=lambda *_: False)
        with self.assertRaises(SignedEventError):
            verify(signed(), checker=lambda *_: (_ for _ in ()).throw(RuntimeError("down")))
        class Broken:
            def consume(self, _): raise RuntimeError("down")
        with self.assertRaises(SignedEventError):
            verify(signed(), Broken())

    def test_wrapper_shape_matches_security_bounds(self):
        for value in (
            dataclasses.replace(unsigned(), sequence=0),
            dataclasses.replace(unsigned(), nonce="x" * 257),
            dataclasses.replace(unsigned(), signer_proof_digest="bad"),
        ):
            with self.assertRaises(SignedEventError):
                value.validate()

if __name__ == "__main__":
    unittest.main()

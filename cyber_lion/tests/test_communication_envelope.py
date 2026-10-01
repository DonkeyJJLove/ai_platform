from __future__ import annotations

from dataclasses import replace
import unittest

from cyber_lion.contracts.cognitive_invocation import InvocationIntent
from cyber_lion.contracts.communication_envelope import (
    AUTHORITY_EFFECT,
    EFFECT,
    SCHEMA_ID,
    CommunicationEnvelope,
    CommunicationEnvelopeError,
    communication_envelope_from_mapping,
)

Z = "0" * 64


def envelope(**overrides):
    values = {
        "envelope_id": "comm:001",
        "sender_ref": "operator:primary",
        "recipient_refs": ("drone:LD001", "worker:MD001"),
        "conversation_ref": "conv:001",
        "mission_ref": "M1",
        "correlation_ref": "corr:001",
        "causation_ref": "msg:parent",
        "causal_group_ref": "causal:001",
        "payload_schema_ref": "lion.operator-message/v1",
        "payload_ref": "msg:001",
        "payload_digest": Z,
        "created_at": "2026-09-29T20:30:00Z",
    }
    values.update(overrides)
    return CommunicationEnvelope.build(**values)


class CommunicationEnvelopeTests(unittest.TestCase):
    def test_sealed_round_trip_is_deterministic_and_non_effectful(self):
        first = envelope()
        second = communication_envelope_from_mapping(first.to_dict())
        self.assertEqual(first, second)
        self.assertEqual(first.schema_id, SCHEMA_ID)
        self.assertEqual(first.authority_effect, AUTHORITY_EFFECT)
        self.assertEqual(first.effect, EFFECT)
        self.assertEqual(first.envelope_digest, second.envelope_digest)
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())

    def test_recipient_set_is_unique_frozen_and_canonical(self):
        normalized = envelope(recipient_refs=("worker:MD001", "drone:LD001"))
        self.assertEqual(normalized.recipient_refs, ("drone:LD001", "worker:MD001"))
        with self.assertRaisesRegex(CommunicationEnvelopeError, "unique"):
            envelope(recipient_refs=("drone:LD001", "drone:LD001"))
        raw = normalized.to_dict()
        raw["recipient_refs"] = ["worker:MD001", "drone:LD001"]
        with self.assertRaisesRegex(CommunicationEnvelopeError, "canonical sorted"):
            communication_envelope_from_mapping(raw)

    def test_payload_causation_or_recipient_substitution_breaks_digest(self):
        valid = envelope()
        mutations = (
            replace(valid, payload_digest="1" * 64),
            replace(valid, causation_ref="msg:other"),
            replace(valid, recipient_refs=("drone:LD001",)),
        )
        for changed in mutations:
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(CommunicationEnvelopeError, "digest mismatch"):
                    changed.validate()

    def test_authority_effect_delivery_and_transport_cannot_be_smuggled(self):
        valid = envelope()
        with self.assertRaisesRegex(CommunicationEnvelopeError, "mint authority"):
            replace(valid, authority_effect="WRITE").validate()
        with self.assertRaisesRegex(CommunicationEnvelopeError, "report an effect"):
            replace(valid, effect="DELIVERED").validate()
        for extra in ("delivery_state", "transport_state", "cognition_state", "runtime_admission"):
            raw = valid.to_dict()
            raw[extra] = "READY"
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(CommunicationEnvelopeError, "fields are not exact"):
                    communication_envelope_from_mapping(raw)

    def test_payload_content_is_not_part_of_envelope_contract(self):
        keys = set(envelope().to_dict())
        self.assertNotIn("payload", keys)
        self.assertNotIn("content", keys)
        self.assertIn("payload_ref", keys)
        self.assertIn("payload_digest", keys)

    def test_cognitive_invocation_may_bind_envelope_without_collapsing_dual_legs(self):
        comm = envelope(causal_group_ref="causal:dual")
        local = InvocationIntent(
            "inv:local", "parent:1", comm.envelope_id, comm.payload_digest,
            "binding:local", Z, "LOCAL", "route:1", "PLANNING",
            "2026-09-29T21:00:00Z", comm.causal_group_ref,
        ).validate()
        saas = InvocationIntent(
            "inv:saas", "parent:1", comm.envelope_id, comm.payload_digest,
            "binding:saas", Z, "SAAS", "route:1", "PLANNING",
            "2026-09-29T21:00:00Z", comm.causal_group_ref,
        ).validate()
        self.assertEqual(local.message_ref, comm.envelope_id)
        self.assertEqual(saas.message_ref, comm.envelope_id)
        self.assertEqual(local.payload_digest, comm.payload_digest)
        self.assertEqual(saas.payload_digest, comm.payload_digest)
        self.assertNotEqual(local.invocation_id, saas.invocation_id)
        self.assertEqual(local.causal_group_ref, saas.causal_group_ref)

    def test_invalid_timestamp_and_self_causation_fail_closed(self):
        with self.assertRaises(CommunicationEnvelopeError):
            envelope(created_at="2026-09-29T20:30:00+02:00")
        with self.assertRaisesRegex(CommunicationEnvelopeError, "self-causation"):
            envelope(envelope_id="msg:self", causation_ref="msg:self")


if __name__ == "__main__":
    unittest.main()

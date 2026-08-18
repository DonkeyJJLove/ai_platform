import unittest

from cyber_lion.contracts.events import (
    Authority,
    EventEnvelope,
    EventValidationError,
    Provenance,
)


def event(event_type, *, provenance=None, authority=None, payload=None):
    return EventEnvelope(
        schema_version="1.0.0",
        event_id=f"event:{event_type}",
        event_type=event_type,
        occurred_at="2026-08-18T14:00:00Z",
        correlation_id="corr:test",
        entity={"entity_id": "service:test"},
        source={"kind": "unit-test"},
        provenance=provenance or Provenance("OBSERVED"),
        authority=authority or Authority(),
        epistemic_state="UNDERSTOOD",
        payload=payload or {},
    )


class EventInvariantTests(unittest.TestCase):
    def test_derived_event_requires_upstream(self):
        with self.assertRaises(EventValidationError):
            event(
                "HypothesisGenerated",
                provenance=Provenance("DERIVED"),
            ).validate()

    def test_consequential_action_requires_applied_gate(self):
        with self.assertRaises(EventValidationError):
            event(
                "ActionExecuted",
                authority=Authority(requested="execute", effective="execute"),
                payload={"consequential": True},
            ).validate()

    def test_consequential_action_with_gate_is_valid(self):
        value = event(
            "ActionExecuted",
            authority=Authority(
                requested="execute",
                effective="execute",
                policy_ids=["policy:tool-exec"],
                gate_event_id="gate:123",
            ),
            payload={"consequential": True},
        ).validate()
        self.assertEqual(value.authority.gate_event_id, "gate:123")

    def test_non_consequential_observation_does_not_need_gate(self):
        value = event("ObservationCreated").validate()
        self.assertEqual(value.event_type, "ObservationCreated")

    def test_memory_commit_requires_policy_provenance_and_candidate(self):
        with self.assertRaises(EventValidationError):
            event("MemoryCommitted").validate()

        value = event(
            "MemoryCommitted",
            provenance=Provenance("DERIVED", upstream=["event:memory-candidate"]),
            authority=Authority(
                requested="memory.write",
                effective="memory.write",
                policy_ids=["policy:memory"],
                gate_event_id="gate:memory",
            ),
            payload={"candidate_event_id": "event:memory-candidate"},
        ).validate()
        self.assertEqual(value.payload["candidate_event_id"], "event:memory-candidate")

    def test_authority_degraded_must_change_effective_authority(self):
        with self.assertRaises(EventValidationError):
            event(
                "AuthorityDegraded",
                authority=Authority(requested="execute", effective="execute"),
            ).validate()


if __name__ == "__main__":
    unittest.main()

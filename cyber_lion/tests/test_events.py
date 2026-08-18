import unittest
from cyber_lion.contracts.events import Authority,EventEnvelope,EventValidationError,Provenance

def make_event(event_type,*,provenance=None,authority=None,payload=None):
    return EventEnvelope("1.0.0",f"event:{event_type}",event_type,"2026-08-18T14:00:00Z","corr:test",{"entity_id":"service:test"},{"kind":"unit-test"},provenance or Provenance("OBSERVED"),authority or Authority(),"UNDERSTOOD",payload or {})

class EventTests(unittest.TestCase):
    def test_derived_requires_upstream(self):
        with self.assertRaises(EventValidationError): make_event("HypothesisGenerated",provenance=Provenance("DERIVED")).validate()
    def test_action_requires_gate(self):
        with self.assertRaises(EventValidationError): make_event("ActionExecuted",authority=Authority("execute","execute"),payload={"consequential":True}).validate()
    def test_action_with_gate(self):
        self.assertEqual(make_event("ActionExecuted",authority=Authority("execute","execute",["policy:x"],"gate:1"),payload={"consequential":True}).validate().authority.gate_event_id,"gate:1")
    def test_memory_commit_requires_policy_provenance_candidate(self):
        with self.assertRaises(EventValidationError): make_event("MemoryCommitted").validate()
        value=make_event("MemoryCommitted",provenance=Provenance("DERIVED",["event:candidate"]),authority=Authority("memory.write","memory.write",["policy:memory"],"gate:memory"),payload={"candidate_event_id":"event:candidate"}).validate()
        self.assertEqual(value.payload["candidate_event_id"],"event:candidate")
    def test_authority_degraded_must_change(self):
        with self.assertRaises(EventValidationError): make_event("AuthorityDegraded",authority=Authority("execute","execute")).validate()

if __name__=="__main__": unittest.main()

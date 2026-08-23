from __future__ import annotations
import unittest
from cyber_lion.contracts.events import Authority,EventEnvelope,Provenance
from cyber_lion.enterprise import event_to_graph_records

def ev(*,causation=None,gate=None):
 return EventEnvelope("1.0.0","x","DecisionProposed","2026-01-01T00:00:00Z","corr",{"entity_id":"a","entity_type":"agent","version":"v1"},{"component":"t"},Provenance("DERIVED",["up"],["t"],None),Authority("none","none",["p"] if gate else [],gate),"FORMALISED",{"k":"v"},causation).validate()

class EventGraphProjectionTests(unittest.TestCase):
 def test_correlation_alone_does_not_create_causal_edge(self):
  nodes,edges=event_to_graph_records(ev());self.assertTrue(nodes);self.assertFalse(any(e.edge_type in {"CAUSED_BY","CORRELATED_WITH"} for e in edges))
 def test_explicit_causation_creates_evidence_bound_edge(self):
  nodes,edges=event_to_graph_records(ev(causation="parent"));causes=[e for e in edges if e.edge_type=="CAUSED_BY"];self.assertEqual(1,len(causes));self.assertEqual("parent",causes[0].causality_evidence_ref)
 def test_authority_metadata_is_reference_only(self):
  nodes,edges=event_to_graph_records(ev(gate="gate-1"));auth=[n for n in nodes if n.node_type=="AUTHORITY_RECORD"];self.assertEqual(1,len(auth));self.assertFalse(auth[0].payload["authoritative"]);self.assertTrue(any(e.plane=="AUTHORITY_REFERENCE" for e in edges))
if __name__=="__main__":unittest.main()

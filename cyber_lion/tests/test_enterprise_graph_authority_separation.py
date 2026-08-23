from __future__ import annotations
from datetime import datetime,timezone
import tempfile,unittest
from cyber_lion.contracts.agent_registry import AgentSpecKey
from cyber_lion.contracts.enterprise_graph import EnterpriseGraphError,GraphEdge,GraphNode
from cyber_lion.enterprise import EnterpriseGraphStore,agent_node_from_registry_key

def clock():return datetime(2026,1,1,tzinfo=timezone.utc)

class EnterpriseGraphAuthoritySeparationTests(unittest.TestCase):
 def test_agent_identity_consumes_registry_key(self):
  key=AgentSpecKey("agent-a","v2","a"*64).validate();n=agent_node_from_registry_key(key);self.assertEqual("AGENT",n.node_type);self.assertEqual("AgentRegistry",n.payload["identity_source"]);self.assertEqual("a"*64,n.payload["spec_digest"])
 def test_authority_edge_cannot_exist_in_data_plane(self):
  with self.assertRaises(EnterpriseGraphError):GraphEdge("e","DATA_PROVENANCE","AUTHORITY_REFERENCED_BY","a","b").validate()
 def test_authority_path_is_reference_only(self):
  with tempfile.TemporaryDirectory() as t:
   g=EnterpriseGraphStore(t+"/g.sqlite",graph_id="g",clock=clock)
   try:
    g.add_node(GraphNode("auth","AUTHORITY_RECORD","1",{"authoritative":False}).validate(),operation_id="n1",evidence_refs=("e",));g.add_node(GraphNode("event","ENTITY","1",{}).validate(),operation_id="n2",evidence_refs=("e",));g.add_edge(GraphEdge("ar","AUTHORITY_REFERENCE","AUTHORITY_REFERENCED_BY","auth","event",("e",)).validate(),operation_id="e1",evidence_refs=("e",));p=g.authority_reference_path("auth","event");self.assertEqual("AUTHORITY_REFERENCE",p.plane);self.assertEqual(("ar",),p.edge_ids)
    with self.assertRaises(Exception):g.find_path("auth","event",plane="DATA_PROVENANCE")
   finally:g.close()
if __name__=="__main__":unittest.main()

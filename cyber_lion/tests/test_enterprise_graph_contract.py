from __future__ import annotations
import unittest
from cyber_lion.contracts.enterprise_graph import EnterpriseGraphError,EnterpriseGraphProjection,GraphEdge,GraphNode,canonical_json
from hashlib import sha256

class EnterpriseGraphContractTests(unittest.TestCase):
 def test_planes_and_causality_are_strict(self):
  with self.assertRaises(EnterpriseGraphError):GraphEdge("e","DATA_PROVENANCE","AUTHORITY_PARENT_OF","a","b").validate()
  with self.assertRaises(EnterpriseGraphError):GraphEdge("e","DATA_PROVENANCE","CAUSED_BY","a","b").validate()
  with self.assertRaises(EnterpriseGraphError):GraphEdge("e","DATA_PROVENANCE","CAUSED_BY","a","b",(),"ev").validate()
  self.assertEqual("CAUSED_BY",GraphEdge("e","DATA_PROVENANCE","CAUSED_BY","a","b",("ev",),"ev").validate().edge_type)
 def test_unknown_types_fail_closed(self):
  with self.assertRaises(EnterpriseGraphError):GraphNode("n","UNKNOWN","1",{}).validate()
  with self.assertRaises(EnterpriseGraphError):GraphEdge("e","UNKNOWN","SUPPORTS","a","b").validate()
 def test_projection_digest_is_logical_state_digest(self):
  n=GraphNode("n","ENTITY","1",{}).validate();logical={"graph_id":"g","nodes":[{"node_id":"n","node_type":"ENTITY","version":"1","payload":{},"provenance_refs":[]}],"edges":[]};dg=sha256(canonical_json(logical)).hexdigest();p=EnterpriseGraphProjection("g",9,"0"*64,(n,),(),dg);self.assertIs(p,p.verify_digest())
  with self.assertRaises(EnterpriseGraphError):EnterpriseGraphProjection("g",9,"0"*64,(n,),(),"1"*64).verify_digest()
if __name__=="__main__":unittest.main()

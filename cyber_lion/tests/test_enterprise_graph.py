from __future__ import annotations
from datetime import datetime,timezone
import sqlite3,tempfile,unittest
from cyber_lion.contracts.enterprise_graph import GraphEdge,GraphNode
from cyber_lion.enterprise import EnterpriseGraphStateError,EnterpriseGraphStore

def clock():return datetime(2026,1,1,tzinfo=timezone.utc)
def node(i,t="ENTITY"):return GraphNode(i,t,"1",{"i":i},("evidence",)).validate()
def edge(i,a,b,t="SUPPORTS"):return GraphEdge(i,"DATA_PROVENANCE",t,a,b,("evidence",)).validate()

class EnterpriseGraphStoreTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.db=self.t.name+"/g.sqlite";self.g=EnterpriseGraphStore(self.db,graph_id="g",clock=clock)
 def tearDown(self):self.g.close();self.t.cleanup()
 def test_restart_replay_and_path(self):
  a=self.g.add_node(node("a"),operation_id="n1",evidence_refs=("e",));self.assertEqual(a,self.g.add_node(node("a"),operation_id="n1",evidence_refs=("e",)))
  self.g.add_node(node("b"),operation_id="n2",evidence_refs=("e",));self.g.add_edge(edge("e1","a","b"),operation_id="e1",evidence_refs=("e",));p1=self.g.projection();self.assertEqual(("a","b"),self.g.find_path("a","b",plane="DATA_PROVENANCE").node_ids)
  self.g.close();self.g=EnterpriseGraphStore(self.db,graph_id="g",clock=clock);self.assertEqual(p1,self.g.projection())
 def test_replay_substitution_and_dangling_denied(self):
  self.g.add_node(node("a"),operation_id="op",evidence_refs=("e",))
  with self.assertRaises(EnterpriseGraphStateError):self.g.add_node(node("b"),operation_id="op",evidence_refs=("e",))
  with self.assertRaises(EnterpriseGraphStateError):self.g.add_edge(edge("x","a","missing"),operation_id="x",evidence_refs=("e",))
 def test_same_logical_graph_different_insert_order_same_digest(self):
  for i in ("a","b","c"):self.g.add_node(node(i),operation_id="n"+i,evidence_refs=("e",))
  self.g.add_edge(edge("e1","a","b"),operation_id="e1",evidence_refs=("e",));self.g.add_edge(edge("e2","b","c"),operation_id="e2",evidence_refs=("e",));d1=self.g.projection().projection_digest
  other=self.t.name+"/h.sqlite";h=EnterpriseGraphStore(other,graph_id="g",clock=clock)
  try:
   for i in ("c","a","b"):h.add_node(node(i),operation_id="x"+i,evidence_refs=("e",))
   h.add_edge(edge("e2","b","c"),operation_id="y2",evidence_refs=("e",));h.add_edge(edge("e1","a","b"),operation_id="y1",evidence_refs=("e",));self.assertEqual(d1,h.projection().projection_digest)
  finally:h.close()
 def test_event_corruption_denies_restart(self):
  self.g.add_node(node("a"),operation_id="n",evidence_refs=("e",));self.g.close();c=sqlite3.connect(self.db);c.execute("DROP TRIGGER graph_event_no_update");c.execute("UPDATE enterprise_graph_event SET payload_json='{}' WHERE seq=1");c.commit();c.close()
  with self.assertRaises(EnterpriseGraphStateError):EnterpriseGraphStore(self.db,graph_id="g",clock=clock)
  self.g=EnterpriseGraphStore.__new__(EnterpriseGraphStore);self.g.c=sqlite3.connect(":memory:")
 def test_self_edge_denied(self):
  self.g.add_node(node("a"),operation_id="n",evidence_refs=("e",))
  with self.assertRaises(EnterpriseGraphStateError):self.g.add_edge(edge("e","a","a"),operation_id="e",evidence_refs=("e",))
if __name__=="__main__":unittest.main()

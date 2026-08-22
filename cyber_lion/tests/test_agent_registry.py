from __future__ import annotations
from datetime import datetime,timezone
import tempfile,unittest
from cyber_lion.enterprise import AgentRegistryStateError,AgentRegistryStore,AgentSpec,MissionSpec

def spec(v="v1",cap=("research",)):return AgentSpec("a",v,"role","mission",cap)
def clock():return datetime(2026,1,1,tzinfo=timezone.utc)
class RegistryTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.db=self.t.name+"/r.sqlite";self.r=AgentRegistryStore(self.db,registry_id="r1",clock=clock)
 def tearDown(self):self.r.close();self.t.cleanup()
 def test_supersession_and_replay(self):
  k=self.r.register_spec(spec(),operation_id="o1",evidence_refs=("e",));self.assertEqual(k,self.r.register_spec(spec(),operation_id="o1",evidence_refs=("e",)))
  k2=self.r.supersede_spec(spec("v2"),expected_version="v1",expected_digest=k.spec_digest,operation_id="o2",evidence_refs=("e2",));self.assertEqual("v2",k2.version)
  with self.assertRaises(AgentRegistryStateError):self.r.supersede_spec(spec("v1"),expected_version="v2",expected_digest=k2.spec_digest,operation_id="o3",evidence_refs=("e3",))
 def test_terminal_revocation(self):
  k=self.r.register_spec(spec(),operation_id="o1",evidence_refs=("e",));i=self.r.register_instance(instance_id="i",agent_id="a",spec_version="v1",spec_digest=k.spec_digest,operation_id="o2",evidence_refs=("e",));self.r.transition_instance("i","ACTIVE",operation_id="o3",evidence_refs=("e",));self.r.transition_instance("i","REVOKED",operation_id="o4",evidence_refs=("e",))
  with self.assertRaises(AgentRegistryStateError):self.r.transition_instance("i","ACTIVE",operation_id="o5",evidence_refs=("e",))
 def test_projection_restart_stable(self):
  self.r.register_spec(spec(),operation_id="o1",evidence_refs=("e",));m=MissionSpec("m","p",("research",));p1=self.r.resolve_for_mission(m);self.r.close();self.r=AgentRegistryStore(self.db,registry_id="r1",clock=clock);p2=self.r.resolve_for_mission(m);self.assertEqual(p1,p2)
 def test_replay_substitution_denied(self):
  self.r.register_spec(spec(),operation_id="o1",evidence_refs=("e",))
  with self.assertRaises(AgentRegistryStateError):self.r.register_spec(AgentSpec("b","v1","r","m",("x",)),operation_id="o1",evidence_refs=("e",))
if __name__=="__main__":unittest.main()

from __future__ import annotations
from dataclasses import asdict
from hashlib import sha256
import unittest
from cyber_lion.contracts.agent_registry import AgentRegistryProjection,canonical_json
from cyber_lion.enterprise import AgentSpec,EnterpriseModelError,MissionSpec,MosaicDelta,SwarmPlanner

def agent(agent_id,capabilities,authority="read",cost=1.0,verifier=False):
 events=("DecisionProposed","OutcomeObserved") if authority not in {"none","read"} else ()
 return AgentSpec(agent_id,"1.0.0",agent_id,"mission-bound template",capabilities,authority,"test",events,max_cost_units=cost,is_verifier=verifier)
def projection(mission,catalog):
 specs=[]
 verifier_required=mission.require_independent_verifier or mission.risk_class=="RED" or mission.authority_ceiling in {"external_write","privileged","deploy"}
 for s in sorted(catalog,key=lambda x:(x.agent_id,x.version)):
  d=asdict(s)
  for k,v in list(d.items()):
   if isinstance(v,tuple):d[k]=list(v)
  if set(s.capabilities)&set(mission.required_capabilities) or (verifier_required and s.is_verifier):specs.append(d)
 p={"registry_id":"r","revision":1,"event_head":"0"*64,"mission_id":mission.mission_id,"required_capabilities":list(mission.required_capabilities),"candidate_specs":specs};dg=sha256(canonical_json(p)).hexdigest();return AgentRegistryProjection("r",1,"0"*64,mission.mission_id,mission.required_capabilities,tuple(specs),dg).verify_digest()
class SwarmPlannerTests(unittest.TestCase):
 def setUp(self):
  self.p=SwarmPlanner();self.c=[agent("research",("research","hypothesis"),cost=.6),agent("architect",("architecture","code"),"local_write",.8),agent("security",("security","validation"),cost=.7,verifier=True),agent("code-only",("code",),"local_write",.5)]
 def test_minimal_mosaic_preserved(self):
  m=MissionSpec("m1","design",("research","architecture","code","security","validation"),"local_write","AMBER",4,max_total_cost_units=4);s=self.p.plan(m,projection(m,self.c));self.assertEqual(set(s.member_agent_ids),{"research","architect","security"})
 def test_missing_capability_fails(self):
  m=MissionSpec("m2","missing",("research","financial.audit"))
  with self.assertRaises(EnterpriseModelError):self.p.plan(m,projection(m,self.c))
 def test_red_requires_verifier(self):
  m=MissionSpec("red","change",("architecture","code"),"deploy","RED",3)
  with self.assertRaises(EnterpriseModelError):self.p.plan(m,projection(m,[x for x in self.c if not x.is_verifier]))
  self.assertTrue(self.p.plan(m,projection(m,self.c)).verifier_agent_ids)
 def test_ambient_list_rejected(self):
  m=MissionSpec("m","p",("research",))
  with self.assertRaises((AttributeError,EnterpriseModelError)):self.p.plan(m,self.c)
class MosaicDeltaTests(unittest.TestCase):
 def test_authority_expansion_requires_gate(self):
  with self.assertRaises(EnterpriseModelError):MosaicDelta("d","s",authority_before="read",authority_after="external_write",reason="r",evidence_refs=("e",)).validate()
if __name__=="__main__":unittest.main()

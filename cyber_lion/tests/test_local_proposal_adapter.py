import unittest,json
from cyber_lion.app_coordination.hybrid_routing import *
from cyber_lion.app_coordination.local_proposal_adapter import *
D=lambda c:c*64
class T(unittest.TestCase):
 def setUp(self):
  p=HybridRoutingPolicy("r8","1",D('a'),D('b')).validate();m=ModelProfile(D('a'),D('b'),"ACTIVE",p.local_classes,4096,1);self.t=TaskEnvelope("t","TEST_CASE_PROPOSAL","MODEL",D('c'),100);self.d=route_task(self.t,p,m)
 def test_valid(self):
  x=materialize_local_proposal(self.t,self.d,lambda t,n:'{"proposal":"x"}',token_counter=lambda t:90);self.assertEqual(x.attempts,1);self.assertEqual((x.authority_effect,x.runtime_effect),("NONE","NONE"))
 def test_repair_once(self):
  vals=iter(['bad','{"proposal":"x"}']);x=materialize_local_proposal(self.t,self.d,lambda t,n:next(vals),token_counter=lambda t:90);self.assertEqual(x.attempts,2)
 def test_failed_repair(self):
  with self.assertRaises(Exception):materialize_local_proposal(self.t,self.d,lambda t,n:'bad',token_counter=lambda t:90)
 def test_nonlocal(self):
  with self.assertRaises(ValueError):materialize_local_proposal(self.t,replace_decision(self.d),lambda t,n:'{"proposal":"x"}',token_counter=lambda t:90)
 def test_measured_over_envelope(self):
  with self.assertRaises(ValueError):materialize_local_proposal(self.t,self.d,lambda t,n:'{"proposal":"x"}',token_counter=lambda t:101)
 def test_schema(self):
  with self.assertRaises(Exception):materialize_local_proposal(self.t,self.d,lambda t,n:'{"x":"y"}',token_counter=lambda t:90)
 def test_provider_required(self):
  with self.assertRaises(ValueError):materialize_local_proposal(self.t,self.d,None,token_counter=lambda t:90)
def replace_decision(d): return RouteDecision("SAAS",d.reason,d.policy_digest,d.task_id)
if __name__=='__main__':unittest.main()

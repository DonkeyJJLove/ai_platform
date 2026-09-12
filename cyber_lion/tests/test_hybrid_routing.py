import unittest
from dataclasses import replace
from cyber_lion.app_coordination.hybrid_routing import *
D=lambda c:c*64
class T(unittest.TestCase):
 def setUp(self):
  self.p=HybridRoutingPolicy("r8","1",D('a'),D('b')).validate();self.m=ModelProfile(D('a'),D('b'),"ACTIVE",self.p.local_classes,4096,1).validate();self.t=TaskEnvelope("t","TEST_CASE_PROPOSAL","MODEL",D('c'),100)
 def test_local(self):self.assertEqual(route_task(self.t,self.p,self.m).route,"LOCAL")
 def test_queue(self):self.assertEqual(route_task(self.t,self.p,self.m,active_local_inferences=1).route,"QUEUE")
 def test_inactive(self):self.assertEqual(route_task(self.t,self.p,replace(self.m,runtime_state="INACTIVE")).route,"SAAS")
 def test_overflow(self):self.assertEqual(route_task(replace(self.t,input_tokens=5000),self.p,self.m).route,"SAAS")
 def test_authority(self):self.assertEqual(route_task(replace(self.t,authority_bound=True),self.p,self.m).route,"SAAS")
 def test_sensitive(self):self.assertEqual(route_task(replace(self.t,task_class="CURRENTNESS_BIND"),self.p,self.m).route,"SAAS")
 def test_deterministic(self):self.assertEqual(route_task(replace(self.t,operation_class="DETERMINISTIC_TEST"),self.p,self.m).route,"DETERMINISTIC")
 def test_no_egress(self):self.assertEqual(route_task(replace(self.t,task_class="FIELD_EXTRACTION",data_may_leave_host=False),self.p,self.m).route,"DEFER")
 def test_substitution(self):
  with self.assertRaises(ValueError):route_task(self.t,self.p,replace(self.m,model_digest=D('d')))
 def test_policy_no_authority(self):
  with self.assertRaises(ValueError):replace(self.p,authority_effect="ALLOW").validate()
 def test_profile_exact_limit(self):self.assertEqual(route_task(replace(self.t,input_tokens=4096),self.p,self.m).route,"LOCAL")
 def test_cross_module_saas(self):self.assertEqual(route_task(replace(self.t,task_class="CROSS_MODULE_DIAGNOSIS"),self.p,self.m).route,"SAAS")
 def test_digest_stable(self):self.assertEqual(self.p.digest(),self.p.digest())
 def test_decision_effect_free(self):self.assertEqual((route_task(self.t,self.p,self.m).authority_effect,route_task(self.t,self.p,self.m).runtime_effect),("NONE","NONE"))
if __name__=='__main__':unittest.main()

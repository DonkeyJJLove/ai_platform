import unittest
from dataclasses import replace
from cyber_lion.app_coordination.hybrid_routing import *
D=lambda c:c*64
class T(unittest.TestCase):
 def setUp(self):self.p=HybridRoutingPolicy('r8','1',D('a'),D('b'));self.m=ModelProfile(D('a'),D('b'),'ACTIVE',self.p.local_classes,4096,1);self.t=TaskEnvelope('x','TEST_CASE_PROPOSAL','MODEL',D('c'),100)
 def test_local_shadow(self):self.assertEqual(route_task(self.t,self.p,self.m).route,'LOCAL')
 def test_complex_shadow(self):self.assertEqual(route_task(replace(self.t,task_class='CROSS_MODULE_DIAGNOSIS'),self.p,self.m).route,'SAAS')
 def test_test_shadow(self):self.assertEqual(route_task(replace(self.t,operation_class='DETERMINISTIC_TEST'),self.p,self.m).route,'DETERMINISTIC')
 def test_queue_shadow(self):self.assertEqual(route_task(self.t,self.p,self.m,active_local_inferences=1).route,'QUEUE')
 def test_inactive_real_state(self):self.assertEqual(route_task(self.t,self.p,replace(self.m,runtime_state='INACTIVE')).route,'SAAS')
 def test_overflow_shadow(self):self.assertEqual(route_task(replace(self.t,input_tokens=4097),self.p,self.m).route,'SAAS')
if __name__=='__main__':unittest.main()

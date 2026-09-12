import unittest
from cyber_lion.app_coordination.test_placement import *
class T(unittest.TestCase):
 def s(self,**kw):return TestSpec(kw.pop('test_id','x'),kw.pop('tier','T1'),kw.pop('source_digest','a'*64),kw.pop('environment_digest','b'*64),**kw)
 def test_t1(self):self.assertEqual(plan_test(self.s()).executor_class,"LOCAL_DETERMINISTIC")
 def test_t5(self):self.assertEqual(plan_test(self.s(tier='T5')).executor_class,"REMOTE_EXACT_HEAD")
 def test_t6(self):self.assertEqual(plan_test(self.s(tier='T6')).executor_class,"AUTHORITY_BOUND")
 def test_currentness_no_cache(self):self.assertIsNone(plan_test(self.s(currentness_sensitive=True)).cache_key)
 def test_exclusive_serial(self):self.assertEqual(plan_test(self.s(exclusive_store='db')).parallelism,1)
 def test_heavy_serial(self):self.assertEqual(plan_test(self.s(heavy=True)).parallelism,1)
 def test_unqualified(self):self.assertEqual(plan_test(self.s(),environment_qualified=False).executor_class,"DEFER")
 def test_env_changes_key(self):self.assertNotEqual(plan_test(self.s()).cache_key,plan_test(self.s(environment_digest='c'*64)).cache_key)
 def test_same_key(self):self.assertEqual(plan_test(self.s()).cache_key,plan_test(self.s()).cache_key)
if __name__=='__main__':unittest.main()

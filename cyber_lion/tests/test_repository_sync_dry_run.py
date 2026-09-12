import unittest
from cyber_lion.app_coordination.repository_sync import *
R=('r'*40,'t'*40)
class T(unittest.TestCase):
 def o(self,id='a',**kw):return RepositoryObservation(id,'x/y',kw.pop('head','r'*40),kw.pop('tree','t'*40),kw.pop('dirty',False),kw.pop('storage_identity',id),kw.pop('runtime_bound',False))
 def one(self,o):return plan_sync((o,),{'x/y':R})[0]
 def test_exact(self):self.assertEqual(self.one(self.o()).action,'NO_ACTION')
 def test_dirty(self):self.assertEqual(self.one(self.o(dirty=True)).action,'PRESERVE_DIRTY')
 def test_runtime(self):self.assertEqual(self.one(self.o(runtime_bound=True)).action,'PRESERVE_RUNTIME_BOUND')
 def test_diverged(self):self.assertEqual(self.one(self.o(head='x'*40)).action,'RECONCILE_ANCESTRY')
 def test_same_head_diff_tree(self):self.assertEqual(self.one(self.o(tree='x'*40)).action,'BLOCK')
 def test_alias(self):self.assertEqual(plan_sync((self.o('a',storage_identity='s'),self.o('b',storage_identity='s')),{'x/y':R})[1].action,'ALIAS_NO_ACTION')
 def test_unknown_remote(self):self.assertEqual(plan_sync((self.o(),),{})[0].action,'DEFER')
 def test_effect_free(self):self.assertTrue(all(x.effect=='NONE' for x in plan_sync((self.o(),),{'x/y':R})))
if __name__=='__main__':unittest.main()

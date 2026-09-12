from pathlib import Path
import unittest
from tools.lion_workflow_homeostasis import audit
ROOT=Path(__file__).resolve().parents[2]
class CoreWorkflowHomeostasisTests(unittest.TestCase):
 def test_core_queues_without_cancelling_evidence(self):
  t=(ROOT/'.github/workflows/cyber-lion-contracts.yml').read_text();self.assertIn('concurrency:',t);self.assertIn('cancel-in-progress: false',t)
 def test_core_existing_exact_synthetic_merge_binding_remains_recognized(self):
  r=audit(ROOT);w=next(x for x in r['workflows'] if x['name']=='cyber-lion-contracts.yml');self.assertTrue(w['explicit_head_tree_binding']);self.assertEqual(w['advisory_findings'],[])
 def test_permissions_not_widened(self):
  t=(ROOT/'.github/workflows/cyber-lion-contracts.yml').read_text();self.assertIn('permissions:\n  contents: read',t)
if __name__=='__main__':unittest.main()

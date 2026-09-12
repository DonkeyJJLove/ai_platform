from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'.github/workflows/fleet-effect-budget-r1.yml'
class FleetEffectBudgetWorkflowHardeningTests(unittest.TestCase):
 def text(self): return P.read_text(encoding='utf-8')
 def test_permissions_and_triggers_preserved(self):
  t=self.text();self.assertIn('permissions:\n  contents: read',t);self.assertIn('push:',t);self.assertIn('pull_request:',t);self.assertNotIn('contents: write',t)
 def test_exact_checkout_and_no_persisted_credentials(self):
  t=self.text();self.assertIn('ref: ${{ github.event.pull_request.head.sha || github.sha }}',t);self.assertIn('fetch-depth: 0',t);self.assertIn('persist-credentials: false',t);self.assertIn('EXPECTED_HEAD: ${{ github.event.pull_request.head.sha || github.sha }}',t);self.assertIn('test "$ACTUAL" = "$EXPECTED_HEAD"',t);self.assertIn('git rev-parse HEAD^{tree}',t)
 def test_bounded_queue_preserves_every_invocation(self):
  t=self.text();self.assertIn('timeout-minutes: 15',t);self.assertIn('concurrency:',t);self.assertIn('cancel-in-progress: false',t)
 def test_terminal_still_declares_no_effect(self):
  t=self.text();self.assertIn("echo 'AUTHORITY_ISSUED=NO'",t);self.assertIn("echo 'LAB_MUTATED=NO'",t);self.assertIn("echo 'MERGE_ATTEMPTED=NO'",t)
if __name__=='__main__':unittest.main()

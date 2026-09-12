from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'.github/workflows/lion-code-perception-observation.yml'
class CodePerceptionWorkflowHardeningTests(unittest.TestCase):
 def text(self): return P.read_text(encoding='utf-8')
 def test_observer_implementation_and_observed_target_are_separate(self):
  t=self.text();self.assertIn('ref: ${{ github.sha }}',t);self.assertIn('EXPECTED_IMPLEMENTATION_HEAD: ${{ github.sha }}',t);self.assertIn('EXPECTED_HEAD: ${{ inputs.expected_head }}',t);self.assertNotIn('ref: ${{ inputs.expected_head }}',t)
 def test_observer_checkout_is_exact_and_noncredentialed(self):
  t=self.text();self.assertIn('persist-credentials: false',t);self.assertIn('implementation_head="$(git rev-parse HEAD)"',t);self.assertIn("implementation_tree=\"$(git rev-parse 'HEAD^{tree}')\"",t);self.assertIn('test "$implementation_head" = "$EXPECTED_IMPLEMENTATION_HEAD"',t)
 def test_observation_permissions_and_effect_semantics_preserved(self):
  t=self.text();self.assertIn('permissions:\n  contents: read\n  actions: read',t);self.assertNotIn('contents: write',t);self.assertIn('observe_exact_projection',t);self.assertIn('authority_effect=',t)
 def test_bounded_queue_does_not_cancel_observations(self):
  t=self.text();self.assertIn('timeout-minutes: 15',t);self.assertIn('concurrency:',t);self.assertIn('cancel-in-progress: false',t)
if __name__=='__main__':unittest.main()

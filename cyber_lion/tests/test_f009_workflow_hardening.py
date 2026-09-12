from pathlib import Path
import unittest
from tools.lion_workflow_homeostasis import audit
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'.github/workflows/f009-live-runtime-proof.yml'
class F009WorkflowHardeningTests(unittest.TestCase):
 def text(self):return P.read_text(encoding='utf-8')
 def test_live_proof_class_and_no_control_findings(self):
  r=audit(ROOT);w=next(x for x in r['workflows'] if x['name']=='f009-live-runtime-proof.yml');self.assertEqual(w['workflow_class'],'LIVE_PROOF');self.assertEqual(w['advisory_findings'],[])
 def test_exact_head_tree_and_noncredentialed_checkout(self):
  t=self.text();self.assertIn('persist-credentials: false',t);self.assertIn('EXPECTED_HEAD: ${{ github.event.pull_request.head.sha || github.sha }}',t);self.assertIn('actual_head="$(git rev-parse HEAD)"',t);self.assertIn("actual_tree=\"$(git rev-parse 'HEAD^{tree}')\"",t);self.assertIn('test "$actual_head" = "$EXPECTED_HEAD"',t)
 def test_concurrency_queues_and_does_not_cancel_live_proofs(self):
  t=self.text();self.assertIn('concurrency:',t);self.assertIn('cancel-in-progress: false',t);self.assertIn('timeout-minutes: 10',t)
 def test_proof_artifact_set_is_digest_bound(self):
  t=self.text();self.assertIn('Digest immutable proof evidence set',t);self.assertIn('F009_PROOF_MANIFEST_SHA256',t);self.assertIn('F009_ARTIFACT_SET_SHA256',t);self.assertIn('artifact-set.sha256',t)
 def test_production_effect_and_independent_observation_guards_preserved(self):
  t=self.text();self.assertIn('manifest["production_effect"] is False',t);self.assertIn('independent_effect_digest',t);self.assertIn('observer_pid',t);self.assertIn('runtime_has_signing_secret',t)
if __name__=='__main__':unittest.main()

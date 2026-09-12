from pathlib import Path
import re, unittest
ROOT=Path(__file__).resolve().parents[2]
FILES=("f005-branch-ownership-registry-ci.yml","f005-repository-observation-source-ci.yml")
class F005CIWorkflowHardeningTests(unittest.TestCase):
    def text(self,name): return (ROOT/'.github/workflows'/name).read_text(encoding='utf-8')
    def test_read_only_permissions_preserved(self):
        for name in FILES:
            t=self.text(name)
            self.assertIn('permissions:\n  contents: read',t)
            self.assertNotRegex(t,r'(?m)^\s+(contents|actions|pull-requests|issues|checks|deployments): write$')
    def test_checkout_identity_is_exact_and_credentials_not_persisted(self):
        for name in FILES:
            t=self.text(name)
            self.assertIn('ref: ${{ github.event.pull_request.head.sha || github.sha }}',t)
            self.assertIn('persist-credentials: false',t)
            self.assertIn('EXPECTED_HEAD: ${{ github.event.pull_request.head.sha || github.sha }}',t)
            self.assertIn('git rev-parse HEAD',t)
            self.assertIn("git rev-parse 'HEAD^{tree}'",t)
            self.assertIn('test "$actual_head" = "$EXPECTED_HEAD"',t)
    def test_bounded_and_concurrent_without_trigger_change(self):
        for name in FILES:
            t=self.text(name)
            self.assertIn('timeout-minutes: 10',t)
            self.assertIn('concurrency:',t)
            self.assertIn('cancel-in-progress: true',t)
            self.assertIn('pull_request:',t); self.assertIn('workflow_dispatch:',t)
    def test_no_runtime_or_effect_invocation_added(self):
        a=self.text(FILES[0]); b=self.text(FILES[1])
        self.assertNotIn('fleet_repository_observation_runtime',a)
        # existing second workflow may mention module only in a negative grep construction, never execute it
        self.assertNotRegex(b,r'(?m)^\s+python -m cyber_lion\.enterprise\.fleet_repository_observation_runtime\s*$')
if __name__=='__main__': unittest.main()

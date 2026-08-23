from __future__ import annotations

from pathlib import Path
import unittest


WORKFLOW = Path('.github/workflows/f009-live-runtime-proof.yml')


class LiveRuntimeWorkflowContractTests(unittest.TestCase):
    def text(self) -> str:
        return WORKFLOW.read_text(encoding='utf-8')

    def test_workflow_has_manual_and_pr_triggers(self):
        text = self.text()
        self.assertIn('workflow_dispatch:', text)
        self.assertIn('pull_request:', text)
        self.assertIn('runs-on: ubuntu-24.04', text)

    def test_permissions_are_read_only_and_no_deployment_surface(self):
        text = self.text()
        self.assertIn('permissions:\n  contents: read', text)
        self.assertNotIn('contents: write', text)
        self.assertNotIn('deploy', text.lower())
        self.assertNotIn('environment:', text)
        self.assertNotIn('secrets.', text)

    def test_positive_proof_uses_runner_temp_and_integrated_module(self):
        text = self.text()
        self.assertIn('$RUNNER_TEMP/f009-live-work-', text)
        self.assertIn('$RUNNER_TEMP/f009-live-artifacts-', text)
        self.assertIn('python -m cyber_lion.enterprise.live_runtime_evidence_plane', text)
        self.assertIn('actions/upload-artifact@v4', text)
        self.assertIn('Cleanup disposable proof plane', text)

    def test_workflow_does_not_reactivate_f005(self):
        text = self.text().lower()
        self.assertNotIn('f005-runtime-', text)
        self.assertNotIn('fleet_runtime', text)
        self.assertNotIn('repository_mutation', text)

    def test_exact_authorized_paths_only(self):
        expected = {
            'cyber_lion/enterprise/live_runtime_evidence_plane.py',
            'cyber_lion/tests/test_live_runtime_evidence_plane.py',
            'cyber_lion/tests/test_live_runtime_evidence_workflow_contract.py',
            '.github/workflows/f009-live-runtime-proof.yml',
        }
        text = self.text()
        for path in expected:
            self.assertIn(path, text)


if __name__ == '__main__':
    unittest.main()

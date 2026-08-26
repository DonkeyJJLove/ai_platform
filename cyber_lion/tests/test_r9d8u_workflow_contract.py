from pathlib import Path
import unittest


class R9D8UWorkflowContractTests(unittest.TestCase):
    def test_production_workflow_uses_mediated_entrypoint_and_trust_client(self):
        text = Path('.github/workflows/lion-repository-maintenance-sandbox.yml').read_text(encoding='utf-8')
        self.assertIn('runs-on: [self-hosted, linux, lion-trust-client]', text)
        self.assertIn('repository_maintenance_mediated_cleanup', text)
        self.assertIn('LION_MAINTENANCE_BUNDLE_URL', text)
        self.assertIn('LION_MAINTENANCE_RUNTIME_MODULE_DIGEST', text)
        self.assertIn('LION_REPOSITORY_DELETE_FENCE_DATABASE_PATH', text)
        self.assertNotIn('repository_maintenance_cleanup \\', text)
        self.assertNotIn('LION-BRANCH-CLEANUP v1', text)
        self.assertIn('LION-REPOSITORY-REF-DELETE v2', text)


if __name__ == '__main__':
    unittest.main()

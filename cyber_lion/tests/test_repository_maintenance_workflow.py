from pathlib import Path
import unittest


class RepositoryMaintenanceWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (
            Path(__file__).resolve().parents[2]
            / ".github"
            / "workflows"
            / "lion-repository-maintenance-sandbox.yml"
        ).read_text(encoding="utf-8")

    def test_issue_comment_trigger_is_bounded_request_evidence_and_owner_validation_is_runtime_step(self):
        self.assertIn("issue_comment:", self.workflow)
        self.assertIn("github.event.issue.number == 144", self.workflow)
        self.assertIn(
            "startsWith(github.event.comment.body, 'LION-REPOSITORY-REF-DELETE v2')",
            self.workflow,
        )
        self.assertIn("Validate repository-owner request actor", self.workflow)
        self.assertIn("actor.get('login') != owner.get('login')", self.workflow)
        self.assertNotIn("github.event.comment.user.login == github.repository_owner", self.workflow)
        self.assertNotIn("LION-BRANCH-CLEANUP v1", self.workflow)

    def test_permissions_and_receipts_are_bounded(self):
        self.assertIn("contents: write", self.workflow)
        self.assertIn("pull-requests: read", self.workflow)
        self.assertIn("issues: write", self.workflow)
        self.assertEqual(
            self.workflow.count("python -m cyber_lion.enterprise.repository_maintenance_receipt"),
            2,
        )
        self.assertIn("--kind failure", self.workflow)
        self.assertIn("--kind observation", self.workflow)
        self.assertIn("--event \"$GITHUB_EVENT_PATH\"", self.workflow)
        self.assertIn("--checked-out-sha \"$GITHUB_SHA\"", self.workflow)
        self.assertNotIn("urllib.request", self.workflow)
        self.assertNotIn("urlopen", self.workflow)
        self.assertNotIn("method='POST'", self.workflow)

    def test_execution_is_fixed_canonical_mediator_not_arbitrary_shell_input(self):
        self.assertIn(
            "python -m cyber_lion.enterprise.repository_maintenance_mediated_cleanup",
            self.workflow,
        )
        self.assertIn("--execute-exact-request", self.workflow)
        self.assertIn("ref: master", self.workflow)
        self.assertIn("runs-on: [self-hosted, linux, lion-trust-client]", self.workflow)
        self.assertIn("LION_MAINTENANCE_BUNDLE_URL", self.workflow)
        self.assertIn("LION_REPOSITORY_DELETE_FENCE_DATABASE_PATH", self.workflow)
        self.assertNotIn(
            "python -m cyber_lion.enterprise.repository_maintenance_cleanup",
            self.workflow,
        )
        self.assertNotIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("repository_dispatch:", self.workflow)


if __name__ == "__main__":
    unittest.main()

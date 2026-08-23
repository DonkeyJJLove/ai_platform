from __future__ import annotations

from pathlib import Path
import unittest


WORKFLOW = Path(".github/workflows/f009-live-runtime-proof.yml")


class LiveRuntimeWorkflowContractR2Tests(unittest.TestCase):
    def text(self) -> str:
        return WORKFLOW.read_text(encoding="utf-8")

    def test_triggers_runner_and_read_only_permissions(self):
        text = self.text()
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("pull_request:", text)
        self.assertIn("runs-on: ubuntu-24.04", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("environment:", text)
        self.assertNotIn("secrets.", text)

    def test_pre_runtime_authority_bootstrap_is_separate_and_private_key_is_destroyed(self):
        text = self.text()
        bootstrap = text.index("Bootstrap immutable authority control inputs")
        runtime = text.index("Run F009 live runtime proof")
        self.assertLess(bootstrap, runtime)
        self.assertIn("openssl genpkey -algorithm ED25519", text)
        self.assertIn("openssl pkeyutl -sign -rawin", text)
        self.assertIn('rm -f \\\n            "$CONTROL_DIR/authority-private.pem"', text)
        self.assertIn('test ! -e "$CONTROL_DIR/authority-private.pem"', text)
        self.assertIn("F009_AUTHORITY_BUNDLE_DIGEST", text)
        self.assertIn("F009_PROVIDER_TRUST_DIGEST", text)

    def test_runtime_consumes_control_dir_and_exact_head(self):
        text = self.text()
        self.assertIn('ref: ${{ github.event.pull_request.head.sha || github.sha }}', text)
        self.assertIn('test "$(git rev-parse HEAD)" = "$CANDIDATE_SHA"', text)
        self.assertIn('--control-dir "$CONTROL_DIR"', text)
        self.assertIn('test ! -e "$CONTROL_DIR/authority-private.pem"', text)

    def test_workflow_does_not_reactivate_f005_or_target_repository_effect(self):
        text = self.text().lower()
        self.assertNotIn("f005-runtime-", text)
        self.assertNotIn("fleet_runtime", text)
        self.assertNotIn("repository_mutation", text)

    def test_exact_authorized_paths_only(self):
        text = self.text()
        for path in {
            "cyber_lion/enterprise/live_runtime_evidence_plane.py",
            "cyber_lion/tests/test_live_runtime_evidence_plane.py",
            "cyber_lion/tests/test_live_runtime_evidence_workflow_contract.py",
            ".github/workflows/f009-live-runtime-proof.yml",
        }:
            self.assertIn(path, text)


if __name__ == "__main__":
    unittest.main()

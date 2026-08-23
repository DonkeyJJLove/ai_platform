from pathlib import Path
import unittest


WORKFLOW = Path('.github/workflows/lion-actions-dispatch-bridge.yml')


class ActionsControlFailureReceiptWorkflowTests(unittest.TestCase):
    def test_failure_receipt_is_fail_closed_and_bounded(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('LION-DISPATCH v1', text)
        self.assertIn('LION-OBSERVE v1', text)
        self.assertIn('LION-ACTIONS-CONTROL-FAILURE v1', text)
        self.assertIn('result=FAILED_CLOSED', text)
        self.assertIn('receipt_is_evidence_not_authority=true', text)
        self.assertIn('issues/144/comments', text)
        self.assertIn('GITHUB_RUN_ID', text)
        self.assertIn('GITHUB_RUN_ATTEMPT', text)
        self.assertIn('GITHUB_SHA', text)
        self.assertIn('control_comment_id=', text)
        self.assertIn('exit_code=', text)
        self.assertIn('[:500]', text)
        self.assertIn('[REDACTED]', text)
        self.assertIn('exit "$rc"', text)

    def test_failure_path_does_not_expand_effect_surface(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('contents: read', text)
        self.assertIn('actions: write', text)
        self.assertIn('issues: write', text)
        self.assertNotIn('contents: write', text)
        self.assertNotIn('pull_request_target', text)
        self.assertNotIn('gh workflow run', text)
        self.assertNotIn('printenv', text)
        self.assertNotIn('env |', text)
        self.assertNotIn('f005-runtime', text.lower())

    def test_bridge_is_executed_once_before_failure_receipt(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        needle = 'python -m cyber_lion.enterprise.actions_dispatch_bridge'
        self.assertEqual(text.count(needle), 1)
        self.assertIn('rc=$?', text)
        self.assertIn('if [ "$rc" -eq 0 ]', text)


if __name__ == '__main__':
    unittest.main()

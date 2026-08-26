from pathlib import Path
import unittest


WORKFLOW = Path('.github/workflows/lion-actions-dispatch-bridge.yml')
FAILURE_BOUNDARY = Path('cyber_lion/enterprise/actions_failure_receipt.py')


class ActionsControlFailureReceiptWorkflowTests(unittest.TestCase):
    def test_failure_receipt_is_fail_closed_and_bounded(self):
        workflow = WORKFLOW.read_text(encoding='utf-8')
        boundary = FAILURE_BOUNDARY.read_text(encoding='utf-8')
        self.assertIn('LION-DISPATCH v1', workflow)
        self.assertIn('LION-OBSERVE v1', workflow)
        self.assertIn('python -m cyber_lion.enterprise.actions_failure_receipt', workflow)
        self.assertIn('LION-ACTIONS-CONTROL-FAILURE v2', boundary)
        self.assertIn('result=FAILED_CLOSED', boundary)
        self.assertIn('receipt_is_evidence_not_authority=true', boundary)
        self.assertIn('issues/{CONTROL_ISSUE}/comments', boundary)
        self.assertIn('workflow_run_id', boundary)
        self.assertIn('workflow_run_attempt', boundary)
        self.assertIn('checked_out_sha', boundary)
        self.assertIn('control_comment_id', boundary)
        self.assertIn('exit_code', boundary)
        self.assertIn('[:500]', boundary)
        self.assertIn('[REDACTED]', boundary)
        self.assertIn('exit "$rc"', workflow)
        self.assertNotIn('urllib.request', workflow)
        self.assertNotIn('urlopen(', workflow)

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
        shim = 'python -m cyber_lion.enterprise.actions_dispatch_temporal_compat'
        direct = 'python -m cyber_lion.enterprise.actions_dispatch_bridge'
        failure = 'python -m cyber_lion.enterprise.actions_failure_receipt'
        self.assertEqual(text.count(shim), 1)
        self.assertEqual(text.count(failure), 1)
        self.assertNotIn(direct, text)
        self.assertIn('rc=$?', text)
        self.assertIn('if [ "$rc" -eq 0 ]', text)
        self.assertLess(text.index(shim), text.index(failure))

    def test_dispatch_bridge_is_bound_to_trusted_moon_execution_context(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('runs-on: [self-hosted, linux, lion-trust-client]', text)
        self.assertNotIn('runs-on: ubuntu-24.04', text)
        self.assertIn('test "$RUNNER_NAME" = "lion-moon-r9d8-test"', text)
        self.assertIn(
            'LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_PATH: '
            '/opt/lion/trusted-runtime/workflow-dispatch-test/runtime_provider.py',
            text,
        )
        self.assertIn(
            'LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_DIGEST: '
            'ef2dc1c79ed368dded5a2725bedb6e97e3c0b76f1d736f037f43fc739ea6a080',
            text,
        )
        self.assertIn(
            'LION_WORKFLOW_DISPATCH_FENCE_DATABASE_PATH: '
            '/var/lib/lion/fence/workflow-dispatch.sqlite',
            text,
        )
        self.assertIn('sha256sum "$LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_PATH"', text)
        self.assertIn('test -w "$(dirname "$LION_WORKFLOW_DISPATCH_FENCE_DATABASE_PATH")"', text)
        self.assertIn('"$GITHUB_WORKSPACE"/*) exit 1 ;;', text)


if __name__ == '__main__':
    unittest.main()

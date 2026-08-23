from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.actions_dispatch_bridge import DispatchPolicy
from cyber_lion.enterprise.actions_dispatch_bridge import (
    DEFAULT_POLICY,
    PREFIX,
    execute,
    parse_envelope,
)


HEAD = "100c454e19b31de066c263117b5bb82e3b11feab"
REPO = "DonkeyJJLove/ai_platform"


def envelope(*, workflow="f009-live-runtime-proof.yml", ref="master", expected_head=HEAD, request_id="req-1", inputs="{}") -> str:
    return "\n".join((
        PREFIX,
        f"workflow={workflow}",
        f"ref={ref}",
        f"expected_head={expected_head}",
        f"request_id={request_id}",
        f"inputs={inputs}",
    ))


def event(body: str, *, issue=144, comment_id=9001, actor="DonkeyJJLove", action="created") -> dict:
    return {
        "action": action,
        "issue": {"number": issue},
        "comment": {"id": comment_id, "body": body, "user": {"login": actor}},
        "repository": {"full_name": REPO},
    }


class FakeApi:
    def __init__(self, *, permission="admin", heads=None, comments=None, dispatch_status=True, workflow_exists=True):
        self.repository = REPO
        self.permission = permission
        self.heads = list(heads or [HEAD, HEAD])
        self.comments = list(comments or [])
        self.dispatch_status = dispatch_status
        self.workflow_present = workflow_exists
        self.claims: list[tuple[int, str]] = []
        self.patches: list[tuple[int, str]] = []
        self.dispatched: list[tuple[str, str, dict]] = []

    def actor_permission(self, actor): return self.permission
    def ref_head(self, ref): return self.heads.pop(0) if self.heads else HEAD
    def workflow_exists(self, workflow, sha): return self.workflow_present
    def issue_comments(self, issue_number): return self.comments
    def post_issue_comment(self, issue_number, body):
        self.claims.append((issue_number, body)); return 777
    def patch_issue_comment(self, comment_id, body): self.patches.append((comment_id, body))
    def dispatch(self, workflow, ref, inputs):
        if not self.dispatch_status: raise RuntimeError("dispatch failed")
        self.dispatched.append((workflow, ref, inputs))


class DispatchBridgeTests(unittest.TestCase):
    def test_positive_exact_request_dispatches_once(self):
        api = FakeApi()
        receipt = execute(event(envelope()), api)
        self.assertEqual(receipt.expected_head, HEAD)
        self.assertEqual(receipt.github_api_result, "ACCEPTED_204")
        self.assertEqual(api.dispatched, [("f009-live-runtime-proof.yml", "master", {})])
        self.assertEqual(len(api.claims), 1)
        self.assertEqual(len(api.patches), 1)
        self.assertIn("LION-DISPATCH-RECEIPT v1", api.patches[0][1])

    def test_untrusted_actor_denied_before_claim(self):
        api = FakeApi(permission="read")
        with self.assertRaisesRegex(RuntimeError, "untrusted"):
            execute(event(envelope(), actor="outsider"), api)
        self.assertFalse(api.claims)
        self.assertFalse(api.dispatched)

    def test_wrong_issue_denied(self):
        api = FakeApi()
        with self.assertRaisesRegex(RuntimeError, "wrong control issue"):
            execute(event(envelope(), issue=145), api)
        self.assertFalse(api.dispatched)

    def test_malformed_envelope_denied(self):
        with self.assertRaises(ValueError):
            parse_envelope("LION-DISPATCH v2", repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")

    def test_workflow_substitution_and_f005_are_denied(self):
        for workflow in ("release.yml", "../evil.yml", "f005-runtime-reconciliation-ingestion.yml"):
            with self.subTest(workflow=workflow):
                with self.assertRaises(ValueError):
                    parse_envelope(envelope(workflow=workflow), repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")

    def test_ref_substitution_denied(self):
        for ref in ("dev", "refs/heads/master", "../master"):
            with self.subTest(ref=ref):
                with self.assertRaises(ValueError):
                    parse_envelope(envelope(ref=ref), repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")

    def test_stale_expected_head_denied_before_claim(self):
        api = FakeApi(heads=["1" * 40])
        with self.assertRaisesRegex(RuntimeError, "stale expected head"):
            execute(event(envelope()), api)
        self.assertFalse(api.claims)

    def test_head_toctou_denied_after_claim_without_dispatch(self):
        api = FakeApi(heads=[HEAD, "2" * 40])
        with self.assertRaisesRegex(RuntimeError, "ref moved"):
            execute(event(envelope()), api)
        self.assertEqual(len(api.claims), 1)
        self.assertFalse(api.dispatched)
        self.assertIn("DENIED_HEAD_MOVED_BEFORE_DISPATCH", api.patches[-1][1])

    def test_inputs_must_be_canonical_and_known(self):
        for inputs in ('{"x":1}', '{ "x": 1 }', '[]', '{not-json}'):
            with self.subTest(inputs=inputs):
                with self.assertRaises(ValueError):
                    parse_envelope(envelope(inputs=inputs), repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")

    def test_shell_metacharacters_cannot_enter_control_fields(self):
        for request_id in ("x;rm", "$(id)", "x y", "x\nworkflow=evil.yml"):
            with self.subTest(request_id=request_id):
                with self.assertRaises(ValueError):
                    parse_envelope(envelope(request_id=request_id), repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")

    def test_replay_key_or_request_id_denied(self):
        req = parse_envelope(envelope(request_id="replay-1"), repository=REPO, issue_number=144, comment_id=9001, actor="DonkeyJJLove")
        existing = {"body": "\n".join((
            "LION-DISPATCH-RECEIPT v1",
            "request_id=replay-1",
            f"replay_key={req.replay_key()}",
        ))}
        api = FakeApi(comments=[existing])
        with self.assertRaisesRegex(RuntimeError, "consumed"):
            execute(event(envelope(request_id="replay-1")), api)
        self.assertFalse(api.dispatched)

    def test_same_request_id_different_payload_is_denied(self):
        existing = {"body": "LION-DISPATCH-CLAIM v1\nrequest_id=same-id\nreplay_key=" + "a" * 64}
        api = FakeApi(comments=[existing])
        with self.assertRaisesRegex(RuntimeError, "request-id-already-consumed"):
            execute(event(envelope(request_id="same-id")), api)

    def test_api_failure_consumes_claim_fail_closed(self):
        api = FakeApi(dispatch_status=False)
        with self.assertRaisesRegex(RuntimeError, "dispatch failed"):
            execute(event(envelope()), api)
        self.assertEqual(len(api.claims), 1)
        self.assertFalse(api.dispatched)
        self.assertIn("DISPATCH_API_FAILED_REQUEST_CONSUMED", api.patches[-1][1])

    def test_workflow_contract_is_narrow(self):
        text = Path(".github/workflows/lion-actions-dispatch-bridge.yml").read_text(encoding="utf-8")
        self.assertIn("issue_comment:", text)
        self.assertIn("types: [created]", text)
        self.assertIn("actions: write", text)
        self.assertIn("issues: write", text)
        self.assertIn("contents: read", text)
        self.assertIn("github.event.issue.number == 144", text)
        self.assertIn("startsWith(github.event.comment.body, 'LION-DISPATCH v1')", text)
        self.assertIn("concurrency:", text)
        self.assertNotIn("pull_request_target", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("gh workflow run", text)
        self.assertNotIn("contents: write", text)

    def test_policy_does_not_accept_status_governor_role_or_graph_as_authority(self):
        policy = asdict(DEFAULT_POLICY)
        rendered = json.dumps(policy, sort_keys=True).lower()
        for forbidden in ("status", "governor", "formation", "mosaic", "enterprisegraph"):
            self.assertNotIn(forbidden, rendered)


if __name__ == "__main__":
    unittest.main()

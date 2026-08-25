from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request

from cyber_lion.enterprise.actions_failure_receipt import (
    FailureReceiptAdmission,
    FailureReceiptError,
    GitHubFailureReceiptBoundary,
    _bounded_diagnostic,
)

REPO = "DonkeyJJLove/ai_platform"
SHA = "e" * 40


def event(*, issue=144, body="LION-DISPATCH v1\nworkflow=x", comment_id=9001, repo=REPO):
    return {
        "action": "created",
        "issue": {"number": issue},
        "comment": {"id": comment_id, "body": body, "user": {"login": "DonkeyJJLove"}},
        "repository": {"full_name": repo},
    }


def admission(**overrides):
    values = dict(
        event=event(), repository=REPO, workflow_run_id=123, workflow_run_attempt=1,
        checked_out_sha=SHA, exit_code=2, diagnostic="failed closed",
    )
    values.update(overrides)
    return FailureReceiptAdmission.from_event(**values)


class _Response:
    def __init__(self, status: int, value: object):
        self.status = status
        self._data = json.dumps(value).encode("utf-8")
    def read(self): return self._data
    def __enter__(self): return self
    def __exit__(self, *args): return False


class _Boundary(GitHubFailureReceiptBoundary):
    def __init__(self):
        super().__init__()
        self.requests: list[Request] = []
        self.created_body = None
    def _open(self, request: Request):
        self.requests.append(request)
        if request.get_method() == "POST":
            payload = json.loads(request.data.decode("utf-8"))
            self.created_body = payload["body"]
            return _Response(201, {"id": 777, "body": self.created_body})
        return _Response(200, {"id": 777, "body": self.created_body})


class FailureReceiptBoundaryTests(unittest.TestCase):
    def test_admission_binds_external_event_run_and_sha(self):
        value = admission()
        self.assertEqual(value.repository, REPO)
        self.assertEqual(value.issue_number, 144)
        self.assertEqual(value.control_comment_id, 9001)
        self.assertEqual(value.command, "DISPATCH")
        self.assertEqual(value.workflow_run_id, 123)
        self.assertEqual(value.checked_out_sha, SHA)
        self.assertIn("result=FAILED_CLOSED", value.receipt_body)
        self.assertIn("receipt_is_evidence_not_authority=true", value.receipt_body)

    def test_observe_command_is_exact(self):
        value = admission(event=event(body="LION-OBSERVE v1\nrequest_id=x"))
        self.assertEqual(value.command, "OBSERVE")

    def test_wrong_issue_repository_or_nonfailure_denied(self):
        for kwargs in (
            {"event": event(issue=145)},
            {"event": event(repo="Other/repo")},
            {"exit_code": 0},
            {"checked_out_sha": "not-a-sha"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(FailureReceiptError):
                admission(**kwargs)

    def test_arbitrary_comment_is_denied(self):
        with self.assertRaises(FailureReceiptError):
            admission(event=event(body="hello"))

    def test_boundary_has_closed_world_post_and_readback(self):
        gate = admission()
        boundary = _Boundary()
        observed = boundary.post(gate, token="token")
        self.assertTrue(observed.observed)
        self.assertEqual(observed.comment_id, 777)
        self.assertEqual(len(boundary.requests), 2)
        post, readback = boundary.requests
        self.assertEqual(post.get_method(), "POST")
        self.assertEqual(post.full_url, f"https://api.github.com/repos/{REPO}/issues/144/comments")
        self.assertEqual(readback.get_method(), "GET")
        self.assertEqual(readback.full_url, f"https://api.github.com/repos/{REPO}/issues/comments/777")

    def test_admission_replay_denied_before_second_post(self):
        gate = admission()
        boundary = _Boundary()
        boundary.post(gate, token="token")
        with self.assertRaises(FailureReceiptError):
            boundary.post(gate, token="token")
        self.assertEqual(len(boundary.requests), 2)

    def test_diagnostic_is_bounded_and_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            err = Path(tmp) / "err"
            out.write_text("unused", encoding="utf-8")
            err.write_text("Bearer abc.def token=secret-value\n", encoding="utf-8")
            value = _bounded_diagnostic(err, out)
            self.assertNotIn("abc.def", value)
            self.assertNotIn("secret-value", value)
            self.assertLessEqual(len(value), 500)

    def test_workflow_no_longer_contains_inline_network_write(self):
        path = Path(".github/workflows/lion-actions-dispatch-bridge.yml")
        text = path.read_text(encoding="utf-8")
        self.assertIn("cyber_lion.enterprise.actions_failure_receipt", text)
        self.assertNotIn("urllib.request", text)
        self.assertNotIn("urlopen(", text)


if __name__ == "__main__":
    unittest.main()

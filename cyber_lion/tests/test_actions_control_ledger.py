from __future__ import annotations

import inspect
import json
import unittest
from unittest.mock import patch

from cyber_lion.enterprise import actions_control_ledger as ledger
from cyber_lion.enterprise.actions_dispatch_bridge import GitHubApi

REPO = "DonkeyJJLove/ai_platform"
CLAIM = "\n".join((
    "LION-DISPATCH-CLAIM v1",
    "request_id=req-r9d7",
    "replay_key=" + "a" * 64,
    "payload_digest=" + "b" * 64,
    "comment_id=9001",
    "actor=DonkeyJJLove",
    "permission=admin",
    "workflow=f009-live-runtime-proof.yml",
    "ref=master",
    "expected_head=" + "c" * 40,
    "state=CLAIMED_BEFORE_EFFECT",
))


class _Response:
    def __init__(self, status: int, value: object):
        self.status = status
        self.headers = {}
        self.raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    def read(self, size=-1):
        return self.raw if size < 0 else self.raw[:size]
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False


class _Opener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def open(self, request, timeout=None):
        self.calls.append((request, timeout))
        if not self.responses:
            raise AssertionError("unexpected network call")
        return self.responses.pop(0)


class ActionsControlLedgerTests(unittest.TestCase):
    def test_github_api_generic_transport_cannot_write_issue_comments(self):
        source = inspect.getsource(GitHubApi)
        self.assertIn('generic GitHub transport is read-only', source)
        api = GitHubApi(REPO, "token")
        with self.assertRaisesRegex(RuntimeError, "read-only"):
            api._request("POST", f"/repos/{REPO}/issues/144/comments", {"body": CLAIM})
        with self.assertRaisesRegex(RuntimeError, "read-only"):
            api._request("PATCH", f"/repos/{REPO}/issues/comments/1", {"body": CLAIM})

    def test_create_is_exact_issue_bound_replay_checked_and_read_back(self):
        created = {"id": 777, "body": CLAIM}
        # durable ledger GET, POST, exact read-back GET
        opener = _Opener([
            _Response(200, []),
            _Response(201, created),
            _Response(200, created),
        ])
        with patch("urllib.request.build_opener", return_value=opener):
            boundary = ledger.ActionsControlLedgerBoundary(REPO, "token")
            comment_id = boundary.create(144, CLAIM)
        self.assertEqual(comment_id, 777)
        methods = [request.get_method() for request, _ in opener.calls]
        self.assertEqual(methods, ["GET", "POST", "GET"])
        self.assertEqual(opener.calls[1][0].full_url, f"https://api.github.com/repos/{REPO}/issues/144/comments")

    def test_durable_replay_denied_before_post(self):
        existing = {"id": 1, "body": CLAIM}
        opener = _Opener([_Response(200, [existing])])
        with patch("urllib.request.build_opener", return_value=opener):
            boundary = ledger.ActionsControlLedgerBoundary(REPO, "token")
            with self.assertRaisesRegex(ledger.ActionsControlLedgerError, "replay"):
                boundary.create(144, CLAIM)
        self.assertEqual([r.get_method() for r, _ in opener.calls], ["GET"])

    def test_target_and_body_substitution_are_denied_before_network(self):
        opener = _Opener([])
        with patch("urllib.request.build_opener", return_value=opener):
            boundary = ledger.ActionsControlLedgerBoundary(REPO, "token")
            with self.assertRaises(ledger.ActionsControlLedgerError):
                boundary.create(145, CLAIM)
            with self.assertRaises(ledger.ActionsControlLedgerError):
                boundary.create(144, "attacker body")
        self.assertEqual(opener.calls, [])

    def test_update_requires_exact_boundary_created_comment_and_readback(self):
        receipt = CLAIM.replace("LION-DISPATCH-CLAIM v1", "LION-DISPATCH-RECEIPT v1")
        created = {"id": 777, "body": CLAIM}
        updated = {"id": 777, "body": receipt}
        opener = _Opener([
            _Response(200, []), _Response(201, created), _Response(200, created),
            _Response(200, updated), _Response(200, updated),
        ])
        with patch("urllib.request.build_opener", return_value=opener):
            boundary = ledger.ActionsControlLedgerBoundary(REPO, "token")
            boundary.create(144, CLAIM)
            boundary.update(777, receipt)
        self.assertEqual([r.get_method() for r, _ in opener.calls], ["GET", "POST", "GET", "PATCH", "GET"])

        with patch("urllib.request.build_opener", return_value=_Opener([])):
            boundary = ledger.ActionsControlLedgerBoundary(REPO, "token")
            with self.assertRaisesRegex(ledger.ActionsControlLedgerError, "not created"):
                boundary.update(777, receipt)

    def test_selected_boundary_has_no_workflow_dispatch_or_ref_mutation_surface(self):
        source = inspect.getsource(ledger)
        self.assertNotIn("/dispatches", source)
        self.assertNotIn("git/refs", source)
        self.assertNotIn('method="DELETE"', source)
        self.assertNotIn('method="PUT"', source)


if __name__ == "__main__":
    unittest.main()

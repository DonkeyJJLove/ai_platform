from datetime import datetime, timedelta, timezone
import unittest

from cyber_lion.contracts.actions_dispatch_bridge import DispatchReceipt
from cyber_lion.enterprise.actions_dispatch_temporal_compat import (
    LEGACY_LOOKBACK_SECONDS,
    _matching_runs_compat,
    _wait_terminal_diagnostic,
)


HEAD = "a" * 40


def receipt() -> DispatchReceipt:
    return DispatchReceipt(
        schema_version="1.0.0",
        request_id="req-1",
        control_comment_id=1,
        actor="DonkeyJJLove",
        permission="admin",
        workflow="f009-live-runtime-proof.yml",
        ref="master",
        expected_head=HEAD,
        canonical_inputs_digest="1" * 64,
        accepted_at="2026-08-23T17:24:55+00:00",
        replay_key="2" * 64,
        bridge_implementation_digest="3" * 64,
        trust_decision="ALLOW",
        github_api_result="ACCEPTED_204",
    ).validate()


def run(created_at: str, *, run_id=10, event="workflow_dispatch", branch="master", head=HEAD):
    return {"id": run_id, "created_at": created_at, "event": event, "head_branch": branch, "head_sha": head}


class _TerminalApi:
    def __init__(self, value: dict):
        self.value = value

    def workflow_run(self, run_id: int) -> dict:
        return dict(self.value)


class TemporalCompatibilityTests(unittest.TestCase):
    def test_exact_run_created_just_before_receipt_is_accepted(self):
        matches = _matching_runs_compat([run("2026-08-23T17:24:54Z")], receipt())
        self.assertEqual([item["id"] for item in matches], [10])

    def test_run_older_than_bounded_lookback_is_rejected(self):
        accepted = datetime(2026, 8, 23, 17, 24, 55, tzinfo=timezone.utc)
        old = accepted - timedelta(seconds=LEGACY_LOOKBACK_SECONDS + 1)
        matches = _matching_runs_compat([run(old.isoformat())], receipt())
        self.assertEqual(matches, [])

    def test_exact_event_branch_head_remain_mandatory(self):
        runs = [
            run("2026-08-23T17:24:54Z", run_id=1, event="pull_request"),
            run("2026-08-23T17:24:54Z", run_id=2, branch="dev"),
            run("2026-08-23T17:24:54Z", run_id=3, head="b" * 40),
        ]
        self.assertEqual(_matching_runs_compat(runs, receipt()), [])

    def test_multiple_exact_candidates_remain_visible_for_fail_closed_ambiguity(self):
        matches = _matching_runs_compat([
            run("2026-08-23T17:24:54Z", run_id=11),
            run("2026-08-23T17:24:56Z", run_id=12),
        ], receipt())
        self.assertEqual([item["id"] for item in matches], [11, 12])

    def test_failed_terminal_run_exposes_exact_non_success_identity(self):
        api = _TerminalApi({
            "id": 77,
            "event": "workflow_dispatch",
            "head_branch": "master",
            "head_sha": HEAD,
            "status": "completed",
            "conclusion": "failure",
        })
        with self.assertRaisesRegex(
            RuntimeError,
            r"run_id=77 .*head=" + HEAD + r" .*conclusion=failure",
        ):
            _wait_terminal_diagnostic(api, 77, timeout_seconds=0, poll_seconds=0)

    def test_successful_terminal_run_is_semantically_unchanged(self):
        value = {
            "id": 78,
            "event": "workflow_dispatch",
            "head_branch": "master",
            "head_sha": HEAD,
            "status": "completed",
            "conclusion": "success",
        }
        self.assertEqual(
            _wait_terminal_diagnostic(_TerminalApi(value), 78, timeout_seconds=0, poll_seconds=0),
            value,
        )


if __name__ == "__main__":
    unittest.main()

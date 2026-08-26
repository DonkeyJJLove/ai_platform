from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.enterprise.repository_maintenance_receipt import (
    GitHubMaintenanceReceiptBoundary,
    MaintenanceReceiptAdmission,
    RepositoryMaintenanceReceiptError,
)

REPOSITORY = "DonkeyJJLove/ai_platform"
SHA = "a" * 40


def _event() -> dict:
    return {
        "action": "created",
        "issue": {"number": 144},
        "comment": {"id": 991, "body": "LION-BRANCH-CLEANUP v1"},
        "repository": {"full_name": REPOSITORY},
    }


class _Response:
    def __init__(self, status: int, payload: object):
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Opener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def open(self, request, timeout=None):
        self.calls.append((request, timeout))
        if not self.responses:
            raise AssertionError("unexpected network call")
        return self.responses.pop(0)


class RepositoryMaintenanceReceiptTests(unittest.TestCase):
    def test_failure_receipt_is_exact_replay_bound_and_read_back(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = root / "event.json"
            stderr_path = root / "stderr.txt"
            event_path.write_text(json.dumps(_event()), encoding="utf-8")
            stderr_path.write_text("Authorization: Bearer secret\nboom\n", encoding="utf-8")
            admission = MaintenanceReceiptAdmission.failure(
                event_path=event_path,
                repository=REPOSITORY,
                workflow_run_id=123,
                workflow_run_attempt=1,
                checked_out_sha=SHA,
                exit_code=2,
                stderr_path=stderr_path,
            )
            self.assertIn("result=FAILED_CLOSED", admission.receipt_body)
            self.assertIn("receipt_is_evidence_not_authority=true", admission.receipt_body)
            self.assertNotIn("secret", admission.receipt_body)
            created = {"id": 555, "body": admission.receipt_body}
            opener = _Opener([
                _Response(200, []),
                _Response(201, created),
                _Response(200, created),
            ])
            with patch("urllib.request.build_opener", return_value=opener):
                observation = GitHubMaintenanceReceiptBoundary().post(admission, token="token")
            self.assertTrue(observation.observed)
            self.assertEqual(observation.comment_id, 555)
            self.assertEqual([call[0].get_method() for call in opener.calls], ["GET", "POST", "GET"])
            self.assertTrue(opener.calls[1][0].full_url.endswith("/issues/144/comments"))
            self.assertTrue(opener.calls[2][0].full_url.endswith("/issues/comments/555"))

    def test_durable_ledger_denies_same_receipt_key_before_post(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = root / "event.json"
            stderr_path = root / "stderr.txt"
            event_path.write_text(json.dumps(_event()), encoding="utf-8")
            stderr_path.write_text("boom", encoding="utf-8")
            admission = MaintenanceReceiptAdmission.failure(
                event_path=event_path,
                repository=REPOSITORY,
                workflow_run_id=123,
                workflow_run_attempt=1,
                checked_out_sha=SHA,
                exit_code=1,
                stderr_path=stderr_path,
            )
            opener = _Opener([_Response(200, [{"body": f"x\nreceipt_key={admission.receipt_key}"}])])
            with patch("urllib.request.build_opener", return_value=opener), self.assertRaisesRegex(
                RepositoryMaintenanceReceiptError, "replay denied"
            ):
                GitHubMaintenanceReceiptBoundary().post(admission, token="token")
            self.assertEqual(len(opener.calls), 1)
            self.assertEqual(opener.calls[0][0].get_method(), "GET")

    def test_observation_requires_unchanged_master_and_exact_result(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = root / "event.json"
            result_path = root / "result.json"
            event_path.write_text(json.dumps(_event()), encoding="utf-8")
            result = {
                "master_before": SHA,
                "master_after": SHA,
                "initial_non_master_count": 3,
                "deleted_count": 1,
                "retained_count": 2,
                "final_branches": ["master", "feature/x"],
            }
            result_path.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            admission = MaintenanceReceiptAdmission.observation(
                event_path=event_path,
                repository=REPOSITORY,
                workflow_run_id=222,
                workflow_run_attempt=1,
                checked_out_sha=SHA,
                result_path=result_path,
            )
            self.assertIn("observation_result=OBSERVED_VERIFIED", admission.receipt_body)
            self.assertIn("master_effect=false", admission.receipt_body)
            self.assertIn("final_branches_digest=", admission.receipt_body)
            bad = dict(result, master_after="b" * 40)
            result_path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(RepositoryMaintenanceReceiptError, "master observation invalid"):
                MaintenanceReceiptAdmission.observation(
                    event_path=event_path,
                    repository=REPOSITORY,
                    workflow_run_id=222,
                    workflow_run_attempt=1,
                    checked_out_sha=SHA,
                    result_path=result_path,
                )

    def test_source_has_no_generic_external_write_surface(self):
        import inspect
        import cyber_lion.enterprise.repository_maintenance_receipt as module

        source = inspect.getsource(module)
        self.assertEqual(source.count('method="POST"'), 1)
        self.assertNotIn("/dispatches", source)
        self.assertNotIn("git/refs", source)
        self.assertNotIn("method: str", source)
        self.assertIn("receipt_key", source)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from dataclasses import asdict
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.contracts.repository_maintenance_sandbox import (
    RepositoryMaintenanceExecutionReceipt,
)
from cyber_lion.enterprise.repository_maintenance_mediated_cleanup import (
    load_request_evidence,
)
from cyber_lion.enterprise.repository_maintenance_receipt import (
    GitHubMaintenanceReceiptBoundary,
    MaintenanceReceiptAdmission,
    RepositoryMaintenanceReceiptError,
)

REPOSITORY = "DonkeyJJLove/ai_platform"
OWNER = "DonkeyJJLove"
SHA = "a" * 40
HEAD = "b" * 40
TREE = "c" * 40
BRANCH = "mission/e006-r9d8-mediation-canary"


def _body(*, branch: str = BRANCH, expected_head: str = HEAD) -> str:
    return "\n".join((
        "LION-REPOSITORY-REF-DELETE v2",
        f"branch={branch}",
        f"expected_head={expected_head}",
    ))


def _event(
    *,
    body: str | None = None,
    issue: int = 144,
    repository: str = REPOSITORY,
    action: str = "created",
    actor: str = OWNER,
    owner: str = OWNER,
) -> dict:
    return {
        "action": action,
        "issue": {"number": issue},
        "comment": {
            "id": 991,
            "body": _body() if body is None else body,
            "user": {"login": actor},
        },
        "repository": {
            "full_name": repository,
            "owner": {"login": owner},
        },
    }


def _write_event(root: Path, event: dict | None = None) -> Path:
    path = root / "event.json"
    path.write_text(json.dumps(_event() if event is None else event), encoding="utf-8")
    return path


def _execution_receipt(
    *,
    branch: str = BRANCH,
    head: str = HEAD,
    master: str = SHA,
    exists_after: bool = False,
    outcome: str = "SUCCEEDED",
) -> dict:
    receipt = RepositoryMaintenanceExecutionReceipt.build(
        schema_version="1.0.0",
        receipt_id="receipt-1",
        operation_id="operation-1",
        operation_digest="1" * 64,
        policy_digest="2" * 64,
        mission_id="mission-1",
        drone_id="drone-1",
        dispatch_id="dispatch-1",
        fencing_token=1,
        generation=1,
        repository=REPOSITORY,
        master_sha_before=master,
        master_sha_after=master,
        branch_name=branch,
        branch_head_before=head,
        branch_exists_after=exists_after,
        effect="DELETE_BRANCH_REF",
        outcome=outcome,
        observed_event_refs=("event:1",),
        authority_effect=False,
        master_effect=False,
    )
    return asdict(receipt)


def _canonical_result(
    *,
    event_path: Path,
    branch: str = BRANCH,
    expected_head: str = HEAD,
    fence_state: str = "RECONCILED",
) -> dict:
    request = load_request_evidence(event_path=event_path, repository=REPOSITORY)
    return {
        "schema_version": "1.0.0",
        "effect": "repository_ref.delete",
        "branch": branch,
        "expected_head": expected_head,
        "master": SHA,
        "tree": TREE,
        "bundle_digest": "3" * 64,
        "context_digest": "4" * 64,
        "authority_lineage_digest": "5" * 64,
        "pdp_decision_digest": "6" * 64,
        "admission_digest": "7" * 64,
        "effect_key": "8" * 64,
        "observation_digest": "9" * 64,
        "reconciliation_digest": "a" * 64,
        "fence_state": fence_state,
        "receipt": _execution_receipt(branch=branch, head=expected_head),
        "request_digest": request.digest(),
        "classification": {"classification": "A"},
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


class _Mediator:
    def __init__(self, *, mutate=False): self.requests=[]; self.mutate=mutate
    def execute(self, request):
        self.requests.append(request)
        if self.mutate: raise RuntimeError("observer mismatch")
        return {"comment_id":555,"fence_state":"RECONCILED"}


class RepositoryMaintenanceReceiptTests(unittest.TestCase):
    def test_exact_v2_event_is_accepted_and_failure_is_request_bound(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = _write_event(root)
            stderr_path = root / "stderr.txt"
            stderr_path.write_text("boom", encoding="utf-8")
            request = load_request_evidence(event_path=event_path, repository=REPOSITORY)
            admission = MaintenanceReceiptAdmission.failure(
                event_path=event_path,
                repository=REPOSITORY,
                workflow_run_id=123,
                workflow_run_attempt=1,
                checked_out_sha=SHA,
                exit_code=2,
                stderr_path=stderr_path,
            )
            self.assertEqual(admission.branch, BRANCH)
            self.assertEqual(admission.expected_head, HEAD)
            self.assertEqual(admission.request_digest, request.digest())
            self.assertIn("LION-REPOSITORY-MAINTENANCE-CONTROL-FAILURE v2", admission.receipt_body)
            self.assertIn(f"branch={BRANCH}", admission.receipt_body)
            self.assertIn(f"expected_head={HEAD}", admission.receipt_body)
            self.assertIn(f"request_digest={request.digest()}", admission.receipt_body)
            self.assertIn("result=FAILED_CLOSED", admission.receipt_body)
            self.assertIn("receipt_is_evidence_not_authority=true", admission.receipt_body)

    def test_legacy_v1_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = _write_event(root, _event(body="LION-BRANCH-CLEANUP v1"))
            stderr_path = root / "stderr.txt"
            stderr_path.write_text("boom", encoding="utf-8")
            with self.assertRaisesRegex(RepositoryMaintenanceReceiptError, "request binding mismatch"):
                MaintenanceReceiptAdmission.failure(
                    event_path=event_path,
                    repository=REPOSITORY,
                    workflow_run_id=1,
                    workflow_run_attempt=1,
                    checked_out_sha=SHA,
                    exit_code=2,
                    stderr_path=stderr_path,
                )

    def test_malformed_v2_request_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            malformed = "\n".join(("LION-REPOSITORY-REF-DELETE v2", f"branch={BRANCH}"))
            event_path = _write_event(root, _event(body=malformed))
            stderr_path = root / "stderr.txt"
            stderr_path.write_text("boom", encoding="utf-8")
            with self.assertRaises(RepositoryMaintenanceReceiptError):
                MaintenanceReceiptAdmission.failure(
                    event_path=event_path,
                    repository=REPOSITORY,
                    workflow_run_id=1,
                    workflow_run_attempt=1,
                    checked_out_sha=SHA,
                    exit_code=2,
                    stderr_path=stderr_path,
                )

    def test_unsafe_branch_request_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = _write_event(root, _event(body=_body(branch="refs/heads/master")))
            stderr_path = root / "stderr.txt"
            stderr_path.write_text("boom", encoding="utf-8")
            with self.assertRaises(RepositoryMaintenanceReceiptError):
                MaintenanceReceiptAdmission.failure(
                    event_path=event_path,
                    repository=REPOSITORY,
                    workflow_run_id=1,
                    workflow_run_attempt=1,
                    checked_out_sha=SHA,
                    exit_code=2,
                    stderr_path=stderr_path,
                )

    def test_invalid_expected_head_request_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = _write_event(root, _event(body=_body(expected_head="B" * 40)))
            stderr_path = root / "stderr.txt"
            stderr_path.write_text("boom", encoding="utf-8")
            with self.assertRaises(RepositoryMaintenanceReceiptError):
                MaintenanceReceiptAdmission.failure(
                    event_path=event_path,
                    repository=REPOSITORY,
                    workflow_run_id=1,
                    workflow_run_attempt=1,
                    checked_out_sha=SHA,
                    exit_code=2,
                    stderr_path=stderr_path,
                )

    def test_wrong_issue_repository_action_or_actor_is_rejected(self):
        variants = (
            _event(issue=145),
            _event(repository="Other/repo"),
            _event(action="edited"),
            _event(actor="not-owner"),
        )
        for event in variants:
            with self.subTest(event=event):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    event_path = _write_event(root, event)
                    stderr_path = root / "stderr.txt"
                    stderr_path.write_text("boom", encoding="utf-8")
                    with self.assertRaises(RepositoryMaintenanceReceiptError):
                        MaintenanceReceiptAdmission.failure(
                            event_path=event_path,
                            repository=REPOSITORY,
                            workflow_run_id=1,
                            workflow_run_attempt=1,
                            checked_out_sha=SHA,
                            exit_code=2,
                            stderr_path=stderr_path,
                        )

    def test_failure_diagnostic_redacts_secret(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = _write_event(root)
            stderr_path = root / "stderr.txt"
            stderr_path.write_text("token=super-secret-value", encoding="utf-8")
            admission = MaintenanceReceiptAdmission.failure(
                event_path=event_path,
                repository=REPOSITORY,
                workflow_run_id=123,
                workflow_run_attempt=1,
                checked_out_sha=SHA,
                exit_code=2,
                stderr_path=stderr_path,
            )
            self.assertNotIn("super-secret-value", admission.receipt_body)
            self.assertIn("token=[REDACTED]", admission.receipt_body)

    def test_replay_identity_is_bound_into_canonical_request(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); event_path=_write_event(root); stderr_path=root/"stderr.txt"; stderr_path.write_text("boom",encoding="utf-8")
            admission=MaintenanceReceiptAdmission.failure(event_path=event_path,repository=REPOSITORY,workflow_run_id=123,workflow_run_attempt=1,checked_out_sha=SHA,exit_code=1,stderr_path=stderr_path)
            mediator=_Mediator(); boundary=GitHubMaintenanceReceiptBoundary(mediator=mediator)
            boundary.post(admission,token="ignored")
            self.assertEqual(len(mediator.requests),1)
            self.assertEqual(mediator.requests[0].semantic_capability,"repository-maintenance.receipt.create")
            self.assertEqual(len(mediator.requests[0].replay_key),64)

    def test_canonical_reconciled_v2_result_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = _write_event(root)
            result_path = root / "result.json"
            result = _canonical_result(event_path=event_path)
            result_path.write_text(
                json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            admission = MaintenanceReceiptAdmission.observation(
                event_path=event_path,
                repository=REPOSITORY,
                workflow_run_id=222,
                workflow_run_attempt=1,
                checked_out_sha=SHA,
                result_path=result_path,
            )
            self.assertIn("LION-REPOSITORY-MAINTENANCE-OBSERVATION-RECEIPT v2", admission.receipt_body)
            self.assertIn("fence_state=RECONCILED", admission.receipt_body)
            self.assertIn("observation_result=OBSERVED_VERIFIED", admission.receipt_body)
            self.assertIn("receipt_is_evidence_not_authority=true", admission.receipt_body)

    def test_non_reconciled_result_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = _write_event(root)
            result_path = root / "result.json"
            result_path.write_text(
                json.dumps(_canonical_result(event_path=event_path, fence_state="OBSERVED")),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RepositoryMaintenanceReceiptError, "not reconciled"):
                MaintenanceReceiptAdmission.observation(
                    event_path=event_path,
                    repository=REPOSITORY,
                    workflow_run_id=222,
                    workflow_run_attempt=1,
                    checked_out_sha=SHA,
                    result_path=result_path,
                )

    def test_result_branch_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = _write_event(root)
            result_path = root / "result.json"
            result = _canonical_result(event_path=event_path)
            result["branch"] = "mission/substituted"
            result_path.write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(RepositoryMaintenanceReceiptError, "branch substitution"):
                MaintenanceReceiptAdmission.observation(
                    event_path=event_path,
                    repository=REPOSITORY,
                    workflow_run_id=222,
                    workflow_run_attempt=1,
                    checked_out_sha=SHA,
                    result_path=result_path,
                )

    def test_result_expected_head_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = _write_event(root)
            result_path = root / "result.json"
            result = _canonical_result(event_path=event_path)
            result["expected_head"] = "d" * 40
            result_path.write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(RepositoryMaintenanceReceiptError, "expected-head substitution"):
                MaintenanceReceiptAdmission.observation(
                    event_path=event_path,
                    repository=REPOSITORY,
                    workflow_run_id=222,
                    workflow_run_attempt=1,
                    checked_out_sha=SHA,
                    result_path=result_path,
                )

    def test_malformed_security_digests_are_rejected(self):
        for field in ("admission_digest", "effect_key", "observation_digest", "reconciliation_digest"):
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    event_path = _write_event(root)
                    result_path = root / "result.json"
                    result = _canonical_result(event_path=event_path)
                    result[field] = "not-a-digest"
                    result_path.write_text(json.dumps(result), encoding="utf-8")
                    with self.assertRaises(RepositoryMaintenanceReceiptError):
                        MaintenanceReceiptAdmission.observation(
                            event_path=event_path,
                            repository=REPOSITORY,
                            workflow_run_id=222,
                            workflow_run_attempt=1,
                            checked_out_sha=SHA,
                            result_path=result_path,
                        )

    def test_legacy_cleanup_result_shape_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = _write_event(root)
            result_path = root / "result.json"
            result_path.write_text(json.dumps({
                "master_before": SHA,
                "master_after": SHA,
                "initial_non_master_count": 3,
                "deleted_count": 1,
                "retained_count": 2,
                "final_branches": ["master"],
            }), encoding="utf-8")
            with self.assertRaisesRegex(RepositoryMaintenanceReceiptError, "canonical maintenance result incomplete"):
                MaintenanceReceiptAdmission.observation(
                    event_path=event_path,
                    repository=REPOSITORY,
                    workflow_run_id=222,
                    workflow_run_attempt=1,
                    checked_out_sha=SHA,
                    result_path=result_path,
                )

    def test_execution_receipt_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            event_path = _write_event(root)
            result_path = root / "result.json"
            result = _canonical_result(event_path=event_path)
            result["receipt"] = _execution_receipt(branch="mission/substituted", head=HEAD)
            result_path.write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(RepositoryMaintenanceReceiptError, "branch substitution"):
                MaintenanceReceiptAdmission.observation(
                    event_path=event_path,
                    repository=REPOSITORY,
                    workflow_run_id=222,
                    workflow_run_attempt=1,
                    checked_out_sha=SHA,
                    result_path=result_path,
                )

    def test_missing_canonical_mediator_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); event_path=_write_event(root); stderr_path=root/"stderr.txt"; stderr_path.write_text("boom",encoding="utf-8")
            admission=MaintenanceReceiptAdmission.failure(event_path=event_path,repository=REPOSITORY,workflow_run_id=123,workflow_run_attempt=1,checked_out_sha=SHA,exit_code=2,stderr_path=stderr_path)
            with self.assertRaisesRegex(RepositoryMaintenanceReceiptError,"mediator unavailable"):
                GitHubMaintenanceReceiptBoundary().post(admission,token="ignored")

    def test_failure_receipt_routes_through_canonical_mediator(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); event_path=_write_event(root); stderr_path=root/"stderr.txt"; stderr_path.write_text("boom",encoding="utf-8")
            admission=MaintenanceReceiptAdmission.failure(event_path=event_path,repository=REPOSITORY,workflow_run_id=123,workflow_run_attempt=1,checked_out_sha=SHA,exit_code=2,stderr_path=stderr_path)
            mediator=_Mediator(); observation=GitHubMaintenanceReceiptBoundary(mediator=mediator).post(admission,token="ignored")
            self.assertTrue(observation.observed); self.assertEqual(observation.comment_id,555)
            self.assertEqual(mediator.requests[0].semantic_capability,"repository-maintenance.receipt.create")
            self.assertEqual(mediator.requests[0].expected_repository_head,SHA)

    def test_source_has_no_raw_external_write_surface(self):
        import cyber_lion.enterprise.repository_maintenance_receipt as module
        source=inspect.getsource(module)
        self.assertNotIn('method="POST"',source)
        self.assertNotIn('method="PATCH"',source)
        self.assertNotIn("/dispatches",source)
        self.assertNotIn("git/refs",source)
        self.assertIn("IssueCommentWriteRequest",source)


if __name__ == "__main__":
    unittest.main()

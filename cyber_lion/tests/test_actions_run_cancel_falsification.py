import tempfile
import unittest
from pathlib import Path

from cyber_lion.contracts.actions_run_cancel import ActionsRunCancelRequest
from cyber_lion.enterprise.actions_run_cancel_mediation import (
    ActionsRunCancelFenceRecord,
    ActionsRunCancelMediationError,
    CanonicalActionsRunCancelAdmission,
    DurableActionsRunCancelFence,
    actions_run_cancel_effect_key,
)


class ActionsRunCancelFalsificationTests(unittest.TestCase):
    def _request(self, **overrides):
        values = dict(
            repository="DonkeyJJLove/ai_platform",
            run_id=123,
            expected_workflow="LION Actions Dispatch Bridge",
            expected_event="issue_comment",
            expected_head_sha="a" * 40,
            reason_code="QUEUE_RECOVERY_ONLY",
            request_id="r2k-fuzz",
        )
        values.update(overrides)
        return ActionsRunCancelRequest(**values).validate()

    def _admission(self, request):
        return CanonicalActionsRunCancelAdmission(
            request_digest=request.payload_digest(),
            repository=request.repository,
            run_id=request.run_id,
            expected_workflow=request.expected_workflow,
            expected_event=request.expected_event,
            expected_head_sha=request.expected_head_sha,
            authority_lineage_digest="1" * 64,
            pdp_decision_digest="2" * 64,
            provider_id="TEST_ONLY",
            authority_epoch=1,
        ).sealed()

    def test_request_substitution_denied(self):
        request = self._request()
        admission = self._admission(request)
        for altered in (
            self._request(run_id=124, request_id="r2k-run"),
            self._request(expected_workflow="other", request_id="r2k-workflow"),
            self._request(expected_event="pull_request", request_id="r2k-event"),
            self._request(expected_head_sha="b" * 40, request_id="r2k-head"),
        ):
            with self.assertRaises(ActionsRunCancelMediationError):
                admission.binds(altered)

    def test_forged_admission_denied(self):
        request = self._request()
        admission = self._admission(request)
        forged = CanonicalActionsRunCancelAdmission(
            **{**admission.payload(), "pdp_decision_digest": "3" * 64, "admission_digest": admission.admission_digest}
        )
        with self.assertRaises(ActionsRunCancelMediationError):
            forged.validate()

    def test_unknown_cannot_reconcile(self):
        request = self._request()
        admission = self._admission(request)
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            key = actions_run_cancel_effect_key(request, admission)
            fence.prepare(ActionsRunCancelFenceRecord(
                key, admission.admission_digest, request.payload_digest(), request.repository,
                request.run_id, "PREPARED", "2026-08-26T00:00:00+00:00"
            ))
            fence.transition(key, "PREPARED", "UNKNOWN")
            with self.assertRaises(ActionsRunCancelMediationError):
                fence.transition(
                    key, "OBSERVED", "RECONCILED",
                    reconciled_at="2026-08-26T00:01:00+00:00",
                    reconciliation_digest="4" * 64,
                )

    def test_replay_prepare_denied(self):
        request = self._request()
        admission = self._admission(request)
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            key = actions_run_cancel_effect_key(request, admission)
            record = ActionsRunCancelFenceRecord(
                key, admission.admission_digest, request.payload_digest(), request.repository,
                request.run_id, "PREPARED", "2026-08-26T00:00:00+00:00"
            )
            fence.prepare(record)
            with self.assertRaises(ActionsRunCancelMediationError):
                fence.prepare(record)


if __name__ == "__main__":
    unittest.main()

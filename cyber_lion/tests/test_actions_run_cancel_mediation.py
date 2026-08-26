import tempfile
import unittest
from pathlib import Path

from cyber_lion.contracts.actions_run_cancel import ActionsRunCancelRequest
from cyber_lion.enterprise.actions_run_cancel_mediation import (
    ActionsRunCancelMediationError,
    CanonicalActionsRunCancelAdmission,
    CanonicalActionsRunCancelMediator,
    DurableActionsRunCancelFence,
)


class _Admissions:
    def __init__(self, request):
        self.request = request
        self.admission = CanonicalActionsRunCancelAdmission(
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

    def resolve(self, request):
        return self.admission


class _Reader:
    def __init__(self, request):
        self.request = request
        self.cancelled = False

    def get_run(self, run_id):
        if self.cancelled:
            return {
                "id": self.request.run_id,
                "name": self.request.expected_workflow,
                "event": self.request.expected_event,
                "head_sha": self.request.expected_head_sha,
                "status": "completed",
                "conclusion": "cancelled",
            }
        return {
            "id": self.request.run_id,
            "name": self.request.expected_workflow,
            "event": self.request.expected_event,
            "head_sha": self.request.expected_head_sha,
            "status": "queued",
            "conclusion": None,
        }


class _Effect:
    def __init__(self, reader):
        self.reader = reader
        self.calls = 0

    def cancel_exact(self, request, admission):
        self.calls += 1
        self.reader.cancelled = True


class ActionsRunCancelMediationTests(unittest.TestCase):
    def _request(self):
        return ActionsRunCancelRequest(
            "DonkeyJJLove/ai_platform",
            123,
            "LION Actions Dispatch Bridge",
            "issue_comment",
            "a" * 40,
            "QUEUE_RECOVERY_ONLY",
            "r2k-1",
        ).validate()

    def test_exact_flow_reconciles(self):
        request = self._request()
        reader = _Reader(request)
        effect = _Effect(reader)
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            out = CanonicalActionsRunCancelMediator(
                admissions=_Admissions(request), repository=reader, effect=effect, fence=fence
            ).execute(request)
            self.assertEqual(out["state"], "RECONCILED")
            self.assertEqual(effect.calls, 1)
            self.assertEqual(fence.get(out["effect_key"]).state, "RECONCILED")

    def test_wrong_head_denied_pre_effect(self):
        request = self._request()
        reader = _Reader(request)
        effect = _Effect(reader)
        bad = ActionsRunCancelRequest(
            request.repository,
            request.run_id,
            request.expected_workflow,
            request.expected_event,
            "b" * 40,
            request.reason_code,
            "r2k-2",
        ).validate()
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            with self.assertRaises(ActionsRunCancelMediationError):
                CanonicalActionsRunCancelMediator(
                    admissions=_Admissions(bad), repository=reader, effect=effect, fence=fence
                ).execute(bad)
            self.assertEqual(effect.calls, 0)

    def test_replay_denied(self):
        request = self._request()
        reader = _Reader(request)
        effect = _Effect(reader)
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            mediator = CanonicalActionsRunCancelMediator(
                admissions=_Admissions(request), repository=reader, effect=effect, fence=fence
            )
            mediator.execute(request)
            reader.cancelled = False
            with self.assertRaises(ActionsRunCancelMediationError):
                mediator.execute(request)


if __name__ == "__main__":
    unittest.main()

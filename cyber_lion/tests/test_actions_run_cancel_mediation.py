import tempfile
import unittest
from pathlib import Path

from cyber_lion.contracts.actions_run_cancel import ActionsRunCancelRequest
from cyber_lion.enterprise.actions_run_cancel_mediation import (
    ActionsRunCancelMediationError,
    CanonicalActionsRunCancelAdmission,
    CanonicalActionsRunCancelMediator,
    DurableActionsRunCancelFence,
    actions_run_cancel_effect_key,
)


class _Admissions:
    def __init__(self, request, *, drift_after_first=False):
        self.request = request
        self.calls = 0
        self.drift_after_first = drift_after_first

    def resolve(self, request):
        self.calls += 1
        pdp = "3" * 64 if self.drift_after_first and self.calls > 1 else "2" * 64
        return CanonicalActionsRunCancelAdmission(
            request_digest=request.payload_digest(),
            repository=request.repository,
            run_id=request.run_id,
            expected_workflow=request.expected_workflow,
            expected_event=request.expected_event,
            expected_head_sha=request.expected_head_sha,
            authority_lineage_digest="1" * 64,
            pdp_decision_digest=pdp,
            provider_id="TEST_ONLY",
            authority_epoch=1,
        ).sealed()


class _Reader:
    def __init__(
        self,
        request,
        *,
        drift_call=0,
        drift_field=None,
        terminal=False,
        observed_conclusion="cancelled",
    ):
        self.request = request
        self.calls = 0
        self.cancelled = False
        self.drift_call = drift_call
        self.drift_field = drift_field
        self.terminal = terminal
        self.observed_conclusion = observed_conclusion

    def get_run(self, run_id):
        self.calls += 1
        value = {
            "id": self.request.run_id,
            "name": self.request.expected_workflow,
            "event": self.request.expected_event,
            "head_sha": self.request.expected_head_sha,
            "status": "queued",
            "conclusion": None,
        }
        if self.terminal:
            value["status"] = "completed"
            value["conclusion"] = "success"
        elif self.cancelled:
            value["status"] = "completed"
            value["conclusion"] = self.observed_conclusion
        if self.drift_call and self.calls >= self.drift_call:
            if self.drift_field == "head":
                value["head_sha"] = "b" * 40
            elif self.drift_field == "workflow":
                value["name"] = "other"
            elif self.drift_field == "event":
                value["event"] = "pull_request"
        return value


class _Effect:
    def __init__(self, reader, *, apply=True, fence=None):
        self.reader = reader
        self.apply = apply
        self.fence = fence
        self.calls = 0
        self.state_at_call = None

    def cancel_exact(self, request, admission):
        self.calls += 1
        if self.fence is not None:
            key = actions_run_cancel_effect_key(request, admission)
            self.state_at_call = self.fence.get(key).state
        if self.apply:
            self.reader.cancelled = True


class ActionsRunCancelMediationTests(unittest.TestCase):
    def _request(self, **overrides):
        values = dict(
            repository="DonkeyJJLove/ai_platform",
            run_id=123,
            expected_workflow="LION Actions Dispatch Bridge",
            expected_event="issue_comment",
            expected_head_sha="a" * 40,
            reason_code="QUEUE_RECOVERY_ONLY",
            request_id="r2k-1",
        )
        values.update(overrides)
        return ActionsRunCancelRequest(**values).validate()

    def test_exact_flow_reconciles_and_attempted_precedes_effect(self):
        request = self._request()
        reader = _Reader(request)
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            effect = _Effect(reader, fence=fence)
            out = CanonicalActionsRunCancelMediator(
                admissions=_Admissions(request),
                repository=reader,
                effect=effect,
                fence=fence,
            ).execute(request)
            self.assertEqual(out["state"], "RECONCILED")
            self.assertEqual(effect.calls, 1)
            self.assertEqual(effect.state_at_call, "ATTEMPTED")
            self.assertEqual(fence.get(out["effect_key"]).state, "RECONCILED")

    def test_wrong_head_denied_pre_effect(self):
        request = self._request(expected_head_sha="b" * 40, request_id="r2k-head")
        reader = _Reader(self._request())
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            effect = _Effect(reader)
            with self.assertRaises(ActionsRunCancelMediationError):
                CanonicalActionsRunCancelMediator(
                    admissions=_Admissions(request),
                    repository=reader,
                    effect=effect,
                    fence=fence,
                ).execute(request)
            self.assertEqual(effect.calls, 0)

    def test_wrong_workflow_denied_pre_effect(self):
        request = self._request(expected_workflow="other", request_id="r2k-workflow")
        reader = _Reader(self._request())
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            effect = _Effect(reader)
            with self.assertRaises(ActionsRunCancelMediationError):
                CanonicalActionsRunCancelMediator(
                    admissions=_Admissions(request),
                    repository=reader,
                    effect=effect,
                    fence=fence,
                ).execute(request)
            self.assertEqual(effect.calls, 0)

    def test_wrong_event_denied_pre_effect(self):
        request = self._request(expected_event="pull_request", request_id="r2k-event")
        reader = _Reader(self._request())
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            effect = _Effect(reader)
            with self.assertRaises(ActionsRunCancelMediationError):
                CanonicalActionsRunCancelMediator(
                    admissions=_Admissions(request),
                    repository=reader,
                    effect=effect,
                    fence=fence,
                ).execute(request)
            self.assertEqual(effect.calls, 0)

    def test_terminal_run_denied_pre_effect(self):
        request = self._request()
        reader = _Reader(request, terminal=True)
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            effect = _Effect(reader)
            with self.assertRaisesRegex(ActionsRunCancelMediationError, "not cancellable"):
                CanonicalActionsRunCancelMediator(
                    admissions=_Admissions(request),
                    repository=reader,
                    effect=effect,
                    fence=fence,
                ).execute(request)
            self.assertEqual(effect.calls, 0)

    def test_authority_drift_after_prepared_denied_pre_effect(self):
        request = self._request()
        reader = _Reader(request)
        admissions = _Admissions(request, drift_after_first=True)
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            effect = _Effect(reader)
            with self.assertRaisesRegex(ActionsRunCancelMediationError, "authority drift"):
                CanonicalActionsRunCancelMediator(
                    admissions=admissions,
                    repository=reader,
                    effect=effect,
                    fence=fence,
                ).execute(request)
            self.assertEqual(effect.calls, 0)

    def test_currentness_drift_after_prepared_denied_pre_effect(self):
        request = self._request()
        reader = _Reader(request, drift_call=2, drift_field="head")
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            effect = _Effect(reader)
            with self.assertRaisesRegex(ActionsRunCancelMediationError, "currentness mismatch"):
                CanonicalActionsRunCancelMediator(
                    admissions=_Admissions(request),
                    repository=reader,
                    effect=effect,
                    fence=fence,
                ).execute(request)
            self.assertEqual(effect.calls, 0)

    def test_replay_denied(self):
        request = self._request()
        reader = _Reader(request)
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            effect = _Effect(reader)
            mediator = CanonicalActionsRunCancelMediator(
                admissions=_Admissions(request),
                repository=reader,
                effect=effect,
                fence=fence,
            )
            mediator.execute(request)
            reader.cancelled = False
            with self.assertRaises(ActionsRunCancelMediationError):
                mediator.execute(request)
            self.assertEqual(effect.calls, 1)

    def test_missing_cancellation_observation_fails_unknown(self):
        request = self._request()
        reader = _Reader(request)
        admissions = _Admissions(request)
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            effect = _Effect(reader, apply=False)
            mediator = CanonicalActionsRunCancelMediator(
                admissions=admissions,
                repository=reader,
                effect=effect,
                fence=fence,
            )
            with self.assertRaisesRegex(
                ActionsRunCancelMediationError,
                "independent cancellation observation missing",
            ):
                mediator.execute(request)
            admission = admissions.resolve(request)
            key = actions_run_cancel_effect_key(request, admission)
            self.assertEqual(fence.get(key).state, "UNKNOWN")

    def test_observation_conclusion_mismatch_fails_unknown(self):
        request = self._request()
        reader = _Reader(request, observed_conclusion="failure")
        admissions = _Admissions(request)
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            effect = _Effect(reader)
            mediator = CanonicalActionsRunCancelMediator(
                admissions=admissions,
                repository=reader,
                effect=effect,
                fence=fence,
            )
            with self.assertRaisesRegex(
                ActionsRunCancelMediationError,
                "independent cancellation observation missing",
            ):
                mediator.execute(request)
            admission = admissions.resolve(request)
            key = actions_run_cancel_effect_key(request, admission)
            self.assertEqual(fence.get(key).state, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from cyber_lion.contracts.actions_run_cancel import ActionsRunCancelRequest
from cyber_lion.enterprise.actions_run_cancel_github_effect import ExactActionsRunCancelEffectProvider
from cyber_lion.enterprise.actions_run_cancel_mediation import (
    ActionsRunCancelFenceRecord,
    ActionsRunCancelMediationError,
    CanonicalActionsRunCancelAdmission,
    DurableActionsRunCancelFence,
    actions_run_cancel_effect_key,
)


class ActionsRunCancelGithubEffectTests(unittest.TestCase):
    def _fixture(self):
        request = ActionsRunCancelRequest(
            "DonkeyJJLove/ai_platform",
            123,
            "LION Actions Dispatch Bridge",
            "issue_comment",
            "a" * 40,
            "QUEUE_RECOVERY_ONLY",
            "r2k-effect",
        ).validate()
        admission = CanonicalActionsRunCancelAdmission(
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
        return request, admission

    def test_provider_denies_before_attempted(self):
        request, admission = self._fixture()
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            key = actions_run_cancel_effect_key(request, admission)
            fence.prepare(
                ActionsRunCancelFenceRecord(
                    key,
                    admission.admission_digest,
                    request.payload_digest(),
                    request.repository,
                    request.run_id,
                    "PREPARED",
                    "2026-08-26T00:00:00+00:00",
                )
            )
            provider = ExactActionsRunCancelEffectProvider(
                repository=request.repository, token="test-only", fence=fence
            )
            with self.assertRaises(ActionsRunCancelMediationError):
                provider.cancel_exact(request, admission)

    def test_repository_substitution_denied(self):
        request, admission = self._fixture()
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "fence.sqlite"))
            provider = ExactActionsRunCancelEffectProvider(
                repository="DonkeyJJLove/ai_platform", token="test-only", fence=fence
            )
            bad = ActionsRunCancelRequest(
                "DonkeyJJLove/ai_platform",
                999,
                request.expected_workflow,
                request.expected_event,
                request.expected_head_sha,
                request.reason_code,
                "r2k-substitute",
            ).validate()
            with self.assertRaises(ActionsRunCancelMediationError):
                provider.cancel_exact(bad, admission)


if __name__ == "__main__":
    unittest.main()

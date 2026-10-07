from __future__ import annotations

import unittest

from cyber_lion.contracts.artifact_candidate_iteration import (
    ArtifactCandidateObservation,
    ArtifactCandidateObservationError,
    ArtifactPollPolicy,
    decide_next,
)

H = "a" * 64
R = "b" * 64


def observation(**updates):
    value = dict(
        run_id="run-1",
        mission_id="mission-1",
        task_id="task-1",
        generation=1,
        attempt=1,
        state="RUNNING",
        source_digest=H,
        stream_state="AVAILABLE",
        worker_state="RUNNING",
        observed_at="2026-10-06T20:00:00+00:00",
    )
    value.update(updates)
    return ArtifactCandidateObservation(**value)


class ArtifactCandidateIterationTests(unittest.TestCase):
    def test_stream_loss_does_not_fail_or_restart_running_work(self):
        decision = decide_next(
            observation(stream_state="EXPIRED"),
            ArtifactPollPolicy(initial_seconds=2, max_seconds=30),
            poll_index=3,
            elapsed_seconds=20,
        )
        self.assertEqual(decision.action, "OBSERVE_LATER")
        self.assertEqual(decision.next_poll_seconds, 16)

    def test_candidate_bytes_trigger_verification_not_more_stream_waiting(self):
        decision = decide_next(
            observation(
                state="CANDIDATE_AVAILABLE",
                stream_state="LOST",
                worker_state="TERMINAL",
                artifact_ref="artifact:gen1",
                artifact_digest=H,
            ),
            ArtifactPollPolicy(),
            poll_index=50,
            elapsed_seconds=100,
        )
        self.assertEqual(decision.action, "VERIFY_ARTIFACT")

    def test_unknown_never_blindly_retries(self):
        decision = decide_next(
            observation(state="UNKNOWN", stream_state="EXPIRED", worker_state="UNKNOWN"),
            ArtifactPollPolicy(),
            poll_index=0,
            elapsed_seconds=0,
        )
        self.assertEqual(decision.action, "RECONCILE")

    def test_rejected_candidate_allows_bounded_successor_generation(self):
        decision = decide_next(
            observation(
                state="REJECTED",
                worker_state="TERMINAL",
                artifact_ref="artifact:gen1",
                artifact_digest=H,
                verifier_receipt_digest=R,
            ),
            ArtifactPollPolicy(max_generations=3),
            poll_index=0,
            elapsed_seconds=10,
        )
        self.assertEqual(decision.action, "NEXT_GENERATION")

    def test_generation_budget_exhaustion_hands_off(self):
        decision = decide_next(
            observation(
                generation=3,
                state="REJECTED",
                worker_state="TERMINAL",
                artifact_ref="artifact:gen3",
                artifact_digest=H,
                verifier_receipt_digest=R,
            ),
            ArtifactPollPolicy(max_generations=3),
            poll_index=0,
            elapsed_seconds=10,
        )
        self.assertEqual(decision.action, "HANDOFF")

    def test_verified_candidate_completes_despite_expired_stream(self):
        decision = decide_next(
            observation(
                state="VERIFIED",
                stream_state="EXPIRED",
                worker_state="TERMINAL",
                artifact_ref="artifact:gen1",
                artifact_digest=H,
                verifier_receipt_digest=R,
            ),
            ArtifactPollPolicy(),
            poll_index=119,
            elapsed_seconds=1700,
        )
        self.assertEqual(decision.action, "COMPLETE")

    def test_terminal_candidate_requires_verifier_receipt(self):
        with self.assertRaisesRegex(ArtifactCandidateObservationError, "verifier receipt"):
            observation(
                state="VERIFIED",
                worker_state="TERMINAL",
                artifact_ref="artifact:gen1",
                artifact_digest=H,
            ).validate()

    def test_artifact_reference_and_digest_are_atomic(self):
        with self.assertRaisesRegex(ArtifactCandidateObservationError, "must appear together"):
            observation(artifact_ref="artifact:gen1").validate()

    def test_poll_interval_is_bounded(self):
        policy = ArtifactPollPolicy(initial_seconds=2, max_seconds=30, multiplier=2)
        self.assertEqual([policy.interval_seconds(i) for i in range(6)], [2, 4, 8, 16, 30, 30])

    def test_observation_digest_is_stable(self):
        self.assertEqual(observation().as_dict()["observation_digest"], observation().as_dict()["observation_digest"])


if __name__ == "__main__":
    unittest.main()

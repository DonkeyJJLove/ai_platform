from __future__ import annotations

import unittest

from cyber_lion.mission_control.control_read_model import build_artifact_candidate_projection


class ArtifactCandidateProjectionTests(unittest.TestCase):
    def header(self):
        return {
            "observed_at": "2026-10-06T20:00:00Z",
            "source_refs": ("source:artifact-candidate",),
            "source_revision": "3079da0f7ebee8c8b17d42bc9553154d9bc35a98",
            "projection_version": "1.0.0",
            "currentness": "CURRENT",
            "gaps": (),
        }

    def test_stream_loss_remains_observable_without_raw_reason(self):
        payload = build_artifact_candidate_projection([
            {
                "run_id": "run2", "mission_id": "M1", "task_id": "T1",
                "generation": 2, "attempt": 1, "state": "RUNNING",
                "source_digest": "a" * 64, "stream_state": "EXPIRED",
                "worker_state": "RUNNING", "observed_at": "2026-10-06T20:00:02Z",
                "authority_effect": "NONE", "observation_digest": "b" * 64,
                "terminal_reason": "omit",
            },
            {
                "run_id": "run1", "mission_id": "M1", "task_id": "T1",
                "generation": 1, "attempt": 1, "state": "REJECTED",
                "source_digest": "a" * 64, "stream_state": "LOST",
                "worker_state": "TERMINAL", "observed_at": "2026-10-06T20:00:01Z",
                "artifact_ref": "artifact:g1", "artifact_digest": "c" * 64,
                "verifier_receipt_digest": "d" * 64,
                "authority_effect": "NONE", "observation_digest": "e" * 64,
                "terminal_reason": "omit",
            },
        ], **self.header()).payload()
        self.assertEqual([x["run_id"] for x in payload["candidates"]], ["run1", "run2"])
        self.assertEqual(payload["running_count"], 1)
        self.assertEqual(payload["terminal_count"], 1)
        self.assertEqual(payload["stream_degraded_count"], 2)
        self.assertTrue(all("terminal_reason" not in x for x in payload["candidates"]))

    def test_projection_is_deterministic_for_input_order(self):
        rows = [
            {"run_id":"run2","mission_id":"M1","task_id":"T1","generation":2,"attempt":1,"state":"RUNNING","source_digest":"a"*64,"stream_state":"AVAILABLE","worker_state":"RUNNING","observed_at":"2026-10-06T20:00:02Z","authority_effect":"NONE","observation_digest":"b"*64},
            {"run_id":"run1","mission_id":"M1","task_id":"T1","generation":1,"attempt":1,"state":"VERIFIED","source_digest":"a"*64,"stream_state":"EXPIRED","worker_state":"TERMINAL","observed_at":"2026-10-06T20:00:01Z","artifact_ref":"artifact:g1","artifact_digest":"c"*64,"verifier_receipt_digest":"d"*64,"authority_effect":"NONE","observation_digest":"e"*64},
        ]
        left = build_artifact_candidate_projection(rows, **self.header())
        right = build_artifact_candidate_projection(list(reversed(rows)), **self.header())
        self.assertEqual(left.projection_digest, right.projection_digest)


if __name__ == "__main__":
    unittest.main()

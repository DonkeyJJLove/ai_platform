"""Source-only negative acceptance for the R11 legacy R24 fleet diagnostic."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from unittest import TestCase, mock

from tools import lion_r11_fleet_recovery_preflight as p


def cohort(*, status: str = "exited", exit_code: int = 137, oom: bool = False):
    base = datetime(2026, 10, 8, 13, 20, 4, tzinfo=timezone.utc)
    result = []
    for idx in range(1, 33):
        finished = base + timedelta(milliseconds=(idx - 1) * 3)
        result.append({
            "Name": f"/lion-r24-md{idx:03d}",
            "Id": f"{idx:064x}",
            "Image": "sha256:" + "f" * 64,
            "State": {
                "Status": status,
                "ExitCode": exit_code,
                "OOMKilled": oom,
                "FinishedAt": finished.isoformat(),
            },
            "Config": {
                "Image": "lion-r20-worker:r1",
                "Labels": {
                    "LION_MATERIAL_WORKER_ID": f"MD{idx:03d}",
                    "LION_WORKER_PROFILE": "LION_MATERIAL_EXECUTOR_V2",
                    "com.docker.compose.project": "lion-r24-autonomy",
                },
            },
        })
    return result


def baseline_inputs():
    deltas = ("compose.yaml", "worker.py", "material_worker_runtime.py")
    files = {
        name: {
            "installed_sha256": "a" * 64,
            "candidate_sha256": ("b" if name in deltas else "a") * 64,
        }
        for name in p.SOURCE_FILES
    }
    return {
        "container": p.classify_containers(cohort()),
        "installed_compose": "WORKER_MOUNT_COUNT_DRIFT:worker-01",
        "canonical_compose": "PASS_SOURCE_STRUCTURE",
        "installed_identity": "MaterialWorkerContractError:worker assignment capability drift",
        "worker_readiness": "worker observation stale or unavailable MD001",
        "file_comparison": files,
        "missing_roots": ["private", "provider-artifact", "unbound"],
    }


class R11FleetRecoverySourcePreflightTests(TestCase):
    def test_exact_stopped_cohort_is_observation_only(self):
        view = p.classify_containers(cohort())
        self.assertEqual(view["state"], "STOPPED_COHORT")
        self.assertEqual(view["observed"], 32)
        self.assertEqual(view["running"], 0)
        self.assertEqual(view["exit_code_137"], 32)
        self.assertEqual(view["docker_oomkilled"], 0)
        self.assertLessEqual(view["finished_span_seconds"], 1)
        self.assertEqual(view["authority_effect"], "NONE")

    def test_running_cohort_does_not_become_admitted(self):
        rows = cohort(status="running", exit_code=0)
        view = p.classify_containers(rows)
        self.assertEqual(view["state"], "RUNNING_NOT_YET_QUALIFIED")
        payload = baseline_inputs()
        payload["container"] = view
        result = p.classify_recovery(**payload)
        self.assertFalse(result["ready"])
        self.assertFalse(result["restart_allowed"])
        self.assertFalse(result["operation_allowed"])
        self.assertEqual(result["classification"], "UNKNOWN_OR_CHANGED_HOLD")

    def test_incomplete_inventory_fails_closed(self):
        view = p.classify_containers(cohort()[:31])
        self.assertEqual(view["state"], "UNKNOWN")
        self.assertEqual(view["reason"], "EXACT_32_CONTAINERS_NOT_OBSERVED")

    def test_label_substitution_fails_closed(self):
        rows = cohort()
        rows[5]["Config"]["Labels"]["LION_MATERIAL_WORKER_ID"] = "MD999"
        self.assertEqual(p.classify_containers(rows)["reason"], "CONTAINER_IDENTITY_OR_PROJECT_DRIFT")

    def test_cross_mission_project_is_not_accepted(self):
        rows = cohort()
        rows[11]["Config"]["Labels"]["com.docker.compose.project"] = "foreign"
        self.assertEqual(p.classify_containers(rows)["state"], "UNKNOWN")

    def test_duplicate_container_identity_fails_closed(self):
        rows = cohort()
        rows[2]["Id"] = rows[1]["Id"]
        self.assertEqual(p.classify_containers(rows)["state"], "UNKNOWN")

    def test_known_legacy_case_is_migration_not_start(self):
        result = p.classify_recovery(**baseline_inputs())
        self.assertEqual(result["classification"], "LEGACY_R24_COHORT_REQUIRES_GOVERNED_UPGRADE")
        self.assertEqual(
            result["source_delta_files"],
            ["compose.yaml", "material_worker_runtime.py", "worker.py"],
        )
        self.assertFalse(result["operation_allowed"])
        self.assertFalse(result["ready"])
        self.assertFalse(result["restart_allowed"])
        self.assertEqual(result["authority_effect"], "NONE")

    def test_unexpected_other_source_delta_fails_closed(self):
        value = baseline_inputs()
        value["file_comparison"]["fleet-currentness.py"]["candidate_sha256"] = "c" * 64
        result = p.classify_recovery(**value)
        self.assertEqual(result["classification"], "UNKNOWN_OR_CHANGED_HOLD")
        self.assertIn("EXACT_LEGACY_SOURCE_DELTA_UNPROVEN", result["blockers"])

    def test_missing_source_bytes_fails_closed(self):
        value = baseline_inputs()
        value["file_comparison"]["worker.py"]["installed_sha256"] = None
        self.assertEqual(p.classify_recovery(**value)["classification"], "UNKNOWN_OR_CHANGED_HOLD")

    def test_private_roots_change_requires_reinspection(self):
        value = baseline_inputs()
        value["missing_roots"] = []
        result = p.classify_recovery(**value)
        self.assertEqual(result["classification"], "UNKNOWN_OR_CHANGED_HOLD")
        self.assertIn("PRIVATE_ROOT_LAYOUT_CHANGED", result["blockers"])

    def test_fresh_worker_status_alone_never_promotes_runtime(self):
        value = baseline_inputs()
        value["worker_readiness"] = "PASS"
        result = p.classify_recovery(**value)
        self.assertEqual(result["classification"], "UNKNOWN_OR_CHANGED_HOLD")
        self.assertFalse(result["operation_allowed"])
        self.assertIn("WORKER_READINESS_MUST_BE_RECLASSIFIED", result["blockers"])

    def test_oom_flag_alters_classification_without_causal_claim(self):
        value = baseline_inputs()
        value["container"] = p.classify_containers(cohort(oom=True))
        result = p.classify_recovery(**value)
        self.assertEqual(result["classification"], "UNKNOWN_OR_CHANGED_HOLD")
        self.assertIn("EXACT_STOPPED_COHORT_EVIDENCE_CHANGED", result["blockers"])

    def test_non_simultaneous_termination_unknown(self):
        value = baseline_inputs()
        value["container"]["finished_span_seconds"] = 600.0
        self.assertEqual(p.classify_recovery(**value)["classification"], "UNKNOWN_OR_CHANGED_HOLD")

    def test_read_only_command_allowlist_rejects_docker_mutation(self):
        with mock.patch.object(p.subprocess, "check_output", side_effect=AssertionError("process invoked")) as sub:
            for argv in (
                ["docker", "stop", "lion-r24-md001"],
                ["docker", "compose", "up", "-d"],
                ["docker", "compose", "-p", "lion-r24-autonomy",
                 "--project-directory", str(p.RUNTIME), "-f",
                 str(p.RUNTIME / "compose.yaml"), "up", "-d", "--no-recreate"],
                ["docker", "inspect", "--format", "{{json .}}", "foreign-container"],
                ["docker", "exec", "lion-r24-md001", "id"],
                ["git", "-C", "/tmp/repo", "reset", "--hard"],
            ):
                with self.assertRaisesRegex(p.PreflightError, "non-read-only"):
                    p._read(argv)
            sub.assert_not_called()

    def test_untrusted_source_head_rejected_before_docker(self):
        with self.assertRaisesRegex(p.PreflightError, "canonical MOON runtime"):
            p.analyze(source_root=Path("/tmp"), runtime=Path("/tmp"))
        self.assertFalse(p.ID_RE.fullmatch("bad"))
        self.assertTrue(p.ID_RE.fullmatch("a" * 40))

    def test_report_never_infers_authority_from_currentness(self):
        for value in (baseline_inputs(),):
            result = p.classify_recovery(**value)
            self.assertEqual(result["authority_effect"], "NONE")
            self.assertIn("EXACT_OPERATOR_LPCL_NOT_LAUNCHED", result["blockers"])


if __name__ == "__main__":
    import unittest
    unittest.main()

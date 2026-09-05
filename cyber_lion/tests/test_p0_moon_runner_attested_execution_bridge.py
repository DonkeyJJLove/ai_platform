from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler
from tools.p0_moon_runner_attested_bridge_contract import (
    AGENT,
    HOST,
    JOB_ID,
    MACHINE,
    OPERATIONS,
    OS_USER,
    POOL,
    RUNNER,
    UID,
    WORKFLOW,
    WORKFLOW_PATH,
    RunnerExecutionAttestation,
)
import tools.p0_moon_runner_attested_execution_bridge as bridge

REPOSITORY = "DonkeyJJLove/ai_platform"
CURRENT_SCAN = "cf13b4c46d1c77a58a2d9ee4d839a4994aa18ff126713886bc5e62649b998c18"
HISTORICAL_SCAN = "2e509f22b7684e465dbebba73886aa9eae74f166480cb7e46d5be90a02a566d3"
LIVE_SOURCE_REVISION = "830f8c2e5561655dc35118c97f4574acc3bf0816"
WORKFLOW_SOURCE = "tools/p0_moon_runner_attested_execution_bridge.workflow.source.yml"


def inventory():
    root = Path(__file__).resolve().parents[2]
    sources: dict[str, str] = {}
    for base in (root / "cyber_lion", root / ".github/workflows"):
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in {".py", ".yml", ".yaml"}:
                sources[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
    raw = EffectSurfaceScanner().scan(
        repository=REPOSITORY,
        revision=revision,
        tree_digest=tree,
        sources=sources,
    )
    reconciled, _, _ = EffectTaxonomyReconciler().reconcile(
        raw_inventory=raw,
        sources=sources,
    )
    return reconciled


class RunnerAttestedExecutionBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.inventory = inventory()
        cls.spec = bridge.bridge_spec(LIVE_SOURCE_REVISION)

    def test_revision_bound_scan_and_candidate_state(self):
        self.assertEqual(self.inventory.scan_digest, CURRENT_SCAN)
        self.assertEqual(bridge.EXPECTED_SCAN_DIGEST, HISTORICAL_SCAN)
        self.assertNotEqual(self.inventory.scan_digest, bridge.EXPECTED_SCAN_DIGEST)
        self.assertEqual(self.spec.revision, LIVE_SOURCE_REVISION)
        self.assertFalse(self.spec.live_execution)
        self.assertEqual(self.spec.state, "CANDIDATE_UNATTACHED")

    def test_exact_seven_operations_and_post_run_verification_requirements(self):
        self.assertEqual(self.spec.operations, OPERATIONS)
        self.assertEqual(len(self.spec.operations), 7)
        self.assertTrue(self.spec.workflow_dispatch_only)
        self.assertEqual(self.spec.permissions, ("contents:read",))
        self.assertTrue(self.spec.independent_post_run_verify)
        self.assertTrue(self.spec.require_run_head_sha_exact)
        self.assertTrue(self.spec.require_job_runner_name_exact)
        self.assertTrue(self.spec.require_job_runner_id_if_exposed)
        self.assertTrue(self.spec.require_job_terminal)
        self.assertTrue(self.spec.require_receipt_identity_match)
        self.assertFalse(self.spec.generic_shell)
        self.assertFalse(self.spec.arbitrary_command)
        self.assertFalse(self.spec.arbitrary_path)
        self.assertFalse(self.spec.arbitrary_module)

    def test_attached_workflow_is_exact_dispatch_only_enum(self):
        workflow = self.root / WORKFLOW_PATH
        source = self.root / WORKFLOW_SOURCE
        self.assertTrue(workflow.is_file())
        workflow_bytes = workflow.read_bytes()
        source_bytes = source.read_bytes()
        self.assertEqual(workflow_bytes, source_bytes)
        self.assertEqual(sha256(workflow_bytes).hexdigest(), "518b0ac3015e4d499595fce752cb9fa15d838237ee292921d3774bf58acb616f")
        text = workflow_bytes.decode("utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("issue_comment:", text)
        self.assertNotIn("repository_dispatch:", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("runs-on: [self-hosted, linux, lion-trust-client]", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("ref: ${{ github.sha }}", text)
        for operation in OPERATIONS:
            self.assertIn(f"- {operation}", text)
        for forbidden_input in ("path:", "command:", "module:", "shell:"):
            self.assertNotIn(forbidden_input, text)

    def test_bridge_exposes_no_actor_controlled_path_module_or_command(self):
        source = (self.root / "tools/p0_moon_runner_attested_execution_bridge.py").read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--operation", required=True, choices=OPERATIONS)', source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("eval(", source)
        self.assertNotIn("exec(", source)
        self.assertNotIn("os.system", source)
        for primitive in ("os.replace", "os.unlink", "write_text(", "write_bytes("):
            self.assertNotIn(primitive, source)
        self.assertIn('["git", "rev-parse", selector]', source)
        with self.assertRaises(bridge.RunnerAttestationError):
            bridge._git_value(self.root, "--exec-path")

    def test_wrong_os_user_uid_host_and_machine_are_denied(self):
        valid = dict(uid=UID, user=OS_USER, hostname=HOST, machine_id=MACHINE)
        for key, wrong in (
            ("uid", 0),
            ("user", "root"),
            ("hostname", "MOON"),
            ("machine_id", "0" * 32),
        ):
            candidate = valid.copy()
            candidate[key] = wrong
            with self.assertRaises(bridge.RunnerAttestationError):
                bridge._validate_local_identity(**candidate)

    def test_wrong_local_runner_metadata_is_denied(self):
        good = {"agentId": AGENT, "agentName": RUNNER, "poolName": POOL}
        bridge._validate_runner_metadata_payload(good)
        for key, wrong in (
            ("agentId", 23),
            ("agentName", "wrong-runner"),
            ("poolName", "wrong-pool"),
        ):
            candidate = good.copy()
            candidate[key] = wrong
            with self.assertRaises(bridge.RunnerAttestationError):
                bridge._validate_runner_metadata_payload(candidate)

    def test_missing_or_forged_github_job_context_is_denied(self):
        valid = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_RUN_ID": "123",
            "GITHUB_JOB": JOB_ID,
            "GITHUB_WORKFLOW": WORKFLOW,
            "GITHUB_WORKFLOW_REF": f"DonkeyJJLove/ai_platform/{WORKFLOW_PATH}@refs/heads/test",
            "GITHUB_REF": "refs/heads/test",
            "GITHUB_SHA": "0" * 40,
            "GITHUB_WORKSPACE": str(self.root),
            "RUNNER_NAME": RUNNER,
        }
        bridge._validate_github_environment(valid)
        for key in valid:
            candidate = valid.copy()
            candidate[key] = ""
            with self.assertRaises(bridge.RunnerAttestationError):
                bridge._validate_github_environment(candidate)
        wrong_ref = valid.copy()
        wrong_ref["GITHUB_WORKFLOW_REF"] = "DonkeyJJLove/ai_platform/.github/workflows/other.yml@refs/heads/test"
        with self.assertRaises(bridge.RunnerAttestationError):
            bridge._validate_github_environment(wrong_ref)

    def test_manual_process_with_forged_environment_still_requires_worker_ancestry(self):
        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_RUN_ID": "123",
            "GITHUB_JOB": JOB_ID,
            "GITHUB_WORKFLOW": WORKFLOW,
            "GITHUB_WORKFLOW_REF": f"DonkeyJJLove/ai_platform/{WORKFLOW_PATH}@refs/heads/test",
            "GITHUB_REF": "refs/heads/test",
            "GITHUB_SHA": "0" * 40,
            "GITHUB_WORKSPACE": str(self.root),
            "RUNNER_NAME": RUNNER,
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch.object(bridge.os, "geteuid", return_value=UID),
            patch.object(bridge.pwd, "getpwuid", return_value=SimpleNamespace(pw_name=OS_USER)),
            patch.object(bridge.socket, "gethostname", return_value=HOST),
            patch.object(bridge.Path, "read_text", return_value=MACHINE),
            patch.object(bridge, "_load_runner_metadata", return_value={"agentId": AGENT, "agentName": RUNNER, "poolName": POOL}),
            patch.object(bridge, "_git_value", side_effect=["0" * 40, "1" * 40]),
            patch.object(bridge, "_attested_worker_ancestor", side_effect=bridge.RunnerAttestationError("GitHub Runner.Worker ancestry missing")),
        ):
            with self.assertRaisesRegex(bridge.RunnerAttestationError, "Runner.Worker ancestry missing"):
                bridge.capture_runner_attestation()

    def test_sha_mismatch_is_denied_by_attestation_contract(self):
        prefix = f"DonkeyJJLove/ai_platform/{WORKFLOW_PATH}@refs/heads/test"
        with self.assertRaises(Exception):
            RunnerExecutionAttestation(
                revision="0" * 40,
                tree="1" * 40,
                runner_name=RUNNER,
                runner_agent_id=AGENT,
                pool_name=POOL,
                os_user=OS_USER,
                uid=UID,
                hostname=HOST,
                machine_id=MACHINE,
                github_actions="true",
                run_id="123",
                job_id=JOB_ID,
                workflow=WORKFLOW,
                workflow_ref=prefix,
                github_ref="refs/heads/test",
                github_sha="2" * 40,
                worker_binary_sha256="3" * 64,
                observed_at="2026-09-04T00:00:00+00:00",
            ).validate()

    def test_unknown_operation_is_denied_before_attestation_or_effect(self):
        with self.assertRaisesRegex(bridge.RunnerAttestationError, "unknown operation"):
            bridge.execute_fixed_operation("ARBITRARY_COMMAND")

    def test_materialization_does_not_execute_any_live_operation(self):
        with patch.object(bridge, "capture_runner_attestation", side_effect=AssertionError("must not execute")):
            with self.assertRaisesRegex(bridge.RunnerAttestationError, "^production scan digest drift$"):
                bridge.materialize_bridge_candidate(inventory=self.inventory)
        self.assertEqual(self.spec.state, "CANDIDATE_UNATTACHED")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import ast
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import lcms
import readonly_process_exec as c2
from readonly_process_observer import IndependentProcessObserver
import readonly_process_observer as observer_module
from readonly_process_reconciliation import reconcile
import readonly_process_reconciliation as reconciliation_module
from cyber_lion.tests.test_action_spec_schema import _validate

SCHEMA = json.loads((ROOT / "cyber_lion/contracts/v1/action_spec.schema.json").read_text())
EXEC_ROOT = c2.EXPECTED_WORKSPACE

BASE = [
    lcms.LCMS_HEADER,
    'schema_version="lion.action-spec/v1.3-candidate"',
    'action_id="c2.git.head.1"',
    'kind="process.exec"',
    'intent_ref="intent:c2-readonly"',
    'mission_ref="mission:c2-readonly-process-exec"',
    'autonomy_ref="autonomy:lion-local-console"',
    'bean_ref="bean:c2-git-observer"',
    'target.host="LAB-DEBIAN"',
    'target.environment="WSL2"',
    'target.runtime="local"',
    'authority_request.domain="information.read"',
    'authority_request.capability="repository.observe"',
    'authority_request.grant_ref=null',
    'boundary.shell=false',
    'boundary.network="DENY"',
    f'boundary.filesystem_read=["{EXEC_ROOT}"]',
    'boundary.filesystem_write=[]',
    'boundary.process_children=["/usr/bin/git"]',
    'boundary.timeout_ms=2000',
    'boundary.max_processes=1',
    'boundary.memory_limit_bytes=536870912',
    'preconditions=["repository.head == workspace.commit","repository.tree == workspace.tree","executable.digest == declared digest"]',
    'expected_effects=["test process created","stdout captured","stderr captured","exit status observed"]',
    'forbidden_effects=["repository mutation","network connection","service mutation","credential read","background process survival"]',
    'observation.observer_class="independent"',
    'observation.required_events=["process-exit","filesystem-delta","network-delta","child-process-closure"]',
    'reconciliation.mode="EXACT"',
    'reconciliation.receipt="REQUIRED"',
    'executable.path="/usr/bin/git"',
    'executable.digest="sha256:' + c2.TARGET_EXECUTABLE_SHA256 + '"',
    'arguments=["rev-parse","HEAD"]',
    'workspace.repository="DonkeyJJLove/ai_platform"',
    f'workspace.commit="{c2.EXPECTED_HEAD}"',
    f'workspace.tree="{c2.EXPECTED_TREE}"',
    f'workspace.path="{EXEC_ROOT}"',
    'environment.inherit=false',
    'environment.allow={"LC_ALL":"C","GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":"/dev/null","GIT_TERMINAL_PROMPT":"0","HOME":"/nonexistent"}',
    'io.stdin="NONE"',
    'io.stdout="CAPTURE"',
    'io.stderr="CAPTURE"',
    'io.tty=false',
]


def source(lines: list[str] | None = None) -> str:
    return "\n".join(lines or BASE) + "\n"


def replace_line(lines: list[str], prefix: str, value: str) -> list[str]:
    result = list(lines)
    for index, line in enumerate(result):
        if line.startswith(prefix):
            result[index] = value
            return result
    raise AssertionError(prefix)


def compiled(lines: list[str] | None = None):
    return lcms.compile_lcms(source(lines))


def live_lab_substrate_reason() -> str | None:
    if os.environ.get("LION_C2_TEST_FORCE_NO_LAB_SUBSTRATE") == "1":
        return "FORCED_TEST_PROJECTION"
    try:
        c2._verify_static_host_binding()
        if c2._probe_git("HEAD") != c2.EXPECTED_HEAD:
            return "HEAD_DRIFT"
        if c2._probe_git("HEAD^{tree}") != c2.EXPECTED_TREE:
            return "TREE_DRIFT"
    except (OSError, ValueError, c2.C2AdmissionError) as exc:
        return type(exc).__name__
    return None


LIVE_LAB_SUBSTRATE_REASON = live_lab_substrate_reason()
LIVE_LAB_SKIP = "C2_LIVE_LAB_SUBSTRATE_UNAVAILABLE" + (f":{LIVE_LAB_SUBSTRATE_REASON}" if LIVE_LAB_SUBSTRATE_REASON else "")


class C2ReadOnlyProcessExecTests(unittest.TestCase):
    def c2_denied(self, lines: list[str], code: str) -> None:
        action = compiled(lines)
        with self.assertRaises(c2.C2AdmissionError) as ctx:
            c2.prepare(action)
        self.assertEqual(ctx.exception.code, code)

    def run_recipe(self, args: list[str]):
        lines = replace_line(BASE, "arguments=", "arguments=" + json.dumps(args, separators=(",", ":")))
        action = compiled(lines)
        spec = action.as_dict()
        _validate(spec, SCHEMA, SCHEMA)
        prepared = c2.prepare(action)
        observer = IndependentProcessObserver(EXEC_ROOT)
        execution, observation = c2.execute(prepared, observer)
        receipt = reconcile(prepared, execution, observation)
        return action, prepared, execution, observation, receipt

    @unittest.skipIf(LIVE_LAB_SUBSTRATE_REASON is not None, LIVE_LAB_SKIP)
    def test_positive_head_and_tree_exact_reconciliation(self):
        for args, expected in [
            (["rev-parse", "HEAD"], c2.EXPECTED_HEAD),
            (["rev-parse", "HEAD^{tree}"], c2.EXPECTED_TREE),
        ]:
            with self.subTest(args=args):
                action, prepared, execution, observation, receipt = self.run_recipe(args)
                self.assertTrue(action.digest.startswith("sha256:"))
                self.assertEqual(execution.stdout, (expected + "\n").encode("ascii"))
                self.assertEqual(execution.stderr, b"")
                self.assertEqual(execution.returncode, 0)
                self.assertFalse(observation.socket_seen)
                self.assertEqual(observation.child_pids, ())
                self.assertTrue(observation.target_exited)
                self.assertEqual(observation.workspace_before, observation.workspace_after)
                self.assertEqual(receipt.status, "MATCH")
                self.assertEqual(receipt.anomalies, ())

    def test_shell_raw_shell_and_environment_inheritance_fail_closed(self):
        with self.assertRaises(lcms.LCMSError) as ctx:
            compiled(replace_line(BASE, "boundary.shell=", "boundary.shell=true"))
        self.assertEqual(ctx.exception.code, "SHELL_TRUE")
        with self.assertRaises(lcms.LCMSError) as ctx:
            compiled(BASE + ['command="git rev-parse HEAD"'])
        self.assertEqual(ctx.exception.code, "RAW_SHELL_STRING")
        with self.assertRaises(lcms.LCMSError) as ctx:
            compiled(replace_line(BASE, "environment.inherit=", "environment.inherit=true"))
        self.assertEqual(ctx.exception.code, "ENVIRONMENT_INHERITANCE")

    def test_write_and_network_authority_are_denied_before_effect(self):
        self.c2_denied(replace_line(BASE, "boundary.filesystem_write=", 'boundary.filesystem_write=["/tmp"]'), "FILESYSTEM_WRITE")
        self.c2_denied(replace_line(BASE, "boundary.network=", 'boundary.network="READ_ONLY_PINNED"'), "NETWORK")

    def test_argv_injection_and_recipe_substitution_are_denied(self):
        for args in [
            ["rev-parse", "HEAD;touch /tmp/c2"],
            ["rev-parse", "origin/master"],
            ["status"],
            ["-c", "credential.helper=!echo bad"],
        ]:
            with self.subTest(args=args):
                self.c2_denied(replace_line(BASE, "arguments=", "arguments=" + json.dumps(args, separators=(",", ":"))), "ARGUMENT_SUBSTITUTION")

    def test_executable_workspace_target_and_authority_substitution_are_denied(self):
        python_digest = "17b78e0a93175e86f9ac03141924fd7a7f0c0c52e66b34bfa0de20ffef989df1"
        exe = replace_line(BASE, "executable.path=", 'executable.path="/usr/bin/python3"')
        exe = replace_line(exe, "executable.digest=", f'executable.digest="sha256:{python_digest}"')
        self.c2_denied(exe, "EXECUTABLE_SUBSTITUTION")
        self.c2_denied(replace_line(BASE, "workspace.path=", 'workspace.path="/tmp/not-c2"'), "WORKSPACE_SUBSTITUTION")
        self.c2_denied(replace_line(BASE, "target.host=", 'target.host="LAB-UBUNTU"'), "TARGET_SUBSTITUTION")
        self.c2_denied(replace_line(BASE, "authority_request.capability=", 'authority_request.capability="test.execute"'), "AUTHORITY_SUBSTITUTION")

    def test_digest_commit_tree_and_remote_currentness_fail_closed(self):
        self.c2_denied(replace_line(BASE, "executable.digest=", 'executable.digest="sha256:' + "0" * 64 + '"'), "EXECUTABLE_SUBSTITUTION")
        self.c2_denied(replace_line(BASE, "workspace.commit=", 'workspace.commit="' + "0" * 40 + '"'), "WORKSPACE_SUBSTITUTION")
        self.c2_denied(replace_line(BASE, "workspace.tree=", 'workspace.tree="' + "0" * 40 + '"'), "WORKSPACE_SUBSTITUTION")
        with mock.patch.object(Path, "read_text", return_value='[remote "origin"]\nurl=https://example.invalid/x\n'):
            with self.assertRaises(c2.C2AdmissionError) as ctx:
                c2._assert_no_remote()
        self.assertEqual(ctx.exception.code, "NETWORK_ROUTE_PRESENT")

    def test_effect_time_currentness_is_rechecked_before_target_spawn(self):
        with mock.patch.object(c2, "_verify_static_host_binding", return_value=None):
            prepared = c2.prepare(compiled())
        observer = mock.Mock()
        observer.start_pid_observation = mock.Mock()
        observer.finish = mock.Mock()
        with mock.patch.object(c2, "_verify_static_host_binding", return_value=None), mock.patch.object(c2, "_sha256_file", return_value=c2.TARGET_EXECUTABLE_SHA256), mock.patch.object(c2, "_probe_git", return_value="0" * 40), mock.patch.object(c2.subprocess, "Popen") as popen:
            with self.assertRaises(c2.C2AdmissionError) as ctx:
                c2.execute(prepared, observer)
        self.assertEqual(ctx.exception.code, "HEAD_DRIFT")
        popen.assert_not_called()
        observer.start_pid_observation.assert_not_called()

    def test_effect_time_executable_drift_is_denied_before_git_probe_and_target_spawn(self):
        with mock.patch.object(c2, "_verify_static_host_binding", return_value=None):
            prepared = c2.prepare(compiled())
        observer = mock.Mock()
        observer.start_pid_observation = mock.Mock()
        observer.finish = mock.Mock()
        with (
            mock.patch.object(c2, "_verify_static_host_binding", return_value=None),
            mock.patch.object(c2, "_sha256_file", return_value="0" * 64),
            mock.patch.object(c2, "_probe_git") as probe_git,
            mock.patch.object(c2.subprocess, "Popen") as popen,
        ):
            with self.assertRaises(c2.C2AdmissionError) as ctx:
                c2.execute(prepared, observer)
        self.assertEqual(ctx.exception.code, "EXECUTABLE_DRIFT")
        probe_git.assert_not_called()
        popen.assert_not_called()
        observer.start_pid_observation.assert_not_called()

    def test_resource_io_observer_and_environment_widening_are_denied(self):
        self.c2_denied(replace_line(BASE, "boundary.max_processes=", "boundary.max_processes=2"), "PROCESS_COUNT")
        self.c2_denied(replace_line(BASE, "boundary.timeout_ms=", "boundary.timeout_ms=5001"), "TIMEOUT")
        self.c2_denied(replace_line(BASE, "boundary.memory_limit_bytes=", "boundary.memory_limit_bytes=1073741824"), "MEMORY")
        with self.assertRaises(lcms.LCMSError) as ctx:
            compiled(replace_line(BASE, "io.tty=", "io.tty=true"))
        self.assertEqual(ctx.exception.code, "AMBIGUOUS_BOOLEAN")
        self.c2_denied(replace_line(BASE, "observation.observer_class=", 'observation.observer_class="deterministic_independent"'), "OBSERVER")
        widened_env = replace_line(BASE, "environment.allow=", 'environment.allow={"LC_ALL":"C","GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":"/dev/null","GIT_TERMINAL_PROMPT":"0","HOME":"/nonexistent","PATH":"/usr/bin"}')
        self.c2_denied(widened_env, "ENVIRONMENT")

    @unittest.skipIf(LIVE_LAB_SUBSTRATE_REASON is not None, LIVE_LAB_SKIP)
    def test_exit_zero_is_not_sufficient_for_success(self):
        _, prepared, execution, observation, receipt = self.run_recipe(["rev-parse", "HEAD"])
        self.assertEqual(receipt.status, "MATCH")
        bad_output = replace(execution, stdout=b"wrong\n")
        bad_receipt = reconcile(prepared, bad_output, observation)
        self.assertEqual(bad_receipt.status, "MISMATCH")
        self.assertIn("STDOUT_MISMATCH", bad_receipt.anomalies)
        bad_observation = replace(observation, socket_seen=True)
        bad_receipt = reconcile(prepared, execution, bad_observation)
        self.assertEqual(bad_receipt.status, "MISMATCH")
        self.assertIn("SOCKET_OBSERVED", bad_receipt.anomalies)
        changed = replace(observation.workspace_after, digest="0" * 64)
        bad_observation = replace(observation, workspace_after=changed)
        bad_receipt = reconcile(prepared, execution, bad_observation)
        self.assertEqual(bad_receipt.status, "MISMATCH")
        self.assertIn("WORKSPACE_MUTATION", bad_receipt.anomalies)

    def test_capability_separation_and_no_generic_transport_surface(self):
        exec_source = Path(c2.__file__).read_text(encoding="utf-8")
        observer_source = Path(observer_module.__file__).read_text(encoding="utf-8")
        recon_source = Path(reconciliation_module.__file__).read_text(encoding="utf-8")
        self.assertIn("shell=False", exec_source)
        self.assertIn('\"-Urn\"', exec_source)
        self.assertIn('\"--map-current-user\"', exec_source)
        for token in ("socket", "urllib", "http.client", "requests", "credential_env", "merge_pull_request"):
            self.assertNotIn(token, exec_source)
        for source_text in (observer_source, recon_source):
            tree = ast.parse(source_text)
            imports = {node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import) and node.names}
            self.assertNotIn("subprocess", imports)
            self.assertNotIn("socket", imports)
            calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
            self.assertNotIn("Popen", calls)
            self.assertNotIn("run", calls)

    @unittest.skipIf(LIVE_LAB_SUBSTRATE_REASON is not None, LIVE_LAB_SKIP)
    def test_sandbox_and_executable_identities_are_exact(self):
        self.assertEqual(c2._sha256_file(c2.TARGET_EXECUTABLE), c2.TARGET_EXECUTABLE_SHA256)
        self.assertEqual(c2._sha256_file(c2.SANDBOX_WRAPPER), c2.SANDBOX_WRAPPER_SHA256)
        self.assertEqual(c2._sandbox_argv(c2.TARGET_EXECUTABLE, ("rev-parse", "HEAD")), ["/usr/bin/unshare", "-Urn", "--map-current-user", "--", "/usr/bin/git", "rev-parse", "HEAD"])


if __name__ == "__main__":
    unittest.main()

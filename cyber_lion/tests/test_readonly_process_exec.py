from __future__ import annotations

from hashlib import sha256
import inspect
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.lcms import compile_lcms
from cyber_lion.readonly_process_exec import (
    C2ReplayGuard,
    ReadonlyProcessAdapter,
    ReadonlyProcessError,
)
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner

ROOT = Path(__file__).resolve().parents[2]
DUMMY_HEAD = "1" * 40
DUMMY_TREE = "2" * 40
DUMMY_EXEC = "0" * 64


def source(workspace: str, *, network: str = "DENY", writes: str = "[]", children: str = "[]", executable_digest: str = DUMMY_EXEC) -> str:
    return f'''ACTION c2.readonly.1 {{
    schema_version = "lion.action-spec/v1.3-candidate";
    kind = "process.exec";
    intent_ref = "intent:c2-readonly";
    mission_ref = "mission:c2";
    autonomy_ref = "autonomy:lion";
    bean_ref = "bean:c2-readonly-process";
    target {{
        host = "LAB-DEBIAN";
        environment = "WSL2";
        runtime = "local-console-test-only";
    }}
    executable {{
        path = "/usr/bin/python3";
        digest = "sha256:{executable_digest}";
    }}
    arguments = ["-m","cyber_lion.tests.c2_readonly_probe"];
    workspace {{
        repository = "DonkeyJJLove/ai_platform";
        commit = "{DUMMY_HEAD}";
        tree = "{DUMMY_TREE}";
        path = "{workspace}";
    }}
    environment {{
        inherit = false;
        allow = {{"PYTHONHASHSEED":"0"}};
    }}
    io {{
        stdin = "NONE";
        stdout = "CAPTURE";
        stderr = "CAPTURE";
        tty = false;
    }}
    authority_request {{
        domain = "local.test-only";
        capability = "read-only-process";
        grant_ref = null;
    }}
    boundary {{
        shell = false;
        network = "{network}";
        filesystem_read = ["/workspace/**","/etc/**","/usr/**"];
        filesystem_write = {writes};
        process_children = {children};
        timeout_ms = 5000;
        max_processes = 1;
        memory_limit_bytes = 536870912;
    }}
    preconditions = ["C0 exact","C1 exact","workspace exact","executable exact"];
    expected_effects = ["one bounded test-only local process","read-only observations"];
    forbidden_effects = ["credential access","network effect","repository mutation","service mutation"];
    observation {{
        observer_class = "deterministic_independent";
        required_events = ["child-process-closure","filesystem-delta","network-delta","process-exit"];
    }}
    reconciliation {{
        mode = "EXACT";
        receipt = "REQUIRED";
    }}
}}\n'''


class ReadonlyProcessExecTests(unittest.TestCase):
    def _compiled(self, workspace: str, **kw):
        return compile_lcms(source(workspace, **kw))

    def test_exact_gate_binds_ir_executable_argv_and_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            compiled = self._compiled(td)
            adapter = ReadonlyProcessAdapter(run_id="C2-R1")
            with patch("cyber_lion.readonly_process_exec._git_head_tree", return_value=(DUMMY_HEAD, DUMMY_TREE)), \
                 patch("cyber_lion.readonly_process_exec._workspace_snapshot", return_value="3" * 64), \
                 patch("cyber_lion.readonly_process_exec._file_sha256", return_value=DUMMY_EXEC):
                gate = adapter.issue_gate(compiled=compiled, workspace_root=Path(td))
            self.assertEqual(gate.action_ir_digest, compiled.canonical_ir_digest)
            self.assertEqual(gate.executable_sha256, DUMMY_EXEC)
            self.assertEqual(gate.workspace_head, DUMMY_HEAD)
            self.assertEqual(gate.workspace_tree, DUMMY_TREE)
            self.assertEqual(gate.workspace_snapshot_digest, "3" * 64)

    def test_network_write_and_children_requests_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = ReadonlyProcessAdapter(run_id="C2-R1")
            for compiled in (
                self._compiled(td, network="ALLOW_EXACT"),
                self._compiled(td, writes='["/tmp/**"]'),
                self._compiled(td, children='["/usr/bin/python3"]'),
            ):
                with self.subTest(ir=compiled.canonical_ir):
                    with self.assertRaises(ReadonlyProcessError):
                        adapter._validate_ir(compiled)

    def test_executable_substitution_fails_before_effect(self):
        with tempfile.TemporaryDirectory() as td:
            compiled = self._compiled(td)
            adapter = ReadonlyProcessAdapter(run_id="C2-R1")
            with patch("cyber_lion.readonly_process_exec._git_head_tree", return_value=(DUMMY_HEAD, DUMMY_TREE)), \
                 patch("cyber_lion.readonly_process_exec._workspace_snapshot", return_value="3" * 64), \
                 patch("cyber_lion.readonly_process_exec._file_sha256", return_value="f" * 64):
                with self.assertRaisesRegex(ReadonlyProcessError, "executable digest substitution"):
                    adapter.issue_gate(compiled=compiled, workspace_root=Path(td))

    def test_workspace_currentness_substitution_fails_before_effect(self):
        with tempfile.TemporaryDirectory() as td:
            compiled = self._compiled(td)
            adapter = ReadonlyProcessAdapter(run_id="C2-R1")
            with patch("cyber_lion.readonly_process_exec._git_head_tree", return_value=("9" * 40, DUMMY_TREE)), \
                 patch("cyber_lion.readonly_process_exec._workspace_snapshot", return_value="3" * 64), \
                 patch("cyber_lion.readonly_process_exec._file_sha256", return_value=DUMMY_EXEC):
                with self.assertRaisesRegex(ReadonlyProcessError, "workspace currentness"):
                    adapter.issue_gate(compiled=compiled, workspace_root=Path(td))

    def test_replay_guard_is_one_shot(self):
        guard = C2ReplayGuard()
        self.assertTrue(guard.consume("a" * 64))
        self.assertFalse(guard.consume("a" * 64))

    def test_sandbox_root_must_be_direct_child_of_system_tmp(self):
        module = __import__("cyber_lion.readonly_process_exec", fromlist=["x"])
        system_tmp = (Path(os.sep) / "tmp").resolve()
        module._require_isolated_sandbox_root(system_tmp / "lion-c2-valid")
        with self.assertRaisesRegex(ReadonlyProcessError, "direct child"):
            module._require_isolated_sandbox_root((Path(os.sep) / "var" / "tmp" / "lion-c2-invalid").resolve())
        with self.assertRaisesRegex(ReadonlyProcessError, "direct child"):
            module._require_isolated_sandbox_root(system_tmp / "nested" / "lion-c2-invalid")

    def test_no_direct_command_surface_is_exported(self):
        module_source = inspect.getsource(__import__("cyber_lion.readonly_process_exec", fromlist=["x"]))
        self.assertNotIn('if __name__ == "__main__"', module_source)
        self.assertNotIn('"--sandbox-helper"', module_source)
        self.assertNotIn('startswith("/tmp/")', module_source)

    def test_effect_inventory_is_explicit_and_classified(self):
        path = "cyber_lion/readonly_process_exec.py"
        inventory = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="1" * 40,
            tree_digest="2" * 40,
            sources={path: (ROOT / path).read_text(encoding="utf-8")},
        )
        refs = [ref for surface in inventory.surfaces for ref in surface.entrypoints]
        self.assertTrue(any("subprocess.Popen" in ref for ref in refs))
        self.assertTrue(any("write_text" in ref for ref in refs))
        self.assertTrue(any("os.execve" in ref for ref in refs))
        self.assertEqual(inventory.unclassified_refs, ())

    def test_target_probe_is_test_only_and_not_production_source(self):
        probe = ROOT / "cyber_lion/tests/c2_readonly_probe.py"
        self.assertTrue(probe.is_file())
        inventory = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="1" * 40,
            tree_digest="2" * 40,
            sources={"cyber_lion/tests/c2_readonly_probe.py": probe.read_text(encoding="utf-8")},
        )
        self.assertEqual(inventory.surfaces, ())


if __name__ == "__main__":
    unittest.main()

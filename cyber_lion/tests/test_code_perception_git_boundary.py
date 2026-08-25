from __future__ import annotations

import inspect
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.enterprise import code_perception
from cyber_lion.enterprise.code_perception_git_boundary import (
    ALLOWED_OPERATIONS,
    CodePerceptionGitBoundary,
    GitReadBoundaryError,
    HASH_STDIN,
    LIST_TREE,
    READ_BLOB,
    RESOLVE_COMMIT,
    RESOLVE_TREE,
)


class CodePerceptionGitBoundaryTests(unittest.TestCase):
    def test_closed_world_operation_enum(self):
        self.assertEqual(ALLOWED_OPERATIONS, {RESOLVE_COMMIT, RESOLVE_TREE, LIST_TREE, READ_BLOB, HASH_STDIN})
        self.assertNotIn("PUSH", ALLOWED_OPERATIONS)
        self.assertNotIn("UPDATE_REF", ALLOWED_OPERATIONS)
        self.assertNotIn("CHECKOUT", ALLOWED_OPERATIONS)
        self.assertNotIn("CLEAN", ALLOWED_OPERATIONS)

    def test_code_perception_has_no_direct_subprocess_run(self):
        source = inspect.getsource(code_perception)
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("subprocess.run", source)
        self.assertIn("CodePerceptionGitBoundary", source)

    def test_raw_argv_surface_is_not_exposed(self):
        boundary = CodePerceptionGitBoundary()
        public = {name for name in dir(boundary) if not name.startswith("_")}
        self.assertNotIn("run", public)
        self.assertNotIn("execute", public)
        self.assertNotIn("command", public)

    def test_commit_reference_injection_is_denied_before_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            boundary = CodePerceptionGitBoundary()
            with patch("cyber_lion.enterprise.code_perception_git_boundary.subprocess.run") as run:
                with self.assertRaises(GitReadBoundaryError):
                    boundary.resolve_commit(tmp, "r", "--upload-pack=evil")
                run.assert_not_called()

    def test_environment_is_minimal_and_forces_read_safety(self):
        old = os.environ.get("GIT_DIR")
        os.environ["GIT_DIR"] = "/tmp/evil"
        try:
            env = CodePerceptionGitBoundary._minimal_env()
        finally:
            if old is None:
                os.environ.pop("GIT_DIR", None)
            else:
                os.environ["GIT_DIR"] = old
        self.assertNotIn("GIT_DIR", env)
        self.assertNotIn("GIT_WORK_TREE", env)
        self.assertNotIn("GIT_INDEX_FILE", env)
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(env["GIT_OPTIONAL_LOCKS"], "0")

    def test_process_argv_is_fixed_and_shell_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed = subprocess.CompletedProcess([], 0, b"a" * 40 + b"\n", b"")
            with patch("cyber_lion.enterprise.code_perception_git_boundary.subprocess.run", return_value=completed) as run:
                value = CodePerceptionGitBoundary().resolve_commit(root, "repo", "HEAD")
            self.assertEqual(value, "a" * 40)
            argv = run.call_args.args[0]
            self.assertEqual(argv[:4], ["git", "-C", str(root.resolve()), "rev-parse"])
            self.assertEqual(argv[-1], "HEAD^{commit}")
            self.assertIs(run.call_args.kwargs["shell"], False)
            self.assertIs(run.call_args.kwargs["check"], False)
            self.assertIn("timeout", run.call_args.kwargs)

    def test_malformed_object_id_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.CompletedProcess([], 0, b"not-a-sha\n", b"")
            with patch("cyber_lion.enterprise.code_perception_git_boundary.subprocess.run", return_value=completed):
                with self.assertRaises(GitReadBoundaryError):
                    CodePerceptionGitBoundary().resolve_commit(tmp, "repo", "HEAD")

    def test_oversized_small_output_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.CompletedProcess([], 0, b"x" * 300, b"")
            with patch("cyber_lion.enterprise.code_perception_git_boundary.subprocess.run", return_value=completed):
                with self.assertRaises(GitReadBoundaryError):
                    CodePerceptionGitBoundary().resolve_commit(tmp, "repo", "HEAD")

    def test_stderr_flood_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.CompletedProcess([], 0, b"a" * 40 + b"\n", b"x" * 70000)
            with patch("cyber_lion.enterprise.code_perception_git_boundary.subprocess.run", return_value=completed):
                with self.assertRaises(GitReadBoundaryError):
                    CodePerceptionGitBoundary().resolve_commit(tmp, "repo", "HEAD")

    def test_timeout_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "cyber_lion.enterprise.code_perception_git_boundary.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["git"], 1),
            ):
                with self.assertRaises(GitReadBoundaryError):
                    CodePerceptionGitBoundary(timeout_seconds=1).resolve_commit(tmp, "repo", "HEAD")

    def test_blob_size_substitution_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.CompletedProcess([], 0, b"abc", b"")
            with patch("cyber_lion.enterprise.code_perception_git_boundary.subprocess.run", return_value=completed):
                with self.assertRaises(GitReadBoundaryError):
                    CodePerceptionGitBoundary().read_blob(
                        tmp, "repo", "a" * 40, "b" * 40, "c" * 40, 4
                    )

    def test_hash_stdin_uses_only_hash_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.CompletedProcess([], 0, b"d" * 40 + b"\n", b"")
            with patch("cyber_lion.enterprise.code_perception_git_boundary.subprocess.run", return_value=completed) as run:
                value = CodePerceptionGitBoundary().hash_stdin(
                    tmp, "repo", "a" * 40, "b" * 40, b"payload"
                )
            self.assertEqual(value, "d" * 40)
            self.assertEqual(run.call_args.args[0][-2:], ["hash-object", "--stdin"])
            self.assertEqual(run.call_args.kwargs["input"], b"payload")


if __name__ == "__main__":
    unittest.main()

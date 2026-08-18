"""Bounded local build runner for generated Startup Evolution scaffolds.

This is NOT an operating-system security sandbox. It is a constrained local execution
primitive for trusted Cyber-Lion templates: paths are validated, files are written only
under a temporary root, subprocess calls never use a shell, environment inheritance is
minimized and execution is time-bounded.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, Optional

from .build_planner import SoftwareBuildSpec
from .models import StartupModelError


@dataclass(frozen=True)
class BuildReceipt:
    spec_id: str
    status: str
    compile_returncode: int
    test_returncode: int
    files_written: tuple[str, ...]
    stdout: str
    stderr: str


class BoundedLocalBuildRunner:
    """Materialize and test a trusted in-memory scaffold in an ephemeral directory."""

    def __init__(self, *, timeout_seconds: float = 20.0) -> None:
        if timeout_seconds <= 0:
            raise StartupModelError("timeout_seconds must be positive")
        self.timeout_seconds = float(timeout_seconds)

    @staticmethod
    def _validate_files(files: Dict[str, str]) -> None:
        if not files:
            raise StartupModelError("build scaffold cannot be empty")
        for raw_path, content in files.items():
            path = PurePosixPath(raw_path)
            if path.is_absolute() or ".." in path.parts:
                raise StartupModelError(f"unsafe scaffold path: {raw_path}")
            if not raw_path or raw_path.endswith("/"):
                raise StartupModelError(f"file path required: {raw_path}")
            if not isinstance(content, str):
                raise StartupModelError(f"scaffold content must be text: {raw_path}")

    @staticmethod
    def _minimal_env() -> Dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        if os.name == "nt":
            for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
                if key in os.environ:
                    env[key] = os.environ[key]
        else:
            env["HOME"] = "/tmp"
        return env

    def run(self, spec: SoftwareBuildSpec, files: Dict[str, str]) -> BuildReceipt:
        spec.validate()
        self._validate_files(files)
        if spec.authority_class not in {"analysis", "local_prototype"}:
            raise StartupModelError(
                f"bounded local build may not execute authority class {spec.authority_class!r}"
            )

        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        written: list[str] = []
        with tempfile.TemporaryDirectory(prefix="cyber-lion-build-") as tmp:
            root = Path(tmp).resolve()
            for raw_path, content in sorted(files.items()):
                destination = (root / Path(*PurePosixPath(raw_path).parts)).resolve()
                if root != destination and root not in destination.parents:
                    raise StartupModelError(f"scaffold escaped build root: {raw_path}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf-8")
                written.append(raw_path)

            compile_result = self._run_command(
                [sys.executable, "-m", "compileall", "-q", "."],
                cwd=root,
            )
            stdout_parts.append(compile_result.stdout)
            stderr_parts.append(compile_result.stderr)

            if compile_result.returncode != 0:
                return BuildReceipt(
                    spec.spec_id,
                    "COMPILE_FAILED",
                    compile_result.returncode,
                    -1,
                    tuple(written),
                    "".join(stdout_parts),
                    "".join(stderr_parts),
                )

            test_result = self._run_command(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
                cwd=root,
            ) if (root / "tests").exists() else subprocess.CompletedProcess([], 0, "", "")
            stdout_parts.append(test_result.stdout)
            stderr_parts.append(test_result.stderr)

            status = "PASS" if test_result.returncode == 0 else "TEST_FAILED"
            return BuildReceipt(
                spec.spec_id,
                status,
                compile_result.returncode,
                test_result.returncode,
                tuple(written),
                "".join(stdout_parts),
                "".join(stderr_parts),
            )

    def _run_command(self, argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                argv,
                cwd=str(cwd),
                env=self._minimal_env(),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise StartupModelError(f"local build command timed out after {self.timeout_seconds}s") from exc

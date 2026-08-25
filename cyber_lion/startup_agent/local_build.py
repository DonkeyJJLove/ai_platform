"""Bounded local build runner with a mandatory pre-effect execution gate.

R9D closes the direct Startup Evolution local subprocess path: callers cannot execute
compile/test effects without an exact, spec-bound gate. The gate is consumed once before
any filesystem mutation or process launch, raw command execution is unavailable outside
an active admitted run, and PASS requires post-effect observation rather than return-code
alone. This is still not an operating-system security sandbox.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import Dict

from .build_planner import SoftwareBuildSpec
from .models import StartupModelError


def _gate_digest(*, gate_event_id: str, spec_id: str, authority_class: str, nonce: str) -> str:
    raw = "\0".join((gate_event_id, spec_id, authority_class, nonce)).encode("utf-8")
    return sha256(b"LION/STARTUP-LOCAL-BUILD-GATE/1\0" + raw).hexdigest()


@dataclass(frozen=True)
class LocalBuildExecutionGate:
    """Externally supplied, exact-spec execution admission; descriptive, not authority minting."""

    gate_event_id: str
    spec_id: str
    authority_class: str
    nonce: str
    gate_digest: str

    @classmethod
    def seal(cls, *, gate_event_id: str, spec_id: str, authority_class: str, nonce: str) -> "LocalBuildExecutionGate":
        if not all(isinstance(x, str) and x.strip() for x in (gate_event_id, spec_id, authority_class, nonce)):
            raise StartupModelError("local build gate fields must be non-empty")
        return cls(
            gate_event_id,
            spec_id,
            authority_class,
            nonce,
            _gate_digest(
                gate_event_id=gate_event_id,
                spec_id=spec_id,
                authority_class=authority_class,
                nonce=nonce,
            ),
        )

    def validate(self) -> "LocalBuildExecutionGate":
        if type(self) is not LocalBuildExecutionGate:
            raise StartupModelError("exact LocalBuildExecutionGate required")
        expected = _gate_digest(
            gate_event_id=self.gate_event_id,
            spec_id=self.spec_id,
            authority_class=self.authority_class,
            nonce=self.nonce,
        )
        if self.gate_digest != expected:
            raise StartupModelError("local build gate digest mismatch")
        return self


@dataclass(frozen=True)
class LocalBuildEffectObservation:
    phase: str
    command_digest: str
    returncode: int
    workspace_digest: str
    observed: bool


@dataclass(frozen=True)
class BuildReceipt:
    spec_id: str
    status: str
    compile_returncode: int
    test_returncode: int
    files_written: tuple[str, ...]
    stdout: str
    stderr: str
    gate_digest: str = ""
    observation_digests: tuple[str, ...] = ()


class LocalBuildEffectObserver:
    """Separate observer component for the bounded local build effect."""

    @staticmethod
    def observe(*, phase: str, argv: list[str], cwd: Path, result: subprocess.CompletedProcess[str]) -> LocalBuildEffectObservation:
        if phase not in {"compile", "test"}:
            raise StartupModelError("unknown local build observation phase")
        if not cwd.exists() or not cwd.is_dir():
            raise StartupModelError("local build workspace unavailable for observation")
        if not isinstance(result.returncode, int) or isinstance(result.returncode, bool):
            raise StartupModelError("local build process result invalid")
        command_digest = sha256("\0".join(argv).encode("utf-8")).hexdigest()
        entries = sorted(str(p.relative_to(cwd)) for p in cwd.rglob("*") if p.is_file())
        workspace_digest = sha256("\n".join(entries).encode("utf-8")).hexdigest()
        return LocalBuildEffectObservation(phase, command_digest, result.returncode, workspace_digest, True)


class BoundedLocalBuildRunner:
    """Materialize/test a trusted scaffold only behind one exact consumed execution gate."""

    def __init__(self, *, timeout_seconds: float = 20.0, observer: LocalBuildEffectObserver | None = None) -> None:
        if timeout_seconds <= 0:
            raise StartupModelError("timeout_seconds must be positive")
        self.timeout_seconds = float(timeout_seconds)
        self._observer = observer or LocalBuildEffectObserver()
        if type(self._observer) is not LocalBuildEffectObserver:
            raise StartupModelError("exact local build observer required")
        self._lock = Lock()
        self._consumed_gates: set[str] = set()
        self._active_gate_digest: str | None = None

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
    def _minimal_env(root: Path) -> Dict[str, str]:
        home = root / ".home"
        temp = root / ".tmp"
        home.mkdir(mode=0o700, exist_ok=True)
        temp.mkdir(mode=0o700, exist_ok=True)
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": str(home),
            "TMPDIR": str(temp),
            "TMP": str(temp),
            "TEMP": str(temp),
        }
        if os.name == "nt":
            env["USERPROFILE"] = str(home)
            for key in ("SYSTEMROOT", "WINDIR"):
                if key in os.environ:
                    env[key] = os.environ[key]
        return env

    def _admit(self, *, spec: SoftwareBuildSpec, gate: LocalBuildExecutionGate) -> str:
        gate.validate()
        if (gate.spec_id, gate.authority_class) != (spec.spec_id, spec.authority_class):
            raise StartupModelError("local build gate/spec binding mismatch")
        if spec.authority_class not in {"analysis", "local_prototype"}:
            raise StartupModelError(
                f"bounded local build may not execute authority class {spec.authority_class!r}"
            )
        with self._lock:
            if self._active_gate_digest is not None:
                raise StartupModelError("local build runner already executing")
            if gate.gate_digest in self._consumed_gates:
                raise StartupModelError("local build gate replay denied")
            self._consumed_gates.add(gate.gate_digest)
            self._active_gate_digest = gate.gate_digest
        return gate.gate_digest

    def _release(self, gate_digest: str) -> None:
        with self._lock:
            if self._active_gate_digest != gate_digest:
                raise StartupModelError("local build active gate continuity lost")
            self._active_gate_digest = None

    def run(self, spec: SoftwareBuildSpec, files: Dict[str, str], *, gate: LocalBuildExecutionGate) -> BuildReceipt:
        spec.validate()
        self._validate_files(files)
        gate_digest = self._admit(spec=spec, gate=gate)
        observations: list[LocalBuildEffectObservation] = []
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        written: list[str] = []
        try:
            with tempfile.TemporaryDirectory(prefix="cyber-lion-build-") as tmp:
                root = Path(tmp).resolve()
                for raw_path, content in sorted(files.items()):
                    destination = (root / Path(*PurePosixPath(raw_path).parts)).resolve()
                    if root != destination and root not in destination.parents:
                        raise StartupModelError(f"scaffold escaped build root: {raw_path}")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(content, encoding="utf-8")
                    if destination.read_text(encoding="utf-8") != content:
                        raise StartupModelError("local build write observation mismatch")
                    written.append(raw_path)

                compile_argv = [sys.executable, "-m", "compileall", "-q", "."]
                compile_result = self._run_command(compile_argv, cwd=root, gate_digest=gate_digest)
                observations.append(self._observer.observe(phase="compile", argv=compile_argv, cwd=root, result=compile_result))
                stdout_parts.append(compile_result.stdout)
                stderr_parts.append(compile_result.stderr)

                if compile_result.returncode != 0 or not observations[-1].observed:
                    return BuildReceipt(
                        spec.spec_id,
                        "COMPILE_FAILED",
                        compile_result.returncode,
                        -1,
                        tuple(written),
                        "".join(stdout_parts),
                        "".join(stderr_parts),
                        gate_digest,
                        tuple(self._observation_digest(x) for x in observations),
                    )

                if (root / "tests").exists():
                    test_argv = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]
                    test_result = self._run_command(test_argv, cwd=root, gate_digest=gate_digest)
                    observations.append(self._observer.observe(phase="test", argv=test_argv, cwd=root, result=test_result))
                else:
                    test_result = subprocess.CompletedProcess([], 0, "", "")
                stdout_parts.append(test_result.stdout)
                stderr_parts.append(test_result.stderr)

                observed_ok = all(item.observed for item in observations)
                status = "PASS" if test_result.returncode == 0 and observed_ok else "TEST_FAILED"
                return BuildReceipt(
                    spec.spec_id,
                    status,
                    compile_result.returncode,
                    test_result.returncode,
                    tuple(written),
                    "".join(stdout_parts),
                    "".join(stderr_parts),
                    gate_digest,
                    tuple(self._observation_digest(x) for x in observations),
                )
        finally:
            self._release(gate_digest)

    @staticmethod
    def _observation_digest(value: LocalBuildEffectObservation) -> str:
        raw = "\0".join(
            (value.phase, value.command_digest, str(value.returncode), value.workspace_digest, str(value.observed))
        ).encode("utf-8")
        return sha256(b"LION/STARTUP-LOCAL-BUILD-OBS/1\0" + raw).hexdigest()

    def _run_command(self, argv: list[str], *, cwd: Path, gate_digest: str) -> subprocess.CompletedProcess[str]:
        with self._lock:
            if self._active_gate_digest != gate_digest:
                raise StartupModelError("local build process effect attempted outside admitted gate")
        allowed = {
            (sys.executable, "-m", "compileall", "-q", "."),
            (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"),
        }
        if tuple(argv) not in allowed:
            raise StartupModelError("local build command outside fixed allowlist")
        try:
            return subprocess.run(
                argv,
                cwd=str(cwd),
                env=self._minimal_env(cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise StartupModelError(f"local build command timed out after {self.timeout_seconds}s") from exc

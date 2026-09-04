"""C2 exact read-only process adapter for the LAB-DEBIAN experiment.

This is deliberately not a generic command runner. Only two exact local Git
observation recipes are admitted. The target runs with shell=False in a
same-UID user+network namespace with no configured route.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import resource
import subprocess
from typing import Any

from lcms import CompiledActionSpec

C2_ADAPTER_VERSION = "lion.c2.readonly-process-exec/v1.0-candidate"
EXPECTED_REPOSITORY = "DonkeyJJLove/ai_platform"
EXPECTED_HEAD = "0f75af9212a814177e08a5c206d1a8504b0937d5"
EXPECTED_TREE = "e722488cda090e62a379584c12f7cee8daa43de1"
EXPECTED_WORKSPACE = "/tmp/lion-c2-exec-workspace"
EXPECTED_HOST = "LAB-DEBIAN"
EXPECTED_ENVIRONMENT = "WSL2"
EXPECTED_RUNTIME = "local"

TARGET_EXECUTABLE = "/usr/bin/git"
TARGET_EXECUTABLE_SHA256 = "356db14e102d68a1a37d8a1ac577dfd678d45d46e92f468bef8b7154e7bfdc60"
SANDBOX_WRAPPER = "/usr/bin/unshare"
SANDBOX_WRAPPER_SHA256 = "d82900dfd64b5dd01493d206236575623c2dcf306c466dbe127e171c18cb4614"

SAFE_ENV = {
    "LC_ALL": "C",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
    "HOME": "/nonexistent",
}
EXPECTED_PRECONDITIONS = frozenset(
    {
        "repository.head == workspace.commit",
        "repository.tree == workspace.tree",
        "executable.digest == declared digest",
    }
)
EXPECTED_EFFECTS = frozenset(
    {
        "test process created",
        "stdout captured",
        "stderr captured",
        "exit status observed",
    }
)
FORBIDDEN_EFFECTS = frozenset(
    {
        "repository mutation",
        "network connection",
        "service mutation",
        "credential read",
        "background process survival",
    }
)
OBSERVATION_EVENTS = frozenset(
    {
        "process-exit",
        "filesystem-delta",
        "network-delta",
        "child-process-closure",
    }
)
ALLOWED_RECIPES = {
    ("rev-parse", "HEAD"): "HEAD",
    ("rev-parse", "HEAD^{tree}"): "TREE",
}


class C2AdmissionError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class PreparedReadOnlyProcess:
    action_spec_digest: str
    executable_path: str
    executable_digest: str
    arguments: tuple[str, ...]
    workspace: str
    workspace_commit: str
    workspace_tree: str
    environment: tuple[tuple[str, str], ...]
    timeout_ms: int
    memory_limit_bytes: int
    expected_stdout: bytes
    sandbox_wrapper_path: str
    sandbox_wrapper_digest: str


@dataclass(frozen=True)
class ProcessExecutionReceipt:
    adapter_version: str
    action_spec_digest: str
    executable_digest: str
    sandbox_wrapper_digest: str
    pid: int
    returncode: int
    stdout: bytes
    stderr: bytes
    execution_digest: str


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _require_exact_list(value: Any, expected: frozenset[str], code: str) -> None:
    if type(value) is not list or len(value) != len(expected) or frozenset(value) != expected:
        raise C2AdmissionError(code, "exact list binding mismatch")


def _assert_no_remote() -> None:
    config = Path(EXPECTED_WORKSPACE, ".git", "config").read_text(encoding="utf-8")
    if '[remote "' in config or "\nremote." in config:
        raise C2AdmissionError("NETWORK_ROUTE_PRESENT", "execution workspace still configures a Git remote")


def _verify_static_host_binding() -> None:
    if Path(EXPECTED_WORKSPACE).resolve(strict=True).as_posix() != EXPECTED_WORKSPACE:
        raise C2AdmissionError("WORKSPACE_SUBSTITUTION", "workspace path is not the exact trusted root")
    if _sha256_file(TARGET_EXECUTABLE) != TARGET_EXECUTABLE_SHA256:
        raise C2AdmissionError("EXECUTABLE_DRIFT", "target executable digest drifted")
    if _sha256_file(SANDBOX_WRAPPER) != SANDBOX_WRAPPER_SHA256:
        raise C2AdmissionError("SANDBOX_DRIFT", "network namespace wrapper digest drifted")
    _assert_no_remote()


def _sandbox_argv(executable: str, arguments: tuple[str, ...]) -> list[str]:
    return [SANDBOX_WRAPPER, "-Urn", "--map-current-user", "--", executable, *arguments]


def _preexec_limits(memory_limit_bytes: int) -> None:
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def _probe_git(expr: str) -> str:
    proc = subprocess.run(
        _sandbox_argv(TARGET_EXECUTABLE, ("rev-parse", expr)),
        cwd=EXPECTED_WORKSPACE,
        env=dict(SAFE_ENV),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        check=False,
        timeout=3.0,
    )
    if proc.returncode != 0 or proc.stderr:
        raise C2AdmissionError("CURRENTNESS_UNAVAILABLE", "fixed Git currentness probe failed")
    try:
        return proc.stdout.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise C2AdmissionError("CURRENTNESS_UNAVAILABLE", "Git currentness output is non-ASCII") from exc


def _effect_time_currentness(prepared: PreparedReadOnlyProcess) -> None:
    _verify_static_host_binding()
    if _sha256_file(prepared.executable_path) != prepared.executable_digest.removeprefix("sha256:"):
        raise C2AdmissionError("EXECUTABLE_DRIFT", "effect-time target executable drift")
    if _probe_git("HEAD") != prepared.workspace_commit:
        raise C2AdmissionError("HEAD_DRIFT", "effect-time HEAD mismatch")
    if _probe_git("HEAD^{tree}") != prepared.workspace_tree:
        raise C2AdmissionError("TREE_DRIFT", "effect-time tree mismatch")


def prepare(compiled: CompiledActionSpec) -> PreparedReadOnlyProcess:
    if not isinstance(compiled, CompiledActionSpec):
        raise C2AdmissionError("ACTION_SPEC_TYPE", "only canonical C1 CompiledActionSpec is accepted")
    spec = compiled.as_dict()
    if spec.get("kind") != "process.exec":
        raise C2AdmissionError("ACTION_KIND", "C2 accepts process.exec only")
    if spec.get("target") != {"host": EXPECTED_HOST, "environment": EXPECTED_ENVIRONMENT, "runtime": EXPECTED_RUNTIME}:
        raise C2AdmissionError("TARGET_SUBSTITUTION", "target binding mismatch")
    if spec.get("authority_request") != {"domain": "information.read", "capability": "repository.observe", "grant_ref": None}:
        raise C2AdmissionError("AUTHORITY_SUBSTITUTION", "C2 authority must remain READ_ONLY")
    boundary = spec.get("boundary")
    if type(boundary) is not dict:
        raise C2AdmissionError("BOUNDARY", "missing boundary")
    if boundary.get("shell") is not False:
        raise C2AdmissionError("SHELL", "shell must be false")
    if boundary.get("network") != "DENY":
        raise C2AdmissionError("NETWORK", "network must be DENY")
    if boundary.get("filesystem_read") != [EXPECTED_WORKSPACE]:
        raise C2AdmissionError("FILESYSTEM_READ_SCOPE", "read scope must equal exact workspace")
    if boundary.get("filesystem_write") != []:
        raise C2AdmissionError("FILESYSTEM_WRITE", "C2 has no filesystem write authority")
    if boundary.get("process_children") != [TARGET_EXECUTABLE]:
        raise C2AdmissionError("PROCESS_CHILDREN", "only the exact target executable may be represented")
    if boundary.get("max_processes") != 1:
        raise C2AdmissionError("PROCESS_COUNT", "max_processes must equal 1")
    timeout_ms = boundary.get("timeout_ms")
    if type(timeout_ms) is not int or not (1 <= timeout_ms <= 5000):
        raise C2AdmissionError("TIMEOUT", "timeout exceeds C2 read-only ceiling")
    memory_limit = boundary.get("memory_limit_bytes")
    if type(memory_limit) is not int or not (64 * 1024 * 1024 <= memory_limit <= 512 * 1024 * 1024):
        raise C2AdmissionError("MEMORY", "memory limit outside C2 ceiling")
    if spec.get("environment") != {"inherit": False, "allow": SAFE_ENV}:
        raise C2AdmissionError("ENVIRONMENT", "environment is not the exact non-inherited C2 environment")
    if spec.get("io") != {"stdin": "NONE", "stdout": "CAPTURE", "stderr": "CAPTURE", "tty": False}:
        raise C2AdmissionError("IO", "C2 requires noninteractive captured IO")
    if spec.get("workspace") != {"repository": EXPECTED_REPOSITORY, "commit": EXPECTED_HEAD, "tree": EXPECTED_TREE, "path": EXPECTED_WORKSPACE}:
        raise C2AdmissionError("WORKSPACE_SUBSTITUTION", "workspace exact binding mismatch")
    if spec.get("executable") != {"path": TARGET_EXECUTABLE, "digest": "sha256:" + TARGET_EXECUTABLE_SHA256}:
        raise C2AdmissionError("EXECUTABLE_SUBSTITUTION", "executable exact binding mismatch")
    arguments = spec.get("arguments")
    if type(arguments) is not list or any(type(x) is not str for x in arguments):
        raise C2AdmissionError("ARGUMENTS", "arguments must be a string array")
    args = tuple(arguments)
    recipe = ALLOWED_RECIPES.get(args)
    if recipe is None:
        raise C2AdmissionError("ARGUMENT_SUBSTITUTION", "argv is not an exact C2 catalog recipe")
    _require_exact_list(spec.get("preconditions"), EXPECTED_PRECONDITIONS, "PRECONDITIONS")
    _require_exact_list(spec.get("expected_effects"), EXPECTED_EFFECTS, "EXPECTED_EFFECTS")
    _require_exact_list(spec.get("forbidden_effects"), FORBIDDEN_EFFECTS, "FORBIDDEN_EFFECTS")
    observation = spec.get("observation")
    if type(observation) is not dict or observation.get("observer_class") != "independent":
        raise C2AdmissionError("OBSERVER", "independent observer is mandatory")
    _require_exact_list(observation.get("required_events"), OBSERVATION_EVENTS, "OBSERVATION_EVENTS")
    if spec.get("reconciliation") != {"mode": "EXACT", "receipt": "REQUIRED"}:
        raise C2AdmissionError("RECONCILIATION", "exact reconciliation receipt is mandatory")

    _verify_static_host_binding()
    expected = (EXPECTED_HEAD if recipe == "HEAD" else EXPECTED_TREE).encode("ascii") + b"\n"
    return PreparedReadOnlyProcess(
        action_spec_digest=compiled.digest,
        executable_path=TARGET_EXECUTABLE,
        executable_digest="sha256:" + TARGET_EXECUTABLE_SHA256,
        arguments=args,
        workspace=EXPECTED_WORKSPACE,
        workspace_commit=EXPECTED_HEAD,
        workspace_tree=EXPECTED_TREE,
        environment=tuple(sorted(SAFE_ENV.items())),
        timeout_ms=timeout_ms,
        memory_limit_bytes=memory_limit,
        expected_stdout=expected,
        sandbox_wrapper_path=SANDBOX_WRAPPER,
        sandbox_wrapper_digest="sha256:" + SANDBOX_WRAPPER_SHA256,
    )


def execute(prepared: PreparedReadOnlyProcess, observer: Any) -> tuple[ProcessExecutionReceipt, Any]:
    if not isinstance(prepared, PreparedReadOnlyProcess):
        raise C2AdmissionError("PREPARED_TYPE", "invalid prepared action")
    if not callable(getattr(observer, "start_pid_observation", None)) or not callable(getattr(observer, "finish", None)):
        raise C2AdmissionError("OBSERVER", "independent observer capability is required")

    _effect_time_currentness(prepared)
    proc = subprocess.Popen(
        _sandbox_argv(prepared.executable_path, prepared.arguments),
        cwd=prepared.workspace,
        env=dict(prepared.environment),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        close_fds=True,
        start_new_session=True,
        preexec_fn=lambda: _preexec_limits(prepared.memory_limit_bytes),
    )
    observer.start_pid_observation(proc.pid)
    try:
        stdout, stderr = proc.communicate(timeout=prepared.timeout_ms / 1000.0)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        proc.communicate()
        observer.finish(proc.pid)
        raise C2AdmissionError("TIMEOUT", "target exceeded exact timeout") from exc
    observation = observer.finish(proc.pid)
    if len(stdout) > 4096 or len(stderr) > 4096:
        raise C2AdmissionError("OUTPUT_BOUND", "captured output exceeds C2 fixed bound")
    payload = {
        "adapter_version": C2_ADAPTER_VERSION,
        "action_spec_digest": prepared.action_spec_digest,
        "executable_digest": prepared.executable_digest,
        "sandbox_wrapper_digest": prepared.sandbox_wrapper_digest,
        "returncode": proc.returncode,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()
    return ProcessExecutionReceipt(
        adapter_version=C2_ADAPTER_VERSION,
        action_spec_digest=prepared.action_spec_digest,
        executable_digest=prepared.executable_digest,
        sandbox_wrapper_digest=prepared.sandbox_wrapper_digest,
        pid=proc.pid,
        returncode=proc.returncode,
        stdout=stdout,
        stderr=stderr,
        execution_digest=digest,
    ), observation

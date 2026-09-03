from __future__ import annotations

import ctypes
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
from threading import Lock
import time
import zlib
from typing import Any

from cyber_lion.lcms import CompiledAction


class ReadonlyProcessError(RuntimeError):
    pass


C2_AUTHORITY_CLASS = "READ_ONLY/TEST_ONLY"
C2_SANDBOX_PROFILE = "linux-user-netns-landlock-seccomp/v1"
C2_DIGEST_DOMAIN = b"LION/C2-READONLY-PROCESS-EXEC/1\0"


def _system_tmp_root() -> Path:
    return (Path(os.sep) / "tmp").resolve()


def _require_isolated_sandbox_root(sandbox_root: Path) -> None:
    if sandbox_root.parent != _system_tmp_root():
        raise ReadonlyProcessError("sandbox root must be a direct child of the system temporary root")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _digest(value: Any) -> str:
    return sha256(C2_DIGEST_DOMAIN + _canonical(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    h = sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _workspace_snapshot(root: Path) -> str:
    rows: list[tuple[str, str, int]] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] == ".git":
            continue
        if path.is_symlink():
            rows.append((str(rel), "symlink:" + os.readlink(path), 0))
        elif path.is_file():
            rows.append((str(rel), _file_sha256(path), path.stat().st_mode & 0o7777))
        elif path.is_dir():
            rows.append((str(rel) + "/", "dir", path.stat().st_mode & 0o7777))
    return _digest(rows)


def _git_head_tree(root: Path) -> tuple[str, str]:
    git = root / ".git"
    if not git.is_dir():
        raise ReadonlyProcessError("workspace .git directory unavailable")
    head_text = (git / "HEAD").read_text(encoding="ascii").strip()
    if head_text.startswith("ref: "):
        ref = head_text[5:]
        ref_path = git / ref
        if ref_path.is_file():
            head = ref_path.read_text(encoding="ascii").strip()
        else:
            head = ""
            packed = git / "packed-refs"
            if packed.is_file():
                for line in packed.read_text(encoding="ascii").splitlines():
                    if line.startswith(("#", "^")) or not line:
                        continue
                    sha, name = line.split(" ", 1)
                    if name == ref:
                        head = sha
                        break
            if not head:
                raise ReadonlyProcessError("workspace HEAD ref unresolved")
    else:
        head = head_text
    if len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head):
        raise ReadonlyProcessError("workspace HEAD invalid")
    obj = git / "objects" / head[:2] / head[2:]
    if not obj.is_file():
        raise ReadonlyProcessError("workspace HEAD object is not loose")
    raw = zlib.decompress(obj.read_bytes())
    marker = b"\x00"
    if marker not in raw:
        raise ReadonlyProcessError("workspace commit object malformed")
    _, body = raw.split(marker, 1)
    first = body.splitlines()[0]
    if not first.startswith(b"tree "):
        raise ReadonlyProcessError("workspace commit tree unavailable")
    tree = first[5:].decode("ascii")
    if len(tree) != 40:
        raise ReadonlyProcessError("workspace tree invalid")
    return head, tree


@dataclass(frozen=True)
class C2ExecutionGate:
    gate_id: str
    authority_class: str
    action_ir_digest: str
    executable_sha256: str
    argv_digest: str
    workspace_head: str
    workspace_tree: str
    workspace_snapshot_digest: str
    sandbox_profile: str
    issued_for_run: str
    gate_digest: str = ""

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value = asdict(self)
        if not include_digest:
            value.pop("gate_digest")
        return value

    def compute_digest(self) -> str:
        return _digest(self.canonical_dict(include_digest=False))

    def sealed(self) -> "C2ExecutionGate":
        value = self.canonical_dict(include_digest=False)
        return C2ExecutionGate(**value, gate_digest=_digest(value)).validate()

    def validate(self) -> "C2ExecutionGate":
        if self.authority_class != C2_AUTHORITY_CLASS:
            raise ReadonlyProcessError("C2 authority class mismatch")
        if self.sandbox_profile != C2_SANDBOX_PROFILE:
            raise ReadonlyProcessError("C2 sandbox profile mismatch")
        for name in ("action_ir_digest", "executable_sha256", "argv_digest", "workspace_snapshot_digest", "gate_digest"):
            value = getattr(self, name)
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise ReadonlyProcessError(f"{name} invalid")
        for name in ("workspace_head", "workspace_tree"):
            value = getattr(self, name)
            if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
                raise ReadonlyProcessError(f"{name} invalid")
        if self.gate_digest != self.compute_digest():
            raise ReadonlyProcessError("C2 gate digest mismatch")
        return self


@dataclass(frozen=True)
class C2ProcessObservation:
    gate_digest: str
    action_ir_digest: str
    exit_code: int
    stdout_sha256: str
    stderr_sha256: str
    workspace_snapshot_before: str
    workspace_snapshot_after: str
    netns_parent: str
    netns_child: str
    seccomp_mode: int
    no_new_privs: int
    landlock_abi: int
    landlock_restricted: bool
    target_tmp_clean_after: bool
    target_pid_closed: bool
    elapsed_ms: int
    sandbox_attestation_digest: str

    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class C2ReconciliationRecord:
    status: str
    gate_digest: str
    observation_digest: str
    exact_currentness: bool
    filesystem_delta: bool
    independent_netns: bool
    seccomp_filter_active: bool
    no_new_privs: bool
    landlock_restricted: bool
    target_tmp_clean_after: bool
    child_process_closure: bool
    exit_success: bool
    replay_state: str

    def validate(self) -> "C2ReconciliationRecord":
        if self.status != "PASS":
            raise ReadonlyProcessError("C2 reconciliation did not pass")
        if not all((
            self.exact_currentness,
            not self.filesystem_delta,
            self.independent_netns,
            self.seccomp_filter_active,
            self.no_new_privs,
            self.landlock_restricted,
            self.target_tmp_clean_after,
            self.child_process_closure,
            self.exit_success,
            self.replay_state == "CONSUMED",
        )):
            raise ReadonlyProcessError("C2 reconciliation invariant failed")
        return self


@dataclass(frozen=True)
class C2ExecutionResult:
    stdout: bytes
    stderr: bytes
    observation: C2ProcessObservation
    reconciliation: C2ReconciliationRecord


class C2ReplayGuard:
    def __init__(self) -> None:
        self._lock = Lock()
        self._seen: set[str] = set()

    def consume(self, gate_digest: str) -> bool:
        with self._lock:
            if gate_digest in self._seen:
                return False
            self._seen.add(gate_digest)
            return True


class ReadonlyProcessAdapter:
    def __init__(self, *, run_id: str, replay_guard: C2ReplayGuard | None = None, timeout_seconds: float = 10.0) -> None:
        if not run_id or timeout_seconds <= 0:
            raise ReadonlyProcessError("invalid C2 adapter configuration")
        self.run_id = run_id
        self.replay_guard = replay_guard or C2ReplayGuard()
        self.timeout_seconds = float(timeout_seconds)

    @staticmethod
    def _validate_ir(compiled: CompiledAction) -> dict[str, Any]:
        if type(compiled) is not CompiledAction:
            raise ReadonlyProcessError("exact CompiledAction required")
        ir = compiled.canonical_ir
        if ir.get("kind") != "process.exec":
            raise ReadonlyProcessError("C2 accepts only process.exec")
        required = {"executable", "arguments", "workspace", "environment", "io"}
        if not required <= set(ir):
            raise ReadonlyProcessError("C2 process execution shape incomplete")
        boundary = ir["boundary"]
        if boundary.get("shell") is not False or boundary.get("network") != "DENY":
            raise ReadonlyProcessError("C2 requires shell=false and network=DENY")
        if boundary.get("filesystem_write"):
            raise ReadonlyProcessError("C2 read-only action cannot request filesystem writes")
        if boundary.get("process_children"):
            raise ReadonlyProcessError("C2 read-only action cannot request child processes")
        if ir["environment"].get("inherit") is not False:
            raise ReadonlyProcessError("C2 requires environment.inherit=false")
        io = ir["io"]
        if io.get("stdin") != "NONE" or io.get("tty") is not False:
            raise ReadonlyProcessError("C2 requires stdin=NONE and tty=false")
        executable = ir["executable"].get("path")
        if not isinstance(executable, str) or not executable.startswith("/"):
            raise ReadonlyProcessError("C2 requires absolute executable path")
        return ir

    @staticmethod
    def _action_digest(compiled: CompiledAction) -> str:
        return compiled.canonical_ir_digest

    def issue_gate(self, *, compiled: CompiledAction, workspace_root: Path) -> C2ExecutionGate:
        ir = self._validate_ir(compiled)
        workspace_root = workspace_root.resolve()
        ws = ir["workspace"]
        if Path(ws["path"]).as_posix() != workspace_root.as_posix():
            raise ReadonlyProcessError("workspace path substitution denied")
        head, tree = _git_head_tree(workspace_root)
        if (head, tree) != (ws["commit"], ws["tree"]):
            raise ReadonlyProcessError("workspace currentness mismatch")
        executable = Path(ir["executable"]["path"])
        if not executable.is_absolute() or not executable.is_file():
            raise ReadonlyProcessError("executable unavailable")
        executable_digest = _file_sha256(executable)
        if ir["executable"]["digest"] != "sha256:" + executable_digest:
            raise ReadonlyProcessError("executable digest substitution denied")
        argv = [str(executable), *ir["arguments"]]
        gate = C2ExecutionGate(
            gate_id="c2-gate:" + self._action_digest(compiled)[:24],
            authority_class=C2_AUTHORITY_CLASS,
            action_ir_digest=self._action_digest(compiled),
            executable_sha256=executable_digest,
            argv_digest=_digest(argv),
            workspace_head=head,
            workspace_tree=tree,
            workspace_snapshot_digest=_workspace_snapshot(workspace_root),
            sandbox_profile=C2_SANDBOX_PROFILE,
            issued_for_run=self.run_id,
        ).sealed()
        return gate

    def _revalidate(self, compiled: CompiledAction, gate: C2ExecutionGate, workspace_root: Path) -> tuple[dict[str, Any], str]:
        gate.validate()
        if gate.issued_for_run != self.run_id:
            raise ReadonlyProcessError("gate run substitution denied")
        ir = self._validate_ir(compiled)
        if self._action_digest(compiled) != gate.action_ir_digest:
            raise ReadonlyProcessError("Action IR substitution denied")
        head, tree = _git_head_tree(workspace_root)
        snapshot = _workspace_snapshot(workspace_root)
        if (head, tree, snapshot) != (gate.workspace_head, gate.workspace_tree, gate.workspace_snapshot_digest):
            raise ReadonlyProcessError("effect-time workspace currentness drift")
        executable = Path(ir["executable"]["path"])
        actual_exec = _file_sha256(executable)
        if actual_exec != gate.executable_sha256 or ir["executable"]["digest"] != "sha256:" + actual_exec:
            raise ReadonlyProcessError("effect-time executable substitution denied")
        argv = [str(executable), *ir["arguments"]]
        if _digest(argv) != gate.argv_digest:
            raise ReadonlyProcessError("effect-time argv substitution denied")
        return ir, snapshot

    def execute(self, *, compiled: CompiledAction, gate: C2ExecutionGate, workspace_root: Path, sandbox_root: Path) -> C2ExecutionResult:
        workspace_root = workspace_root.resolve()
        sandbox_root = sandbox_root.resolve()
        _require_isolated_sandbox_root(sandbox_root)
        ir, snapshot_before = self._revalidate(compiled, gate, workspace_root)
        if not self.replay_guard.consume(gate.gate_digest):
            raise ReadonlyProcessError("C2 execution replay denied")
        if sandbox_root.exists() and any(sandbox_root.iterdir()):
            raise ReadonlyProcessError("sandbox root must start empty")
        sandbox_root.mkdir(parents=True, exist_ok=True)
        parent_netns = os.readlink("/proc/self/ns/net")
        att_r, att_w = os.pipe()
        target_tmp = sandbox_root / "target-tmp"
        target_tmp.mkdir(mode=0o700, exist_ok=False)
        helper_payload = {
            "sandbox_root": str(sandbox_root),
            "target_tmp": str(target_tmp),
            "workspace_root": str(workspace_root),
            "executable": ir["executable"]["path"],
            "arguments": ir["arguments"],
            "environment": ir["environment"]["allow"],
            "memory_limit_bytes": ir["boundary"]["memory_limit_bytes"],
            "timeout_ms": ir["boundary"]["timeout_ms"],
            "attestation_fd": att_w,
        }
        helper_json = json.dumps(helper_payload, sort_keys=True, separators=(",", ":"))
        helper_path = sandbox_root / ".c2-sandbox-helper.py"
        helper_path.write_text(
            "import os, sys\n"
            "sys.path.insert(0, os.getcwd())\n"
            "from cyber_lion.readonly_process_exec import _sandbox_helper\n"
            "raise SystemExit(_sandbox_helper(sys.argv[1]))\n",
            encoding="utf-8",
        )
        launcher = [
            "/usr/bin/unshare",
            "--user",
            "--map-root-user",
            "--mount",
            "--net",
            "--ipc",
            "--uts",
            "/usr/bin/python3",
            str(helper_path),
            helper_json,
        ]
        minimal_env = {
            "PATH": "/usr/bin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
        }
        started = time.monotonic()
        proc = subprocess.Popen(
            launcher,
            cwd=str(workspace_root),
            env=minimal_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            close_fds=True,
            pass_fds=(att_w,),
            start_new_session=True,
        )
        os.close(att_w)
        try:
            stdout, stderr = proc.communicate(timeout=min(self.timeout_seconds, ir["boundary"]["timeout_ms"] / 1000.0))
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            finally:
                proc.wait()
            raise ReadonlyProcessError("C2 process timeout") from exc
        elapsed_ms = int((time.monotonic() - started) * 1000)
        attestation_raw = os.read(att_r, 65536)
        os.close(att_r)
        try:
            attestation = json.loads(attestation_raw.decode("ascii"))
        except Exception as exc:
            bounded_stderr = stderr.decode("utf-8", errors="replace")[-2000:]
            raise ReadonlyProcessError(
                f"sandbox attestation unavailable; returncode={proc.returncode}; stderr_tail={bounded_stderr!r}"
            ) from exc
        snapshot_after = _workspace_snapshot(workspace_root)
        head_after, tree_after = _git_head_tree(workspace_root)
        target_tmp_clean = target_tmp.is_dir() and not any(target_tmp.iterdir())
        target_closed = not Path(f"/proc/{proc.pid}").exists()
        observation = C2ProcessObservation(
            gate_digest=gate.gate_digest,
            action_ir_digest=gate.action_ir_digest,
            exit_code=proc.returncode,
            stdout_sha256=sha256(stdout).hexdigest(),
            stderr_sha256=sha256(stderr).hexdigest(),
            workspace_snapshot_before=snapshot_before,
            workspace_snapshot_after=snapshot_after,
            netns_parent=parent_netns,
            netns_child=str(attestation.get("netns", "")),
            seccomp_mode=int(attestation.get("seccomp", -1)),
            no_new_privs=int(attestation.get("no_new_privs", -1)),
            landlock_abi=int(attestation.get("landlock_abi", -1)),
            landlock_restricted=attestation.get("landlock_restricted") is True,
            target_tmp_clean_after=target_tmp_clean,
            target_pid_closed=target_closed,
            elapsed_ms=elapsed_ms,
            sandbox_attestation_digest=_digest(attestation),
        )
        exact_currentness = (head_after, tree_after, snapshot_after) == (
            gate.workspace_head,
            gate.workspace_tree,
            gate.workspace_snapshot_digest,
        )
        reconciliation = C2ReconciliationRecord(
            status="PASS" if (
                proc.returncode == 0
                and exact_currentness
                and snapshot_before == snapshot_after
                and parent_netns != observation.netns_child
                and observation.seccomp_mode == 2
                and observation.no_new_privs == 1
                and observation.landlock_abi >= 3
                and observation.landlock_restricted
                and observation.target_tmp_clean_after
                and target_closed
            ) else "FAIL",
            gate_digest=gate.gate_digest,
            observation_digest=observation.digest(),
            exact_currentness=exact_currentness,
            filesystem_delta=snapshot_before != snapshot_after,
            independent_netns=parent_netns != observation.netns_child,
            seccomp_filter_active=observation.seccomp_mode == 2,
            no_new_privs=observation.no_new_privs == 1,
            landlock_restricted=observation.landlock_abi >= 3 and observation.landlock_restricted,
            target_tmp_clean_after=observation.target_tmp_clean_after,
            child_process_closure=target_closed,
            exit_success=proc.returncode == 0,
            replay_state="CONSUMED",
        ).validate()
        return C2ExecutionResult(stdout, stderr, observation, reconciliation)


# Linux sandbox helper. It runs inside an unshare-created user/network namespace.
_PR_SET_NO_NEW_PRIVS = 38
_PR_GET_SECCOMP = 21
_PR_GET_NO_NEW_PRIVS = 39
_SCMP_ACT_ALLOW = 0x7FFF0000
_SCMP_ACT_ERRNO_EPERM = 0x00050000 | 1

_SYS_LANDLOCK_CREATE_RULESET = 444
_SYS_LANDLOCK_ADD_RULE = 445
_SYS_LANDLOCK_RESTRICT_SELF = 446
_LANDLOCK_CREATE_RULESET_VERSION = 1
_LANDLOCK_RULE_PATH_BENEATH = 1
_LL_EXECUTE = 1 << 0
_LL_WRITE_FILE = 1 << 1
_LL_READ_FILE = 1 << 2
_LL_READ_DIR = 1 << 3
_LL_REMOVE_DIR = 1 << 4
_LL_REMOVE_FILE = 1 << 5
_LL_MAKE_CHAR = 1 << 6
_LL_MAKE_DIR = 1 << 7
_LL_MAKE_REG = 1 << 8
_LL_MAKE_SOCK = 1 << 9
_LL_MAKE_FIFO = 1 << 10
_LL_MAKE_BLOCK = 1 << 11
_LL_MAKE_SYM = 1 << 12
_LL_REFER = 1 << 13
_LL_TRUNCATE = 1 << 14
_LL_ABI1 = (_LL_EXECUTE | _LL_WRITE_FILE | _LL_READ_FILE | _LL_READ_DIR | _LL_REMOVE_DIR |
            _LL_REMOVE_FILE | _LL_MAKE_CHAR | _LL_MAKE_DIR | _LL_MAKE_REG | _LL_MAKE_SOCK |
            _LL_MAKE_FIFO | _LL_MAKE_BLOCK | _LL_MAKE_SYM)
_LL_ABI2 = _LL_ABI1 | _LL_REFER
_LL_ABI3 = _LL_ABI2 | _LL_TRUNCATE
_LL_READ_EXEC = _LL_EXECUTE | _LL_READ_FILE | _LL_READ_DIR
_LL_READ = _LL_READ_FILE | _LL_READ_DIR


class _LandlockRulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class _LandlockPathBeneathAttr(ctypes.Structure):
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def _landlock_abi() -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    rc = libc.syscall(_SYS_LANDLOCK_CREATE_RULESET, 0, 0, _LANDLOCK_CREATE_RULESET_VERSION)
    if rc < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), "landlock_create_ruleset(VERSION)")
    return int(rc)


def _landlock_handled(abi: int) -> int:
    if abi >= 3:
        return _LL_ABI3
    if abi == 2:
        return _LL_ABI2
    if abi == 1:
        return _LL_ABI1
    raise ReadonlyProcessError(f"unsupported Landlock ABI {abi}")


def _landlock_add_rule(ruleset_fd: int, path: Path, allowed: int) -> None:
    flags = os.O_PATH | os.O_CLOEXEC
    fd = os.open(path, flags)
    try:
        attr = _LandlockPathBeneathAttr(allowed_access=allowed, parent_fd=fd)
        libc = ctypes.CDLL(None, use_errno=True)
        rc = libc.syscall(_SYS_LANDLOCK_ADD_RULE, ruleset_fd, _LANDLOCK_RULE_PATH_BENEATH, ctypes.byref(attr), 0)
        if rc != 0:
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err), str(path))
    finally:
        os.close(fd)


def _install_landlock(*, workspace: Path, target_tmp: Path) -> int:
    abi = _landlock_abi()
    handled = _landlock_handled(abi)
    attr = _LandlockRulesetAttr(handled_access_fs=handled)
    libc = ctypes.CDLL(None, use_errno=True)
    fd = libc.syscall(_SYS_LANDLOCK_CREATE_RULESET, ctypes.byref(attr), ctypes.sizeof(attr), 0)
    if fd < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), "landlock_create_ruleset")
    try:
        _landlock_add_rule(fd, Path("/usr"), _LL_READ_EXEC)
        _landlock_add_rule(fd, Path("/etc"), _LL_READ)
        _landlock_add_rule(fd, workspace, _LL_READ)
        _landlock_add_rule(fd, target_tmp, handled)
        rc = libc.syscall(_SYS_LANDLOCK_RESTRICT_SELF, fd, 0)
        if rc != 0:
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err), "landlock_restrict_self")
    finally:
        os.close(fd)
    return abi


def _install_seccomp() -> None:
    lib = ctypes.CDLL("libseccomp.so.2")
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_rule_add.restype = ctypes.c_int
    ctx = lib.seccomp_init(_SCMP_ACT_ALLOW)
    if not ctx:
        raise ReadonlyProcessError("seccomp_init failed")
    deny = (
        "socket", "socketpair", "connect", "bind", "listen", "accept", "accept4",
        "sendto", "recvfrom", "sendmsg", "recvmsg", "shutdown", "setsockopt", "getsockopt",
        "fork", "vfork", "clone", "clone3", "unshare", "setns", "mount", "umount2",
        "pivot_root", "ptrace", "bpf", "keyctl", "add_key", "request_key",
    )
    try:
        for name in deny:
            nr = lib.seccomp_syscall_resolve_name(name.encode())
            if nr < 0:
                continue
            rc = lib.seccomp_rule_add(ctx, _SCMP_ACT_ERRNO_EPERM, nr, 0)
            if rc != 0:
                raise ReadonlyProcessError(f"seccomp rule failed for {name}: {rc}")
        if lib.seccomp_load(ctx) != 0:
            raise ReadonlyProcessError("seccomp_load failed")
    finally:
        lib.seccomp_release(ctx)


def _sandbox_helper(payload_text: str) -> int:
    payload = json.loads(payload_text)
    sandbox_root = Path(payload["sandbox_root"]).resolve()
    target_tmp = Path(payload["target_tmp"]).resolve()
    workspace = Path(payload["workspace_root"]).resolve()
    _require_isolated_sandbox_root(sandbox_root)
    if target_tmp.parent != sandbox_root:
        raise ReadonlyProcessError("isolated target tmp binding invalid")
    if not workspace.is_dir() or not target_tmp.is_dir():
        raise ReadonlyProcessError("sandbox paths unavailable")
    os.chdir(workspace)
    netns_identity = os.readlink("/proc/self/ns/net")
    memory = int(payload["memory_limit_bytes"])
    timeout_ms = int(payload["timeout_ms"])
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    cpu = max(1, min(60, (timeout_ms + 999) // 1000))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), "prctl(NO_NEW_PRIVS)")
    landlock_abi = _install_landlock(workspace=workspace, target_tmp=target_tmp)
    _install_seccomp()
    seccomp_mode = int(libc.prctl(_PR_GET_SECCOMP, 0, 0, 0, 0))
    no_new_privs = int(libc.prctl(_PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0))
    attestation = {
        "profile": C2_SANDBOX_PROFILE,
        "landlock_abi": landlock_abi,
        "landlock_restricted": True,
        "netns": netns_identity,
        "seccomp": seccomp_mode,
        "no_new_privs": no_new_privs,
        "procfs_allowed": False,
        "workspace": str(workspace),
        "target_tmp": str(target_tmp),
    }
    fd = int(payload["attestation_fd"])
    os.write(fd, _canonical(attestation))
    os.close(fd)
    env = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "HOME": str(target_tmp),
        "TMPDIR": str(target_tmp),
        "TMP": str(target_tmp),
        "TEMP": str(target_tmp),
    }
    for key, value in payload["environment"].items():
        if key in {"PATH", "LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONPATH"}:
            raise ReadonlyProcessError("unsafe environment key denied")
        env[str(key)] = str(value)
    executable = str(payload["executable"])
    argv = [executable, *[str(item) for item in payload["arguments"]]]
    os.execve(executable, argv, env)
    return 127


# Deliberately no __main__ command surface. The private helper is reached only
# through the gate-consumed adapter and an ephemeral helper file inside the
# isolated TEST_ONLY sandbox root.

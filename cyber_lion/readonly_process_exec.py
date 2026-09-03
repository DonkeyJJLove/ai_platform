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
C2_SANDBOX_PROFILE = "linux-user-mount-netns-chroot-seccomp/v1"
C2_DIGEST_DOMAIN = b"LION/C2-READONLY-PROCESS-EXEC/1\0"


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
        ir, snapshot_before = self._revalidate(compiled, gate, workspace_root)
        if not self.replay_guard.consume(gate.gate_digest):
            raise ReadonlyProcessError("C2 execution replay denied")
        if sandbox_root.exists() and any(sandbox_root.iterdir()):
            raise ReadonlyProcessError("sandbox root must start empty")
        sandbox_root.mkdir(parents=True, exist_ok=True)
        parent_netns = os.readlink("/proc/self/ns/net")
        att_r, att_w = os.pipe()
        helper_payload = {
            "sandbox_root": str(sandbox_root),
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
            raise ReadonlyProcessError("sandbox attestation unavailable") from exc
        snapshot_after = _workspace_snapshot(workspace_root)
        head_after, tree_after = _git_head_tree(workspace_root)
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
                and target_closed
            ) else "FAIL",
            gate_digest=gate.gate_digest,
            observation_digest=observation.digest(),
            exact_currentness=exact_currentness,
            filesystem_delta=snapshot_before != snapshot_after,
            independent_netns=parent_netns != observation.netns_child,
            seccomp_filter_active=observation.seccomp_mode == 2,
            no_new_privs=observation.no_new_privs == 1,
            child_process_closure=target_closed,
            exit_success=proc.returncode == 0,
            replay_state="CONSUMED",
        ).validate()
        return C2ExecutionResult(stdout, stderr, observation, reconciliation)


# Linux sandbox helper. It runs only inside unshare-created user/mount/network namespaces.
_MS_RDONLY = 1
_MS_NOSUID = 2
_MS_NODEV = 4
_MS_NOEXEC = 8
_MS_REMOUNT = 32
_MS_BIND = 4096
_MS_REC = 16384
_MS_PRIVATE = 1 << 18
_PR_SET_NO_NEW_PRIVS = 38
_SCMP_ACT_ALLOW = 0x7FFF0000
_SCMP_ACT_ERRNO_EPERM = 0x00050000 | 1


def _libc_mount(source: str | None, target: str, fstype: str | None, flags: int, data: str | None) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.mount
    fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p]
    fn.restype = ctypes.c_int
    def b(value: str | None):
        return None if value is None else value.encode()
    if fn(b(source), b(target), b(fstype), flags, b(data)) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), target)


def _bind_ro(source: str, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    _libc_mount(source, str(target), None, _MS_BIND | _MS_REC, None)
    _libc_mount(None, str(target), None, _MS_BIND | _MS_REMOUNT | _MS_RDONLY, None)


def _install_seccomp() -> None:
    lib = ctypes.CDLL("libseccomp.so.2")
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
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


def _status_field(name: str) -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith(name + ":"):
            return int(line.split(":", 1)[1].strip().split()[0])
    return -1


def _sandbox_helper(payload_text: str) -> int:
    payload = json.loads(payload_text)
    root = Path(payload["sandbox_root"]).resolve()
    workspace = Path(payload["workspace_root"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    _libc_mount(None, "/", None, _MS_REC | _MS_PRIVATE, None)
    _libc_mount("tmpfs", str(root), "tmpfs", _MS_NOSUID | _MS_NODEV, "mode=0755,size=64m")
    for name in ("usr", "etc", "workspace", "tmp", "proc"):
        (root / name).mkdir(parents=True, exist_ok=True)
    for link, target in (("bin", "usr/bin"), ("sbin", "usr/sbin"), ("lib", "usr/lib"), ("lib64", "usr/lib64")):
        p = root / link
        if not p.exists():
            p.symlink_to(target)
    _bind_ro("/usr", root / "usr")
    _bind_ro("/etc", root / "etc")
    _bind_ro(str(workspace), root / "workspace")
    _libc_mount("tmpfs", str(root / "tmp"), "tmpfs", _MS_NOSUID | _MS_NODEV | _MS_NOEXEC, "mode=0700,size=32m")
    _libc_mount("proc", str(root / "proc"), "proc", _MS_NOSUID | _MS_NODEV | _MS_NOEXEC, None)
    # Freeze the chroot root itself; /tmp remains a separate writable submount.
    _libc_mount(None, str(root), None, _MS_REMOUNT | _MS_RDONLY | _MS_NOSUID | _MS_NODEV, None)
    os.chroot(root)
    os.chdir("/workspace")
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
    _install_seccomp()
    attestation = {
        "profile": C2_SANDBOX_PROFILE,
        "netns": os.readlink("/proc/self/ns/net"),
        "seccomp": _status_field("Seccomp"),
        "no_new_privs": _status_field("NoNewPrivs"),
        "workspace": "/workspace",
        "tmp": "/tmp",
    }
    fd = int(payload["attestation_fd"])
    os.write(fd, _canonical(attestation))
    os.close(fd)
    env = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "HOME": "/tmp",
        "TMPDIR": "/tmp",
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

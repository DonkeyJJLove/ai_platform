"""Independent read-only observer for the C2 local-console experiment.

This module has no process-launch, network-client, credential, or mutation
capability. It observes a bounded workspace and a single target PID.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import threading
import time

OBSERVER_VERSION = "lion.c2.readonly-process-observer/v1.0-candidate"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _workspace_manifest(root: Path) -> tuple[str, int]:
    root = root.resolve(strict=True)
    rows: list[tuple[str, int, int, str]] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".git/objects/") or rel.startswith(".git/logs/"):
            continue
        if path.is_symlink():
            target = os.readlink(path)
            data = target.encode("utf-8")
            rows.append((rel, 0o120000, len(data), _sha256_bytes(data)))
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            rows.append((rel, 0, 0, "SPECIAL"))
            continue
        data = path.read_bytes()
        mode = path.stat().st_mode & 0o7777
        rows.append((rel, mode, len(data), _sha256_bytes(data)))
    payload = json.dumps(rows, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return _sha256_bytes(payload), len(rows)


@dataclass(frozen=True)
class WorkspaceSnapshot:
    digest: str
    file_count: int


@dataclass(frozen=True)
class ProcessObservation:
    observer_version: str
    workspace_before: WorkspaceSnapshot
    workspace_after: WorkspaceSnapshot
    socket_seen: bool
    child_pids: tuple[int, ...]
    target_exited: bool
    observation_digest: str


class IndependentProcessObserver:
    """Capability-reduced observer with no process execution method."""

    def __init__(self, workspace: str):
        self._workspace = Path(workspace).resolve(strict=True)
        self._before = self.snapshot_workspace()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket_seen = False
        self._child_pids: set[int] = set()

    def snapshot_workspace(self) -> WorkspaceSnapshot:
        digest, count = _workspace_manifest(self._workspace)
        return WorkspaceSnapshot(digest=digest, file_count=count)

    def start_pid_observation(self, pid: int) -> None:
        if type(pid) is not int or pid <= 0 or self._thread is not None:
            raise ValueError("invalid or duplicate PID observation")

        def monitor() -> None:
            proc = Path("/proc") / str(pid)
            while not self._stop.is_set() and proc.exists():
                fd_dir = proc / "fd"
                try:
                    for fd in fd_dir.iterdir():
                        try:
                            if os.readlink(fd).startswith("socket:["):
                                self._socket_seen = True
                        except OSError:
                            pass
                except OSError:
                    pass
                children = proc / "task" / str(pid) / "children"
                try:
                    raw = children.read_text(encoding="ascii").strip()
                    if raw:
                        self._child_pids.update(int(x) for x in raw.split())
                except (OSError, ValueError):
                    pass
                time.sleep(0.001)

        self._thread = threading.Thread(target=monitor, name="lion-c2-observer", daemon=True)
        self._thread.start()

    def finish(self, pid: int) -> ProcessObservation:
        if self._thread is None:
            raise ValueError("PID observation was not started")
        self._stop.set()
        self._thread.join(timeout=1.0)
        after = self.snapshot_workspace()
        target_exited = not (Path("/proc") / str(pid)).exists()
        payload = {
            "observer_version": OBSERVER_VERSION,
            "workspace_before": self._before.__dict__,
            "workspace_after": after.__dict__,
            "socket_seen": self._socket_seen,
            "child_pids": sorted(self._child_pids),
            "target_exited": target_exited,
        }
        digest = _sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii"))
        return ProcessObservation(
            observer_version=OBSERVER_VERSION,
            workspace_before=self._before,
            workspace_after=after,
            socket_seen=self._socket_seen,
            child_pids=tuple(sorted(self._child_pids)),
            target_exited=target_exited,
            observation_digest=digest,
        )

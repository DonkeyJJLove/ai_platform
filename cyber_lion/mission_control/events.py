from __future__ import annotations

import json
import os
import pwd
import socket
import struct
import threading
from pathlib import Path
from typing import Any

from .models import normalize_run
from .schema import MAX_EVENT_BYTES, validate_event


class EventSocketServer:
    def __init__(self, store, path: str = "/run/lion-mission-control/events.sock") -> None:
        self.store = store
        self.path = Path(path)
        self.stop_event = threading.Event()
        self.sock: socket.socket | None = None
        self.thread: threading.Thread | None = None
        self.allowed_uids = {0, pwd.getpwnam("sentinelx").pw_uid}

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(self.path))
        os.chmod(self.path, 0o600)
        sock.listen(16)
        sock.settimeout(0.5)
        self.sock = sock
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.stop_event.set()
        if self.sock is not None:
            self.sock.close()
        if self.thread is not None:
            self.thread.join(timeout=2)
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def _loop(self) -> None:
        assert self.sock is not None
        while not self.stop_event.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                try:
                    rawcred = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
                    _, uid, _ = struct.unpack("3i", rawcred)
                    if uid not in self.allowed_uids:
                        raise PermissionError("event peer denied")
                    raw = b""
                    while len(raw) <= MAX_EVENT_BYTES:
                        part = conn.recv(min(65536, MAX_EVENT_BYTES + 1 - len(raw)))
                        if not part:
                            break
                        raw += part
                        if b"\n" in raw:
                            raw = raw.split(b"\n", 1)[0]
                            break
                    if len(raw) > MAX_EVENT_BYTES:
                        raise ValueError("event too large")
                    event = validate_event(json.loads(raw.decode("utf-8")))
                    inserted = self.store.append_event(event)
                    if inserted:
                        self._project_run(event)
                    response = {"ok": True, "inserted": inserted, "event_id": event["event_id"]}
                except Exception as exc:
                    response = {"ok": False, "error": type(exc).__name__ + ":" + str(exc)[:500]}
                conn.sendall(json.dumps(response, sort_keys=True, separators=(",", ":")).encode() + b"\n")

    def _project_run(self, event: dict[str, Any]) -> None:
        existing = self.store.get_run(event["run_id"]) or {"run_id": event["run_id"]}
        projected = dict(existing)
        for key in ("process_language", "process_class", "adapter_type", "host", "runtime", "phase", "status"):
            if event.get(key) is not None:
                projected[key] = event[key]
        # Observation events commonly carry only the subset of source/target/
        # authority known to the LPCL emitter. Merge these contexts so later
        # lifecycle events cannot erase stronger adapter-derived runtime proof
        # such as target.cloned_head or exact image/runtime identity.
        for key in ("source", "target", "authority"):
            value = event.get(key)
            if isinstance(value, dict):
                projected[key] = {**(projected.get(key) or {}), **value}
        payload = event.get("payload") or {}
        event_type = event["event_type"]
        if event_type == "RUN_STARTED":
            projected["status"] = projected.get("status") or "STARTING"
            projected["started_at"] = projected.get("started_at") or event["timestamp"]
        elif event_type == "PHASE_STARTED":
            projected["phase"] = event.get("phase") or payload.get("phase") or projected.get("phase")
            if projected.get("status") in (None, "UNKNOWN", "DISCOVERED", "STARTING"):
                projected["status"] = "RUNNING"
        elif event_type == "RUN_COMPLETED":
            projected["status"] = str(payload.get("status") or event.get("status") or "PASS").upper()
            projected["finished_at"] = event["timestamp"]
            if payload.get("verification_status"):
                projected["verification_status"] = str(payload["verification_status"]).upper()
        elif event_type == "CLEANUP_STARTED":
            projected["status"] = "CLEANING"
            projected["cleanup"] = {**(projected.get("cleanup") or {}), "started_at": event["timestamp"]}
        elif event_type == "CLEANUP_COMPLETED":
            projected["status"] = str(payload.get("status") or "CLEANED").upper()
            projected["cleanup"] = {**(projected.get("cleanup") or {}), "finished_at": event["timestamp"], **payload}
        if payload.get("verification_status"):
            projected["verification_status"] = str(payload["verification_status"]).upper()
        run = self.store.upsert_run(normalize_run(projected))
        run_id = run["run_id"]
        if event_type == "METRIC":
            name = payload.get("name")
            if isinstance(name, str) and name:
                self.store.add_metric(run_id, name, payload.get("value"), event["timestamp"])
        elif event_type == "PARTICIPANT":
            name = payload.get("name")
            if isinstance(name, str) and name:
                self.store.add_participant(run_id, name, payload.get("value"), event["timestamp"])
        elif event_type == "ARTIFACT" and isinstance(payload.get("artifact_id"), str):
            self.store.add_artifact(run_id, payload)
        elif event_type == "RECEIPT" and isinstance(payload.get("receipt_id"), str):
            self.store.add_receipt(run_id, payload)
        elif event_type == "EVIDENCE":
            projected = dict(self.store.get_run(run_id) or run)
            projected["evidence"] = {**(projected.get("evidence") or {}), **payload}
            self.store.upsert_run(projected)

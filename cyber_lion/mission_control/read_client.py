from __future__ import annotations

import hashlib
import json
import os
import re
import socket
from typing import Any

SOCKET_PATH = "/run/lion-mission-control-read.sock"
SCHEMA = "1.0.0"
MAX_RESPONSE = 8 * 1024 * 1024
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
READ_OPERATIONS = {"PING", "READ_POD_EVIDENCE", "READ_OSS_REPO_TEST_EVIDENCE"}


def _rid() -> str:
    return hashlib.sha256(os.urandom(32)).hexdigest()


def call(operation: str, *, source_head: str | None = None, source_tree: str | None = None,
         run_id: str | None = None, socket_path: str = SOCKET_PATH) -> dict[str, Any]:
    if operation not in READ_OPERATIONS:
        raise ValueError("Mission Control read client operation denied")
    request: dict[str, Any] = {"schema_version": SCHEMA, "request_id": _rid(), "operation": operation}
    if operation != "PING":
        if not isinstance(source_head, str) or not HEX40.fullmatch(source_head):
            raise ValueError("invalid source_head")
        if not isinstance(source_tree, str) or not HEX40.fullmatch(source_tree):
            raise ValueError("invalid source_tree")
        if not isinstance(run_id, str) or not SAFE_RUN_ID.fullmatch(run_id):
            raise ValueError("invalid run_id")
        request.update(source_head=source_head, source_tree=source_tree, run_id=run_id)
    raw = json.dumps(request, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(45)
    sock.connect(socket_path)
    sock.sendall(raw)
    sock.shutdown(socket.SHUT_WR)
    data = bytearray()
    while True:
        part = sock.recv(65536)
        if not part:
            break
        data.extend(part)
        if len(data) > MAX_RESPONSE:
            raise RuntimeError("Mission Control read response too large")
    sock.close()
    value = json.loads(bytes(data).decode("utf-8"))
    if not isinstance(value, dict) or value.get("ok") is not True or not isinstance(value.get("result"), dict):
        raise RuntimeError("Mission Control read denied:" + str(value.get("error") if isinstance(value, dict) else "malformed"))
    return value["result"]

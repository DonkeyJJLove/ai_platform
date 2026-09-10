#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import socket
import struct
import sys
from typing import Any

SCHEMA = "1.0.0"
UPSTREAM_SOCKET = "/run/lion-vkt-effect-admission.sock"
SENTINEL_USER = "sentinelx"
MAX_REQUEST = 64 * 1024
MAX_RESPONSE = 8 * 1024 * 1024
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
READ_OPERATIONS = {"PING", "READ_POD_EVIDENCE", "READ_OSS_REPO_TEST_EVIDENCE"}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def peer_uid() -> int:
    sock = socket.fromfd(0, socket.AF_UNIX, socket.SOCK_STREAM)
    raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    sock.close()
    return struct.unpack("3i", raw)[1]


def receive() -> dict[str, Any]:
    raw = sys.stdin.buffer.readline(MAX_REQUEST + 1)
    if len(raw) > MAX_REQUEST:
        raise ValueError("request too large")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("request must be object")
    return value


def validate(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("schema_version") != SCHEMA:
        raise ValueError("schema mismatch")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not HEX64.fullmatch(request_id):
        raise ValueError("invalid request_id")
    operation = request.get("operation")
    if operation not in READ_OPERATIONS:
        raise PermissionError("operation not read-allowlisted")
    if operation == "PING":
        if set(request) != {"schema_version", "request_id", "operation"}:
            raise ValueError("ping field set")
        return request
    if set(request) != {"schema_version", "request_id", "operation", "source_head", "source_tree", "run_id"}:
        raise ValueError("read field set")
    if not isinstance(request.get("source_head"), str) or not HEX40.fullmatch(request["source_head"]):
        raise ValueError("invalid source_head")
    if not isinstance(request.get("source_tree"), str) or not HEX40.fullmatch(request["source_tree"]):
        raise ValueError("invalid source_tree")
    if not isinstance(request.get("run_id"), str) or not SAFE_RUN_ID.fullmatch(request["run_id"]):
        raise ValueError("invalid run_id")
    return request


def upstream(request: dict[str, Any]) -> dict[str, Any]:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(45)
    sock.connect(UPSTREAM_SOCKET)
    sock.sendall(canonical(request) + b"\n")
    sock.shutdown(socket.SHUT_WR)
    data = bytearray()
    while True:
        part = sock.recv(65536)
        if not part:
            break
        data.extend(part)
        if len(data) > MAX_RESPONSE:
            raise RuntimeError("upstream response too large")
    sock.close()
    value = json.loads(bytes(data).decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("upstream malformed")
    return value


def reply(value: dict[str, Any]) -> None:
    sys.stdout.buffer.write(canonical(value) + b"\n")
    sys.stdout.buffer.flush()


def main() -> int:
    request_id = None
    try:
        if os.geteuid() != pwd.getpwnam(SENTINEL_USER).pw_uid:
            raise PermissionError("proxy must run as sentinelx")
        if peer_uid() != pwd.getpwnam(SENTINEL_USER).pw_uid:
            raise PermissionError("proxy caller denied")
        request = receive()
        request_id = request.get("request_id") if isinstance(request.get("request_id"), str) else None
        request = validate(request)
        value = upstream(request)
        reply(value)
        return 0 if value.get("ok") is True else 2
    except Exception as exc:
        reply({"ok": False, "request_id": request_id, "error": type(exc).__name__ + ":" + str(exc)[:500]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

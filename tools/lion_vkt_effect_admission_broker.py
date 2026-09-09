#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import socket
import struct
import subprocess
import sys
from typing import Any

SCHEMA = "1.0.0"
EXPECTED_HOST = "LION-AUTH-LAB"
EXPECTED_HOST_ID = "host_f78ddce3275144e4"
SENTINEL_USER = "sentinelx"
RUNNER_EXEC_CLIENT = "/usr/local/libexec/lion-runner-exec-client.py"
REPOSITORY = "DonkeyJJLove/ai_platform"
REPO_URL = "https://github.com/DonkeyJJLove/ai_platform.git"
BRANCH = "mission/vkt-r3-pod-materialization-r2"
MISSION_ID = "VKT-R3-384-REAL-POD-MISSION-CONTROL-R2"
IDENTITY_FILE = Path("/opt/lion/k3s-vkt-r3/source-identity.json")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
MAX_REQUEST = 16 * 1024
MAX_RESPONSE = 8 * 1024 * 1024
OPERATIONS = {
    "PING",
    "PRECHECK_POD_RUNTIME",
    "PREPARE_LOCAL_K8S",
    "MATERIALIZE_VKT_PODS",
    "READ_POD_EVIDENCE",
    "STOP_VKT_PODS",
}
LIVE_CURRENTNESS_REQUIRED = {
    "PRECHECK_POD_RUNTIME",
    "PREPARE_LOCAL_K8S",
    "MATERIALIZE_VKT_PODS",
}


class Deny(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require_hex40(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HEX40.fullmatch(value):
        raise Deny(f"{label}:invalid")
    return value


def require_hex64(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise Deny(f"{label}:invalid")
    return value


def require_run_id(value: Any) -> str:
    if not isinstance(value, str) or not SAFE_RUN_ID.fullmatch(value):
        raise Deny("run_id:invalid")
    return value


def peer_uid() -> int:
    sock = socket.fromfd(0, socket.AF_UNIX, socket.SOCK_STREAM)
    raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    sock.close()
    return struct.unpack("3i", raw)[1]


def receive() -> dict[str, Any]:
    raw = sys.stdin.buffer.readline(MAX_REQUEST + 1)
    if len(raw) > MAX_REQUEST:
        raise Deny("request-too-large")
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise Deny("invalid-json") from exc
    if not isinstance(value, dict):
        raise Deny("request-not-object")
    return value


def reply(value: dict[str, Any]) -> None:
    raw = canonical(value) + b"\n"
    if len(raw) > MAX_RESPONSE:
        raw = canonical({"ok": False, "error": "response-too-large"}) + b"\n"
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def run(argv: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        timeout=timeout,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "GIT_TERMINAL_PROMPT": "0"},
    )
    if proc.returncode != 0:
        raise Deny(f"command-failed:{os.path.basename(argv[0])}:rc={proc.returncode}:{(proc.stderr or proc.stdout)[-2000:]}")
    return proc


def live_head() -> str:
    proc = run(["/usr/bin/git", "ls-remote", "--exit-code", REPO_URL, f"refs/heads/{BRANCH}"], timeout=60)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise Deny("remote-head-cardinality")
    fields = lines[0].split()
    if len(fields) != 2 or fields[1] != f"refs/heads/{BRANCH}":
        raise Deny("remote-head-malformed")
    return require_hex40(fields[0], "remote-head")


def installed_identity() -> dict[str, Any]:
    if not IDENTITY_FILE.is_file():
        raise Deny("vkt-provider-not-installed")
    value = json.loads(IDENTITY_FILE.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Deny("installed-identity-not-object")
    if value.get("repository") != REPOSITORY or value.get("branch") != BRANCH:
        raise Deny("installed-identity-scope-mismatch")
    if value.get("trust_class") != "TEST_ONLY":
        raise Deny("installed-identity-trust-mismatch")
    require_hex40(value.get("source_head"), "installed-source-head")
    require_hex40(value.get("source_tree"), "installed-source-tree")
    return value


def verify_identity(head: str, tree: str, require_live: bool) -> dict[str, Any]:
    ident = installed_identity()
    if ident.get("source_head") != head or ident.get("source_tree") != tree:
        raise Deny("installed-source-mismatch")
    observed = None
    if require_live:
        observed = live_head()
        if observed != head:
            raise Deny("VKT_LIVE_SOURCE_HEAD_DRIFT:" + observed)
    return {"installed": ident, "live_source_head": observed}


def runner_call(operation: str, head: str, tree: str, run_id: str) -> dict[str, Any]:
    if operation not in OPERATIONS - {"PING"}:
        raise Deny("provider-operation-denied")
    argv = [
        "/usr/bin/python3",
        RUNNER_EXEC_CLIENT,
        "pod-provider-call",
        "--provider-operation", operation,
        "--source-head", head,
        "--source-tree", tree,
        "--run-id", run_id,
    ]
    proc = run(argv, timeout=300)
    value = json.loads(proc.stdout)
    if not isinstance(value, dict) or value.get("ok") is not True or not isinstance(value.get("result"), dict):
        raise Deny("runner-provider-call-failed")
    return value["result"]


def handle(request: dict[str, Any]) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise Deny("broker-not-root")
    if socket.gethostname() != EXPECTED_HOST:
        raise Deny("wrong-host")
    if peer_uid() != pwd.getpwnam(SENTINEL_USER).pw_uid:
        raise Deny("caller-uid-denied")
    if request.get("schema_version") != SCHEMA:
        raise Deny("schema-mismatch")
    require_hex64(request.get("request_id"), "request_id")
    operation = request.get("operation")
    if operation not in OPERATIONS:
        raise Deny("operation-not-allowlisted")

    if operation == "PING":
        if set(request) != {"schema_version", "request_id", "operation"}:
            raise Deny("ping-field-set")
        identity = None
        try:
            identity = installed_identity()
        except Deny:
            pass
        return {
            "broker": "READY",
            "authority_class": "BOUNDED_PRIVILEGED_ADMISSION",
            "host_id": EXPECTED_HOST_ID,
            "hostname": EXPECTED_HOST,
            "namespace": "vkt-r3",
            "mission_id": MISSION_ID,
            "installed_identity": identity,
            "operations": sorted(OPERATIONS),
            "direct_docker_authority": False,
            "direct_kubernetes_authority": False,
            "vendor_requests": 0,
        }

    expected = {"schema_version", "request_id", "operation", "source_head", "source_tree", "run_id"}
    if set(request) != expected:
        raise Deny("pod-operation-field-set")
    head = require_hex40(request.get("source_head"), "source_head")
    tree = require_hex40(request.get("source_tree"), "source_tree")
    run_id = require_run_id(request.get("run_id"))
    verify_identity(head, tree, require_live=operation in LIVE_CURRENTNESS_REQUIRED)
    return runner_call(operation, head, tree, run_id)


def main() -> int:
    request_id = None
    try:
        request = receive()
        if isinstance(request.get("request_id"), str):
            request_id = request["request_id"]
        result = handle(request)
        reply({"ok": True, "request_id": request_id, "result": result})
        return 0
    except Exception as exc:
        reply({"ok": False, "request_id": request_id, "error": type(exc).__name__ + ":" + str(exc)[:3000]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

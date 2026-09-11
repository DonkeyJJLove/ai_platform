#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import re
import socket

SCHEMA = "1.0.0"
MISSION_ID = "VKT-R3-384-REAL-POD-MISSION-CONTROL-R2"
RUNNER_USER = "lion-maintenance-runner"
SOCKET = "/run/lion-k3s-vkt-r3/provider.sock"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
OPERATIONS = (
    "PRECHECK_POD_RUNTIME",
    "PREPARE_LOCAL_K8S",
    "MATERIALIZE_VKT_PODS",
    "READ_POD_EVIDENCE",
    "STOP_VKT_PODS",
)
MAX = 8 * 1024 * 1024


def request_id() -> str:
    return hashlib.sha256(os.urandom(32)).hexdigest()


def call(req: dict) -> int:
    if pwd.getpwuid(os.geteuid()).pw_name != RUNNER_USER:
        raise SystemExit("k3s provider client requires lion-maintenance-runner")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(SOCKET)
    sock.sendall(json.dumps(req, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    sock.shutdown(socket.SHUT_WR)
    data = bytearray()
    while True:
        part = sock.recv(65536)
        if not part:
            break
        data.extend(part)
        if len(data) > MAX:
            raise SystemExit("provider response too large")
    sock.close()
    value = json.loads(bytes(data).decode())
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))
    return 0 if value.get("ok") is True else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not HEX40.fullmatch(args.source_head) or not HEX40.fullmatch(args.source_tree):
        raise SystemExit("invalid source identity")
    if not SAFE_RUN_ID.fullmatch(args.run_id):
        raise SystemExit("invalid run id")
    req = {
        "schema_version": SCHEMA,
        "request_id": request_id(),
        "operation": args.operation,
        "mission_id": MISSION_ID,
        "run_id": args.run_id,
        "source_head": args.source_head,
        "source_tree": args.source_tree,
    }
    return call(req)


if __name__ == "__main__":
    raise SystemExit(main())

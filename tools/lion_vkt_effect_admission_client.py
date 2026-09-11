#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import sys

SOCKET_PATH = "/run/lion-vkt-effect-admission.sock"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
COMMANDS = {
    "precheck": "PRECHECK_POD_RUNTIME",
    "prepare": "PREPARE_LOCAL_K8S",
    "materialize": "MATERIALIZE_VKT_PODS",
    "evidence": "READ_POD_EVIDENCE",
    "stop": "STOP_VKT_PODS",
    "oss-start": "START_OSS_REPO_TEST",
    "oss-evidence": "READ_OSS_REPO_TEST_EVIDENCE",
    "oss-stop": "STOP_OSS_REPO_TEST",
}


def rid() -> str:
    return hashlib.sha256(os.urandom(32)).hexdigest()


def call(request: dict) -> int:
    raw = json.dumps(request, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(SOCKET_PATH)
    sock.sendall(raw)
    sock.shutdown(socket.SHUT_WR)
    data = bytearray()
    while True:
        part = sock.recv(65536)
        if not part:
            break
        data.extend(part)
        if len(data) > 8 * 1024 * 1024:
            raise SystemExit("response too large")
    sock.close()
    value = json.loads(bytes(data).decode())
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))
    return 0 if value.get("ok") is True else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ping")
    for name in COMMANDS:
        p = sub.add_parser(name)
        p.add_argument("--source-head", required=True)
        p.add_argument("--source-tree", required=True)
        p.add_argument("--run-id", required=True)
    args = parser.parse_args()
    request = {"schema_version": "1.0.0", "request_id": rid()}
    if args.command == "ping":
        request["operation"] = "PING"
    else:
        if not HEX40.fullmatch(args.source_head) or not HEX40.fullmatch(args.source_tree):
            raise SystemExit("invalid source identity")
        if not SAFE_RUN_ID.fullmatch(args.run_id):
            raise SystemExit("invalid run id")
        request.update(
            operation=COMMANDS[args.command],
            source_head=args.source_head,
            source_tree=args.source_tree,
            run_id=args.run_id,
        )
    return call(request)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import re
import socket
import sys


SOCKET_PATH = "/run/lion-effect-admission.sock"

HEX40 = re.compile(
    r"^[0-9a-f]{40}$"
)

HEX64 = re.compile(
    r"^[0-9a-f]{64}$"
)


def request_id():
    return hashlib.sha256(
        os.urandom(32)
    ).hexdigest()


def call(request):
    raw = json.dumps(
        request,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"

    with socket.socket(
        socket.AF_UNIX,
        socket.SOCK_STREAM,
    ) as conn:

        conn.connect(
            SOCKET_PATH
        )

        conn.sendall(raw)
        conn.shutdown(
            socket.SHUT_WR
        )

        data = bytearray()

        while True:
            block = conn.recv(8192)

            if not block:
                break

            data.extend(block)

            if (
                len(data)
                > 8 * 1024 * 1024
            ):
                raise RuntimeError(
                    "response too large"
                )

    result = json.loads(
        bytes(data).decode(
            "utf-8"
        )
    )

    print(
        json.dumps(
            result,
            sort_keys=True,
            separators=(",", ":"),
        )
    )

    return (
        0
        if result.get("ok")
        is True
        else 2
    )


parser = argparse.ArgumentParser()

commands = parser.add_subparsers(
    dest="command",
    required=True,
)

commands.add_parser(
    "ping"
)

precheck = commands.add_parser(
    "precheck-scale64"
)
precheck.add_argument("--source-head", required=True)
precheck.add_argument("--source-tree", required=True)

prepare = commands.add_parser(
    "prepare-scale64"
)

prepare.add_argument(
    "--source-head",
    required=True,
)

prepare.add_argument(
    "--source-tree",
    required=True,
)

run = commands.add_parser(
    "run-scale64"
)

run.add_argument(
    "--source-head",
    required=True,
)

run.add_argument(
    "--source-tree",
    required=True,
)

evidence = commands.add_parser(
    "evidence"
)

evidence.add_argument(
    "--run-request-id",
    required=True,
)

args = parser.parse_args()

req = {
    "schema_version": "1.0.0",
    "request_id": request_id(),
}

if args.command == "ping":
    req["operation"] = "PING"

elif args.command in {
    "precheck-scale64",
    "prepare-scale64",
    "run-scale64",
}:

    if not HEX40.fullmatch(
        args.source_head
    ):
        raise SystemExit(
            "invalid source head"
        )

    if not HEX40.fullmatch(
        args.source_tree
    ):
        raise SystemExit(
            "invalid source tree"
        )

    req.update(
        {
            "operation": ("PRECHECK_SCALE64" if args.command == "precheck-scale64" else ("PREPARE_SCALE64" if args.command == "prepare-scale64" else "RUN_SCALE64")),
            "source_head": (
                args.source_head
            ),
            "source_tree": (
                args.source_tree
            ),
        }
    )

else:
    if not HEX64.fullmatch(
        args.run_request_id
    ):
        raise SystemExit(
            "invalid run request id"
        )

    req.update(
        {
            "operation": (
                "READ_EVIDENCE"
            ),
            "run_request_id": (
                args.run_request_id
            ),
        }
    )

raise SystemExit(
    call(req)
)

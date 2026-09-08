#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys


SOCKET = "/run/lion-broker-update.sock"

HEX40 = re.compile(
    r"^[0-9a-f]{40}$"
)

HEX64 = re.compile(
    r"^[0-9a-f]{64}$"
)


def rid():
    return hashlib.sha256(
        os.urandom(32)
    ).hexdigest()


def call(req):
    raw = json.dumps(
        req,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8") + b"\n"

    with socket.socket(
        socket.AF_UNIX,
        socket.SOCK_STREAM,
    ) as conn:

        conn.connect(SOCKET)

        conn.sendall(raw)

        conn.shutdown(
            socket.SHUT_WR
        )

        data = bytearray()

        while True:
            part = conn.recv(65536)

            if not part:
                break

            data.extend(part)

            if len(data) > 1024 * 1024:
                raise RuntimeError(
                    "response too large"
                )

    value = json.loads(
        bytes(data).decode(
            "utf-8"
        )
    )

    print(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        )
    )

    return (
        0
        if value.get("ok")
        is True
        else 2
    )


p = argparse.ArgumentParser()

sub = p.add_subparsers(
    dest="command",
    required=True,
)

sub.add_parser(
    "ping"
)

for name in (
    "validate-update",
    "apply-update",
):
    q = sub.add_parser(name)

    q.add_argument(
        "--expected-current-sha256",
        required=True,
    )

    q.add_argument(
        "--replacement-file",
        required=True,
    )

    q.add_argument(
        "--source-head",
        required=True,
    )

    q.add_argument(
        "--source-tree",
        required=True,
    )

    q.add_argument(
        "--reason",
        required=True,
    )

read = sub.add_parser(
    "receipt"
)

read.add_argument(
    "--receipt-id",
    required=True,
)

a = p.parse_args()

req = {
    "schema_version": "1.0.0",
    "request_id": rid(),
}

if a.command == "ping":
    req["operation"] = "PING"

elif a.command in (
    "validate-update",
    "apply-update",
):
    if not HEX64.fullmatch(
        a.expected_current_sha256
    ):
        raise SystemExit(
            "invalid current sha"
        )

    if not HEX40.fullmatch(
        a.source_head
    ):
        raise SystemExit(
            "invalid source head"
        )

    if not HEX40.fullmatch(
        a.source_tree
    ):
        raise SystemExit(
            "invalid source tree"
        )

    path = Path(
        a.replacement_file
    )

    raw = path.read_bytes()

    text = raw.decode(
        "utf-8"
    )

    replacement_sha = (
        hashlib.sha256(raw).hexdigest()
    )

    req.update(
        {
            "operation": (
                "VALIDATE_UPDATE"
                if a.command
                == "validate-update"
                else "APPLY_UPDATE"
            ),
            "expected_current_sha256": (
                a.expected_current_sha256
            ),
            "replacement_sha256": (
                replacement_sha
            ),
            "replacement_content": text,
            "update_reason": a.reason,
            "source_head": (
                a.source_head
            ),
            "source_tree": (
                a.source_tree
            ),
        }
    )

else:
    if not HEX64.fullmatch(
        a.receipt_id
    ):
        raise SystemExit(
            "invalid receipt id"
        )

    req.update(
        {
            "operation": (
                "READ_UPDATE_RECEIPT"
            ),
            "receipt_id": (
                a.receipt_id
            ),
        }
    )

raise SystemExit(
    call(req)
)

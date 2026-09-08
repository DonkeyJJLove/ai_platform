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
import tempfile
from datetime import datetime, timezone
from typing import Any


SCHEMA = "1.0.0"

EXPECTED_HOST = "LION-AUTH-LAB"
SENTINEL_USER = "sentinelx"

TARGET = Path(
    "/usr/local/libexec/"
    "lion-effect-admission-broker.py"
)

STATE = Path(
    "/var/lib/lion-broker-update"
)

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

MAX_REQUEST = 4 * 1024 * 1024
MAX_RESPONSE = 1024 * 1024

REQUIRED_LITERALS = (
    'EXPECTED_HOST = "LION-AUTH-LAB"',
    'SENTINEL_USER = "sentinelx"',
    'RUNNER_USER = "lion-maintenance-runner"',
    'PROVIDER_GROUP = "lion-docker-p0"',
    'TRUST_CLASS',
    '"PING"',
    '"PRECHECK_SCALE64"',
    '"PREPARE_SCALE64"',
    '"RUN_SCALE64"',
    '"READ_EVIDENCE"',
)

FORBIDDEN_LITERALS = (
    "shell=True",
    "chmod(0o777",
    "chmod 0777",
    "os.system(",
    "subprocess.Popen(request",
    "subprocess.run(request",
)


class Deny(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def atomic_json(
    path: Path,
    value: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = path.with_name(
        path.name
        + ".tmp-"
        + digest(os.urandom(16))[:12]
    )

    tmp.write_bytes(
        canonical(value) + b"\n"
    )

    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def peer_uid() -> int:
    sock = socket.fromfd(
        0,
        socket.AF_UNIX,
        socket.SOCK_STREAM,
    )

    raw = sock.getsockopt(
        socket.SOL_SOCKET,
        socket.SO_PEERCRED,
        struct.calcsize("3i"),
    )

    sock.close()

    _, uid, _ = struct.unpack(
        "3i",
        raw,
    )

    return uid


def require_hex40(
    value: Any,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or not HEX40.fullmatch(value)
    ):
        raise Deny(label + ":invalid")
    return value


def require_hex64(
    value: Any,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or not HEX64.fullmatch(value)
    ):
        raise Deny(label + ":invalid")
    return value


def compile_candidate(
    raw: bytes,
) -> None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Deny(
            "replacement-not-utf8"
        ) from exc

    for literal in REQUIRED_LITERALS:
        if literal not in text:
            raise Deny(
                "required-literal-missing:"
                + literal
            )

    for literal in FORBIDDEN_LITERALS:
        if literal in text:
            raise Deny(
                "forbidden-literal:"
                + literal
            )

    with tempfile.NamedTemporaryFile(
        mode="wb",
        prefix="lion-broker-candidate-",
        suffix=".py",
        delete=False,
    ) as handle:
        handle.write(raw)
        candidate = Path(handle.name)

    try:
        proc = subprocess.run(
            [
                "/usr/bin/python3",
                "-m",
                "py_compile",
                str(candidate),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            check=False,
            timeout=30,
        )

        if proc.returncode != 0:
            raise Deny(
                "python-compile-failed:"
                + proc.stderr.decode(
                    "utf-8",
                    "replace",
                )[-2000:]
            )

    finally:
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass


def validate_common(
    req: dict[str, Any],
) -> tuple[str, str, bytes, str, str]:

    expected = require_hex64(
        req.get(
            "expected_current_sha256"
        ),
        "expected_current_sha256",
    )

    replacement_sha = require_hex64(
        req.get(
            "replacement_sha256"
        ),
        "replacement_sha256",
    )

    source_head = require_hex40(
        req.get("source_head"),
        "source_head",
    )

    source_tree = require_hex40(
        req.get("source_tree"),
        "source_tree",
    )

    replacement = req.get(
        "replacement_content"
    )

    if not isinstance(
        replacement,
        str,
    ):
        raise Deny(
            "replacement-content-invalid"
        )

    raw = replacement.encode(
        "utf-8"
    )

    if digest(raw) != replacement_sha:
        raise Deny(
            "replacement-sha-mismatch"
        )

    current_raw = TARGET.read_bytes()

    if digest(current_raw) != expected:
        raise Deny(
            "current-sha-mismatch"
        )

    compile_candidate(raw)

    return (
        expected,
        replacement_sha,
        raw,
        source_head,
        source_tree,
    )


def validate_update(
    req: dict[str, Any],
) -> dict[str, Any]:

    (
        expected,
        replacement,
        raw,
        source_head,
        source_tree,
    ) = validate_common(req)

    return {
        "valid": True,
        "target": str(TARGET),
        "current_sha256": expected,
        "replacement_sha256": replacement,
        "replacement_size": len(raw),
        "source_head": source_head,
        "source_tree": source_tree,
        "python_compile": "PASS",
        "static_security": "PASS",
    }


def apply_update(
    req: dict[str, Any],
) -> dict[str, Any]:

    (
        expected,
        replacement,
        raw,
        source_head,
        source_tree,
    ) = validate_common(req)

    STATE.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = (
        datetime.now(timezone.utc)
        .strftime("%Y%m%dT%H%M%SZ")
    )

    backup = (
        STATE
        / (
            "lion-effect-admission-broker."
            + expected
            + "."
            + stamp
            + ".bak"
        )
    )

    backup.write_bytes(
        TARGET.read_bytes()
    )

    os.chown(
        backup,
        0,
        0,
    )

    os.chmod(
        backup,
        0o400,
    )

    if digest(
        backup.read_bytes()
    ) != expected:
        raise Deny(
            "backup-sha-mismatch"
        )

    fd, tmp_name = tempfile.mkstemp(
        prefix=".lion-effect-admission.",
        suffix=".new",
        dir=str(TARGET.parent),
    )

    tmp = Path(tmp_name)

    try:
        with os.fdopen(
            fd,
            "wb",
        ) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(
                handle.fileno()
            )

        os.chown(
            tmp,
            0,
            0,
        )

        os.chmod(
            tmp,
            0o555,
        )

        if digest(
            tmp.read_bytes()
        ) != replacement:
            raise Deny(
                "temp-sha-mismatch"
            )

        os.replace(
            tmp,
            TARGET,
        )

        dir_fd = os.open(
            str(TARGET.parent),
            os.O_DIRECTORY,
        )

        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    finally:
        if tmp.exists():
            tmp.unlink()

    if digest(
        TARGET.read_bytes()
    ) != replacement:
        raise Deny(
            "post-write-sha-mismatch"
        )

    receipt = {
        "schema_version": SCHEMA,
        "operation": "APPLY_UPDATE",
        "target": str(TARGET),
        "expected_current_sha256": expected,
        "replacement_sha256": replacement,
        "backup_path": str(backup),
        "backup_sha256": expected,
        "source_head": source_head,
        "source_tree": source_tree,
        "applied_at": now(),
        "atomic_replace": True,
    }

    receipt_id = digest(
        canonical(receipt)
    )

    atomic_json(
        STATE
        / (
            "receipt-"
            + receipt_id
            + ".json"
        ),
        receipt,
    )

    return {
        **receipt,
        "receipt_id": receipt_id,
    }


def read_receipt(
    receipt_id: str,
) -> dict[str, Any]:

    require_hex64(
        receipt_id,
        "receipt_id",
    )

    path = STATE / (
        "receipt-"
        + receipt_id
        + ".json"
    )

    if not path.is_file():
        raise Deny(
            "unknown-receipt"
        )

    value = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        value,
        dict,
    ):
        raise Deny(
            "receipt-invalid"
        )

    return value


def receive() -> dict[str, Any]:
    raw = sys.stdin.buffer.readline(
        MAX_REQUEST + 1
    )

    if len(raw) > MAX_REQUEST:
        raise Deny(
            "request-too-large"
        )

    value = json.loads(
        raw.decode("utf-8")
    )

    if not isinstance(
        value,
        dict,
    ):
        raise Deny(
            "request-not-object"
        )

    return value


def reply(
    value: dict[str, Any],
) -> None:
    raw = canonical(value) + b"\n"

    if len(raw) > MAX_RESPONSE:
        raw = canonical(
            {
                "ok": False,
                "error": (
                    "response-too-large"
                ),
            }
        ) + b"\n"

    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def main() -> int:
    request_id = None

    try:
        uid = peer_uid()

        expected_uid = pwd.getpwnam(
            SENTINEL_USER
        ).pw_uid

        if uid != expected_uid:
            raise Deny(
                "caller-uid-denied"
            )

        if os.getuid() != 0:
            raise Deny(
                "provider-not-root"
            )

        if socket.gethostname() != EXPECTED_HOST:
            raise Deny(
                "wrong-host"
            )

        req = receive()

        if req.get(
            "schema_version"
        ) != SCHEMA:
            raise Deny(
                "schema-invalid"
            )

        request_id = require_hex64(
            req.get("request_id"),
            "request_id",
        )

        op = req.get(
            "operation"
        )

        if op == "PING":
            if set(req) != {
                "schema_version",
                "request_id",
                "operation",
            }:
                raise Deny(
                    "ping-field-set"
                )

            result = {
                "provider": "READY",
                "runtime_uid": 0,
                "caller_uid": uid,
                "general_root_shell": False,
                "general_file_write": False,
                "allowed_target": str(
                    TARGET
                ),
                "operations": [
                    "PING",
                    "VALIDATE_UPDATE",
                    "APPLY_UPDATE",
                    "READ_UPDATE_RECEIPT",
                ],
                "target_sha256": digest(
                    TARGET.read_bytes()
                ),
            }

        elif op in {
            "VALIDATE_UPDATE",
            "APPLY_UPDATE",
        }:
            required = {
                "schema_version",
                "request_id",
                "operation",
                "expected_current_sha256",
                "replacement_sha256",
                "replacement_content",
                "update_reason",
                "source_head",
                "source_tree",
            }

            if set(req) != required:
                raise Deny(
                    "update-field-set"
                )

            reason = req.get(
                "update_reason"
            )

            if (
                not isinstance(
                    reason,
                    str,
                )
                or not reason
                or len(reason) > 512
            ):
                raise Deny(
                    "update-reason-invalid"
                )

            result = (
                validate_update(req)
                if op
                == "VALIDATE_UPDATE"
                else apply_update(req)
            )

        elif op == "READ_UPDATE_RECEIPT":
            if set(req) != {
                "schema_version",
                "request_id",
                "operation",
                "receipt_id",
            }:
                raise Deny(
                    "receipt-field-set"
                )

            result = read_receipt(
                req["receipt_id"]
            )

        else:
            raise Deny(
                "operation-not-allowlisted"
            )

        reply(
            {
                "ok": True,
                "request_id": (
                    request_id
                ),
                "result": result,
            }
        )

        return 0

    except Exception as exc:
        reply(
            {
                "ok": False,
                "request_id": (
                    request_id
                ),
                "error": (
                    type(exc).__name__
                    + ":"
                    + str(exc)[:2000]
                ),
            }
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(main())
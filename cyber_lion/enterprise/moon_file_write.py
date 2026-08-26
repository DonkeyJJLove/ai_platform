"""Bounded MOON file-write capability.

Accepts an exact issue-comment envelope, authorizes the actor against GitHub collaborator
permissions, and writes only a direct child of /home/d2j3. No shell command is accepted.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid

PREFIX = "MOON-FILE-WRITE v1"
CONTROL_ISSUE = 144
BASE_DIR = Path("/home/d2j3")
MAX_CONTENT_BYTES = 4096
TRUSTED_PERMISSIONS = {"admin", "maintain", "write"}
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_FILENAME = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_FIELD_ORDER = ("path", "content_b64", "expected_sha256", "request_id")


def _parse_envelope(body: str) -> dict[str, str]:
    lines = body.splitlines()
    if len(lines) != 1 + len(_FIELD_ORDER) or lines[0] != PREFIX:
        raise RuntimeError("malformed MOON-FILE-WRITE envelope")
    values: dict[str, str] = {}
    for key, line in zip(_FIELD_ORDER, lines[1:]):
        marker = key + "="
        if not line.startswith(marker):
            raise RuntimeError(f"missing or reordered field: {key}")
        values[key] = line[len(marker):]
    if not _REQUEST_ID.fullmatch(values["request_id"]):
        raise RuntimeError("invalid request_id")
    if not _HEX64.fullmatch(values["expected_sha256"]):
        raise RuntimeError("invalid expected_sha256")
    return values


def _decode_content(value: str) -> bytes:
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError("content_b64 is not canonical base64") from exc
    if base64.b64encode(data).decode("ascii") != value:
        raise RuntimeError("content_b64 is not canonical base64")
    if len(data) > MAX_CONTENT_BYTES:
        raise RuntimeError("content exceeds bounded write limit")
    return data


def _target_name(path_text: str) -> str:
    target = Path(path_text)
    if not target.is_absolute() or target.parent != BASE_DIR:
        raise RuntimeError("target must be a direct child of /home/d2j3")
    name = target.name
    if name in {"", ".", ".."} or not _FILENAME.fullmatch(name):
        raise RuntimeError("target filename is not allowlisted")
    return name


def _github_permission(repository: str, actor: str, token: str) -> str:
    if not repository or "/" not in repository:
        raise RuntimeError("invalid repository")
    if not token:
        raise RuntimeError("GitHub token unavailable")
    quoted_actor = urllib.parse.quote(actor, safe="")
    url = f"https://api.github.com/repos/{repository}/collaborators/{quoted_actor}/permission"
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lion-moon-file-write/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError("unable to resolve actor permission") from exc
    permission = payload.get("permission") if isinstance(payload, dict) else None
    if not isinstance(permission, str):
        raise RuntimeError("unable to resolve actor permission")
    return permission


def _atomic_write(name: str, data: bytes) -> str:
    if not BASE_DIR.exists() or not BASE_DIR.is_dir() or BASE_DIR.is_symlink():
        raise RuntimeError("bounded base directory is unavailable or unsafe")

    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    dir_fd = os.open(BASE_DIR, os.O_RDONLY | directory | nofollow)
    temp_name = f".moon-write-{uuid.uuid4().hex}.tmp"
    try:
        fd = os.open(
            temp_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
            0o600,
            dir_fd=dir_fd,
        )
        try:
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise RuntimeError("short write")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)

        os.replace(temp_name, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        os.fsync(dir_fd)

        read_fd = os.open(name, os.O_RDONLY | nofollow, dir_fd=dir_fd)
        try:
            observed = bytearray()
            while True:
                chunk = os.read(read_fd, 65536)
                if not chunk:
                    break
                observed.extend(chunk)
                if len(observed) > MAX_CONTENT_BYTES:
                    raise RuntimeError("post-write content exceeded bound")
        finally:
            os.close(read_fd)
        return hashlib.sha256(bytes(observed)).hexdigest()
    finally:
        try:
            os.unlink(temp_name, dir_fd=dir_fd)
        except FileNotFoundError:
            pass
        os.close(dir_fd)


def execute(event: dict, *, repository: str, token: str, runner_name: str) -> dict[str, object]:
    if runner_name != "lion-moon-r9d8-test":
        raise RuntimeError("unexpected MOON runner")
    issue = event.get("issue")
    comment = event.get("comment")
    sender = event.get("sender")
    if not isinstance(issue, dict) or int(issue.get("number", 0)) != CONTROL_ISSUE:
        raise RuntimeError("wrong control issue")
    if not isinstance(comment, dict) or not isinstance(comment.get("body"), str):
        raise RuntimeError("missing issue comment")
    if not isinstance(sender, dict) or not isinstance(sender.get("login"), str):
        raise RuntimeError("missing actor")

    actor = sender["login"]
    permission = _github_permission(repository, actor, token)
    if permission not in TRUSTED_PERMISSIONS:
        raise RuntimeError("actor permission is not trusted")

    fields = _parse_envelope(comment["body"])
    data = _decode_content(fields["content_b64"])
    expected = fields["expected_sha256"]
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("pre-write content digest mismatch")
    name = _target_name(fields["path"])
    observed = _atomic_write(name, data)
    if observed != expected:
        raise RuntimeError("post-write digest mismatch")

    return {
        "schema_version": "1.0.0",
        "operation": "MOON_FILE_WRITE",
        "request_id": fields["request_id"],
        "actor": actor,
        "permission": permission,
        "path": str(BASE_DIR / name),
        "bytes": len(data),
        "sha256": observed,
        "runner": runner_name,
        "effect": "RECONCILED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--runner-name", required=True)
    args = parser.parse_args(argv)
    event = json.loads(Path(args.event).read_text(encoding="utf-8"))
    if not isinstance(event, dict):
        raise RuntimeError("event must be an object")
    receipt = execute(
        event,
        repository=args.repository,
        token=os.environ.get(args.token_env, ""),
        runner_name=args.runner_name,
    )
    print("MOON-FILE-WRITE-RECEIPT v1")
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

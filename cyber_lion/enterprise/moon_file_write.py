"""Canonical, bounded MOON host file-write entrypoint.

The issue comment describes intent only. A write is reachable only through an exact request,
current permission-backed admission, restart-durable single-use fence, effect provider, independent
post-effect observation and reconciliation. No shell or arbitrary path surface is exposed.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from dataclasses import dataclass
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import stat
import urllib.parse
import uuid

from cyber_lion.contracts.moon_file_write import (
    BASE_DIR as BASE_DIR_TEXT,
    CONTROL_ISSUE,
    MAX_CONTENT_BYTES,
    REPOSITORY,
    RUNNER_NAME,
    MoonFileWriteRequest,
)
from cyber_lion.enterprise.moon_file_write_mediation import (
    CanonicalMoonFileWriteAdmission,
    CanonicalMoonFileWriteMediator,
    DurableMoonFileWriteFence,
    MoonFileWriteMediationError,
    MoonFileWriteObserver,
    moon_file_write_effect_key,
)

PREFIX = "MOON-FILE-WRITE v2"
BASE_DIR = Path(BASE_DIR_TEXT)
MAX_PERMISSION_RESPONSE_BYTES = 65536
TRUSTED_PERMISSIONS = {"admin", "maintain", "write"}
FENCE_PATH = "/home/d2j3/.lion-moon-file-write-fence.sqlite3"
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_FILENAME = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_FIELD_ORDER = (
    "path",
    "operation_mode",
    "expected_previous_state",
    "expected_previous_sha256",
    "content_b64",
    "expected_sha256",
    "request_id",
)
_GITHUB_API_HOST = "api.github.com"


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
    previous = values["expected_previous_sha256"]
    if previous != "-" and _HEX64.fullmatch(previous) is None:
        raise RuntimeError("invalid expected_previous_sha256")
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
    if name in {"", ".", "..", Path(FENCE_PATH).name} or not _FILENAME.fullmatch(name):
        raise RuntimeError("target filename is not allowlisted")
    return name


def _github_permission(repository: str, actor: str, token: str) -> str:
    if repository != REPOSITORY or not _REPOSITORY.fullmatch(repository):
        raise RuntimeError("invalid repository")
    if not actor:
        raise RuntimeError("invalid actor")
    if not token:
        raise RuntimeError("GitHub token unavailable")
    quoted_actor = urllib.parse.quote(actor, safe="")
    path = f"/repos/{repository}/collaborators/{quoted_actor}/permission"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "lion-moon-file-write/2",
    }
    connection = http.client.HTTPSConnection(_GITHUB_API_HOST, 443, timeout=20)
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError("unable to resolve actor permission")
        raw = response.read(MAX_PERMISSION_RESPONSE_BYTES + 1)
        if len(raw) > MAX_PERMISSION_RESPONSE_BYTES:
            raise RuntimeError("unable to resolve actor permission")
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("unable to resolve actor permission") from exc
    except (OSError, http.client.HTTPException) as exc:
        raise RuntimeError("unable to resolve actor permission") from exc
    finally:
        connection.close()
    permission = payload.get("permission") if isinstance(payload, dict) else None
    if not isinstance(permission, str):
        raise RuntimeError("unable to resolve actor permission")
    return permission


@dataclass(frozen=True)
class _PermissionAdmissionResolver:
    repository: str
    token: str
    expected_actor: str
    provider_id: str = "github-collaborator-permission-pdp-v1"

    def resolve(self, request: MoonFileWriteRequest) -> CanonicalMoonFileWriteAdmission:
        request.validate()
        if request.repository != self.repository or request.actor_login != self.expected_actor:
            raise MoonFileWriteMediationError("authority subject substitution")
        permission = _github_permission(self.repository, self.expected_actor, self.token)
        if permission not in TRUSTED_PERMISSIONS:
            raise MoonFileWriteMediationError("actor permission is not trusted")
        authority_source_digest = hashlib.sha256(
            b"LION/MOON-GITHUB-PERMISSION-SOURCE/1\0"
            + json.dumps(
                {"repository": self.repository, "actor": self.expected_actor, "permission": permission},
                sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        pdp_decision_digest = hashlib.sha256(
            b"LION/MOON-FILE-WRITE-PDP/1\0"
            + json.dumps(
                {"authority_source_digest": authority_source_digest, "decision": "ALLOW", "scope": request.target_path},
                sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        admission = CanonicalMoonFileWriteAdmission(
            request_digest=request.request_digest,
            repository=request.repository,
            control_issue=request.control_issue,
            actor_login=request.actor_login,
            runner_name=request.runner_name,
            target_path=request.target_path,
            operation_mode=request.operation_mode,
            expected_previous_state=request.expected_previous_state,
            expected_previous_sha256=request.expected_previous_sha256,
            intended_content_sha256=request.intended_content_sha256,
            intended_content_size=request.intended_content_size,
            source_event_digest=request.source_event_digest,
            authority_source_digest=authority_source_digest,
            pdp_decision_digest=pdp_decision_digest,
            authority_epoch=0,
            provider_id=self.provider_id,
        ).sealed()
        return admission


class ExactMoonFileWriteEffectProvider:
    """The only MOON provider allowed to materialize the selected host effect."""

    provider_id = "moon-exact-host-file-write-v1"

    def __init__(self, *, content: bytes, fence: DurableMoonFileWriteFence):
        if type(fence) is not DurableMoonFileWriteFence:
            raise MoonFileWriteMediationError("exact durable fence required")
        if not isinstance(content, bytes) or len(content) > MAX_CONTENT_BYTES:
            raise MoonFileWriteMediationError("bounded exact content required")
        self._content = content
        self._fence = fence

    @staticmethod
    def _safe_dir_fd() -> int:
        base_stat = os.lstat(BASE_DIR)
        if stat.S_ISLNK(base_stat.st_mode) or not stat.S_ISDIR(base_stat.st_mode):
            raise MoonFileWriteMediationError("bounded base directory unsafe")
        return os.open(BASE_DIR, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))

    @staticmethod
    def _hash_existing(dir_fd: int, name: str) -> str:
        fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=dir_fd)
        try:
            h = hashlib.sha256(); total = 0
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_CONTENT_BYTES:
                    raise MoonFileWriteMediationError("existing target exceeds bounded size")
                h.update(chunk)
            return h.hexdigest()
        finally:
            os.close(fd)

    def write_exact(self, request: MoonFileWriteRequest, admission: CanonicalMoonFileWriteAdmission) -> None:
        if type(request) is not MoonFileWriteRequest or type(admission) is not CanonicalMoonFileWriteAdmission:
            raise MoonFileWriteMediationError("exact request/admission required")
        request.validate(); admission.validate(); admission.binds(request)
        if hashlib.sha256(self._content).hexdigest() != request.intended_content_sha256 or len(self._content) != request.intended_content_size:
            raise MoonFileWriteMediationError("effect content substitution")
        effect_key = moon_file_write_effect_key(request, admission)
        if self._fence.get(effect_key).state != "ATTEMPTED":
            raise MoonFileWriteMediationError("write requires ATTEMPTED durable fence")
        name = _target_name(request.target_path)
        dir_fd = self._safe_dir_fd()
        temp_name = f".moon-mediated-{uuid.uuid4().hex}.tmp"
        try:
            if request.operation_mode == "CREATE_ONLY":
                try:
                    os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise MoonFileWriteMediationError("CREATE_ONLY target exists at effect time")
            else:
                try:
                    current = self._hash_existing(dir_fd, name)
                except (FileNotFoundError, OSError) as exc:
                    raise MoonFileWriteMediationError("REPLACE target unavailable at effect time") from exc
                if current != request.expected_previous_sha256:
                    raise MoonFileWriteMediationError("REPLACE target changed at effect time")

            fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=dir_fd)
            try:
                view = memoryview(self._content)
                while view:
                    written = os.write(fd, view)
                    if written <= 0:
                        raise MoonFileWriteMediationError("short write")
                    view = view[written:]
                os.fsync(fd)
            finally:
                os.close(fd)

            if request.operation_mode == "CREATE_ONLY":
                try:
                    os.link(temp_name, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd, follow_symlinks=False)
                except FileExistsError as exc:
                    raise MoonFileWriteMediationError("CREATE_ONLY target raced into existence") from exc
                os.unlink(temp_name, dir_fd=dir_fd)
            else:
                if self._hash_existing(dir_fd, name) != request.expected_previous_sha256:
                    raise MoonFileWriteMediationError("REPLACE target drift before commit")
                os.replace(temp_name, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
            os.fsync(dir_fd)
        finally:
            try:
                os.unlink(temp_name, dir_fd=dir_fd)
            except FileNotFoundError:
                pass
            os.close(dir_fd)


def _make_request(event: dict, fields: dict[str, str], data: bytes, *, repository: str, runner_name: str, event_digest: str) -> MoonFileWriteRequest:
    sender = event.get("sender")
    actor = sender.get("login") if isinstance(sender, dict) else None
    if not isinstance(actor, str) or not actor:
        raise RuntimeError("missing actor")
    expected_previous_sha256 = None if fields["expected_previous_sha256"] == "-" else fields["expected_previous_sha256"]
    return MoonFileWriteRequest(
        schema_version="1.0.0",
        request_id=fields["request_id"], repository=repository, control_issue=CONTROL_ISSUE,
        actor_login=actor, runner_name=runner_name, target_path=str(BASE_DIR / _target_name(fields["path"])),
        operation_mode=fields["operation_mode"], expected_previous_state=fields["expected_previous_state"],
        expected_previous_sha256=expected_previous_sha256, intended_content_sha256=fields["expected_sha256"],
        intended_content_size=len(data), source_event_digest=event_digest,
    ).sealed()


def _execute(event: dict, *, repository: str, token: str, runner_name: str, event_digest: str) -> dict[str, object]:
    if runner_name != RUNNER_NAME:
        raise RuntimeError("unexpected MOON runner")
    if repository != REPOSITORY:
        raise RuntimeError("repository substitution denied")
    issue = event.get("issue"); comment = event.get("comment"); sender = event.get("sender")
    if not isinstance(issue, dict) or int(issue.get("number", 0)) != CONTROL_ISSUE:
        raise RuntimeError("wrong control issue")
    if not isinstance(comment, dict) or not isinstance(comment.get("body"), str):
        raise RuntimeError("missing issue comment")
    if not isinstance(sender, dict) or not isinstance(sender.get("login"), str):
        raise RuntimeError("missing actor")
    fields = _parse_envelope(comment["body"]); data = _decode_content(fields["content_b64"])
    if hashlib.sha256(data).hexdigest() != fields["expected_sha256"]:
        raise RuntimeError("pre-write content digest mismatch")
    request = _make_request(event, fields, data, repository=repository, runner_name=runner_name, event_digest=event_digest)
    fence = DurableMoonFileWriteFence(FENCE_PATH)
    resolver = _PermissionAdmissionResolver(repository, token, request.actor_login)
    effect = ExactMoonFileWriteEffectProvider(content=data, fence=fence)
    mediator = CanonicalMoonFileWriteMediator(
        admissions=resolver, effect=effect, fence=fence,
        pre_observer=MoonFileWriteObserver(), post_observer=MoonFileWriteObserver(),
    )
    receipt = mediator.execute(request)
    return {
        "schema_version": "2.0.0", "operation": "MOON_FILE_WRITE", "request_id": request.request_id,
        "actor": request.actor_login, "path": request.target_path, "bytes": request.intended_content_size,
        "sha256": receipt.observed_sha256, "runner": runner_name, "effect_key": receipt.effect_key,
        "request_digest": request.request_digest, "admission_digest": receipt.admission_digest,
        "pre_observation_digest": receipt.pre_observation_digest,
        "post_observation_digest": receipt.post_observation_digest,
        "reconciliation_digest": receipt.reconciliation_digest,
        "effect": "RECONCILED" if receipt.result == "MATCH" else receipt.result,
        "authority_effect": False, "repository_effect": False, "external_network_effect": False,
    }


def execute(event: dict, *, repository: str, token: str, runner_name: str) -> dict[str, object]:
    """Test/API wrapper; workflow main binds the digest to exact event-file bytes."""
    event_digest = hashlib.sha256(json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    return _execute(event, repository=repository, token=token, runner_name=runner_name, event_digest=event_digest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True); parser.add_argument("--repository", required=True)
    parser.add_argument("--token-env", default="GITHUB_TOKEN"); parser.add_argument("--runner-name", required=True)
    args = parser.parse_args(argv)
    raw = Path(args.event).read_bytes()
    event = json.loads(raw)
    if not isinstance(event, dict):
        raise RuntimeError("event must be an object")
    receipt = _execute(event, repository=args.repository, token=os.environ.get(args.token_env, ""), runner_name=args.runner_name,
                       event_digest=hashlib.sha256(raw).hexdigest())
    print("MOON-FILE-WRITE-RECEIPT v2")
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Linux worker artifact storage; byte integrity is not runtime authorization.

Production writes must be called by the canonical admitted executor. Direct calls
are suitable for operator-scoped component tests, not mission admission. Storage
requires a private caller-owned root. It is not a security boundary against a
malicious process with the same UID or a writable mount of the same root.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping
from uuid import uuid4

SCHEMA_VERSION = "1.1.0"
WRITE_KIND = "COOPERATIVE_ARTIFACT_WRITE"
VERIFY_KIND = "COOPERATIVE_ARTIFACT_VERIFY"
MAX_ARTIFACT_BYTES = 131072
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


class CooperativeArtifactError(ValueError):
    pass


def _id(value: Any, name: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise CooperativeArtifactError(name)
    return value


def _name(value: Any) -> str:
    if type(value) is not str or _NAME.fullmatch(value) is None:
        raise CooperativeArtifactError("artifact_name")
    return value


def _digest(value: Any, name: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise CooperativeArtifactError(name)
    return value


def _generation(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise CooperativeArtifactError("generation")
    return value


def _root(value: str | Path) -> Path:
    root = Path(value)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise CooperativeArtifactError("artifact root")
    if root != root.resolve(strict=True):
        raise CooperativeArtifactError("artifact root symlink indirection")
    return root


def artifact_path(root: str | Path, *, mission_id: str, generation: int, artifact_name: str) -> Path:
    return _root(root) / _id(mission_id, "mission_id") / f"g{_generation(generation):08d}" / _name(artifact_name)


def validate_write_payload(payload: Mapping[str, Any], worker_id: str) -> tuple[dict[str, Any], bytes]:
    if not isinstance(payload, Mapping) or payload.get("kind") != WRITE_KIND:
        raise CooperativeArtifactError("write kind")
    # All caller identities are checked before mkdir, open or publication.
    out = {
        "kind": WRITE_KIND,
        "mission_id": _id(payload.get("mission_id"), "mission_id"),
        "assignment_id": _id(payload.get("assignment_id"), "assignment_id"),
        "generation": _generation(payload.get("generation")),
        "artifact_name": _name(payload.get("artifact_name")),
        "producer_worker_id": _id(worker_id, "worker_id"),
        "producer_model_call_id": _id(payload.get("producer_model_call_id"), "producer_model_call_id"),
        "parent_response_digest": _digest(payload.get("parent_response_digest"), "parent_response_digest"),
    }
    content = payload.get("content")
    if type(content) is not str:
        raise CooperativeArtifactError("content")
    try:
        data = content.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise CooperativeArtifactError("invalid UTF-8 content") from exc
    if not 1 <= len(data) <= MAX_ARTIFACT_BYTES:
        raise CooperativeArtifactError("content size")
    expected = _digest(payload.get("expected_sha256"), "expected_sha256")
    if sha256(data).hexdigest() != expected:
        raise CooperativeArtifactError("payload digest mismatch")
    out["artifact_sha256"] = expected
    out["artifact_bytes"] = len(data)
    return out, data


def _linux_storage_required() -> None:
    if os.name != "posix" or not all(hasattr(os, x) for x in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK")):
        raise CooperativeArtifactError("Linux descriptor-relative storage required")


@contextmanager
def _generation_dir(root: Path, mission_id: str, generation: int, *, create: bool):
    _linux_storage_required()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    handles = []
    try:
        fd = os.open(root, flags)
        handles.append(fd)
        for name in (mission_id, f"g{generation:08d}"):
            if create:
                try:
                    os.mkdir(name, 0o750, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
            fd = os.open(name, flags, dir_fd=fd)
            handles.append(fd)
        yield fd
    except OSError as exc:
        raise CooperativeArtifactError("artifact directory unavailable or unsafe") from exc
    finally:
        for fd in reversed(handles):
            os.close(fd)


def _read_at(dir_fd: int, name: str) -> bytes:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise CooperativeArtifactError("artifact must be a private regular file")
        if before.st_size > MAX_ARTIFACT_BYTES:
            raise CooperativeArtifactError("artifact too large")
        data = handle.read(MAX_ARTIFACT_BYTES + 1)
        after = os.fstat(handle.fileno())
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        if len(data) != before.st_size or len(data) > MAX_ARTIFACT_BYTES or any(getattr(before,k) != getattr(after,k) for k in fields):
            raise CooperativeArtifactError("artifact changed during read")
        return data


def materialize_text(root: str | Path, payload: Mapping[str, Any], *, worker_id: str) -> dict[str, Any]:
    """Publish atomically WITHOUT replacing an existing generation's artifact."""
    out, data = validate_write_payload(payload, worker_id)
    root_path = _root(root)
    name = out["artifact_name"]
    with _generation_dir(root_path, out["mission_id"], out["generation"], create=True) as dfd:
        temp_name = ".lion-publish-" + uuid4().hex
        created = False
        try:
            fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640, dir_fd=dfd)
            created = True
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            # Unlike replace(), link() fails if another writer already won.
            try:
                os.link(temp_name, name, src_dir_fd=dfd, dst_dir_fd=dfd, follow_symlinks=False)
            except FileExistsError as exc:
                raise CooperativeArtifactError("artifact already exists") from exc
        finally:
            if created:
                os.unlink(temp_name, dir_fd=dfd)
        os.fsync(dfd)
        observed = _read_at(dfd, name)
        if observed != data:
            raise CooperativeArtifactError("artifact readback mismatch")
    return {**out, "artifact_path": str(root_path / out["mission_id"] / f"g{out['generation']:08d}" / name),
            "readback_match": True, "authority_effect": "NONE", "storage_profile": "LINUX_PRIVATE_ROOT_NO_REPLACE"}


def verify_text(root: str | Path, payload: Mapping[str, Any], *, worker_id: str) -> dict[str, Any]:
    """A separate read checks bytes, not the truth/authorship of a claimed producer."""
    if not isinstance(payload, Mapping) or payload.get("kind") != VERIFY_KIND:
        raise CooperativeArtifactError("verify kind")
    mission = _id(payload.get("mission_id"), "mission_id")
    assignment = _id(payload.get("source_assignment_id"), "source_assignment_id")
    generation = _generation(payload.get("generation"))
    name = _name(payload.get("artifact_name"))
    expected = _digest(payload.get("expected_sha256"), "expected_sha256")
    producer = _id(payload.get("expected_producer_worker_id"), "expected_producer_worker_id")
    verifier = _id(worker_id, "worker_id")
    if verifier == producer:
        raise CooperativeArtifactError("verifier must differ from producer")
    root_path = _root(root)
    with _generation_dir(root_path, mission, generation, create=False) as dfd:
        observed = _read_at(dfd, name)
    actual = sha256(observed).hexdigest()
    if actual != expected:
        raise CooperativeArtifactError("artifact digest mismatch")
    return {"kind": VERIFY_KIND, "mission_id": mission, "source_assignment_id": assignment,
            "generation": generation, "artifact_name": name,
            "artifact_path": str(root_path / mission / f"g{generation:08d}" / name),
            "artifact_sha256": actual, "artifact_bytes": len(observed),
            "expected_producer_worker_id": producer, "verifier_worker_id": verifier,
            "digest_match": True, "authority_effect": "NONE"}

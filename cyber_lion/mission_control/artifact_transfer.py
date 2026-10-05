"""Bounded, byte-preserving artifact transport; no execution or authority.

The caller must obtain expected_binding and expected_sha256 independently of
an incoming bundle. This carrier does not replace sbom/AID, authorize export,
claim a mission lease, or advance Mission Control. Materialization uses a fresh
workspace under a caller-owned private directory, never a shared checkout.
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
import stat
import tempfile
from typing import Mapping

SCHEMA = "lion.artifact-transfer-bundle/v1"
MAX_FILES = 64
MAX_FILE_BYTES = 131072
MAX_TOTAL_BYTES = 524288
MAX_BUNDLE_BYTES = 800000
BINDING_FIELDS = frozenset({
    "repository", "source_head", "mission_id", "assignment_id", "conversation_id",
    "binding_epoch", "generation", "lease_generation", "context_digest",
    "projection_digest", "request_id", "producer_ref",
})
INTEGER_FIELDS = frozenset({"binding_epoch", "generation", "lease_generation"})
DIGEST_FIELDS = frozenset({"context_digest", "projection_digest"})
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SEGMENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,79}\Z")
_RESERVED = {"CON", "PRN", "AUX", "NUL", *("COM" + str(i) for i in range(10)), *("LPT" + str(i) for i in range(10))}
_SECRET_NAMES = {"credentials", "credentials.json", "secrets", "secrets.json", "id_rsa", "id_ed25519"}


class ArtifactTransferError(ValueError):
    """An invalid, substituted, oversized or nonportable transfer."""


def _json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def _load(raw: bytes) -> dict:
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ArtifactTransferError("duplicate JSON key")
            out[key] = value
        return out
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ArtifactTransferError("nonfinite JSON")))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ArtifactTransferError("invalid unambiguous UTF-8 JSON") from exc
    if type(value) is not dict:
        raise ArtifactTransferError("JSON object required")
    return value


def _binding(value: Mapping) -> dict:
    if not isinstance(value, Mapping) or set(value) != BINDING_FIELDS:
        raise ArtifactTransferError("binding fields")
    out = dict(value)
    for key, item in out.items():
        if key in INTEGER_FIELDS:
            if type(item) is not int or not 0 <= item <= 2147483647:
                raise ArtifactTransferError("binding integer")
        elif type(item) is not str or not 1 <= len(item) <= 256 or any(ord(c) < 33 or ord(c) > 126 for c in item):
            raise ArtifactTransferError("binding identifier")
    if re.fullmatch(r"[0-9a-f]{40}", out["source_head"]) is None:
        raise ArtifactTransferError("source head")
    if any(_SHA.fullmatch(out[key]) is None for key in DIGEST_FIELDS):
        raise ArtifactTransferError("context/projection digest")
    return out


def _path(value: str) -> str:
    if type(value) is not str or not 1 <= len(value) <= 160:
        raise ArtifactTransferError("portable path length")
    parts = value.split("/")
    for part in parts:
        if (not _SEGMENT.fullmatch(part) or part.endswith(".")
                or part.split(".", 1)[0].upper() in _RESERVED
                or part.lower() in _SECRET_NAMES or part.casefold() == "_lion_transfer.json"):
            raise ArtifactTransferError("nonportable or secret-like path")
    return value


def _paths(names: list[str]) -> None:
    seen = set()
    for name in names:
        folded = _path(name).casefold()
        if folded in seen:
            raise ArtifactTransferError("case-insensitive path collision")
        seen.add(folded)
    for name in seen:
        if any("/".join(name.split("/")[:i]) in seen for i in range(1, len(name.split("/")))):
            raise ArtifactTransferError("file/directory collision")


def create_bundle(files: Mapping[str, bytes], binding: Mapping, *, parent_transfer_sha256: str | None = None) -> bytes:
    """Encode actual bytes. This is packaging, not a build or code review."""
    bound = _binding(binding)
    if not isinstance(files, Mapping) or not 1 <= len(files) <= MAX_FILES:
        raise ArtifactTransferError("file count")
    _paths(list(files))
    if parent_transfer_sha256 is not None and (type(parent_transfer_sha256) is not str or not _SHA.fullmatch(parent_transfer_sha256)):
        raise ArtifactTransferError("parent transfer digest")
    rows = []
    total = 0
    for name in sorted(files):
        data = files[name]
        if type(data) is not bytes or len(data) > MAX_FILE_BYTES:
            raise ArtifactTransferError("file bytes/limit")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ArtifactTransferError("aggregate byte limit")
        rows.append({"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                     "data_b64": base64.b64encode(data).decode("ascii")})
    raw = _json({"schema": SCHEMA, "binding": bound, "parent_transfer_sha256": parent_transfer_sha256,
                 "authority_effect": "NONE", "files": rows})
    if len(raw) > MAX_BUNDLE_BYTES:
        raise ArtifactTransferError("bundle byte limit")
    return raw


def verify_bundle(raw: bytes, expected_sha256: str, expected_binding: Mapping) -> tuple[dict, dict[str, bytes]]:
    """Verify the entire carrier before any filesystem effect is attempted."""
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_BUNDLE_BYTES:
        raise ArtifactTransferError("bundle byte limit/type")
    if type(expected_sha256) is not str or not _SHA.fullmatch(expected_sha256):
        raise ArtifactTransferError("expected digest")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ArtifactTransferError("transfer digest mismatch")
    value = _load(raw)
    if set(value) != {"schema", "binding", "parent_transfer_sha256", "authority_effect", "files"}:
        raise ArtifactTransferError("bundle fields")
    if value["schema"] != SCHEMA or value["authority_effect"] != "NONE":
        raise ArtifactTransferError("schema/authority")
    if _binding(value["binding"]) != _binding(expected_binding):
        raise ArtifactTransferError("binding mismatch")
    parent = value["parent_transfer_sha256"]
    if parent is not None and (type(parent) is not str or not _SHA.fullmatch(parent)):
        raise ArtifactTransferError("parent transfer digest")
    rows = value["files"]
    if type(rows) is not list or not 1 <= len(rows) <= MAX_FILES:
        raise ArtifactTransferError("file count")
    decoded = {}
    names = []
    total = 0
    for row in rows:
        if type(row) is not dict or set(row) != {"path", "size", "sha256", "data_b64"}:
            raise ArtifactTransferError("file fields")
        name = _path(row["path"])
        names.append(name)
        size = row["size"]
        encoded = row["data_b64"]
        if type(size) is not int or not 0 <= size <= MAX_FILE_BYTES:
            raise ArtifactTransferError("file size")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise ArtifactTransferError("aggregate byte limit")
        if type(encoded) is not str or len(encoded) != 4 * ((size + 2) // 3):
            raise ArtifactTransferError("encoded length")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ArtifactTransferError("invalid base64") from exc
        if len(data) != size or base64.b64encode(data).decode("ascii") != encoded:
            raise ArtifactTransferError("noncanonical base64 or size mismatch")
        if type(row["sha256"]) is not str or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ArtifactTransferError("file digest mismatch")
        decoded[name] = data
    _paths(names)
    return value, decoded


def _read(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ArtifactTransferError("regular file required")
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ArtifactTransferError("file read limit")
    return data


def verify_workspace(root: str | Path, raw: bytes, expected_sha256: str, expected_binding: Mapping) -> dict:
    value, files = verify_bundle(raw, expected_sha256, expected_binding)
    path = Path(root)
    if path.is_symlink() or not path.is_dir():
        raise ArtifactTransferError("workspace must be a directory, not a symlink")
    found = set()
    for node in path.rglob("*"):
        if node.is_symlink():
            raise ArtifactTransferError("workspace symlink")
        mode = node.stat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ArtifactTransferError("workspace special file")
        found.add(node.relative_to(path).as_posix())
    if found != set(files) | {"_LION_TRANSFER.json"}:
        raise ArtifactTransferError("workspace file set mismatch")
    if _read(path / "_LION_TRANSFER.json", MAX_BUNDLE_BYTES) != raw:
        raise ArtifactTransferError("workspace carrier mismatch")
    for name, data in files.items():
        if _read(path / name, MAX_FILE_BYTES) != data:
            raise ArtifactTransferError("workspace content mismatch")
    return {"transfer_sha256": expected_sha256, "binding": value["binding"], "file_count": len(files),
            "payload_bytes": sum(map(len, files.values())), "readback_match": True,
            "authority_effect": "NONE", "execution_performed": False}


def materialize_bundle(raw: bytes, expected_sha256: str, expected_binding: Mapping, private_parent: str | Path) -> dict:
    """Write a fresh isolated workspace, never overwrite an existing product.

    The parent must be controlled by the caller and not concurrently mutable by
    an adversary. This is not a privileged multi-tenant filesystem boundary.
    Partial workspaces are retained without a complete manifest on write failure.
    """
    _, files = verify_bundle(raw, expected_sha256, expected_binding)
    if any(name.casefold() == "_lion_transfer.json" for name in files):
        raise ArtifactTransferError("reserved carrier name")
    parent = Path(private_parent)
    if parent.is_symlink() or not parent.is_dir() or parent.absolute() != parent.resolve():
        raise ArtifactTransferError("private parent must exist without symlink indirection")
    workspace = Path(tempfile.mkdtemp(prefix="lion-product-", dir=parent))
    for name, data in files.items():
        target = workspace / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    with (workspace / "_LION_TRANSFER.json").open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    result = verify_workspace(workspace, raw, expected_sha256, expected_binding)
    return {**result, "workspace": str(workspace)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("verify", "materialize"))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--binding", type=Path, required=True, help="independently supplied expected binding")
    parser.add_argument("--private-parent", type=Path)
    args = parser.parse_args(argv)
    try:
        raw = _read(args.bundle, MAX_BUNDLE_BYTES)
        binding = _load(_read(args.binding, 8192))
        if args.operation == "materialize":
            if args.private_parent is None:
                raise ArtifactTransferError("private-parent required")
            out = materialize_bundle(raw, args.expected_sha256, binding, args.private_parent)
        else:
            value, files = verify_bundle(raw, args.expected_sha256, binding)
            out = {"transfer_sha256": args.expected_sha256, "binding": value["binding"],
                   "files": sorted(files), "authority_effect": "NONE", "execution_performed": False}
        print(json.dumps(out, ensure_ascii=True, sort_keys=True))
        return 0
    except (ArtifactTransferError, OSError) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}, ensure_ascii=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

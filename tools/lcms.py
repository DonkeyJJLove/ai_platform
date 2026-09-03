"""Deterministic, non-effectful LCMS -> ActionSpec compiler for C1.

LCMS is a candidate surface syntax only.  It does not execute actions, select
providers, perform transport, mint authority, or infer runtime support.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import unicodedata
from typing import Any

LCMS_GRAMMAR_VERSION = "lion.lcms/v1.0-candidate"
LCMS_HEADER = "LCMS/1.0"
ACTION_SPEC_SCHEMA_VERSION = "lion.action-spec/v1.3-candidate"

ERROR_CODES = frozenset(
    {
        "UNKNOWN_FIELD",
        "DUPLICATE_FIELD",
        "UNKNOWN_ENUM",
        "UNKNOWN_ACTION_KIND",
        "ALIAS_NOT_CANONICAL",
        "NONCANONICAL_UNICODE",
        "AMBIGUOUS_UNIT",
        "AMBIGUOUS_BOOLEAN",
        "PATH_TRAVERSAL",
        "RELATIVE_EXECUTABLE_PATH",
        "IMPLICIT_DEFAULT_WITH_EFFECT",
        "RAW_SHELL_STRING",
        "SHELL_TRUE",
        "ENVIRONMENT_INHERITANCE",
        "UNBOUND_WORKSPACE",
        "MALFORMED_DIGEST",
        "DUPLICATE_SET_MEMBER",
        "UNKNOWN_PIPELINE_EDGE",
        "CYCLIC_PIPELINE",
        "UNDECLARED_PIPELINE_NODE",
    }
)

KINDS = frozenset(
    {
        "process.exec",
        "filesystem.read",
        "filesystem.write",
        "repository.observe",
        "repository.prepare_candidate",
        "repository.attach_exact",
        "test.execute",
        "artifact.generate",
        "robot.task",
    }
)
NETWORK_MODES = frozenset({"DENY", "READ_ONLY_PINNED", "ALLOW_EXACT"})
OBSERVER_CLASSES = frozenset({"independent", "deterministic_independent"})
RECONCILIATION_MODES = frozenset({"EXACT", "PHYSICAL_POSTCONDITION"})
STDOUT_MODES = frozenset({"CAPTURE", "DISCARD"})
STDERR_MODES = STDOUT_MODES

_BASE_FIELDS = frozenset(
    {
        "schema_version",
        "action_id",
        "kind",
        "intent_ref",
        "mission_ref",
        "autonomy_ref",
        "bean_ref",
        "target.host",
        "target.environment",
        "target.runtime",
        "authority_request.domain",
        "authority_request.capability",
        "authority_request.grant_ref",
        "boundary.shell",
        "boundary.network",
        "boundary.filesystem_read",
        "boundary.filesystem_write",
        "boundary.process_children",
        "boundary.timeout_ms",
        "boundary.max_processes",
        "boundary.memory_limit_bytes",
        "preconditions",
        "expected_effects",
        "forbidden_effects",
        "observation.observer_class",
        "observation.required_events",
        "reconciliation.mode",
        "reconciliation.receipt",
    }
)

_PROCESS_FIELDS = frozenset(
    {
        "executable.path",
        "executable.digest",
        "arguments",
        "workspace.repository",
        "workspace.commit",
        "workspace.tree",
        "workspace.path",
        "environment.inherit",
        "environment.allow",
        "io.stdin",
        "io.stdout",
        "io.stderr",
        "io.tty",
    }
)

_ALLOWED_FIELDS = _BASE_FIELDS | _PROCESS_FIELDS

_ALIAS_FIELDS = frozenset(
    {
        "action",
        "action.kind",
        "cmd",
        "env",
        "repo",
        "shell",
        "network",
        "target",
        "workspace",
    }
)
_RAW_SHELL_FIELDS = frozenset({"command", "shell_command", "pipeline"})
_PIPELINE_REJECTIONS = {
    "pipeline.edge": "UNKNOWN_PIPELINE_EDGE",
    "pipeline.cycle": "CYCLIC_PIPELINE",
    "pipeline.node": "UNDECLARED_PIPELINE_NODE",
}

_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_ACTION_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:.-]{0,255}$")


class LCMSError(ValueError):
    """Fail-closed LCMS parse/normalization error with a stable class."""

    def __init__(self, code: str, detail: str):
        if code not in ERROR_CODES:
            raise ValueError(f"unknown LCMS error code {code!r}")
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class CompiledActionSpec:
    grammar_version: str
    canonical_bytes: bytes
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return json.loads(self.canonical_bytes.decode("ascii"))


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-RFC8259 constant {value}")


def _pairs_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LCMSError("DUPLICATE_FIELD", f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _json_value(raw: str, field: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=_pairs_object,
            parse_constant=_reject_constant,
        )
    except LCMSError:
        raise
    except (ValueError, json.JSONDecodeError) as exc:
        raise LCMSError("UNKNOWN_FIELD", f"invalid JSON value for {field}") from exc


def _parse_source(source: str) -> dict[str, Any]:
    if type(source) is not str:
        raise LCMSError("UNKNOWN_FIELD", "LCMS source must be a string")
    if "\r" in source or "\x00" in source:
        raise LCMSError("NONCANONICAL_UNICODE", "CR and NUL are not canonical LCMS")
    if source != unicodedata.normalize("NFC", source):
        raise LCMSError("NONCANONICAL_UNICODE", "source is not NFC")
    if any(ord(ch) > 0x7F for ch in source):
        raise LCMSError("NONCANONICAL_UNICODE", "C1 LCMS source is ASCII-only")

    lines = source.splitlines()
    if not lines or lines[0] != LCMS_HEADER:
        raise LCMSError("UNKNOWN_FIELD", f"first line must be {LCMS_HEADER}")
    if any(not line for line in lines[1:]):
        raise LCMSError("UNKNOWN_FIELD", "blank LCMS lines are not canonical")

    fields: dict[str, Any] = {}
    for line in lines[1:]:
        key, sep, raw = line.partition("=")
        if not sep or not key or key != key.strip():
            raise LCMSError("UNKNOWN_FIELD", "assignment must be exact key=json")
        if key in _RAW_SHELL_FIELDS:
            raise LCMSError("RAW_SHELL_STRING", f"{key} is not an LCMS field")
        if key in _ALIAS_FIELDS:
            raise LCMSError("ALIAS_NOT_CANONICAL", f"{key} is an alias, not canonical LCMS")
        if key in _PIPELINE_REJECTIONS:
            raise LCMSError(_PIPELINE_REJECTIONS[key], "pipelines are deferred in C1")
        if key.startswith("pipeline."):
            raise LCMSError("UNKNOWN_PIPELINE_EDGE", "pipelines are deferred in C1")
        if key not in _ALLOWED_FIELDS:
            raise LCMSError("UNKNOWN_FIELD", f"unknown LCMS field {key!r}")
        if key in fields:
            raise LCMSError("DUPLICATE_FIELD", f"duplicate LCMS field {key!r}")
        fields[key] = _json_value(raw, key)
    return fields


def _require_string(value: Any, field: str, *, nullable: bool = False, max_len: int = 4096) -> str | None:
    if value is None and nullable:
        return None
    if type(value) is not str or not value or len(value) > max_len:
        raise LCMSError("UNKNOWN_FIELD", f"{field} must be a bounded nonempty string")
    return value


def _require_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise LCMSError("AMBIGUOUS_BOOLEAN", f"{field} must be JSON true or false")
    return value


def _require_int(value: Any, field: str, minimum: int, maximum: int | None = None) -> int:
    if type(value) is not int:
        raise LCMSError("AMBIGUOUS_UNIT", f"{field} must be a unitless JSON integer")
    if value < minimum or (maximum is not None and value > maximum):
        raise LCMSError("AMBIGUOUS_UNIT", f"{field} is outside the canonical numeric range")
    return value


def _require_enum(value: Any, field: str, allowed: frozenset[str]) -> str:
    value = _require_string(value, field)
    assert isinstance(value, str)
    if value not in allowed:
        raise LCMSError("UNKNOWN_ENUM", f"{field} has an unknown enum value")
    return value


def _require_string_list(value: Any, field: str, *, max_items: int | None = None) -> list[str]:
    if type(value) is not list:
        raise LCMSError("UNKNOWN_FIELD", f"{field} must be a JSON array")
    if max_items is not None and len(value) > max_items:
        raise LCMSError("UNKNOWN_FIELD", f"{field} exceeds its item bound")
    result: list[str] = []
    for item in value:
        parsed = _require_string(item, field)
        assert isinstance(parsed, str)
        result.append(parsed)
    if len(result) != len(set(result)):
        raise LCMSError("DUPLICATE_SET_MEMBER", f"{field} contains a duplicate member")
    return result


def _require_env_map(value: Any) -> dict[str, str]:
    if type(value) is not dict:
        raise LCMSError("UNKNOWN_FIELD", "environment.allow must be a JSON object")
    result: dict[str, str] = {}
    for key in sorted(value):
        if type(key) is not str or not re.fullmatch(r'[A-Z_][A-Z0-9_]*', key):
            raise LCMSError("UNKNOWN_FIELD", "environment.allow keys must be canonical environment names")
        parsed = _require_string(value[key], f"environment.allow.{key}", max_len=4096)
        assert isinstance(parsed, str)
        result[key] = parsed
    return result


def _safe_absolute_path(value: Any, field: str, *, executable: bool = False) -> str:
    value = _require_string(value, field)
    assert isinstance(value, str)
    if not value.startswith("/"):
        code = "RELATIVE_EXECUTABLE_PATH" if executable else "PATH_TRAVERSAL"
        raise LCMSError(code, f"{field} must be absolute")
    if "\\" in value or "//" in value:
        raise LCMSError("PATH_TRAVERSAL", f"{field} is not a canonical POSIX path")
    segments = value.split("/")[1:]
    if any(segment in {".", ".."} for segment in segments):
        raise LCMSError("PATH_TRAVERSAL", f"{field} contains traversal")
    if any(segment == "" for segment in segments) and value != "/":
        raise LCMSError("PATH_TRAVERSAL", f"{field} contains an empty segment")
    return value


def _require_sha40(value: Any, field: str) -> str:
    value = _require_string(value, field)
    assert isinstance(value, str)
    if not _SHA40_RE.fullmatch(value):
        raise LCMSError("MALFORMED_DIGEST", f"{field} must be lowercase SHA-1 object identity")
    return value


def _require_sha256(value: Any, field: str) -> str:
    value = _require_string(value, field)
    assert isinstance(value, str)
    if not _SHA256_RE.fullmatch(value):
        raise LCMSError("MALFORMED_DIGEST", f"{field} must be sha256:<64 lowercase hex>")
    return value


def _validate_required(fields: dict[str, Any]) -> None:
    missing = sorted(_BASE_FIELDS - fields.keys())
    if missing:
        raise LCMSError(
            "IMPLICIT_DEFAULT_WITH_EFFECT",
            "missing explicit base field(s): " + ",".join(missing),
        )

    kind = fields["kind"]
    if type(kind) is str and kind == "process.exec":
        process_missing = sorted(_PROCESS_FIELDS - fields.keys())
        if process_missing:
            if any(name.startswith("workspace.") for name in process_missing):
                raise LCMSError("UNBOUND_WORKSPACE", "process.exec requires an exact workspace binding")
            raise LCMSError(
                "IMPLICIT_DEFAULT_WITH_EFFECT",
                "process.exec requires explicit execution-shaped fields",
            )
    elif _PROCESS_FIELDS & fields.keys():
        raise LCMSError(
            "IMPLICIT_DEFAULT_WITH_EFFECT",
            "execution-shaped fields are canonical only for process.exec",
        )


def _normalize(fields: dict[str, Any]) -> dict[str, Any]:
    _validate_required(fields)

    schema_version = _require_string(fields["schema_version"], "schema_version")
    if schema_version != ACTION_SPEC_SCHEMA_VERSION:
        raise LCMSError("UNKNOWN_ENUM", "schema_version is not the frozen C0 ActionSpec version")

    action_id = _require_string(fields["action_id"], "action_id", max_len=256)
    assert isinstance(action_id, str)
    if not _ACTION_ID_RE.fullmatch(action_id):
        raise LCMSError("UNKNOWN_FIELD", "action_id is not canonical")

    kind = _require_string(fields["kind"], "kind")
    assert isinstance(kind, str)
    if kind not in KINDS:
        raise LCMSError("UNKNOWN_ACTION_KIND", f"unsupported ActionSpec kind {kind!r}")

    target = {
        "host": _require_string(fields["target.host"], "target.host"),
        "environment": _require_string(fields["target.environment"], "target.environment"),
        "runtime": _require_string(fields["target.runtime"], "target.runtime"),
    }

    authority_request = {
        "domain": _require_string(fields["authority_request.domain"], "authority_request.domain"),
        "capability": _require_string(fields["authority_request.capability"], "authority_request.capability"),
        "grant_ref": _require_string(
            fields["authority_request.grant_ref"],
            "authority_request.grant_ref",
            nullable=True,
        ),
    }

    shell = _require_bool(fields["boundary.shell"], "boundary.shell")
    if shell:
        raise LCMSError("SHELL_TRUE", "boundary.shell=true is unrepresentable")

    boundary = {
        "shell": False,
        "network": _require_enum(fields["boundary.network"], "boundary.network", NETWORK_MODES),
        "filesystem_read": _require_string_list(fields["boundary.filesystem_read"], "boundary.filesystem_read"),
        "filesystem_write": _require_string_list(fields["boundary.filesystem_write"], "boundary.filesystem_write"),
        "process_children": _require_string_list(fields["boundary.process_children"], "boundary.process_children"),
        "timeout_ms": _require_int(fields["boundary.timeout_ms"], "boundary.timeout_ms", 1, 3_000_000),
        "max_processes": _require_int(fields["boundary.max_processes"], "boundary.max_processes", 1, 128),
        "memory_limit_bytes": _require_int(
            fields["boundary.memory_limit_bytes"],
            "boundary.memory_limit_bytes",
            1_048_576,
        ),
    }
    for field_name in ("filesystem_read", "filesystem_write", "process_children"):
        boundary[field_name] = [
            _safe_absolute_path(item, f"boundary.{field_name}")
            for item in boundary[field_name]
        ]

    preconditions = _require_string_list(fields["preconditions"], "preconditions")
    expected_effects = _require_string_list(fields["expected_effects"], "expected_effects")
    forbidden_effects = _require_string_list(fields["forbidden_effects"], "forbidden_effects")

    observation = {
        "observer_class": _require_enum(
            fields["observation.observer_class"],
            "observation.observer_class",
            OBSERVER_CLASSES,
        ),
        "required_events": _require_string_list(
            fields["observation.required_events"],
            "observation.required_events",
        ),
    }
    reconciliation = {
        "mode": _require_enum(
            fields["reconciliation.mode"],
            "reconciliation.mode",
            RECONCILIATION_MODES,
        ),
        "receipt": _require_string(fields["reconciliation.receipt"], "reconciliation.receipt"),
    }
    if reconciliation["receipt"] != "REQUIRED":
        raise LCMSError("UNKNOWN_ENUM", "reconciliation.receipt must be REQUIRED")

    spec: dict[str, Any] = {
        "schema_version": schema_version,
        "action_id": action_id,
        "kind": kind,
        "intent_ref": _require_string(fields["intent_ref"], "intent_ref"),
        "mission_ref": _require_string(fields["mission_ref"], "mission_ref"),
        "autonomy_ref": _require_string(fields["autonomy_ref"], "autonomy_ref"),
        "bean_ref": _require_string(fields["bean_ref"], "bean_ref"),
        "target": target,
        "authority_request": authority_request,
        "boundary": boundary,
        "preconditions": preconditions,
        "expected_effects": expected_effects,
        "forbidden_effects": forbidden_effects,
        "observation": observation,
        "reconciliation": reconciliation,
    }

    if kind == "process.exec":
        executable_path = _safe_absolute_path(
            fields["executable.path"],
            "executable.path",
            executable=True,
        )
        executable_digest = _require_sha256(fields["executable.digest"], "executable.digest")
        workspace_repository = _require_string(fields["workspace.repository"], "workspace.repository")
        assert isinstance(workspace_repository, str)
        if not _REPOSITORY_RE.fullmatch(workspace_repository):
            raise LCMSError("UNBOUND_WORKSPACE", "workspace.repository is not canonical")
        workspace_path = _safe_absolute_path(fields["workspace.path"], "workspace.path")
        inherit = _require_bool(fields["environment.inherit"], "environment.inherit")
        if inherit:
            raise LCMSError("ENVIRONMENT_INHERITANCE", "environment inheritance is forbidden")

        spec.update(
            {
                "executable": {
                    "path": executable_path,
                    "digest": executable_digest,
                },
                "arguments": _require_string_list(fields["arguments"], "arguments", max_items=256),
                "workspace": {
                    "repository": workspace_repository,
                    "commit": _require_sha40(fields["workspace.commit"], "workspace.commit"),
                    "tree": _require_sha40(fields["workspace.tree"], "workspace.tree"),
                    "path": workspace_path,
                },
                "environment": {
                    "inherit": False,
                    "allow": _require_env_map(fields["environment.allow"]),
                },
                "io": {
                    "stdin": _require_string(fields["io.stdin"], "io.stdin"),
                    "stdout": _require_enum(fields["io.stdout"], "io.stdout", STDOUT_MODES),
                    "stderr": _require_enum(fields["io.stderr"], "io.stderr", STDERR_MODES),
                    "tty": _require_bool(fields["io.tty"], "io.tty"),
                },
            }
        )
        if spec["io"]["stdin"] != "NONE":
            raise LCMSError("UNKNOWN_ENUM", "io.stdin must be NONE")
        if spec["io"]["tty"]:
            raise LCMSError("AMBIGUOUS_BOOLEAN", "io.tty must be false")

    return spec


def canonical_action_spec_bytes(spec: dict[str, Any]) -> bytes:
    """Return the single C1 canonical byte representation."""
    return (
        json.dumps(
            spec,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )


def compile_lcms(source: str) -> CompiledActionSpec:
    """Parse, normalize, and canonicalize LCMS without executing anything."""
    fields = _parse_source(source)
    spec = _normalize(fields)
    canonical = canonical_action_spec_bytes(spec)
    digest = "sha256:" + hashlib.sha256(canonical).hexdigest()
    return CompiledActionSpec(
        grammar_version=LCMS_GRAMMAR_VERSION,
        canonical_bytes=canonical,
        digest=digest,
    )

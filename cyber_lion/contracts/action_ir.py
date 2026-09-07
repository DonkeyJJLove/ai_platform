"""Canonical, deterministic and non-effectful LION Action IR representation.

ActionSpec is the schema/type contract. CanonicalActionIR is one validated,
digest-bindable instance of that contract. This module does not create an
ActionProposal, execution plan, grant, permit, executor request, transport, or
effect. Its payload digest is intentionally raw lowercase SHA-256 so it can be
bound directly by the existing ActionProposal.payload_digest/runtime contracts
without an implicit digest-format translation.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping


SCHEMA_ID = "cyberlion://schemas/action-spec/v1"
SCHEMA_VERSION = "1.0.0"
KINDS = frozenset({
    "process.exec",
    "filesystem.read",
    "filesystem.write",
    "repository.observe",
    "repository.prepare_candidate",
    "repository.attach_exact",
    "test.execute",
    "artifact.generate",
    "robot.task",
})
NETWORK_MODES = frozenset({"DENY", "READ_ONLY_PINNED", "ALLOW_EXACT"})
OBSERVER_CLASSES = frozenset({"independent", "deterministic_independent"})
RECONCILIATION_MODES = frozenset({"EXACT", "PHYSICAL_POSTCONDITION"})
CAPTURE_MODES = frozenset({"CAPTURE", "DISCARD"})

_REQUIRED = frozenset({
    "schema_version", "action_id", "kind", "intent_ref", "mission_ref",
    "autonomy_ref", "bean_ref", "target", "authority_request", "boundary",
    "preconditions", "expected_effects", "forbidden_effects", "observation",
    "reconciliation",
})
_PROCESS = frozenset({"executable", "arguments", "workspace", "environment", "io"})
_ALLOWED = _REQUIRED | _PROCESS
_ACTION_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,255}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class ActionIRContractError(ValueError):
    pass


def _exact_keys(value: Any, expected: set[str] | frozenset[str], name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ActionIRContractError(f"{name} must be an object")
    if set(value) != set(expected):
        raise ActionIRContractError(f"{name} keys are not canonical")
    return value


def _allowed_keys(value: Any, allowed: set[str] | frozenset[str], required: set[str] | frozenset[str], name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ActionIRContractError(f"{name} must be an object")
    keys = set(value)
    if not set(required) <= keys or not keys <= set(allowed):
        raise ActionIRContractError(f"{name} keys are not canonical")
    return value


def _string(value: Any, name: str, *, minimum: int = 0, maximum: int | None = None, pattern: re.Pattern[str] | None = None) -> str:
    if type(value) is not str:
        raise ActionIRContractError(f"{name} must be a string")
    if len(value) < minimum or (maximum is not None and len(value) > maximum):
        raise ActionIRContractError(f"{name} length is invalid")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ActionIRContractError(f"{name} format is invalid")
    return value


def _integer(value: Any, name: str, *, minimum: int, maximum: int | None = None) -> int:
    if type(value) is not int:
        raise ActionIRContractError(f"{name} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        raise ActionIRContractError(f"{name} range is invalid")
    return value


def _unique_strings(value: Any, name: str) -> list[str]:
    if type(value) is not list:
        raise ActionIRContractError(f"{name} must be an array")
    result = [_string(item, name, minimum=1, maximum=4096) for item in value]
    if len(result) != len(set(result)):
        raise ActionIRContractError(f"{name} must contain unique strings")
    return result


def _target(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, {"host", "environment", "runtime"}, "target")
    for name in ("host", "environment", "runtime"):
        _string(value[name], f"target.{name}", minimum=1)
    return value


def _authority_request(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, {"domain", "capability", "grant_ref"}, "authority_request")
    _string(value["domain"], "authority_request.domain", minimum=1)
    _string(value["capability"], "authority_request.capability", minimum=1)
    if value["grant_ref"] is not None:
        _string(value["grant_ref"], "authority_request.grant_ref")
    return value


def _boundary(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, {
        "shell", "network", "filesystem_read", "filesystem_write", "process_children",
        "timeout_ms", "max_processes", "memory_limit_bytes",
    }, "boundary")
    if value["shell"] is not False:
        raise ActionIRContractError("boundary.shell must be false")
    if value["network"] not in NETWORK_MODES:
        raise ActionIRContractError("boundary.network is invalid")
    for name in ("filesystem_read", "filesystem_write", "process_children"):
        _unique_strings(value[name], f"boundary.{name}")
    _integer(value["timeout_ms"], "boundary.timeout_ms", minimum=1, maximum=3_600_000)
    _integer(value["max_processes"], "boundary.max_processes", minimum=1, maximum=128)
    _integer(value["memory_limit_bytes"], "boundary.memory_limit_bytes", minimum=1_048_576)
    return value


def _observation(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, {"observer_class", "required_events"}, "observation")
    if value["observer_class"] not in OBSERVER_CLASSES:
        raise ActionIRContractError("observation.observer_class is invalid")
    _unique_strings(value["required_events"], "observation.required_events")
    return value


def _reconciliation(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, {"mode", "receipt"}, "reconciliation")
    if value["mode"] not in RECONCILIATION_MODES:
        raise ActionIRContractError("reconciliation.mode is invalid")
    if value["receipt"] != "REQUIRED":
        raise ActionIRContractError("reconciliation.receipt must be REQUIRED")
    return value


def _executable(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, {"path", "digest"}, "executable")
    path = _string(value["path"], "executable.path")
    if not path.startswith("/"):
        raise ActionIRContractError("executable.path format is invalid")
    _string(value["digest"], "executable.digest", pattern=_SHA256_REF)
    return value


def _arguments(value: Any) -> list[str]:
    if type(value) is not list or len(value) > 256:
        raise ActionIRContractError("arguments must be a bounded array")
    return [_string(item, "arguments", maximum=4096) for item in value]


def _workspace(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, {"repository", "commit", "tree", "path"}, "workspace")
    _string(value["repository"], "workspace.repository", pattern=_REPOSITORY)
    _string(value["commit"], "workspace.commit", pattern=_SHA40)
    _string(value["tree"], "workspace.tree", pattern=_SHA40)
    path = _string(value["path"], "workspace.path")
    if not path.startswith("/"):
        raise ActionIRContractError("workspace.path format is invalid")
    return value


def _environment(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, {"inherit", "allow"}, "environment")
    if value["inherit"] is not False:
        raise ActionIRContractError("environment.inherit must be false")
    allow = value["allow"]
    if type(allow) is not dict or any(type(key) is not str for key in allow):
        raise ActionIRContractError("environment.allow must be an object")
    for key, item in allow.items():
        _string(item, f"environment.allow.{key}", maximum=4096)
    return value


def _io(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, {"stdin", "stdout", "stderr", "tty"}, "io")
    if value["stdin"] != "NONE":
        raise ActionIRContractError("io.stdin must be NONE")
    if value["stdout"] not in CAPTURE_MODES or value["stderr"] not in CAPTURE_MODES:
        raise ActionIRContractError("io capture mode is invalid")
    if value["tty"] is not False:
        raise ActionIRContractError("io.tty must be false")
    return value


def validate_action_ir(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate exactly the live ActionSpec v1 data contract.

    This intentionally does not add stronger policy or execution constraints. For
    example, fields that the JSON Schema permits on non-process kinds remain type-
    valid here; later producers such as LCMS may choose a stricter source language.
    """
    if type(value) is not dict:
        raise ActionIRContractError("Action IR must be an object")
    value = _allowed_keys(value, _ALLOWED, _REQUIRED, "ActionIR")
    if value["schema_version"] != SCHEMA_VERSION:
        raise ActionIRContractError("schema_version mismatch")
    _string(value["action_id"], "action_id", pattern=_ACTION_ID)
    if value["kind"] not in KINDS:
        raise ActionIRContractError("kind is outside the closed vocabulary")
    for name in ("intent_ref", "mission_ref", "autonomy_ref", "bean_ref"):
        _string(value[name], name, minimum=1)
    _target(value["target"])
    _authority_request(value["authority_request"])
    _boundary(value["boundary"])
    for name in ("preconditions", "expected_effects", "forbidden_effects"):
        _unique_strings(value[name], name)
    _observation(value["observation"])
    _reconciliation(value["reconciliation"])
    if value["kind"] == "process.exec" and not _PROCESS <= set(value):
        raise ActionIRContractError("process.exec requires execution-shaped fields")
    if "executable" in value:
        _executable(value["executable"])
    if "arguments" in value:
        _arguments(value["arguments"])
    if "workspace" in value:
        _workspace(value["workspace"])
    if "environment" in value:
        _environment(value["environment"])
    if "io" in value:
        _io(value["io"])
    return value


def canonical_action_ir_bytes(value: Mapping[str, Any]) -> bytes:
    validate_action_ir(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def action_ir_payload_digest(value: Mapping[str, Any]) -> str:
    return sha256(canonical_action_ir_bytes(value)).hexdigest()


def _reject_constant(value: str) -> None:
    raise ActionIRContractError(f"non-RFC8259 constant is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ActionIRContractError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _parse_json(raw: bytes | str) -> Mapping[str, Any]:
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise ActionIRContractError("Action IR JSON must be UTF-8") from exc
    if type(raw) is not str:
        raise ActionIRContractError("Action IR JSON must be bytes or str")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except ActionIRContractError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ActionIRContractError("Action IR JSON is invalid") from exc
    if type(value) is not dict:
        raise ActionIRContractError("Action IR root must be an object")
    return value


@dataclass(frozen=True)
class CanonicalActionIR:
    canonical_bytes: bytes
    payload_digest: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CanonicalActionIR":
        raw = canonical_action_ir_bytes(value)
        return cls(raw, sha256(raw).hexdigest()).validate()

    @classmethod
    def from_json(cls, raw: bytes | str) -> "CanonicalActionIR":
        return cls.from_mapping(_parse_json(raw))

    def validate(self) -> "CanonicalActionIR":
        if type(self.canonical_bytes) is not bytes:
            raise ActionIRContractError("canonical_bytes must be bytes")
        value = _parse_json(self.canonical_bytes)
        expected = canonical_action_ir_bytes(value)
        if expected != self.canonical_bytes:
            raise ActionIRContractError("canonical_bytes are not canonical")
        if type(self.payload_digest) is not str or _SHA256.fullmatch(self.payload_digest) is None:
            raise ActionIRContractError("payload_digest must be lowercase SHA-256")
        if self.payload_digest != sha256(self.canonical_bytes).hexdigest():
            raise ActionIRContractError("payload_digest mismatch")
        return self

    def as_dict(self) -> dict[str, Any]:
        return dict(_parse_json(self.canonical_bytes))

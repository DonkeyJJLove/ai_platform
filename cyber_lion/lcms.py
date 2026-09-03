from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import posixpath
import re
import unicodedata
from typing import Any


class LCMSError(ValueError):
    """Fail-closed parse, normalization, or canonicalization error."""


C0_ACTION_SPEC_SCHEMA_SHA256 = "2da1a37043a19b96e99a5e2270c09dd0d4f3a996906740ec3e72322f2823a7a6"
C0_ACTION_SPEC_SUPPORT_MATRIX_SHA256 = "1b14a6eeee5cf4fe504b782dee9c63fe41790ae09dc0a30a8627361981229a66"
ACTION_SPEC_SCHEMA_VERSION = "lion.action-spec/v1.3-candidate"
DIGEST_DOMAIN = b"LION/ACTION-SPEC/CANONICAL-IR/1\0"

_KIND = {
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
_OBSERVER_CLASS = {"independent", "deterministic_independent"}
_RECONCILIATION_MODE = {"EXACT", "PHYSICAL_POSTCONDITION"}
_NETWORK = {"DENY", "READ_ONLY_PINNED", "ALLOW_EXACT"}
_IO_CAPTURE = {"CAPTURE", "DISCARD"}

_TOP_REQUIRED = {
    "schema_version",
    "action_id",
    "kind",
    "intent_ref",
    "mission_ref",
    "autonomy_ref",
    "bean_ref",
    "target",
    "authority_request",
    "boundary",
    "preconditions",
    "expected_effects",
    "forbidden_effects",
    "observation",
    "reconciliation",
}
_TOP_OPTIONAL = {"executable", "arguments", "workspace", "environment", "io"}
_BLOCK_FIELDS = {
    "target",
    "executable",
    "workspace",
    "environment",
    "io",
    "authority_request",
    "boundary",
    "observation",
    "reconciliation",
}
_ASSIGNMENT_FIELDS = (_TOP_REQUIRED | _TOP_OPTIONAL) - _BLOCK_FIELDS - {"action_id"}
_SET_LIKE_TOP = {"preconditions", "expected_effects", "forbidden_effects"}

_CANONICAL_TOP_ORDER = (
    "schema_version",
    "kind",
    "intent_ref",
    "mission_ref",
    "autonomy_ref",
    "bean_ref",
    "target",
    "executable",
    "arguments",
    "workspace",
    "environment",
    "io",
    "authority_request",
    "boundary",
    "preconditions",
    "expected_effects",
    "forbidden_effects",
    "observation",
    "reconciliation",
)

_CANONICAL_BLOCK_ORDER = {
    "target": ("host", "environment", "runtime"),
    "executable": ("path", "digest"),
    "workspace": ("repository", "commit", "tree", "path"),
    "environment": ("inherit", "allow"),
    "io": ("stdin", "stdout", "stderr", "tty"),
    "authority_request": ("domain", "capability", "grant_ref"),
    "boundary": (
        "shell",
        "network",
        "filesystem_read",
        "filesystem_write",
        "process_children",
        "timeout_ms",
        "max_processes",
        "memory_limit_bytes",
    ),
    "observation": ("observer_class", "required_events"),
    "reconciliation": ("mode", "receipt"),
}

_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,255}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.:-]*")
_INT_RE = re.compile(r"0|[1-9][0-9]*")


@dataclass(frozen=True)
class _Token:
    kind: str
    value: Any
    offset: int


@dataclass(frozen=True)
class CompiledAction:
    parsed_ir: dict[str, Any]
    canonical_ir: dict[str, Any]
    canonical_ir_bytes: bytes
    canonical_ir_digest: str
    canonical_lcms: str


def _fail(message: str, offset: int | None = None) -> LCMSError:
    if offset is None:
        return LCMSError(message)
    return LCMSError(f"{message} at offset {offset}")


def _lex(text: str) -> tuple[_Token, ...]:
    if type(text) is not str or not text:
        raise _fail("LCMS source must be a nonempty string")
    if unicodedata.normalize("NFC", text) != text:
        raise _fail("LCMS source is not NFC-normalized")
    if "\r" in text or "\t" in text:
        raise _fail("LCMS source contains noncanonical whitespace")
    if any(ord(ch) > 0x7F for ch in text):
        raise _fail("LCMS R1 source must be ASCII")

    out: list[_Token] = []
    i = 0
    n = len(text)
    punctuation = set("{}[]=,;:")
    while i < n:
        ch = text[i]
        if ch in " \n":
            i += 1
            continue
        if ch in punctuation:
            out.append(_Token(ch, ch, i))
            i += 1
            continue
        if ch == '"':
            start = i
            i += 1
            escaped = False
            while i < n:
                cur = text[i]
                if escaped:
                    escaped = False
                    i += 1
                    continue
                if cur == "\\":
                    escaped = True
                    i += 1
                    continue
                if cur == '"':
                    i += 1
                    break
                if ord(cur) < 0x20:
                    raise _fail("control character in string", i)
                i += 1
            else:
                raise _fail("unterminated string", start)
            raw = text[start:i]
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise _fail("invalid JSON string literal", start) from exc
            if type(value) is not str:
                raise _fail("string token did not decode to string", start)
            if unicodedata.normalize("NFC", value) != value or any(ord(c) > 0x7F for c in value):
                raise _fail("decoded string is noncanonical for LCMS R1", start)
            out.append(_Token("STRING", value, start))
            continue
        ident = _IDENT_RE.match(text, i)
        if ident:
            value = ident.group(0)
            kind = {"true": "TRUE", "false": "FALSE", "null": "NULL"}.get(value, "IDENT")
            out.append(_Token(kind, value, i))
            i = ident.end()
            continue
        integer = _INT_RE.match(text, i)
        if integer:
            value = integer.group(0)
            end = integer.end()
            if end < n and (text[end].isalnum() or text[end] in "_.:-"):
                raise _fail("invalid numeric token", i)
            out.append(_Token("INT", int(value), i))
            i = end
            continue
        raise _fail("unexpected character", i)
    out.append(_Token("EOF", None, n))
    return tuple(out)


class _Parser:
    def __init__(self, tokens: tuple[_Token, ...]) -> None:
        self.tokens = tokens
        self.index = 0

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def take(self, kind: str) -> _Token:
        token = self.current
        if token.kind != kind:
            raise _fail(f"expected {kind}, got {token.kind}", token.offset)
        self.index += 1
        return token

    def take_ident(self, expected: str | None = None) -> str:
        token = self.take("IDENT")
        if expected is not None and token.value != expected:
            raise _fail(f"expected {expected!r}, got {token.value!r}", token.offset)
        return token.value

    def parse_value(self) -> Any:
        token = self.current
        if token.kind == "STRING":
            self.index += 1
            return token.value
        if token.kind == "INT":
            self.index += 1
            return token.value
        if token.kind == "TRUE":
            self.index += 1
            return True
        if token.kind == "FALSE":
            self.index += 1
            return False
        if token.kind == "NULL":
            self.index += 1
            return None
        if token.kind == "[":
            return self.parse_array()
        if token.kind == "{":
            return self.parse_map()
        raise _fail("expected LCMS value", token.offset)

    def parse_array(self) -> list[Any]:
        self.take("[")
        values: list[Any] = []
        if self.current.kind != "]":
            while True:
                values.append(self.parse_value())
                if self.current.kind != ",":
                    break
                self.take(",")
                if self.current.kind == "]":
                    raise _fail("trailing comma is noncanonical", self.current.offset)
        self.take("]")
        return values

    def parse_map(self) -> dict[str, Any]:
        self.take("{")
        result: dict[str, Any] = {}
        if self.current.kind != "}":
            while True:
                key_token = self.take("STRING")
                key = key_token.value
                if key in result:
                    raise _fail(f"duplicate map key {key!r}", key_token.offset)
                self.take(":")
                result[key] = self.parse_value()
                if self.current.kind != ",":
                    break
                self.take(",")
                if self.current.kind == "}":
                    raise _fail("trailing comma is noncanonical", self.current.offset)
        self.take("}")
        return result

    def parse_block(self) -> dict[str, Any]:
        self.take("{")
        result: dict[str, Any] = {}
        while self.current.kind != "}":
            key_token = self.take("IDENT")
            key = key_token.value
            if key in result:
                raise _fail(f"duplicate field {key!r}", key_token.offset)
            self.take("=")
            result[key] = self.parse_value()
            self.take(";")
        self.take("}")
        return result

    def parse_action(self) -> dict[str, Any]:
        first = self.take("IDENT")
        if first.value != "ACTION":
            if first.value in {"PLAN", "NODE", "EDGE"}:
                raise _fail(f"{first.value} is reserved but unsupported in C1 R1", first.offset)
            raise _fail("document must begin with ACTION", first.offset)
        action_token = self.take("IDENT")
        action_id = action_token.value
        self.take("{")
        result: dict[str, Any] = {"action_id": action_id}
        while self.current.kind != "}":
            key_token = self.take("IDENT")
            key = key_token.value
            if key == "action_id":
                raise _fail("action_id has exactly one representation in ACTION header", key_token.offset)
            if key in result:
                raise _fail(f"duplicate top-level field {key!r}", key_token.offset)
            if key in _BLOCK_FIELDS:
                if self.current.kind != "{":
                    raise _fail(f"{key} must use block syntax", self.current.offset)
                result[key] = self.parse_block()
            elif key in _ASSIGNMENT_FIELDS:
                self.take("=")
                result[key] = self.parse_value()
                self.take(";")
            else:
                raise _fail(f"unknown top-level field {key!r}", key_token.offset)
        self.take("}")
        self.take("EOF")
        return result


def parse_lcms(text: str) -> dict[str, Any]:
    """Parse LCMS syntax only. No execution, transport, authority, or effects."""
    return _Parser(_lex(text)).parse_action()


def _ascii_string(value: Any, label: str, *, min_length: int = 0, max_length: int | None = None) -> str:
    if type(value) is not str:
        raise _fail(f"{label} must be a string")
    if len(value) < min_length or (max_length is not None and len(value) > max_length):
        raise _fail(f"{label} length is invalid")
    if unicodedata.normalize("NFC", value) != value or any(ord(ch) > 0x7F for ch in value):
        raise _fail(f"{label} must be canonical ASCII in LCMS R1")
    return value


def _exact_keys(value: Any, label: str, required: set[str], optional: set[str] | None = None) -> dict[str, Any]:
    if type(value) is not dict:
        raise _fail(f"{label} must be an object")
    optional = optional or set()
    keys = set(value)
    if keys - required - optional:
        raise _fail(f"{label} contains unknown fields: {sorted(keys - required - optional)!r}")
    missing = required - keys
    if missing:
        raise _fail(f"{label} is missing required fields: {sorted(missing)!r}")
    return value


def _unique_strings(value: Any, label: str, *, sort_semantically: bool) -> list[str]:
    if type(value) is not list:
        raise _fail(f"{label} must be an array")
    strings = [_ascii_string(item, f"{label}[]", min_length=1, max_length=4096) for item in value]
    if len(strings) != len(set(strings)):
        raise _fail(f"{label} contains duplicate values")
    return sorted(strings) if sort_semantically else strings


def _positive_int(value: Any, label: str, *, minimum: int, maximum: int | None = None) -> int:
    if type(value) is not int:
        raise _fail(f"{label} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        raise _fail(f"{label} is outside bounds")
    return value


def _absolute_path(value: Any, label: str, *, allow_glob: bool) -> str:
    path = _ascii_string(value, label, min_length=1, max_length=4096)
    if not path.startswith("/") or "\\" in path or "\x00" in path:
        raise _fail(f"{label} must be an absolute POSIX path")
    parts = path.split("/")[1:]
    if any(part in {"", ".", ".."} for part in parts):
        raise _fail(f"{label} is not path-normalized")
    if not allow_glob and any(ch in path for ch in "*?["):
        raise _fail(f"{label} cannot contain glob syntax")
    if not allow_glob and posixpath.normpath(path) != path:
        raise _fail(f"{label} is not path-normalized")
    return path


def _normalize_target(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, "target", {"host", "environment", "runtime"})
    return {
        "host": _ascii_string(value["host"], "target.host", min_length=1),
        "environment": _ascii_string(value["environment"], "target.environment", min_length=1),
        "runtime": _ascii_string(value["runtime"], "target.runtime", min_length=1),
    }


def _normalize_authority(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, "authority_request", {"domain", "capability", "grant_ref"})
    grant_ref = value["grant_ref"]
    if grant_ref is not None:
        grant_ref = _ascii_string(grant_ref, "authority_request.grant_ref")
    return {
        "domain": _ascii_string(value["domain"], "authority_request.domain", min_length=1),
        "capability": _ascii_string(value["capability"], "authority_request.capability", min_length=1),
        "grant_ref": grant_ref,
    }


def _normalize_boundary(value: Any) -> dict[str, Any]:
    required = {
        "shell", "network", "filesystem_read", "filesystem_write", "process_children",
        "timeout_ms", "max_processes", "memory_limit_bytes",
    }
    value = _exact_keys(value, "boundary", required)
    if value["shell"] is not False:
        raise _fail("boundary.shell must be false")
    network = _ascii_string(value["network"], "boundary.network")
    if network not in _NETWORK:
        raise _fail("boundary.network enum is unknown")
    filesystem_read = _unique_strings(value["filesystem_read"], "boundary.filesystem_read", sort_semantically=True)
    filesystem_write = _unique_strings(value["filesystem_write"], "boundary.filesystem_write", sort_semantically=True)
    process_children = _unique_strings(value["process_children"], "boundary.process_children", sort_semantically=True)
    filesystem_read = [_absolute_path(item, "boundary.filesystem_read[]", allow_glob=True) for item in filesystem_read]
    filesystem_write = [_absolute_path(item, "boundary.filesystem_write[]", allow_glob=True) for item in filesystem_write]
    process_children = [_absolute_path(item, "boundary.process_children[]", allow_glob=False) for item in process_children]
    return {
        "shell": False,
        "network": network,
        "filesystem_read": filesystem_read,
        "filesystem_write": filesystem_write,
        "process_children": process_children,
        "timeout_ms": _positive_int(value["timeout_ms"], "boundary.timeout_ms", minimum=1, maximum=3600000),
        "max_processes": _positive_int(value["max_processes"], "boundary.max_processes", minimum=1, maximum=128),
        "memory_limit_bytes": _positive_int(value["memory_limit_bytes"], "boundary.memory_limit_bytes", minimum=1048576),
    }


def _normalize_observation(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, "observation", {"observer_class", "required_events"})
    observer_class = _ascii_string(value["observer_class"], "observation.observer_class")
    if observer_class not in _OBSERVER_CLASS:
        raise _fail("observation.observer_class enum is unknown")
    return {
        "observer_class": observer_class,
        "required_events": _unique_strings(value["required_events"], "observation.required_events", sort_semantically=True),
    }


def _normalize_reconciliation(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, "reconciliation", {"mode", "receipt"})
    mode = _ascii_string(value["mode"], "reconciliation.mode")
    receipt = _ascii_string(value["receipt"], "reconciliation.receipt")
    if mode not in _RECONCILIATION_MODE:
        raise _fail("reconciliation.mode enum is unknown")
    if receipt != "REQUIRED":
        raise _fail("reconciliation.receipt must be REQUIRED")
    return {"mode": mode, "receipt": receipt}


def _normalize_executable(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, "executable", {"path", "digest"})
    digest = _ascii_string(value["digest"], "executable.digest")
    if not _SHA256_RE.fullmatch(digest):
        raise _fail("executable.digest must be sha256:<64 lowercase hex>")
    return {"path": _absolute_path(value["path"], "executable.path", allow_glob=False), "digest": digest}


def _normalize_workspace(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, "workspace", {"repository", "commit", "tree", "path"})
    repository = _ascii_string(value["repository"], "workspace.repository")
    commit = _ascii_string(value["commit"], "workspace.commit")
    tree = _ascii_string(value["tree"], "workspace.tree")
    if not _REPO_RE.fullmatch(repository):
        raise _fail("workspace.repository is invalid")
    if not _SHA40_RE.fullmatch(commit) or not _SHA40_RE.fullmatch(tree):
        raise _fail("workspace commit/tree must be lowercase SHA-40")
    return {
        "repository": repository,
        "commit": commit,
        "tree": tree,
        "path": _absolute_path(value["path"], "workspace.path", allow_glob=False),
    }


def _normalize_environment(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, "environment", {"inherit", "allow"})
    if value["inherit"] is not False:
        raise _fail("environment.inherit must be false")
    allow = value["allow"]
    if type(allow) is not dict:
        raise _fail("environment.allow must be an object")
    normalized_allow: dict[str, str] = {}
    for key in sorted(allow):
        normalized_key = _ascii_string(key, "environment.allow key", min_length=1, max_length=4096)
        normalized_allow[normalized_key] = _ascii_string(allow[key], f"environment.allow[{key!r}]", max_length=4096)
    return {"inherit": False, "allow": normalized_allow}


def _normalize_io(value: Any) -> dict[str, Any]:
    value = _exact_keys(value, "io", {"stdin", "stdout", "stderr", "tty"})
    stdin = _ascii_string(value["stdin"], "io.stdin")
    stdout = _ascii_string(value["stdout"], "io.stdout")
    stderr = _ascii_string(value["stderr"], "io.stderr")
    if stdin != "NONE" or stdout not in _IO_CAPTURE or stderr not in _IO_CAPTURE or value["tty"] is not False:
        raise _fail("io contract is outside frozen C0 schema")
    return {"stdin": stdin, "stdout": stdout, "stderr": stderr, "tty": False}


def normalize_action_ir(parsed: dict[str, Any]) -> dict[str, Any]:
    """Normalize parsed LCMS into exactly one C0 ActionSpec-shaped IR."""
    if type(parsed) is not dict:
        raise _fail("parsed Action IR must be an object")
    keys = set(parsed)
    unknown = keys - _TOP_REQUIRED - _TOP_OPTIONAL
    if unknown:
        raise _fail(f"Action IR contains unknown fields: {sorted(unknown)!r}")
    missing = _TOP_REQUIRED - keys
    if missing:
        raise _fail(f"Action IR is missing required fields: {sorted(missing)!r}")

    schema_version = _ascii_string(parsed["schema_version"], "schema_version")
    if schema_version != ACTION_SPEC_SCHEMA_VERSION:
        raise _fail("schema_version does not match frozen C0 ActionSpec")
    action_id = _ascii_string(parsed["action_id"], "action_id", min_length=1, max_length=256)
    if not _ID_RE.fullmatch(action_id):
        raise _fail("action_id is invalid")
    kind = _ascii_string(parsed["kind"], "kind")
    if kind not in _KIND:
        raise _fail("kind enum is unknown")

    result: dict[str, Any] = {
        "schema_version": schema_version,
        "action_id": action_id,
        "kind": kind,
        "intent_ref": _ascii_string(parsed["intent_ref"], "intent_ref", min_length=1),
        "mission_ref": _ascii_string(parsed["mission_ref"], "mission_ref", min_length=1),
        "autonomy_ref": _ascii_string(parsed["autonomy_ref"], "autonomy_ref", min_length=1),
        "bean_ref": _ascii_string(parsed["bean_ref"], "bean_ref", min_length=1),
        "target": _normalize_target(parsed["target"]),
        "authority_request": _normalize_authority(parsed["authority_request"]),
        "boundary": _normalize_boundary(parsed["boundary"]),
        "preconditions": _unique_strings(parsed["preconditions"], "preconditions", sort_semantically=True),
        "expected_effects": _unique_strings(parsed["expected_effects"], "expected_effects", sort_semantically=True),
        "forbidden_effects": _unique_strings(parsed["forbidden_effects"], "forbidden_effects", sort_semantically=True),
        "observation": _normalize_observation(parsed["observation"]),
        "reconciliation": _normalize_reconciliation(parsed["reconciliation"]),
    }

    execution_fields = {"executable", "arguments", "workspace", "environment", "io"}
    if kind == "process.exec" and not execution_fields <= keys:
        raise _fail("process.exec requires the complete frozen C0 execution shape")
    if "executable" in parsed:
        result["executable"] = _normalize_executable(parsed["executable"])
    if "arguments" in parsed:
        arguments = parsed["arguments"]
        if type(arguments) is not list or len(arguments) > 256:
            raise _fail("arguments must be an array with at most 256 entries")
        result["arguments"] = [_ascii_string(item, "arguments[]", max_length=4096) for item in arguments]
    if "workspace" in parsed:
        result["workspace"] = _normalize_workspace(parsed["workspace"])
    if "environment" in parsed:
        result["environment"] = _normalize_environment(parsed["environment"])
    if "io" in parsed:
        result["io"] = _normalize_io(parsed["io"])
    return result


def canonical_ir_bytes(ir: dict[str, Any]) -> bytes:
    normalized = normalize_action_ir(ir)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def canonical_ir_digest(ir: dict[str, Any]) -> str:
    return sha256(DIGEST_DOMAIN + canonical_ir_bytes(ir)).hexdigest()


def _render_value(value: Any) -> str:
    if type(value) is str:
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if type(value) is int:
        return str(value)
    if type(value) in {list, dict}:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    raise _fail(f"cannot render LCMS value of type {type(value).__name__}")


def render_canonical_lcms(ir: dict[str, Any]) -> str:
    normalized = normalize_action_ir(ir)
    lines = [f"ACTION {normalized['action_id']} {{"]
    for field in _CANONICAL_TOP_ORDER:
        if field not in normalized:
            continue
        value = normalized[field]
        if field in _BLOCK_FIELDS:
            lines.append(f"    {field} {{")
            for child in _CANONICAL_BLOCK_ORDER[field]:
                lines.append(f"        {child} = {_render_value(value[child])};")
            lines.append("    }")
        else:
            lines.append(f"    {field} = {_render_value(value)};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def compile_lcms(text: str) -> CompiledAction:
    parsed = parse_lcms(text)
    normalized = normalize_action_ir(parsed)
    encoded = canonical_ir_bytes(normalized)
    digest = sha256(DIGEST_DOMAIN + encoded).hexdigest()
    canonical_lcms = render_canonical_lcms(normalized)
    reparsed = normalize_action_ir(parse_lcms(canonical_lcms))
    if reparsed != normalized:
        raise _fail("canonical LCMS round-trip mismatch")
    return CompiledAction(parsed, normalized, encoded, digest, canonical_lcms)

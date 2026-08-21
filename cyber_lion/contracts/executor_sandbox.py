"""Deterministic contracts for one bounded coding-agent execution sandbox.

The contract is adapter-neutral and deliberately exposes no general shell, network,
Git-ref, merge, release, or deployment action.  It binds one executor and one sandbox
workspace to an already-authorized mission.  The authority digest is evidence/binding
only; this module cannot mint, widen, consume, or delegate authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from typing import Any, Final, Mapping

_SCHEMA_VERSION: Final = "1.0.0"
_SHA40: Final = re.compile(r"^[0-9a-f]{40}$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_REPOSITORY: Final = re.compile(r"^[^/\s]+/[^/\s]+$")
_BRANCH: Final = re.compile(
    r"^(?!/)(?!.*//)(?!.*\.\.)(?!.*@\{)(?!.*[~^:?*\[\\])"
    r"(?!.*\.$)(?!.*\.lock(?:/|$))[A-Za-z0-9._/-]+$"
)
_ACTIONS: Final = frozenset({"READ_FILE", "WRITE_FILE", "RUN_TEST"})
_OUTCOMES: Final = frozenset({"SUCCEEDED", "FAILED", "ABORTED"})


class ExecutionSandboxContractError(ValueError):
    """Raised when a sandbox contract is malformed, unsafe, or ambiguous."""


def _text(value: object, name: str, *, limit: int = 1024) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise ExecutionSandboxContractError(f"{name} is invalid")
    return value


def _sha40(value: object, name: str) -> str:
    value = _text(value, name, limit=40)
    if not _SHA40.fullmatch(value):
        raise ExecutionSandboxContractError(
            f"{name} must be a full lowercase git SHA"
        )
    return value


def _digest(value: object, name: str) -> str:
    value = _text(value, name, limit=64)
    if not _SHA256.fullmatch(value):
        raise ExecutionSandboxContractError(
            f"{name} must be a lowercase sha256 hex digest"
        )
    return value


def _branch(value: object) -> str:
    value = _text(value, "branch", limit=255)
    if value.startswith("refs/") or not _BRANCH.fullmatch(value):
        raise ExecutionSandboxContractError("branch is invalid")
    return value


def _path(value: object, name: str = "path") -> str:
    value = _text(value, name, limit=2048)
    if "\\" in value:
        raise ExecutionSandboxContractError(
            f"{name} must use repository-relative POSIX syntax"
        )
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or ".." in parsed.parts or str(parsed) in {"", "."}:
        raise ExecutionSandboxContractError(f"{name} is unsafe")
    normalized = str(parsed)
    if normalized != value:
        raise ExecutionSandboxContractError(f"{name} must be normalized")
    return normalized


def _scope(values: object, name: str) -> tuple[str, ...]:
    if type(values) is not tuple or not values:
        raise ExecutionSandboxContractError(f"{name} must be a non-empty tuple")
    normalized = tuple(_path(value, name) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ExecutionSandboxContractError(f"{name} entries must be unique")
    return normalized


def _command(value: object, name: str = "command") -> tuple[str, ...]:
    if type(value) is not tuple or not value:
        raise ExecutionSandboxContractError(f"{name} must be a non-empty argv tuple")
    tokens: list[str] = []
    for token in value:
        token = _text(token, f"{name} token", limit=2048)
        if "\n" in token or "\r" in token:
            raise ExecutionSandboxContractError(
                f"{name} tokens must not contain line breaks"
            )
        tokens.append(token)
    return tuple(tokens)


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def path_within_scope(path: str, scope: tuple[str, ...]) -> bool:
    """Return True only when *path* is equal to or below an explicit scope root."""

    candidate = PurePosixPath(_path(path)).parts
    roots = _scope(scope, "scope")
    for root in roots:
        root_parts = PurePosixPath(root).parts
        if candidate[: len(root_parts)] == root_parts:
            return True
    return False


@dataclass(frozen=True)
class SandboxResourceLimits:
    """Deterministic budgets enforced by the sandbox boundary."""

    max_operations: int
    max_write_bytes: int
    max_output_bytes: int
    max_test_runs: int

    def validate(self) -> "SandboxResourceLimits":
        for name in (
            "max_operations",
            "max_write_bytes",
            "max_output_bytes",
            "max_test_runs",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ExecutionSandboxContractError(f"{name} must be a positive integer")
        return self

    def canonical_dict(self) -> dict[str, int]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class SandboxRuntimeBinding:
    """Composition-root pin for the isolated backend used by one sandbox instance."""

    backend_id: str
    backend_identity_digest: str
    backend_implementation_digest: str
    isolation_evidence_digest: str
    sandbox_id: str
    workspace_id: str
    filesystem_mode: str = "WORKSPACE_ONLY"
    network_mode: str = "DENY_ALL"
    process_mode: str = "ALLOWLIST_ONLY"
    ephemeral: bool = True
    schema_version: str = _SCHEMA_VERSION

    def validate(self) -> "SandboxRuntimeBinding":
        if self.schema_version != _SCHEMA_VERSION:
            raise ExecutionSandboxContractError("unsupported runtime binding schema")
        for name in ("backend_id", "sandbox_id", "workspace_id"):
            _text(getattr(self, name), name)
        for name in (
            "backend_identity_digest",
            "backend_implementation_digest",
            "isolation_evidence_digest",
        ):
            _digest(getattr(self, name), name)
        if self.filesystem_mode != "WORKSPACE_ONLY":
            raise ExecutionSandboxContractError("sandbox filesystem must be WORKSPACE_ONLY")
        if self.network_mode != "DENY_ALL":
            raise ExecutionSandboxContractError("sandbox network must be DENY_ALL")
        if self.process_mode != "ALLOWLIST_ONLY":
            raise ExecutionSandboxContractError("sandbox process mode must be ALLOWLIST_ONLY")
        if self.ephemeral is not True:
            raise ExecutionSandboxContractError("sandbox workspace must be ephemeral")
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(
            b"LION/EXECUTOR-SANDBOX-RUNTIME-BINDING/1.0.0\x00"
            + canonical_json(asdict(self))
        ).hexdigest()


@dataclass(frozen=True)
class ExecutionSandboxPolicy:
    """Exact, non-delegable policy for one coding-agent sandbox workspace."""

    repository: str
    baseline_sha: str
    branch: str
    mission_id: str
    executor_id: str
    sandbox_id: str
    workspace_id: str
    authority_binding_digest: str
    runtime_binding_digest: str
    read_scope: tuple[str, ...]
    write_scope: tuple[str, ...]
    test_scope: tuple[str, ...]
    allowed_test_commands: tuple[tuple[str, ...], ...]
    resource_limits: SandboxResourceLimits
    schema_version: str = _SCHEMA_VERSION

    def validate(self) -> "ExecutionSandboxPolicy":
        if self.schema_version != _SCHEMA_VERSION:
            raise ExecutionSandboxContractError("unsupported sandbox policy schema")
        if not isinstance(self.repository, str) or not _REPOSITORY.fullmatch(self.repository):
            raise ExecutionSandboxContractError("repository must use owner/name form")
        _sha40(self.baseline_sha, "baseline_sha")
        _branch(self.branch)
        for name in ("mission_id", "executor_id", "sandbox_id", "workspace_id"):
            _text(getattr(self, name), name)
        _digest(self.authority_binding_digest, "authority_binding_digest")
        _digest(self.runtime_binding_digest, "runtime_binding_digest")
        _scope(self.read_scope, "read_scope")
        _scope(self.write_scope, "write_scope")
        _scope(self.test_scope, "test_scope")
        if type(self.allowed_test_commands) is not tuple or not self.allowed_test_commands:
            raise ExecutionSandboxContractError(
                "allowed_test_commands must be a non-empty immutable tuple"
            )
        commands = tuple(_command(command, "allowed_test_command") for command in self.allowed_test_commands)
        if len(set(commands)) != len(commands):
            raise ExecutionSandboxContractError("allowed_test_commands must be unique")
        if type(self.resource_limits) is not SandboxResourceLimits:
            raise ExecutionSandboxContractError("resource_limits type is invalid")
        self.resource_limits.validate()
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["read_scope"] = list(self.read_scope)
        value["write_scope"] = list(self.write_scope)
        value["test_scope"] = list(self.test_scope)
        value["allowed_test_commands"] = [list(item) for item in self.allowed_test_commands]
        return value

    def digest(self) -> str:
        return sha256(
            b"LION/EXECUTION-SANDBOX-POLICY/1.0.0\x00"
            + canonical_json(self.canonical_dict())
        ).hexdigest()


@dataclass(frozen=True)
class SandboxOperation:
    """One exact sandbox operation bound to one policy and executor."""

    operation_id: str
    mission_id: str
    executor_id: str
    sandbox_id: str
    workspace_id: str
    policy_digest: str
    action: str
    path: str
    payload_digest: str | None = None
    payload_size: int = 0
    command: tuple[str, ...] = ()
    schema_version: str = _SCHEMA_VERSION

    def validate(self) -> "SandboxOperation":
        if self.schema_version != _SCHEMA_VERSION:
            raise ExecutionSandboxContractError("unsupported sandbox operation schema")
        for name in ("operation_id", "mission_id", "executor_id", "sandbox_id", "workspace_id"):
            _text(getattr(self, name), name)
        _digest(self.policy_digest, "policy_digest")
        if self.action not in _ACTIONS:
            raise ExecutionSandboxContractError("sandbox action is not representable")
        _path(self.path)
        if isinstance(self.payload_size, bool) or not isinstance(self.payload_size, int) or self.payload_size < 0:
            raise ExecutionSandboxContractError("payload_size must be a non-negative integer")

        if self.action == "WRITE_FILE":
            if self.payload_digest is None:
                raise ExecutionSandboxContractError("WRITE_FILE requires payload_digest")
            _digest(self.payload_digest, "payload_digest")
            if self.command != ():
                raise ExecutionSandboxContractError("WRITE_FILE cannot carry a command")
        elif self.action == "RUN_TEST":
            if self.payload_digest is not None or self.payload_size != 0:
                raise ExecutionSandboxContractError("RUN_TEST cannot carry a payload")
            _command(self.command)
        else:
            if self.payload_digest is not None or self.payload_size != 0:
                raise ExecutionSandboxContractError("READ_FILE cannot carry a payload")
            if self.command != ():
                raise ExecutionSandboxContractError("READ_FILE cannot carry a command")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["command"] = list(self.command)
        return value

    def digest(self) -> str:
        return sha256(
            b"LION/SANDBOX-OPERATION/1.0.0\x00" + canonical_json(self.canonical_dict())
        ).hexdigest()


@dataclass(frozen=True)
class SandboxExecutionReceipt:
    """Evidence for one admitted operation; it carries no authority."""

    receipt_id: str
    operation_id: str
    operation_digest: str
    policy_digest: str
    authority_binding_digest: str
    runtime_binding_digest: str
    mission_id: str
    executor_id: str
    sandbox_id: str
    workspace_id: str
    action: str
    outcome: str
    effect_digest: str
    output_digest: str
    bytes_read: int
    bytes_written: int
    exit_code: int | None
    observed_events: tuple[str, ...]
    side_effect_refs: tuple[str, ...] = ()
    schema_version: str = _SCHEMA_VERSION

    def validate(self) -> "SandboxExecutionReceipt":
        if self.schema_version != _SCHEMA_VERSION:
            raise ExecutionSandboxContractError("unsupported sandbox receipt schema")
        for name in (
            "receipt_id",
            "operation_id",
            "mission_id",
            "executor_id",
            "sandbox_id",
            "workspace_id",
        ):
            _text(getattr(self, name), name)
        for name in (
            "operation_digest",
            "policy_digest",
            "authority_binding_digest",
            "runtime_binding_digest",
            "effect_digest",
            "output_digest",
        ):
            _digest(getattr(self, name), name)
        if self.action not in _ACTIONS:
            raise ExecutionSandboxContractError("receipt action is invalid")
        if self.outcome not in _OUTCOMES:
            raise ExecutionSandboxContractError("receipt outcome is invalid")
        for name in ("bytes_read", "bytes_written"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ExecutionSandboxContractError(f"{name} must be non-negative")
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise ExecutionSandboxContractError("exit_code must be an integer or None")
        if type(self.observed_events) is not tuple or not self.observed_events:
            raise ExecutionSandboxContractError("receipt requires observed_events")
        if len(set(self.observed_events)) != len(self.observed_events):
            raise ExecutionSandboxContractError("observed_events must be unique")
        for value in self.observed_events:
            _text(value, "observed_event")
        if type(self.side_effect_refs) is not tuple:
            raise ExecutionSandboxContractError("side_effect_refs must be an immutable tuple")
        if len(set(self.side_effect_refs)) != len(self.side_effect_refs):
            raise ExecutionSandboxContractError("side_effect_refs must be unique")
        for value in self.side_effect_refs:
            _text(value, "side_effect_ref")
        if self.action != "WRITE_FILE" and self.bytes_written != 0:
            raise ExecutionSandboxContractError("non-write receipt cannot report bytes_written")
        if self.action != "READ_FILE" and self.bytes_read != 0:
            raise ExecutionSandboxContractError("non-read receipt cannot report bytes_read")
        if self.action == "RUN_TEST" and self.exit_code is None:
            raise ExecutionSandboxContractError("RUN_TEST receipt requires exit_code")
        if self.action != "RUN_TEST" and self.exit_code is not None:
            raise ExecutionSandboxContractError("non-test receipt cannot report exit_code")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["observed_events"] = list(self.observed_events)
        value["side_effect_refs"] = list(self.side_effect_refs)
        return value

    def digest(self) -> str:
        return sha256(
            b"LION/SANDBOX-EXECUTION-RECEIPT/1.0.0\x00"
            + canonical_json(self.canonical_dict())
        ).hexdigest()

"""Fail-closed enforcement core for one bounded coding-agent sandbox.

This module mediates the only three representable operations: read a repository file,
write a repository file, and run one exactly allowlisted test command.  OS/container
isolation remains an external runtime obligation and is pinned by SandboxRuntimeBinding;
this reference core does not claim production complete mediation by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from typing import Protocol

from cyber_lion.contracts.executor_sandbox import (
    ExecutionSandboxContractError,
    ExecutionSandboxPolicy,
    SandboxExecutionReceipt,
    SandboxOperation,
    SandboxRuntimeBinding,
    path_within_scope,
)


class SandboxEnforcementError(ValueError):
    """Raised when an operation is denied before reaching the backend."""


@dataclass(frozen=True)
class SandboxBackendReadResult:
    data: bytes
    observed_event_ref: str


@dataclass(frozen=True)
class SandboxBackendWriteResult:
    observed_content_digest: str
    observed_event_ref: str
    side_effect_ref: str


@dataclass(frozen=True)
class SandboxBackendTestResult:
    exit_code: int
    stdout: bytes
    stderr: bytes
    observed_event_ref: str
    side_effect_refs: tuple[str, ...] = ()


class SandboxBackend(Protocol):
    backend_id: str
    backend_identity_digest: str
    backend_implementation_digest: str
    sandbox_id: str
    workspace_id: str

    def read_file(self, path: str) -> SandboxBackendReadResult: ...

    def write_file(self, path: str, payload: bytes) -> SandboxBackendWriteResult: ...

    def run_test(self, path: str, command: tuple[str, ...]) -> SandboxBackendTestResult: ...


class SandboxReplayGuard(Protocol):
    def consume(self, mission_id: str, operation_id: str) -> bool: ...


class InMemorySandboxReplayGuard:
    """Atomic process-local at-most-once guard for exact operation identifiers."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._seen: set[tuple[str, str]] = set()

    def consume(self, mission_id: str, operation_id: str) -> bool:
        key = (mission_id, operation_id)
        with self._lock:
            if key in self._seen:
                return False
            self._seen.add(key)
            return True


@dataclass(frozen=True)
class SandboxBudgetSnapshot:
    operations: int
    write_bytes: int
    test_runs: int


class SandboxBudgetLedger:
    """Atomic deterministic pre-effect budget reservation."""

    def __init__(self, policy: ExecutionSandboxPolicy) -> None:
        policy.validate()
        self._limits = policy.resource_limits
        self._lock = Lock()
        self._operations = 0
        self._write_bytes = 0
        self._test_runs = 0

    def reserve(self, operation: SandboxOperation) -> None:
        with self._lock:
            next_operations = self._operations + 1
            next_write_bytes = self._write_bytes + (
                operation.payload_size if operation.action == "WRITE_FILE" else 0
            )
            next_test_runs = self._test_runs + (1 if operation.action == "RUN_TEST" else 0)
            if next_operations > self._limits.max_operations:
                raise SandboxEnforcementError("sandbox operation budget exhausted")
            if next_write_bytes > self._limits.max_write_bytes:
                raise SandboxEnforcementError("sandbox write-byte budget exhausted")
            if next_test_runs > self._limits.max_test_runs:
                raise SandboxEnforcementError("sandbox test-run budget exhausted")
            self._operations = next_operations
            self._write_bytes = next_write_bytes
            self._test_runs = next_test_runs

    def snapshot(self) -> SandboxBudgetSnapshot:
        with self._lock:
            return SandboxBudgetSnapshot(
                operations=self._operations,
                write_bytes=self._write_bytes,
                test_runs=self._test_runs,
            )


@dataclass(frozen=True)
class SandboxExecutionResult:
    receipt: SandboxExecutionReceipt
    output: bytes


class ExecutorSandbox:
    """Narrow policy-enforcement point around a pinned isolated backend."""

    def __init__(
        self,
        *,
        policy: ExecutionSandboxPolicy,
        runtime_binding: SandboxRuntimeBinding,
        backend: SandboxBackend,
        replay_guard: SandboxReplayGuard,
        budget_ledger: SandboxBudgetLedger | None = None,
    ) -> None:
        try:
            policy.validate()
            runtime_binding.validate()
        except ExecutionSandboxContractError as exc:
            raise SandboxEnforcementError("sandbox configuration is invalid") from exc
        if runtime_binding.digest() != policy.runtime_binding_digest:
            raise SandboxEnforcementError("runtime binding does not match sandbox policy")
        if (
            runtime_binding.sandbox_id != policy.sandbox_id
            or runtime_binding.workspace_id != policy.workspace_id
        ):
            raise SandboxEnforcementError("runtime workspace binding mismatch")
        actual_backend = (
            getattr(backend, "backend_id", None),
            getattr(backend, "backend_identity_digest", None),
            getattr(backend, "backend_implementation_digest", None),
            getattr(backend, "sandbox_id", None),
            getattr(backend, "workspace_id", None),
        )
        expected_backend = (
            runtime_binding.backend_id,
            runtime_binding.backend_identity_digest,
            runtime_binding.backend_implementation_digest,
            runtime_binding.sandbox_id,
            runtime_binding.workspace_id,
        )
        if actual_backend != expected_backend:
            raise SandboxEnforcementError("sandbox backend identity/provenance mismatch")
        if not hasattr(replay_guard, "consume"):
            raise SandboxEnforcementError("sandbox replay guard is missing")
        self._policy = policy
        self._runtime_binding = runtime_binding
        self._backend = backend
        self._replay_guard = replay_guard
        self._budget = budget_ledger or SandboxBudgetLedger(policy)
        self._state_lock = Lock()
        self._closed = False

    @property
    def policy_digest(self) -> str:
        return self._policy.digest()

    def close(self) -> None:
        with self._state_lock:
            self._closed = True

    def budget_snapshot(self) -> SandboxBudgetSnapshot:
        return self._budget.snapshot()

    def execute(self, operation: SandboxOperation, *, payload: bytes = b"") -> SandboxExecutionResult:
        self._ensure_open()
        self._validate_operation(operation, payload)
        self._enforce_scope(operation)

        try:
            consumed = self._replay_guard.consume(operation.mission_id, operation.operation_id)
        except Exception as exc:
            raise SandboxEnforcementError("sandbox replay guard failed closed") from exc
        if consumed is not True:
            raise SandboxEnforcementError("sandbox operation replay denied")

        # Reservation happens before any effect-capable backend call.  Once the replay key
        # is consumed, a budget failure is intentionally not retryable under the same id.
        self._budget.reserve(operation)

        try:
            if operation.action == "READ_FILE":
                return self._execute_read(operation)
            if operation.action == "WRITE_FILE":
                return self._execute_write(operation, payload)
            return self._execute_test(operation)
        except Exception:
            # Effect state may be unknown.  The operation id remains consumed and the
            # boundary emits an ABORTED receipt instead of automatically retrying.
            return self._aborted_result(operation)

    def _ensure_open(self) -> None:
        with self._state_lock:
            if self._closed:
                raise SandboxEnforcementError("sandbox is closed")

    def _validate_operation(self, operation: SandboxOperation, payload: bytes) -> None:
        if type(operation) is not SandboxOperation:
            raise SandboxEnforcementError("sandbox operation type is invalid")
        try:
            operation.validate()
        except ExecutionSandboxContractError as exc:
            raise SandboxEnforcementError("sandbox operation contract is invalid") from exc
        expected = (
            self._policy.mission_id,
            self._policy.executor_id,
            self._policy.sandbox_id,
            self._policy.workspace_id,
            self._policy.digest(),
        )
        actual = (
            operation.mission_id,
            operation.executor_id,
            operation.sandbox_id,
            operation.workspace_id,
            operation.policy_digest,
        )
        if actual != expected:
            raise SandboxEnforcementError("sandbox operation binding mismatch")
        if not isinstance(payload, bytes):
            raise SandboxEnforcementError("sandbox payload must be bytes")
        if operation.action == "WRITE_FILE":
            if len(payload) != operation.payload_size:
                raise SandboxEnforcementError("write payload size mismatch")
            if sha256(payload).hexdigest() != operation.payload_digest:
                raise SandboxEnforcementError("write payload digest mismatch")
        elif payload:
            raise SandboxEnforcementError("non-write operation cannot carry payload bytes")

    def _enforce_scope(self, operation: SandboxOperation) -> None:
        if operation.action == "READ_FILE":
            allowed = path_within_scope(operation.path, self._policy.read_scope)
        elif operation.action == "WRITE_FILE":
            allowed = path_within_scope(operation.path, self._policy.write_scope)
        else:
            allowed = path_within_scope(operation.path, self._policy.test_scope)
            if operation.command not in self._policy.allowed_test_commands:
                raise SandboxEnforcementError("test command is not exactly allowlisted")
        if not allowed:
            raise SandboxEnforcementError("sandbox path is outside admitted scope")

    def _execute_read(self, operation: SandboxOperation) -> SandboxExecutionResult:
        result = self._backend.read_file(operation.path)
        if type(result) is not SandboxBackendReadResult:
            raise SandboxEnforcementError("sandbox backend returned invalid read result")
        if not isinstance(result.data, bytes) or not result.observed_event_ref:
            raise SandboxEnforcementError("sandbox read result is invalid")
        if len(result.data) > self._policy.resource_limits.max_output_bytes:
            raise SandboxEnforcementError("sandbox read output exceeds budget")
        output_digest = sha256(result.data).hexdigest()
        receipt = self._receipt(
            operation,
            outcome="SUCCEEDED",
            effect_digest=output_digest,
            output_digest=output_digest,
            bytes_read=len(result.data),
            bytes_written=0,
            exit_code=None,
            observed_events=(result.observed_event_ref,),
        )
        return SandboxExecutionResult(receipt=receipt, output=result.data)

    def _execute_write(self, operation: SandboxOperation, payload: bytes) -> SandboxExecutionResult:
        result = self._backend.write_file(operation.path, payload)
        if type(result) is not SandboxBackendWriteResult:
            raise SandboxEnforcementError("sandbox backend returned invalid write result")
        if result.observed_content_digest != operation.payload_digest:
            raise SandboxEnforcementError("post-write content digest mismatch")
        if not result.observed_event_ref or not result.side_effect_ref:
            raise SandboxEnforcementError("sandbox write observation is incomplete")
        empty_digest = sha256(b"").hexdigest()
        receipt = self._receipt(
            operation,
            outcome="SUCCEEDED",
            effect_digest=result.observed_content_digest,
            output_digest=empty_digest,
            bytes_read=0,
            bytes_written=len(payload),
            exit_code=None,
            observed_events=(result.observed_event_ref,),
            side_effect_refs=(result.side_effect_ref,),
        )
        return SandboxExecutionResult(receipt=receipt, output=b"")

    def _execute_test(self, operation: SandboxOperation) -> SandboxExecutionResult:
        result = self._backend.run_test(operation.path, operation.command)
        if type(result) is not SandboxBackendTestResult:
            raise SandboxEnforcementError("sandbox backend returned invalid test result")
        if isinstance(result.exit_code, bool) or not isinstance(result.exit_code, int):
            raise SandboxEnforcementError("sandbox test exit_code is invalid")
        if not isinstance(result.stdout, bytes) or not isinstance(result.stderr, bytes):
            raise SandboxEnforcementError("sandbox test output must be bytes")
        if not result.observed_event_ref:
            raise SandboxEnforcementError("sandbox test observation is missing")
        if type(result.side_effect_refs) is not tuple or len(set(result.side_effect_refs)) != len(result.side_effect_refs):
            raise SandboxEnforcementError("sandbox test side_effect_refs are invalid")
        output = result.stdout + result.stderr
        if len(output) > self._policy.resource_limits.max_output_bytes:
            raise SandboxEnforcementError("sandbox test output exceeds budget")
        output_digest = sha256(output).hexdigest()
        effect_digest = sha256(
            b"LION/SANDBOX-TEST-EFFECT/1.0.0\x00"
            + str(result.exit_code).encode("ascii")
            + b"\x00"
            + output_digest.encode("ascii")
        ).hexdigest()
        receipt = self._receipt(
            operation,
            outcome="SUCCEEDED" if result.exit_code == 0 else "FAILED",
            effect_digest=effect_digest,
            output_digest=output_digest,
            bytes_read=0,
            bytes_written=0,
            exit_code=result.exit_code,
            observed_events=(result.observed_event_ref,),
            side_effect_refs=result.side_effect_refs,
        )
        return SandboxExecutionResult(receipt=receipt, output=output)

    def _aborted_result(self, operation: SandboxOperation) -> SandboxExecutionResult:
        empty_digest = sha256(b"").hexdigest()
        unknown_effect_digest = sha256(
            b"LION/SANDBOX-UNKNOWN-EFFECT/1.0.0\x00"
            + operation.digest().encode("ascii")
        ).hexdigest()
        event_ref = f"sandbox:{self._policy.sandbox_id}:operation:{operation.operation_id}:aborted"
        receipt = self._receipt(
            operation,
            outcome="ABORTED",
            effect_digest=unknown_effect_digest,
            output_digest=empty_digest,
            bytes_read=0,
            bytes_written=0,
            exit_code=-1 if operation.action == "RUN_TEST" else None,
            observed_events=(event_ref,),
        )
        return SandboxExecutionResult(receipt=receipt, output=b"")

    def _receipt(
        self,
        operation: SandboxOperation,
        *,
        outcome: str,
        effect_digest: str,
        output_digest: str,
        bytes_read: int,
        bytes_written: int,
        exit_code: int | None,
        observed_events: tuple[str, ...],
        side_effect_refs: tuple[str, ...] = (),
    ) -> SandboxExecutionReceipt:
        operation_digest = operation.digest()
        receipt = SandboxExecutionReceipt(
            receipt_id=f"{self._policy.sandbox_id}:{operation.operation_id}",
            operation_id=operation.operation_id,
            operation_digest=operation_digest,
            policy_digest=self._policy.digest(),
            authority_binding_digest=self._policy.authority_binding_digest,
            runtime_binding_digest=self._runtime_binding.digest(),
            mission_id=self._policy.mission_id,
            executor_id=self._policy.executor_id,
            sandbox_id=self._policy.sandbox_id,
            workspace_id=self._policy.workspace_id,
            action=operation.action,
            outcome=outcome,
            effect_digest=effect_digest,
            output_digest=output_digest,
            bytes_read=bytes_read,
            bytes_written=bytes_written,
            exit_code=exit_code,
            observed_events=observed_events,
            side_effect_refs=side_effect_refs,
        )
        receipt.validate()
        return receipt

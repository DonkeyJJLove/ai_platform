from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import unittest

from cyber_lion.contracts.executor_sandbox import (
    ExecutionSandboxPolicy,
    SandboxOperation,
    SandboxResourceLimits,
    SandboxRuntimeBinding,
)
from cyber_lion.enterprise.executor_sandbox import (
    ExecutorSandbox,
    InMemorySandboxReplayGuard,
    SandboxBackendReadResult,
    SandboxBackendTestResult,
    SandboxBackendWriteResult,
    SandboxBudgetLedger,
    SandboxEnforcementError,
)

BASELINE = "2" * 40
AUTHORITY = sha256(b"authority-binding").hexdigest()
IDENTITY = sha256(b"sandbox-backend-identity").hexdigest()
IMPLEMENTATION = sha256(b"sandbox-backend-implementation").hexdigest()
ISOLATION = sha256(b"sandbox-isolation-evidence").hexdigest()


def runtime_binding(**changes) -> SandboxRuntimeBinding:
    base = SandboxRuntimeBinding(
        backend_id="sandbox-backend-v1",
        backend_identity_digest=IDENTITY,
        backend_implementation_digest=IMPLEMENTATION,
        isolation_evidence_digest=ISOLATION,
        sandbox_id="f005-c-sandbox-01",
        workspace_id="workspace-f005-c-01",
    )
    return replace(base, **changes)


def policy(*, limits: SandboxResourceLimits | None = None, **changes) -> ExecutionSandboxPolicy:
    binding = runtime_binding()
    base = ExecutionSandboxPolicy(
        repository="DonkeyJJLove/ai_platform",
        baseline_sha=BASELINE,
        branch="mission/f005-c-executor-sandbox",
        mission_id="F005-C-EXECUTION-SANDBOX-BUILD",
        executor_id="F005-C-BUILDER-01",
        sandbox_id=binding.sandbox_id,
        workspace_id=binding.workspace_id,
        authority_binding_digest=AUTHORITY,
        runtime_binding_digest=binding.digest(),
        read_scope=("cyber_lion",),
        write_scope=(
            "cyber_lion/contracts/executor_sandbox.py",
            "cyber_lion/enterprise/executor_sandbox.py",
            "cyber_lion/tests/test_executor_sandbox_contract.py",
            "cyber_lion/tests/test_executor_sandbox.py",
        ),
        test_scope=("cyber_lion/tests",),
        allowed_test_commands=(
            ("python", "-m", "unittest", "cyber_lion.tests.test_executor_sandbox", "-v"),
        ),
        resource_limits=limits or SandboxResourceLimits(
            max_operations=16,
            max_write_bytes=10_000,
            max_output_bytes=10_000,
            max_test_runs=4,
        ),
    )
    return replace(base, **changes)


class FakeBackend:
    backend_id = "sandbox-backend-v1"
    backend_identity_digest = IDENTITY
    backend_implementation_digest = IMPLEMENTATION
    sandbox_id = "f005-c-sandbox-01"
    workspace_id = "workspace-f005-c-01"

    def __init__(self) -> None:
        self.files = {"cyber_lion/README.md": b"fleet sandbox\n"}
        self.read_calls = 0
        self.write_calls = 0
        self.test_calls = 0
        self.raise_on_write = False
        self.wrong_post_write_digest = False
        self.test_exit_code = 0
        self.test_stdout = b"ok\n"
        self.test_stderr = b""

    def read_file(self, path: str) -> SandboxBackendReadResult:
        self.read_calls += 1
        data = self.files.get(path, b"")
        return SandboxBackendReadResult(data=data, observed_event_ref=f"read:{path}")

    def write_file(self, path: str, payload: bytes) -> SandboxBackendWriteResult:
        self.write_calls += 1
        self.files[path] = payload
        if self.raise_on_write:
            raise RuntimeError("effect may already have happened")
        digest = sha256(payload).hexdigest()
        if self.wrong_post_write_digest:
            digest = sha256(b"different").hexdigest()
        return SandboxBackendWriteResult(
            observed_content_digest=digest,
            observed_event_ref=f"write-observed:{path}",
            side_effect_ref=f"workspace-write:{path}",
        )

    def run_test(self, path: str, command: tuple[str, ...]) -> SandboxBackendTestResult:
        self.test_calls += 1
        return SandboxBackendTestResult(
            exit_code=self.test_exit_code,
            stdout=self.test_stdout,
            stderr=self.test_stderr,
            observed_event_ref=f"test:{path}:{self.test_calls}",
        )


def sandbox(*, item: ExecutionSandboxPolicy | None = None, backend: FakeBackend | None = None) -> tuple[ExecutorSandbox, FakeBackend]:
    item = item or policy()
    backend = backend or FakeBackend()
    return (
        ExecutorSandbox(
            policy=item,
            runtime_binding=runtime_binding(),
            backend=backend,
            replay_guard=InMemorySandboxReplayGuard(),
        ),
        backend,
    )


def read_op(item: ExecutionSandboxPolicy, *, operation_id: str = "read-1", **changes) -> SandboxOperation:
    base = SandboxOperation(
        operation_id=operation_id,
        mission_id=item.mission_id,
        executor_id=item.executor_id,
        sandbox_id=item.sandbox_id,
        workspace_id=item.workspace_id,
        policy_digest=item.digest(),
        action="READ_FILE",
        path="cyber_lion/README.md",
    )
    return replace(base, **changes)


def write_op(item: ExecutionSandboxPolicy, payload: bytes, *, operation_id: str = "write-1", **changes) -> SandboxOperation:
    base = SandboxOperation(
        operation_id=operation_id,
        mission_id=item.mission_id,
        executor_id=item.executor_id,
        sandbox_id=item.sandbox_id,
        workspace_id=item.workspace_id,
        policy_digest=item.digest(),
        action="WRITE_FILE",
        path="cyber_lion/contracts/executor_sandbox.py",
        payload_digest=sha256(payload).hexdigest(),
        payload_size=len(payload),
    )
    return replace(base, **changes)


def test_op(item: ExecutionSandboxPolicy, *, operation_id: str = "test-1", **changes) -> SandboxOperation:
    base = SandboxOperation(
        operation_id=operation_id,
        mission_id=item.mission_id,
        executor_id=item.executor_id,
        sandbox_id=item.sandbox_id,
        workspace_id=item.workspace_id,
        policy_digest=item.digest(),
        action="RUN_TEST",
        path="cyber_lion/tests/test_executor_sandbox.py",
        command=item.allowed_test_commands[0],
    )
    return replace(base, **changes)


class ExecutorSandboxTests(unittest.TestCase):
    def test_valid_read_returns_bound_receipt(self) -> None:
        item = policy()
        executor, backend = sandbox(item=item)
        result = executor.execute(read_op(item))
        self.assertEqual(result.output, b"fleet sandbox\n")
        self.assertEqual(result.receipt.outcome, "SUCCEEDED")
        self.assertEqual(result.receipt.policy_digest, item.digest())
        self.assertEqual(result.receipt.authority_binding_digest, item.authority_binding_digest)
        self.assertEqual(backend.read_calls, 1)

    def test_out_of_scope_read_fails_before_backend(self) -> None:
        item = replace(policy(), read_scope=("cyber_lion/contracts",))
        executor, backend = sandbox(item=item)
        with self.assertRaises(SandboxEnforcementError):
            executor.execute(read_op(item, path="README.md"))
        self.assertEqual(backend.read_calls, 0)

    def test_valid_write_is_observed_and_bounded(self) -> None:
        item = policy()
        executor, backend = sandbox(item=item)
        payload = b"contract-v1\n"
        result = executor.execute(write_op(item, payload), payload=payload)
        self.assertEqual(result.receipt.outcome, "SUCCEEDED")
        self.assertEqual(result.receipt.effect_digest, sha256(payload).hexdigest())
        self.assertEqual(result.receipt.bytes_written, len(payload))
        self.assertEqual(backend.files["cyber_lion/contracts/executor_sandbox.py"], payload)

    def test_write_outside_exact_scope_is_denied_before_effect(self) -> None:
        item = policy()
        executor, backend = sandbox(item=item)
        payload = b"evil"
        operation = write_op(item, payload, path="cyber_lion/contracts/runtime_attestation.py")
        with self.assertRaises(SandboxEnforcementError):
            executor.execute(operation, payload=payload)
        self.assertEqual(backend.write_calls, 0)

    def test_payload_tamper_is_denied_before_effect(self) -> None:
        item = policy()
        executor, backend = sandbox(item=item)
        payload = b"expected"
        with self.assertRaises(SandboxEnforcementError):
            executor.execute(write_op(item, payload), payload=b"tampered")
        self.assertEqual(backend.write_calls, 0)

    def test_wrong_executor_and_policy_binding_are_denied(self) -> None:
        item = policy()
        executor, backend = sandbox(item=item)
        with self.assertRaises(SandboxEnforcementError):
            executor.execute(read_op(item, executor_id="other-builder"))
        with self.assertRaises(SandboxEnforcementError):
            executor.execute(read_op(item, policy_digest=sha256(b"other-policy").hexdigest()))
        self.assertEqual(backend.read_calls, 0)

    def test_unallowlisted_test_command_is_denied_before_backend(self) -> None:
        item = policy()
        executor, backend = sandbox(item=item)
        with self.assertRaises(SandboxEnforcementError):
            executor.execute(test_op(item, command=("sh", "-c", "git push origin master")))
        self.assertEqual(backend.test_calls, 0)

    def test_test_result_preserves_success_and_failure(self) -> None:
        item = policy()
        backend = FakeBackend()
        executor, _ = sandbox(item=item, backend=backend)
        success = executor.execute(test_op(item, operation_id="test-success"))
        self.assertEqual(success.receipt.outcome, "SUCCEEDED")
        backend.test_exit_code = 2
        backend.test_stdout = b""
        backend.test_stderr = b"failed\n"
        failure = executor.execute(test_op(item, operation_id="test-failure"))
        self.assertEqual(failure.receipt.outcome, "FAILED")
        self.assertEqual(failure.receipt.exit_code, 2)
        self.assertEqual(failure.output, b"failed\n")

    def test_replay_is_denied_and_effect_is_not_repeated(self) -> None:
        item = policy()
        executor, backend = sandbox(item=item)
        payload = b"once"
        operation = write_op(item, payload)
        executor.execute(operation, payload=payload)
        with self.assertRaises(SandboxEnforcementError):
            executor.execute(operation, payload=payload)
        self.assertEqual(backend.write_calls, 1)

    def test_write_budget_is_reserved_before_effect(self) -> None:
        constrained = SandboxResourceLimits(
            max_operations=4,
            max_write_bytes=3,
            max_output_bytes=100,
            max_test_runs=2,
        )
        item = policy(limits=constrained)
        executor, backend = sandbox(item=item)
        payload = b"four"
        with self.assertRaises(SandboxEnforcementError):
            executor.execute(write_op(item, payload), payload=payload)
        self.assertEqual(backend.write_calls, 0)

    def test_test_run_budget_is_pre_effect(self) -> None:
        constrained = SandboxResourceLimits(
            max_operations=4,
            max_write_bytes=100,
            max_output_bytes=100,
            max_test_runs=1,
        )
        item = policy(limits=constrained)
        executor, backend = sandbox(item=item)
        executor.execute(test_op(item, operation_id="test-a"))
        with self.assertRaises(SandboxEnforcementError):
            executor.execute(test_op(item, operation_id="test-b"))
        self.assertEqual(backend.test_calls, 1)

    def test_backend_error_after_possible_effect_aborts_without_auto_retry(self) -> None:
        item = policy()
        backend = FakeBackend()
        backend.raise_on_write = True
        executor, _ = sandbox(item=item, backend=backend)
        payload = b"uncertain"
        operation = write_op(item, payload)
        result = executor.execute(operation, payload=payload)
        self.assertEqual(result.receipt.outcome, "ABORTED")
        self.assertEqual(backend.write_calls, 1)
        self.assertEqual(backend.files["cyber_lion/contracts/executor_sandbox.py"], payload)
        with self.assertRaises(SandboxEnforcementError):
            executor.execute(operation, payload=payload)
        self.assertEqual(backend.write_calls, 1)

    def test_post_write_digest_mismatch_aborts_and_cannot_replay(self) -> None:
        item = policy()
        backend = FakeBackend()
        backend.wrong_post_write_digest = True
        executor, _ = sandbox(item=item, backend=backend)
        payload = b"candidate"
        operation = write_op(item, payload)
        result = executor.execute(operation, payload=payload)
        self.assertEqual(result.receipt.outcome, "ABORTED")
        with self.assertRaises(SandboxEnforcementError):
            executor.execute(operation, payload=payload)
        self.assertEqual(backend.write_calls, 1)

    def test_output_budget_violation_aborts_consumed_operation(self) -> None:
        constrained = SandboxResourceLimits(
            max_operations=4,
            max_write_bytes=100,
            max_output_bytes=3,
            max_test_runs=2,
        )
        item = policy(limits=constrained)
        backend = FakeBackend()
        backend.files["cyber_lion/README.md"] = b"too-large"
        executor, _ = sandbox(item=item, backend=backend)
        operation = read_op(item)
        result = executor.execute(operation)
        self.assertEqual(result.receipt.outcome, "ABORTED")
        with self.assertRaises(SandboxEnforcementError):
            executor.execute(operation)
        self.assertEqual(backend.read_calls, 1)

    def test_backend_identity_and_runtime_provenance_are_pinned(self) -> None:
        item = policy()
        backend = FakeBackend()
        backend.backend_implementation_digest = sha256(b"tampered-backend").hexdigest()
        with self.assertRaises(SandboxEnforcementError):
            ExecutorSandbox(
                policy=item,
                runtime_binding=runtime_binding(),
                backend=backend,
                replay_guard=InMemorySandboxReplayGuard(),
            )

    def test_runtime_binding_must_match_exact_policy(self) -> None:
        binding = runtime_binding(isolation_evidence_digest=sha256(b"different-isolation").hexdigest())
        item = policy()
        with self.assertRaises(SandboxEnforcementError):
            ExecutorSandbox(
                policy=item,
                runtime_binding=binding,
                backend=FakeBackend(),
                replay_guard=InMemorySandboxReplayGuard(),
            )

    def test_close_denies_late_execution(self) -> None:
        item = policy()
        executor, backend = sandbox(item=item)
        executor.close()
        with self.assertRaises(SandboxEnforcementError):
            executor.execute(read_op(item))
        self.assertEqual(backend.read_calls, 0)

    def test_no_generic_effect_surface_exists(self) -> None:
        item = policy()
        executor, _ = sandbox(item=item)
        for name in ("execute_shell", "run_command", "network_request", "update_ref", "merge", "deploy"):
            self.assertFalse(hasattr(executor, name), name)

    def test_budget_ledger_can_be_injected_and_observed(self) -> None:
        item = policy()
        ledger = SandboxBudgetLedger(item)
        backend = FakeBackend()
        executor = ExecutorSandbox(
            policy=item,
            runtime_binding=runtime_binding(),
            backend=backend,
            replay_guard=InMemorySandboxReplayGuard(),
            budget_ledger=ledger,
        )
        executor.execute(read_op(item))
        self.assertEqual(executor.budget_snapshot().operations, 1)
        self.assertEqual(executor.budget_snapshot().write_bytes, 0)


if __name__ == "__main__":
    unittest.main()

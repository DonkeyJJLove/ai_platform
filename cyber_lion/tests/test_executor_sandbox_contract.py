from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import unittest

from cyber_lion.contracts.executor_sandbox import (
    ExecutionSandboxContractError,
    ExecutionSandboxPolicy,
    SandboxExecutionReceipt,
    SandboxOperation,
    SandboxResourceLimits,
    SandboxRuntimeBinding,
    path_within_scope,
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


def limits(**changes) -> SandboxResourceLimits:
    base = SandboxResourceLimits(
        max_operations=32,
        max_write_bytes=200_000,
        max_output_bytes=100_000,
        max_test_runs=8,
    )
    return replace(base, **changes)


def policy(**changes) -> ExecutionSandboxPolicy:
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
            ("python", "-m", "unittest", "cyber_lion.tests.test_executor_sandbox_contract", "-v"),
            ("python", "-m", "unittest", "cyber_lion.tests.test_executor_sandbox", "-v"),
        ),
        resource_limits=limits(),
    )
    return replace(base, **changes)


def read_operation(**changes) -> SandboxOperation:
    item = policy()
    base = SandboxOperation(
        operation_id="op-read-1",
        mission_id=item.mission_id,
        executor_id=item.executor_id,
        sandbox_id=item.sandbox_id,
        workspace_id=item.workspace_id,
        policy_digest=item.digest(),
        action="READ_FILE",
        path="cyber_lion/TARGET_ARCHITECTURE.md",
    )
    return replace(base, **changes)


class ExecutorSandboxContractTests(unittest.TestCase):
    def test_runtime_binding_requires_fail_closed_isolation_modes(self) -> None:
        runtime_binding().validate()
        for field, value in (
            ("network_mode", "ALLOW"),
            ("filesystem_mode", "HOST_RW"),
            ("process_mode", "SHELL"),
            ("ephemeral", False),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ExecutionSandboxContractError):
                    replace(runtime_binding(), **{field: value}).validate()

    def test_policy_digest_binds_authority_and_runtime_without_minting_authority(self) -> None:
        item = policy()
        item.validate()
        changed = replace(item, authority_binding_digest=sha256(b"other-authority").hexdigest())
        self.assertNotEqual(item.digest(), changed.digest())
        self.assertFalse(hasattr(item, "grant"))
        self.assertFalse(hasattr(item, "delegate"))

    def test_policy_rejects_unsafe_or_duplicate_scope(self) -> None:
        with self.assertRaises(ExecutionSandboxContractError):
            replace(policy(), write_scope=("../master",)).validate()
        with self.assertRaises(ExecutionSandboxContractError):
            replace(policy(), read_scope=("cyber_lion", "cyber_lion")).validate()
        with self.assertRaises(ExecutionSandboxContractError):
            replace(policy(), branch="refs/heads/master").validate()

    def test_path_scope_uses_component_boundaries(self) -> None:
        self.assertTrue(path_within_scope("cyber_lion/tests/test_x.py", ("cyber_lion/tests",)))
        self.assertFalse(path_within_scope("cyber_lion/tests_evil/test_x.py", ("cyber_lion/tests",)))

    def test_arbitrary_shell_network_and_ref_actions_are_unrepresentable(self) -> None:
        for action in ("SHELL", "NETWORK", "GIT_PUSH", "UPDATE_REF", "MERGE", "DEPLOY"):
            with self.subTest(action=action):
                with self.assertRaises(ExecutionSandboxContractError):
                    replace(read_operation(), action=action).validate()

    def test_read_operation_cannot_smuggle_payload_or_command(self) -> None:
        with self.assertRaises(ExecutionSandboxContractError):
            replace(
                read_operation(),
                payload_digest=sha256(b"x").hexdigest(),
                payload_size=1,
            ).validate()
        with self.assertRaises(ExecutionSandboxContractError):
            replace(read_operation(), command=("sh", "-c", "id")).validate()

    def test_write_operation_requires_exact_payload_binding(self) -> None:
        item = policy()
        payload = b"new bytes"
        operation = SandboxOperation(
            operation_id="op-write-1",
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
        operation.validate()
        self.assertNotEqual(operation.digest(), replace(operation, payload_size=len(payload) + 1).digest())

    def test_test_operation_uses_argv_not_generic_shell_field(self) -> None:
        item = policy()
        operation = SandboxOperation(
            operation_id="op-test-1",
            mission_id=item.mission_id,
            executor_id=item.executor_id,
            sandbox_id=item.sandbox_id,
            workspace_id=item.workspace_id,
            policy_digest=item.digest(),
            action="RUN_TEST",
            path="cyber_lion/tests/test_executor_sandbox.py",
            command=item.allowed_test_commands[1],
        )
        operation.validate()
        self.assertFalse(hasattr(operation, "shell"))

    def test_resource_limits_are_positive_integers(self) -> None:
        for field, value in (
            ("max_operations", 0),
            ("max_write_bytes", -1),
            ("max_output_bytes", True),
            ("max_test_runs", 0),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ExecutionSandboxContractError):
                    replace(limits(), **{field: value}).validate()

    def test_receipt_is_evidence_not_permission(self) -> None:
        item = policy()
        operation = read_operation()
        digest = sha256(b"observed").hexdigest()
        receipt = SandboxExecutionReceipt(
            receipt_id="receipt-1",
            operation_id=operation.operation_id,
            operation_digest=operation.digest(),
            policy_digest=item.digest(),
            authority_binding_digest=item.authority_binding_digest,
            runtime_binding_digest=item.runtime_binding_digest,
            mission_id=item.mission_id,
            executor_id=item.executor_id,
            sandbox_id=item.sandbox_id,
            workspace_id=item.workspace_id,
            action="READ_FILE",
            outcome="SUCCEEDED",
            effect_digest=digest,
            output_digest=digest,
            bytes_read=8,
            bytes_written=0,
            exit_code=None,
            observed_events=("sandbox:read:1",),
        )
        receipt.validate()
        self.assertFalse(hasattr(receipt, "authority_ceiling"))
        self.assertFalse(hasattr(receipt, "approve"))


if __name__ == "__main__":
    unittest.main()

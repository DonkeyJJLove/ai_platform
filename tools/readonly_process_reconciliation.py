"""Pure reconciliation for the C2 read-only process experiment."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

RECONCILER_VERSION = "lion.c2.readonly-process-reconcile/v1.0-candidate"


@dataclass(frozen=True)
class ReconciliationReceipt:
    reconciler_version: str
    action_spec_digest: str
    execution_digest: str
    observation_digest: str
    status: str
    anomalies: tuple[str, ...]
    receipt_digest: str


def reconcile(prepared: Any, execution: Any, observation: Any) -> ReconciliationReceipt:
    anomalies: list[str] = []
    if execution.action_spec_digest != prepared.action_spec_digest:
        anomalies.append("ACTION_SPEC_DIGEST_MISMATCH")
    if execution.executable_digest != prepared.executable_digest:
        anomalies.append("EXECUTABLE_DIGEST_MISMATCH")
    if execution.sandbox_wrapper_digest != prepared.sandbox_wrapper_digest:
        anomalies.append("SANDBOX_DIGEST_MISMATCH")
    if execution.returncode != 0:
        anomalies.append("NONZERO_EXIT")
    if execution.stdout != prepared.expected_stdout:
        anomalies.append("STDOUT_MISMATCH")
    if execution.stderr != b"":
        anomalies.append("STDERR_NONEMPTY")
    if observation.workspace_before.digest != observation.workspace_after.digest:
        anomalies.append("WORKSPACE_MUTATION")
    if observation.workspace_before.file_count != observation.workspace_after.file_count:
        anomalies.append("WORKSPACE_CARDINALITY_CHANGE")
    if observation.socket_seen:
        anomalies.append("SOCKET_OBSERVED")
    if observation.child_pids:
        anomalies.append("CHILD_PROCESS_OBSERVED")
    if not observation.target_exited:
        anomalies.append("TARGET_SURVIVED")
    status = "MATCH" if not anomalies else "MISMATCH"
    payload = {
        "reconciler_version": RECONCILER_VERSION,
        "action_spec_digest": prepared.action_spec_digest,
        "execution_digest": execution.execution_digest,
        "observation_digest": observation.observation_digest,
        "status": status,
        "anomalies": anomalies,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()
    return ReconciliationReceipt(
        reconciler_version=RECONCILER_VERSION,
        action_spec_digest=prepared.action_spec_digest,
        execution_digest=execution.execution_digest,
        observation_digest=observation.observation_digest,
        status=status,
        anomalies=tuple(anomalies),
        receipt_digest=digest,
    )

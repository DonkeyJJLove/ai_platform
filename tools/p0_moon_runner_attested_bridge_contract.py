from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Tuple

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")

RUNNER = "lion-moon-r9d8-test"
AGENT = 24
OS_USER = "lion-maintenance-runner"
UID = 993
HOST = "LION-AUTH-LAB"
MACHINE = "e69aa593257d47b8885d1bd87710b196"
POOL = "Default"
CONTROL_ISSUE = 144
WORKFLOW = "LION MOON Runner Attested Execution Bridge"
WORKFLOW_PATH = ".github/workflows/lion-moon-runner-attested-execution-bridge.yml"
JOB_ID = "execute-operation"
OPERATIONS = (
    "OBSERVE_SCHEMA",
    "OBSERVE_SAME_CONNECTION_PRAGMA",
    "DENY_WRONG_EXPECTED_STATE",
    "DENY_REPLAYED_EFFECT_KEY",
    "DENY_REPOSITORY_SUBSTITUTION",
    "DENY_ACTOR_SUBSTITUTION",
    "DENY_CONTROL_ISSUE_SUBSTITUTION",
)


class RunnerAttestationContractError(ValueError):
    pass


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise RunnerAttestationContractError(f"{name} invalid")
    return value


def _sha40(value: str, name: str) -> str:
    _text(value, name)
    if _SHA40.fullmatch(value) is None:
        raise RunnerAttestationContractError(f"{name} must be git sha")
    return value


def _sha64(value: str, name: str) -> str:
    _text(value, name)
    if _SHA64.fullmatch(value) is None:
        raise RunnerAttestationContractError(f"{name} must be sha256")
    return value


def _digest(domain: bytes, value: object) -> str:
    raw = json.dumps(
        asdict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=list,
    ).encode("utf-8")
    return sha256(domain + b"\0" + raw).hexdigest()


@dataclass(frozen=True)
class RunnerExecutionAttestation:
    revision: str
    tree: str
    runner_name: str
    runner_agent_id: int
    pool_name: str
    os_user: str
    uid: int
    hostname: str
    machine_id: str
    github_actions: str
    run_id: str
    job_id: str
    workflow: str
    workflow_ref: str
    github_ref: str
    github_sha: str
    worker_binary_sha256: str
    observed_at: str
    attestation_digest: str = ""

    def payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("attestation_digest")
        return value

    def validate(self) -> "RunnerExecutionAttestation":
        _sha40(self.revision, "revision")
        _sha40(self.tree, "tree")
        _sha40(self.github_sha, "github_sha")
        _sha64(self.worker_binary_sha256, "worker_binary_sha256")
        if self.revision != self.github_sha:
            raise RunnerAttestationContractError("runtime sha mismatch")
        expected_identity = (RUNNER, AGENT, POOL, OS_USER, UID, HOST, MACHINE)
        actual_identity = (
            self.runner_name,
            self.runner_agent_id,
            self.pool_name,
            self.os_user,
            self.uid,
            self.hostname,
            self.machine_id,
        )
        if actual_identity != expected_identity:
            raise RunnerAttestationContractError("runner identity mismatch")
        if self.github_actions != "true":
            raise RunnerAttestationContractError("GITHUB_ACTIONS missing")
        if not self.run_id.isdigit() or int(self.run_id) <= 0:
            raise RunnerAttestationContractError("run id invalid")
        if self.job_id != JOB_ID or self.workflow != WORKFLOW:
            raise RunnerAttestationContractError("workflow job identity mismatch")
        _text(self.github_ref, "github_ref")
        prefix = f"DonkeyJJLove/ai_platform/{WORKFLOW_PATH}@"
        if self.workflow_ref != prefix + self.github_ref:
            raise RunnerAttestationContractError("workflow ref mismatch")
        _text(self.observed_at, "observed_at")
        expected = sha256(
            b"LION/MOON-RUNNER-EXECUTION-ATTESTATION/1\0"
            + json.dumps(
                self.payload(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        if self.attestation_digest and self.attestation_digest != expected:
            raise RunnerAttestationContractError("attestation digest mismatch")
        return self

    def sealed(self) -> "RunnerExecutionAttestation":
        self.validate()
        payload = self.payload()
        digest = sha256(
            b"LION/MOON-RUNNER-EXECUTION-ATTESTATION/1\0"
            + json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        return RunnerExecutionAttestation(
            **payload,
            attestation_digest=digest,
        ).validate()


@dataclass(frozen=True)
class RunnerAttestedOperationReceipt:
    attestation_digest: str
    run_id: str
    job_id: str
    workflow_ref: str
    revision: str
    tree: str
    runner_name: str
    runner_agent_id: int
    os_user: str
    uid: int
    hostname: str
    machine_id: str
    operation: str
    result: str
    result_digest: str
    observed_at: str
    receipt_digest: str = ""

    def payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("receipt_digest")
        return value

    def validate(self) -> "RunnerAttestedOperationReceipt":
        _sha64(self.attestation_digest, "attestation_digest")
        _sha64(self.result_digest, "result_digest")
        _sha40(self.revision, "revision")
        _sha40(self.tree, "tree")
        if (
            self.runner_name,
            self.runner_agent_id,
            self.os_user,
            self.uid,
            self.hostname,
            self.machine_id,
        ) != (RUNNER, AGENT, OS_USER, UID, HOST, MACHINE):
            raise RunnerAttestationContractError("receipt runner mismatch")
        if self.operation not in OPERATIONS:
            raise RunnerAttestationContractError("receipt operation invalid")
        expected_result = "OBSERVED" if self.operation.startswith("OBSERVE_") else "DENIED"
        if self.result != expected_result:
            raise RunnerAttestationContractError("receipt result invalid")
        if self.job_id != JOB_ID or not self.run_id.isdigit():
            raise RunnerAttestationContractError("receipt job/run invalid")
        _text(self.workflow_ref, "workflow_ref")
        _text(self.observed_at, "observed_at")
        expected = sha256(
            b"LION/MOON-RUNNER-ATTESTED-OPERATION-RECEIPT/1\0"
            + json.dumps(
                self.payload(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        if self.receipt_digest and self.receipt_digest != expected:
            raise RunnerAttestationContractError("receipt digest mismatch")
        return self

    def sealed(self) -> "RunnerAttestedOperationReceipt":
        self.validate()
        payload = self.payload()
        digest = sha256(
            b"LION/MOON-RUNNER-ATTESTED-OPERATION-RECEIPT/1\0"
            + json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        return RunnerAttestedOperationReceipt(
            **payload,
            receipt_digest=digest,
        ).validate()


@dataclass(frozen=True)
class RunnerAttestedBridgeSpec:
    revision: str
    workflow_path: str
    operations: Tuple[str, ...]
    runner_name: str
    runner_agent_id: int
    os_user: str
    uid: int
    hostname: str
    machine_id: str
    control_issue: int
    permissions: Tuple[str, ...]
    workflow_dispatch_only: bool
    independent_post_run_verify: bool
    require_run_head_sha_exact: bool
    require_job_runner_name_exact: bool
    require_job_runner_id_if_exposed: bool
    require_job_terminal: bool
    require_receipt_identity_match: bool
    generic_shell: bool
    arbitrary_command: bool
    arbitrary_path: bool
    arbitrary_module: bool
    live_execution: bool
    state: str

    def validate(self) -> "RunnerAttestedBridgeSpec":
        _sha40(self.revision, "revision")
        if self.workflow_path != WORKFLOW_PATH or self.operations != OPERATIONS:
            raise RunnerAttestationContractError("bridge workflow/operations invalid")
        if (
            self.runner_name,
            self.runner_agent_id,
            self.os_user,
            self.uid,
            self.hostname,
            self.machine_id,
            self.control_issue,
        ) != (RUNNER, AGENT, OS_USER, UID, HOST, MACHINE, CONTROL_ISSUE):
            raise RunnerAttestationContractError("bridge identity invalid")
        if self.permissions != ("contents:read",):
            raise RunnerAttestationContractError("bridge permissions invalid")
        if not all(
            (
                self.workflow_dispatch_only,
                self.independent_post_run_verify,
                self.require_run_head_sha_exact,
                self.require_job_runner_name_exact,
                self.require_job_runner_id_if_exposed,
                self.require_job_terminal,
                self.require_receipt_identity_match,
            )
        ):
            raise RunnerAttestationContractError("bridge verification invariant invalid")
        if any(
            (
                self.generic_shell,
                self.arbitrary_command,
                self.arbitrary_path,
                self.arbitrary_module,
                self.live_execution,
            )
        ):
            raise RunnerAttestationContractError("bridge safety invariant invalid")
        if self.state != "CANDIDATE_UNATTACHED":
            raise RunnerAttestationContractError("bridge state invalid")
        return self

    def digest(self) -> str:
        self.validate()
        return _digest(b"LION/MOON-RUNNER-ATTESTED-BRIDGE-SPEC/1", self)

"""Contracts for bounded GitHub Actions dispatch and run observation.

Comments and receipts are evidence only. They never mint LION authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Mapping

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_WORKFLOW = re.compile(r"^[A-Za-z0-9._-]+\.ya?ml$")
_REF = re.compile(r"^[A-Za-z0-9._/-]{1,128}$")
_TARGET = re.compile(r"^(architecture|security|runtime)$")


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: object) -> str:
    return sha256(canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class DispatchPolicy:
    control_issue: int
    allowed_workflows: tuple[str, ...]
    allowed_refs: tuple[str, ...]
    allowed_inputs: tuple[tuple[str, tuple[str, ...]], ...] = ()
    trusted_permissions: tuple[str, ...] = ("admin", "maintain", "write")

    def validate(self) -> "DispatchPolicy":
        if self.control_issue <= 0:
            raise ValueError("control issue must be positive")
        if not self.allowed_workflows or any(not _WORKFLOW.fullmatch(v) for v in self.allowed_workflows):
            raise ValueError("invalid workflow allowlist")
        if not self.allowed_refs or any(not _REF.fullmatch(v) or ".." in v for v in self.allowed_refs):
            raise ValueError("invalid ref allowlist")
        if len(set(self.allowed_workflows)) != len(self.allowed_workflows):
            raise ValueError("duplicate workflow allowlist entry")
        if len(set(self.allowed_refs)) != len(self.allowed_refs):
            raise ValueError("duplicate ref allowlist entry")
        workflows = [workflow for workflow, _ in self.allowed_inputs]
        if len(set(workflows)) != len(workflows) or any(
            workflow not in self.allowed_workflows for workflow in workflows
        ):
            raise ValueError("invalid workflow input policy")
        for _, keys in self.allowed_inputs:
            if len(set(keys)) != len(keys) or any(not isinstance(key, str) or not key for key in keys):
                raise ValueError("invalid workflow input key policy")
        return self

    def input_keys_for(self, workflow: str) -> tuple[str, ...]:
        return dict(self.allowed_inputs).get(workflow, ())


@dataclass(frozen=True)
class DispatchRequest:
    schema_version: str
    repository: str
    issue_number: int
    comment_id: int
    actor: str
    request_id: str
    workflow: str
    ref: str
    expected_head: str
    canonical_inputs: str

    def validate(self, policy: DispatchPolicy) -> "DispatchRequest":
        policy.validate()
        if self.schema_version != "1":
            raise ValueError("unsupported dispatch schema")
        if self.issue_number != policy.control_issue:
            raise ValueError("wrong control issue")
        if self.comment_id <= 0:
            raise ValueError("comment id must be positive")
        if not _TOKEN.fullmatch(self.request_id) or not _TOKEN.fullmatch(self.actor):
            raise ValueError("invalid request or actor token")
        if self.workflow not in policy.allowed_workflows:
            raise ValueError("workflow not allowlisted")
        if self.ref not in policy.allowed_refs or ".." in self.ref:
            raise ValueError("ref not allowlisted")
        if not _HEX40.fullmatch(self.expected_head):
            raise ValueError("expected head must be lowercase 40-hex")
        try:
            inputs = json.loads(self.canonical_inputs)
        except json.JSONDecodeError as exc:
            raise ValueError("inputs must be valid JSON") from exc
        if not isinstance(inputs, dict):
            raise ValueError("inputs must be an object")
        if canonical_json(inputs).decode("utf-8") != self.canonical_inputs:
            raise ValueError("inputs must be canonical JSON")
        allowed = set(policy.input_keys_for(self.workflow))
        if any(not isinstance(k, str) for k in inputs):
            raise ValueError("workflow input keys must be strings")
        if set(inputs) != allowed:
            raise ValueError("workflow input key set mismatch")
        return self

    def inputs(self) -> Mapping[str, object]:
        return json.loads(self.canonical_inputs)

    def payload_digest(self) -> str:
        return digest({
            "schema_version": self.schema_version,
            "repository": self.repository,
            "issue_number": self.issue_number,
            "comment_id": self.comment_id,
            "actor": self.actor,
            "request_id": self.request_id,
            "workflow": self.workflow,
            "ref": self.ref,
            "expected_head": self.expected_head,
            "inputs": json.loads(self.canonical_inputs),
        })

    def replay_key(self) -> str:
        return digest({
            "repository": self.repository,
            "control_issue": self.issue_number,
            "comment_id": self.comment_id,
            "request_id": self.request_id,
            "workflow": self.workflow,
            "ref": self.ref,
            "expected_head": self.expected_head,
            "inputs_digest": sha256(self.canonical_inputs.encode("utf-8")).hexdigest(),
        })


@dataclass(frozen=True)
class DispatchReceipt:
    schema_version: str
    request_id: str
    control_comment_id: int
    actor: str
    permission: str
    workflow: str
    ref: str
    expected_head: str
    canonical_inputs_digest: str
    accepted_at: str
    replay_key: str
    bridge_implementation_digest: str
    trust_decision: str
    github_api_result: str

    def validate(self) -> "DispatchReceipt":
        if self.schema_version != "1.0.0":
            raise ValueError("unsupported receipt schema")
        if self.trust_decision != "ALLOW" or self.github_api_result != "ACCEPTED_204":
            raise ValueError("receipt is not an accepted dispatch")
        if self.control_comment_id <= 0:
            raise ValueError("receipt control comment invalid")
        if not _HEX40.fullmatch(self.expected_head):
            raise ValueError("receipt head invalid")
        for value in (self.canonical_inputs_digest, self.replay_key, self.bridge_implementation_digest):
            if not _HEX64.fullmatch(value):
                raise ValueError("receipt digest invalid")
        return self


@dataclass(frozen=True)
class ObservationRequest:
    schema_version: str
    repository: str
    issue_number: int
    comment_id: int
    actor: str
    request_id: str

    def validate(self, policy: DispatchPolicy) -> "ObservationRequest":
        policy.validate()
        if self.schema_version != "1":
            raise ValueError("unsupported observation schema")
        if self.issue_number != policy.control_issue:
            raise ValueError("wrong control issue")
        if self.comment_id <= 0:
            raise ValueError("comment id must be positive")
        if not _TOKEN.fullmatch(self.request_id) or not _TOKEN.fullmatch(self.actor):
            raise ValueError("invalid request or actor token")
        return self


@dataclass(frozen=True)
class RunObservationReceipt:
    """F009-specific observation receipt. Its semantics are intentionally unchanged."""
    schema_version: str
    request_id: str
    observation_comment_id: int
    actor: str
    permission: str
    workflow: str
    ref: str
    expected_head: str
    dispatch_accepted_at: str
    run_id: int
    run_attempt: int
    event: str
    status: str
    conclusion: str
    artifact_id: int
    artifact_name: str
    artifact_digest: str
    artifact_size: int
    proof_manifest_digest: str
    positive_reconciliation: str
    bridge_implementation_digest: str
    trust_decision: str
    observation_result: str

    def validate(self) -> "RunObservationReceipt":
        if self.schema_version != "1.0.0":
            raise ValueError("unsupported observation receipt schema")
        if self.trust_decision != "ALLOW" or self.observation_result != "OBSERVED_VERIFIED":
            raise ValueError("observation receipt is not verified")
        if not _HEX40.fullmatch(self.expected_head):
            raise ValueError("observation head invalid")
        if self.run_id <= 0 or self.run_attempt <= 0 or self.artifact_id <= 0 or self.artifact_size <= 0:
            raise ValueError("observation identifiers invalid")
        if self.event != "workflow_dispatch" or self.status != "completed" or self.conclusion != "success":
            raise ValueError("run is not successful workflow_dispatch")
        if not self.artifact_digest.startswith("sha256:") or not _HEX64.fullmatch(
            self.artifact_digest.removeprefix("sha256:")
        ):
            raise ValueError("artifact digest invalid")
        if not _HEX64.fullmatch(self.proof_manifest_digest):
            raise ValueError("proof manifest digest invalid")
        if self.positive_reconciliation != "MATCHED":
            raise ValueError("positive reconciliation is not MATCHED")
        if not _HEX64.fullmatch(self.bridge_implementation_digest):
            raise ValueError("bridge implementation digest invalid")
        return self


@dataclass(frozen=True)
class GroupChannelRunObservationReceipt:
    """Dedicated evidence-only observation receipt for lion-group-channel.yml."""
    schema_version: str
    request_id: str
    observation_comment_id: int
    control_comment_id: int
    actor: str
    permission: str
    workflow: str
    ref: str
    expected_head: str
    dispatch_accepted_at: str
    run_id: int
    run_attempt: int
    event: str
    status: str
    conclusion: str
    run_actor: str
    triggering_actor: str
    artifact_id: int
    artifact_name: str
    artifact_digest: str
    artifact_size: int
    message_id: str
    target: str
    envelope_digest: str
    payload_digest: str
    group_channel_receipt_digest: str
    emitted_at: str
    state: str
    authority_effect: bool
    repository_effect: bool
    bridge_implementation_digest: str
    trust_decision: str
    observation_result: str

    def validate(self) -> "GroupChannelRunObservationReceipt":
        if self.schema_version != "1.0.0":
            raise ValueError("unsupported group observation receipt schema")
        if self.workflow != "lion-group-channel.yml":
            raise ValueError("group observation workflow invalid")
        if not _HEX40.fullmatch(self.expected_head):
            raise ValueError("group observation head invalid")
        if not _TOKEN.fullmatch(self.request_id) or not _TOKEN.fullmatch(self.actor):
            raise ValueError("group observation request identity invalid")
        if not _TOKEN.fullmatch(self.message_id) or _TARGET.fullmatch(self.target) is None:
            raise ValueError("group observation routing invalid")
        if self.observation_comment_id <= 0 or self.control_comment_id <= 0:
            raise ValueError("group observation comment binding invalid")
        if self.run_id <= 0 or self.run_attempt <= 0 or self.artifact_id <= 0 or self.artifact_size <= 0:
            raise ValueError("group observation identifiers invalid")
        if self.event != "workflow_dispatch" or self.status != "completed" or self.conclusion != "success":
            raise ValueError("group run is not successful workflow_dispatch")
        if not self.run_actor or not self.triggering_actor:
            raise ValueError("group run actor binding incomplete")
        if not self.artifact_digest.startswith("sha256:") or not _HEX64.fullmatch(
            self.artifact_digest.removeprefix("sha256:")
        ):
            raise ValueError("group artifact digest invalid")
        for value in (
            self.envelope_digest,
            self.payload_digest,
            self.group_channel_receipt_digest,
            self.bridge_implementation_digest,
        ):
            if not _HEX64.fullmatch(value):
                raise ValueError("group observation digest invalid")
        if self.state != "EMITTED_EVIDENCE_ONLY":
            raise ValueError("group observation is not evidence-only")
        if self.authority_effect is not False or self.repository_effect is not False:
            raise ValueError("group observation cannot report an effect")
        if self.trust_decision != "ALLOW" or self.observation_result != "OBSERVED_VERIFIED":
            raise ValueError("group observation is not verified")
        return self


@dataclass(frozen=True)
class CodePerceptionRunObservationReceipt:
    """Evidence-only observation of the repository-native code-perception observer."""
    schema_version: str
    request_id: str
    observation_comment_id: int
    control_comment_id: int
    actor: str
    permission: str
    workflow: str
    ref: str
    expected_head: str
    dispatch_accepted_at: str
    observer_run_id: int
    observer_run_attempt: int
    observer_status: str
    observer_conclusion: str
    target_workflow_name: str
    target_workflow_id: int
    target_workflow_path: str
    target_event: str
    target_branch: str
    target_head_sha: str
    target_tree_sha: str
    target_run_id: int
    target_job_id: int
    projection_digest: str
    tree_semantic_digest: str
    file_count: int
    symbol_count: int
    edge_count: int
    authority_effect: bool
    repository_effect: bool
    bridge_implementation_digest: str
    trust_decision: str
    observation_result: str

    def validate(self) -> "CodePerceptionRunObservationReceipt":
        if self.schema_version != "1.0.0":
            raise ValueError("unsupported code-perception observation receipt schema")
        if self.workflow != "lion-code-perception-observation.yml" or self.ref != "master":
            raise ValueError("code-perception observer workflow binding invalid")
        if not _HEX40.fullmatch(self.expected_head):
            raise ValueError("code-perception observer head invalid")
        if not _TOKEN.fullmatch(self.request_id) or not _TOKEN.fullmatch(self.actor):
            raise ValueError("code-perception observation identity invalid")
        if self.observation_comment_id <= 0 or self.control_comment_id <= 0:
            raise ValueError("code-perception observation comment binding invalid")
        if self.observer_run_id <= 0 or self.observer_run_attempt <= 0:
            raise ValueError("code-perception observer run identity invalid")
        if self.observer_status != "completed" or self.observer_conclusion != "success":
            raise ValueError("code-perception observer run is not successful")
        if self.target_workflow_name != "Cyber-Lion Core":
            raise ValueError("code-perception target workflow name invalid")
        if self.target_workflow_id != 337046823:
            raise ValueError("code-perception target workflow id invalid")
        if self.target_workflow_path != ".github/workflows/cyber-lion-contracts.yml":
            raise ValueError("code-perception target workflow path invalid")
        if self.target_event != "push" or self.target_branch != "master":
            raise ValueError("code-perception target event or branch invalid")
        if not _HEX40.fullmatch(self.target_head_sha) or not _HEX40.fullmatch(self.target_tree_sha):
            raise ValueError("code-perception target git identity invalid")
        if self.target_run_id <= 0 or self.target_job_id <= 0:
            raise ValueError("code-perception target run identity invalid")
        if not _HEX64.fullmatch(self.projection_digest) or not _HEX64.fullmatch(self.tree_semantic_digest):
            raise ValueError("code-perception projection digest invalid")
        if self.file_count <= 0 or self.symbol_count <= 0 or self.edge_count <= 0:
            raise ValueError("code-perception projection counts invalid")
        if self.authority_effect is not False or self.repository_effect is not False:
            raise ValueError("code-perception observation cannot report an effect")
        if not _HEX64.fullmatch(self.bridge_implementation_digest):
            raise ValueError("code-perception bridge implementation digest invalid")
        if self.trust_decision != "ALLOW" or self.observation_result != "OBSERVED_VERIFIED":
            raise ValueError("code-perception observation is not verified")
        return self

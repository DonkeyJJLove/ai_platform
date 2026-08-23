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
        if any(not isinstance(k, str) or k not in allowed for k in inputs):
            raise ValueError("unknown workflow input key")
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
        if not self.artifact_digest.startswith("sha256:") or not _HEX64.fullmatch(self.artifact_digest.removeprefix("sha256:")):
            raise ValueError("artifact digest invalid")
        if not _HEX64.fullmatch(self.proof_manifest_digest):
            raise ValueError("proof manifest digest invalid")
        if self.positive_reconciliation != "MATCHED":
            raise ValueError("positive reconciliation is not MATCHED")
        if not _HEX64.fullmatch(self.bridge_implementation_digest):
            raise ValueError("bridge implementation digest invalid")
        return self

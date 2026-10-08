"""Prepare one cooperative WRITE runtime context from existing canonical evidence.

R6.20 is a composition adapter, not a new authority, PDP, provisioning, scheduler
or execution owner.  It binds one canonical HELD cooperative assignment to the
existing Action -> PDP -> RuntimeAdmission path and to already-existing sandbox,
dispatch and provisioning evidence.

The only stateful operation reachable here is RuntimeAdmissionEngine's existing
replay/admission boundary.  This module does not claim/release assignments,
publish worker/provider state, execute RuntimeExecutionEngine or write artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from cyber_lion.contracts.action_proposal_context import ExplicitActionProposalContext
from cyber_lion.contracts.action_runtime_binding import (
    RuntimeBindingCurrentness,
    bind_allowed_action_to_runtime_inputs,
)
from cyber_lion.contracts.executor_provisioning import (
    ExecutorProvisioningRequest,
    ProviderTrustBinding,
    ProvisionedExecutor,
)
from cyber_lion.contracts.executor_sandbox import (
    ExecutionSandboxPolicy,
    FleetDispatchBinding,
    ProvisioningBinding,
    SandboxRuntimeBinding,
)
from cyber_lion.contracts.runtime_enforcement import RuntimeAdmission
from cyber_lion.contracts.runtime_execution import RuntimeExecutionRequest
from cyber_lion.enterprise.control_plane import ActionProposal
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority
from cyber_lion.enterprise.policy_gate import PDPResult
from cyber_lion.enterprise.runtime_enforcement import RuntimeAdmissionEngine
from cyber_lion.enterprise.cooperative_runtime_composition import CooperativeRuntimeContext
from cyber_lion.enterprise.cooperative_runtime_writer import CooperativeExecutionBinding
from cyber_lion.mission_control.cooperative_artifacts import (
    WRITE_KIND,
    artifact_path,
    validate_write_payload,
)
from cyber_lion.mission_control.cooperative_production import CAPABILITY_PRODUCTION
from tools.lion_cooperative_worker_adapter import assignment_input

_PREPARATION_DOMAIN = b"LION/COOPERATIVE-RUNTIME-PREPARATION/1\0"
_FORBIDDEN_METHODS = frozenset({
    "claim", "release", "execute", "write", "deploy", "schedule", "dispatch",
})


class CooperativeRuntimePreparationError(ValueError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CooperativeRuntimePreparationError(reason)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _direct_root(value: str | Path) -> Path:
    root = Path(value)
    _require(root.is_absolute() and root.is_dir() and not root.is_symlink(), "artifact root")
    resolved = root.resolve(strict=True)
    _require(root == resolved, "artifact root symlink indirection")
    return resolved


def _assignment_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    _require(isinstance(value, Mapping), "assignment mapping required")
    row = dict(value)
    for name in (
        "assignment_id", "mission_id", "material_drone_id", "logical_drone_id",
        "lease_generation", "state", "input_digest",
    ):
        _require(name in row, "assignment field missing:" + name)
    _require(row["state"] == "HELD", "runtime preparation requires HELD assignment")
    _require(
        type(row["lease_generation"]) is int and row["lease_generation"] >= 1,
        "assignment generation",
    )
    return row


def _validate_provisioning_binding(
    request: ExecutorProvisioningRequest,
    provisioned: ProvisionedExecutor,
    binding: ProvisioningBinding,
) -> None:
    request.validate()
    provisioned.validate()
    binding.validate()
    _require(binding.provisioning_request_digest == request.digest(), "provisioning request binding")
    _require(binding.provisioned_executor_digest == provisioned.digest(), "provisioned executor binding")
    expected = (
        provisioned.mission_id,
        provisioned.drone_id,
        provisioned.executor_id,
        provisioned.repository,
        provisioned.baseline_sha,
        provisioned.baseline_tree_sha,
        provisioned.branch,
        provisioned.read_scope,
        provisioned.write_scope,
        provisioned.runtime_instance_id,
        provisioned.sandbox_id,
        provisioned.workspace_id,
        provisioned.runtime_attestation_digest,
    )
    actual = (
        binding.mission_id,
        binding.drone_id,
        binding.executor_id,
        binding.repository,
        binding.baseline_sha,
        binding.baseline_tree_sha,
        binding.branch,
        binding.read_scope,
        binding.write_scope,
        binding.runtime_instance_id,
        binding.sandbox_id,
        binding.workspace_id,
        binding.runtime_attestation_digest,
    )
    _require(actual == expected, "provisioning binding/provisioned executor substitution")


@dataclass(frozen=True)
class CooperativeRuntimePreparationEvidence:
    proposal: ActionProposal
    proposal_context: ExplicitActionProposalContext
    pdp_result: PDPResult
    currentness: RuntimeBindingCurrentness
    admitted_authority: LiveAdmittedAuthority
    provisioning_request: ExecutorProvisioningRequest
    provider_trust: ProviderTrustBinding
    provisioned_executor: ProvisionedExecutor
    sandbox_runtime: SandboxRuntimeBinding
    dispatch: FleetDispatchBinding
    provisioning: ProvisioningBinding
    sandbox_policy: ExecutionSandboxPolicy

    def validate(self) -> "CooperativeRuntimePreparationEvidence":
        exact = (
            (self.proposal, ActionProposal),
            (self.proposal_context, ExplicitActionProposalContext),
            (self.pdp_result, PDPResult),
            (self.currentness, RuntimeBindingCurrentness),
            (self.admitted_authority, LiveAdmittedAuthority),
            (self.provisioning_request, ExecutorProvisioningRequest),
            (self.provider_trust, ProviderTrustBinding),
            (self.provisioned_executor, ProvisionedExecutor),
            (self.sandbox_runtime, SandboxRuntimeBinding),
            (self.dispatch, FleetDispatchBinding),
            (self.provisioning, ProvisioningBinding),
            (self.sandbox_policy, ExecutionSandboxPolicy),
        )
        for value, cls in exact:
            _require(type(value) is cls, "exact preparation evidence type required:" + cls.__name__)
        self.proposal.validate()
        self.proposal_context.validate()
        self.pdp_result.requested.validate()
        self.pdp_result.applied.validate()
        self.pdp_result.receipt.validate()
        self.currentness.validate()
        self.admitted_authority.validate()
        self.provisioning_request.validate()
        self.provider_trust.validate()
        self.provisioned_executor.validate_for(self.provisioning_request, self.provider_trust)
        self.sandbox_runtime.validate()
        self.dispatch.validate()
        _validate_provisioning_binding(
            self.provisioning_request, self.provisioned_executor, self.provisioning
        )
        self.sandbox_policy.validate_bindings(self.dispatch, self.provisioning)
        _require(
            self.sandbox_policy.runtime_binding_digest == self.sandbox_runtime.digest(),
            "sandbox runtime binding substitution",
        )
        return self


def _preflight_preparation(
    *,
    assignment: Mapping[str, Any],
    artifact_root: str | Path,
    evidence: CooperativeRuntimePreparationEvidence,
) -> None:
    """Reject all caller-visible substitution before consuming admission replay."""
    _require(type(evidence) is CooperativeRuntimePreparationEvidence, "exact preparation evidence required")
    evidence.validate()
    row = _assignment_mapping(assignment)
    root = _direct_root(artifact_root)
    inp = assignment_input(row)
    _require(inp.get("kind") == WRITE_KIND, "cooperative WRITE assignment required")
    _require(inp.get("capability") == CAPABILITY_PRODUCTION, "cooperative production capability required")
    _require(inp.get("mission_id") == row["mission_id"], "assignment/input mission mismatch")
    _require(inp.get("generation") == row["lease_generation"], "assignment/input generation mismatch")
    derived_payload = {**inp, "assignment_id": row["assignment_id"]}
    metadata, _ = validate_write_payload(derived_payload, row["material_drone_id"])
    resource = artifact_path(
        root,
        mission_id=metadata["mission_id"],
        generation=metadata["generation"],
        artifact_name=metadata["artifact_name"],
    ).relative_to(root).as_posix()
    proposal = evidence.proposal
    _require(
        (
            proposal.mission_id,
            proposal.capability,
            proposal.requested_authority,
            proposal.action_class,
            proposal.target,
            proposal.payload_digest,
        )
        == (
            row["mission_id"],
            inp["capability"],
            "local_write",
            "WRITE_FILE",
            resource,
            metadata["artifact_sha256"],
        ),
        "proposal/cooperative assignment substitution",
    )
    _require(evidence.admitted_authority.mission_id == row["mission_id"], "authority mission substitution")
    provisioned = evidence.provisioned_executor
    dispatch = evidence.dispatch
    provisioning = evidence.provisioning
    policy = evidence.sandbox_policy
    runtime = evidence.sandbox_runtime
    _require(provisioned.mission_id == row["mission_id"], "provisioned mission substitution")
    _require(dispatch.mission_id == row["mission_id"], "dispatch mission substitution")
    _require(dispatch.generation == row["lease_generation"], "dispatch generation substitution")
    _require(policy.mission_id == row["mission_id"], "sandbox policy mission substitution")
    _require(policy.generation == row["lease_generation"], "sandbox policy generation substitution")
    _require(policy.write_scope == (resource,), "sandbox policy must bind one artifact resource")
    _require(provisioned.write_scope == (resource,), "provisioned executor write scope substitution")
    _require(provisioning.write_scope == (resource,), "provisioning write scope substitution")
    _require(dispatch.write_scope == (resource,), "dispatch write scope substitution")
    _require(
        (runtime.sandbox_id, runtime.workspace_id)
        == (provisioned.sandbox_id, provisioned.workspace_id),
        "sandbox runtime/provisioned executor substitution",
    )


def validate_cooperative_runtime_preparation_inputs(
    *,
    assignment: Mapping[str, Any],
    artifact_root: str | Path,
    evidence: CooperativeRuntimePreparationEvidence,
) -> None:
    """Validate all pure preparation bindings without consuming admission replay."""
    _preflight_preparation(
        assignment=assignment,
        artifact_root=artifact_root,
        evidence=evidence,
    )


def _compose_context_from_admission(
    *,
    assignment: Mapping[str, Any],
    artifact_root: str | Path,
    evidence: CooperativeRuntimePreparationEvidence,
    admission: RuntimeAdmission,
) -> CooperativeRuntimeContext:
    """Compose a cooperative context around one already-sealed admission.

    The caller is responsible for obtaining the admission from the canonical
    admission engine or from a trusted durable RuntimeAdmission source.
    """
    _require(type(evidence) is CooperativeRuntimePreparationEvidence, "exact preparation evidence required")
    evidence.validate()
    _require(type(admission) is RuntimeAdmission, "exact RuntimeAdmission required")
    admission.validate()

    row = _assignment_mapping(assignment)
    root = _direct_root(artifact_root)
    inp = assignment_input(row)
    _require(inp.get("kind") == WRITE_KIND, "cooperative WRITE assignment required")
    _require(inp.get("capability") == CAPABILITY_PRODUCTION, "cooperative production capability required")
    _require(inp.get("mission_id") == row["mission_id"], "assignment/input mission mismatch")
    _require(inp.get("generation") == row["lease_generation"], "assignment/input generation mismatch")

    derived_payload = {**inp, "assignment_id": row["assignment_id"]}
    metadata, data = validate_write_payload(derived_payload, row["material_drone_id"])
    resource = artifact_path(
        root,
        mission_id=metadata["mission_id"],
        generation=metadata["generation"],
        artifact_name=metadata["artifact_name"],
    ).relative_to(root).as_posix()

    proposal = evidence.proposal
    expected_proposal = (
        row["mission_id"],
        inp["capability"],
        "local_write",
        "WRITE_FILE",
        resource,
        metadata["artifact_sha256"],
    )
    actual_proposal = (
        proposal.mission_id,
        proposal.capability,
        proposal.requested_authority,
        proposal.action_class,
        proposal.target,
        proposal.payload_digest,
    )
    _require(actual_proposal == expected_proposal, "proposal/cooperative assignment substitution")
    _require(evidence.admitted_authority.mission_id == row["mission_id"], "authority mission substitution")

    provisioned = evidence.provisioned_executor
    dispatch = evidence.dispatch
    provisioning = evidence.provisioning
    policy = evidence.sandbox_policy
    runtime = evidence.sandbox_runtime

    _require(provisioned.mission_id == row["mission_id"], "provisioned mission substitution")
    _require(dispatch.mission_id == row["mission_id"], "dispatch mission substitution")
    _require(dispatch.generation == row["lease_generation"], "dispatch generation substitution")
    _require(policy.mission_id == row["mission_id"], "sandbox policy mission substitution")
    _require(policy.generation == row["lease_generation"], "sandbox policy generation substitution")
    _require(policy.write_scope == (resource,), "sandbox policy must bind one artifact resource")
    _require(provisioned.write_scope == (resource,), "provisioned executor write scope substitution")
    _require(provisioning.write_scope == (resource,), "provisioning write scope substitution")
    _require(dispatch.write_scope == (resource,), "dispatch write scope substitution")
    _require(
        (runtime.sandbox_id, runtime.workspace_id)
        == (provisioned.sandbox_id, provisioned.workspace_id),
        "sandbox runtime/provisioned executor substitution",
    )

    try:
        effect, identity, canonical_pdp = bind_allowed_action_to_runtime_inputs(
            proposal,
            evidence.proposal_context,
            evidence.pdp_result,
            evidence.currentness,
            provisioned,
        )
    except Exception as exc:
        raise CooperativeRuntimePreparationError("action runtime binding denied") from exc

    gate = evidence.pdp_result.applied
    receipt = evidence.pdp_result.receipt
    authority = evidence.admitted_authority
    _require(
        (
            admission.request_id,
            admission.gate_event_id,
            admission.proposal_id,
            admission.gate_decision_digest,
        )
        == (
            gate.request_id,
            gate.gate_event_id,
            gate.proposal_id,
            gate.decision_digest,
        ),
        "admission/PDP coordinate mismatch",
    )
    _require(admission.requested_effect_digest == effect.digest(), "admission/effect digest mismatch")
    _require(admission.runtime_identity_digest == identity.digest(), "admission/runtime identity mismatch")
    _require(admission.provisioned_executor_digest == provisioned.digest(), "admission/provisioning digest mismatch")
    _require(admission.pdp_evidence_digest == canonical_pdp.evidence_digest, "admission/PDP evidence mismatch")
    _require(admission.live_authority_digest == authority.digest(), "admission/live authority mismatch")
    _require(admission.authority_lineage_digest == authority.lineage_digest, "admission authority lineage mismatch")
    _require(admission.policy_binding == gate.policy_binding, "admission policy binding mismatch")
    _require(admission.effective_authority == proposal.requested_authority, "admission authority class mismatch")
    _require(admission.pdp_receipt_digest, "admission PDP receipt digest missing")
    _require(receipt.request_id == gate.request_id and receipt.gate_event_id == gate.gate_event_id,
             "PDP receipt coordinate mismatch")
    _require(effect.resource == resource and effect.payload_digest == metadata["artifact_sha256"],
             "runtime effect/artifact substitution")

    execution_seed = {
        "assignment_id": row["assignment_id"],
        "admission_digest": admission.admission_digest,
        "effect_digest": effect.digest(),
        "runtime_identity_digest": identity.digest(),
        "provisioned_executor_digest": provisioned.digest(),
        "dispatch_digest": dispatch.digest(),
        "input_digest": row["input_digest"],
    }
    execution_id = "cooperative-execution:" + sha256(
        _PREPARATION_DOMAIN + _canonical(execution_seed)
    ).hexdigest()

    request = RuntimeExecutionRequest(
        execution_id=execution_id,
        admission_digest=admission.admission_digest,
        requested_effect_digest=effect.digest(),
        runtime_identity_digest=identity.digest(),
        provisioned_executor_digest=provisioned.digest(),
        mission_id=row["mission_id"],
        executor_id=identity.execution_subject,
        runtime_instance_id=identity.runtime_instance_id,
        sandbox_id=identity.sandbox_id,
        workspace_id=identity.workspace_id,
        dispatch_id=dispatch.dispatch_id,
        fencing_token=dispatch.fencing_token,
        generation=int(row["lease_generation"]),
        action="WRITE_FILE",
        resource=resource,
        payload_digest=metadata["artifact_sha256"],
        payload_size=len(data),
        command=(),
    ).validate()

    binding = CooperativeExecutionBinding(
        assignment_id=row["assignment_id"],
        worker_id=row["material_drone_id"],
        input_digest=row["input_digest"],
        artifact_root=root,
        admission=admission,
        request=request,
        effect=effect,
        identity=identity,
    )
    return CooperativeRuntimeContext(
        execution=binding,
        policy=policy,
        runtime=runtime,
        dispatch=dispatch,
        provisioning=provisioning,
    ).validate()


def prepare_cooperative_runtime_context(
    *,
    assignment: Mapping[str, Any],
    artifact_root: str | Path,
    evidence: CooperativeRuntimePreparationEvidence,
    admission_engine: RuntimeAdmissionEngine,
    trusted_now: datetime,
) -> CooperativeRuntimeContext:
    """Issue one canonical admission, then compose a pre-effect context."""
    _preflight_preparation(
        assignment=assignment,
        artifact_root=artifact_root,
        evidence=evidence,
    )
    _require(type(admission_engine) is RuntimeAdmissionEngine, "exact RuntimeAdmissionEngine required")
    _require(isinstance(trusted_now, datetime) and trusted_now.tzinfo is not None, "trusted zoned time required")
    now = trusted_now.astimezone(timezone.utc)
    try:
        admission = admission_engine.admit_bound_action(
            proposal=evidence.proposal,
            context=evidence.proposal_context,
            pdp_result=evidence.pdp_result,
            currentness=evidence.currentness,
            admitted_authority=evidence.admitted_authority,
            provisioned_executor=evidence.provisioned_executor,
            provisioning_request=evidence.provisioning_request,
            provider_trust=evidence.provider_trust,
            trusted_now=now,
        )
    except Exception as exc:
        raise CooperativeRuntimePreparationError("canonical runtime admission denied") from exc
    return _compose_context_from_admission(
        assignment=assignment,
        artifact_root=artifact_root,
        evidence=evidence,
        admission=admission,
    )


def reconstruct_cooperative_runtime_context(
    *,
    assignment: Mapping[str, Any],
    artifact_root: str | Path,
    evidence: CooperativeRuntimePreparationEvidence,
    durable_admission: RuntimeAdmission,
) -> CooperativeRuntimeContext:
    """Reconstruct from an already-issued durable admission without replaying admission."""
    return _compose_context_from_admission(
        assignment=assignment,
        artifact_root=artifact_root,
        evidence=evidence,
        admission=durable_admission,
    )


class PreparedCooperativeContextSource:
    """Immutable in-process source for one already-prepared context.

    Construction performs validation only. Repeated reads never re-run PDP,
    admission or any materialization/effect path.
    """

    def __init__(self, context: CooperativeRuntimeContext):
        _require(type(context) is CooperativeRuntimeContext, "exact prepared context required")
        self._context = context.validate()
        self.assignment_id = self._context.execution.assignment_id
        self.authority_effect = "NONE"

    def __call__(self, assignment_id: str) -> CooperativeRuntimeContext:
        _require(assignment_id == self.assignment_id, "prepared context assignment substitution")
        current = self._context.validate()
        _require(
            current.execution.assignment_id == self.assignment_id,
            "prepared context identity drift",
        )
        return current


def assert_no_effect_surface() -> None:
    public = {name.lower() for name in globals() if not name.startswith("_")}
    if public & _FORBIDDEN_METHODS:
        raise CooperativeRuntimePreparationError("direct effect surface exposed")

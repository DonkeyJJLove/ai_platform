"""Non-effectful materializer from canonical PDP ALLOW to runtime admission inputs.

This module binds already-existing evidence. It does not mint authority, create an
admission, execute a provider, resolve secrets, or perform a runtime/host effect.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256

from cyber_lion.contracts.action_proposal_context import ExplicitActionProposalContext
from cyber_lion.contracts.executor_provisioning import ProvisionedExecutor
from cyber_lion.contracts.runtime_enforcement import (
    CanonicalPDPDecisionEvidence,
    PDPSourceTrustBinding,
    RequestedRuntimeEffect,
    RuntimeIdentityBinding,
    canonical_json,
)
from cyber_lion.enterprise.control_plane import ActionProposal
from cyber_lion.enterprise.policy_gate import PDPResult


class ActionRuntimeBindingError(ValueError):
    """Raised when an inert runtime binding would require substitution or stale evidence."""


def _aware(value: datetime, name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None:
        raise ActionRuntimeBindingError(f"{name} must be an exact timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _pdp_receipt_digest(result: PDPResult) -> str:
    result.receipt.validate()
    return sha256(
        b"LION/F009-PDP-RECEIPT/2\0" + canonical_json(asdict(result.receipt))
    ).hexdigest()


@dataclass(frozen=True)
class RuntimeBindingCurrentness:
    """Trusted time/source envelope used only to seal PDP evidence for admission."""

    pdp_source_trust: PDPSourceTrustBinding
    trusted_now: datetime
    issued_at: datetime
    expires_at: datetime

    def validate(self) -> "RuntimeBindingCurrentness":
        if type(self.pdp_source_trust) is not PDPSourceTrustBinding:
            raise ActionRuntimeBindingError("exact PDPSourceTrustBinding required")
        self.pdp_source_trust.validate()
        now = _aware(self.trusted_now, "trusted_now")
        issued = _aware(self.issued_at, "issued_at")
        expires = _aware(self.expires_at, "expires_at")
        if not issued <= now < expires:
            raise ActionRuntimeBindingError("PDP binding evidence is stale or not yet current")
        return self


def _validate_proposal_context(
    proposal: ActionProposal,
    context: ExplicitActionProposalContext,
) -> None:
    proposal.validate()
    context.validate()
    expected = (
        context.proposal_id,
        context.mission_id,
        context.swarm_id,
        context.proposer_agent_id,
        context.capability,
        context.requested_authority,
        context.action_class,
        context.target,
        context.consequential,
        context.evidence_refs,
        context.required_observability,
        context.verifier_agent_id,
        context.expected_lair_payload_digest,
    )
    actual = (
        proposal.proposal_id,
        proposal.mission_id,
        proposal.swarm_id,
        proposal.proposer_agent_id,
        proposal.capability,
        proposal.requested_authority,
        proposal.action_class,
        proposal.target,
        proposal.consequential,
        proposal.evidence_refs,
        proposal.required_observability,
        proposal.verifier_agent_id,
        proposal.payload_digest,
    )
    if actual != expected:
        raise ActionRuntimeBindingError("ActionProposal/explicit-context substitution denied")


def bind_allowed_action_to_runtime_inputs(
    proposal: ActionProposal,
    context: ExplicitActionProposalContext,
    pdp_result: PDPResult,
    currentness: RuntimeBindingCurrentness,
    trusted_provisioning: ProvisionedExecutor,
) -> tuple[RequestedRuntimeEffect, RuntimeIdentityBinding, CanonicalPDPDecisionEvidence]:
    """Materialize only inert runtime-input records from exact existing evidence."""

    if type(proposal) is not ActionProposal:
        raise ActionRuntimeBindingError("exact ActionProposal required")
    if type(context) is not ExplicitActionProposalContext:
        raise ActionRuntimeBindingError("exact ExplicitActionProposalContext required")
    if type(pdp_result) is not PDPResult:
        raise ActionRuntimeBindingError("exact PDPResult required")
    if type(currentness) is not RuntimeBindingCurrentness:
        raise ActionRuntimeBindingError("exact RuntimeBindingCurrentness required")
    if type(trusted_provisioning) is not ProvisionedExecutor:
        raise ActionRuntimeBindingError("exact trusted ProvisionedExecutor required")

    _validate_proposal_context(proposal, context)
    currentness.validate()
    trusted_provisioning.validate()
    pdp_result.requested.validate()
    pdp_result.applied.validate()
    pdp_result.receipt.validate()

    requested = pdp_result.requested
    gate = pdp_result.applied
    receipt = pdp_result.receipt
    if gate.decision != "ALLOW" or gate.effective_authority == "none":
        raise ActionRuntimeBindingError("runtime binding requires canonical PDP ALLOW")
    if gate.effective_authority != proposal.requested_authority:
        raise ActionRuntimeBindingError("PDP effective authority/proposal substitution denied")
    if trusted_provisioning.mission_id != proposal.mission_id:
        raise ActionRuntimeBindingError("provisioning mission/proposal substitution denied")

    expected_gate = (
        proposal.proposal_id,
        requested.request_id,
        requested.policy_binding,
        requested.authority_lineage_digest,
        requested.observability_state,
        requested.requested_authority,
    )
    actual_gate = (
        gate.proposal_id,
        gate.request_id,
        gate.policy_binding,
        gate.authority_lineage_digest,
        gate.observability_state,
        gate.effective_authority,
    )
    if actual_gate != expected_gate:
        raise ActionRuntimeBindingError("GateRequested/GateApplied binding mismatch")
    if requested.proposal_id != proposal.proposal_id:
        raise ActionRuntimeBindingError("GateRequested/proposal substitution denied")
    if (
        receipt.request_id,
        receipt.gate_event_id,
        receipt.request_digest,
        receipt.decision_digest,
    ) != (
        gate.request_id,
        gate.gate_event_id,
        requested.request_digest,
        gate.decision_digest,
    ):
        raise ActionRuntimeBindingError("PDP receipt does not bind exact request and decision")

    runtime_identity = RuntimeIdentityBinding(
        workload_identity=trusted_provisioning.drone_id,
        execution_subject=trusted_provisioning.executor_id,
        runtime_instance_id=trusted_provisioning.runtime_instance_id,
        sandbox_id=trusted_provisioning.sandbox_id,
        workspace_id=trusted_provisioning.workspace_id,
        runtime_attestation_digest=trusted_provisioning.runtime_attestation_digest,
        provisioned_executor_digest=trusted_provisioning.digest(),
    ).validate()

    effect_seed = (
        proposal.proposal_id
        + "\0"
        + gate.decision_digest
        + "\0"
        + runtime_identity.digest()
    ).encode("utf-8")
    effect = RequestedRuntimeEffect(
        effect_id="runtime-effect:" + sha256(effect_seed).hexdigest(),
        proposal_id=proposal.proposal_id,
        mission_id=proposal.mission_id,
        policy_binding=gate.policy_binding,
        authority_lineage_digest=gate.authority_lineage_digest,
        requested_authority=proposal.requested_authority,
        action_class=proposal.action_class,
        resource=proposal.target,
        payload_digest=proposal.payload_digest or "",
        observability_state=gate.observability_state,
        runtime_identity_digest=runtime_identity.digest(),
    ).validate()

    trust = currentness.pdp_source_trust
    evidence = CanonicalPDPDecisionEvidence(
        request_id=gate.request_id,
        gate_event_id=gate.gate_event_id,
        proposal_id=gate.proposal_id,
        gate_decision_digest=gate.decision_digest,
        pdp_receipt_digest=_pdp_receipt_digest(pdp_result),
        request_digest=receipt.request_digest,
        replay_key=receipt.replay_key,
        policy_binding=gate.policy_binding,
        authority_lineage_digest=gate.authority_lineage_digest,
        observability_state=gate.observability_state,
        source_id=trust.source_id,
        source_instance_id=trust.source_instance_id,
        source_implementation_digest=trust.source_implementation_digest,
        trust_anchor_id=trust.trust_anchor_id,
        trust_anchor_digest=trust.trust_anchor_digest,
        issued_at=_aware(currentness.issued_at, "issued_at").isoformat(),
        expires_at=_aware(currentness.expires_at, "expires_at").isoformat(),
    ).sealed()

    return effect, runtime_identity, evidence

"""Canonical downstream evidence binding for LPCL ACTION_REQUIRED outcomes.

This module is deliberately non-effectful.  It does not create authority, run a PDP,
perform runtime admission, execute an effect, observe the world, or reconcile an
effect.  It only verifies that a ProcessTransitionOutcome is bound to an already
materialized chain of existing canonical Action/runtime/reconciliation contracts.

The ProcessTransitionOutcome is therefore an evidence carrier, never self-attesting
proof of downstream success.
"""
from __future__ import annotations

from dataclasses import dataclass

from cyber_lion.contracts.action_ir import CanonicalActionIR
from cyber_lion.contracts.action_proposal_context import (
    ExplicitActionProposalContext,
    bind_lair_to_action_proposal,
)
from cyber_lion.contracts.process_action import ActionIntentCandidate, ProcessTransitionOutcome
from cyber_lion.contracts.runtime_currentness import EffectTimeCurrentnessEvidence
from cyber_lion.contracts.runtime_enforcement import (
    CanonicalPDPDecisionEvidence,
    RequestedRuntimeEffect,
    RuntimeAdmission,
    RuntimeIdentityBinding,
)
from cyber_lion.contracts.runtime_execution import RuntimeExecutionReceipt
from cyber_lion.contracts.runtime_reconciliation import (
    RuntimeEffectObservation,
    RuntimeReconciliationReceipt,
)
from cyber_lion.enterprise.control_plane import ActionProposal


class ProcessOutcomeEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalDownstreamEvidence:
    """Exact, typed downstream evidence required to close ACTION_REQUIRED + PASS.

    Every member is an existing canonical contract.  The bundle contributes no new
    authority semantics and contains no boolean "verified" escape hatch.  Validation
    succeeds only when the contracts form one exact causal/binding chain.
    """

    action_intent: ActionIntentCandidate
    action_ir: CanonicalActionIR
    proposal_context: ExplicitActionProposalContext
    proposal: ActionProposal
    pdp_evidence: CanonicalPDPDecisionEvidence
    runtime_identity: RuntimeIdentityBinding
    requested_effect: RequestedRuntimeEffect
    admission: RuntimeAdmission
    effect_currentness: EffectTimeCurrentnessEvidence
    execution_receipt: RuntimeExecutionReceipt
    effect_observation: RuntimeEffectObservation
    reconciliation: RuntimeReconciliationReceipt

    @staticmethod
    def _exact(value: object, expected: type, name: str) -> None:
        if type(value) is not expected:
            raise ProcessOutcomeEvidenceError(f"exact {name} required")

    def validate_for(
        self,
        *,
        outcome: ProcessTransitionOutcome,
        process_id: str,
        process_ir_digest: str,
        transition_id: str,
        mission_ref: str,
    ) -> "CanonicalDownstreamEvidence":
        self._exact(outcome, ProcessTransitionOutcome, "ProcessTransitionOutcome")
        self._exact(self.action_intent, ActionIntentCandidate, "ActionIntentCandidate")
        self._exact(self.action_ir, CanonicalActionIR, "CanonicalActionIR")
        self._exact(self.proposal_context, ExplicitActionProposalContext, "ExplicitActionProposalContext")
        self._exact(self.proposal, ActionProposal, "ActionProposal")
        self._exact(self.pdp_evidence, CanonicalPDPDecisionEvidence, "CanonicalPDPDecisionEvidence")
        self._exact(self.runtime_identity, RuntimeIdentityBinding, "RuntimeIdentityBinding")
        self._exact(self.requested_effect, RequestedRuntimeEffect, "RequestedRuntimeEffect")
        self._exact(self.admission, RuntimeAdmission, "RuntimeAdmission")
        self._exact(self.effect_currentness, EffectTimeCurrentnessEvidence, "EffectTimeCurrentnessEvidence")
        self._exact(self.execution_receipt, RuntimeExecutionReceipt, "RuntimeExecutionReceipt")
        self._exact(self.effect_observation, RuntimeEffectObservation, "RuntimeEffectObservation")
        self._exact(self.reconciliation, RuntimeReconciliationReceipt, "RuntimeReconciliationReceipt")

        try:
            outcome.validate()
            self.action_intent.validate()
            self.action_ir.validate()
            self.proposal_context.validate()
            self.proposal.validate()
            self.pdp_evidence.validate()
            self.runtime_identity.validate()
            self.requested_effect.validate()
            self.admission.validate()
            self.effect_currentness.validate()
            self.execution_receipt.validate()
            self.effect_observation.validate()
            self.reconciliation.validate()
        except Exception as exc:
            raise ProcessOutcomeEvidenceError("canonical downstream contract validation failed") from exc

        if not self.action_intent.action_intent_digest:
            raise ProcessOutcomeEvidenceError("unsealed ActionIntentCandidate denied")
        if self.action_intent.action_intent_digest != self.action_intent.compute_digest():
            raise ProcessOutcomeEvidenceError("ActionIntentCandidate digest mismatch")
        if (
            self.action_intent.process_id,
            self.action_intent.process_ir_digest,
            self.action_intent.transition_id,
            self.action_intent.mission_ref,
        ) != (process_id, process_ir_digest, transition_id, mission_ref):
            raise ProcessOutcomeEvidenceError("process-to-ActionIntent binding mismatch")

        action = self.action_ir.as_dict()
        if action["intent_ref"] != self.action_intent.action_intent_digest:
            raise ProcessOutcomeEvidenceError("Action IR does not bind selected ActionIntentCandidate")
        if action["mission_ref"] != mission_ref:
            raise ProcessOutcomeEvidenceError("Action IR mission binding mismatch")
        if action["authority_request"]["capability"] != self.action_intent.required_capability:
            raise ProcessOutcomeEvidenceError("Action IR capability binding mismatch")

        try:
            expected_proposal = bind_lair_to_action_proposal(self.action_ir, self.proposal_context)
        except Exception as exc:
            raise ProcessOutcomeEvidenceError("canonical ActionProposal binding failed") from exc
        if expected_proposal != self.proposal:
            raise ProcessOutcomeEvidenceError("ActionProposal substitution denied")
        if self.proposal_context.mission_id != mission_ref or self.proposal.mission_id != mission_ref:
            raise ProcessOutcomeEvidenceError("ActionProposal mission binding mismatch")
        if self.proposal.payload_digest != self.action_ir.payload_digest:
            raise ProcessOutcomeEvidenceError("ActionProposal payload is not bound to canonical Action IR")

        if outcome.action_ref != self.action_ir.payload_digest:
            raise ProcessOutcomeEvidenceError("outcome action_ref does not bind canonical Action IR")
        if outcome.proposal_digest != self.proposal_context.digest():
            raise ProcessOutcomeEvidenceError("outcome proposal_digest does not bind canonical proposal context")

        pdp = self.pdp_evidence
        admission = self.admission
        effect = self.requested_effect
        identity_digest = self.runtime_identity.digest()
        if (
            pdp.request_id,
            pdp.gate_event_id,
            pdp.proposal_id,
            pdp.gate_decision_digest,
            pdp.pdp_receipt_digest,
            pdp.policy_binding,
            pdp.authority_lineage_digest,
            pdp.replay_key,
        ) != (
            admission.request_id,
            admission.gate_event_id,
            admission.proposal_id,
            admission.gate_decision_digest,
            admission.pdp_receipt_digest,
            admission.policy_binding,
            admission.authority_lineage_digest,
            admission.replay_key,
        ):
            raise ProcessOutcomeEvidenceError("PDP evidence/admission binding mismatch")
        if admission.pdp_evidence_digest != pdp.evidence_digest:
            raise ProcessOutcomeEvidenceError("RuntimeAdmission does not bind canonical PDP evidence")
        if pdp.proposal_id != self.proposal.proposal_id:
            raise ProcessOutcomeEvidenceError("PDP evidence proposal substitution denied")

        if (
            effect.proposal_id,
            effect.mission_id,
            effect.requested_authority,
            effect.action_class,
            effect.resource,
            effect.payload_digest,
            effect.policy_binding,
            effect.authority_lineage_digest,
        ) != (
            self.proposal.proposal_id,
            self.proposal.mission_id,
            self.proposal.requested_authority,
            self.proposal.action_class,
            self.proposal.target,
            self.proposal.payload_digest,
            admission.policy_binding,
            admission.authority_lineage_digest,
        ):
            raise ProcessOutcomeEvidenceError("ActionProposal/requested-effect binding mismatch")
        if effect.runtime_identity_digest != identity_digest:
            raise ProcessOutcomeEvidenceError("RequestedRuntimeEffect runtime identity mismatch")
        if admission.requested_effect_digest != effect.digest():
            raise ProcessOutcomeEvidenceError("RuntimeAdmission requested-effect binding mismatch")
        if admission.runtime_identity_digest != identity_digest:
            raise ProcessOutcomeEvidenceError("RuntimeAdmission runtime identity mismatch")
        if admission.provisioned_executor_digest != self.runtime_identity.provisioned_executor_digest:
            raise ProcessOutcomeEvidenceError("RuntimeAdmission executor binding mismatch")
        if outcome.admission_ref != admission.admission_digest:
            raise ProcessOutcomeEvidenceError("outcome admission_ref does not bind RuntimeAdmission")

        currentness = self.effect_currentness
        if (
            currentness.admission_digest,
            currentness.requested_effect_digest,
            currentness.runtime_identity_digest,
            currentness.live_authority_digest,
            currentness.authority_lineage_digest,
            currentness.policy_binding,
            currentness.observability_state,
        ) != (
            admission.admission_digest,
            admission.requested_effect_digest,
            admission.runtime_identity_digest,
            admission.live_authority_digest,
            admission.authority_lineage_digest,
            admission.policy_binding,
            admission.observability_state,
        ):
            raise ProcessOutcomeEvidenceError("effect-time currentness/admission binding mismatch")

        receipt = self.execution_receipt
        if receipt.outcome != "SUCCEEDED" or receipt.effect_state != "OBSERVED":
            raise ProcessOutcomeEvidenceError("ACTION_REQUIRED PASS requires successful observed runtime execution")
        if (
            receipt.admission_digest,
            receipt.mission_id,
            receipt.runtime_instance_id,
            receipt.sandbox_id,
            receipt.workspace_id,
            receipt.action,
            receipt.resource,
            receipt.payload_digest,
        ) != (
            admission.admission_digest,
            self.proposal.mission_id,
            self.runtime_identity.runtime_instance_id,
            self.runtime_identity.sandbox_id,
            self.runtime_identity.workspace_id,
            effect.action_class,
            effect.resource,
            effect.payload_digest,
        ):
            raise ProcessOutcomeEvidenceError("runtime execution binding mismatch")
        if outcome.effect_ref != receipt.effect_digest:
            raise ProcessOutcomeEvidenceError("outcome effect_ref does not bind observed runtime effect")

        observation = self.effect_observation
        if observation.effect_state != "OBSERVED":
            raise ProcessOutcomeEvidenceError("ACTION_REQUIRED PASS requires independent observed effect")
        if (
            observation.execution_id,
            observation.admission_digest,
            observation.request_digest,
            observation.operation_digest,
            observation.action,
            observation.resource,
            observation.effect_digest,
            tuple(observation.observed_events),
            set(observation.side_effect_refs),
        ) != (
            receipt.execution_id,
            receipt.admission_digest,
            receipt.request_digest,
            receipt.operation_digest,
            receipt.action,
            receipt.resource,
            receipt.effect_digest,
            tuple(receipt.observed_events),
            set(receipt.side_effect_refs),
        ):
            raise ProcessOutcomeEvidenceError("independent observation/runtime receipt binding mismatch")
        if outcome.observation_ref != observation.observation_digest:
            raise ProcessOutcomeEvidenceError("outcome observation_ref does not bind independent observation")

        reconciliation = self.reconciliation
        if reconciliation.disposition != "MATCHED" or reconciliation.anomaly_codes:
            raise ProcessOutcomeEvidenceError("ACTION_REQUIRED PASS requires MATCHED anomaly-free reconciliation")
        if (
            reconciliation.runtime_execution_receipt_digest,
            reconciliation.effect_observation_digest,
            reconciliation.currentness_evidence_digest,
            reconciliation.execution_id,
            reconciliation.admission_digest,
            reconciliation.reconciled_effect_digest,
        ) != (
            receipt.receipt_digest,
            observation.observation_digest,
            currentness.evidence_digest,
            receipt.execution_id,
            admission.admission_digest,
            receipt.effect_digest,
        ):
            raise ProcessOutcomeEvidenceError("runtime reconciliation chain mismatch")
        if outcome.reconciliation_ref != reconciliation.reconciliation_digest:
            raise ProcessOutcomeEvidenceError("outcome reconciliation_ref does not bind canonical reconciliation")
        return self

"""Translate enterprise runtime records into Cyber-Lion EventEnvelope objects."""
from __future__ import annotations

from typing import Mapping

from cyber_lion.contracts.events import Authority, EventEnvelope, Provenance

from .control_plane import ActionProposal, ExecutionReceipt, GateDecision
from .models import AgentSpec


def proposal_event(
    proposal: ActionProposal,
    *,
    agent: AgentSpec,
    occurred_at: str,
    correlation_id: str,
    provenance_upstream: tuple[str, ...],
) -> EventEnvelope:
    proposal.validate()
    agent.validate()
    return EventEnvelope(
        schema_version="1.0.0",
        event_id=f"event:{proposal.proposal_id}:proposed",
        event_type="DecisionProposed",
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        entity={"entity_id": agent.agent_id, "entity_type": "agent", "version": agent.version},
        source={"component": "cyber_lion.enterprise.control_plane", "swarm_id": proposal.swarm_id},
        provenance=Provenance(
            epistemic_status="DERIVED",
            upstream=list(provenance_upstream),
            transformation_chain=["evidence→ActionProposal"],
            content_hash=proposal.payload_digest,
        ),
        authority=Authority(
            requested=proposal.requested_authority,
            effective="none",
            policy_ids=[],
            gate_event_id=None,
        ),
        epistemic_state="FORMALISED",
        payload={
            "proposal_id": proposal.proposal_id,
            "mission_id": proposal.mission_id,
            "swarm_id": proposal.swarm_id,
            "capability": proposal.capability,
            "action_class": proposal.action_class,
            "target": proposal.target,
            "consequential": proposal.consequential,
            "evidence_refs": list(proposal.evidence_refs),
            "required_observability": list(proposal.required_observability),
            "verifier_agent_id": proposal.verifier_agent_id,
        },
    ).validate()


def gate_event(
    decision: GateDecision,
    *,
    proposal_event_id: str,
    occurred_at: str,
    correlation_id: str,
    authority_entity_id: str = "cyber-lion:mand",
) -> EventEnvelope:
    decision.validate()
    return EventEnvelope(
        schema_version="1.0.0",
        event_id=decision.gate_event_id,
        event_type="GateApplied",
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        causation_id=proposal_event_id,
        entity={"entity_id": authority_entity_id, "entity_type": "authority-plane"},
        source={"component": "cyber_lion.enterprise.control_plane"},
        provenance=Provenance(
            epistemic_status="DERIVED",
            upstream=[proposal_event_id],
            transformation_chain=["ActionProposal→GateDecision"],
        ),
        authority=Authority(
            requested=decision.effective_authority,
            effective=decision.effective_authority if decision.decision == "ALLOW" else "none",
            policy_ids=list(decision.policy_ids),
            gate_event_id=decision.gate_event_id if decision.decision == "ALLOW" else None,
        ),
        epistemic_state="FORMALISED",
        payload={
            "proposal_id": decision.proposal_id,
            "decision": decision.decision,
            "rationale": decision.rationale,
            "verifier_agent_id": decision.verifier_agent_id,
        },
    ).validate()


def execution_event(
    receipt: ExecutionReceipt,
    *,
    proposal: ActionProposal,
    decision: GateDecision,
    occurred_at: str,
    correlation_id: str,
    policy_ids: tuple[str, ...],
) -> EventEnvelope:
    receipt.validate()
    proposal.validate()
    decision.validate()
    if receipt.proposal_id != proposal.proposal_id or receipt.gate_event_id != decision.gate_event_id:
        raise ValueError("receipt/proposal/gate causal binding mismatch")
    return EventEnvelope(
        schema_version="1.0.0",
        event_id=f"event:{receipt.receipt_id}:executed",
        event_type="ActionExecuted",
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        causation_id=decision.gate_event_id,
        entity={"entity_id": receipt.executor_agent_id, "entity_type": "agent"},
        source={"component": "cyber_lion.enterprise.execution"},
        provenance=Provenance(
            epistemic_status="DERIVED",
            upstream=[decision.gate_event_id, proposal.proposal_id],
            transformation_chain=["GateDecision→ExecutionReceipt"],
            content_hash=receipt.effect_digest,
        ),
        authority=Authority(
            requested=proposal.requested_authority,
            effective=decision.effective_authority,
            policy_ids=list(policy_ids),
            gate_event_id=decision.gate_event_id,
        ),
        epistemic_state="FORMALISED",
        payload={
            "proposal_id": receipt.proposal_id,
            "receipt_id": receipt.receipt_id,
            "outcome": receipt.outcome,
            "effect_digest": receipt.effect_digest,
            "observed_events": list(receipt.observed_events),
            "side_effect_refs": list(receipt.side_effect_refs),
            "consequential": proposal.consequential,
        },
    ).validate()

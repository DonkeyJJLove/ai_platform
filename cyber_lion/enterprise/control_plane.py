"""Deterministic execution control plane for Cyber-Lion enterprise swarms.

The control plane separates semantic proposals from runtime authority and effects:

    proposal (SEM) -> gate decision (MAND) -> execution receipt (INF)

It does not execute external tools. It validates whether a proposed consequential action
is admissible and produces typed records that can be emitted as Cyber-Lion events.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Tuple

from .models import AgentSpec, EnterpriseModelError, MissionSpec, SwarmSpec, authority_rank


@dataclass(frozen=True)
class ActionProposal:
    proposal_id: str
    mission_id: str
    swarm_id: str
    proposer_agent_id: str
    capability: str
    requested_authority: str
    action_class: str
    target: str
    consequential: bool = True
    evidence_refs: Tuple[str, ...] = ()
    required_observability: Tuple[str, ...] = ()
    verifier_agent_id: str | None = None
    payload_digest: str | None = None

    def validate(self) -> "ActionProposal":
        if not all((self.proposal_id, self.mission_id, self.swarm_id, self.proposer_agent_id)):
            raise EnterpriseModelError("proposal identity/mission/swarm/proposer are required")
        if not self.capability or not self.action_class or not self.target:
            raise EnterpriseModelError("proposal capability/action_class/target are required")
        authority_rank(self.requested_authority)
        if self.consequential and not self.evidence_refs:
            raise EnterpriseModelError("consequential proposal requires evidence_refs")
        if self.consequential and not self.required_observability:
            raise EnterpriseModelError("consequential proposal requires observability requirements")
        return self


@dataclass(frozen=True)
class GateDecision:
    gate_event_id: str
    proposal_id: str
    decision: str
    effective_authority: str
    policy_ids: Tuple[str, ...]
    rationale: str
    verifier_agent_id: str | None = None

    def validate(self) -> "GateDecision":
        if self.decision not in {"ALLOW", "DENY"}:
            raise EnterpriseModelError("gate decision must be ALLOW or DENY")
        if not self.gate_event_id or not self.proposal_id or not self.rationale:
            raise EnterpriseModelError("gate identity/proposal/rationale are required")
        authority_rank(self.effective_authority)
        if self.decision == "ALLOW" and not self.policy_ids:
            raise EnterpriseModelError("ALLOW requires policy_ids")
        if self.decision == "DENY" and self.effective_authority != "none":
            raise EnterpriseModelError("DENY must have effective_authority=none")
        return self


@dataclass(frozen=True)
class ExecutionReceipt:
    receipt_id: str
    proposal_id: str
    gate_event_id: str
    executor_agent_id: str
    outcome: str
    effect_digest: str
    observed_events: Tuple[str, ...]
    side_effect_refs: Tuple[str, ...] = ()

    def validate(self) -> "ExecutionReceipt":
        if not all((self.receipt_id, self.proposal_id, self.gate_event_id, self.executor_agent_id)):
            raise EnterpriseModelError("receipt identity/proposal/gate/executor are required")
        if self.outcome not in {"SUCCEEDED", "FAILED", "PARTIAL", "ABORTED"}:
            raise EnterpriseModelError("invalid execution outcome")
        if not self.effect_digest:
            raise EnterpriseModelError("execution receipt requires effect_digest")
        if not self.observed_events:
            raise EnterpriseModelError("execution receipt requires observed_events")
        return self


class ExecutionControlPlane:
    """Admit or deny action proposals using deterministic enterprise invariants."""

    def evaluate(
        self,
        *,
        proposal: ActionProposal,
        mission: MissionSpec,
        swarm: SwarmSpec,
        agents: Mapping[str, AgentSpec],
        policy_ids: Tuple[str, ...],
        observed_event_types: Tuple[str, ...],
        gate_event_id: str,
    ) -> GateDecision:
        proposal.validate()
        mission.validate()
        swarm.validate()

        if proposal.mission_id != mission.mission_id or proposal.swarm_id != swarm.swarm_id:
            return self._deny(proposal, gate_event_id, "proposal mission/swarm binding mismatch")
        if proposal.proposer_agent_id not in swarm.member_agent_ids:
            return self._deny(proposal, gate_event_id, "proposer is not a swarm member")

        proposer = agents.get(proposal.proposer_agent_id)
        if proposer is None:
            return self._deny(proposal, gate_event_id, "proposer AgentSpec unavailable")
        proposer.validate()

        if proposal.capability not in proposer.capabilities:
            return self._deny(proposal, gate_event_id, "proposer lacks requested capability")
        requested = authority_rank(proposal.requested_authority)
        if requested > authority_rank(proposer.authority_ceiling):
            return self._deny(proposal, gate_event_id, "proposal exceeds agent authority ceiling")
        if requested > authority_rank(mission.authority_ceiling):
            return self._deny(proposal, gate_event_id, "proposal exceeds mission authority ceiling")
        if requested > authority_rank(swarm.authority_ceiling):
            return self._deny(proposal, gate_event_id, "proposal exceeds swarm authority ceiling")

        missing_observability = set(proposal.required_observability) - set(observed_event_types)
        if missing_observability:
            return self._deny(
                proposal,
                gate_event_id,
                f"observability preconditions missing: {sorted(missing_observability)}",
            )

        verifier_required = (
            proposal.consequential
            and (
                mission.risk_class == "RED"
                or requested >= authority_rank("external_write")
                or mission.require_independent_verifier
            )
        )
        verifier_id = proposal.verifier_agent_id
        if verifier_required:
            if not verifier_id or verifier_id == proposal.proposer_agent_id:
                return self._deny(proposal, gate_event_id, "independent verifier required")
            if verifier_id not in swarm.verifier_agent_ids:
                return self._deny(proposal, gate_event_id, "verifier is not admitted by SwarmSpec")
            verifier = agents.get(verifier_id)
            if verifier is None or not verifier.validate().is_verifier:
                return self._deny(proposal, gate_event_id, "invalid verifier AgentSpec")

        if proposal.consequential and not policy_ids:
            return self._deny(proposal, gate_event_id, "consequential ALLOW requires policy_ids")

        return GateDecision(
            gate_event_id=gate_event_id,
            proposal_id=proposal.proposal_id,
            decision="ALLOW",
            effective_authority=proposal.requested_authority,
            policy_ids=tuple(policy_ids),
            rationale="all deterministic admission invariants satisfied",
            verifier_agent_id=verifier_id,
        ).validate()

    @staticmethod
    def issue_receipt(
        *,
        proposal: ActionProposal,
        decision: GateDecision,
        executor_agent_id: str,
        outcome: str,
        effect_digest: str,
        observed_events: Tuple[str, ...],
        side_effect_refs: Tuple[str, ...] = (),
    ) -> ExecutionReceipt:
        proposal.validate()
        decision.validate()
        if decision.proposal_id != proposal.proposal_id:
            raise EnterpriseModelError("gate decision does not bind to proposal")
        if decision.decision != "ALLOW":
            raise EnterpriseModelError("cannot issue execution receipt for denied proposal")
        return ExecutionReceipt(
            receipt_id=f"receipt:{proposal.proposal_id}",
            proposal_id=proposal.proposal_id,
            gate_event_id=decision.gate_event_id,
            executor_agent_id=executor_agent_id,
            outcome=outcome,
            effect_digest=effect_digest,
            observed_events=observed_events,
            side_effect_refs=side_effect_refs,
        ).validate()

    @staticmethod
    def _deny(proposal: ActionProposal, gate_event_id: str, rationale: str) -> GateDecision:
        return GateDecision(
            gate_event_id=gate_event_id,
            proposal_id=proposal.proposal_id,
            decision="DENY",
            effective_authority="none",
            policy_ids=(),
            rationale=rationale,
            verifier_agent_id=None,
        ).validate()

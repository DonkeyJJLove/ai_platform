"""Non-effectful handoff from a context-complete ActionProposal to the canonical PDP."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from cyber_lion.contracts.enterprise_graph import EnterpriseGraphProjection
from cyber_lion.contracts.policy_gate import PolicyRevision
from cyber_lion.enterprise.authority_source import AuthorityLookupKey
from cyber_lion.enterprise.control_plane import ActionProposal
from cyber_lion.enterprise.models import AgentSpec, MissionSpec, SwarmSpec
from cyber_lion.enterprise.policy_gate import CanonicalPolicyDecisionPoint, PDPResult


class ActionProposalPDPHandoffError(ValueError):
    """Raised when explicit PDP handoff context is incomplete or identity-incoherent."""


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip() or "\x00" in value:
        raise ActionProposalPDPHandoffError(f"{name} invalid")
    return value


def _refs(value: object, name: str, *, require_nonempty: bool = False) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise ActionProposalPDPHandoffError(f"{name} must be an immutable tuple")
    if require_nonempty and not value:
        raise ActionProposalPDPHandoffError(f"{name} required")
    if any(type(item) is not str or not item.strip() or "\x00" in item for item in value):
        raise ActionProposalPDPHandoffError(f"{name} invalid")
    if len(value) != len(set(value)):
        raise ActionProposalPDPHandoffError(f"{name} duplicates")
    return value


@dataclass(frozen=True)
class CanonicalPDPAdmissionContext:
    request_id: str
    gate_event_id: str
    mission: MissionSpec
    swarm: SwarmSpec
    agents: Mapping[str, AgentSpec]
    policy: PolicyRevision
    authority_key: AuthorityLookupKey
    graph_projection: EnterpriseGraphProjection
    status: Mapping[str, object]
    observability_state: str
    observed_event_types: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    trusted_now: datetime

    def validate(self) -> "CanonicalPDPAdmissionContext":
        _text(self.request_id, "request_id")
        _text(self.gate_event_id, "gate_event_id")
        if type(self.mission) is not MissionSpec:
            raise ActionProposalPDPHandoffError("exact MissionSpec required")
        if type(self.swarm) is not SwarmSpec:
            raise ActionProposalPDPHandoffError("exact SwarmSpec required")
        if type(self.policy) is not PolicyRevision:
            raise ActionProposalPDPHandoffError("exact PolicyRevision required")
        if type(self.authority_key) is not AuthorityLookupKey:
            raise ActionProposalPDPHandoffError("exact AuthorityLookupKey required")
        if type(self.graph_projection) is not EnterpriseGraphProjection:
            raise ActionProposalPDPHandoffError("exact EnterpriseGraphProjection required")
        if type(self.status) is not dict:
            raise ActionProposalPDPHandoffError("canonical status dict required")
        if not isinstance(self.agents, Mapping):
            raise ActionProposalPDPHandoffError("agents mapping required")
        if any(type(key) is not str or type(value) is not AgentSpec for key, value in self.agents.items()):
            raise ActionProposalPDPHandoffError("agents mapping must contain exact AgentSpec values")
        if any(key != value.agent_id for key, value in self.agents.items()):
            raise ActionProposalPDPHandoffError("agents mapping key/AgentSpec identity mismatch")
        _text(self.observability_state, "observability_state")
        _refs(self.observed_event_types, "observed_event_types")
        _refs(self.evidence_refs, "evidence_refs", require_nonempty=True)
        if type(self.trusted_now) is not datetime or self.trusted_now.tzinfo is None:
            raise ActionProposalPDPHandoffError("trusted_now must be exact timezone-aware datetime")
        self.mission.validate()
        self.swarm.validate()
        self.policy.validate()
        self.authority_key.validate()
        self.graph_projection.verify_digest()
        if self.swarm.mission_id != self.mission.mission_id:
            raise ActionProposalPDPHandoffError("swarm/mission identity mismatch")
        return self


def handoff_action_proposal_to_canonical_pdp(
    proposal: ActionProposal,
    pdp: CanonicalPolicyDecisionPoint,
    context: CanonicalPDPAdmissionContext,
) -> PDPResult:
    """Validate explicit identity bindings, then delegate policy authority to the live PDP."""
    if type(proposal) is not ActionProposal:
        raise ActionProposalPDPHandoffError("exact ActionProposal required")
    if type(pdp) is not CanonicalPolicyDecisionPoint:
        raise ActionProposalPDPHandoffError("exact CanonicalPolicyDecisionPoint required")
    if type(context) is not CanonicalPDPAdmissionContext:
        raise ActionProposalPDPHandoffError("exact CanonicalPDPAdmissionContext required")
    proposal.validate()
    context.validate()
    if proposal.mission_id != context.mission.mission_id:
        raise ActionProposalPDPHandoffError("proposal/mission identity mismatch")
    if proposal.swarm_id != context.swarm.swarm_id:
        raise ActionProposalPDPHandoffError("proposal/swarm identity mismatch")
    result = pdp.evaluate(
        request_id=context.request_id,
        gate_event_id=context.gate_event_id,
        proposal=proposal,
        mission=context.mission,
        swarm=context.swarm,
        agents=context.agents,
        policy=context.policy,
        authority_key=context.authority_key,
        graph_projection=context.graph_projection,
        status=context.status,
        observability_state=context.observability_state,
        observed_event_types=context.observed_event_types,
        evidence_refs=context.evidence_refs,
        trusted_now=context.trusted_now,
    )
    if type(result) is not PDPResult:
        raise ActionProposalPDPHandoffError("canonical PDP returned invalid result type")
    return result

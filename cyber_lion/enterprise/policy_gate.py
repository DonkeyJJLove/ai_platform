"""Canonical deterministic PDP layered over the existing ExecutionControlPlane.

AuthoritySource is the authority input. EnterpriseGraph, LION status, roles and governor
state are evidence/context only and can only preserve or reduce admissibility.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping, MutableMapping

from cyber_lion.contracts.policy_gate import GateApplied,GateRequested,PDPDecisionReceipt,PolicyRevision
from .authority_source import AuthorityLookupKey,AuthoritySource,AuthoritySourceError
from .control_plane import ActionProposal,ExecutionControlPlane
from .models import AgentSpec,MissionSpec,SwarmSpec

_CONTAINS={
 "none":{"none"},
 "read":{"none","read"},
 "local_write":{"none","read","local_write"},
 "external_write":{"none","read","local_write","external_write"},
 "financial":{"none","read","local_write","external_write","financial"},
 "deploy":{"none","read","local_write","external_write","deploy"},
 "privileged":{"none","read","local_write","external_write","financial","deploy","privileged"},
}
_OBS_CEILING={"HEALTHY":"privileged","DEGRADED":"read","LOST":"none"}

class PolicyGateError(RuntimeError): pass

def authority_contains(parent:str,child:str)->bool:
    try:return child in _CONTAINS[parent]
    except KeyError as exc:raise PolicyGateError(f"unknown authority class: {exc.args[0]}") from exc

def _hex64(value:object,name:str)->str:
    if not isinstance(value,str) or len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
        raise PolicyGateError(f"{name} must be canonical sha256 hex")
    return value

def _status_digest(status:Mapping[str,object])->str:
    if status.get("epistemic_state")!="CURRENT": raise PolicyGateError("LION status is not CURRENT")
    return _hex64(status.get("status_digest"),"status_digest")

def _graph_digest(graph_projection:object)->str:
    value=getattr(graph_projection,"projection_digest",None)
    return _hex64(value,"enterprise_graph_digest")

@dataclass(frozen=True)
class PDPResult:
    requested:GateRequested
    applied:GateApplied
    receipt:PDPDecisionReceipt

class CanonicalPolicyDecisionPoint:
    """Fail-closed PDP. It never mints, delegates or consumes authority."""
    def __init__(self,*,authority_source:AuthoritySource,control_plane:ExecutionControlPlane|None=None):
        self.authority_source=authority_source
        self.control_plane=control_plane or ExecutionControlPlane()
        self._replay:MutableMapping[str,tuple[str,PDPResult]]={}

    def evaluate(self,*,request_id:str,gate_event_id:str,proposal:ActionProposal,mission:MissionSpec,
                 swarm:SwarmSpec,agents:Mapping[str,AgentSpec],policy:PolicyRevision,
                 authority_key:AuthorityLookupKey,graph_projection:object,status:Mapping[str,object],
                 observability_state:str,observed_event_types:tuple[str,...],evidence_refs:tuple[str,...])->PDPResult:
        proposal.validate();mission.validate();swarm.validate();policy.validate();authority_key.validate()
        if not policy.active: raise PolicyGateError("policy revision inactive")
        if policy.lane!=mission.risk_class: raise PolicyGateError("policy lane does not bind mission risk class")
        if observability_state not in _OBS_CEILING: raise PolicyGateError("invalid observability_state")
        if not evidence_refs or len(set(evidence_refs))!=len(evidence_refs): raise PolicyGateError("unique evidence_refs required")
        sd=_status_digest(status);gd=_graph_digest(graph_projection)
        try:lineage=self.authority_source.resolve_exact(authority_key)
        except AuthoritySourceError as exc:raise PolicyGateError("canonical authority lineage unavailable") from exc
        leaf=lineage.lineage[-1]
        if leaf.mission_id!=proposal.mission_id or leaf.capability_id!=proposal.capability:
            raise PolicyGateError("authority lineage mission/capability mismatch")
        if not authority_contains(leaf.authority_ceiling,proposal.requested_authority):
            raise PolicyGateError("requested authority not semantically contained by lineage")
        request=GateRequested(request_id=request_id,proposal_id=proposal.proposal_id,policy_binding=policy.binding,
            authority_lineage_digest=lineage.lineage_digest,enterprise_graph_digest=gd,status_digest=sd,
            observability_state=observability_state,lane=policy.lane,requested_authority=proposal.requested_authority,
            evidence_refs=evidence_refs).sealed()
        old=self._replay.get(request_id)
        if old is not None:
            if old[0]!=request.request_digest: raise PolicyGateError("replayed request_id payload substitution denied")
            return old[1]

        rationale="all canonical PDP invariants satisfied";decision="ALLOW";effective=proposal.requested_authority
        if not authority_contains(_OBS_CEILING[observability_state],proposal.requested_authority):
            decision="DENY";effective="none";rationale="observability-conditioned authority ceiling exceeded"
        if proposal.consequential and policy.lane in {"AMBER","RED"}:
            if not proposal.verifier_agent_id or proposal.verifier_agent_id==proposal.proposer_agent_id:
                decision="DENY";effective="none";rationale="AMBER/RED consequential request requires independent verifier"
        base=self.control_plane.evaluate(proposal=proposal,mission=mission,swarm=swarm,agents=agents,
            policy_ids=(policy.binding,),observed_event_types=observed_event_types,gate_event_id=gate_event_id)
        if base.decision!="ALLOW":
            decision="DENY";effective="none";rationale=f"base deterministic admission denied: {base.rationale}"
        applied=GateApplied(gate_event_id=gate_event_id,request_id=request_id,proposal_id=proposal.proposal_id,
            decision=decision,effective_authority=effective,policy_binding=policy.binding,
            authority_lineage_digest=lineage.lineage_digest,enterprise_graph_digest=gd,status_digest=sd,
            observability_state=observability_state,lane=policy.lane,rationale=rationale).sealed()
        replay_key=sha256((request.request_digest+applied.decision_digest).encode("ascii")).hexdigest()
        receipt=PDPDecisionReceipt(receipt_id=f"pdp-receipt:{request_id}",request_id=request_id,
            gate_event_id=gate_event_id,request_digest=request.request_digest,
            decision_digest=applied.decision_digest,replay_key=replay_key).validate()
        result=PDPResult(request,applied,receipt);self._replay[request_id]=(request.request_digest,result);return result

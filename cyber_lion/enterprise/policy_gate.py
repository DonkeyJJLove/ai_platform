"""Canonical deterministic PDP layered over the existing ExecutionControlPlane.

LiveAuthorityAdmission is the mandatory authority-admission boundary. EnterpriseGraph,
LION status, roles and governor state are evidence/context only and can only preserve
or reduce admissibility; none can mint authority.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Mapping,MutableMapping
from cyber_lion.contracts.enterprise_graph import EnterpriseGraphProjection
from cyber_lion.contracts.policy_gate import GateApplied,GateRequested,PDPDecisionReceipt,PolicyRevision
from .authority_source import AuthorityLookupKey
from .control_plane import ActionProposal,ExecutionControlPlane
from .live_authority_admission import LiveAuthorityAdmission,LiveAuthorityAdmissionError
from .models import AgentSpec,MissionSpec,SwarmSpec
from .swarm_status_projection import validate_status_projection

_CONTAINS={"none":{"none"},"read":{"none","read"},"local_write":{"none","read","local_write"},"external_write":{"none","read","local_write","external_write"},"financial":{"none","read","local_write","external_write","financial"},"deploy":{"none","read","local_write","external_write","deploy"},"privileged":{"none","read","local_write","external_write","financial","deploy","privileged"}}
_OBS_CEILING={"HEALTHY":"privileged","DEGRADED":"read","LOST":"none"}
class PolicyGateError(RuntimeError):pass

def authority_contains(parent:str,child:str)->bool:
    try:return child in _CONTAINS[parent]
    except KeyError as exc:raise PolicyGateError(f"unknown authority class: {exc.args[0]}") from exc

def _status_digest(status:Mapping[str,object])->str:
    if not isinstance(status,dict):raise PolicyGateError("canonical LION status mapping required")
    try:validate_status_projection(status)
    except Exception as exc:raise PolicyGateError("LION status projection invalid") from exc
    if status["epistemic_state"]!="CURRENT":raise PolicyGateError("LION status is not CURRENT")
    return status["status_digest"]

def _graph_digest(graph_projection:object)->str:
    if type(graph_projection) is not EnterpriseGraphProjection:raise PolicyGateError("exact EnterpriseGraphProjection required")
    try:return graph_projection.verify_digest().projection_digest
    except Exception as exc:raise PolicyGateError("EnterpriseGraph projection digest invalid") from exc

def _pre_request_digest(*,request_id,gate_event_id,proposal,policy,authority_key,graph_digest,status_digest,observability_state,observed_event_types,evidence_refs):
    payload={"request_id":request_id,"gate_event_id":gate_event_id,"proposal":asdict(proposal),"policy":asdict(policy),"authority_key":authority_key.binding(),"graph_digest":graph_digest,"status_digest":status_digest,"observability_state":observability_state,"observed_event_types":list(observed_event_types),"evidence_refs":list(evidence_refs)}
    return sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=list).encode()).hexdigest()

@dataclass(frozen=True)
class PDPResult:requested:GateRequested;applied:GateApplied;receipt:PDPDecisionReceipt

class CanonicalPolicyDecisionPoint:
    """Fail-closed PDP. It never mints, delegates or itself consumes effect authority."""
    def __init__(self,*,authority_admission:LiveAuthorityAdmission,control_plane:ExecutionControlPlane|None=None):
        if not isinstance(authority_admission,LiveAuthorityAdmission):raise PolicyGateError("LiveAuthorityAdmission is required")
        self.authority_admission=authority_admission;self.control_plane=control_plane or ExecutionControlPlane();self._replay:MutableMapping[str,tuple[str,PDPResult]]={}
    def evaluate(self,*,request_id:str,gate_event_id:str,proposal:ActionProposal,mission:MissionSpec,swarm:SwarmSpec,agents:Mapping[str,AgentSpec],policy:PolicyRevision,authority_key:AuthorityLookupKey,graph_projection:EnterpriseGraphProjection,status:Mapping[str,object],observability_state:str,observed_event_types:tuple[str,...],evidence_refs:tuple[str,...],trusted_now:datetime)->PDPResult:
        proposal.validate();mission.validate();swarm.validate();policy.validate();authority_key.validate()
        if trusted_now.tzinfo is None:raise PolicyGateError("trusted_now must be timezone-aware")
        if not policy.active:raise PolicyGateError("policy revision inactive")
        if policy.lane!=mission.risk_class:raise PolicyGateError("policy lane does not bind mission risk class")
        if observability_state not in _OBS_CEILING:raise PolicyGateError("invalid observability_state")
        if not evidence_refs or len(set(evidence_refs))!=len(evidence_refs):raise PolicyGateError("unique evidence_refs required")
        sd=_status_digest(status);gd=_graph_digest(graph_projection)
        pre=_pre_request_digest(request_id=request_id,gate_event_id=gate_event_id,proposal=proposal,policy=policy,authority_key=authority_key,graph_digest=gd,status_digest=sd,observability_state=observability_state,observed_event_types=observed_event_types,evidence_refs=evidence_refs)
        old=self._replay.get(request_id)
        if old is not None:
            if old[0]!=pre:raise PolicyGateError("replayed request_id payload substitution denied")
            return old[1]
        try:
            admitted=self.authority_admission.admit(repository=authority_key.repository,pr_number=authority_key.pr_number,base_sha=authority_key.base_sha,head_sha=authority_key.head_sha,mission_id=authority_key.mission_id,grant_id=authority_key.grant_id,now=trusted_now,replay_nonce=f"pdp:{request_id}")
            lineage=self.authority_admission._source.resolve_exact(authority_key)
        except Exception as exc:raise PolicyGateError("live canonical authority admission unavailable") from exc
        admitted.validate();lineage.validate();leaf=lineage.lineage[-1]
        if lineage.lineage_digest!=admitted.lineage_digest or leaf.digest()!=admitted.leaf_grant_digest:raise PolicyGateError("live admission/lineage binding mismatch")
        if leaf.mission_id!=proposal.mission_id or leaf.capability_id!=proposal.capability:raise PolicyGateError("authority mission/capability mismatch")
        if leaf.policy_digest!=policy.content_digest:raise PolicyGateError("policy revision digest does not match admitted authority grant")
        if not authority_contains(admitted.authority_ceiling,proposal.requested_authority):raise PolicyGateError("requested authority not semantically contained by live admission")
        request=GateRequested(request_id=request_id,proposal_id=proposal.proposal_id,policy_binding=policy.binding,authority_lineage_digest=admitted.lineage_digest,enterprise_graph_digest=gd,status_digest=sd,observability_state=observability_state,lane=policy.lane,requested_authority=proposal.requested_authority,evidence_refs=evidence_refs).sealed()
        rationale="all canonical PDP invariants satisfied";decision="ALLOW";effective=proposal.requested_authority
        if not authority_contains(_OBS_CEILING[observability_state],proposal.requested_authority):decision="DENY";effective="none";rationale="observability-conditioned authority ceiling exceeded"
        if proposal.consequential and policy.lane in {"AMBER","RED"} and (not proposal.verifier_agent_id or proposal.verifier_agent_id==proposal.proposer_agent_id):decision="DENY";effective="none";rationale="AMBER/RED consequential request requires independent verifier"
        base=self.control_plane.evaluate(proposal=proposal,mission=mission,swarm=swarm,agents=agents,policy_ids=(policy.binding,),observed_event_types=observed_event_types,gate_event_id=gate_event_id)
        if base.decision!="ALLOW":decision="DENY";effective="none";rationale=f"base deterministic admission denied: {base.rationale}"
        try:self.authority_admission.revalidate(admitted,now=trusted_now)
        except LiveAuthorityAdmissionError as exc:raise PolicyGateError("live authority changed before GateApplied") from exc
        applied=GateApplied(gate_event_id=gate_event_id,request_id=request_id,proposal_id=proposal.proposal_id,decision=decision,effective_authority=effective,policy_binding=policy.binding,authority_lineage_digest=admitted.lineage_digest,enterprise_graph_digest=gd,status_digest=sd,observability_state=observability_state,lane=policy.lane,rationale=rationale).sealed()
        replay_key=sha256((request.request_digest+applied.decision_digest+admitted.digest()).encode("ascii")).hexdigest();receipt=PDPDecisionReceipt(receipt_id=f"pdp-receipt:{request_id}",request_id=request_id,gate_event_id=gate_event_id,request_digest=request.request_digest,decision_digest=applied.decision_digest,replay_key=replay_key).validate();result=PDPResult(request,applied,receipt);self._replay[request_id]=(pre,result);return result

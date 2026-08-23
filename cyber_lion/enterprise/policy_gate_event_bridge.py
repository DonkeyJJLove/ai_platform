"""EventEnvelope bridge for canonical PDP GateRequested/GateApplied records."""
from __future__ import annotations
from cyber_lion.contracts.events import Authority,EventEnvelope,Provenance
from cyber_lion.contracts.policy_gate import GateApplied,GateRequested


def gate_requested_event(request:GateRequested,*,occurred_at:str,correlation_id:str)->EventEnvelope:
    request.validate()
    return EventEnvelope(schema_version="1.0.0",event_id=f"event:{request.request_id}",event_type="GateRequested",
        occurred_at=occurred_at,correlation_id=correlation_id,
        entity={"entity_id":"cyber-lion:pdp","entity_type":"policy-decision-point"},
        source={"component":"cyber_lion.enterprise.policy_gate"},
        provenance=Provenance(epistemic_status="DERIVED",upstream=list(request.evidence_refs),
            transformation_chain=["ActionProposal+PolicyRevision+AuthorityLineage+Evidence→GateRequested"],content_hash=request.request_digest),
        authority=Authority(requested=request.requested_authority,effective="none",policy_ids=[request.policy_binding]),
        epistemic_state="FORMALISED",payload={"request_id":request.request_id,"proposal_id":request.proposal_id,
        "lane":request.lane,"observability_state":request.observability_state,
        "authority_lineage_digest":request.authority_lineage_digest,"enterprise_graph_digest":request.enterprise_graph_digest,
        "status_digest":request.status_digest,"request_digest":request.request_digest}).validate()


def gate_applied_event(applied:GateApplied,*,request_event_id:str,occurred_at:str,correlation_id:str)->EventEnvelope:
    applied.validate()
    return EventEnvelope(schema_version="1.0.0",event_id=applied.gate_event_id,event_type="GateApplied",
        occurred_at=occurred_at,correlation_id=correlation_id,causation_id=request_event_id,
        entity={"entity_id":"cyber-lion:mand","entity_type":"authority-plane"},
        source={"component":"cyber_lion.enterprise.policy_gate"},
        provenance=Provenance(epistemic_status="DERIVED",upstream=[request_event_id],
            transformation_chain=["GateRequested→CanonicalPDP→GateApplied"],content_hash=applied.decision_digest),
        authority=Authority(requested=applied.effective_authority,effective=applied.effective_authority,
            policy_ids=[applied.policy_binding],gate_event_id=applied.gate_event_id if applied.decision=="ALLOW" else None),
        epistemic_state="FORMALISED",payload={"request_id":applied.request_id,"proposal_id":applied.proposal_id,
        "decision":applied.decision,"lane":applied.lane,"observability_state":applied.observability_state,
        "rationale":applied.rationale,"decision_digest":applied.decision_digest}).validate()

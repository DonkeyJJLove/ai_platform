"""Pure EventEnvelope/AgentRegistry projections into Enterprise Graph records."""
from __future__ import annotations
from dataclasses import asdict
from cyber_lion.contracts.agent_registry import AgentSpecKey
from cyber_lion.contracts.enterprise_graph import GraphEdge,GraphNode
from cyber_lion.contracts.events import EventEnvelope


def agent_node_from_registry_key(key:AgentSpecKey)->GraphNode:
    key.validate()
    return GraphNode(node_id=f"agent:{key.agent_id}",node_type="AGENT",version=key.version,payload={"agent_id":key.agent_id,"spec_digest":key.spec_digest,"identity_source":"AgentRegistry"},provenance_refs=(f"agent-registry:{key.spec_digest}",)).validate()

def _event_node_type(event_type:str)->str:
    if event_type=="ActionExecuted":return "EXECUTION"
    if event_type in {"EvidenceAttached","MemoryCommitted"}:return "EVIDENCE"
    if event_type in {"ObservationCreated","OutcomeObserved","AnomalyDetected"}:return "OBSERVATION"
    return "ENTITY"

def event_to_graph_records(event:EventEnvelope)->tuple[tuple[GraphNode,...],tuple[GraphEdge,...]]:
    event.validate();entity_id=event.entity["entity_id"]
    event_node=GraphNode(node_id=f"event:{event.event_id}",node_type=_event_node_type(event.event_type),version=event.schema_version,payload={"event_id":event.event_id,"event_type":event.event_type,"occurred_at":event.occurred_at,"correlation_id":event.correlation_id,"causation_id":event.causation_id,"epistemic_state":event.epistemic_state,"source":event.source,"payload":event.payload},provenance_refs=tuple(event.provenance.upstream)).validate()
    entity_type=str(event.entity.get("entity_type","entity")).upper().replace("-","_")
    mapped={"AGENT":"AGENT","MISSION":"MISSION","SWARM":"SWARM","POLICY":"POLICY","EXECUTION":"EXECUTION","ARTIFACT":"ARTIFACT"}.get(entity_type,"ENTITY")
    entity_node=GraphNode(node_id=f"entity:{entity_id}",node_type=mapped,version=str(event.entity.get("version","1")),payload=dict(event.entity),provenance_refs=()).validate()
    nodes=[entity_node,event_node];edges=[GraphEdge(edge_id=f"edge:{event.event_id}:entity",plane="DATA_PROVENANCE",edge_type="OBSERVED_FROM",source_id=event_node.node_id,target_id=entity_node.node_id,provenance_refs=tuple(event.provenance.upstream)).validate()]
    if event.causation_id:
        cause=GraphNode(node_id=f"event:{event.causation_id}",node_type="ENTITY",version="1",payload={"external_event_ref":event.causation_id},provenance_refs=(event.causation_id,)).validate();nodes.append(cause)
        # Event causation_id is an explicit causal assertion from the envelope contract.
        edges.append(GraphEdge(edge_id=f"edge:{event.event_id}:caused-by",plane="DATA_PROVENANCE",edge_type="CAUSED_BY",source_id=event_node.node_id,target_id=cause.node_id,provenance_refs=tuple(event.provenance.upstream),causality_evidence_ref=event.causation_id).validate())
    if event.authority.gate_event_id or event.authority.policy_ids:
        authority_key=event.authority.gate_event_id or ":".join(sorted(event.authority.policy_ids))
        auth=GraphNode(node_id=f"authority-ref:{authority_key}",node_type="AUTHORITY_RECORD",version="1",payload={"requested":event.authority.requested,"effective":event.authority.effective,"policy_ids":list(event.authority.policy_ids),"gate_event_id":event.authority.gate_event_id,"authoritative":False,"note":"reference evidence only; resolve through AuthoritySource"},provenance_refs=tuple(event.provenance.upstream)).validate();nodes.append(auth)
        edges.append(GraphEdge(edge_id=f"edge:{event.event_id}:authority-ref",plane="AUTHORITY_REFERENCE",edge_type="AUTHORITY_REFERENCED_BY",source_id=auth.node_id,target_id=event_node.node_id,provenance_refs=tuple(event.provenance.upstream)).validate())
    # Correlation is not causation; no edge is created from correlation_id alone.
    return tuple(nodes),tuple(edges)

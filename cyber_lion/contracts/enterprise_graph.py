"""Typed Enterprise Graph contracts. Graph state is evidence, never permission."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from hashlib import sha256
import json,re
from typing import Any,Mapping

NODE_TYPES={"ENTITY","MISSION","CAPABILITY","AGENT","SWARM","POLICY","AUTHORITY_RECORD","PROVENANCE","EVIDENCE","EXECUTION","ARTIFACT","OBSERVATION"}
DATA_EDGE_TYPES={"HAS_CAPABILITY","MEMBER_OF","DERIVED_FROM","SUPPORTS","CONTRADICTS","OBSERVED_FROM","EXECUTED_BY","PRODUCED","SUPERSEDES","CORRELATED_WITH","CAUSED_BY"}
AUTHORITY_EDGE_TYPES={"AUTHORITY_PARENT_OF","AUTHORITY_BINDS_RESOURCE","AUTHORITY_REFERENCED_BY"}
PLANES={"DATA_PROVENANCE","AUTHORITY_REFERENCE"}
_DIGEST=re.compile(r"^[0-9a-f]{64}$")

class EnterpriseGraphError(ValueError):pass

def canonical_json(value:Any)->bytes:return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _text(v:object,name:str)->str:
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise EnterpriseGraphError(f"{name} invalid")
    return v

def _digest(v:object,name:str)->str:
    _text(v,name)
    if not _DIGEST.fullmatch(v):raise EnterpriseGraphError(f"{name} must be sha256 hex")
    return v

def _refs(v:object,name:str)->tuple[str,...]:
    if type(v) is not tuple:raise EnterpriseGraphError(f"{name} must be tuple")
    for ref in v:_text(ref,name)
    if len(set(v))!=len(v):raise EnterpriseGraphError(f"{name} must be unique")
    return v

@dataclass(frozen=True)
class GraphNode:
    node_id:str;node_type:str;version:str;payload:Mapping[str,Any];provenance_refs:tuple[str,...]=()
    def validate(self):
        _text(self.node_id,"node_id");_text(self.version,"version")
        if self.node_type not in NODE_TYPES:raise EnterpriseGraphError("unknown node_type")
        if not isinstance(self.payload,Mapping):raise EnterpriseGraphError("payload must be mapping")
        _refs(self.provenance_refs,"provenance_refs")
        return self
    def digest(self):return sha256(canonical_json(asdict(self))).hexdigest()

@dataclass(frozen=True)
class GraphEdge:
    edge_id:str;plane:str;edge_type:str;source_id:str;target_id:str;provenance_refs:tuple[str,...]=();causality_evidence_ref:str|None=None
    def validate(self):
        for n,v in (("edge_id",self.edge_id),("source_id",self.source_id),("target_id",self.target_id)):_text(v,n)
        if self.plane not in PLANES:raise EnterpriseGraphError("unknown plane")
        allowed=DATA_EDGE_TYPES if self.plane=="DATA_PROVENANCE" else AUTHORITY_EDGE_TYPES
        if self.edge_type not in allowed:raise EnterpriseGraphError("edge_type not allowed in plane")
        _refs(self.provenance_refs,"provenance_refs")
        if self.edge_type=="CAUSED_BY":
            if not self.causality_evidence_ref:raise EnterpriseGraphError("CAUSED_BY requires causality evidence")
            if self.causality_evidence_ref not in self.provenance_refs:raise EnterpriseGraphError("CAUSED_BY evidence must be provenance-bound")
        elif self.causality_evidence_ref is not None:raise EnterpriseGraphError("causality evidence only valid for CAUSED_BY")
        return self
    def digest(self):return sha256(canonical_json(asdict(self))).hexdigest()

@dataclass(frozen=True)
class EnterpriseGraphProjection:
    graph_id:str;revision:int;event_head:str;nodes:tuple[GraphNode,...];edges:tuple[GraphEdge,...];projection_digest:str
    def validate(self):
        _text(self.graph_id,"graph_id");_digest(self.event_head,"event_head");_digest(self.projection_digest,"projection_digest")
        if not isinstance(self.revision,int) or self.revision<0:raise EnterpriseGraphError("revision invalid")
        if type(self.nodes) is not tuple or type(self.edges) is not tuple:raise EnterpriseGraphError("projection collections must be tuple")
        for n in self.nodes:n.validate()
        for e in self.edges:e.validate()
        return self
    def logical_payload(self):
        return {"graph_id":self.graph_id,"nodes":[asdict(x) for x in self.nodes],"edges":[asdict(x) for x in self.edges]}
    def verify_digest(self):
        self.validate();expected=sha256(canonical_json(self.logical_payload())).hexdigest()
        if expected!=self.projection_digest:raise EnterpriseGraphError("projection digest mismatch")
        return self

@dataclass(frozen=True)
class GraphPath:
    plane:str;node_ids:tuple[str,...];edge_ids:tuple[str,...]
    def validate(self):
        if self.plane not in PLANES:raise EnterpriseGraphError("unknown plane")
        if len(self.node_ids)!=len(self.edge_ids)+1:raise EnterpriseGraphError("path shape invalid")
        return self

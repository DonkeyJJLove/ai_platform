"""Canonical non-effectful semantic relevance contracts for LION."""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json,re
from typing import Tuple

SCHEMA_ID="lion.semantic-relevance/v1";AUTHORITY_EFFECT="NONE";EFFECT="NONE"
DELTA_OPERATIONS=frozenset({"ADD","UPDATE","SUPERSEDE","CONTRADICT","RETRACT","REVALIDATE"})
TEMPORAL_STATES=frozenset({"CURRENT","STALE","UNKNOWN","SUPERSEDED"})
_FORBIDDEN_DELTA_PREDICATES=frozenset({"credential","credentials","password","secret_value","authority_grant","runtime_admission"})
_SAFE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$");_HEX=re.compile(r"^[0-9a-f]{64}$")
class SemanticRelevanceError(ValueError):pass

def _id(v,n):
    if not isinstance(v,str) or _SAFE.fullmatch(v) is None:raise SemanticRelevanceError(f"{n} invalid")
    return v
def _txt(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise SemanticRelevanceError(f"{n} invalid")
    return v
def _hex(v,n):
    if not isinstance(v,str) or _HEX.fullmatch(v) is None:raise SemanticRelevanceError(f"{n} invalid")
    return v
def _refs(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise SemanticRelevanceError(f"{n} invalid")
    for x in v:_id(x,n)
    if len(v)!=len(set(v)):raise SemanticRelevanceError(f"{n} unique")
    return v

@dataclass(frozen=True)
class EvidenceInstance:
    evidence_ref:str;root_ref:str;content_digest:str;observed_at:str;currentness:str
    def validate(self):
        _id(self.evidence_ref,"evidence_ref");_id(self.root_ref,"root_ref");_hex(self.content_digest,"content_digest");_txt(self.observed_at,"observed_at")
        if self.currentness not in TEMPORAL_STATES:raise SemanticRelevanceError("evidence currentness invalid")
        return self

@dataclass(frozen=True)
class SemanticAtom:
    atom_id:str
    semantic_key:str
    proposition_core:str
    relation_signature:Tuple[str,...]
    scope:Tuple[str,...]
    temporal_state:str
    evidence:Tuple[EvidenceInstance,...]
    source_representation_refs:Tuple[str,...]
    atom_digest:str=""
    authority_effect:str="NONE"
    effect:str="NONE"
    def payload(self):d=asdict(self);d.pop("atom_digest",None);return d
    def compute_digest(self):
        return sha256(b"LION/SEMANTIC-ATOM/1\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def independent_root_count(self):
        self.validate(require_digest=False)
        return len({x.root_ref for x in self.evidence})
    def validate(self,require_digest=True):
        _id(self.atom_id,"atom_id");_id(self.semantic_key,"semantic_key");_txt(self.proposition_core,"proposition_core")
        _refs(self.relation_signature,"relation_signature",True);_refs(self.scope,"scope",True);_refs(self.source_representation_refs,"source_representation_refs",True)
        if self.temporal_state not in TEMPORAL_STATES:raise SemanticRelevanceError("temporal_state invalid")
        if type(self.evidence) is not tuple or not self.evidence:raise SemanticRelevanceError("evidence required")
        seen=set()
        for item in self.evidence:
            item.validate()
            if item.evidence_ref in seen:raise SemanticRelevanceError("duplicate evidence_ref")
            seen.add(item.evidence_ref)
        if self.authority_effect!="NONE" or self.effect!="NONE":raise SemanticRelevanceError("SemanticAtom cannot carry authority/effect")
        if require_digest:
            _hex(self.atom_digest,"atom_digest")
            if self.atom_digest!=self.compute_digest():raise SemanticRelevanceError("atom_digest mismatch")
        return self
    def sealed(self):return replace(self,atom_digest=self.compute_digest()).validate()

@dataclass(frozen=True)
class SemanticDelta:
    delta_id:str
    base_graph_digest:str
    operation:str
    subject_ref:str
    predicate:str
    object_ref:str
    evidence_refs:Tuple[str,...]
    currentness_basis:Tuple[str,...]
    delta_digest:str=""
    authority_effect:str="NONE"
    effect:str="NONE"
    def payload(self):d=asdict(self);d.pop("delta_digest",None);return d
    def compute_digest(self):
        return sha256(b"LION/SEMANTIC-DELTA/1\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def validate(self,require_digest=True):
        _id(self.delta_id,"delta_id");_hex(self.base_graph_digest,"base_graph_digest");_id(self.subject_ref,"subject_ref");_id(self.predicate,"predicate");_id(self.object_ref,"object_ref")
        if self.operation not in DELTA_OPERATIONS:raise SemanticRelevanceError("delta operation invalid")
        if self.predicate.casefold() in _FORBIDDEN_DELTA_PREDICATES:raise SemanticRelevanceError("credential/authority-bearing semantic delta denied")
        _refs(self.evidence_refs,"evidence_refs",True);_refs(self.currentness_basis,"currentness_basis",True)
        if self.authority_effect!="NONE" or self.effect!="NONE":raise SemanticRelevanceError("SemanticDelta cannot carry authority/effect")
        if require_digest:
            _hex(self.delta_digest,"delta_digest")
            if self.delta_digest!=self.compute_digest():raise SemanticRelevanceError("delta_digest mismatch")
        return self
    def sealed(self):return replace(self,delta_digest=self.compute_digest()).validate()

@dataclass(frozen=True)
class RelevanceGraph:
    graph_id:str
    mission_intent_ref:str
    semantic_scaffold_ref:str
    node_refs:Tuple[str,...]
    edge_refs:Tuple[str,...]
    currentness_basis:Tuple[str,...]
    graph_digest:str=""
    authority_effect:str="NONE"
    effect:str="NONE"
    def payload(self):d=asdict(self);d.pop("graph_digest",None);return d
    def compute_digest(self):
        return sha256(b"LION/RELEVANCE-GRAPH/1\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def validate(self,require_digest=True):
        _id(self.graph_id,"graph_id");_id(self.mission_intent_ref,"mission_intent_ref");_id(self.semantic_scaffold_ref,"semantic_scaffold_ref")
        _refs(self.node_refs,"node_refs",True);_refs(self.edge_refs,"edge_refs");_refs(self.currentness_basis,"currentness_basis",True)
        if self.authority_effect!="NONE" or self.effect!="NONE":raise SemanticRelevanceError("RelevanceGraph cannot carry authority/effect")
        if require_digest:
            _hex(self.graph_digest,"graph_digest")
            if self.graph_digest!=self.compute_digest():raise SemanticRelevanceError("graph_digest mismatch")
        return self
    def sealed(self):return replace(self,graph_digest=self.compute_digest()).validate()

@dataclass(frozen=True)
class RelevanceProjection:
    projection_id:str
    graph_ref:str
    graph_digest:str
    consumer_ref:str
    required_capability_refs:Tuple[str,...]
    visible_node_refs:Tuple[str,...]
    visible_edge_refs:Tuple[str,...]
    excluded_classes:Tuple[str,...]
    resource_budget:int
    projection_digest:str=""
    authority_effect:str="NONE"
    effect:str="NONE"
    def payload(self):d=asdict(self);d.pop("projection_digest",None);return d
    def compute_digest(self):
        return sha256(b"LION/RELEVANCE-PROJECTION/1\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def validate(self,require_digest=True):
        _id(self.projection_id,"projection_id");_id(self.graph_ref,"graph_ref");_hex(self.graph_digest,"graph_digest");_id(self.consumer_ref,"consumer_ref")
        _refs(self.required_capability_refs,"required_capability_refs");_refs(self.visible_node_refs,"visible_node_refs",True);_refs(self.visible_edge_refs,"visible_edge_refs");_refs(self.excluded_classes,"excluded_classes")
        if isinstance(self.resource_budget,bool) or not isinstance(self.resource_budget,int) or self.resource_budget<1:raise SemanticRelevanceError("resource_budget invalid")
        if self.authority_effect!="NONE" or self.effect!="NONE":raise SemanticRelevanceError("RelevanceProjection cannot carry authority/effect")
        if require_digest:
            _hex(self.projection_digest,"projection_digest")
            if self.projection_digest!=self.compute_digest():raise SemanticRelevanceError("projection_digest mismatch")
        return self
    def validate_against(self,graph:RelevanceGraph,allowed_capabilities:Tuple[str,...]):
        self.validate();graph.validate()
        if self.graph_ref!=graph.graph_id or self.graph_digest!=graph.graph_digest:raise SemanticRelevanceError("graph substitution denied")
        if not set(self.visible_node_refs).issubset(set(graph.node_refs)):raise SemanticRelevanceError("projection node widening denied")
        if not set(self.visible_edge_refs).issubset(set(graph.edge_refs)):raise SemanticRelevanceError("projection edge widening denied")
        if not set(self.required_capability_refs).issubset(set(allowed_capabilities)):raise SemanticRelevanceError("capability widening denied")
        return self
    def sealed(self):return replace(self,projection_digest=self.compute_digest()).validate()


def projection_capability_requirements(*, projection:RelevanceProjection, graph:RelevanceGraph, gap, allowed_capabilities:Tuple[str,...])->Tuple[str,...]:
    """Bind a relevance projection to an existing Gap without minting capabilities or authority."""
    projection.validate_against(graph,allowed_capabilities)
    gap.validate()
    required=tuple(sorted(projection.required_capability_refs))
    missing=tuple(sorted(gap.missing_capabilities))
    if required!=missing:
        raise SemanticRelevanceError("relevance projection / Gap capability mismatch")
    return required

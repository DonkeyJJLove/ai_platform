"""Canonical non-effectful semantic scaffold IR for LION."""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json,re
from typing import Tuple

SCHEMA_ID="lion.semantic-scaffold/v1";AUTHORITY_EFFECT="NONE";EFFECT="NONE"
_SAFE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$");_HEX=re.compile(r"^[0-9a-f]{64}$")
class SemanticScaffoldError(ValueError):pass

def _id(v,n):
    if not isinstance(v,str) or _SAFE.fullmatch(v) is None:raise SemanticScaffoldError(f"{n} invalid")
    return v
def _hex(v,n):
    if not isinstance(v,str) or _HEX.fullmatch(v) is None:raise SemanticScaffoldError(f"{n} invalid")
    return v
def _refs(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise SemanticScaffoldError(f"{n} invalid")
    for x in v:_id(x,n)
    if len(v)!=len(set(v)):raise SemanticScaffoldError(f"{n} unique")
    return v

@dataclass(frozen=True)
class ScaffoldRelation:
    relation_id:str;subject_ref:str;predicate:str;object_ref:str;evidence_refs:Tuple[str,...]
    def validate(self):
        for v,n in ((self.relation_id,"relation_id"),(self.subject_ref,"subject_ref"),(self.predicate,"predicate"),(self.object_ref,"object_ref")):_id(v,n)
        _refs(self.evidence_refs,"evidence_refs",True)
        return self

@dataclass(frozen=True)
class SemanticScaffoldIR:
    scaffold_id:str
    mission_intent_ref:str;mission_intent_digest:str
    query_plan_ref:str;query_plan_digest:str
    rag_context_ref:str;rag_context_digest:str
    entity_refs:Tuple[str,...]
    relations:Tuple[ScaffoldRelation,...]
    gap_refs:Tuple[str,...]
    dependency_refs:Tuple[str,...]
    constraint_refs:Tuple[str,...]
    hypothesis_refs:Tuple[str,...]
    counter_hypothesis_refs:Tuple[str,...]
    falsifier_refs:Tuple[str,...]
    unknown_refs:Tuple[str,...]
    capability_need_refs:Tuple[str,...]
    representation_candidates:Tuple[str,...]
    evidence_bindings:Tuple[str,...]
    currentness_basis:Tuple[str,...]
    next_frontier:str
    scaffold_digest:str=""
    schema_id:str=SCHEMA_ID
    authority_effect:str="NONE"
    effect:str="NONE"

    def payload(self):d=asdict(self);d.pop("scaffold_digest",None);return d
    def compute_digest(self):
        return sha256(b"LION/SEMANTIC-SCAFFOLD/1\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def validate(self,require_digest=True):
        for v,n in ((self.scaffold_id,"scaffold_id"),(self.mission_intent_ref,"mission_intent_ref"),(self.query_plan_ref,"query_plan_ref"),(self.rag_context_ref,"rag_context_ref"),(self.next_frontier,"next_frontier")):_id(v,n)
        for v,n in ((self.mission_intent_digest,"mission_intent_digest"),(self.query_plan_digest,"query_plan_digest"),(self.rag_context_digest,"rag_context_digest")):_hex(v,n)
        for n in ("entity_refs","gap_refs","dependency_refs","constraint_refs","hypothesis_refs","counter_hypothesis_refs","falsifier_refs","unknown_refs","capability_need_refs","representation_candidates","evidence_bindings","currentness_basis"):
            _refs(getattr(self,n),n,n in {"entity_refs","currentness_basis"})
        if type(self.relations) is not tuple:raise SemanticScaffoldError("relations invalid")
        ids=set()
        for rel in self.relations:
            rel.validate()
            if rel.relation_id in ids:raise SemanticScaffoldError("duplicate relation")
            ids.add(rel.relation_id)
        if self.schema_id!=SCHEMA_ID or self.authority_effect!="NONE" or self.effect!="NONE":raise SemanticScaffoldError("SemanticScaffold cannot carry authority/effect")
        if require_digest:
            _hex(self.scaffold_digest,"scaffold_digest")
            if self.scaffold_digest!=self.compute_digest():raise SemanticScaffoldError("scaffold_digest mismatch")
        return self
    def sealed(self):return replace(self,scaffold_digest=self.compute_digest()).validate()

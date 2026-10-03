"""Canonical non-effectful QueryPlan bound to MissionIntent."""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json, re
from typing import Tuple

SCHEMA_ID="lion.query-plan/v1"; AUTHORITY_EFFECT="NONE"; EFFECT="NONE"
_SAFE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$"); _HEX=re.compile(r"^[0-9a-f]{64}$")
class QueryPlanError(ValueError): pass

def _id(v,n):
    if not isinstance(v,str) or _SAFE.fullmatch(v) is None: raise QueryPlanError(f"{n} invalid")
    return v
def _hex(v,n):
    if not isinstance(v,str) or _HEX.fullmatch(v) is None: raise QueryPlanError(f"{n} invalid")
    return v
def _refs(v,n,required=False):
    if type(v) is not tuple or (required and not v): raise QueryPlanError(f"{n} invalid")
    for x in v:_id(x,n)
    if len(v)!=len(set(v)): raise QueryPlanError(f"{n} must be unique")
    return v

@dataclass(frozen=True)
class QueryPlan:
    plan_id:str
    mission_intent_ref:str
    mission_intent_digest:str
    question_refs:Tuple[str,...]
    retrieval_semantics:Tuple[str,...]
    evidence_requirements:Tuple[str,...]
    scope:Tuple[str,...]
    budget_limit:int
    stop_conditions:Tuple[str,...]
    currentness_requirements:Tuple[str,...]
    plan_digest:str=""
    schema_id:str=SCHEMA_ID
    authority_effect:str="NONE"
    effect:str="NONE"

    def payload(self): d=asdict(self);d.pop("plan_digest",None);return d
    def compute_digest(self):
        return sha256(b"LION/QUERY-PLAN/1\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def validate(self,require_digest=True):
        _id(self.plan_id,"plan_id");_id(self.mission_intent_ref,"mission_intent_ref");_hex(self.mission_intent_digest,"mission_intent_digest")
        _refs(self.question_refs,"question_refs",True);_refs(self.retrieval_semantics,"retrieval_semantics",True)
        _refs(self.evidence_requirements,"evidence_requirements",True);_refs(self.scope,"scope",True)
        _refs(self.stop_conditions,"stop_conditions",True);_refs(self.currentness_requirements,"currentness_requirements",True)
        if isinstance(self.budget_limit,bool) or not isinstance(self.budget_limit,int) or self.budget_limit<1: raise QueryPlanError("budget_limit invalid")
        if self.schema_id!=SCHEMA_ID or self.authority_effect!="NONE" or self.effect!="NONE": raise QueryPlanError("QueryPlan cannot carry authority or effect")
        if require_digest:
            _hex(self.plan_digest,"plan_digest")
            if self.plan_digest!=self.compute_digest():raise QueryPlanError("plan_digest mismatch")
        return self
    def sealed(self):return replace(self,plan_digest=self.compute_digest()).validate()

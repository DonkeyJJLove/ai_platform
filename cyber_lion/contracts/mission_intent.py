"""Canonical non-effectful MissionIntent for LION v1.5."""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json, re
from typing import Tuple

SCHEMA_ID="lion.mission-intent/v1"
AUTHORITY_EFFECT="NONE"
EFFECT="NONE"
_SAFE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_HEX=re.compile(r"^[0-9a-f]{64}$")

class MissionIntentError(ValueError): pass

def _txt(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v: raise MissionIntentError(f"{n} invalid")
    return v

def _id(v,n):
    _txt(v,n)
    if _SAFE.fullmatch(v) is None: raise MissionIntentError(f"{n} invalid")
    return v

def _hex(v,n):
    if not isinstance(v,str) or _HEX.fullmatch(v) is None: raise MissionIntentError(f"{n} invalid")
    return v

def _refs(v,n,required=False):
    if type(v) is not tuple or (required and not v): raise MissionIntentError(f"{n} must be immutable tuple")
    for x in v: _id(x,n)
    if len(v)!=len(set(v)): raise MissionIntentError(f"{n} must be unique")
    return v

@dataclass(frozen=True)
class MissionIntent:
    intent_id:str
    mission_ref:str
    conversation_ref:str|None
    source_envelope_ref:str
    source_envelope_digest:str
    correlation_ref:str|None
    causation_ref:str|None
    causal_group_ref:str|None
    intent_class:str
    goal_ref:str
    goal_digest:str
    required_capabilities:Tuple[str,...]
    constraints:Tuple[str,...]
    preconditions:Tuple[str,...]
    evidence_requirements:Tuple[str,...]
    currentness_requirements:Tuple[str,...]
    next_representation:str
    intent_digest:str=""
    schema_id:str=SCHEMA_ID
    authority_effect:str="NONE"
    effect:str="NONE"

    def payload(self):
        d=asdict(self); d.pop("intent_digest",None); return d
    def compute_digest(self):
        raw=json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
        return sha256(b"LION/MISSION-INTENT/1\0"+raw).hexdigest()
    def validate(self,require_digest=True):
        for v,n in ((self.intent_id,"intent_id"),(self.mission_ref,"mission_ref"),
                    (self.source_envelope_ref,"source_envelope_ref"),(self.intent_class,"intent_class"),
                    (self.goal_ref,"goal_ref"),(self.next_representation,"next_representation")): _id(v,n)
        for v,n in ((self.conversation_ref,"conversation_ref"),(self.correlation_ref,"correlation_ref"),
                    (self.causation_ref,"causation_ref"),(self.causal_group_ref,"causal_group_ref")):
            if v is not None: _id(v,n)
        _hex(self.source_envelope_digest,"source_envelope_digest"); _hex(self.goal_digest,"goal_digest")
        _refs(self.required_capabilities,"required_capabilities")
        _refs(self.constraints,"constraints")
        _refs(self.preconditions,"preconditions")
        _refs(self.evidence_requirements,"evidence_requirements",required=True)
        _refs(self.currentness_requirements,"currentness_requirements",required=True)
        if self.schema_id!=SCHEMA_ID or self.authority_effect!="NONE" or self.effect!="NONE":
            raise MissionIntentError("MissionIntent cannot carry authority or effect")
        if require_digest:
            _hex(self.intent_digest,"intent_digest")
            if self.intent_digest!=self.compute_digest(): raise MissionIntentError("intent_digest mismatch")
        return self
    def sealed(self):
        return replace(self,intent_digest=self.compute_digest()).validate()

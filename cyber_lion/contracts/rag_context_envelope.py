"""Evidence/currentness envelope for retrieved context; never live truth."""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json,re
from typing import Tuple

SCHEMA_ID="lion.rag-context-envelope/v1";AUTHORITY_EFFECT="NONE";EFFECT="NONE"
CURRENTNESS=frozenset({"CURRENT","STALE","UNKNOWN","HISTORICAL","VERSIONED_STATIC"})
_SAFE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$");_HEX=re.compile(r"^[0-9a-f]{64}$")
class RagContextEnvelopeError(ValueError):pass

def _id(v,n):
    if not isinstance(v,str) or _SAFE.fullmatch(v) is None:raise RagContextEnvelopeError(f"{n} invalid")
    return v
def _hex(v,n):
    if not isinstance(v,str) or _HEX.fullmatch(v) is None:raise RagContextEnvelopeError(f"{n} invalid")
    return v
def _dt(v,n):
    if not isinstance(v,str) or not v:raise RagContextEnvelopeError(f"{n} invalid")
    try:d=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as e:raise RagContextEnvelopeError(f"{n} invalid") from e
    if d.tzinfo is None:raise RagContextEnvelopeError(f"{n} timezone required")
    return d.astimezone(timezone.utc)
def _refs(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise RagContextEnvelopeError(f"{n} invalid")
    for x in v:_id(x,n)
    if len(v)!=len(set(v)):raise RagContextEnvelopeError(f"{n} unique")
    return v

@dataclass(frozen=True)
class RagContextSource:
    source_ref:str
    content_digest:str
    currentness:str
    observed_at:str
    available_at:str
    provenance_refs:Tuple[str,...]
    def validate(self,input_cutoff:str):
        _id(self.source_ref,"source_ref");_hex(self.content_digest,"content_digest")
        if self.currentness not in CURRENTNESS:raise RagContextEnvelopeError("source currentness invalid")
        observed=_dt(self.observed_at,"observed_at");available=_dt(self.available_at,"available_at");cutoff=_dt(input_cutoff,"input_cutoff")
        if available<observed:raise RagContextEnvelopeError("available_at precedes observed_at")
        if available>cutoff:raise RagContextEnvelopeError("post-cutoff source denied")
        _refs(self.provenance_refs,"provenance_refs",True)
        return self

@dataclass(frozen=True)
class RagContextEnvelope:
    envelope_id:str
    query_plan_ref:str
    query_plan_digest:str
    knowledge_release_ref:str
    retrieval_time:str
    input_cutoff:str
    sources:Tuple[RagContextSource,...]
    context_digest:str=""
    schema_id:str=SCHEMA_ID
    authority_effect:str="NONE"
    effect:str="NONE"

    def payload(self):d=asdict(self);d.pop("context_digest",None);return d
    def compute_digest(self):
        return sha256(b"LION/RAG-CONTEXT/1\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def validate(self,require_digest=True):
        _id(self.envelope_id,"envelope_id");_id(self.query_plan_ref,"query_plan_ref");_hex(self.query_plan_digest,"query_plan_digest");_id(self.knowledge_release_ref,"knowledge_release_ref")
        retrieval=_dt(self.retrieval_time,"retrieval_time");cutoff=_dt(self.input_cutoff,"input_cutoff")
        if retrieval>cutoff:raise RagContextEnvelopeError("retrieval_time after input_cutoff")
        if type(self.sources) is not tuple or not self.sources:raise RagContextEnvelopeError("sources required")
        refs=set()
        for source in self.sources:
            source.validate(self.input_cutoff)
            if source.source_ref in refs:raise RagContextEnvelopeError("duplicate source_ref")
            refs.add(source.source_ref)
        if self.schema_id!=SCHEMA_ID or self.authority_effect!="NONE" or self.effect!="NONE":raise RagContextEnvelopeError("RAG context cannot carry authority or effect")
        if require_digest:
            _hex(self.context_digest,"context_digest")
            if self.context_digest!=self.compute_digest():raise RagContextEnvelopeError("context_digest mismatch")
        return self
    def sealed(self):return replace(self,context_digest=self.compute_digest()).validate()

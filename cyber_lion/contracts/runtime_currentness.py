"""Effect-time currentness contracts for F009.

These records prove that the authority, policy and observability state bound by one
RuntimeAdmission are still current immediately before bounded effect execution. They
are evidence only and mint no authority.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass
from datetime import datetime
from hashlib import sha256
import json,re
from typing import Any,Mapping

SCHEMA_VERSION="1.0.0"
_SHA256=re.compile(r"^[0-9a-f]{64}$")
_OBS={"HEALTHY","DEGRADED","LOST"}
class RuntimeCurrentnessContractError(ValueError):pass

def canonical_json(value:Mapping[str,Any])->bytes:return json.dumps(dict(value),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _text(v:Any,n:str,limit:int=2048)->str:
    if not isinstance(v,str) or not v.strip() or len(v)>limit or "\x00" in v:raise RuntimeCurrentnessContractError(f"{n} invalid")
    return v
def _digest(v:Any,n:str)->str:
    v=_text(v,n,64)
    if not _SHA256.fullmatch(v):raise RuntimeCurrentnessContractError(f"{n} must be sha256 hex")
    return v
def _utc(v:Any,n:str)->datetime:
    v=_text(v,n)
    try:d=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as exc:raise RuntimeCurrentnessContractError(f"{n} invalid") from exc
    if d.tzinfo is None:raise RuntimeCurrentnessContractError(f"{n} must be timezone-aware")
    return d

@dataclass(frozen=True)
class CurrentnessSourceTrustBinding:
    source_id:str;source_instance_id:str;source_implementation_digest:str;trust_anchor_id:str;trust_anchor_digest:str;schema_version:str=SCHEMA_VERSION
    def validate(self):
        if self.schema_version!=SCHEMA_VERSION:raise RuntimeCurrentnessContractError("unsupported currentness trust schema")
        for n in ("source_id","source_instance_id","trust_anchor_id"):_text(getattr(self,n),n)
        _digest(self.source_implementation_digest,"source_implementation_digest");_digest(self.trust_anchor_digest,"trust_anchor_digest");return self
    def binding(self):self.validate();return (self.source_id,self.source_instance_id,self.source_implementation_digest,self.trust_anchor_id,self.trust_anchor_digest)

@dataclass(frozen=True)
class EffectTimeCurrentnessEvidence:
    evidence_id:str;admission_digest:str;requested_effect_digest:str;runtime_identity_digest:str;live_authority_digest:str;authority_lineage_digest:str;policy_binding:str;observability_state:str;source_id:str;source_instance_id:str;source_implementation_digest:str;trust_anchor_id:str;trust_anchor_digest:str;observed_at:str;evidence_digest:str="";schema_version:str=SCHEMA_VERSION
    def canonical_dict(self,*,include_digest=True):
        self.validate(check_digest=False);d=asdict(self)
        if not include_digest:d.pop("evidence_digest")
        return d
    def compute_digest(self):return sha256(b"LION/F009-EFFECT-CURRENTNESS/1\0"+canonical_json(self.canonical_dict(include_digest=False))).hexdigest()
    def validate(self,*,check_digest=True):
        if self.schema_version!=SCHEMA_VERSION:raise RuntimeCurrentnessContractError("unsupported currentness evidence schema")
        for n in ("evidence_id","policy_binding","source_id","source_instance_id","trust_anchor_id"):_text(getattr(self,n),n)
        for n in ("admission_digest","requested_effect_digest","runtime_identity_digest","live_authority_digest","authority_lineage_digest","source_implementation_digest","trust_anchor_digest"):_digest(getattr(self,n),n)
        if self.observability_state not in _OBS:raise RuntimeCurrentnessContractError("invalid observability_state")
        _utc(self.observed_at,"observed_at")
        if check_digest:
            _digest(self.evidence_digest,"evidence_digest")
            if self.evidence_digest!=self.compute_digest():raise RuntimeCurrentnessContractError("evidence_digest mismatch")
        return self
    def sealed(self):self.validate(check_digest=False);return EffectTimeCurrentnessEvidence(**{**asdict(self),"evidence_digest":self.compute_digest()}).validate()

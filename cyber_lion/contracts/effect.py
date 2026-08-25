"""Generic effect identity, observation and reconciliation contracts.

These normalize existing effect-specific enforcement paths. They do not execute effects
and do not replace an effect-specific PEP/reference monitor.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass
from hashlib import sha256
import json,re
from typing import Tuple
_SHA64=re.compile(r"^[0-9a-f]{64}$")

class EffectContractError(ValueError):pass

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise EffectContractError(f"{n} invalid")
    return v
def _sha(v,n):
    _text(v,n)
    if not _SHA64.fullmatch(v):raise EffectContractError(f"{n} must be sha256")
def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise EffectContractError(f"{n} invalid")
    for x in v:_text(x,n)
    if len(set(v))!=len(v):raise EffectContractError(f"{n} duplicate")

def _digest(domain:bytes,obj)->str:
    raw=json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode();return sha256(domain+b"\0"+raw).hexdigest()

@dataclass(frozen=True)
class EffectContract:
    effect_id:str
    effect_class:str
    mission_id:str
    provider_class:str
    exact_effect_digest:str
    requested_authority:str
    authority_evidence_digest:str
    currentness_evidence_digest:str
    pep_identity_digest:str
    execution_identity_digest:str
    target:str
    payload_digest:str
    required_observer_ids:Tuple[str,...]
    required_observation_channels:Tuple[str,...]
    reconciliation_required:bool=True
    def validate(self):
        for n in ("effect_id","effect_class","mission_id","provider_class","requested_authority","target"):_text(getattr(self,n),n)
        for n in ("exact_effect_digest","authority_evidence_digest","currentness_evidence_digest","pep_identity_digest","execution_identity_digest","payload_digest"):_sha(getattr(self,n),n)
        _tuple(self.required_observer_ids,"required_observer_ids",True);_tuple(self.required_observation_channels,"required_observation_channels",True)
        if not self.reconciliation_required:raise EffectContractError("consequential effect must require reconciliation")
        return self
    def digest(self):self.validate();return _digest(b"LION/EFFECT-CONTRACT/1",self)

@dataclass(frozen=True)
class EffectObservation:
    observation_id:str
    effect_contract_digest:str
    observer_id:str
    observer_identity_digest:str
    observed_effect_digest:str
    channel:str
    observed_state_digest:str
    observed_at:str
    epistemic_state:str="OBSERVED"
    def validate(self):
        for n in ("observation_id","observer_id","channel","observed_at"):_text(getattr(self,n),n)
        for n in ("effect_contract_digest","observer_identity_digest","observed_effect_digest","observed_state_digest"):_sha(getattr(self,n),n)
        if self.epistemic_state!="OBSERVED":raise EffectContractError("effect observation cannot be inferred/simulated")
        return self
    def digest(self):self.validate();return _digest(b"LION/EFFECT-OBSERVATION/1",self)

@dataclass(frozen=True)
class EffectReconciliation:
    reconciliation_id:str
    effect_contract_digest:str
    expected_effect_digest:str
    observed_effect_digest:str
    observation_digests:Tuple[str,...]
    status:str
    reconciler_id:str
    reconciler_identity_digest:str
    reconciled_at:str
    def validate(self):
        for n in ("reconciliation_id","status","reconciler_id","reconciled_at"):_text(getattr(self,n),n)
        for n in ("effect_contract_digest","expected_effect_digest","observed_effect_digest","reconciler_identity_digest"):_sha(getattr(self,n),n)
        _tuple(self.observation_digests,"observation_digests",True)
        if self.status not in {"MATCH","MISMATCH","PARTIAL","UNKNOWN"}:raise EffectContractError("invalid reconciliation status")
        if self.status=="MATCH" and self.expected_effect_digest!=self.observed_effect_digest:raise EffectContractError("MATCH requires exact effect equality")
        if self.status!="MATCH" and self.expected_effect_digest==self.observed_effect_digest:raise EffectContractError("non-MATCH cannot hide exact equality")
        return self
    def digest(self):self.validate();return _digest(b"LION/EFFECT-RECONCILIATION/1",self)

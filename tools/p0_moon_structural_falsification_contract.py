from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json, re
from typing import Tuple

_SHA40=re.compile(r"^[0-9a-f]{40}$")
_SHA64=re.compile(r"^[0-9a-f]{64}$")
VERIFIER_DOMAIN=b"LION/MOON-STRUCTURAL-FALSIFICATION-VERIFIER/1"
OBSERVATION_DOMAIN=b"LION/MOON-STRUCTURAL-FALSIFICATION-OBSERVATION/1"
PLAN_DOMAIN=b"LION/MOON-STRUCTURAL-FALSIFICATION-PLAN/1"

class MoonStructuralFalsificationContractError(ValueError): pass

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v: raise MoonStructuralFalsificationContractError(f"{n} invalid")
    return v

def _sha40(v,n):
    _text(v,n)
    if _SHA40.fullmatch(v) is None: raise MoonStructuralFalsificationContractError(f"{n} must be git sha")
    return v

def _sha64(v,n):
    _text(v,n)
    if _SHA64.fullmatch(v) is None: raise MoonStructuralFalsificationContractError(f"{n} must be sha256")
    return v

def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v): raise MoonStructuralFalsificationContractError(f"{n} must be immutable tuple")
    for x in v: _text(x,n)
    if len(set(v))!=len(v): raise MoonStructuralFalsificationContractError(f"{n} must be unique")
    return v

def _digest(domain,obj):
    raw=json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode()
    return sha256(domain+b"\0"+raw).hexdigest()

@dataclass(frozen=True)
class StructuralFalsificationVerifierIdentity:
    revision:str
    tree_digest:str
    adapter_source_sha256:str
    production_pep_source_blob_sha:str
    verifier_name:str
    execution_class:str="STRUCTURAL_ONLY"
    def validate(self):
        _sha40(self.revision,"revision");_sha40(self.tree_digest,"tree_digest")
        _sha64(self.adapter_source_sha256,"adapter_source_sha256")
        _sha40(self.production_pep_source_blob_sha,"production_pep_source_blob_sha")
        _text(self.verifier_name,"verifier_name")
        if self.execution_class!="STRUCTURAL_ONLY": raise MoonStructuralFalsificationContractError("verifier must be structural-only")
        return self
    def digest(self): self.validate(); return _digest(VERIFIER_DOMAIN,self)

@dataclass(frozen=True)
class StructuralFalsificationObservation:
    attack_id:str
    inventory_digest:str
    surface_digest:str
    expected_pep_digest:str
    attempted_entrypoint:str
    candidate_digest:str
    observed_error:str
    verifier_identity_digest:str
    revision:str
    tree_digest:str
    epoch:str
    evidence_refs:Tuple[str,...]
    def validate(self):
        for n in ("attack_id","attempted_entrypoint","observed_error","epoch"): _text(getattr(self,n),n)
        for n in ("inventory_digest","surface_digest","expected_pep_digest","candidate_digest","verifier_identity_digest"): _sha64(getattr(self,n),n)
        _sha40(self.revision,"revision");_sha40(self.tree_digest,"tree_digest");_tuple(self.evidence_refs,"evidence_refs",True)
        return self
    def digest(self): self.validate(); return _digest(OBSERVATION_DOMAIN,self)

@dataclass(frozen=True)
class StructuralFalsificationPlan:
    inventory_digest:str
    attack_policy_digest:str
    verifier_identity_digest:str
    observation_digests:Tuple[str,...]
    bypass_result_digests:Tuple[str,...]
    surface_count:int
    attack_count:int
    global_status:str
    evidence_refs:Tuple[str,...]
    def validate(self):
        for n in ("inventory_digest","attack_policy_digest","verifier_identity_digest"): _sha64(getattr(self,n),n)
        _tuple(self.observation_digests,"observation_digests",True);_tuple(self.bypass_result_digests,"bypass_result_digests",True);_tuple(self.evidence_refs,"evidence_refs",True)
        for d in self.observation_digests+self.bypass_result_digests: _sha64(d,"artifact_digest")
        if type(self.surface_count) is not int or self.surface_count!=6: raise MoonStructuralFalsificationContractError("structural surface count must be six")
        if type(self.attack_count) is not int or self.attack_count!=24: raise MoonStructuralFalsificationContractError("structural attack count must be twenty-four")
        if len(self.observation_digests)!=24 or len(self.bypass_result_digests)!=24: raise MoonStructuralFalsificationContractError("exact structural matrix required")
        if self.global_status!="UNKNOWN": raise MoonStructuralFalsificationContractError("structural plan cannot globally promote")
        return self
    def digest(self): self.validate(); return _digest(PLAN_DOMAIN,self)

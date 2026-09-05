"""Evidence-only contract for the P0 production-surface closure campaign."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from hashlib import sha256
import json,re
from typing import Tuple

_SHA64=re.compile(r"^[0-9a-f]{64}$")
_RUNTIME=frozenset({"OBSERVED","UNKNOWN"})
_EVIDENCE=frozenset({"PRESENT","ABSENT"})
_CLOSURE=frozenset({"PARTIAL","UNKNOWN"})
_CARRIER=frozenset({"PRESENT","ABSENT"})

class SurfaceClosureCampaignContractError(ValueError):pass

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise SurfaceClosureCampaignContractError(f"{n} invalid")
    return v

def _sha(v,n):
    _text(v,n)
    if not _SHA64.fullmatch(v):raise SurfaceClosureCampaignContractError(f"{n} must be sha256")
    return v

def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise SurfaceClosureCampaignContractError(f"{n} must be immutable tuple")
    for x in v:_text(x,n)
    if len(set(v))!=len(v):raise SurfaceClosureCampaignContractError(f"{n} must be unique")
    return v

def _digest(domain,obj):
    raw=json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode("utf-8")
    return sha256(domain+b"\0"+raw).hexdigest()

@dataclass(frozen=True)
class SurfaceClosureWorkItem:
    surface_digest:str
    provider:str
    effect_class:str
    authority_class:str
    target_class:str
    entrypoint:str
    runtime_state:str
    runtime_evidence_refs:Tuple[str,...]
    binding_state:str
    chain_state:str
    bypass_state:str
    closure_status:str
    required_evidence:Tuple[str,...]
    priority:int
    def validate(self):
        _sha(self.surface_digest,"surface_digest")
        for n in ("provider","effect_class","authority_class","target_class","entrypoint"):_text(getattr(self,n),n)
        _tuple(self.runtime_evidence_refs,"runtime_evidence_refs");_tuple(self.required_evidence,"required_evidence",True)
        if self.runtime_state not in _RUNTIME:raise SurfaceClosureCampaignContractError("runtime_state invalid")
        for n in ("binding_state","chain_state","bypass_state"):
            if getattr(self,n) not in _EVIDENCE:raise SurfaceClosureCampaignContractError(f"{n} invalid")
        if self.closure_status not in _CLOSURE:raise SurfaceClosureCampaignContractError("closure_status invalid")
        if type(self.priority) is not int or self.priority not in {1,2,3}:raise SurfaceClosureCampaignContractError("priority invalid")
        if self.runtime_state=="OBSERVED" and not self.runtime_evidence_refs:raise SurfaceClosureCampaignContractError("OBSERVED requires runtime evidence")
        if self.runtime_state=="UNKNOWN" and self.runtime_evidence_refs:raise SurfaceClosureCampaignContractError("UNKNOWN cannot carry runtime evidence")
        if self.closure_status=="PARTIAL" and self.runtime_state!="OBSERVED":raise SurfaceClosureCampaignContractError("PARTIAL requires observed runtime trace")
        if self.binding_state=="PRESENT" or self.chain_state=="PRESENT" or self.bypass_state=="PRESENT":raise SurfaceClosureCampaignContractError("campaign planner cannot fabricate closure evidence")
        return self
    def digest(self):self.validate();return _digest(b"LION/P0-SURFACE-CLOSURE-WORK-ITEM/1",self)

@dataclass(frozen=True)
class ProviderFamilyClosurePlan:
    provider:str
    priority:int
    surface_digests:Tuple[str,...]
    observed_surface_digests:Tuple[str,...]
    effect_classes:Tuple[str,...]
    authority_classes:Tuple[str,...]
    target_classes:Tuple[str,...]
    shared_requirements:Tuple[str,...]
    def validate(self):
        _text(self.provider,"provider")
        if type(self.priority) is not int or self.priority not in {1,2,3}:raise SurfaceClosureCampaignContractError("priority invalid")
        for n in ("surface_digests","effect_classes","authority_classes","target_classes","shared_requirements"):_tuple(getattr(self,n),n,True)
        _tuple(self.observed_surface_digests,"observed_surface_digests")
        for d in self.surface_digests:self._check_sha(d,"surface_digest")
        for d in self.observed_surface_digests:self._check_sha(d,"observed_surface_digest")
        if set(self.observed_surface_digests)-set(self.surface_digests):raise SurfaceClosureCampaignContractError("observed surface outside provider family")
        return self
    @staticmethod
    def _check_sha(v,n):_sha(v,n)
    def digest(self):self.validate();return _digest(b"LION/P0-PROVIDER-FAMILY-CLOSURE-PLAN/1",self)

@dataclass(frozen=True)
class SurfaceClosureCampaign:
    repository:str
    revision:str
    tree_digest:str
    inventory_digest:str
    scan_digest:str
    total_surface_count:int
    remaining_surface_count:int
    excluded_surface_digests:Tuple[str,...]
    work_items:Tuple[SurfaceClosureWorkItem,...]
    provider_families:Tuple[ProviderFamilyClosurePlan,...]
    first_safe_batch_digests:Tuple[str,...]
    live_falsification_carrier_state:str
    evidence_refs:Tuple[str,...]
    global_status:str
    def validate(self):
        for n in ("repository","revision","tree_digest"):_text(getattr(self,n),n)
        _sha(self.inventory_digest,"inventory_digest");_sha(self.scan_digest,"scan_digest")
        if type(self.total_surface_count) is not int or self.total_surface_count<0 or type(self.remaining_surface_count) is not int or self.remaining_surface_count<0:raise SurfaceClosureCampaignContractError("counts invalid")
        _tuple(self.excluded_surface_digests,"excluded_surface_digests");_tuple(self.first_safe_batch_digests,"first_safe_batch_digests",True);_tuple(self.evidence_refs,"evidence_refs",True)
        for d in self.excluded_surface_digests:_sha(d,"excluded_surface_digest")
        if type(self.work_items) is not tuple or type(self.provider_families) is not tuple:raise SurfaceClosureCampaignContractError("campaign members must be tuples")
        for x in self.work_items:x.validate()
        for x in self.provider_families:x.validate()
        work={x.surface_digest:x for x in self.work_items}
        if len(work)!=len(self.work_items) or len(work)!=self.remaining_surface_count:raise SurfaceClosureCampaignContractError("work-item cardinality mismatch")
        if self.total_surface_count!=self.remaining_surface_count+len(self.excluded_surface_digests):raise SurfaceClosureCampaignContractError("surface cardinality mismatch")
        if set(self.excluded_surface_digests)&set(work):raise SurfaceClosureCampaignContractError("excluded surface remains in work matrix")
        if set(self.first_safe_batch_digests)-set(work):raise SurfaceClosureCampaignContractError("first batch outside work matrix")
        if any(work[d].runtime_state!="OBSERVED" for d in self.first_safe_batch_digests):raise SurfaceClosureCampaignContractError("first batch requires observed runtime trace")
        family_surfaces=[d for f in self.provider_families for d in f.surface_digests]
        if len(family_surfaces)!=len(set(family_surfaces)) or set(family_surfaces)!=set(work):raise SurfaceClosureCampaignContractError("provider family coverage mismatch")
        if self.live_falsification_carrier_state not in _CARRIER:raise SurfaceClosureCampaignContractError("live falsification carrier state invalid")
        if self.global_status!="UNKNOWN":raise SurfaceClosureCampaignContractError("campaign cannot promote global status")
        if any(x.closure_status not in {"PARTIAL","UNKNOWN"} for x in self.work_items):raise SurfaceClosureCampaignContractError("campaign cannot synthesize MEDIATED")
        return self
    def digest(self):self.validate();return _digest(b"LION/P0-SURFACE-CLOSURE-CAMPAIGN/1",self)

"""Evidence-only contracts for E006 R9C production mediation closure."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from hashlib import sha256
import json,re
from typing import Tuple

_SHA64=re.compile(r"^[0-9a-f]{64}$")
_EPISTEMIC=frozenset({"OBSERVED","UNKNOWN","CONFLICTED"})
_STATUSES=frozenset({"MEDIATED","UNMEDIATED","PARTIAL","UNKNOWN"})
_REASONS=frozenset({"dynamic-dispatch","dynamic-SQL","dynamic-path","unresolved-provider","unresolved-backend","unresolved-network-method","unresolved-workflow-effect","unsupported-language","syntax-error","ambiguous-effect-class"})
class ProductionMediationContractError(ValueError):pass

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise ProductionMediationContractError(f"{n} invalid")
    return v
def _sha(v,n):
    _text(v,n)
    if not _SHA64.fullmatch(v):raise ProductionMediationContractError(f"{n} must be sha256")
    return v
def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise ProductionMediationContractError(f"{n} must be immutable tuple")
    for x in v:_text(x,n)
    return v
def _digest(domain,obj):
    raw=json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode()
    return sha256(domain+b"\0"+raw).hexdigest()

@dataclass(frozen=True)
class ProductionEffectTrace:
    trace_id:str;inventory_digest:str;surface_digest:str;source_entrypoint:str;call_path:Tuple[str,...];consequential_primitive:str;effect_class:str;provider_identity:str;target_identity:str;source_refs:Tuple[str,...];runtime_evidence_refs:Tuple[str,...];epistemic_state:str
    def validate(self):
        for n in ("trace_id","source_entrypoint","consequential_primitive","effect_class","provider_identity","target_identity"):_text(getattr(self,n),n)
        _sha(self.inventory_digest,"inventory_digest");_sha(self.surface_digest,"surface_digest");_tuple(self.call_path,"call_path",True);_tuple(self.source_refs,"source_refs",True);_tuple(self.runtime_evidence_refs,"runtime_evidence_refs")
        if self.epistemic_state not in _EPISTEMIC:raise ProductionMediationContractError("invalid epistemic state")
        if self.epistemic_state=="OBSERVED" and not self.runtime_evidence_refs:raise ProductionMediationContractError("OBSERVED trace requires runtime evidence")
        return self
    def digest(self):self.validate();return _digest(b"LION/PRODUCTION-EFFECT-TRACE/1",self)

@dataclass(frozen=True)
class MediationChainEvidence:
    surface_digest:str;trace_digest:str;effect_contract_digest:str;authority_source_digest:str;currentness_source_digest:str;pep_identity_digest:str;execution_boundary_digest:str;replay_guard_digest:str;bounded_scope_digest:str;observer_identity_digests:Tuple[str,...];reconciliation_boundary_digest:str;evidence_refs:Tuple[str,...];verifier_identity_digest:str;epoch:str
    def validate(self):
        for n in ("surface_digest","trace_digest","effect_contract_digest","authority_source_digest","currentness_source_digest","pep_identity_digest","execution_boundary_digest","replay_guard_digest","bounded_scope_digest","reconciliation_boundary_digest","verifier_identity_digest"):_sha(getattr(self,n),n)
        _tuple(self.observer_identity_digests,"observer_identity_digests",True);_tuple(self.evidence_refs,"evidence_refs",True)
        for x in self.observer_identity_digests:_sha(x,"observer_identity_digest")
        _text(self.epoch,"epoch");return self
    def digest(self):self.validate();return _digest(b"LION/MEDIATION-CHAIN-EVIDENCE/1",self)

@dataclass(frozen=True)
class MediationClosureRecord:
    surface_digest:str;inventory_digest:str;binding_digest:str;trace_digest:str;bypass_result_digests:Tuple[str,...];status:str;evidence_refs:Tuple[str,...]
    def validate(self):
        for n in ("surface_digest","inventory_digest","trace_digest"):_sha(getattr(self,n),n)
        if self.binding_digest:_sha(self.binding_digest,"binding_digest")
        _tuple(self.bypass_result_digests,"bypass_result_digests");_tuple(self.evidence_refs,"evidence_refs")
        for x in self.bypass_result_digests:_sha(x,"bypass_result_digest")
        if self.status not in _STATUSES:raise ProductionMediationContractError("invalid closure status")
        if self.status=="MEDIATED" and (not self.binding_digest or not self.bypass_result_digests or not self.evidence_refs):raise ProductionMediationContractError("MEDIATED requires complete evidence")
        return self

@dataclass(frozen=True)
class UnclassifiedEffectRecord:
    source_ref:str;call_expression:str;reason:str;epistemic_state:str="UNKNOWN"
    def validate(self):
        _text(self.source_ref,"source_ref");_text(self.call_expression,"call_expression")
        if self.reason not in _REASONS:raise ProductionMediationContractError("invalid unclassified reason")
        if self.epistemic_state!="UNKNOWN":raise ProductionMediationContractError("unclassified effect must remain UNKNOWN")
        return self

@dataclass(frozen=True)
class GlobalMediationClosureReport:
    inventory_digest:str;total_production_surfaces:int;mediated_count:int;partial_count:int;unmediated_count:int;unknown_count:int;unclassified_count:int;bypass_attempt_count:int;bypass_denied_count:int;bypass_reached_effect_count:int;evidence_refs:Tuple[str,...];independent_verifier_identity:str;global_status:str
    def validate(self):
        _sha(self.inventory_digest,"inventory_digest");_tuple(self.evidence_refs,"evidence_refs");_text(self.independent_verifier_identity,"independent_verifier_identity")
        nums=(self.total_production_surfaces,self.mediated_count,self.partial_count,self.unmediated_count,self.unknown_count,self.unclassified_count,self.bypass_attempt_count,self.bypass_denied_count,self.bypass_reached_effect_count)
        if any(type(x) is not int or x<0 for x in nums):raise ProductionMediationContractError("counts must be non-negative integers")
        if self.mediated_count+self.partial_count+self.unmediated_count+self.unknown_count!=self.total_production_surfaces:raise ProductionMediationContractError("surface counts inconsistent")
        if self.global_status not in {"PASS","UNKNOWN"}:raise ProductionMediationContractError("invalid global status")
        if self.global_status=="PASS" and (not self.total_production_surfaces or self.partial_count or self.unmediated_count or self.unknown_count or self.unclassified_count or self.bypass_reached_effect_count or self.bypass_attempt_count!=self.bypass_denied_count or not self.evidence_refs):raise ProductionMediationContractError("PASS requires closed production matrix")
        return self

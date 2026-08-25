"""Evidence-only contracts for E006 R9B mediation binding and bypass falsification."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json,re
from typing import Tuple

_SHA64=re.compile(r"^[0-9a-f]{64}$")
_EPISTEMIC=frozenset({"OBSERVED","UNKNOWN","CONFLICTED"})
_OUTCOMES=frozenset({"DENIED","REACHED_EFFECT","UNKNOWN"})

class MediationFalsificationContractError(ValueError):pass

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise MediationFalsificationContractError(f"{n} invalid")
    return v

def _sha(v,n):
    _text(v,n)
    if not _SHA64.fullmatch(v):raise MediationFalsificationContractError(f"{n} must be sha256")
    return v

def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise MediationFalsificationContractError(f"{n} must be immutable tuple")
    for x in v:_text(x,n)
    if len(set(v))!=len(v):raise MediationFalsificationContractError(f"{n} must be unique")
    return v

def _digest(domain,obj):
    raw=json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode()
    return sha256(domain+b"\0"+raw).hexdigest()

@dataclass(frozen=True)
class MediationBindingCandidate:
    inventory_digest:str
    surface_digest:str
    effect_contract_digest:str
    pep_identity_digest:str
    authority_source_digest:str
    currentness_source_digest:str
    execution_boundary_digest:str
    replay_guard_digest:str
    observer_identity_digests:Tuple[str,...]
    reconciliation_boundary_digest:str
    provider_identity:str
    entrypoint_ref:str
    evidence_refs:Tuple[str,...]
    epoch:str
    def validate(self):
        for n in ("inventory_digest","surface_digest","effect_contract_digest","pep_identity_digest","authority_source_digest","currentness_source_digest","execution_boundary_digest","replay_guard_digest","reconciliation_boundary_digest"):_sha(getattr(self,n),n)
        for n in ("provider_identity","entrypoint_ref","epoch"):_text(getattr(self,n),n)
        _tuple(self.observer_identity_digests,"observer_identity_digests",True);_tuple(self.evidence_refs,"evidence_refs",True)
        for d in self.observer_identity_digests:_sha(d,"observer_identity_digest")
        return self
    def digest(self):self.validate();return _digest(b"LION/MEDIATION-BINDING-CANDIDATE/1",self)

@dataclass(frozen=True)
class BypassFalsificationResult:
    attack_id:str
    inventory_digest:str
    surface_digest:str
    attempted_entrypoint:str
    expected_pep_digest:str
    observed_outcome:str
    evidence_refs:Tuple[str,...]
    verifier_identity_digest:str
    epistemic_state:str
    epoch:str
    def validate(self):
        for n in ("attack_id","attempted_entrypoint","epoch"):_text(getattr(self,n),n)
        for n in ("inventory_digest","surface_digest","expected_pep_digest","verifier_identity_digest"):_sha(getattr(self,n),n)
        _tuple(self.evidence_refs,"evidence_refs",True)
        if self.observed_outcome not in _OUTCOMES:raise MediationFalsificationContractError("invalid observed outcome")
        if self.epistemic_state not in _EPISTEMIC:raise MediationFalsificationContractError("invalid epistemic state")
        if self.observed_outcome in {"DENIED","REACHED_EFFECT"} and self.epistemic_state!="OBSERVED":raise MediationFalsificationContractError("terminal bypass outcome must be observed")
        return self
    def digest(self):self.validate();return _digest(b"LION/BYPASS-FALSIFICATION/1",self)

@dataclass(frozen=True)
class MediationReassessment:
    inventory_digest:str
    surface_statuses:Tuple[Tuple[str,str],...]
    global_status:str
    evidence_refs:Tuple[str,...]
    def validate(self):
        _sha(self.inventory_digest,"inventory_digest");_tuple(self.evidence_refs,"evidence_refs")
        if type(self.surface_statuses) is not tuple:raise MediationFalsificationContractError("surface_statuses must be tuple")
        seen=set()
        for item in self.surface_statuses:
            if type(item) is not tuple or len(item)!=2:raise MediationFalsificationContractError("invalid surface status entry")
            sd,status=item;_sha(sd,"surface_digest")
            if sd in seen:raise MediationFalsificationContractError("duplicate surface status")
            seen.add(sd)
            if status not in {"MEDIATED","UNMEDIATED","PARTIAL","UNKNOWN"}:raise MediationFalsificationContractError("invalid surface status")
        if self.global_status not in {"PASS","UNKNOWN"}:raise MediationFalsificationContractError("invalid global status")
        if self.global_status=="PASS" and (not self.surface_statuses or any(s!="MEDIATED" for _,s in self.surface_statuses) or not self.evidence_refs):raise MediationFalsificationContractError("PASS requires complete mediated evidence")
        return self

"""Canonical contracts for consequential effect-surface inventory and mediation assessment.

These contracts are descriptive and evidentiary only.  They cannot execute an effect,
grant authority, select a PEP, or promote UNKNOWN to PASS without explicit bindings.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json,re
from typing import Tuple

_SHA64=re.compile(r"^[0-9a-f]{64}$")
STATUSES=frozenset({"MEDIATED","UNMEDIATED","PARTIAL","UNKNOWN","NON_CONSEQUENTIAL"})
EPISTEMIC=frozenset({"OBSERVED","UNKNOWN","CONFLICTED"})

class CompleteMediationContractError(ValueError):pass

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise CompleteMediationContractError(f"{n} invalid")
    return v

def _sha(v,n):
    _text(v,n)
    if not _SHA64.fullmatch(v):raise CompleteMediationContractError(f"{n} must be sha256")
    return v

def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise CompleteMediationContractError(f"{n} must be immutable tuple")
    for x in v:_text(x,n)
    if len(set(v))!=len(v):raise CompleteMediationContractError(f"{n} must be unique")
    return v

def _digest(domain,obj):
    raw=json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode()
    return sha256(domain+b"\0"+raw).hexdigest()

@dataclass(frozen=True)
class ConsequentialEffectSurface:
    surface_id:str
    effect_class:str
    implementation_refs:Tuple[str,...]
    entrypoints:Tuple[str,...]
    effect_provider:str
    target_class:str
    mutation_kind:str
    authority_class:str
    currentness_requirement:str
    pep_required:bool
    observer_required:bool
    reconciliation_required:bool
    evidence_refs:Tuple[str,...]
    epistemic_state:str
    def validate(self):
        for n in ("surface_id","effect_class","effect_provider","target_class","mutation_kind","authority_class","currentness_requirement"):_text(getattr(self,n),n)
        for n in ("implementation_refs","entrypoints","evidence_refs"):_tuple(getattr(self,n),n,True)
        if self.epistemic_state not in EPISTEMIC:raise CompleteMediationContractError("invalid epistemic state")
        if not all(type(getattr(self,n)) is bool for n in ("pep_required","observer_required","reconciliation_required")):raise CompleteMediationContractError("mediation flags must be bool")
        return self
    def digest(self):self.validate();return _digest(b"LION/CONSEQUENTIAL-EFFECT-SURFACE/1",self)

@dataclass(frozen=True)
class MediationBinding:
    surface_digest:str
    effect_contract_digest:str
    pep_identity_digest:str
    authority_source_digest:str
    currentness_source_digest:str
    execution_boundary_digest:str
    observer_identity_digests:Tuple[str,...]
    reconciliation_boundary_digest:str
    evidence_refs:Tuple[str,...]
    def validate(self):
        for n in ("surface_digest","effect_contract_digest","pep_identity_digest","authority_source_digest","currentness_source_digest","execution_boundary_digest","reconciliation_boundary_digest"):_sha(getattr(self,n),n)
        _tuple(self.observer_identity_digests,"observer_identity_digests",True);_tuple(self.evidence_refs,"evidence_refs",True)
        for d in self.observer_identity_digests:_sha(d,"observer_identity_digest")
        return self
    def digest(self):self.validate();return _digest(b"LION/MEDIATION-BINDING/1",self)

@dataclass(frozen=True)
class CompleteMediationMatrixEntry:
    surface_digest:str
    status:str
    binding_digest:str
    rationale:str
    evidence_refs:Tuple[str,...]
    def validate(self):
        _sha(self.surface_digest,"surface_digest");_text(self.rationale,"rationale");_tuple(self.evidence_refs,"evidence_refs",True)
        if self.status not in STATUSES:raise CompleteMediationContractError("invalid matrix status")
        if self.status=="MEDIATED":_sha(self.binding_digest,"binding_digest")
        elif self.binding_digest: _sha(self.binding_digest,"binding_digest")
        return self

@dataclass(frozen=True)
class EffectSurfaceInventory:
    repository:str
    revision:str
    tree_digest:str
    scan_digest:str
    surfaces:Tuple[ConsequentialEffectSurface,...]
    unclassified_refs:Tuple[str,...]
    evidence_refs:Tuple[str,...]
    def validate(self):
        for n in ("repository","revision","tree_digest"):_text(getattr(self,n),n)
        _sha(self.scan_digest,"scan_digest");_tuple(self.unclassified_refs,"unclassified_refs");_tuple(self.evidence_refs,"evidence_refs",True)
        if type(self.surfaces) is not tuple:raise CompleteMediationContractError("surfaces must be tuple")
        for s in self.surfaces:s.validate()
        if len({s.surface_id for s in self.surfaces})!=len(self.surfaces):raise CompleteMediationContractError("duplicate surface id")
        return self
    def digest(self):self.validate();return _digest(b"LION/EFFECT-SURFACE-INVENTORY/1",self)

@dataclass(frozen=True)
class CompleteMediationAssessment:
    inventory_digest:str
    matrix:Tuple[CompleteMediationMatrixEntry,...]
    global_status:str
    falsification_evidence_refs:Tuple[str,...]
    observation_evidence_refs:Tuple[str,...]
    def validate(self):
        _sha(self.inventory_digest,"inventory_digest")
        _tuple(self.falsification_evidence_refs,"falsification_evidence_refs")
        _tuple(self.observation_evidence_refs,"observation_evidence_refs")
        if type(self.matrix) is not tuple:raise CompleteMediationContractError("matrix must be tuple")
        for e in self.matrix:e.validate()
        if self.global_status not in {"PASS","UNKNOWN"}:raise CompleteMediationContractError("global status must be PASS or UNKNOWN")
        if self.global_status=="PASS":
            if not self.falsification_evidence_refs or not self.observation_evidence_refs:
                raise CompleteMediationContractError("PASS requires independent falsification and observation evidence")
            if not self.matrix or any(e.status!="MEDIATED" for e in self.matrix):
                raise CompleteMediationContractError("PASS requires every matrix entry MEDIATED")
        return self

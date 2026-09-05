"""Evidence-only contracts for conservative effect-taxonomy reconciliation.

Raw scanner UNKNOWN entries are never silently discarded. A resolution record must
carry structural proof. Alias resolutions preserve the consequential target surface.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json,re
from typing import Tuple

_SHA64=re.compile(r"^[0-9a-f]{64}$")
_KINDS=frozenset({"NON_CONSEQUENTIAL_READ_ONLY","MEDIATION_GATE_ALIAS","EFFECT_ALIAS"})
class EffectTaxonomyContractError(ValueError):pass

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise EffectTaxonomyContractError(f"{n} invalid")
    return v

def _sha(v,n):
    _text(v,n)
    if not _SHA64.fullmatch(v):raise EffectTaxonomyContractError(f"{n} must be sha256")
    return v

def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise EffectTaxonomyContractError(f"{n} must be immutable tuple")
    for x in v:_text(x,n)
    if len(set(v))!=len(v):raise EffectTaxonomyContractError(f"{n} must be unique")
    return v

def _digest(domain,obj):
    raw=json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode()
    return sha256(domain+b"\0"+raw).hexdigest()

@dataclass(frozen=True)
class EffectTaxonomyResolution:
    source_ref:str
    resolution_kind:str
    target_surface_digest:str
    target_entrypoint:str
    proof_refs:Tuple[str,...]
    epistemic_state:str="OBSERVED"
    def validate(self):
        _text(self.source_ref,"source_ref");_tuple(self.proof_refs,"proof_refs",True)
        if self.resolution_kind not in _KINDS:raise EffectTaxonomyContractError("resolution kind invalid")
        if self.epistemic_state!="OBSERVED":raise EffectTaxonomyContractError("resolution must be OBSERVED")
        if self.resolution_kind=="NON_CONSEQUENTIAL_READ_ONLY":
            if self.target_surface_digest or self.target_entrypoint:raise EffectTaxonomyContractError("read-only resolution cannot target effect")
        else:
            _sha(self.target_surface_digest,"target_surface_digest");_text(self.target_entrypoint,"target_entrypoint")
        return self
    def digest(self):self.validate();return _digest(b"LION/EFFECT-TAXONOMY-RESOLUTION/1",self)

@dataclass(frozen=True)
class EffectTaxonomyReconciliationReport:
    raw_inventory_digest:str
    reconciled_inventory_digest:str
    resolution_digests:Tuple[str,...]
    unresolved_refs:Tuple[str,...]
    status:str
    def validate(self):
        _sha(self.raw_inventory_digest,"raw_inventory_digest");_sha(self.reconciled_inventory_digest,"reconciled_inventory_digest")
        _tuple(self.resolution_digests,"resolution_digests");_tuple(self.unresolved_refs,"unresolved_refs")
        for d in self.resolution_digests:_sha(d,"resolution_digest")
        if self.status not in {"PASS","UNKNOWN"}:raise EffectTaxonomyContractError("status invalid")
        if self.status=="PASS" and self.unresolved_refs:raise EffectTaxonomyContractError("PASS cannot retain unresolved refs")
        if self.status=="UNKNOWN" and not self.unresolved_refs:raise EffectTaxonomyContractError("UNKNOWN requires unresolved refs")
        return self
    def digest(self):self.validate();return _digest(b"LION/EFFECT-TAXONOMY-RECONCILIATION/1",self)

"""Gap-derived capability requirements. Descriptive only; never build authority."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json,re
from typing import Tuple
from .bean import BeanContractError
from .evolutionary_state import Gap
_SHA256=re.compile(r"^[0-9a-f]{64}$")

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v: raise BeanContractError(f"{n} invalid")
    return v

def _sha(v,n):
    _text(v,n)
    if not _SHA256.fullmatch(v): raise BeanContractError(f"{n} must be sha256")

def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v): raise BeanContractError(f"{n} must be immutable tuple")
    for x in v:_text(x,n)
    if len(set(v))!=len(v): raise BeanContractError(f"{n} must be unique")

@dataclass(frozen=True)
class CapabilityNeed:
    need_id:str
    gap_digest:str
    goal_digest:str
    required_capability:str
    required_inputs:Tuple[str,...]
    required_outputs:Tuple[str,...]
    acceptance_conditions:Tuple[str,...]
    falsification_conditions:Tuple[str,...]
    required_observability:Tuple[str,...]
    authority_ceiling:str
    provenance_refs:Tuple[str,...]
    derivation_reason:str
    authority_effect:str="NONE"
    execution_effect:str="NONE"
    external_effect:str="NONE"
    def validate(self):
        for n in ("need_id","required_capability","authority_ceiling","derivation_reason"):_text(getattr(self,n),n)
        _sha(self.gap_digest,"gap_digest");_sha(self.goal_digest,"goal_digest")
        for n in ("required_inputs","required_outputs","acceptance_conditions","falsification_conditions","required_observability","provenance_refs"):_tuple(getattr(self,n),n,n in {"acceptance_conditions","falsification_conditions","provenance_refs"})
        for n in ("authority_effect","execution_effect","external_effect"):
            if getattr(self,n)!="NONE": raise BeanContractError(f"CapabilityNeed cannot carry {n}")
        if self.authority_ceiling!="none" and not self.required_observability: raise BeanContractError("nonzero authority ceiling requires observability")
        return self
    def digest(self):
        self.validate();raw=json.dumps(asdict(self),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
        return sha256(b"LION/CAPABILITY-NEED/1\0"+raw).hexdigest()

def derive_capability_needs(*,gap:Gap,goal_digest:str,capability_requirements:Tuple[Tuple[str,Tuple[str,...],Tuple[str,...],str],...],provenance_refs:Tuple[str,...])->Tuple[CapabilityNeed,...]:
    """Mechanically bind declared missing capabilities to exact Gap; no solution selection."""
    gap.validate();_sha(goal_digest,"goal_digest")
    if goal_digest!=gap.goal_digest: raise BeanContractError("goal substitution detected")
    missing=set(gap.missing_capabilities)
    if not capability_requirements and missing: raise BeanContractError("missing capability requirements cannot be silently omitted")
    seen=set();out=[]
    for capability,inputs,outputs,ceiling in capability_requirements:
        _text(capability,"capability")
        if capability not in missing: raise BeanContractError("CapabilityNeed must derive from explicit Gap missing_capabilities")
        if capability in seen: raise BeanContractError("duplicate CapabilityNeed")
        seen.add(capability)
        need=CapabilityNeed(need_id=f"need:{gap.gap_id}:{capability}",gap_digest=gap.digest(),goal_digest=goal_digest,required_capability=capability,required_inputs=inputs,required_outputs=outputs,acceptance_conditions=gap.unsatisfied_conditions,falsification_conditions=gap.falsification_conditions,required_observability=("pre-state","post-state") if ceiling!="none" else (),authority_ceiling=ceiling,provenance_refs=provenance_refs,derivation_reason=f"explicit missing capability in {gap.gap_id}").validate();out.append(need)
    if seen!=missing: raise BeanContractError("silent capability substitution/omission denied")
    return tuple(sorted(out,key=lambda n:n.required_capability))

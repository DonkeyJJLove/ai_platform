"""Heterogeneous time-bounded organizational Mosaic over admitted Bean bindings."""
from __future__ import annotations
from dataclasses import asdict,dataclass,replace
from hashlib import sha256
import json
from typing import Tuple
from .bean import BeanContractError
from .bean_composition import CompositionContract

MOSAIC_LIFECYCLE=("FORM","ATTEST","OPERATE","OBSERVE","RECONCILE","DISSOLVE")

@dataclass(frozen=True)
class MosaicMember:
    bean_id:str
    bean_type:str
    spec_digest:str
    implementation_digest:str
    role:str
    def validate(self):
        if not all(isinstance(x,str) and x for x in (self.bean_id,self.bean_type,self.spec_digest,self.implementation_digest,self.role)):raise BeanContractError("mosaic member invalid")
        return self

@dataclass(frozen=True)
class MosaicCell:
    mosaic_id:str
    mission_id:str
    composition_digest:str
    members:Tuple[MosaicMember,...]
    lifecycle_state:str
    authority_ceiling:str
    verifier_bean_ids:Tuple[str,...]
    observer_bean_ids:Tuple[str,...]
    evidence_refs:Tuple[str,...]
    attestation_refs:Tuple[str,...]=()
    operation_refs:Tuple[str,...]=()
    observation_refs:Tuple[str,...]=()
    reconciliation_refs:Tuple[str,...]=()
    dissolved_reason:str=""
    authority_effect:str="NONE"
    def validate(self):
        if not self.mosaic_id or not self.mission_id or not self.composition_digest:raise BeanContractError("mosaic identity required")
        if type(self.members) is not tuple or not self.members:raise BeanContractError("mosaic members required")
        for m in self.members:m.validate()
        ids={m.bean_id for m in self.members}
        if len(ids)!=len(self.members):raise BeanContractError("duplicate mosaic member")
        if self.lifecycle_state not in MOSAIC_LIFECYCLE:raise BeanContractError("invalid mosaic lifecycle")
        if not set(self.verifier_bean_ids)<=ids or not set(self.observer_bean_ids)<=ids:raise BeanContractError("mosaic role binding invalid")
        if type(self.evidence_refs) is not tuple or not self.evidence_refs:raise BeanContractError("mosaic evidence required")
        if self.authority_effect!="NONE":raise BeanContractError("Mosaic organization cannot mint authority")
        index=MOSAIC_LIFECYCLE.index(self.lifecycle_state)
        required=(self.attestation_refs,self.operation_refs,self.observation_refs,self.reconciliation_refs)
        for i,refs in enumerate(required,start=1):
            if index>=i and not refs:raise BeanContractError(f"lifecycle {self.lifecycle_state} requires prior-stage evidence")
        if self.lifecycle_state=="DISSOLVE" and not self.dissolved_reason:raise BeanContractError("DISSOLVE requires reason")
        return self
    def digest(self):
        self.validate();raw=json.dumps(asdict(self),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode();return sha256(b"LION/MOSAIC-CELL/1\0"+raw).hexdigest()

def form_mosaic(*,mosaic_id:str,composition:CompositionContract,member_types:Tuple[Tuple[str,str,str],...],evidence_refs:Tuple[str,...])->MosaicCell:
    """member_types tuples are (bean_id, bean_type, role); spec/impl come only from sealed composition."""
    composition.validate();declared={bid:(btype,role) for bid,btype,role in member_types}
    if set(declared)!={b.bean_id for b in composition.bean_bindings}:raise BeanContractError("mosaic membership substitution/omission denied")
    members=tuple(sorted((MosaicMember(b.bean_id,declared[b.bean_id][0],b.spec_digest,b.implementation_digest,declared[b.bean_id][1]).validate() for b in composition.bean_bindings),key=lambda m:m.bean_id))
    return MosaicCell(mosaic_id,composition.mission_id,composition.digest(),members,"FORM",composition.authority_ceiling,composition.verifier_bean_ids,composition.observer_bean_ids,evidence_refs).validate()

def advance_mosaic(cell:MosaicCell,next_state:str,*,evidence_refs:Tuple[str,...],reason:str="")->MosaicCell:
    cell.validate()
    current=MOSAIC_LIFECYCLE.index(cell.lifecycle_state)
    if current+1>=len(MOSAIC_LIFECYCLE) or MOSAIC_LIFECYCLE[current+1]!=next_state:raise BeanContractError("mosaic lifecycle skip/replay denied")
    kwargs={}
    if next_state=="ATTEST":kwargs["attestation_refs"]=evidence_refs
    elif next_state=="OPERATE":kwargs["operation_refs"]=evidence_refs
    elif next_state=="OBSERVE":kwargs["observation_refs"]=evidence_refs
    elif next_state=="RECONCILE":kwargs["reconciliation_refs"]=evidence_refs
    elif next_state=="DISSOLVE":kwargs["dissolved_reason"]=reason
    return replace(cell,lifecycle_state=next_state,**kwargs).validate()

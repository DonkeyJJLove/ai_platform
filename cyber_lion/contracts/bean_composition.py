"""Deterministic, non-authoritative composition contracts for heterogeneous Beans."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Tuple

from .bean import BeanContractError

_SHA256=re.compile(r"^[0-9a-f]{64}$")


def _text(v:Any,n:str)->str:
    if not isinstance(v,str) or not v.strip() or "\x00" in v: raise BeanContractError(f"{n} is invalid")
    return v

def _sha(v:Any,n:str)->str:
    v=_text(v,n)
    if not _SHA256.fullmatch(v): raise BeanContractError(f"{n} must be sha256 hex")
    return v

def _tuple(v:Any,n:str,nonempty:bool=False)->Tuple[str,...]:
    if type(v) is not tuple or (nonempty and not v): raise BeanContractError(f"{n} must be immutable tuple")
    for x in v:_text(x,n)
    if len(set(v))!=len(v): raise BeanContractError(f"{n} must be unique")
    return v

def _digest(domain:bytes,payload:Mapping[str,Any])->str:
    raw=json.dumps(dict(payload),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return sha256(domain+b"\0"+raw).hexdigest()

@dataclass(frozen=True)
class CompositionBeanBinding:
    bean_id:str
    spec_digest:str
    implementation_digest:str
    provider_family:str
    resource_units:int
    cost_units:int
    def validate(self):
        _text(self.bean_id,"bean_id");_sha(self.spec_digest,"spec_digest");_sha(self.implementation_digest,"implementation_digest");_text(self.provider_family,"provider_family")
        for n in ("resource_units","cost_units"):
            v=getattr(self,n)
            if isinstance(v,bool) or not isinstance(v,int) or v<0: raise BeanContractError(f"{n} must be non-negative int")
        return self

@dataclass(frozen=True)
class CompositionRequest:
    composition_id:str
    mission_id:str
    goal_digest:str
    required_capabilities:Tuple[str,...]
    external_allowed_capabilities:Tuple[str,...]
    mission_inputs:Tuple[str,...]
    max_resource_units:int
    max_cost_units:int
    required_observability_channels:Tuple[str,...]
    observability_quorum:int
    consequential:bool
    mission_authority_ceiling:str
    conflict_pairs:Tuple[str,...]
    provenance_refs:Tuple[str,...]
    def validate(self):
        _text(self.composition_id,"composition_id");_text(self.mission_id,"mission_id");_sha(self.goal_digest,"goal_digest");_text(self.mission_authority_ceiling,"mission_authority_ceiling")
        for n in ("required_capabilities","external_allowed_capabilities","mission_inputs","required_observability_channels","conflict_pairs","provenance_refs"):_tuple(getattr(self,n),n, n in {"required_capabilities","provenance_refs"})
        for n in ("max_resource_units","max_cost_units","observability_quorum"):
            v=getattr(self,n)
            if isinstance(v,bool) or not isinstance(v,int) or v<0: raise BeanContractError(f"{n} invalid")
        if self.observability_quorum>len(self.required_observability_channels): raise BeanContractError("observability quorum exceeds channels")
        for pair in self.conflict_pairs:
            parts=pair.split("|")
            if len(parts)!=2 or not all(parts): raise BeanContractError("conflict pair must be 'beanA|beanB'")
        return self

@dataclass(frozen=True)
class CompositionContract:
    composition_id:str
    mission_id:str
    goal_digest:str
    bean_bindings:Tuple[CompositionBeanBinding,...]
    required_capabilities:Tuple[str,...]
    resolved_capabilities:Tuple[str,...]
    interface_bindings:Tuple[str,...]
    dependency_edges:Tuple[str,...]
    observability_channels:Tuple[str,...]
    verifier_bean_ids:Tuple[str,...]
    observer_bean_ids:Tuple[str,...]
    authority_ceiling:str
    total_resource_units:int
    total_cost_units:int
    provenance_refs:Tuple[str,...]
    def validate(self):
        _text(self.composition_id,"composition_id");_text(self.mission_id,"mission_id");_sha(self.goal_digest,"goal_digest");_text(self.authority_ceiling,"authority_ceiling")
        if type(self.bean_bindings) is not tuple or not self.bean_bindings: raise BeanContractError("bean_bindings required")
        for b in self.bean_bindings:b.validate()
        if len({b.bean_id for b in self.bean_bindings})!=len(self.bean_bindings): raise BeanContractError("duplicate bean binding")
        for n in ("required_capabilities","resolved_capabilities","interface_bindings","dependency_edges","observability_channels","verifier_bean_ids","observer_bean_ids","provenance_refs"):_tuple(getattr(self,n),n, n in {"required_capabilities","resolved_capabilities","provenance_refs"})
        for n in ("total_resource_units","total_cost_units"):
            v=getattr(self,n)
            if isinstance(v,bool) or not isinstance(v,int) or v<0: raise BeanContractError(f"{n} invalid")
        ids={b.bean_id for b in self.bean_bindings}
        if not set(self.verifier_bean_ids)<=ids or not set(self.observer_bean_ids)<=ids: raise BeanContractError("role ids must be selected bindings")
        return self
    def digest(self)->str:
        self.validate()
        payload=asdict(self);payload["bean_bindings"]=[asdict(x) for x in self.bean_bindings]
        return _digest(b"LION/BEAN-COMPOSITION/1",payload)

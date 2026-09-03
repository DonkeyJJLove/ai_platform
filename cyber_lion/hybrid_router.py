from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Iterable


class HybridRouteError(ValueError):
    pass

_PROVIDER_CLASSES={"deterministic","local_model","saas_model"}
_AUTHORITIES={"none","read","local_write","external_write","financial","deploy","privileged"}
_SHA64=re.compile(r"^[0-9a-f]{64}$")


def _text(v:object,name:str)->str:
    if type(v) is not str or not v.strip() or "\x00" in v: raise HybridRouteError(f"{name} invalid")
    return v

def _digest(v:object,name:str)->str:
    v=_text(v,name)
    if not _SHA64.fullmatch(v): raise HybridRouteError(f"{name} digest invalid")
    return v

def _canon(v:object)->bytes:
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")

@dataclass(frozen=True)
class MissionRouteRequest:
    mission_id:str
    capability:str
    requested_authority:str
    action_ir_digest:str
    policy_id:str
    required_provider_classes:tuple[str,...]
    forbidden_provider_ids:tuple[str,...]=()
    def validate(self):
        _text(self.mission_id,"mission_id");_text(self.capability,"capability");_text(self.policy_id,"policy_id");_digest(self.action_ir_digest,"action_ir_digest")
        if self.requested_authority not in _AUTHORITIES: raise HybridRouteError("requested_authority invalid")
        if type(self.required_provider_classes) is not tuple or not self.required_provider_classes: raise HybridRouteError("provider class requirements missing")
        if len(set(self.required_provider_classes))!=len(self.required_provider_classes) or any(x not in _PROVIDER_CLASSES for x in self.required_provider_classes): raise HybridRouteError("provider class requirements invalid")
        if type(self.forbidden_provider_ids) is not tuple or len(set(self.forbidden_provider_ids))!=len(self.forbidden_provider_ids): raise HybridRouteError("forbidden providers invalid")
        for x in self.forbidden_provider_ids:_text(x,"forbidden_provider_id")
        return self
    def digest(self): self.validate();return sha256(b"LION/HYBRID-ROUTE-REQUEST/1\0"+_canon(asdict(self))).hexdigest()

@dataclass(frozen=True)
class ProviderDescriptor:
    provider_id:str
    provider_class:str
    identity_digest:str
    implementation_digest:str
    supported_capabilities:tuple[str,...]
    admissible_authorities:tuple[str,...]
    current:bool
    available:bool
    evidence_digest:str
    def validate(self):
        _text(self.provider_id,"provider_id");_digest(self.identity_digest,"identity_digest");_digest(self.implementation_digest,"implementation_digest");_digest(self.evidence_digest,"evidence_digest")
        if self.provider_class not in _PROVIDER_CLASSES: raise HybridRouteError("provider_class invalid")
        if type(self.supported_capabilities) is not tuple or not self.supported_capabilities or len(set(self.supported_capabilities))!=len(self.supported_capabilities): raise HybridRouteError("supported_capabilities invalid")
        for x in self.supported_capabilities:_text(x,"supported_capability")
        if type(self.admissible_authorities) is not tuple or not self.admissible_authorities or len(set(self.admissible_authorities))!=len(self.admissible_authorities) or any(x not in _AUTHORITIES for x in self.admissible_authorities): raise HybridRouteError("admissible_authorities invalid")
        if type(self.current) is not bool or type(self.available) is not bool: raise HybridRouteError("provider state invalid")
        return self
    def digest(self): self.validate();return sha256(b"LION/HYBRID-PROVIDER/1\0"+_canon(asdict(self))).hexdigest()

@dataclass(frozen=True)
class RoutePolicy:
    policy_id:str
    preference_order:tuple[str,...]
    require_current:bool=True
    require_available:bool=True
    def validate(self):
        _text(self.policy_id,"policy_id")
        if type(self.preference_order) is not tuple or set(self.preference_order)!=_PROVIDER_CLASSES or len(self.preference_order)!=3: raise HybridRouteError("preference_order must contain each provider class exactly once")
        if type(self.require_current) is not bool or type(self.require_available) is not bool: raise HybridRouteError("policy flags invalid")
        return self
    def digest(self): self.validate();return sha256(b"LION/HYBRID-ROUTE-POLICY/1\0"+_canon(asdict(self))).hexdigest()

@dataclass(frozen=True)
class RouteDecision:
    request_digest:str
    policy_digest:str
    provider_id:str
    provider_class:str
    provider_digest:str
    capability:str
    requested_authority:str
    action_ir_digest:str
    authority_effect:str="NONE"
    execution_effect:str="NONE"
    route_digest:str=""
    def compute_digest(self):
        d=asdict(self);d.pop("route_digest")
        return sha256(b"LION/HYBRID-ROUTE-DECISION/1\0"+_canon(d)).hexdigest()
    def validate(self,request:MissionRouteRequest,policy:RoutePolicy,provider:ProviderDescriptor):
        request.validate();policy.validate();provider.validate()
        for x,n in ((self.request_digest,"request_digest"),(self.policy_digest,"policy_digest"),(self.provider_digest,"provider_digest"),(self.action_ir_digest,"action_ir_digest"),(self.route_digest,"route_digest")):_digest(x,n)
        if self.request_digest!=request.digest() or self.policy_digest!=policy.digest() or self.provider_digest!=provider.digest(): raise HybridRouteError("route provenance substitution")
        if (self.provider_id,self.provider_class)!=(provider.provider_id,provider.provider_class): raise HybridRouteError("provider substitution")
        if (self.capability,self.requested_authority,self.action_ir_digest)!=(request.capability,request.requested_authority,request.action_ir_digest): raise HybridRouteError("route changed capability or authority")
        if (self.authority_effect,self.execution_effect)!=("NONE","NONE"): raise HybridRouteError("routing cannot carry authority/execution effect")
        if self.route_digest!=self.compute_digest(): raise HybridRouteError("route_digest mismatch")
        return self

class HybridRouter:
    @staticmethod
    def route(request:MissionRouteRequest,policy:RoutePolicy,providers:Iterable[ProviderDescriptor])->RouteDecision:
        request.validate();policy.validate()
        if request.policy_id!=policy.policy_id: raise HybridRouteError("policy substitution")
        candidates=[]
        seen=set()
        for p in providers:
            if type(p) is not ProviderDescriptor: raise HybridRouteError("exact ProviderDescriptor required")
            p.validate()
            if p.provider_id in seen: raise HybridRouteError("duplicate provider identity")
            seen.add(p.provider_id)
            if p.provider_id in request.forbidden_provider_ids: continue
            if p.provider_class not in request.required_provider_classes: continue
            if request.capability not in p.supported_capabilities: continue
            if request.requested_authority not in p.admissible_authorities: continue
            if policy.require_current and not p.current: continue
            if policy.require_available and not p.available: continue
            rank=policy.preference_order.index(p.provider_class)
            candidates.append((rank,p.provider_id,p))
        if not candidates: raise HybridRouteError("no admissible provider route")
        _,_,p=min(candidates,key=lambda x:(x[0],x[1]))
        d=RouteDecision(request.digest(),policy.digest(),p.provider_id,p.provider_class,p.digest(),request.capability,request.requested_authority,request.action_ir_digest)
        return RouteDecision(**{**asdict(d),"route_digest":d.compute_digest()}).validate(request,policy,p)

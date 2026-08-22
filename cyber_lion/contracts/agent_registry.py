"""Immutable contracts for the canonical Agent Foundry registry.

Registry state is organizational state, never execution authority or credentials.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json, re
from typing import Any, Mapping, Tuple

_SHA256=re.compile(r"^[0-9a-f]{64}$")
INSTANCE_STATES=frozenset({"REGISTERED","ACTIVE","SUSPENDED","REVOKED","TERMINATED"})
TERMINAL_INSTANCE_STATES=frozenset({"REVOKED","TERMINATED"})

class AgentRegistryContractError(ValueError): pass

def canonical_json(value: Mapping[str,Any])->bytes:
    return json.dumps(dict(value),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def _text(v:Any,n:str)->str:
    if not isinstance(v,str) or not v.strip() or "\x00" in v: raise AgentRegistryContractError(f"{n} is invalid")
    return v

def _digest(v:Any,n:str)->str:
    v=_text(v,n)
    if not _SHA256.fullmatch(v): raise AgentRegistryContractError(f"{n} must be sha256 hex")
    return v

def _strings(v:Any,n:str,nonempty=False)->Tuple[str,...]:
    if type(v) is not tuple or (nonempty and not v): raise AgentRegistryContractError(f"{n} must be tuple")
    for x in v:_text(x,n)
    if len(set(v))!=len(v): raise AgentRegistryContractError(f"{n} must be unique")
    return v

@dataclass(frozen=True)
class AgentSpecKey:
    agent_id:str; version:str; spec_digest:str
    def validate(self): _text(self.agent_id,"agent_id");_text(self.version,"version");_digest(self.spec_digest,"spec_digest");return self

@dataclass(frozen=True)
class AgentInstance:
    instance_id:str; agent_id:str; spec_version:str; spec_digest:str; state:str="REGISTERED"; generation:int=0; created_at:str=""; updated_at:str=""; evidence_refs:Tuple[str,...]=()
    def validate(self):
        for n in ("instance_id","agent_id","spec_version","created_at","updated_at"):_text(getattr(self,n),n)
        _digest(self.spec_digest,"spec_digest");_strings(self.evidence_refs,"evidence_refs",True)
        if self.state not in INSTANCE_STATES or isinstance(self.generation,bool) or not isinstance(self.generation,int) or self.generation<0: raise AgentRegistryContractError("instance lifecycle invalid")
        return self

@dataclass(frozen=True)
class AgentRegistryProjection:
    registry_id:str; revision:int; event_head:str; mission_id:str; required_capabilities:Tuple[str,...]; candidate_specs:Tuple[Mapping[str,Any],...]; resolution_digest:str
    def validate(self):
        _text(self.registry_id,"registry_id");_digest(self.event_head,"event_head");_text(self.mission_id,"mission_id");_strings(self.required_capabilities,"required_capabilities",True);_digest(self.resolution_digest,"resolution_digest")
        if isinstance(self.revision,bool) or not isinstance(self.revision,int) or self.revision<0 or type(self.candidate_specs) is not tuple: raise AgentRegistryContractError("projection invalid")
        return self
    def canonical_payload(self):
        return {"registry_id":self.registry_id,"revision":self.revision,"event_head":self.event_head,"mission_id":self.mission_id,"required_capabilities":list(self.required_capabilities),"candidate_specs":[dict(x) for x in self.candidate_specs]}
    def verify_digest(self):
        self.validate(); expected=sha256(canonical_json(self.canonical_payload())).hexdigest()
        if expected!=self.resolution_digest: raise AgentRegistryContractError("projection digest mismatch")
        return self

@dataclass(frozen=True)
class AgentRegistrySnapshot:
    registry_id:str; revision:int; event_head:str; active_specs:Tuple[AgentSpecKey,...]; instances:Tuple[AgentInstance,...]
    def validate(self):
        _text(self.registry_id,"registry_id");_digest(self.event_head,"event_head")
        if isinstance(self.revision,bool) or not isinstance(self.revision,int) or self.revision<0: raise AgentRegistryContractError("snapshot revision invalid")
        for x in self.active_specs:x.validate()
        for x in self.instances:x.validate()
        if len({x.agent_id for x in self.active_specs})!=len(self.active_specs): raise AgentRegistryContractError("multiple canonical specs")
        return self

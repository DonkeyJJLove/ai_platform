"""Contracts for dynamic LION swarm governance. Governance state is not authority."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Any, Mapping

ROLES={"BUILDER","VERIFIER","OBSERVER","PLANNER","RESEARCHER","SECURITY","ARCHITECTURE","INCIDENT_RESPONSE","RECONCILER","FORMATION_LEAD","COMMUNICATION_RELAY"}
ROLE_STATES={"ACTIVE","RELEASED"}
FORMATION_STATES={"PROPOSED","ACTIVE","DEGRADED","BLOCKED","RECONFIGURING","COMPLETED","DISSOLVED"}
OBSERVABILITY_STATES={"CURRENT","STALE","UNKNOWN","CONFLICTED"}
_ROLE_CONFLICTS={frozenset(("BUILDER","VERIFIER")),frozenset(("SECURITY","VERIFIER"))}

class SwarmGovernanceError(ValueError): pass

def canonical_json(value:Any)->bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _text(v:object,name:str)->str:
    if not isinstance(v,str) or not v.strip() or "\x00" in v: raise SwarmGovernanceError(f"{name} invalid")
    return v
def _tuple_text(v:object,name:str)->tuple[str,...]:
    if type(v) is not tuple: raise SwarmGovernanceError(f"{name} must be tuple")
    for x in v:_text(x,name)
    if len(set(v))!=len(v): raise SwarmGovernanceError(f"{name} must be unique")
    return v
def _when(v:str,name:str)->datetime:
    _text(v,name)
    try:d=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as exc: raise SwarmGovernanceError(f"{name} invalid") from exc
    if d.tzinfo is None: raise SwarmGovernanceError(f"{name} timezone required")
    return d

@dataclass(frozen=True)
class GovernorLease:
    instance_id:str; epoch:int; lease_id:str; fencing_token:int; acquired_at:str; expires_at:str
    logical_role:str="SWARM_GOVERNOR"; is_authority_source:bool=False
    def validate(self):
        _text(self.instance_id,"instance_id");_text(self.lease_id,"lease_id")
        if self.logical_role!="SWARM_GOVERNOR":raise SwarmGovernanceError("logical_role invalid")
        if self.is_authority_source:raise SwarmGovernanceError("governor must not be authority source")
        if type(self.epoch) is not int or self.epoch<1:raise SwarmGovernanceError("epoch invalid")
        if type(self.fencing_token) is not int or self.fencing_token<1:raise SwarmGovernanceError("fencing_token invalid")
        if _when(self.expires_at,"expires_at")<=_when(self.acquired_at,"acquired_at"):raise SwarmGovernanceError("lease interval invalid")
        return self

@dataclass(frozen=True)
class RoleAssignment:
    assignment_id:str;drone_id:str;mission_id:str;role:str;formation_id:str|None;state:str;assigned_epoch:int;evidence_refs:tuple[str,...]=()
    def validate(self):
        for n,v in (("assignment_id",self.assignment_id),("drone_id",self.drone_id),("mission_id",self.mission_id)):_text(v,n)
        if self.role not in ROLES:raise SwarmGovernanceError("unknown role")
        if self.state not in ROLE_STATES:raise SwarmGovernanceError("invalid role state")
        if self.formation_id is not None:_text(self.formation_id,"formation_id")
        if type(self.assigned_epoch) is not int or self.assigned_epoch<1:raise SwarmGovernanceError("assigned_epoch invalid")
        _tuple_text(self.evidence_refs,"evidence_refs");return self

@dataclass(frozen=True)
class SwarmFormation:
    formation_id:str;mission_ids:tuple[str,...];purpose:str;member_drones:tuple[str,...];role_assignment_ids:tuple[str,...];capability_union:tuple[str,...];dependency_boundary:tuple[str,...];communication_channel:str;observability_state:str;lifecycle_state:str;creation_evidence:tuple[str,...]=()
    def validate(self):
        _text(self.formation_id,"formation_id");_text(self.purpose,"purpose");_text(self.communication_channel,"communication_channel")
        for n,v in (("mission_ids",self.mission_ids),("member_drones",self.member_drones),("role_assignment_ids",self.role_assignment_ids),("capability_union",self.capability_union),("dependency_boundary",self.dependency_boundary),("creation_evidence",self.creation_evidence)):_tuple_text(v,n)
        if not self.mission_ids or not self.member_drones:raise SwarmGovernanceError("formation requires mission and members")
        if self.observability_state not in OBSERVABILITY_STATES:raise SwarmGovernanceError("invalid observability state")
        if self.lifecycle_state not in FORMATION_STATES:raise SwarmGovernanceError("invalid formation state")
        return self

def roles_conflict(a:str,b:str)->bool:
    if a not in ROLES or b not in ROLES:raise SwarmGovernanceError("unknown role")
    return frozenset((a,b)) in _ROLE_CONFLICTS

def governance_digest(value:GovernorLease|RoleAssignment|SwarmFormation|Mapping[str,Any])->str:
    raw=asdict(value) if hasattr(value,"__dataclass_fields__") else dict(value)
    return sha256(canonical_json(raw)).hexdigest()

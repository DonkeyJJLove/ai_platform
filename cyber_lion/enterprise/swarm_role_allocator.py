"""Deterministic transient-role allocation. Role assignment never expands authority."""
from __future__ import annotations
from cyber_lion.contracts.swarm_governance import RoleAssignment,ROLES,roles_conflict,SwarmGovernanceError

class SwarmRoleAllocator:
    def select(self,*,role:str,mission_id:str,formation_id:str|None,required_capabilities:tuple[str,...],candidate_capabilities:dict[str,tuple[str,...]],active_assignments:tuple[RoleAssignment,...],governor_epoch:int,evidence_refs:tuple[str,...])->RoleAssignment:
        if role not in ROLES:raise SwarmGovernanceError("unknown role")
        req=set(required_capabilities);eligible=[]
        for drone_id,caps in candidate_capabilities.items():
            if not req.issubset(set(caps)):continue
            current=[a.role for a in active_assignments if a.drone_id==drone_id and a.state=="ACTIVE"]
            if any(roles_conflict(role,r) for r in current):continue
            eligible.append((len(set(caps)-req),drone_id))
        if not eligible:raise SwarmGovernanceError("no compatible drone for transient role")
        drone_id=sorted(eligible)[0][1]
        return RoleAssignment(assignment_id=f"role:{mission_id}:{drone_id}:{role}:{governor_epoch}",drone_id=drone_id,mission_id=mission_id,role=role,formation_id=formation_id,state="ACTIVE",assigned_epoch=governor_epoch,evidence_refs=evidence_refs).validate()

    @staticmethod
    def release(assignment:RoleAssignment)->RoleAssignment:
        assignment.validate()
        if assignment.state!="ACTIVE":raise SwarmGovernanceError("role already released")
        return RoleAssignment(**{**assignment.__dict__,"state":"RELEASED"}).validate()

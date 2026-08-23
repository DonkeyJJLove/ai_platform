"""Pure deterministic dynamic formation operations for LION swarms."""
from __future__ import annotations
from cyber_lion.contracts.swarm_governance import SwarmFormation,SwarmGovernanceError

class SwarmFormationManager:
    @staticmethod
    def create(*,formation_id:str,mission_ids:tuple[str,...],purpose:str,member_drones:tuple[str,...],role_assignment_ids:tuple[str,...],capability_union:tuple[str,...],dependency_boundary:tuple[str,...],communication_channel:str,observability_state:str,creation_evidence:tuple[str,...])->SwarmFormation:
        return SwarmFormation(formation_id,tuple(sorted(mission_ids)),purpose,tuple(sorted(member_drones)),tuple(sorted(role_assignment_ids)),tuple(sorted(capability_union)),tuple(sorted(dependency_boundary)),communication_channel,observability_state,"ACTIVE",creation_evidence).validate()
    @staticmethod
    def merge(a:SwarmFormation,b:SwarmFormation,*,formation_id:str,communication_channel:str,evidence:tuple[str,...])->SwarmFormation:
        a.validate();b.validate()
        if a.lifecycle_state not in {"ACTIVE","DEGRADED","BLOCKED"} or b.lifecycle_state not in {"ACTIVE","DEGRADED","BLOCKED"}:raise SwarmGovernanceError("only live formations may merge")
        if set(a.member_drones)&set(b.member_drones):raise SwarmGovernanceError("formation membership overlap")
        obs="CONFLICTED" if "CONFLICTED" in {a.observability_state,b.observability_state} else ("UNKNOWN" if "UNKNOWN" in {a.observability_state,b.observability_state} else ("STALE" if "STALE" in {a.observability_state,b.observability_state} else "CURRENT"))
        return SwarmFormationManager.create(formation_id=formation_id,mission_ids=tuple(set(a.mission_ids)|set(b.mission_ids)),purpose=f"merge:{a.formation_id}+{b.formation_id}",member_drones=tuple(set(a.member_drones)|set(b.member_drones)),role_assignment_ids=tuple(set(a.role_assignment_ids)|set(b.role_assignment_ids)),capability_union=tuple(set(a.capability_union)|set(b.capability_union)),dependency_boundary=tuple(set(a.dependency_boundary)|set(b.dependency_boundary)),communication_channel=communication_channel,observability_state=obs,creation_evidence=evidence)
    @staticmethod
    def split(source:SwarmFormation,*,left_id:str,right_id:str,left_members:tuple[str,...],right_members:tuple[str,...],left_channel:str,right_channel:str,evidence:tuple[str,...])->tuple[SwarmFormation,SwarmFormation]:
        source.validate();left=set(left_members);right=set(right_members)
        if not left or not right or left&right or left|right!=set(source.member_drones):raise SwarmGovernanceError("split must form disjoint full partition")
        base=dict(mission_ids=source.mission_ids,purpose=f"split:{source.formation_id}",role_assignment_ids=(),capability_union=source.capability_union,dependency_boundary=source.dependency_boundary,observability_state=source.observability_state,creation_evidence=evidence)
        return (SwarmFormationManager.create(formation_id=left_id,member_drones=tuple(left),communication_channel=left_channel,**base),SwarmFormationManager.create(formation_id=right_id,member_drones=tuple(right),communication_channel=right_channel,**base))

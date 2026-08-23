import pytest
from cyber_lion.contracts.swarm_governance import RoleAssignment,SwarmGovernanceError
from cyber_lion.enterprise.swarm_role_allocator import SwarmRoleAllocator

def test_dynamic_role_selection_is_deterministic():
    r=SwarmRoleAllocator().select(role="BUILDER",mission_id="m",formation_id=None,required_capabilities=("code",),candidate_capabilities={"b":("code","test"),"a":("code",)},active_assignments=(),governor_epoch=1,evidence_refs=("e",))
    assert r.drone_id=="a"

def test_builder_cannot_self_become_independent_verifier():
    active=(RoleAssignment("x","a","m","BUILDER",None,"ACTIVE",1,("e",)).validate(),)
    with pytest.raises(SwarmGovernanceError):SwarmRoleAllocator().select(role="VERIFIER",mission_id="m",formation_id=None,required_capabilities=("test",),candidate_capabilities={"a":("test",)},active_assignments=active,governor_epoch=1,evidence_refs=("e",))

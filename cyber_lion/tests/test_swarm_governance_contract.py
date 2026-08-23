from cyber_lion.contracts.swarm_governance import GovernorLease,RoleAssignment,SwarmFormation,SwarmGovernanceError,roles_conflict
import pytest

def test_governor_is_never_authority_source():
    with pytest.raises(SwarmGovernanceError):GovernorLease("g",1,"l",1,"2026-01-01T00:00:00+00:00","2026-01-01T00:00:30+00:00",is_authority_source=True).validate()

def test_builder_verifier_conflict():
    assert roles_conflict("BUILDER","VERIFIER")

def test_formation_requires_unique_members():
    with pytest.raises(SwarmGovernanceError):SwarmFormation("f",("m",),"p",("d","d"),(),(),(),"issue:1","CURRENT","ACTIVE",()).validate()

def test_role_assignment_is_transient_state_not_authority():
    a=RoleAssignment("a","d","m","BUILDER",None,"ACTIVE",1,("e",)).validate();assert a.role=="BUILDER" and not hasattr(a,"authority")

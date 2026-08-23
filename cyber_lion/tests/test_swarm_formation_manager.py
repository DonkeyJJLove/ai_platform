import pytest
from cyber_lion.enterprise.swarm_formation_manager import SwarmFormationManager
from cyber_lion.contracts.swarm_governance import SwarmGovernanceError

def _f(fid,members):
    return SwarmFormationManager.create(formation_id=fid,mission_ids=("m",),purpose="p",member_drones=members,role_assignment_ids=(),capability_union=("code",),dependency_boundary=(),communication_channel=f"issue:{fid}",observability_state="CURRENT",creation_evidence=("e",))

def test_split_requires_full_disjoint_partition():
    f=_f("f",("a","b"))
    left,right=SwarmFormationManager.split(f,left_id="l",right_id="r",left_members=("a",),right_members=("b",),left_channel="issue:l",right_channel="issue:r",evidence=("e",))
    assert set(left.member_drones)|set(right.member_drones)=={"a","b"}
    with pytest.raises(SwarmGovernanceError):SwarmFormationManager.split(f,left_id="x",right_id="y",left_members=("a",),right_members=("a",),left_channel="x",right_channel="y",evidence=("e",))

def test_merge_denies_membership_overlap():
    with pytest.raises(SwarmGovernanceError):SwarmFormationManager.merge(_f("a",("d",)),_f("b",("d",)),formation_id="c",communication_channel="issue:c",evidence=("e",))

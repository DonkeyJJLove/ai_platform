from datetime import datetime,timedelta,timezone
import pytest
from cyber_lion.enterprise.swarm_governor import SwarmGovernorLeaseStore,SwarmGovernorStateError

class Clock:
    def __init__(self):self.v=datetime(2026,1,1,tzinfo=timezone.utc)
    def __call__(self):return self.v
    def add(self,s):self.v+=timedelta(seconds=s)

def test_governor_epoch_and_fencing(tmp_path):
    c=Clock();s=SwarmGovernorLeaseStore(tmp_path/"g.db",clock=c);a=s.acquire("g1",lease_seconds=10)
    with pytest.raises(SwarmGovernorStateError):s.acquire("g2",lease_seconds=10)
    c.add(11);b=s.acquire("g2",lease_seconds=10)
    assert b.epoch==a.epoch+1 and b.fencing_token==a.fencing_token+1
    with pytest.raises(SwarmGovernorStateError):s.assert_current(a)
    s.assert_current(b);s.close()

def test_expired_governor_is_fenced(tmp_path):
    c=Clock();s=SwarmGovernorLeaseStore(tmp_path/"g.db",clock=c);a=s.acquire("g1",lease_seconds=1);c.add(2)
    with pytest.raises(SwarmGovernorStateError):s.assert_current(a)

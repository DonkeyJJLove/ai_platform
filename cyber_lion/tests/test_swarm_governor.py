from datetime import datetime,timedelta,timezone
import sqlite3,tempfile,pathlib,unittest
from cyber_lion.enterprise.swarm_governor import SwarmGovernorLeaseStore,SwarmGovernorStateError

class Clock:
    def __init__(self):self.v=datetime(2026,1,1,tzinfo=timezone.utc)
    def __call__(self):return self.v
    def add(self,s):self.v+=timedelta(seconds=s)

class SwarmGovernorTests(unittest.TestCase):
    def test_governor_epoch_and_fencing(self):
        with tempfile.TemporaryDirectory() as d:
            c=Clock();s=SwarmGovernorLeaseStore(pathlib.Path(d)/"g.db",clock=c);a=s.acquire("g1",lease_seconds=10)
            with self.assertRaises(SwarmGovernorStateError):s.acquire("g2",lease_seconds=10)
            c.add(11);b=s.acquire("g2",lease_seconds=10);self.assertEqual(b.epoch,a.epoch+1);self.assertEqual(b.fencing_token,a.fencing_token+1)
            with self.assertRaises(SwarmGovernorStateError):s.assert_current(a)
            s.assert_current(b);s.close()
    def test_expired_governor_is_fenced(self):
        with tempfile.TemporaryDirectory() as d:
            c=Clock();s=SwarmGovernorLeaseStore(pathlib.Path(d)/"g.db",clock=c);a=s.acquire("g1",lease_seconds=1);c.add(2)
            with self.assertRaises(SwarmGovernorStateError):s.assert_current(a)
    def test_fenced_callback_blocks_successor_epoch_until_commit_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/"g.db";c=Clock();leader=SwarmGovernorLeaseStore(path,clock=c,timeout=0.05);successor=SwarmGovernorLeaseStore(path,clock=c,timeout=0.05);old=leader.acquire("g1",lease_seconds=1)
            def protected_status_commit():
                c.add(2)
                with self.assertRaises(sqlite3.OperationalError):successor.acquire("g2",lease_seconds=10)
                return "status-committed"
            self.assertEqual(leader.run_fenced(old,protected_status_commit),"status-committed")
            new=successor.acquire("g2",lease_seconds=10);self.assertEqual(new.epoch,old.epoch+1);self.assertEqual(new.fencing_token,old.fencing_token+1)
            with self.assertRaises(SwarmGovernorStateError):leader.run_fenced(old,lambda:None)
            leader.close();successor.close()

if __name__=="__main__":unittest.main()

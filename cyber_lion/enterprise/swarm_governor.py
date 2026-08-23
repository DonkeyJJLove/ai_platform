"""Leased logical SWARM_GOVERNOR with monotonically increasing fencing tokens."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
import sqlite3,uuid
from cyber_lion.contracts.swarm_governance import GovernorLease,SwarmGovernanceError

class SwarmGovernorStateError(RuntimeError):pass

def _utc(clock):
    v=clock()
    if not isinstance(v,datetime) or v.tzinfo is None:raise SwarmGovernorStateError("trusted clock must be timezone-aware")
    return v.astimezone(timezone.utc)

def _iso(v:datetime)->str:return v.astimezone(timezone.utc).isoformat()
def _parse(v:str)->datetime:return datetime.fromisoformat(v.replace("Z","+00:00")).astimezone(timezone.utc)

class SwarmGovernorLeaseStore:
    """Correctness-oriented logical singleton. Authority remains external."""
    def __init__(self,db_path,*,clock):
        self.clock=clock;self.c=sqlite3.connect(str(db_path),isolation_level=None);self.c.row_factory=sqlite3.Row
        self.c.execute("PRAGMA journal_mode=WAL");self.c.execute("PRAGMA synchronous=FULL")
        self.c.executescript("""
CREATE TABLE IF NOT EXISTS swarm_governor(singleton INTEGER PRIMARY KEY CHECK(singleton=1),instance_id TEXT,epoch INTEGER NOT NULL,fencing_token INTEGER NOT NULL,lease_id TEXT,acquired_at TEXT,expires_at TEXT);
INSERT OR IGNORE INTO swarm_governor VALUES(1,NULL,0,0,NULL,NULL,NULL);
""")
    def close(self):self.c.close()
    def _tx(self,fn):
        try:self.c.execute("BEGIN IMMEDIATE");r=fn();self.c.execute("COMMIT");return r
        except Exception:
            if self.c.in_transaction:self.c.execute("ROLLBACK")
            raise
    def acquire(self,instance_id:str,*,lease_seconds:int=30)->GovernorLease:
        if not instance_id or lease_seconds<1:raise SwarmGovernorStateError("invalid lease request")
        def work():
            now=_utc(self.clock);r=self.c.execute("SELECT * FROM swarm_governor WHERE singleton=1").fetchone()
            if r["instance_id"] and r["expires_at"] and _parse(r["expires_at"])>now and r["instance_id"]!=instance_id:raise SwarmGovernorStateError("active governor lease exists")
            epoch=int(r["epoch"])+1;token=int(r["fencing_token"])+1;lease_id=str(uuid.uuid4());exp=now+timedelta(seconds=lease_seconds)
            self.c.execute("UPDATE swarm_governor SET instance_id=?,epoch=?,fencing_token=?,lease_id=?,acquired_at=?,expires_at=? WHERE singleton=1",(instance_id,epoch,token,lease_id,_iso(now),_iso(exp)))
            return GovernorLease(instance_id,epoch,lease_id,token,_iso(now),_iso(exp)).validate()
        return self._tx(work)
    def renew(self,lease:GovernorLease,*,lease_seconds:int=30)->GovernorLease:
        lease.validate()
        def work():
            now=_utc(self.clock);r=self.c.execute("SELECT * FROM swarm_governor WHERE singleton=1").fetchone()
            self._assert_row(r,lease,now)
            exp=now+timedelta(seconds=lease_seconds);self.c.execute("UPDATE swarm_governor SET expires_at=? WHERE singleton=1",(_iso(exp),))
            return GovernorLease(lease.instance_id,lease.epoch,lease.lease_id,lease.fencing_token,lease.acquired_at,_iso(exp)).validate()
        return self._tx(work)
    def assert_current(self,lease:GovernorLease)->None:
        lease.validate();self._assert_row(self.c.execute("SELECT * FROM swarm_governor WHERE singleton=1").fetchone(),lease,_utc(self.clock))
    @staticmethod
    def _assert_row(r,lease,now):
        if r["instance_id"]!=lease.instance_id or int(r["epoch"])!=lease.epoch or int(r["fencing_token"])!=lease.fencing_token or r["lease_id"]!=lease.lease_id:raise SwarmGovernorStateError("stale governor fenced")
        if not r["expires_at"] or _parse(r["expires_at"])<=now:raise SwarmGovernorStateError("governor lease expired")

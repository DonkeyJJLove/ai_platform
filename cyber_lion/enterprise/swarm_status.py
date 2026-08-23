"""Serialized deterministic LION status writer. Status is observable state, never authority."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
import json,os,sqlite3
from pathlib import Path
from cyber_lion.contracts.swarm_status import StatusReport,canonical_json,compute_status_digest,compute_revision_digest,transition_allowed,TERMINAL_ACTION_STATES
from cyber_lion.contracts.swarm_governance import GovernorLease
from .swarm_governor import SwarmGovernorLeaseStore

_ZERO="0"*64
_EVENT_STATE={"ACTION_PLANNED":"PLANNED","ACTION_ACCEPTED":"ACCEPTED","ACTION_STARTED":"STARTED","ACTION_PROGRESS":"IN_PROGRESS","ACTION_BLOCKED":"BLOCKED","ACTION_VERIFYING":"VERIFYING","ACTION_COMPLETED":"COMPLETED","ACTION_FAILED":"FAILED","ACTION_CANCELLED":"CANCELLED","ACTION_SUPERSEDED":"SUPERSEDED"}
class SwarmStatusStateError(RuntimeError):pass

def _now(clock):
    v=clock()
    if not isinstance(v,datetime) or v.tzinfo is None:raise SwarmStatusStateError("trusted clock must be timezone-aware")
    return v.astimezone(timezone.utc).isoformat()
def _jd(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)

class SwarmStatusStore:
    def __init__(self,db_path,status_path,*,system_id,clock,governor_store:SwarmGovernorLeaseStore,known_drones:tuple[str,...],initial_context:dict):
        self.clock=clock;self.status_path=Path(status_path);self.system_id=system_id;self.governor_store=governor_store;self.known_drones=set(known_drones);self.c=sqlite3.connect(str(db_path),isolation_level=None);self.c.row_factory=sqlite3.Row
        self.c.execute("PRAGMA journal_mode=WAL");self.c.execute("PRAGMA synchronous=FULL")
        self.c.executescript("""
CREATE TABLE IF NOT EXISTS lion_status_meta(singleton INTEGER PRIMARY KEY CHECK(singleton=1),revision INTEGER NOT NULL,status_digest TEXT NOT NULL,previous_status_digest TEXT NOT NULL,revision_digest TEXT NOT NULL,previous_revision_digest TEXT NOT NULL,generated_at TEXT NOT NULL,context_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lion_status_operation(operation_id TEXT PRIMARY KEY,payload_digest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lion_current_action(action_id TEXT PRIMARY KEY,record_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lion_history(action_id TEXT PRIMARY KEY,record_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lion_status_report(seq INTEGER PRIMARY KEY AUTOINCREMENT,operation_id TEXT UNIQUE NOT NULL,report_json TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS lion_history_no_update BEFORE UPDATE ON lion_history BEGIN SELECT RAISE(ABORT,'history immutable');END;
CREATE TRIGGER IF NOT EXISTS lion_history_no_delete BEFORE DELETE ON lion_history BEGIN SELECT RAISE(ABORT,'history immutable');END;
CREATE TRIGGER IF NOT EXISTS lion_report_no_update BEFORE UPDATE ON lion_status_report BEGIN SELECT RAISE(ABORT,'report immutable');END;
CREATE TRIGGER IF NOT EXISTS lion_report_no_delete BEFORE DELETE ON lion_status_report BEGIN SELECT RAISE(ABORT,'report immutable');END;
""")
        if self.c.execute("SELECT 1 FROM lion_status_meta WHERE singleton=1").fetchone() is None:
            at=_now(clock);self.c.execute("INSERT INTO lion_status_meta VALUES(1,0,?,?,?,?,?,?)",(_ZERO,_ZERO,_ZERO,_ZERO,at,_jd(initial_context)));self._recompute_and_write()
        else:
            if self.status_path.exists():self._verify_external_file()
            self._recompute_and_write(verify_existing=True)
    def close(self):self.c.close()
    def _tx(self,fn):
        try:self.c.execute("BEGIN IMMEDIATE");r=fn();self.c.execute("COMMIT");return r
        except Exception:
            if self.c.in_transaction:self.c.execute("ROLLBACK")
            raise
    def _projection(self):
        m=self.c.execute("SELECT * FROM lion_status_meta WHERE singleton=1").fetchone();ctx=json.loads(m["context_json"]);current=[json.loads(r[0]) for r in self.c.execute("SELECT record_json FROM lion_current_action ORDER BY action_id")];history=[json.loads(r[0]) for r in self.c.execute("SELECT record_json FROM lion_history ORDER BY action_id")]
        return {"schema_version":"1.0.0","system_id":self.system_id,"revision":m["revision"],"status_digest":m["status_digest"],"previous_status_digest":m["previous_status_digest"],"revision_digest":m["revision_digest"],"previous_revision_digest":m["previous_revision_digest"],**ctx,"current_actions":current,"history":history,"generated_at":m["generated_at"]}
    def _verify_external_file(self):
        try:raw=self.status_path.read_bytes()
        except Exception as exc:raise SwarmStatusStateError("external status file unreadable") from exc
        expected=canonical_json(self._projection())+b"\n"
        if raw!=expected:raise SwarmStatusStateError("external status modification detected")
    def _recompute_and_write(self,verify_existing=False):
        s=self._projection();logical=compute_status_digest(s);rev=compute_revision_digest(revision=s["revision"],status_digest=logical,previous_revision_digest=s["previous_revision_digest"])
        if verify_existing and s["status_digest"] not in {_ZERO,logical}:raise SwarmStatusStateError("status projection corruption")
        self.c.execute("UPDATE lion_status_meta SET status_digest=?,revision_digest=? WHERE singleton=1",(logical,rev));s=self._projection();self.status_path.parent.mkdir(parents=True,exist_ok=True);tmp=self.status_path.with_suffix(self.status_path.suffix+".tmp");tmp.write_bytes(canonical_json(s)+b"\n");os.replace(tmp,self.status_path);return s
    def snapshot(self):return self._projection()
    def apply_report(self,report:StatusReport,*,lease:GovernorLease):
        report.validate()
        if report.reporter_drone_id not in self.known_drones:raise SwarmStatusStateError("unknown reporter drone")
        def work():
            m=self.c.execute("SELECT * FROM lion_status_meta WHERE singleton=1").fetchone()
            if report.expected_revision!=m["revision"] or report.expected_status_digest!=m["status_digest"]:raise SwarmStatusStateError("stale status CAS")
            raw={"operation_id":report.operation_id,"expected_revision":report.expected_revision,"expected_status_digest":report.expected_status_digest,"reporter_drone_id":report.reporter_drone_id,"mission_id":report.mission_id,"event_type":report.event_type,"payload":dict(report.payload),"evidence_refs":list(report.evidence_refs),"observed_at":report.observed_at};pd=sha256(canonical_json(raw)).hexdigest();old=self.c.execute("SELECT payload_digest FROM lion_status_operation WHERE operation_id=?",(report.operation_id,)).fetchone()
            if old:
                if old[0]!=pd:raise SwarmStatusStateError("operation replay substitution denied")
                return self._projection()
            if report.event_type in _EVENT_STATE:self._apply_action(report,_EVENT_STATE[report.event_type])
            self.c.execute("INSERT INTO lion_status_operation VALUES(?,?)",(report.operation_id,pd));self.c.execute("INSERT INTO lion_status_report(operation_id,report_json) VALUES(?,?)",(report.operation_id,_jd(raw)));self.c.execute("UPDATE lion_status_meta SET revision=revision+1,previous_status_digest=status_digest,previous_revision_digest=revision_digest,generated_at=? WHERE singleton=1",(report.observed_at,));return self._recompute_and_write()
        return self.governor_store.run_fenced(lease,lambda:self._tx(work))
    def replace_context(self,context:dict,*,operation_id:str,expected_revision:int,expected_status_digest:str,lease:GovernorLease,evidence_refs:tuple[str,...]):
        if not evidence_refs:raise SwarmStatusStateError("context update requires evidence")
        def work():
            m=self.c.execute("SELECT * FROM lion_status_meta WHERE singleton=1").fetchone()
            if expected_revision!=m["revision"] or expected_status_digest!=m["status_digest"]:raise SwarmStatusStateError("stale status CAS")
            payload={"context":context,"evidence_refs":list(evidence_refs)};pd=sha256(canonical_json(payload)).hexdigest();old=self.c.execute("SELECT payload_digest FROM lion_status_operation WHERE operation_id=?",(operation_id,)).fetchone()
            if old:
                if old[0]!=pd:raise SwarmStatusStateError("operation replay substitution denied")
                return self._projection()
            self.c.execute("INSERT INTO lion_status_operation VALUES(?,?)",(operation_id,pd));self.c.execute("UPDATE lion_status_meta SET context_json=?,revision=revision+1,previous_status_digest=status_digest,previous_revision_digest=revision_digest,generated_at=? WHERE singleton=1",(_jd(context),_now(self.clock)));return self._recompute_and_write()
        return self.governor_store.run_fenced(lease,lambda:self._tx(work))
    def _apply_action(self,report:StatusReport,new_state:str):
        action_id=str(report.payload.get("action_id","")).strip()
        if not action_id:raise SwarmStatusStateError("action_id required")
        row=self.c.execute("SELECT record_json FROM lion_current_action WHERE action_id=?",(action_id,)).fetchone()
        if new_state=="PLANNED":
            if row or self.c.execute("SELECT 1 FROM lion_history WHERE action_id=?",(action_id,)).fetchone():raise SwarmStatusStateError("action already exists")
            rec={"action_id":action_id,"mission_id":report.mission_id,"drone_id":report.reporter_drone_id,"role":report.payload.get("role"),"formation_id":report.payload.get("formation_id"),"state":"PLANNED","started_at":None,"completed_at":None,"evidence_refs":sorted(set(report.evidence_refs)),"correlation_id":report.payload.get("correlation_id")};self.c.execute("INSERT INTO lion_current_action VALUES(?,?)",(action_id,_jd(rec)));return
        if not row:raise SwarmStatusStateError("action transition without current action")
        rec=json.loads(row[0]);old=rec["state"]
        if not transition_allowed(old,new_state):raise SwarmStatusStateError(f"illegal action transition {old}->{new_state}")
        rec["state"]=new_state;rec["evidence_refs"]=sorted(set(rec.get("evidence_refs",[]))|set(report.evidence_refs))
        if new_state=="STARTED" and not rec.get("started_at"):rec["started_at"]=report.observed_at
        if new_state in TERMINAL_ACTION_STATES:
            rec["completed_at"]=report.observed_at;rec["result_refs"]=sorted(set(report.payload.get("result_refs",[])));self.c.execute("DELETE FROM lion_current_action WHERE action_id=?",(action_id,));self.c.execute("INSERT INTO lion_history VALUES(?,?)",(action_id,_jd(rec)))
        else:self.c.execute("UPDATE lion_current_action SET record_json=? WHERE action_id=?",(_jd(rec),action_id))

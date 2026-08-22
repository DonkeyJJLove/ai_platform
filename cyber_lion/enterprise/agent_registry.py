"""Restart-durable canonical Agent Registry; registry state never grants authority."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime,timezone
from hashlib import sha256
import json,sqlite3
from pathlib import Path
from cyber_lion.contracts.agent_registry import AgentInstance,AgentRegistryProjection,AgentRegistrySnapshot,AgentSpecKey,canonical_json
from .models import AgentSpec,MissionSpec,authority_rank
_ZERO="0"*64
class AgentRegistryStateError(RuntimeError):pass

def _now(clock):
    v=clock()
    if not isinstance(v,datetime) or v.tzinfo is None:raise AgentRegistryStateError("trusted clock must be timezone-aware")
    return v.astimezone(timezone.utc).isoformat()
def _spec_dict(s):
    s.validate();d=asdict(s)
    for k,v in list(d.items()):
        if isinstance(v,tuple):d[k]=list(v)
    return d
def _spec_digest(s):return sha256(canonical_json(_spec_dict(s))).hexdigest()
def _spec_from(raw):
    try:d=json.loads(raw)
    except Exception as e:raise AgentRegistryStateError("stored AgentSpec invalid") from e
    for k in ("capabilities","observability_events","memory_policy_ids"):d[k]=tuple(d.get(k,()))
    try:return AgentSpec(**d).validate()
    except Exception as e:raise AgentRegistryStateError("stored AgentSpec invalid") from e
def _event(prev,typ,agent,instance,payload,at):return sha256(canonical_json({"previous_digest":prev,"event_type":typ,"agent_id":agent,"instance_id":instance,"payload":payload,"observed_at":at})).hexdigest()

class AgentRegistryStore:
    def __init__(self,db_path,*,registry_id,clock):
        if not registry_id:raise AgentRegistryStateError("registry_id required")
        self.registry_id=registry_id;self.clock=clock;self.db_path=str(Path(db_path));self.c=sqlite3.connect(self.db_path,isolation_level=None);self.c.row_factory=sqlite3.Row
        try:
            self.c.execute("PRAGMA foreign_keys=ON");self.c.execute("PRAGMA journal_mode=WAL");self.c.execute("PRAGMA synchronous=FULL");self._schema();self._bind();self.verify_event_chain();self.verify_consistency()
        except Exception:self.c.close();raise
    def close(self):self.c.close()
    def _schema(self):
        self.c.executescript("""
CREATE TABLE IF NOT EXISTS agent_registry_meta(singleton INTEGER PRIMARY KEY CHECK(singleton=1),registry_id TEXT NOT NULL,revision INTEGER NOT NULL,event_head TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_registry_spec(agent_id TEXT NOT NULL,version TEXT NOT NULL,spec_digest TEXT NOT NULL UNIQUE,spec_json TEXT NOT NULL,registered_at TEXT NOT NULL,PRIMARY KEY(agent_id,version));
CREATE TABLE IF NOT EXISTS agent_registry_active_spec(agent_id TEXT PRIMARY KEY,version TEXT NOT NULL,spec_digest TEXT NOT NULL,activated_at TEXT NOT NULL,FOREIGN KEY(agent_id,version) REFERENCES agent_registry_spec(agent_id,version));
CREATE TABLE IF NOT EXISTS agent_registry_instance(instance_id TEXT PRIMARY KEY,agent_id TEXT NOT NULL,spec_version TEXT NOT NULL,spec_digest TEXT NOT NULL,state TEXT NOT NULL,generation INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,evidence_refs_json TEXT NOT NULL,FOREIGN KEY(agent_id,spec_version) REFERENCES agent_registry_spec(agent_id,version));
CREATE TABLE IF NOT EXISTS agent_registry_operation(operation_id TEXT PRIMARY KEY,operation_digest TEXT NOT NULL,result_json TEXT NOT NULL,result_digest TEXT NOT NULL,observed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_registry_event(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,event_type TEXT NOT NULL,agent_id TEXT,instance_id TEXT,payload_json TEXT NOT NULL,previous_digest TEXT NOT NULL,event_digest TEXT UNIQUE NOT NULL,observed_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS spec_no_update BEFORE UPDATE ON agent_registry_spec BEGIN SELECT RAISE(ABORT,'spec append-only');END;
CREATE TRIGGER IF NOT EXISTS spec_no_delete BEFORE DELETE ON agent_registry_spec BEGIN SELECT RAISE(ABORT,'spec append-only');END;
CREATE TRIGGER IF NOT EXISTS op_no_update BEFORE UPDATE ON agent_registry_operation BEGIN SELECT RAISE(ABORT,'operation append-only');END;
CREATE TRIGGER IF NOT EXISTS op_no_delete BEFORE DELETE ON agent_registry_operation BEGIN SELECT RAISE(ABORT,'operation append-only');END;
CREATE TRIGGER IF NOT EXISTS event_no_update BEFORE UPDATE ON agent_registry_event BEGIN SELECT RAISE(ABORT,'event append-only');END;
CREATE TRIGGER IF NOT EXISTS event_no_delete BEFORE DELETE ON agent_registry_event BEGIN SELECT RAISE(ABORT,'event append-only');END;
""")
    def _bind(self):
        r=self.c.execute("SELECT registry_id FROM agent_registry_meta WHERE singleton=1").fetchone()
        if r is None:self.c.execute("INSERT INTO agent_registry_meta VALUES(1,?,?,?)",(self.registry_id,0,_ZERO))
        elif r[0]!=self.registry_id:raise AgentRegistryStateError("registry substitution denied")
    def _tx(self,fn):
        try:self.c.execute("BEGIN IMMEDIATE");out=fn();self.c.execute("COMMIT");return out
        except Exception:
            if self.c.in_transaction:self.c.execute("ROLLBACK")
            raise
    def _append(self,typ,agent,instance,payload,at):
        prev=self.c.execute("SELECT event_head FROM agent_registry_meta WHERE singleton=1").fetchone()[0];dg=_event(prev,typ,agent,instance,payload,at);self.c.execute("INSERT INTO agent_registry_event(event_id,event_type,agent_id,instance_id,payload_json,previous_digest,event_digest,observed_at) VALUES(?,?,?,?,?,?,?,?)",(dg,typ,agent,instance,canonical_json(payload).decode(),prev,dg,at));self.c.execute("UPDATE agent_registry_meta SET revision=revision+1,event_head=? WHERE singleton=1",(dg,))
    def _cached(self,operation_id,payload):
        od=sha256(canonical_json(payload)).hexdigest();r=self.c.execute("SELECT operation_digest,result_json,result_digest FROM agent_registry_operation WHERE operation_id=?",(operation_id,)).fetchone()
        if not r:return od,None
        if r[0]!=od or sha256(r[1].encode()).hexdigest()!=r[2]:raise AgentRegistryStateError("operation replay substitution/corruption denied")
        return od,json.loads(r[1])
    def _save(self,op,od,result,at):
        raw=json.dumps(result,sort_keys=True,separators=(",",":"));self.c.execute("INSERT INTO agent_registry_operation VALUES(?,?,?,?,?)",(op,od,raw,sha256(raw.encode()).hexdigest(),at))
    def register_spec(self,spec,*,operation_id,evidence_refs):
        spec.validate();dg=_spec_digest(spec);p={"kind":"register","agent_id":spec.agent_id,"version":spec.version,"spec_digest":dg,"evidence_refs":list(evidence_refs)}
        def work():
            od,x=self._cached(operation_id,p)
            if x:return AgentSpecKey(**x).validate()
            if not evidence_refs:raise AgentRegistryStateError("evidence required")
            if self.c.execute("SELECT 1 FROM agent_registry_active_spec WHERE agent_id=?",(spec.agent_id,)).fetchone():raise AgentRegistryStateError("explicit supersession required")
            if self.c.execute("SELECT 1 FROM agent_registry_spec WHERE agent_id=? AND version=?",(spec.agent_id,spec.version)).fetchone():raise AgentRegistryStateError("version reuse denied")
            at=_now(self.clock);self.c.execute("INSERT INTO agent_registry_spec VALUES(?,?,?,?,?)",(spec.agent_id,spec.version,dg,canonical_json(_spec_dict(spec)).decode(),at));self.c.execute("INSERT INTO agent_registry_active_spec VALUES(?,?,?,?)",(spec.agent_id,spec.version,dg,at));k=AgentSpecKey(spec.agent_id,spec.version,dg);self._append("SPEC_REGISTERED",spec.agent_id,None,p,at);self._save(operation_id,od,asdict(k),at);return k
        return self._tx(work)
    def supersede_spec(self,spec,*,expected_version,expected_digest,operation_id,evidence_refs):
        spec.validate();dg=_spec_digest(spec);p={"kind":"supersede","agent_id":spec.agent_id,"expected_version":expected_version,"expected_digest":expected_digest,"version":spec.version,"spec_digest":dg,"evidence_refs":list(evidence_refs)}
        def work():
            od,x=self._cached(operation_id,p)
            if x:return AgentSpecKey(**x).validate()
            cur=self.c.execute("SELECT version,spec_digest FROM agent_registry_active_spec WHERE agent_id=?",(spec.agent_id,)).fetchone()
            if not cur or tuple(cur)!=(expected_version,expected_digest):raise AgentRegistryStateError("exact current binding mismatch")
            if self.c.execute("SELECT 1 FROM agent_registry_spec WHERE agent_id=? AND version=?",(spec.agent_id,spec.version)).fetchone():raise AgentRegistryStateError("historical rollback/reuse denied")
            at=_now(self.clock);self.c.execute("INSERT INTO agent_registry_spec VALUES(?,?,?,?,?)",(spec.agent_id,spec.version,dg,canonical_json(_spec_dict(spec)).decode(),at));self.c.execute("UPDATE agent_registry_active_spec SET version=?,spec_digest=?,activated_at=? WHERE agent_id=?",(spec.version,dg,at,spec.agent_id));k=AgentSpecKey(spec.agent_id,spec.version,dg);self._append("SPEC_SUPERSEDED",spec.agent_id,None,p,at);self._save(operation_id,od,asdict(k),at);return k
        return self._tx(work)
    def register_instance(self,*,instance_id,agent_id,spec_version,spec_digest,operation_id,evidence_refs):
        p={"kind":"instance","instance_id":instance_id,"agent_id":agent_id,"spec_version":spec_version,"spec_digest":spec_digest,"evidence_refs":list(evidence_refs)}
        def work():
            od,x=self._cached(operation_id,p)
            if x:x["evidence_refs"]=tuple(x["evidence_refs"]);return AgentInstance(**x).validate()
            r=self.c.execute("SELECT spec_digest FROM agent_registry_spec WHERE agent_id=? AND version=?",(agent_id,spec_version)).fetchone()
            if not r or r[0]!=spec_digest:raise AgentRegistryStateError("exact spec binding unavailable")
            at=_now(self.clock);i=AgentInstance(instance_id,agent_id,spec_version,spec_digest,"REGISTERED",0,at,at,evidence_refs).validate();self.c.execute("INSERT INTO agent_registry_instance VALUES(?,?,?,?,?,?,?,?,?)",(instance_id,agent_id,spec_version,spec_digest,"REGISTERED",0,at,at,json.dumps(evidence_refs)));self._append("INSTANCE_REGISTERED",agent_id,instance_id,p,at);d=asdict(i);d["evidence_refs"]=list(evidence_refs);self._save(operation_id,od,d,at);return i
        return self._tx(work)
    def transition_instance(self,instance_id,to_state,*,operation_id,evidence_refs):
        allowed={"REGISTERED":{"ACTIVE","REVOKED","TERMINATED"},"ACTIVE":{"SUSPENDED","REVOKED","TERMINATED"},"SUSPENDED":{"ACTIVE","REVOKED","TERMINATED"}};p={"kind":"transition","instance_id":instance_id,"to_state":to_state,"evidence_refs":list(evidence_refs)}
        def work():
            od,x=self._cached(operation_id,p)
            if x:x["evidence_refs"]=tuple(x["evidence_refs"]);return AgentInstance(**x).validate()
            r=self.c.execute("SELECT * FROM agent_registry_instance WHERE instance_id=?",(instance_id,)).fetchone()
            if not r or to_state not in allowed.get(r["state"],set()):raise AgentRegistryStateError("instance transition denied")
            at=_now(self.clock);g=r["generation"]+1;self.c.execute("UPDATE agent_registry_instance SET state=?,generation=?,updated_at=?,evidence_refs_json=? WHERE instance_id=?",(to_state,g,at,json.dumps(evidence_refs),instance_id));i=AgentInstance(instance_id,r["agent_id"],r["spec_version"],r["spec_digest"],to_state,g,r["created_at"],at,evidence_refs).validate();self._append("INSTANCE_TRANSITIONED",r["agent_id"],instance_id,p,at);d=asdict(i);d["evidence_refs"]=list(evidence_refs);self._save(operation_id,od,d,at);return i
        return self._tx(work)
    def resolve_for_mission(self,mission):
        mission.validate();m=self.c.execute("SELECT registry_id,revision,event_head FROM agent_registry_meta WHERE singleton=1").fetchone();specs=[]
        verifier_required=(mission.require_independent_verifier or mission.risk_class=="RED" or authority_rank(mission.authority_ceiling)>=authority_rank("external_write"))
        for r in self.c.execute("SELECT s.spec_json FROM agent_registry_active_spec a JOIN agent_registry_spec s ON s.agent_id=a.agent_id AND s.version=a.version ORDER BY a.agent_id,a.version,a.spec_digest"):
            s=_spec_from(r[0])
            if set(s.capabilities)&set(mission.required_capabilities) or (verifier_required and s.is_verifier):specs.append(_spec_dict(s))
        p={"registry_id":m[0],"revision":m[1],"event_head":m[2],"mission_id":mission.mission_id,"required_capabilities":list(mission.required_capabilities),"candidate_specs":specs};dg=sha256(canonical_json(p)).hexdigest();return AgentRegistryProjection(m[0],m[1],m[2],mission.mission_id,mission.required_capabilities,tuple(specs),dg).verify_digest()
    def snapshot(self):
        m=self.c.execute("SELECT registry_id,revision,event_head FROM agent_registry_meta WHERE singleton=1").fetchone();keys=tuple(AgentSpecKey(*r) for r in self.c.execute("SELECT agent_id,version,spec_digest FROM agent_registry_active_spec ORDER BY agent_id"));ins=[]
        for r in self.c.execute("SELECT * FROM agent_registry_instance ORDER BY instance_id"):ins.append(AgentInstance(r["instance_id"],r["agent_id"],r["spec_version"],r["spec_digest"],r["state"],r["generation"],r["created_at"],r["updated_at"],tuple(json.loads(r["evidence_refs_json"]))).validate())
        return AgentRegistrySnapshot(m[0],m[1],m[2],keys,tuple(ins)).validate()
    def verify_event_chain(self):
        prev=_ZERO
        for r in self.c.execute("SELECT * FROM agent_registry_event ORDER BY seq"):
            try:p=json.loads(r["payload_json"])
            except Exception as e:raise AgentRegistryStateError("event corruption") from e
            dg=_event(prev,r["event_type"],r["agent_id"],r["instance_id"],p,r["observed_at"])
            if r["previous_digest"]!=prev or r["event_digest"]!=dg or r["event_id"]!=dg:raise AgentRegistryStateError("event chain corruption")
            prev=dg
        if self.c.execute("SELECT event_head FROM agent_registry_meta WHERE singleton=1").fetchone()[0]!=prev:raise AgentRegistryStateError("event head mismatch")
        return prev
    def verify_consistency(self):
        for r in self.c.execute("SELECT a.agent_id,a.version,a.spec_digest,s.spec_digest actual FROM agent_registry_active_spec a LEFT JOIN agent_registry_spec s ON s.agent_id=a.agent_id AND s.version=a.version"):
            if r["actual"] is None or r["actual"]!=r["spec_digest"]:raise AgentRegistryStateError("active spec projection corruption")
        for r in self.c.execute("SELECT i.agent_id,i.spec_version,i.spec_digest,s.spec_digest actual FROM agent_registry_instance i LEFT JOIN agent_registry_spec s ON s.agent_id=i.agent_id AND s.version=i.spec_version"):
            if r["actual"] is None or r["actual"]!=r["spec_digest"]:raise AgentRegistryStateError("instance spec binding corruption")
        return True
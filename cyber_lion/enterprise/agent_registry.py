"""Restart-durable canonical Agent Registry. Registry state never grants authority."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json, sqlite3
from pathlib import Path
from typing import Callable, Iterator
from cyber_lion.contracts.agent_registry import AgentInstance,AgentRegistryProjection,AgentRegistrySnapshot,AgentSpecKey,TERMINAL_INSTANCE_STATES,canonical_json
from .models import AgentSpec, MissionSpec

_ZERO="0"*64
class AgentRegistryStateError(RuntimeError): pass

def _utc(v:datetime)->str:
    if not isinstance(v,datetime) or v.tzinfo is None: raise AgentRegistryStateError("trusted clock must be timezone-aware")
    return v.astimezone(timezone.utc).isoformat()
def _parse(v:str)->datetime:
    try:x=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as e:raise AgentRegistryStateError("stored timestamp invalid") from e
    if x.tzinfo is None:raise AgentRegistryStateError("stored timestamp not timezone-aware")
    return x.astimezone(timezone.utc)
def _spec_dict(s:AgentSpec):
    s.validate(); d=asdict(s)
    for k,v in list(d.items()):
        if isinstance(v,tuple):d[k]=list(v)
    return d
def _spec_digest(s:AgentSpec)->str:return sha256(canonical_json(_spec_dict(s))).hexdigest()
def _spec_from(raw:str)->AgentSpec:
    try:d=json.loads(raw)
    except json.JSONDecodeError as e:raise AgentRegistryStateError("stored AgentSpec JSON invalid") from e
    for k in ("capabilities","observability_events","memory_policy_ids"):
        d[k]=tuple(d.get(k,()))
    try:return AgentSpec(**d).validate()
    except (TypeError,ValueError) as e:raise AgentRegistryStateError("stored AgentSpec invalid") from e
def _event_digest(prev,typ,agent,instance,payload,at):return sha256(canonical_json({"previous_digest":prev,"event_type":typ,"agent_id":agent,"instance_id":instance,"payload":payload,"observed_at":at})).hexdigest()

class AgentRegistryStore:
    def __init__(self,db_path:str|Path,*,registry_id:str,clock:Callable[[],datetime]):
        if not registry_id:raise AgentRegistryStateError("registry_id required")
        self.registry_id=registry_id;self._clock=clock;self.db_path=str(Path(db_path));self._conn=sqlite3.connect(self.db_path,isolation_level=None);self._conn.row_factory=sqlite3.Row
        try:
            self._conn.execute("PRAGMA foreign_keys=ON");self._conn.execute("PRAGMA journal_mode=WAL");self._conn.execute("PRAGMA synchronous=FULL");self._conn.execute("PRAGMA busy_timeout=5000");self._init();self._bind();self.verify_event_chain(self._conn);self.verify_consistency(self._conn)
        except Exception:self._conn.close();raise
    def close(self):self._conn.close()
    def _init(self):
        self._conn.executescript("""
CREATE TABLE IF NOT EXISTS agent_registry_meta(singleton INTEGER PRIMARY KEY CHECK(singleton=1),registry_id TEXT NOT NULL,revision INTEGER NOT NULL,event_head TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_registry_spec(agent_id TEXT NOT NULL,version TEXT NOT NULL,spec_digest TEXT NOT NULL UNIQUE,spec_json TEXT NOT NULL,registered_at TEXT NOT NULL,PRIMARY KEY(agent_id,version));
CREATE TABLE IF NOT EXISTS agent_registry_active_spec(agent_id TEXT PRIMARY KEY,version TEXT NOT NULL,spec_digest TEXT NOT NULL,activated_at TEXT NOT NULL,FOREIGN KEY(agent_id,version) REFERENCES agent_registry_spec(agent_id,version));
CREATE TABLE IF NOT EXISTS agent_registry_instance(instance_id TEXT PRIMARY KEY,agent_id TEXT NOT NULL,spec_version TEXT NOT NULL,spec_digest TEXT NOT NULL,state TEXT NOT NULL,generation INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,evidence_refs_json TEXT NOT NULL,FOREIGN KEY(agent_id,spec_version) REFERENCES agent_registry_spec(agent_id,version));
CREATE TABLE IF NOT EXISTS agent_registry_operation(operation_id TEXT PRIMARY KEY,operation_digest TEXT NOT NULL,result_digest TEXT NOT NULL,result_json TEXT NOT NULL,observed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_registry_event(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL UNIQUE,event_type TEXT NOT NULL,agent_id TEXT,instance_id TEXT,payload_json TEXT NOT NULL,previous_digest TEXT NOT NULL,event_digest TEXT NOT NULL UNIQUE,observed_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS ars_no_update BEFORE UPDATE ON agent_registry_spec BEGIN SELECT RAISE(ABORT,'agent_registry_spec append-only'); END;
CREATE TRIGGER IF NOT EXISTS ars_no_delete BEFORE DELETE ON agent_registry_spec BEGIN SELECT RAISE(ABORT,'agent_registry_spec append-only'); END;
CREATE TRIGGER IF NOT EXISTS aro_no_update BEFORE UPDATE ON agent_registry_operation BEGIN SELECT RAISE(ABORT,'agent_registry_operation append-only'); END;
CREATE TRIGGER IF NOT EXISTS aro_no_delete BEFORE DELETE ON agent_registry_operation BEGIN SELECT RAISE(ABORT,'agent_registry_operation append-only'); END;
CREATE TRIGGER IF NOT EXISTS are_no_update BEFORE UPDATE ON agent_registry_event BEGIN SELECT RAISE(ABORT,'agent_registry_event append-only'); END;
CREATE TRIGGER IF NOT EXISTS are_no_delete BEFORE DELETE ON agent_registry_event BEGIN SELECT RAISE(ABORT,'agent_registry_event append-only'); END;
""")
    def _bind(self):
        r=self._conn.execute("SELECT registry_id FROM agent_registry_meta WHERE singleton=1").fetchone()
        if r is None:self._conn.execute("INSERT INTO agent_registry_meta VALUES(1,?,?,?)",(self.registry_id,0,_ZERO))
        elif r[0]!=self.registry_id:raise AgentRegistryStateError("registry instance substitution denied")
    @contextmanager
    def _write(self)->Iterator[sqlite3.Connection]:
        try:self._conn.execute("BEGIN IMMEDIATE");yield self._conn;self._conn.execute("COMMIT")
        except Exception:
            if self._conn.in_transaction:self._conn.execute("ROLLBACK")
            raise
    def open_query_reader(self):
        c=sqlite3.connect(self.db_path,isolation_level=None);c.row_factory=sqlite3.Row;c.execute("PRAGMA foreign_keys=ON");c.execute("PRAGMA query_only=ON");return c
    def _now(self,c):
        now=_utc(self._clock());r=c.execute("SELECT observed_at FROM agent_registry_event ORDER BY seq DESC LIMIT 1").fetchone()
        if r and _parse(now)<_parse(r[0]):raise AgentRegistryStateError("trusted clock rollback denied")
        return now
    def _append(self,c,typ,agent,instance,payload,at):
        prev=c.execute("SELECT event_head FROM agent_registry_meta WHERE singleton=1").fetchone()[0];d=_event_digest(prev,typ,agent,instance,payload,at);c.execute("INSERT INTO agent_registry_event(event_id,event_type,agent_id,instance_id,payload_json,previous_digest,event_digest,observed_at) VALUES(?,?,?,?,?,?,?,?)",(d,typ,agent,instance,canonical_json(payload).decode(),prev,d,at));c.execute("UPDATE agent_registry_meta SET event_head=?,revision=revision+1 WHERE singleton=1",(d,));return d
    def _op(self,c,operation_id,payload):
        od=sha256(canonical_json(payload)).hexdigest();r=c.execute("SELECT operation_digest,result_json,result_digest FROM agent_registry_operation WHERE operation_id=?",(operation_id,)).fetchone()
        if r:
            if r[0]!=od:raise AgentRegistryStateError("operation replay substitution denied")
            if sha256(r[1].encode()).hexdigest()!=r[2]:raise AgentRegistryStateError("operation result corruption")
            return od,json.loads(r[1])
        return od,None
    def _save_op(self,c,operation_id,od,result,at):
        raw=json.dumps(result,sort_keys=True,separators=(",",":"));c.execute("INSERT INTO agent_registry_operation VALUES(?,?,?,?,?)",(operation_id,od,sha256(raw.encode()).hexdigest(),raw,at))
    def register_spec(self,spec:AgentSpec,*,operation_id:str,evidence_refs:tuple[str,...]):
        spec.validate();dg=_spec_digest(spec);payload={"kind":"register_spec","agent_id":spec.agent_id,"version":spec.version,"spec_digest":dg,"evidence_refs":list(evidence_refs)}
        with self._write() as c:
            od,cached=self._op(c,operation_id,payload)
            if cached:return AgentSpecKey(**cached).validate()
            if not evidence_refs:raise AgentRegistryStateError("spec registration requires evidence")
            existing=c.execute("SELECT spec_digest FROM agent_registry_spec WHERE agent_id=? AND version=?",(spec.agent_id,spec.version)).fetchone()
            if existing:raise AgentRegistryStateError("spec identity/version already exists; use replay operation")
            if c.execute("SELECT 1 FROM agent_registry_active_spec WHERE agent_id=?",(spec.agent_id,)).fetchone():raise AgentRegistryStateError("agent already has canonical spec; explicit supersession required")
            at=self._now(c);c.execute("INSERT INTO agent_registry_spec VALUES(?,?,?,?,?)",(spec.agent_id,spec.version,dg,canonical_json(_spec_dict(spec)).decode(),at));c.execute("INSERT INTO agent_registry_active_spec VALUES(?,?,?,?)",(spec.agent_id,spec.version,dg,at));key=AgentSpecKey(spec.agent_id,spec.version,dg);self._append(c,"SPEC_REGISTERED",spec.agent_id,None,payload,at);result=asdict(key);self._save_op(c,operation_id,od,result,at);return key
    def supersede_spec(self,new_spec:AgentSpec,*,expected_version:str,expected_digest:str,operation_id:str,evidence_refs:tuple[str,...]):
        new_spec.validate();nd=_spec_digest(new_spec);payload={"kind":"supersede_spec","agent_id":new_spec.agent_id,"expected_version":expected_version,"expected_digest":expected_digest,"new_version":new_spec.version,"new_digest":nd,"evidence_refs":list(evidence_refs)}
        with self._write() as c:
            od,cached=self._op(c,operation_id,payload)
            if cached:return AgentSpecKey(**cached).validate()
            if not evidence_refs:raise AgentRegistryStateError("supersession requires evidence")
            cur=c.execute("SELECT version,spec_digest FROM agent_registry_active_spec WHERE agent_id=?",(new_spec.agent_id,)).fetchone()
            if not cur or (cur[0],cur[1])!=(expected_version,expected_digest):raise AgentRegistryStateError("exact current spec binding mismatch")
            if c.execute("SELECT 1 FROM agent_registry_spec WHERE agent_id=? AND version=?",(new_spec.agent_id,new_spec.version)).fetchone():raise AgentRegistryStateError("historical version rollback/reuse denied")
            at=self._now(c);c.execute("INSERT INTO agent_registry_spec VALUES(?,?,?,?,?)",(new_spec.agent_id,new_spec.version,nd,canonical_json(_spec_dict(new_spec)).decode(),at));c.execute("UPDATE agent_registry_active_spec SET version=?,spec_digest=?,activated_at=? WHERE agent_id=?",(new_spec.version,nd,at,new_spec.agent_id));key=AgentSpecKey(new_spec.agent_id,new_spec.version,nd);self._append(c,"SPEC_SUPERSEDED",new_spec.agent_id,None,payload,at);result=asdict(key);self._save_op(c,operation_id,od,result,at);return key
    def register_instance(self,*,instance_id:str,agent_id:str,spec_version:str,spec_digest:str,operation_id:str,evidence_refs:tuple[str,...]):
        payload={"kind":"register_instance","instance_id":instance_id,"agent_id":agent_id,"spec_version":spec_version,"spec_digest":spec_digest,"evidence_refs":list(evidence_refs)}
        with self._write() as c:
            od,cached=self._op(c,operation_id,payload)
            if cached:return AgentInstance(**{**cached,"evidence_refs":tuple(cached["evidence_refs"])}).validate()
            r=c.execute("SELECT spec_digest FROM agent_registry_spec WHERE agent_id=? AND version=?",(agent_id,spec_version)).fetchone()
            if not r or r[0]!=spec_digest:raise AgentRegistryStateError("instance exact spec binding unavailable")
            at=self._now(c);inst=AgentInstance(instance_id,agent_id,spec_version,spec_digest,"REGISTERED",0,at,at,evidence_refs).validate();c.execute("INSERT INTO agent_registry_instance VALUES(?,?,?,?,?,?,?,?,?)",(instance_id,agent_id,spec_version,spec_digest,"REGISTERED",0,at,at,json.dumps(evidence_refs)));self._append(c,"INSTANCE_REGISTERED",agent_id,instance_id,payload,at);result=asdict(inst);result["evidence_refs"]=list(evidence_refs);self._save_op(c,operation_id,od,result,at);return inst
    def transition_instance(self,instance_id:str,to_state:str,*,operation_id:str,evidence_refs:tuple[str,...]):
        allowed={"REGISTERED":{"ACTIVE","REVOKED","TERMINATED"},"ACTIVE":{"SUSPENDED","REVOKED","TERMINATED"},"SUSPENDED":{"ACTIVE","REVOKED","TERMINATED"}}
        payload={"kind":"transition_instance","instance_id":instance_id,"to_state":to_state,"evidence_refs":list(evidence_refs)}
        with self._write() as c:
            od,cached=self._op(c,operation_id,payload)
            if cached:return AgentInstance(**{**cached,"evidence_refs":tuple(cached["evidence_refs"])}).validate()
            r=c.execute("SELECT * FROM agent_registry_instance WHERE instance_id=?",(instance_id,)).fetchone()
            if not r:raise AgentRegistryStateError("unknown instance")
            if to_state not in allowed.get(r["state"],set()):raise AgentRegistryStateError("instance transition denied")
            at=self._now(c);gen=r["generation"]+1;c.execute("UPDATE agent_registry_instance SET state=?,generation=?,updated_at=?,evidence_refs_json=? WHERE instance_id=?",(to_state,gen,at,json.dumps(evidence_refs),instance_id));inst=AgentInstance(instance_id,r["agent_id"],r["spec_version"],r["spec_digest"],to_state,gen,r["created_at"],at,evidence_refs).validate();self._append(c,"INSTANCE_TRANSITIONED",r["agent_id"],instance_id,payload,at);result=asdict(inst);result["evidence_refs"]=list(evidence_refs);self._save_op(c,operation_id,od,result,at);return inst
    def resolve_for_mission(self,mission:MissionSpec)->AgentRegistryProjection:
        mission.validate();c=self.open_query_reader()
        try:
            meta=c.execute("SELECT registry_id,revision,event_head FROM agent_registry_meta WHERE singleton=1").fetchone();rows=c.execute("SELECT s.spec_json FROM agent_registry_active_spec a JOIN agent_registry_spec s ON s.agent_id=a.agent_id AND s.version=a.version ORDER BY a.agent_id,a.version,a.spec_digest").fetchall();specs=[]
            for r in rows:
                s=_spec_from(r[0]);
                if set(s.capabilities)&set(mission.required_capabilities):specs.append(_spec_dict(s))
            payload={"registry_id":meta[0],"revision":meta[1],"event_head":meta[2],"mission_id":mission.mission_id,"required_capabilities":list(mission.required_capabilities),"candidate_specs":specs};dg=sha256(canonical_json(payload)).hexdigest();return AgentRegistryProjection(meta[0],meta[1],meta[2],mission.mission_id,mission.required_capabilities,tuple(specs),dg).verify_digest()
        finally:c.close()
    def snapshot(self):
        c=self.open_query_reader()
        try:
            m=c.execute("SELECT registry_id,revision,event_head FROM agent_registry_meta WHERE singleton=1").fetchone();keys=tuple(AgentSpecKey(*r) for r in c.execute("SELECT agent_id,version,spec_digest FROM agent_registry_active_spec ORDER BY agent_id"));inst=[]
            for r in c.execute("SELECT * FROM agent_registry_instance ORDER BY instance_id"):inst.append(AgentInstance(r["instance_id"],r["agent_id"],r["spec_version"],r["spec_digest"],r["state"],r["generation"],r["created_at"],r["updated_at"],tuple(json.loads(r["evidence_refs_json"]))).validate())
            return AgentRegistrySnapshot(m[0],m[1],m[2],keys,tuple(inst)).validate()
        finally:c.close()
    def verify_event_chain(self,conn=None):
        c=conn or self.open_query_reader();close=conn is None;prev=_ZERO;last_time=None
        try:
            for r in c.execute("SELECT * FROM agent_registry_event ORDER BY seq"):
                payload=json.loads(r["payload_json"]);exp=_event_digest(prev,r["event_type"],r["agent_id"],r["instance_id"],payload,r["observed_at"]);t=_parse(r["observed_at"])
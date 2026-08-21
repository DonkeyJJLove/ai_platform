"""Restart-durable deterministic fleet coordination state for F005-B R1."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
from typing import Callable, Iterator, Mapping, Sequence

from cyber_lion.contracts.fleet_coordination import (
    TERMINAL_STATES,
    FleetCoordinationSnapshot,
    FleetCoordinationSpec,
    FleetDispatch,
    FleetLease,
    FleetMissionState,
    FleetPlanRequest,
    canonical_json,
)

_SHA256=re.compile(r"^[0-9a-f]{64}$")
_ZERO="0"*64

class FleetCoordinationStateError(RuntimeError):
    pass

def _text(v:object,n:str)->str:
    if not isinstance(v,str) or not v.strip() or "\x00" in v: raise FleetCoordinationStateError(f"{n} is invalid")
    return v

def _digest(v:object,n:str)->str:
    v=_text(v,n)
    if not _SHA256.fullmatch(v): raise FleetCoordinationStateError(f"{n} must be sha256 hex")
    return v

def _utc(v:datetime)->str:
    if not isinstance(v,datetime) or v.tzinfo is None: raise FleetCoordinationStateError("trusted clock must be timezone-aware")
    return v.astimezone(timezone.utc).isoformat()

def _parse_time(v:str)->datetime:
    try: x=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as e: raise FleetCoordinationStateError("stored timestamp invalid") from e
    if x.tzinfo is None: raise FleetCoordinationStateError("stored timestamp not timezone-aware")
    return x.astimezone(timezone.utc)

def _path_overlap(a:str,b:str)->bool:
    x=PurePosixPath(a).parts; y=PurePosixPath(b).parts; n=min(len(x),len(y)); return x[:n]==y[:n]

def _event_digest(prev:str,event_type:str,mission_id:str|None,payload:Mapping[str,object],observed_at:str)->str:
    return sha256(canonical_json({"previous_digest":prev,"event_type":event_type,"mission_id":mission_id,"payload":dict(payload),"observed_at":observed_at})).hexdigest()

def _dispatches_json(xs:Sequence[FleetDispatch])->str:
    return json.dumps([x.canonical_dict() for x in xs],sort_keys=True,separators=(",",":"),ensure_ascii=False)

def _request_from_json(raw:str)->FleetPlanRequest:
    try: v=json.loads(raw)
    except json.JSONDecodeError as e: raise FleetCoordinationStateError("stored request JSON invalid") from e
    if not isinstance(v,dict): raise FleetCoordinationStateError("stored request invalid")
    try:
        return FleetPlanRequest(v["request_id"],v["coordinator_id"],tuple(tuple(x) for x in v["current_heads"]),v["max_parallel"]).validate()
    except (KeyError,TypeError,ValueError) as e: raise FleetCoordinationStateError("stored request failed reconstruction") from e

def _dispatches_from_json(raw:str)->tuple[FleetDispatch,...]:
    try: vals=json.loads(raw)
    except json.JSONDecodeError as e: raise FleetCoordinationStateError("stored result JSON invalid") from e
    if not isinstance(vals,list): raise FleetCoordinationStateError("stored result invalid")
    out=[]
    for v in vals:
        if not isinstance(v,dict): raise FleetCoordinationStateError("stored dispatch invalid")
        try:
            out.append(FleetDispatch(v["dispatch_id"],v["fencing_token"],v["request_id"],v["coordinator_id"],v["mission_id"],v["drone_id"],v["generation"],v["repository"],v["baseline_sha"],v["baseline_tree_sha"],v["branch"],tuple(v["write_scope"]),v["issued_at"]).validate())
        except (KeyError,TypeError,ValueError) as e: raise FleetCoordinationStateError("stored dispatch failed reconstruction") from e
    return tuple(out)

class FleetCoordinationStore:
    def __init__(self,db_path:str|Path,*,coordinator_id:str,clock:Callable[[],datetime])->None:
        self._coordinator_id=_text(coordinator_id,"coordinator_id"); self._clock=clock; self._db_path=str(Path(db_path)); self._conn=sqlite3.connect(self._db_path,isolation_level=None)
        try:
            self._conn.row_factory=sqlite3.Row; self._conn.execute("PRAGMA foreign_keys=ON"); self._conn.execute("PRAGMA journal_mode=WAL"); self._conn.execute("PRAGMA synchronous=FULL"); self._conn.execute("PRAGMA busy_timeout=5000")
            self._init_schema(); self._bind(); self.verify_event_chain(self._conn); self._verify_consistency(self._conn)
        except Exception:
            self._conn.close(); raise
    @property
    def coordinator_id(self): return self._coordinator_id
    @property
    def db_path(self): return self._db_path
    def close(self): self._conn.close()
    def _init_schema(self):
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS fleet_coordination_meta(singleton INTEGER PRIMARY KEY CHECK(singleton=1),coordinator_id TEXT NOT NULL,revision INTEGER NOT NULL,event_head TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS fleet_coordination_mission(mission_id TEXT PRIMARY KEY,drone_id TEXT NOT NULL UNIQUE,repository TEXT NOT NULL,baseline_sha TEXT NOT NULL,baseline_tree_sha TEXT NOT NULL,branch TEXT NOT NULL,write_scope_json TEXT NOT NULL,dependencies_json TEXT NOT NULL,evidence_refs_json TEXT NOT NULL,spec_digest TEXT NOT NULL UNIQUE,state TEXT NOT NULL,generation INTEGER NOT NULL,dispatch_id TEXT,fencing_token TEXT,terminal_evidence_ref TEXT,last_requeue_evidence_ref TEXT,registered_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS fleet_coordination_dependency(mission_id TEXT NOT NULL REFERENCES fleet_coordination_mission(mission_id) ON DELETE RESTRICT,dependency_mission_id TEXT NOT NULL,PRIMARY KEY(mission_id,dependency_mission_id));
        CREATE TABLE IF NOT EXISTS fleet_coordination_active_lease(repository TEXT NOT NULL,lease_kind TEXT NOT NULL,resource TEXT NOT NULL,mission_id TEXT NOT NULL REFERENCES fleet_coordination_mission(mission_id) ON DELETE RESTRICT,drone_id TEXT NOT NULL,dispatch_id TEXT NOT NULL,generation INTEGER NOT NULL,acquired_at TEXT NOT NULL,PRIMARY KEY(repository,lease_kind,resource));
        CREATE TABLE IF NOT EXISTS fleet_coordination_plan(request_id TEXT PRIMARY KEY,request_digest TEXT NOT NULL,request_json TEXT NOT NULL,result_json TEXT NOT NULL,result_digest TEXT NOT NULL,observed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS fleet_coordination_event(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL UNIQUE,event_type TEXT NOT NULL,mission_id TEXT,payload_json TEXT NOT NULL,previous_digest TEXT NOT NULL,event_digest TEXT NOT NULL UNIQUE,observed_at TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS fleet_coordination_plan_no_update BEFORE UPDATE ON fleet_coordination_plan BEGIN SELECT RAISE(ABORT,'fleet_coordination_plan is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS fleet_coordination_plan_no_delete BEFORE DELETE ON fleet_coordination_plan BEGIN SELECT RAISE(ABORT,'fleet_coordination_plan is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS fleet_coordination_event_no_update BEFORE UPDATE ON fleet_coordination_event BEGIN SELECT RAISE(ABORT,'fleet_coordination_event is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS fleet_coordination_event_no_delete BEFORE DELETE ON fleet_coordination_event BEGIN SELECT RAISE(ABORT,'fleet_coordination_event is append-only'); END;
        """)
    def _bind(self):
        row=self._conn.execute("SELECT coordinator_id FROM fleet_coordination_meta WHERE singleton=1").fetchone()
        if row is None: self._conn.execute("INSERT INTO fleet_coordination_meta VALUES(1,?,?,?)",(self._coordinator_id,0,_ZERO))
        elif row["coordinator_id"]!=self._coordinator_id: raise FleetCoordinationStateError("coordinator instance substitution denied")
    @contextmanager
    def _write(self)->Iterator[sqlite3.Connection]:
        try:
            self._conn.execute("BEGIN IMMEDIATE"); yield self._conn; self._conn.execute("COMMIT")
        except Exception:
            if self._conn.in_transaction: self._conn.execute("ROLLBACK")
            raise
    def open_query_reader(self):
        c=sqlite3.connect(self._db_path,isolation_level=None); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA query_only=ON"); return c
    def _now(self,c):
        now=_utc(self._clock()); row=c.execute("SELECT observed_at FROM fleet_coordination_event ORDER BY seq DESC LIMIT 1").fetchone()
        if row is not None and _parse_time(now)<_parse_time(row["observed_at"]): raise FleetCoordinationStateError("trusted clock rollback denied")
        return now
    def _bump(self,c): c.execute("UPDATE fleet_coordination_meta SET revision=revision+1 WHERE singleton=1")
    def _append_event(self,c,*,event_type,mission_id,payload,observed_at):
        prev=c.execute("SELECT event_head FROM fleet_coordination_meta WHERE singleton=1").fetchone()[0]; d=_event_digest(prev,event_type,mission_id,payload,observed_at)
        c.execute("INSERT INTO fleet_coordination_event(event_id,event_type,mission_id,payload_json,previous_digest,event_digest,observed_at) VALUES(?,?,?,?,?,?,?)",(d,event_type,mission_id,canonical_json(payload).decode(),prev,d,observed_at)); c.execute("UPDATE fleet_coordination_meta SET event_head=? WHERE singleton=1",(d,)); return d
    def verify_event_chain(self,conn=None):
        c=conn or self.open_query_reader(); close=conn is None; prev=_ZERO; last=prev; last_time=None
        try:
            for r in c.execute("SELECT * FROM fleet_coordination_event ORDER BY seq"):
                try: payload=json.loads(r["payload_json"])
                except json.JSONDecodeError as e: raise FleetCoordinationStateError("event payload corruption") from e
                if not isinstance(payload,dict): raise FleetCoordinationStateError("event payload corruption")
                exp=_event_digest(prev,r["event_type"],r["mission_id"],payload,r["observed_at"]); t=_parse_time(r["observed_at"])
                if last_time and t<last_time: raise FleetCoordinationStateError("event time ordering corruption")
                if r["previous_digest"]!=prev or r["event_digest"]!=exp or r["event_id"]!=exp: raise FleetCoordinationStateError("event chain corruption")
                prev=last=exp; last_time=t
            if c.execute("SELECT event_head FROM fleet_coordination_meta WHERE singleton=1").fetchone()[0]!=last: raise FleetCoordinationStateError("event chain head mismatch")
            return last
        finally:
            if close: c.close()
    def register_mission(self,spec:FleetCoordinationSpec):
        spec.validate(); dg=spec.digest()
        with self._write() as c:
            row=c.execute("SELECT spec_digest FROM fleet_coordination_mission WHERE mission_id=?",(spec.mission_id,)).fetchone()
            if row is not None:
                if row[0]==dg: return
                raise FleetCoordinationStateError("mission identity substitution denied")
            if c.execute("SELECT 1 FROM fleet_coordination_mission WHERE drone_id=?",(spec.drone_id,)).fetchone(): raise FleetCoordinationStateError("drone already bound")
            graph=self._dependency_graph(c); graph[spec.mission_id]=frozenset(spec.dependencies)
            if self._has_cycle(graph): raise FleetCoordinationStateError("dependency cycle detected")
            now=self._now(c)
            c.execute("INSERT INTO fleet_coordination_mission VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(spec.mission_id,spec.drone_id,spec.repository,spec.baseline_sha,spec.baseline_tree_sha,spec.branch,json.dumps(spec.write_scope,separators=(",",":")),json.dumps(spec.dependencies,separators=(",",":")),json.dumps(spec.evidence_refs,separators=(",",":")),dg,"STARTING",0,None,None,None,None,now,now))
            for dep in spec.dependencies: c.execute("INSERT INTO fleet_coordination_dependency VALUES(?,?)",(spec.mission_id,dep))
            self._append_event(c,event_type="MISSION_REGISTERED",mission_id=spec.mission_id,payload={"drone_id":spec.drone_id,"spec_digest":dg},observed_at=now); self._bump(c)
    def plan(self,request:FleetPlanRequest):
        request.validate()
        if request.coordinator_id!=self._coordinator_id: raise FleetCoordinationStateError("plan coordinator mismatch")
        rd=request.digest()
        with self._write() as c:
            cached=c.execute("SELECT request_digest,result_json,result_digest FROM fleet_coordination_plan WHERE request_id=?",(request.request_id,)).fetchone()
            if cached:
                if cached[0]!=rd: raise FleetCoordinationStateError("request_id replay substitution denied")
                if sha256(cached[1].encode()).hexdigest()!=cached[2]: raise FleetCoordinationStateError("stored plan result digest mismatch")
                return _dispatches_from_json(cached[1])
            now=self._now(c); heads=request.head_map(); selected=[]
            for row in c.execute("SELECT * FROM fleet_coordination_mission WHERE state IN ('STARTING','WAITING') ORDER BY mission_id").fetchall():
                if len(selected)>=request.max_parallel: break
                if not self._dependencies_done(c,row["mission_id"]): continue
                head=heads.get(row["repository"])
                if head is None: raise FleetCoordinationStateError(f"current head missing for repository: {row['repository']}")
                if head!=row["baseline_sha"]: raise FleetCoordinationStateError(f"stale baseline: {row['repository']}:{row['mission_id']}")
                scope=tuple(json.loads(row["write_scope_json"]))
                if not self._leases_available(c,row["repository"],row["branch"],scope): continue
                gen=row["generation"]+1; seed={"coordinator_id":self._coordinator_id,"request_digest":rd,"mission_id":row["mission_id"],"drone_id":row["drone_id"],"spec_digest":row["spec_digest"],"generation":gen,"issued_at":now}
                did=sha256(canonical_json({"kind":"dispatch",**seed})).hexdigest(); fence=sha256(canonical_json({"kind":"fence",**seed})).hexdigest()
                d=FleetDispatch(did,fence,request.request_id,self._coordinator_id,row["mission_id"],row["drone_id"],gen,row["repository"],row["baseline_sha"],row["baseline_tree_sha"],row["branch"],scope,now).validate(); self._claim_leases(c,d)
                c.execute("UPDATE fleet_coordination_mission SET state='RUNNING',generation=?,dispatch_id=?,fencing_token=?,terminal_evidence_ref=NULL,last_requeue_evidence_ref=NULL,updated_at=? WHERE mission_id=?",(gen,did,fence,now,row["mission_id"]))
                self._append_event(c,event_type="MISSION_DISPATCHED",mission_id=row["mission_id"],payload={"request_id":request.request_id,"request_digest":rd,"dispatch_id":did,"fencing_token":fence,"generation":gen,"spec_digest":row["spec_digest"]},observed_at=now); selected.append(d)
            result=_dispatches_json(selected); result_digest=sha256(result.encode()).hexdigest(); req_json=canonical_json(request.canonical_dict()).decode()
            c.execute("INSERT INTO fleet_coordination_plan VALUES(?,?,?,?,?,?)",(request.request_id,rd,req_json,result,result_digest,now)); self._append_event(c,event_type="PLAN_COMMITTED",mission_id=None,payload={"request_id":request.request_id,"request_digest":rd,"result_digest":result_digest,"dispatch_ids":[x.dispatch_id for x in selected]},observed_at=now); self._bump(c); return tuple(selected)
    def requeue(self,mission_id,*,dispatch_id,fencing_token,evidence_ref):
        _text(mission_id,"mission_id"); _digest(dispatch_id,"dispatch_id"); _digest(fencing_token,"fencing_token"); _text(evidence_ref,"evidence_ref")
        with self._write() as c:
            row=self._require_mission(c,mission_id)
            if row["state"]=="WAITING":
                if row["dispatch_id"]==dispatch_id and row["fencing_token"]==fencing_token and row["last_requeue_evidence_ref"]==evidence_ref: return
                raise FleetCoordinationStateError("requeue replay mismatch")
            if row["state"]!="RUNNING": raise FleetCoordinationStateError("only RUNNING may requeue")
            self._require_active(row,dispatch_id,fencing_token); now=self._now(c); released=self._release(c,mission_id,dispatch_id)
            c.execute("UPDATE fleet_coordination_mission SET state='WAITING',terminal_evidence_ref=NULL,last_requeue_evidence_ref=?,updated_at=? WHERE mission_id=?",(evidence_ref,now,mission_id)); self._append_event(c,event_type="MISSION_REQUEUED",mission_id=mission_id,payload={"dispatch_id":dispatch_id,"generation":row["generation"],"evidence_ref":evidence_ref,"released_lease_count":released},observed_at=now); self._bump(c)
    def record_terminal(self,mission_id,*,dispatch_id,fencing_token,terminal_state,evidence_ref):
        _text(mission_id,"mission_id"); _digest(dispatch_id,"dispatch_id"); _digest(fencing_token,"fencing_token"); _text(evidence_ref,"evidence_ref")
        if terminal_state not in TERMINAL_STATES: raise FleetCoordinationStateError("terminal_state invalid")
        with self._write() as c:
            row=self._require_mission(c,mission_id)
            if row["state"] in TERMINAL_STATES:
                if row["state"]==terminal_state and row["dispatch_id"]==dispatch_id and row["fencing_token"]==fencing_token and row["terminal_evidence_ref"]==evidence_ref: return
                raise FleetCoordinationStateError("terminal replay mismatch")
            if row["state"]!="RUNNING": raise FleetCoordinationStateError("only RUNNING may become terminal")
            self._require_active(row,dispatch_id,fencing_token); now=self._now(c); released=self._release(c,mission_id,dispatch_id)
            c.execute("UPDATE fleet_coordination_mission SET state=?,terminal_evidence_ref=?,last_requeue_evidence_ref=NULL,updated_at=? WHERE mission_id=?",(terminal_state,evidence_ref,now,mission_id)); self._append_event(c,event_type="MISSION_TERMINAL",mission_id=mission_id,payload={"dispatch_id":dispatch_id,"generation":row["generation"],"terminal_state":terminal_state,"evidence_ref":evidence_ref,"released_lease_count":released},observed_at=now); self._bump(c)
    def mission_state(self,mission_id):
        c=self.open_query_reader()
        try: return self._mission_state(self._require_mission(c,mission_id))
        finally: c.close()
    def active_leases(self):
        c=self.open_query_reader()
        try: return self._leases(c)
        finally: c.close()
    def snapshot(self):
        c=self.open_query_reader()
        try:
            meta=c.execute("SELECT coordinator_id,revision,event_head FROM fleet_coordination_meta WHERE singleton=1").fetchone(); missions=tuple(self._mission_state(r) for r in c.execute("SELECT * FROM fleet_coordination_mission ORDER BY mission_id")); return FleetCoordinationSnapshot(meta[0],meta[1],meta[2],missions,self._leases(c)).validate()
        finally: c.close()
    def _mission_state(self,r): return FleetMissionState(r["mission_id"],r["drone_id"],r["state"],r["generation"],r["spec_digest"],r["dispatch_id"],r["fencing_token"],r["terminal_evidence_ref"],r["updated_at"]).validate()
    def _leases(self,c): return tuple(FleetLease(r["mission_id"],r["drone_id"],r["dispatch_id"],r["generation"],r["repository"],r["lease_kind"],r["resource"],r["acquired_at"]).validate() for r in c.execute("SELECT * FROM fleet_coordination_active_lease ORDER BY repository,lease_kind,resource"))
    def _dependency_graph(self,c):
        g={r[0]:set() for r in c.execute("SELECT mission_id FROM fleet_coordination_mission")}
        for r in c.execute("SELECT mission_id,dependency_mission_id FROM fleet_coordination_dependency"): g.setdefault(r[0],set()).add(r[1])
        return {k:frozenset(v) for k,v in g.items()}
    @staticmethod
    def _has_cycle(g):
        visiting=set(); visited=set()
        def visit(n):
            if n in visited:return False
            if n in visiting:return True
            visiting.add(n)
            for d in g.get(n,frozenset()):
                if d in g and visit(d):return True
            visiting.remove(n); visited.add(n); return False
        return any(visit(n) for n in g)
    def _dependencies_done(self,c,mid):
        rows=c.execute("SELECT d.dependency_mission_id,m.state FROM fleet_coordination_dependency d LEFT JOIN fleet_coordination_mission m ON m.mission_id=d.dependency_mission_id WHERE d.mission_id=?",(mid,)).fetchall(); return all(r[1]=="DONE" for r in rows)
    def _leases_available(self,c,repo,branch,scope):
        if c.execute("SELECT 1 FROM fleet_coordination_active_lease WHERE repository=? AND lease_kind='BRANCH' AND resource=?",(repo,branch)).fetchone(): return False
        paths=[r[0] for r in c.execute("SELECT resource FROM fleet_coordination_active_lease WHERE repository=? AND lease_kind='PATH'",(repo,))]; return not any(_path_overlap(a,b) for a in scope for b in paths)
    def _claim_leases(self,c,d):
        vals=[(d.repository,"BRANCH",d.branch,d.mission_id,d.drone_id,d.dispatch_id,d.generation,d.issued_at)]+[(d.repository,"PATH",p,d.mission_id,d.drone_id,d.dispatch_id,d.generation,d.issued_at) for p in d.write_scope]
        try:c.executemany("INSERT INTO fleet_coordination_active_lease VALUES(?,?,?,?,?,?,?,?)",vals)
        except sqlite3.IntegrityError as e: raise FleetCoordinationStateError("lease conflict during atomic claim") from e
    @staticmethod
    def _release(c,mid,did): return c.execute("DELETE FROM fleet_coordination_active_lease WHERE mission_id=? AND dispatch_id=?",(mid,did)).rowcount
    @staticmethod
    def _require_mission(c,mid):
        r=c.execute("SELECT * FROM fleet_coordination_mission WHERE mission_id=?",(mid,)).fetchone()
        if r is None: raise FleetCoordinationStateError(f"unknown mission: {mid}")
        return r
    @staticmethod
    def _require_active(r,did,fence):
        if r["dispatch_id"]!=did or r["fencing_token"]!=fence: raise FleetCoordinationStateError("stale or foreign dispatch fencing token denied")
    def _reconstruct_spec(self,r):
        try:
            scope=tuple(json.loads(r["write_scope_json"])); deps=tuple(json.loads(r["dependencies_json"])); evidence=tuple(json.loads(r["evidence_refs_json"]))
            return FleetCoordinationSpec(r["mission_id"],r["drone_id"],r["repository"],r["baseline_sha"],r["baseline_tree_sha"],r["branch"],scope,deps,evidence).validate()
        except (json.JSONDecodeError,TypeError,ValueError) as e: raise FleetCoordinationStateError("mission spec reconstruction failed") from e
    def _verify_materialized_state_from_events(self,c):
        replay={}
        for e in c.execute("SELECT event_type,mission_id,payload_json FROM fleet_coordination_event ORDER BY seq"):
            payload=json.loads(e["payload_json"]); mid=e["mission_id"]; typ=e["event_type"]
            if typ=="MISSION_REGISTERED": replay[mid]={"state":"STARTING","generation":0,"dispatch_id":None,"fencing_token":None,"terminal_evidence_ref":None,"last_requeue_evidence_ref":None}
            elif typ=="MISSION_DISPATCHED": replay[mid].update(state="RUNNING",generation=payload["generation"],dispatch_id=payload["dispatch_id"],fencing_token=payload["fencing_token"],terminal_evidence_ref=None,last_requeue_evidence_ref=None)
            elif typ=="MISSION_REQUEUED": replay[mid].update(state="WAITING",last_requeue_evidence_ref=payload["evidence_ref"],terminal_evidence_ref=None)
            elif typ=="MISSION_TERMINAL": replay[mid].update(state=payload["terminal_state"],terminal_evidence_ref=payload["evidence_ref"],last_requeue_evidence_ref=None)
        rows=list(c.execute("SELECT * FROM fleet_coordination_mission"))
        if set(replay)!= {r["mission_id"] for r in rows}: raise FleetCoordinationStateError("event/materialized mission population mismatch")
        for r in rows:
            x=replay[r["mission_id"]]
            for k in ("state","generation","dispatch_id","fencing_token","terminal_evidence_ref","last_requeue_evidence_ref"):
                if r[k]!=x[k]: raise FleetCoordinationStateError(f"materialized mission state mismatch: {k}")
    def _verify_consistency(self,c):
        specs={}
        for r in c.execute("SELECT * FROM fleet_coordination_mission"):
            spec=self._reconstruct_spec(r)
            if spec.digest()!=r["spec_digest"]: raise FleetCoordinationStateError("mission spec digest mismatch")
            deps={x[0] for x in c.execute("SELECT dependency_mission_id FROM fleet_coordination_dependency WHERE mission_id=?",(r["mission_id"],))}
            if deps!=set(spec.dependencies): raise FleetCoordinationStateError("dependency materialization mismatch")
            specs[r["mission_id"]]=spec
        all_dispatches={}
        for r in c.execute("SELECT * FROM fleet_coordination_plan"):
            req=_request_from_json(r["request_json"])
            if req.request_id!=r["request_id"] or req.coordinator_id!=self._coordinator_id or req.digest()!=r["request_digest"]: raise FleetCoordinationStateError("plan request digest/materialization mismatch")
            if sha256(r["result_json"].encode()).hexdigest()!=r["result_digest"]: raise FleetCoordinationStateError("stored plan result digest mismatch")
            for d in _dispatches_from_json(r["result_json"]):
                spec=specs.get(d.mission_id)
                if spec is None: raise FleetCoordinationStateError("dispatch references unknown mission")
                try:d.validate_for(spec,req)
                except ValueError as e: raise FleetCoordinationStateError("dispatch-to-spec binding mismatch") from e
                all_dispatches[d.dispatch_id]=d
        self._verify_materialized_state_from_events(c)
        active_by={}
        for l in c.execute("SELECT * FROM fleet_coordination_active_lease"): active_by.setdefault(l["mission_id"],[]).append(l)
        for r in c.execute("SELECT * FROM fleet_coordination_mission"):
            leases=active_by.get(r["mission_id"],[])
            if r["generation"]>0:
                d=all_dispatches.get(r["dispatch_id"])
                if d is None or d.fencing_token!=r["fencing_token"] or d.generation!=r["generation"]: raise FleetCoordinationStateError("materialized dispatch binding mismatch")
            if r["state"]=="RUNNING":
                spec=specs[r["mission_id"]]; expected={("BRANCH",spec.branch)}|{("PATH",p) for p in spec.write_scope}; actual={(x["lease_kind"],x["resource"]) for x in leases}
                if expected!=actual: raise FleetCoordinationStateError("RUNNING mission lease set mismatch")
                for x in leases:
                    if x["dispatch_id"]!=r["dispatch_id"] or x["generation"]!=r["generation"] or x["drone_id"]!=r["drone_id"] or x["repository"]!=r["repository"]: raise FleetCoordinationStateError("active lease binding mismatch")
            elif leases: raise FleetCoordinationStateError("non-RUNNING mission owns active leases")

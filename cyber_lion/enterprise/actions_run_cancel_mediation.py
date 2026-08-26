from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json,re,sqlite3
from threading import RLock
from typing import Protocol
from cyber_lion.contracts.actions_run_cancel import ActionsRunCancelRequest

_HEX64=re.compile(r"^[0-9a-f]{64}$")
_STATES={"PREPARED","ATTEMPTED","OBSERVED","RECONCILED","UNKNOWN"}

class ActionsRunCancelMediationError(RuntimeError): pass

def _digest(domain:bytes,value:object)->str:
    return sha256(domain+json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def _hex64(v:str,name:str)->str:
    if not isinstance(v,str) or _HEX64.fullmatch(v) is None: raise ActionsRunCancelMediationError(f"{name} invalid")
    return v

@dataclass(frozen=True)
class CanonicalActionsRunCancelAdmission:
    request_digest:str; repository:str; run_id:int; expected_workflow:str; expected_event:str; expected_head_sha:str
    authority_lineage_digest:str; pdp_decision_digest:str; provider_id:str; authority_epoch:int; admission_digest:str=""
    def payload(self):
        v=asdict(self); v.pop("admission_digest"); return v
    def validate(self):
        for n in ("request_digest","authority_lineage_digest","pdp_decision_digest"): _hex64(getattr(self,n),n)
        if self.repository!="DonkeyJJLove/ai_platform" or self.run_id<=0 or not self.expected_workflow or not self.expected_event or not self.provider_id: raise ActionsRunCancelMediationError("admission identity invalid")
        expected=_digest(b"LION/ACTIONS-RUN-CANCEL-ADMISSION/1\0",self.payload())
        if self.admission_digest and self.admission_digest!=expected: raise ActionsRunCancelMediationError("admission digest mismatch")
        return self
    def sealed(self):
        self.validate(); return CanonicalActionsRunCancelAdmission(**{**self.payload(),"admission_digest":_digest(b"LION/ACTIONS-RUN-CANCEL-ADMISSION/1\0",self.payload())}).validate()
    def binds(self,request:ActionsRunCancelRequest):
        if (self.request_digest,self.repository,self.run_id,self.expected_workflow,self.expected_event,self.expected_head_sha)!=(request.payload_digest(),request.repository,request.run_id,request.expected_workflow,request.expected_event,request.expected_head_sha):
            raise ActionsRunCancelMediationError("admission/request binding mismatch")

class ActionsRunCancelAdmissionResolver(Protocol):
    def resolve(self,request:ActionsRunCancelRequest)->CanonicalActionsRunCancelAdmission: ...
class ActionsRunReader(Protocol):
    def get_run(self,run_id:int)->dict: ...
class ActionsRunCancelEffect(Protocol):
    def cancel_exact(self,request:ActionsRunCancelRequest,admission:CanonicalActionsRunCancelAdmission)->None: ...

@dataclass(frozen=True)
class ActionsRunCancelFenceRecord:
    effect_key:str; admission_digest:str; request_digest:str; repository:str; run_id:int; state:str; prepared_at:str
    attempted_at:str|None=None; observed_at:str|None=None; reconciled_at:str|None=None; observation_digest:str|None=None; reconciliation_digest:str|None=None

class DurableActionsRunCancelFence:
    def __init__(self,database_path:str):
        p=Path(database_path)
        if not p.is_absolute(): raise ActionsRunCancelMediationError("fence path must be absolute")
        p.parent.mkdir(parents=True,exist_ok=True); self._p=str(p); self._lock=RLock(); self._init()
    def _c(self):
        c=sqlite3.connect(self._p,timeout=10,isolation_level=None,check_same_thread=False); c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=FULL"); return c
    def _init(self):
        with self._lock,self._c() as c:
            c.execute("CREATE TABLE IF NOT EXISTS actions_run_cancel_effect(effect_key TEXT PRIMARY KEY,admission_digest TEXT UNIQUE NOT NULL,request_digest TEXT UNIQUE NOT NULL,repository TEXT NOT NULL,run_id INTEGER NOT NULL,state TEXT NOT NULL,prepared_at TEXT NOT NULL,attempted_at TEXT,observed_at TEXT,reconciled_at TEXT,observation_digest TEXT,reconciliation_digest TEXT)")
    def get(self,key:str):
        with self._c() as c: row=c.execute("SELECT effect_key,admission_digest,request_digest,repository,run_id,state,prepared_at,attempted_at,observed_at,reconciled_at,observation_digest,reconciliation_digest FROM actions_run_cancel_effect WHERE effect_key=?",(key,)).fetchone()
        if row is None: raise ActionsRunCancelMediationError("cancel effect unknown")
        return ActionsRunCancelFenceRecord(*row)
    def prepare(self,r:ActionsRunCancelFenceRecord):
        if r.state!="PREPARED": raise ActionsRunCancelMediationError("PREPARED required")
        with self._lock,self._c() as c:
            try: c.execute("INSERT INTO actions_run_cancel_effect VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",tuple(asdict(r).values()))
            except sqlite3.IntegrityError as e: raise ActionsRunCancelMediationError("cancel replay denied") from e
    def transition(self,key:str,old:str,new:str,**kw):
        if old not in _STATES or new not in _STATES: raise ActionsRunCancelMediationError("state invalid")
        cols={"ATTEMPTED":("attempted_at",),"OBSERVED":("observed_at","observation_digest"),"RECONCILED":("reconciled_at","reconciliation_digest"),"UNKNOWN":()}
        if new=="ATTEMPTED": sql="UPDATE actions_run_cancel_effect SET state='ATTEMPTED',attempted_at=? WHERE effect_key=? AND state='PREPARED'"; args=(kw["attempted_at"],key)
        elif new=="OBSERVED": sql="UPDATE actions_run_cancel_effect SET state='OBSERVED',observed_at=?,observation_digest=? WHERE effect_key=? AND state='ATTEMPTED'"; args=(kw["observed_at"],kw["observation_digest"],key)
        elif new=="RECONCILED": sql="UPDATE actions_run_cancel_effect SET state='RECONCILED',reconciled_at=?,reconciliation_digest=? WHERE effect_key=? AND state='OBSERVED'"; args=(kw["reconciled_at"],kw["reconciliation_digest"],key)
        else: sql="UPDATE actions_run_cancel_effect SET state='UNKNOWN' WHERE effect_key=? AND state IN ('PREPARED','ATTEMPTED','OBSERVED')"; args=(key,)
        with self._lock,self._c() as c:
            cur=c.execute(sql,args)
            if cur.rowcount!=1: raise ActionsRunCancelMediationError("cancel fence transition denied")
        return self.get(key)

def actions_run_cancel_effect_key(request,admission):
    admission.validate(); admission.binds(request); _hex64(admission.admission_digest,"admission_digest")
    return _digest(b"LION/ACTIONS-RUN-CANCEL-EFFECT/1\0",{"request":request.payload_digest(),"admission":admission.admission_digest})

class CanonicalActionsRunCancelMediator:
    def __init__(self,*,admissions:ActionsRunCancelAdmissionResolver,repository:ActionsRunReader,effect:ActionsRunCancelEffect,fence:DurableActionsRunCancelFence):
        self.admissions=admissions; self.repository=repository; self.effect=effect; self.fence=fence
    def _validate_run(self,request,run):
        if run.get("id")!=request.run_id or run.get("name")!=request.expected_workflow or run.get("event")!=request.expected_event or str(run.get("head_sha",""))!=request.expected_head_sha: raise ActionsRunCancelMediationError("run currentness mismatch")
        if run.get("status") not in {"queued","in_progress"}: raise ActionsRunCancelMediationError("run not cancellable")
    def execute(self,request:ActionsRunCancelRequest):
        request.validate(); self._validate_run(request,self.repository.get_run(request.run_id))
        admission=self.admissions.resolve(request)
        if type(admission) is not CanonicalActionsRunCancelAdmission: raise ActionsRunCancelMediationError("exact admission required")
        admission.validate(); _hex64(admission.admission_digest,"admission_digest"); admission.binds(request)
        key=actions_run_cancel_effect_key(request,admission); now=datetime.now(timezone.utc).isoformat()
        self.fence.prepare(ActionsRunCancelFenceRecord(key,admission.admission_digest,request.payload_digest(),request.repository,request.run_id,"PREPARED",now))
        try:
            cur=self.admissions.resolve(request)
            if type(cur) is not CanonicalActionsRunCancelAdmission or cur.admission_digest!=admission.admission_digest: raise ActionsRunCancelMediationError("authority drift")
            self._validate_run(request,self.repository.get_run(request.run_id))
            attempted=datetime.now(timezone.utc).isoformat(); self.fence.transition(key,"PREPARED","ATTEMPTED",attempted_at=attempted)
            self.effect.cancel_exact(request,admission)
            run=self.repository.get_run(request.run_id)
            if not (run.get("status")=="completed" and run.get("conclusion")=="cancelled"): raise ActionsRunCancelMediationError("independent cancellation observation missing")
            obs=_digest(b"LION/ACTIONS-RUN-CANCEL-OBS/1\0",{"run_id":request.run_id,"status":run.get("status"),"conclusion":run.get("conclusion")}); observed=datetime.now(timezone.utc).isoformat(); self.fence.transition(key,"ATTEMPTED","OBSERVED",observed_at=observed,observation_digest=obs)
            rec=_digest(b"LION/ACTIONS-RUN-CANCEL-REC/1\0",{"effect_key":key,"observation_digest":obs}); reconciled=datetime.now(timezone.utc).isoformat(); self.fence.transition(key,"OBSERVED","RECONCILED",reconciled_at=reconciled,reconciliation_digest=rec)
            return {"effect_key":key,"state":"RECONCILED","run_id":request.run_id,"observation_digest":obs,"reconciliation_digest":rec}
        except Exception:
            try: self.fence.transition(key,"PREPARED","UNKNOWN")
            except Exception:
                try: self.fence.transition(key,"ATTEMPTED","UNKNOWN")
                except Exception: pass
            raise

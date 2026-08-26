"""Durable complete mediation for exact GitHub issue-comment writes."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
from hashlib import sha256
import json,sqlite3
from pathlib import Path
from typing import Protocol
from cyber_lion.contracts.issue_comment_write import *

class IssueCommentWriteMediationError(RuntimeError): pass
_STATES={"PREPARED","ATTEMPTED","OBSERVED","RECONCILED","UNKNOWN"}
def _canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _h(domain,v): return sha256(domain+_canon(v)).hexdigest()
def _now(): return datetime.now(timezone.utc).isoformat()

def issue_comment_effect_key(r,a):
 a.binds(r); return _h(b"LION/ISSUE-COMMENT-EFFECT/1\0",{"request":r.request_digest,"admission":a.admission_digest,"action":r.action,"replay":r.replay_key})

class IssueCommentWriteAdmissionResolver(Protocol):
 def resolve(self,request:IssueCommentWriteRequest)->CanonicalIssueCommentWriteAdmission: ...
class IssueCommentRepositoryReader(Protocol):
 def ref_head(self,ref:str)->str: ...
 def get_comment(self,comment_id:int)->dict: ...
class IssueCommentWriteEffect(Protocol):
 def write_exact(self,request:IssueCommentWriteRequest,admission:CanonicalIssueCommentWriteAdmission)->int: ...

@dataclass(frozen=True)
class IssueCommentFenceRecord:
 effect_key:str; request_digest:str; admission_digest:str; repository:str; issue_number:int; action:str; semantic_capability:str; body_digest:str; target_comment_id:int; authority_lineage_digest:str; expected_repository_head:str; state:str; prepared_at:str; attempted_at:str|None=None; observed_at:str|None=None; reconciled_at:str|None=None; observation_digest:str|None=None; reconciliation_digest:str|None=None
 def validate(self):
  if self.state not in _STATES: raise IssueCommentWriteMediationError("state invalid")
  if self.state in {"ATTEMPTED","OBSERVED","RECONCILED"} and not self.attempted_at: raise IssueCommentWriteMediationError("attempt timestamp missing")
  if self.state in {"OBSERVED","RECONCILED"} and (not self.observed_at or not self.observation_digest): raise IssueCommentWriteMediationError("observation missing")
  if self.state=="RECONCILED" and (not self.reconciled_at or not self.reconciliation_digest): raise IssueCommentWriteMediationError("reconciliation missing")
  return self

class DurableIssueCommentWriteFence:
 def __init__(self,database_path:str):
  if not database_path: raise IssueCommentWriteMediationError("fence path missing")
  self.path=Path(database_path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()
 def _c(self):
  c=sqlite3.connect(self.path,timeout=30,isolation_level=None); c.execute("PRAGMA busy_timeout=30000"); return c
 def _init(self):
  with self._c() as c:
   c.execute("CREATE TABLE IF NOT EXISTS issue_comment_write_effect(effect_key TEXT PRIMARY KEY,request_digest TEXT NOT NULL,admission_digest TEXT NOT NULL,repository TEXT NOT NULL,issue_number INTEGER NOT NULL,action TEXT NOT NULL,semantic_capability TEXT NOT NULL,body_digest TEXT NOT NULL,target_comment_id INTEGER NOT NULL,authority_lineage_digest TEXT NOT NULL,expected_repository_head TEXT NOT NULL,state TEXT NOT NULL,prepared_at TEXT NOT NULL,attempted_at TEXT,observed_at TEXT,reconciled_at TEXT,observation_digest TEXT,reconciliation_digest TEXT)")
   c.execute("CREATE UNIQUE INDEX IF NOT EXISTS issue_comment_write_exact_binding ON issue_comment_write_effect(request_digest,admission_digest)")
 def _row(self,row): return IssueCommentFenceRecord(*row).validate()
 def get(self,k):
  with self._c() as c: row=c.execute("SELECT effect_key,request_digest,admission_digest,repository,issue_number,action,semantic_capability,body_digest,target_comment_id,authority_lineage_digest,expected_repository_head,state,prepared_at,attempted_at,observed_at,reconciled_at,observation_digest,reconciliation_digest FROM issue_comment_write_effect WHERE effect_key=?",(k,)).fetchone()
  if row is None: raise IssueCommentWriteMediationError("effect unknown")
  return self._row(row)
 def prepare(self,r):
  r.validate()
  try:
   with self._c() as c: c.execute("INSERT INTO issue_comment_write_effect VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",tuple(r.__dict__.values()))
  except sqlite3.IntegrityError as e: raise IssueCommentWriteMediationError("replay or collision denied") from e
  return self.get(r.effect_key)
 def mark_attempted(self,k,at):
  with self._c() as c:
   cur=c.execute("UPDATE issue_comment_write_effect SET state='ATTEMPTED',attempted_at=? WHERE effect_key=? AND state='PREPARED' AND attempted_at IS NULL",(at,k))
   if cur.rowcount!=1: raise IssueCommentWriteMediationError("invalid fence transition")
  return self.get(k)
 def mark_observed(self,k,d,at):
  with self._c() as c:
   cur=c.execute("UPDATE issue_comment_write_effect SET state='OBSERVED',observation_digest=?,observed_at=? WHERE effect_key=? AND state='ATTEMPTED'",(d,at,k))
   if cur.rowcount!=1: raise IssueCommentWriteMediationError("invalid fence transition")
  return self.get(k)
 def mark_reconciled(self,k,d,at):
  with self._c() as c:
   cur=c.execute("UPDATE issue_comment_write_effect SET state='RECONCILED',reconciliation_digest=?,reconciled_at=? WHERE effect_key=? AND state='OBSERVED'",(d,at,k))
   if cur.rowcount!=1: raise IssueCommentWriteMediationError("invalid fence transition")
  return self.get(k)
 def mark_unknown(self,k):
  with self._c() as c:
   cur=c.execute("UPDATE issue_comment_write_effect SET state='UNKNOWN' WHERE effect_key=? AND state IN ('PREPARED','ATTEMPTED','OBSERVED')",(k,))
   if cur.rowcount!=1: raise IssueCommentWriteMediationError("invalid fence transition")
  return self.get(k)

class CanonicalIssueCommentWriteMediator:
 def __init__(self,*,admissions,repository,effect,fence):
  if not callable(getattr(admissions,"resolve",None)) or not callable(getattr(repository,"ref_head",None)) or not callable(getattr(repository,"get_comment",None)) or not callable(getattr(effect,"write_exact",None)) or type(fence) is not DurableIssueCommentWriteFence: raise IssueCommentWriteMediationError("canonical components unavailable")
  self.admissions=admissions;self.repository=repository;self.effect=effect;self.fence=fence
 def execute(self,request:IssueCommentWriteRequest):
  request.validate()
  if not request.request_digest: raise IssueCommentWriteMediationError("sealed request required")
  admission=self.admissions.resolve(request); admission.binds(request)
  if self.repository.ref_head("master")!=request.expected_repository_head: raise IssueCommentWriteMediationError("repository head drift")
  if request.action=="UPDATE_OWN_CREATED_COMMENT":
   old=self.repository.get_comment(request.expected_existing_comment_id)
   if not isinstance(old,dict) or old.get("id")!=request.expected_existing_comment_id or body_digest(old.get("body",""))!=request.expected_existing_body_digest: raise IssueCommentWriteMediationError("update target currentness failed")
  k=issue_comment_effect_key(request,admission)
  self.fence.prepare(IssueCommentFenceRecord(k,request.request_digest,admission.admission_digest,request.repository,request.issue_number,request.action,request.semantic_capability,body_digest(request.body),request.expected_existing_comment_id,admission.authority_lineage_digest,request.expected_repository_head,"PREPARED",_now()))
  try:
   current=self.admissions.resolve(request); current.binds(request)
   if current.admission_digest!=admission.admission_digest or current.authority_lineage_digest!=admission.authority_lineage_digest or current.authority_epoch!=admission.authority_epoch or current.authority_state_version!=admission.authority_state_version: raise IssueCommentWriteMediationError("authority drift")
   if self.repository.ref_head("master")!=request.expected_repository_head: raise IssueCommentWriteMediationError("head drift after PREPARED")
   if request.action=="UPDATE_OWN_CREATED_COMMENT":
    old=self.repository.get_comment(request.expected_existing_comment_id)
    if body_digest(old.get("body",""))!=request.expected_existing_body_digest: raise IssueCommentWriteMediationError("comment drift after PREPARED")
   self.fence.mark_attempted(k,_now())
   cid=self.effect.write_exact(request,admission)
   if request.action=="UPDATE_OWN_CREATED_COMMENT" and cid!=request.expected_existing_comment_id: raise IssueCommentWriteMediationError("update identity changed")
   got=self.repository.get_comment(cid)
   if not isinstance(got,dict) or got.get("id")!=cid or body_digest(got.get("body",""))!=body_digest(request.body): raise IssueCommentWriteMediationError("independent observation mismatch")
   od=_h(b"LION/ISSUE-COMMENT-OBSERVATION/1\0",{"effect_key":k,"comment_id":cid,"body_digest":body_digest(request.body)})
   self.fence.mark_observed(k,od,_now())
   rd=_h(b"LION/ISSUE-COMMENT-RECONCILIATION/1\0",{"effect_key":k,"observation_digest":od,"admission_digest":admission.admission_digest,"authority":admission.authority_lineage_digest,"state":"RECONCILED"})
   final=self.fence.mark_reconciled(k,rd,_now())
   return {"comment_id":cid,"effect_key":k,"fence_state":final.state,"observation_digest":od,"reconciliation_digest":rd}
  except Exception:
   try:self.fence.mark_unknown(k)
   except Exception:pass
   raise
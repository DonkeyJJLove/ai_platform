"""Exact contract for one governed GitHub issue-comment write effect."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
import json,re

REPOSITORY="DonkeyJJLove/ai_platform"
CONTROL_ISSUE=144
TEST_CANARY_ISSUE=226
ACTIONS=("CREATE_COMMENT","UPDATE_OWN_CREATED_COMMENT")
CAPABILITIES=(
 "actions.control-ledger.create","actions.control-ledger.update",
 "actions.failure-receipt.create","repository-maintenance.receipt.create",
 "test.issue-comment-canary.create",
)
_CAPABILITY_SCOPE={
 "actions.control-ledger.create":(CONTROL_ISSUE,"CREATE_COMMENT",False),
 "actions.control-ledger.update":(CONTROL_ISSUE,"UPDATE_OWN_CREATED_COMMENT",False),
 "actions.failure-receipt.create":(CONTROL_ISSUE,"CREATE_COMMENT",False),
 "repository-maintenance.receipt.create":(CONTROL_ISSUE,"CREATE_COMMENT",False),
 "test.issue-comment-canary.create":(TEST_CANARY_ISSUE,"CREATE_COMMENT",True),
}
_HEX40=re.compile(r"^[0-9a-f]{40}$"); _HEX64=re.compile(r"^[0-9a-f]{64}$")
_ID=re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
_DOMAIN=b"LION/ISSUE-COMMENT-WRITE/1\0"

class IssueCommentWriteContractError(ValueError): pass

def _canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _digest(v): return sha256(_DOMAIN+_canon(v)).hexdigest()

def body_digest(body:str)->str:
 if not isinstance(body,str) or not body or len(body.encode())>65536 or "\x00" in body: raise IssueCommentWriteContractError("body invalid")
 return sha256(body.encode()).hexdigest()

@dataclass(frozen=True)
class IssueCommentWriteRequest:
 repository:str; issue_number:int; action:str; semantic_capability:str; body:str
 request_id:str; replay_key:str; expected_repository_head:str
 expected_existing_comment_id:int=0; expected_existing_body_digest:str=""; authority_context:str=""
 request_digest:str=""
 test_only:bool=False
 def payload(self):
  v=asdict(self); v.pop("request_digest",None); v["body_digest"]=body_digest(v.pop("body")); return v
 def compute_digest(self): return _digest(self.payload())
 def validate(self):
  if self.repository!=REPOSITORY: raise IssueCommentWriteContractError("repository outside closed world")
  if self.action not in ACTIONS or self.semantic_capability not in CAPABILITIES: raise IssueCommentWriteContractError("action/capability invalid")
  scope=_CAPABILITY_SCOPE[self.semantic_capability]
  if (self.issue_number,self.action,self.test_only)!=scope: raise IssueCommentWriteContractError("capability scope mismatch")
  body_digest(self.body)
  if not _ID.fullmatch(self.request_id): raise IssueCommentWriteContractError("request_id invalid")
  if not _HEX64.fullmatch(self.replay_key): raise IssueCommentWriteContractError("replay_key invalid")
  if not _HEX40.fullmatch(self.expected_repository_head): raise IssueCommentWriteContractError("head invalid")
  if not isinstance(self.authority_context,str) or not self.authority_context or len(self.authority_context)>512: raise IssueCommentWriteContractError("authority_context invalid")
  if self.action=="CREATE_COMMENT":
   if self.expected_existing_comment_id!=0 or self.expected_existing_body_digest: raise IssueCommentWriteContractError("create cannot bind existing comment")
  else:
   if not isinstance(self.expected_existing_comment_id,int) or isinstance(self.expected_existing_comment_id,bool) or self.expected_existing_comment_id<=0: raise IssueCommentWriteContractError("update target invalid")
   if not _HEX64.fullmatch(self.expected_existing_body_digest): raise IssueCommentWriteContractError("existing body digest invalid")
  if self.request_digest and self.request_digest!=self.compute_digest(): raise IssueCommentWriteContractError("request digest mismatch")
  return self
 def sealed(self):
  self.validate(); return IssueCommentWriteRequest(**{**asdict(self),"request_digest":self.compute_digest()}).validate()

@dataclass(frozen=True)
class CanonicalIssueCommentWriteAdmission:
 request_digest:str; repository:str; issue_number:int; action:str; semantic_capability:str; body_digest:str
 expected_repository_head:str; authority_lineage_digest:str; pdp_decision_digest:str
 authority_epoch:int; authority_state_version:int; provider_id:str; admission_digest:str=""; test_only:bool=False
 def payload(self): v=asdict(self);v.pop("admission_digest",None);return v
 def compute_digest(self): return _digest(self.payload())
 def validate(self):
  for x in (self.request_digest,self.body_digest,self.authority_lineage_digest,self.pdp_decision_digest):
   if not _HEX64.fullmatch(x): raise IssueCommentWriteContractError("digest invalid")
  if self.repository!=REPOSITORY or self.action not in ACTIONS or self.semantic_capability not in CAPABILITIES: raise IssueCommentWriteContractError("admission scope invalid")
  scope=_CAPABILITY_SCOPE[self.semantic_capability]
  if (self.issue_number,self.action,self.test_only)!=scope: raise IssueCommentWriteContractError("admission capability scope mismatch")
  if not _HEX40.fullmatch(self.expected_repository_head): raise IssueCommentWriteContractError("admission head invalid")
  if not isinstance(self.authority_epoch,int) or isinstance(self.authority_epoch,bool) or self.authority_epoch<0: raise IssueCommentWriteContractError("epoch invalid")
  if not isinstance(self.authority_state_version,int) or isinstance(self.authority_state_version,bool) or self.authority_state_version<0: raise IssueCommentWriteContractError("state version invalid")
  if not _ID.fullmatch(self.provider_id): raise IssueCommentWriteContractError("provider invalid")
  if self.admission_digest and self.admission_digest!=self.compute_digest(): raise IssueCommentWriteContractError("admission digest mismatch")
  return self
 def sealed(self):
  self.validate(); return CanonicalIssueCommentWriteAdmission(**{**asdict(self),"admission_digest":self.compute_digest()}).validate()
 def binds(self,r:IssueCommentWriteRequest):
  r.validate();self.validate()
  if (self.request_digest,self.repository,self.issue_number,self.action,self.semantic_capability,self.body_digest,self.expected_repository_head,self.test_only)!=(r.request_digest,r.repository,r.issue_number,r.action,r.semantic_capability,body_digest(r.body),r.expected_repository_head,r.test_only): raise IssueCommentWriteContractError("admission/request substitution")

@dataclass(frozen=True)
class IssueCommentObservation:
 comment_id:int; body_digest:str; observed:bool
 def validate(self):
  if not isinstance(self.comment_id,int) or isinstance(self.comment_id,bool) or self.comment_id<=0 or not _HEX64.fullmatch(self.body_digest) or type(self.observed) is not bool: raise IssueCommentWriteContractError("observation invalid")
  return self

@dataclass(frozen=True)
class IssueCommentReconciliation:
 effect_key:str; observation_digest:str; reconciliation_digest:str; state:str="RECONCILED"
 def validate(self):
  if not all(_HEX64.fullmatch(x) for x in (self.effect_key,self.observation_digest,self.reconciliation_digest)) or self.state!="RECONCILED": raise IssueCommentWriteContractError("reconciliation invalid")
  return self

"""Capability-reduced GitHub effect provider for exact issue-comment writes."""
import json,urllib.error,urllib.request
from cyber_lion.contracts.issue_comment_write import IssueCommentWriteRequest,CanonicalIssueCommentWriteAdmission
from cyber_lion.enterprise.issue_comment_write_mediation import DurableIssueCommentWriteFence,IssueCommentWriteMediationError,issue_comment_effect_key
class ExactIssueCommentWriteEffectProvider:
 API_ORIGIN="https://api.github.com"
 class _NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,req,fp,code,msg,headers,newurl): return None
 def __init__(self,*,repository:str,token:str,fence:DurableIssueCommentWriteFence):
  if repository!="DonkeyJJLove/ai_platform" or not token or type(fence) is not DurableIssueCommentWriteFence: raise IssueCommentWriteMediationError("effect provider configuration invalid")
  self.repository=repository;self.token=token;self.fence=fence
 def write_exact(self,request:IssueCommentWriteRequest,admission:CanonicalIssueCommentWriteAdmission)->int:
  admission.binds(request); k=issue_comment_effect_key(request,admission); rec=self.fence.get(k)
  if rec.state!="ATTEMPTED" or rec.request_digest!=request.request_digest or rec.admission_digest!=admission.admission_digest: raise IssueCommentWriteMediationError("effect requires exact ATTEMPTED fence")
  payload=json.dumps({"body":request.body},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
  headers={"Authorization":f"Bearer {self.token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json","User-Agent":"lion-issue-comment-write/1"}
  if request.action=="CREATE_COMMENT":
   req=urllib.request.Request(self.API_ORIGIN+f"/repos/{self.repository}/issues/{request.issue_number}/comments",data=payload,method="POST",headers=headers);expected=201
  elif request.action=="UPDATE_OWN_CREATED_COMMENT":
   req=urllib.request.Request(self.API_ORIGIN+f"/repos/{self.repository}/issues/comments/{request.expected_existing_comment_id}",data=payload,method="PATCH",headers=headers);expected=200
  else: raise IssueCommentWriteMediationError("unsupported effect action")
  try:
   with urllib.request.build_opener(self._NoRedirect()).open(req,timeout=20) as response:
    raw=response.read(1024*1024+1)
    if response.status!=expected: raise IssueCommentWriteMediationError("GitHub write rejected")
  except urllib.error.URLError as e: raise IssueCommentWriteMediationError("GitHub write failed") from e
  if len(raw)>1024*1024: raise IssueCommentWriteMediationError("GitHub response oversized")
  try:value=json.loads(raw)
  except Exception as e: raise IssueCommentWriteMediationError("GitHub response malformed") from e
  cid=value.get("id") if isinstance(value,dict) else None
  if not isinstance(cid,int) or isinstance(cid,bool) or cid<=0: raise IssueCommentWriteMediationError("comment identity missing")
  return cid

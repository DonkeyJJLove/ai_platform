"""Pinned external trust composition for issue-comment complete mediation."""
from __future__ import annotations
from hashlib import sha256
import importlib.util,json,os,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from cyber_lion.enterprise.issue_comment_write_mediation import CanonicalIssueCommentWriteMediator,DurableIssueCommentWriteFence,IssueCommentWriteMediationError
from cyber_lion.enterprise.issue_comment_write_github_effect import ExactIssueCommentWriteEffectProvider
_FACTORY="build_issue_comment_write_admission_resolver"
class _NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl): return None
class GitHubIssueCommentRepositoryReader:
 def __init__(self,repository:str,token:str):
  if repository!="DonkeyJJLove/ai_platform" or not token: raise IssueCommentWriteMediationError("reader configuration invalid")
  self.repository=repository;self.token=token
 def _get(self,path):
  if not path.startswith(f"/repos/{self.repository}/") or ".." in path or "\\" in path: raise IssueCommentWriteMediationError("reader path outside repository")
  req=urllib.request.Request("https://api.github.com"+path,method="GET",headers={"Authorization":f"Bearer {self.token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"lion-issue-comment-reader/1"})
  try:
   with urllib.request.build_opener(_NoRedirect()).open(req,timeout=20) as r:
    raw=r.read(1024*1024+1)
    if r.status!=200: raise IssueCommentWriteMediationError("reader GET rejected")
  except urllib.error.URLError as e: raise IssueCommentWriteMediationError("reader GET failed") from e
  if len(raw)>1024*1024: raise IssueCommentWriteMediationError("reader response oversized")
  try:return json.loads(raw)
  except Exception as e: raise IssueCommentWriteMediationError("reader response malformed") from e
 def ref_head(self,ref:str)->str:
  if ref!="master": raise IssueCommentWriteMediationError("only master currentness supported")
  v=self._get(f"/repos/{self.repository}/git/ref/heads/master")
  try:sha=v["object"]["sha"]
  except Exception as e: raise IssueCommentWriteMediationError("master observation malformed") from e
  return sha
 def get_comment(self,comment_id:int)->dict:
  if not isinstance(comment_id,int) or isinstance(comment_id,bool) or comment_id<=0: raise IssueCommentWriteMediationError("comment id invalid")
  v=self._get(f"/repos/{self.repository}/issues/comments/{comment_id}")
  if not isinstance(v,dict): raise IssueCommentWriteMediationError("comment observation malformed")
  return v

def _external_resolver():
 path_raw=os.environ.get("LION_ISSUE_COMMENT_RUNTIME_MODULE_PATH","");digest=os.environ.get("LION_ISSUE_COMMENT_RUNTIME_MODULE_DIGEST","")
 if not path_raw or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest): raise IssueCommentWriteMediationError("trusted issue-comment runtime unavailable")
 path=Path(path_raw)
 if not path.is_absolute(): raise IssueCommentWriteMediationError("trusted issue-comment runtime path must be absolute")
 try:resolved=path.resolve(strict=True)
 except OSError as e: raise IssueCommentWriteMediationError("trusted issue-comment runtime unavailable") from e
 ws=os.environ.get("GITHUB_WORKSPACE")
 if ws:
  w=Path(ws).resolve()
  if resolved==w or w in resolved.parents: raise IssueCommentWriteMediationError("trusted issue-comment runtime must remain outside repository")
 if resolved.suffix!=".py" or sha256(resolved.read_bytes()).hexdigest()!=digest: raise IssueCommentWriteMediationError("trusted issue-comment runtime digest mismatch")
 spec=importlib.util.spec_from_file_location("_lion_issue_comment_runtime_"+digest[:20],resolved)
 if spec is None or spec.loader is None: raise IssueCommentWriteMediationError("trusted issue-comment runtime cannot load")
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);factory=getattr(mod,_FACTORY,None)
 if not callable(factory): raise IssueCommentWriteMediationError("trusted issue-comment resolver factory unavailable")
 resolver=factory()
 if not callable(getattr(resolver,"resolve",None)): raise IssueCommentWriteMediationError("trusted issue-comment resolver unavailable")
 return resolver

def _fence_path():
 raw=os.environ.get("LION_ISSUE_COMMENT_FENCE_DATABASE_PATH","");p=Path(raw)
 if not raw or not p.is_absolute(): raise IssueCommentWriteMediationError("trusted issue-comment fence unavailable")
 ws=os.environ.get("GITHUB_WORKSPACE")
 if ws:
  w=Path(ws).resolve();r=p.resolve()
  if r==w or w in r.parents: raise IssueCommentWriteMediationError("issue-comment fence must remain outside repository")
 return str(p)

def build_issue_comment_write_mediator_from_environment(*,repository:str,token:str):
 fence=DurableIssueCommentWriteFence(_fence_path());reader=GitHubIssueCommentRepositoryReader(repository,token)
 return CanonicalIssueCommentWriteMediator(admissions=_external_resolver(),repository=reader,effect=ExactIssueCommentWriteEffectProvider(repository=repository,token=token,fence=fence),fence=fence)
class EnvironmentIssueCommentMediator:
 def __init__(self,repository:str,token:str): self.repository=repository;self.token=token
 def execute(self,request): return build_issue_comment_write_mediator_from_environment(repository=self.repository,token=self.token).execute(request)

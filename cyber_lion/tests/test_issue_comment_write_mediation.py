from __future__ import annotations
import json,tempfile,unittest
from unittest.mock import patch
from cyber_lion.contracts.issue_comment_write import IssueCommentWriteRequest,CanonicalIssueCommentWriteAdmission,IssueCommentWriteContractError,body_digest
from cyber_lion.enterprise.issue_comment_write_mediation import CanonicalIssueCommentWriteMediator,DurableIssueCommentWriteFence,IssueCommentWriteMediationError,issue_comment_effect_key
from cyber_lion.enterprise.issue_comment_write_github_effect import ExactIssueCommentWriteEffectProvider
REPO="DonkeyJJLove/ai_platform";HEAD="a"*40;D="b"*64

def req(**kw):
 v=dict(repository=REPO,issue_number=144,action="CREATE_COMMENT",semantic_capability="actions.control-ledger.create",body="LION-DISPATCH-CLAIM v1\nrequest_id=x",request_id="req:1",replay_key="1"*64,expected_repository_head=HEAD,authority_context="test")
 v.update(kw);return IssueCommentWriteRequest(**v).sealed()
def adm(r): return CanonicalIssueCommentWriteAdmission(r.request_digest,r.repository,r.issue_number,r.action,r.semantic_capability,body_digest(r.body),r.expected_repository_head,"2"*64,"3"*64,1,7,"test-provider",test_only=r.test_only).sealed()
class Resolver:
 def __init__(self): self.calls=0
 def resolve(self,r): self.calls+=1;return adm(r)
class Repo:
 def __init__(self): self.head=HEAD;self.comments={};self.old=None
 def ref_head(self,ref): return self.head
 def get_comment(self,cid): return self.comments.get(cid,{"id":cid,"body":self.old})
class Effect:
 def __init__(self,repo): self.repo=repo;self.calls=0
 def write_exact(self,r,a): self.calls+=1;cid=r.expected_existing_comment_id or 777;self.repo.comments[cid]={"id":cid,"body":r.body};return cid
class Response:
 def __init__(self,status,val): self.status=status;self.raw=json.dumps(val).encode()
 def read(self,n=-1): return self.raw
 def __enter__(self): return self
 def __exit__(self,*a): return False
class Opener:
 def __init__(self,response):self.response=response;self.calls=[]
 def open(self,request,timeout=None):self.calls.append(request);return self.response
class IssueCommentWriteMediationTests(unittest.TestCase):
 def test_contract_denies_wrong_scope_and_action_capability_mismatch(self):
  with self.assertRaises(IssueCommentWriteContractError): req(repository="other/repo")
  with self.assertRaises(IssueCommentWriteContractError): req(issue_number=145)
  with self.assertRaises(IssueCommentWriteContractError): req(action="UPDATE_OWN_CREATED_COMMENT",semantic_capability="actions.control-ledger.create",expected_existing_comment_id=1,expected_existing_body_digest="4"*64)
 def test_test_canary_scope_is_exact_and_structurally_test_only(self):
  r=req(issue_number=226,semantic_capability="test.issue-comment-canary.create",test_only=True,request_id="req:canary")
  self.assertEqual(r.issue_number,226);self.assertTrue(r.test_only);adm(r).binds(r)
  for bad in (
   dict(issue_number=144,semantic_capability="test.issue-comment-canary.create",test_only=True),
   dict(issue_number=198,semantic_capability="test.issue-comment-canary.create",test_only=True),
   dict(issue_number=227,semantic_capability="test.issue-comment-canary.create",test_only=True),
   dict(issue_number=226,semantic_capability="test.issue-comment-canary.create",test_only=False),
   dict(issue_number=226,semantic_capability="actions.control-ledger.create",test_only=True),
   dict(issue_number=226,semantic_capability="actions.control-ledger.create",test_only=False),
   dict(repository="other/repo",issue_number=226,semantic_capability="test.issue-comment-canary.create",test_only=True),
   dict(issue_number=226,action="UPDATE_OWN_CREATED_COMMENT",semantic_capability="test.issue-comment-canary.create",test_only=True,expected_existing_comment_id=1,expected_existing_body_digest="4"*64),
  ):
   with self.subTest(bad=bad):
    with self.assertRaises(IssueCommentWriteContractError): req(**bad)
 def test_admission_cannot_relabel_test_scope(self):
  r=req(issue_number=226,semantic_capability="test.issue-comment-canary.create",test_only=True,request_id="req:canary2")
  a=CanonicalIssueCommentWriteAdmission(r.request_digest,r.repository,r.issue_number,r.action,r.semantic_capability,body_digest(r.body),r.expected_repository_head,"2"*64,"3"*64,1,7,"test-provider",test_only=False)
  with self.assertRaises(IssueCommentWriteContractError): a.sealed()
 def test_production_scope_remains_issue_144_only(self):
  for capability,action in (("actions.control-ledger.create","CREATE_COMMENT"),("actions.control-ledger.update","UPDATE_OWN_CREATED_COMMENT"),("actions.failure-receipt.create","CREATE_COMMENT"),("repository-maintenance.receipt.create","CREATE_COMMENT")):
   kw=dict(semantic_capability=capability,action=action,request_id="req:"+capability)
   if action=="UPDATE_OWN_CREATED_COMMENT": kw.update(expected_existing_comment_id=7,expected_existing_body_digest="4"*64)
   self.assertEqual(req(**kw).issue_number,144)
   with self.assertRaises(IssueCommentWriteContractError): req(issue_number=226,test_only=True,**kw)
 def test_complete_create_reconciles_exactly_once(self):
  with tempfile.TemporaryDirectory() as td:
   r=req();repo=Repo();resolver=Resolver();effect=Effect(repo);f=DurableIssueCommentWriteFence(td+"/f.sqlite");m=CanonicalIssueCommentWriteMediator(admissions=resolver,repository=repo,effect=effect,fence=f)
   out=m.execute(r);self.assertEqual(out["fence_state"],"RECONCILED");self.assertEqual(effect.calls,1);self.assertEqual(resolver.calls,2);self.assertEqual(f.get(out["effect_key"]).state,"RECONCILED")
   with self.assertRaises(IssueCommentWriteMediationError): m.execute(r)
   self.assertEqual(effect.calls,1)
 def test_currentness_drift_denied_before_attempt(self):
  with tempfile.TemporaryDirectory() as td:
   r=req();repo=Repo();repo.head="c"*40;f=DurableIssueCommentWriteFence(td+"/f.sqlite");effect=Effect(repo)
   with self.assertRaisesRegex(IssueCommentWriteMediationError,"head drift"): CanonicalIssueCommentWriteMediator(admissions=Resolver(),repository=repo,effect=effect,fence=f).execute(r)
   self.assertEqual(effect.calls,0)
 def test_update_binds_exact_previous_comment_body(self):
  with tempfile.TemporaryDirectory() as td:
   old="old";r=req(action="UPDATE_OWN_CREATED_COMMENT",semantic_capability="actions.control-ledger.update",expected_existing_comment_id=5,expected_existing_body_digest=body_digest(old),body="new",request_id="req:u")
   repo=Repo();repo.old=old;repo.comments[5]={"id":5,"body":old};f=DurableIssueCommentWriteFence(td+"/f.sqlite");effect=Effect(repo);out=CanonicalIssueCommentWriteMediator(admissions=Resolver(),repository=repo,effect=effect,fence=f).execute(r);self.assertEqual(out["comment_id"],5)
 def test_provider_before_attempted_is_denied(self):
  with tempfile.TemporaryDirectory() as td:
   r=req();a=adm(r);f=DurableIssueCommentWriteFence(td+"/f.sqlite");k=issue_comment_effect_key(r,a)
   from cyber_lion.enterprise.issue_comment_write_mediation import IssueCommentFenceRecord
   f.prepare(IssueCommentFenceRecord(k,r.request_digest,a.admission_digest,REPO,144,r.action,r.semantic_capability,body_digest(r.body),0,a.authority_lineage_digest,HEAD,"PREPARED","now"))
   p=ExactIssueCommentWriteEffectProvider(repository=REPO,token="t",fence=f)
   with self.assertRaisesRegex(IssueCommentWriteMediationError,"ATTEMPTED"): p.write_exact(r,a)
 def test_exact_provider_uses_only_canonical_post_route(self):
  with tempfile.TemporaryDirectory() as td:
   r=req();a=adm(r);f=DurableIssueCommentWriteFence(td+"/f.sqlite");k=issue_comment_effect_key(r,a)
   from cyber_lion.enterprise.issue_comment_write_mediation import IssueCommentFenceRecord
   f.prepare(IssueCommentFenceRecord(k,r.request_digest,a.admission_digest,REPO,144,r.action,r.semantic_capability,body_digest(r.body),0,a.authority_lineage_digest,HEAD,"PREPARED","now"));f.mark_attempted(k,"later")
   op=Opener(Response(201,{"id":777,"body":r.body}))
   with patch("urllib.request.build_opener",return_value=op): cid=ExactIssueCommentWriteEffectProvider(repository=REPO,token="t",fence=f).write_exact(r,a)
   self.assertEqual(cid,777);self.assertEqual(op.calls[0].get_method(),"POST");self.assertEqual(op.calls[0].full_url,f"https://api.github.com/repos/{REPO}/issues/144/comments")
if __name__=="__main__":unittest.main()

from __future__ import annotations
import inspect,tempfile,unittest
from pathlib import Path
from cyber_lion.enterprise.actions_failure_receipt import FailureReceiptAdmission,FailureReceiptError,GitHubFailureReceiptBoundary,_bounded_diagnostic
REPO="DonkeyJJLove/ai_platform";SHA="e"*40
def event(**kw):
 v={"action":"created","issue":{"number":144},"comment":{"id":9001,"body":"LION-DISPATCH v1\nworkflow=x","user":{"login":"DonkeyJJLove"}},"repository":{"full_name":REPO}}
 if "issue" in kw:v["issue"]["number"]=kw["issue"]
 if "body" in kw:v["comment"]["body"]=kw["body"]
 if "repo" in kw:v["repository"]["full_name"]=kw["repo"]
 return v
def admission(**over):
 v=dict(event=event(),repository=REPO,workflow_run_id=123,workflow_run_attempt=1,checked_out_sha=SHA,exit_code=2,diagnostic="failed closed");v.update(over);return FailureReceiptAdmission.from_event(**v)
class _Mediator:
 def __init__(self):self.requests=[]
 def execute(self,r):self.requests.append(r);return {"comment_id":777,"fence_state":"RECONCILED"}
class FailureReceiptBoundaryTests(unittest.TestCase):
 def test_admission_binds_external_event_run_and_sha(self):
  v=admission();self.assertEqual(v.issue_number,144);self.assertEqual(v.checked_out_sha,SHA);self.assertIn("receipt_is_evidence_not_authority=true",v.receipt_body)
 def test_observe_command_is_exact(self): self.assertEqual(admission(event=event(body="LION-OBSERVE v1\nrequest_id=x")).command,"OBSERVE")
 def test_wrong_issue_repository_or_nonfailure_denied(self):
  for kw in ({"event":event(issue=145)},{"event":event(repo="Other/repo")},{"exit_code":0},{"checked_out_sha":"bad"}):
   with self.assertRaises(FailureReceiptError): admission(**kw)
 def test_boundary_routes_only_through_mediator(self):
  m=_Mediator();o=GitHubFailureReceiptBoundary(mediator=m).post(admission(),token="ignored");self.assertTrue(o.observed);self.assertEqual(o.comment_id,777);self.assertEqual(m.requests[0].semantic_capability,"actions.failure-receipt.create")
 def test_admission_replay_denied_before_second_mediator_call(self):
  m=_Mediator();b=GitHubFailureReceiptBoundary(mediator=m);g=admission();b.post(g,token="x")
  with self.assertRaises(FailureReceiptError): b.post(g,token="x")
  self.assertEqual(len(m.requests),1)
 def test_missing_mediator_fails_closed(self):
  with self.assertRaisesRegex(FailureReceiptError,"mediator unavailable"): GitHubFailureReceiptBoundary().post(admission(),token="x")
 def test_diagnostic_is_bounded_and_redacted(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)/"out";err=Path(td)/"err";out.write_text("unused");err.write_text("Bearer abc.def token=secret-value\n");v=_bounded_diagnostic(err,out);self.assertNotIn("abc.def",v);self.assertNotIn("secret-value",v)
 def test_source_has_no_raw_post(self):
  import cyber_lion.enterprise.actions_failure_receipt as mod
  self.assertNotIn('method="POST"',inspect.getsource(mod))
if __name__=="__main__":unittest.main()

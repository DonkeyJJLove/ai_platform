from __future__ import annotations
import inspect,json,unittest
from unittest.mock import patch
from cyber_lion.enterprise import actions_control_ledger as ledger
from cyber_lion.enterprise.actions_dispatch_bridge import GitHubApi
REPO="DonkeyJJLove/ai_platform"; HEAD="c"*40
CLAIM="\n".join(("LION-DISPATCH-CLAIM v1","request_id=req-r9d7","replay_key="+"a"*64,"payload_digest="+"b"*64,"comment_id=9001","actor=DonkeyJJLove","permission=admin","workflow=f009-live-runtime-proof.yml","ref=master","expected_head="+HEAD,"state=CLAIMED_BEFORE_EFFECT"))
class _Response:
 def __init__(self,status,value): self.status=status;self.headers={};self.raw=json.dumps(value).encode()
 def read(self,size=-1): return self.raw if size<0 else self.raw[:size]
 def __enter__(self): return self
 def __exit__(self,*a): return False
class _Opener:
 def __init__(self,responses): self.responses=list(responses);self.calls=[]
 def open(self,request,timeout=None): self.calls.append((request,timeout)); return self.responses.pop(0)
class _Mediator:
 def __init__(self): self.requests=[];self.next_id=777
 def execute(self,r):
  self.requests.append(r); cid=r.expected_existing_comment_id or self.next_id
  return {"comment_id":cid,"fence_state":"RECONCILED"}
class ActionsControlLedgerTests(unittest.TestCase):
 def boundary(self,opener,med=None):
  return ledger.ActionsControlLedgerBoundary(REPO,"token",mediator=med or _Mediator(),expected_repository_head=HEAD,authority_context="test:ledger")
 def test_github_api_generic_transport_cannot_write_issue_comments(self):
  source=inspect.getsource(GitHubApi);self.assertIn('generic GitHub transport is read-only',source);api=GitHubApi(REPO,"token")
  with self.assertRaisesRegex(RuntimeError,"read-only"): api._request("POST",f"/repos/{REPO}/issues/144/comments",{"body":CLAIM})
 def test_create_is_exact_issue_bound_replay_checked_and_mediated(self):
  opener=_Opener([_Response(200,[])]);med=_Mediator()
  with patch("urllib.request.build_opener",return_value=opener): cid=self.boundary(opener,med).create(144,CLAIM)
  self.assertEqual(cid,777);self.assertEqual([x[0].get_method() for x in opener.calls],["GET"]);self.assertEqual(med.requests[0].semantic_capability,"actions.control-ledger.create")
 def test_durable_replay_denied_before_mediator(self):
  opener=_Opener([_Response(200,[{"id":1,"body":CLAIM}])]);med=_Mediator()
  with patch("urllib.request.build_opener",return_value=opener):
   with self.assertRaisesRegex(ledger.ActionsControlLedgerError,"replay"): self.boundary(opener,med).create(144,CLAIM)
  self.assertFalse(med.requests)
 def test_target_and_body_substitution_denied(self):
  med=_Mediator();b=self.boundary(_Opener([]),med)
  with self.assertRaises(ledger.ActionsControlLedgerError): b.create(145,CLAIM)
  with self.assertRaises(ledger.ActionsControlLedgerError): b.create(144,"attacker")
  self.assertFalse(med.requests)
 def test_update_requires_boundary_created_comment_and_exact_previous_digest(self):
  receipt=CLAIM.replace("LION-DISPATCH-CLAIM v1","LION-DISPATCH-RECEIPT v1");opener=_Opener([_Response(200,[]),_Response(200,{"id":777,"body":CLAIM})]);med=_Mediator()
  with patch("urllib.request.build_opener",return_value=opener):
   b=self.boundary(opener,med);b.create(144,CLAIM);b.update(777,receipt)
  self.assertEqual([r.semantic_capability for r in med.requests],["actions.control-ledger.create","actions.control-ledger.update"]);self.assertEqual(med.requests[1].expected_existing_comment_id,777)
  with self.assertRaisesRegex(ledger.ActionsControlLedgerError,"not created"): self.boundary(_Opener([]),_Mediator()).update(777,receipt)
 def test_no_raw_issue_comment_write_in_ledger(self):
  source=inspect.getsource(ledger);self.assertNotIn('method="POST"',source);self.assertNotIn('method="PATCH"',source);self.assertNotIn("/dispatches",source);self.assertNotIn("git/refs",source)
if __name__=="__main__":unittest.main()

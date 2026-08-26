from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.contracts.actions_dispatch_bridge import DispatchRequest
from cyber_lion.enterprise import actions_dispatch_bridge_legacy as legacy
from cyber_lion.enterprise.workflow_dispatch_github_effect import ExactWorkflowDispatchEffectProvider
from cyber_lion.enterprise.workflow_dispatch_mediation import (
    CanonicalWorkflowDispatchAdmission,
    DurableWorkflowDispatchFence,
    WorkflowDispatchFenceRecord,
    WorkflowDispatchMediationError,
    workflow_dispatch_effect_key,
)

REPO="DonkeyJJLove/ai_platform"
HEAD="a"*40


def request(**changes):
    values=dict(schema_version="1", repository=REPO, issue_number=144, comment_id=123,
        actor="DonkeyJJLove", request_id="r2-provider", workflow="f009-live-runtime-proof.yml",
        ref="master", expected_head=HEAD, canonical_inputs="{}")
    values.update(changes)
    return DispatchRequest(**values)


def admission(req):
    return CanonicalWorkflowDispatchAdmission(
        request_digest=req.payload_digest(), repository=req.repository, workflow=req.workflow,
        ref=req.ref, expected_head=req.expected_head,
        canonical_inputs_digest=sha256(req.canonical_inputs.encode()).hexdigest(),
        authority_lineage_digest="1"*64, pdp_decision_digest="2"*64,
        provider_id="external-test-live-authority+pdp", authority_epoch=7,
    ).sealed()


class Response:
    status=204
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self): return b""

class Opener:
    def __init__(self): self.calls=[]
    def open(self, req, timeout=None):
        self.calls.append((req,timeout))
        return Response()


class WorkflowDispatchGitHubEffectTests(unittest.TestCase):
    def build(self, *, attempted=True):
        td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        fence=DurableWorkflowDispatchFence(str(Path(td.name)/"dispatch.sqlite"))
        req=request(); adm=admission(req); key=workflow_dispatch_effect_key(req,adm)
        fence.prepare(WorkflowDispatchFenceRecord(
            effect_key=key, admission_digest=adm.admission_digest, request_digest=req.payload_digest(),
            repository=req.repository, workflow=req.workflow, ref=req.ref, expected_head=req.expected_head,
            state="PREPARED", prepared_at="2026-08-26T14:00:00+00:00",
        ))
        if attempted:
            fence.mark_attempted(key,"2026-08-26T14:00:01+00:00")
        return req,adm,fence,ExactWorkflowDispatchEffectProvider(repository=REPO,token="token",fence=fence)

    def test_exact_attempted_effect_uses_single_fixed_post(self):
        req,adm,_,provider=self.build(); opener=Opener()
        with patch("urllib.request.build_opener",return_value=opener):
            provider.execute_exact(req,adm)
        self.assertEqual(len(opener.calls),1)
        sent=opener.calls[0][0]
        self.assertEqual(sent.get_method(),"POST")
        self.assertEqual(sent.full_url, f"https://api.github.com/repos/{REPO}/actions/workflows/f009-live-runtime-proof.yml/dispatches")

    def test_effect_before_attempted_is_denied_without_network(self):
        req,adm,_,provider=self.build(attempted=False); opener=Opener()
        with patch("urllib.request.build_opener",return_value=opener):
            with self.assertRaisesRegex(WorkflowDispatchMediationError,"ATTEMPTED"):
                provider.execute_exact(req,adm)
        self.assertEqual(opener.calls,[])

    def test_request_substitution_is_denied_without_network(self):
        req,adm,_,provider=self.build(); opener=Opener()
        altered=replace(req, expected_head="b"*40)
        with patch("urllib.request.build_opener",return_value=opener):
            with self.assertRaises(WorkflowDispatchMediationError): provider.execute_exact(altered,adm)
        self.assertEqual(opener.calls,[])

    def test_legacy_direct_dispatch_is_fail_closed(self):
        api=legacy.GitHubApi(REPO,"token")
        with self.assertRaisesRegex(RuntimeError,"canonical mediator required"):
            api.dispatch("f009-live-runtime-proof.yml","master",{})

    def test_exactly_one_raw_dispatch_post_owner(self):
        enterprise=Path(__file__).resolve().parents[1]/"enterprise"
        files=[enterprise/"actions_dispatch_bridge.py", enterprise/"actions_dispatch_bridge_legacy.py",
               enterprise/"workflow_dispatch_github_effect.py"]
        texts={f.name:f.read_text(encoding="utf-8") for f in files}
        self.assertEqual(sum(text.count('method="POST"') for text in texts.values()),1)
        self.assertEqual(texts["workflow_dispatch_github_effect.py"].count('method="POST"'),1)
        self.assertNotIn('/dispatches', texts["actions_dispatch_bridge_legacy.py"])


if __name__ == "__main__": unittest.main()
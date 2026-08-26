from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.actions_dispatch_bridge import DispatchRequest
from cyber_lion.enterprise.actions_dispatch_bridge import GitHubApi
from cyber_lion.enterprise.workflow_dispatch_mediation import (
    CanonicalWorkflowDispatchAdmission,
    CanonicalWorkflowDispatchMediator,
    DurableWorkflowDispatchFence,
    WorkflowDispatchMediationError,
)
from cyber_lion.enterprise.workflow_dispatch_runtime import load_pinned_workflow_dispatch_admission_resolver

REPO = "DonkeyJJLove/ai_platform"
HEAD = "a" * 40


def request(*, workflow="f009-live-runtime-proof.yml", ref="master", head=HEAD, inputs="{}"):
    return DispatchRequest(
        schema_version="1", repository=REPO, issue_number=144, comment_id=123,
        actor="DonkeyJJLove", request_id="r2-test", workflow=workflow, ref=ref,
        expected_head=head, canonical_inputs=inputs,
    )


def admission(req: DispatchRequest):
    return CanonicalWorkflowDispatchAdmission(
        request_digest=req.payload_digest(), repository=req.repository, workflow=req.workflow,
        ref=req.ref, expected_head=req.expected_head,
        canonical_inputs_digest=sha256(req.canonical_inputs.encode()).hexdigest(),
        authority_lineage_digest="1" * 64, pdp_decision_digest="2" * 64,
        provider_id="external-test-live-authority+pdp", authority_epoch=7,
    ).sealed()


class Resolver:
    def __init__(self, req): self.value = admission(req)
    def resolve(self, req): return self.value


class Repo:
    def __init__(self, req): self.req=req; self.runs=[]
    def ref_head(self, ref): return self.req.expected_head if ref == self.req.ref else "b" * 40
    def workflow_exists(self, workflow, sha): return workflow == self.req.workflow and sha == self.req.expected_head
    def workflow_runs(self, workflow, ref): return list(self.runs)


class Effect:
    def __init__(self, repo): self.repo=repo; self.calls=0
    def execute_exact(self, req, adm):
        adm.binds(req); self.calls += 1
        self.repo.runs.append({
            "id": 9001, "event": "workflow_dispatch", "head_branch": req.ref,
            "head_sha": req.expected_head,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })


class WorkflowDispatchMediationTests(unittest.TestCase):
    def build(self, req):
        td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        repo=Repo(req); effect=Effect(repo)
        mediator=CanonicalWorkflowDispatchMediator(
            admissions=Resolver(req), repository=repo, effect=effect,
            fence=DurableWorkflowDispatchFence(str(Path(td.name)/"dispatch.sqlite")),
        )
        return mediator,repo,effect

    def test_exact_dispatch_reaches_reconciled(self):
        req=request(); mediator,_,effect=self.build(req)
        result=mediator.execute(req)
        self.assertEqual(result["effect"], "workflow_dispatch")
        self.assertEqual(result["fence_state"], "RECONCILED")
        self.assertEqual(result["run_id"], 9001)
        self.assertEqual(effect.calls, 1)

    def test_request_substitution_is_denied_before_effect(self):
        req=request(); mediator,_,effect=self.build(req)
        mediator.admissions.value=replace(admission(req), expected_head="b"*40, admission_digest="").sealed()
        with self.assertRaises(WorkflowDispatchMediationError): mediator.execute(req)
        self.assertEqual(effect.calls, 0)

    def test_authority_or_pdp_drift_after_prepared_is_denied(self):
        req=request(); mediator,_,effect=self.build(req)
        first=admission(req); second=replace(first, pdp_decision_digest="3"*64, admission_digest="").sealed()
        class Drift:
            def __init__(self): self.n=0
            def resolve(self, _): self.n+=1; return first if self.n == 1 else second
        mediator.admissions=Drift()
        with self.assertRaises(WorkflowDispatchMediationError): mediator.execute(req)
        self.assertEqual(effect.calls, 0)

    def test_durable_replay_is_denied(self):
        req=request(); mediator,repo,effect=self.build(req)
        self.assertEqual(mediator.execute(req)["fence_state"], "RECONCILED")
        repo.runs=[]
        with self.assertRaises(WorkflowDispatchMediationError): mediator.execute(req)
        self.assertEqual(effect.calls, 1)

    def test_ambiguous_observation_fails_closed(self):
        req=request(); mediator,repo,effect=self.build(req)
        original=effect.execute_exact
        def ambiguous(r,a):
            original(r,a)
            repo.runs.append(dict(repo.runs[0], id=9002))
        effect.execute_exact=ambiguous
        with self.assertRaisesRegex(WorkflowDispatchMediationError, "missing or ambiguous"):
            mediator.execute(req)
        self.assertEqual(effect.calls, 1)

    def test_production_api_direct_dispatch_is_disabled(self):
        api=GitHubApi(REPO, "not-used")
        with self.assertRaisesRegex(RuntimeError, "canonical mediator required"):
            api.dispatch("f009-live-runtime-proof.yml", "master", {})

    def test_missing_external_trusted_runtime_fails_closed(self):
        saved={k:os.environ.pop(k, None) for k in (
            "LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_PATH",
            "LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_DIGEST",
        )}
        try:
            with self.assertRaisesRegex(WorkflowDispatchMediationError, "runtime unavailable"):
                load_pinned_workflow_dispatch_admission_resolver()
        finally:
            for k,v in saved.items():
                if v is not None: os.environ[k]=v


if __name__ == "__main__": unittest.main()
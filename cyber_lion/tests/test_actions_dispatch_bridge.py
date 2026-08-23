from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import unittest
import zipfile

from cyber_lion.enterprise.actions_dispatch_bridge import (
    DEFAULT_POLICY,
    OBSERVE_PREFIX,
    PREFIX,
    execute,
    parse_envelope,
    parse_observe_envelope,
)


HEAD = "af93c8364a722f9184127379ee51df92d071a368"
REPO = "DonkeyJJLove/ai_platform"
RUN_ID = 424242


def envelope(*, workflow="f009-live-runtime-proof.yml", ref="master", expected_head=HEAD, request_id="req-1", inputs="{}") -> str:
    return "\n".join((PREFIX, f"workflow={workflow}", f"ref={ref}", f"expected_head={expected_head}", f"request_id={request_id}", f"inputs={inputs}"))


def observe_envelope(*, request_id="f009-post-merge-r2", require_success="true") -> str:
    return "\n".join((OBSERVE_PREFIX, f"request_id={request_id}", f"require_success={require_success}"))


def event(body: str, *, issue=144, comment_id=9001, actor="DonkeyJJLove", action="created") -> dict:
    return {"action": action, "issue": {"number": issue}, "comment": {"id": comment_id, "body": body, "user": {"login": actor}}, "repository": {"full_name": REPO}}


def dispatch_receipt_body(*, request_id="f009-post-merge-r2", accepted_at=None) -> str:
    accepted_at = accepted_at or datetime.now(timezone.utc).isoformat()
    return "\n".join((
        "LION-DISPATCH-RECEIPT v1", f"request_id={request_id}", "control_comment_id=5387369264",
        "actor=DonkeyJJLove", "permission=admin", "workflow=f009-live-runtime-proof.yml", "ref=master",
        f"expected_head={HEAD}", "canonical_inputs_digest=" + sha256(b"{}").hexdigest(),
        f"accepted_at={accepted_at}", "replay_key=" + "1" * 64,
        "bridge_implementation_digest=" + "2" * 64, "trust_decision=ALLOW", "github_api_result=ACCEPTED_204",
    ))


def f009_artifact_zip(run_id=RUN_ID, head=HEAD) -> tuple[bytes, dict]:
    payloads = {
        "runtime-identity.json": b'{"runtime":"ok"}', "admission.json": b'{"admission":"ok"}',
        "effect-currentness.json": b'{"current":true}', "sandbox-execution-receipt.json": b'{"effect":"ok"}',
        "independent-observation.json": b'{"observed":true}', "reconciliation-receipt.json": b'{"disposition":"MATCHED"}',
        "replay-denial.json": b'{"denied":true}',
    }
    manifest = {
        "schema_version": "2.0.0", "github_sha": head, "github_run_id": str(run_id),
        "artifact_digests": {name: sha256(data).hexdigest() for name, data in payloads.items()},
        "positive": {"effect_digest": "a" * 64, "independent_effect_digest": "a" * 64, "effect_executed_once": True, "reconciliation": "MATCHED"},
        "negative_results": {
            "authority-revoked-after-admission-before-effect": True, "authority-state-version-changed-before-effect": True,
            "policy-changed-before-effect": True, "observer-terminated-before-effect": True, "forged-authority-record": True,
            "forged-authority-signature": True, "forged-runtime-attestation": True, "runtime-identity-substitution": True,
            "execution-subject-substitution": True, "workspace-substitution": True, "resource-substitution": True,
            "payload-substitution": True, "replayed-admission": True, "replayed-execution": True,
            "missing-independent-observation": True, "observer-effect-mismatch": True, "receipt-without-observed-effect": True,
            "effect-without-receipt": True, "partial-effect": True, "UNKNOWN-effect-state": True,
        },
        "runtime_can_mint_authority": False, "runtime_has_signing_secret": False,
        "f005_runtime_resumed": False, "production_effect": False,
    }
    payloads["proof-manifest.json"] = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in payloads.items(): archive.writestr(name, data)
    data = output.getvalue()
    artifact = {"id": 888, "name": f"f009-live-runtime-proof-{run_id}-1", "digest": "sha256:" + sha256(data).hexdigest(), "expired": False, "workflow_run": {"head_sha": head}}
    return data, artifact


class FakeApi:
    def __init__(self, *, permission="admin", heads=None, comments=None, dispatch_status=True, workflow_exists=True, runs=None, terminal_run=None, artifacts=None, artifact_zip_bytes=b""):
        self.repository = REPO; self.permission = permission; self.heads = list(heads or [HEAD, HEAD]); self.comments = list(comments or [])
        self.dispatch_status = dispatch_status; self.workflow_present = workflow_exists; self.runs = list(runs or []); self.terminal_run = terminal_run
        self.artifacts = list(artifacts or []); self.artifact_zip_bytes = artifact_zip_bytes; self.claims = []; self.patches = []; self.dispatched = []; self.observation_comments = []
    def actor_permission(self, actor): return self.permission
    def ref_head(self, ref): return self.heads.pop(0) if self.heads else HEAD
    def workflow_exists(self, workflow, sha): return self.workflow_present
    def issue_comments(self, issue_number): return self.comments
    def post_issue_comment(self, issue_number, body):
        if body.startswith("LION-DISPATCH-CLAIM"): self.claims.append((issue_number, body)); return 777
        self.observation_comments.append((issue_number, body)); return 778
    def patch_issue_comment(self, comment_id, body): self.patches.append((comment_id, body))
    def dispatch(self, workflow, ref, inputs):
        if not self.dispatch_status: raise RuntimeError("dispatch failed")
        self.dispatched.append((workflow, ref, inputs))
    def workflow_runs(self, workflow, ref): return self.runs
    def workflow_run(self, run_id):
        if self.terminal_run is None: raise RuntimeError("missing terminal run")
        return self.terminal_run
    def run_artifacts(self, run_id): return self.artifacts
    def artifact_zip(self, artifact_id): return self.artifact_zip_bytes


class DispatchObservationBridgeTests(unittest.TestCase):
    def test_positive_exact_request_dispatches_once(self):
        api = FakeApi(); receipt = execute(event(envelope()), api)
        self.assertEqual(receipt.expected_head, HEAD); self.assertEqual(receipt.github_api_result, "ACCEPTED_204")
        self.assertEqual(api.dispatched, [("f009-live-runtime-proof.yml", "master", {})]); self.assertEqual(len(api.claims), 1); self.assertEqual(len(api.patches), 1)

    def test_untrusted_actor_denied_before_claim(self):
        api = FakeApi(permission="read")
        with self.assertRaisesRegex(RuntimeError, "untrusted"): execute(event(envelope(), actor="outsider"), api)
        self.assertFalse(api.claims); self.assertFalse(api.dispatched)

    def test_wrong_issue_denied(self):
        api = FakeApi()
        with self.assertRaisesRegex(RuntimeError, "wrong control issue"): execute(event(envelope(), issue=145), api)

    def test_malformed_dispatch_envelope_denied(self):
        with self.assertRaises(ValueError): parse_envelope("LION-DISPATCH v2", repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")

    def test_workflow_substitution_and_f005_are_denied(self):
        for workflow in ("release.yml", "../evil.yml", "f005-runtime-reconciliation-ingestion.yml"):
            with self.subTest(workflow=workflow):
                with self.assertRaises(ValueError): parse_envelope(envelope(workflow=workflow), repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")

    def test_ref_substitution_denied(self):
        for ref in ("dev", "refs/heads/master", "../master"):
            with self.subTest(ref=ref):
                with self.assertRaises(ValueError): parse_envelope(envelope(ref=ref), repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")

    def test_head_toctou_denied_after_claim_without_dispatch(self):
        api = FakeApi(heads=[HEAD, "2" * 40])
        with self.assertRaisesRegex(RuntimeError, "ref moved"): execute(event(envelope()), api)
        self.assertEqual(len(api.claims), 1); self.assertFalse(api.dispatched); self.assertIn("DENIED_HEAD_MOVED_BEFORE_DISPATCH", api.patches[-1][1])

    def test_api_failure_consumes_claim_fail_closed(self):
        api = FakeApi(dispatch_status=False)
        with self.assertRaisesRegex(RuntimeError, "dispatch failed"): execute(event(envelope()), api)
        self.assertEqual(len(api.claims), 1); self.assertIn("DISPATCH_API_FAILED_REQUEST_CONSUMED", api.patches[-1][1])

    def test_observation_discovers_existing_dispatch_without_redispatch(self):
        accepted = datetime.now(timezone.utc) - timedelta(seconds=5); created = accepted + timedelta(seconds=1); zip_bytes, artifact = f009_artifact_zip()
        comments = [{"body": dispatch_receipt_body(accepted_at=accepted.isoformat())}]
        run = {"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD, "created_at": created.isoformat(), "status": "completed", "conclusion": "success"}
        api = FakeApi(heads=[HEAD], comments=comments, runs=[run], terminal_run=run, artifacts=[artifact], artifact_zip_bytes=zip_bytes)
        receipt = execute(event(observe_envelope(), comment_id=9100), api)
        self.assertEqual(receipt.run_id, RUN_ID); self.assertEqual(receipt.observation_result, "OBSERVED_VERIFIED"); self.assertFalse(api.dispatched)
        self.assertEqual(len(api.observation_comments), 1); self.assertIn("LION-OBSERVATION-RECEIPT v1", api.observation_comments[0][1])

    def test_observation_rejects_ambiguous_runs(self):
        accepted = datetime.now(timezone.utc) - timedelta(seconds=5); created = accepted + timedelta(seconds=1)
        comments = [{"body": dispatch_receipt_body(accepted_at=accepted.isoformat())}]
        run = {"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD, "created_at": created.isoformat(), "status": "completed", "conclusion": "success"}
        api = FakeApi(heads=[HEAD], comments=comments, runs=[run, dict(run, id=RUN_ID + 1)])
        with self.assertRaisesRegex(RuntimeError, "ambiguous"): execute(event(observe_envelope()), api)
        self.assertFalse(api.dispatched)

    def test_observation_rejects_old_candidate_run(self):
        accepted = datetime.now(timezone.utc); old = accepted - timedelta(seconds=60); comments = [{"body": dispatch_receipt_body(accepted_at=accepted.isoformat())}]
        run = {"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD, "created_at": old.isoformat()}
        api = FakeApi(heads=[HEAD], comments=comments, runs=[run])
        with self.assertRaisesRegex(RuntimeError, "0 candidates"): execute(event(observe_envelope()), api)

    def test_observation_requires_terminal_success_when_requested(self):
        accepted = datetime.now(timezone.utc) - timedelta(seconds=5); created = accepted + timedelta(seconds=1); comments = [{"body": dispatch_receipt_body(accepted_at=accepted.isoformat())}]
        run = {"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD, "created_at": created.isoformat(), "status": "completed", "conclusion": "failure"}
        api = FakeApi(heads=[HEAD], comments=comments, runs=[run], terminal_run=run)
        with self.assertRaisesRegex(RuntimeError, "conclusion"): execute(event(observe_envelope()), api)

    def test_observation_rejects_artifact_digest_tamper(self):
        accepted = datetime.now(timezone.utc) - timedelta(seconds=5); created = accepted + timedelta(seconds=1); zip_bytes, artifact = f009_artifact_zip(); artifact = dict(artifact, digest="sha256:" + "0" * 64)
        comments = [{"body": dispatch_receipt_body(accepted_at=accepted.isoformat())}]
        run = {"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD, "created_at": created.isoformat(), "status": "completed", "conclusion": "success"}
        api = FakeApi(heads=[HEAD], comments=comments, runs=[run], terminal_run=run, artifacts=[artifact], artifact_zip_bytes=zip_bytes)
        with self.assertRaisesRegex(RuntimeError, "archive digest mismatch"): execute(event(observe_envelope()), api)

    def test_observation_envelope_is_exact(self):
        parsed = parse_observe_envelope(observe_envelope(), repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove"); self.assertTrue(parsed.require_success)
        for bad in ("LION-OBSERVE v2\nrequest_id=x\nrequire_success=true", "LION-OBSERVE v1\nrequire_success=true\nrequest_id=x", "LION-OBSERVE v1\nrequest_id=x\nrequire_success=yes"):
            with self.subTest(body=bad):
                with self.assertRaises(ValueError): parse_observe_envelope(bad, repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")

    def test_workflow_contract_supports_dispatch_and_observation_only(self):
        text = Path(".github/workflows/lion-actions-dispatch-bridge.yml").read_text(encoding="utf-8")
        for required in ("issue_comment:", "types: [created]", "actions: write", "issues: write", "contents: read", "github.event.issue.number == 144", "LION-DISPATCH v1", "LION-OBSERVE v1", "concurrency:"):
            self.assertIn(required, text)
        for forbidden in ("pull_request_target", "secrets.", "gh workflow run", "contents: write"):
            self.assertNotIn(forbidden, text)

    def test_policy_does_not_accept_status_governor_role_or_graph_as_authority(self):
        rendered = json.dumps(asdict(DEFAULT_POLICY), sort_keys=True).lower()
        for forbidden in ("status", "governor", "formation", "mosaic", "enterprisegraph"): self.assertNotIn(forbidden, rendered)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import unittest
import zipfile

from cyber_lion.enterprise.actions_dispatch_bridge import (
    DEFAULT_POLICY,
    GitHubApi,
    OBSERVE_PREFIX,
    OBSERVATION_RECEIPT_PREFIX,
    PREFIX,
    RECEIPT_PREFIX,
    execute,
    observe,
    parse_envelope,
    parse_observation_envelope,
)

HEAD = "af93c8364a722f9184127379ee51df92d071a368"
REPO = "DonkeyJJLove/ai_platform"
RUN_ID = 32660000001
ARTIFACT_ID = 9500000001
ACCEPTED = "2026-08-23T17:24:55+00:00"


def envelope(*, workflow="f009-live-runtime-proof.yml", ref="master", expected_head=HEAD, request_id="req-1", inputs="{}") -> str:
    return "\n".join((PREFIX, f"workflow={workflow}", f"ref={ref}", f"expected_head={expected_head}", f"request_id={request_id}", f"inputs={inputs}"))


def observe_envelope(request_id="req-1") -> str:
    return "\n".join((OBSERVE_PREFIX, f"request_id={request_id}"))


def event(body: str, *, issue=144, comment_id=9001, actor="DonkeyJJLove", action="created") -> dict:
    return {"action": action, "issue": {"number": issue}, "comment": {"id": comment_id, "body": body, "user": {"login": actor}}, "repository": {"full_name": REPO}}


def dispatch_receipt_comment(request_id="req-1", *, accepted_at=ACCEPTED, expected_head=HEAD) -> dict:
    body = "\n".join((
        RECEIPT_PREFIX,
        f"request_id={request_id}",
        "control_comment_id=8001",
        "actor=DonkeyJJLove",
        "permission=admin",
        "workflow=f009-live-runtime-proof.yml",
        "ref=master",
        f"expected_head={expected_head}",
        "canonical_inputs_digest=" + sha256(b"{}").hexdigest(),
        f"accepted_at={accepted_at}",
        "replay_key=" + "1" * 64,
        "bridge_implementation_digest=" + "2" * 64,
        "trust_decision=ALLOW",
        "github_api_result=ACCEPTED_204",
    ))
    return {"body": body}


def make_artifact(run_id=RUN_ID, head=HEAD):
    payloads = {
        "runtime-identity.json": b'{"runtime":"ok"}',
        "admission.json": b'{"admission":"ok"}',
        "effect-currentness.json": b'{"current":"ok"}',
        "sandbox-execution-receipt.json": b'{"receipt":"ok"}',
        "independent-observation.json": b'{"observation":"ok"}',
        "reconciliation-receipt.json": b'{"disposition":"MATCHED","anomaly_codes":[]}',
        "replay-denial.json": b'{"replay_denied":true}',
    }
    manifest = {
        "github_run_id": str(run_id),
        "github_sha": head,
        "artifact_digests": {name: sha256(data).hexdigest() for name, data in payloads.items()},
        "positive": {"reconciliation": "MATCHED", "effect_executed_once": True, "effect_digest": "a" * 64, "independent_effect_digest": "a" * 64},
        "negative_results": {"authority-revoked-after-admission-before-effect": True, "policy-changed-before-effect": True, "UNKNOWN-effect-state": True},
        "runtime_can_mint_authority": False,
        "runtime_has_signing_secret": False,
        "f005_runtime_resumed": False,
        "production_effect": False,
    }
    payloads["proof-manifest.json"] = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in payloads.items():
            zf.writestr(name, data)
    return out.getvalue()


class FakeApi:
    def __init__(self, *, permission="admin", heads=None, comments=None, dispatch_status=True, workflow_exists=True, runs=None, terminal=None, artifacts=None, artifact_bytes=None):
        self.repository = REPO
        self.permission = permission
        self.heads = list(heads or [HEAD, HEAD])
        self.comments = list(comments or [])
        self.dispatch_status = dispatch_status
        self.workflow_present = workflow_exists
        self.claims = []
        self.patches = []
        self.dispatched = []
        self.posted = []
        self.runs = list(runs or [{"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD, "created_at": "2026-08-23T17:25:00Z"}])
        self.terminal = terminal or {"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD, "status": "completed", "conclusion": "success", "run_attempt": 1}
        self.artifact_bytes = artifact_bytes or make_artifact()
        digest = "sha256:" + sha256(self.artifact_bytes).hexdigest()
        self.artifacts = list(artifacts or [{"id": ARTIFACT_ID, "name": f"f009-live-runtime-proof-{RUN_ID}-1", "size_in_bytes": len(self.artifact_bytes), "expired": False, "digest": digest}])

    def actor_permission(self, actor): return self.permission
    def ref_head(self, ref): return self.heads.pop(0) if self.heads else HEAD
    def workflow_exists(self, workflow, sha): return self.workflow_present
    def issue_comments(self, issue_number): return self.comments
    def post_issue_comment(self, issue_number, body):
        self.posted.append((issue_number, body)); self.claims.append((issue_number, body)); return 777 + len(self.posted)
    def patch_issue_comment(self, comment_id, body): self.patches.append((comment_id, body))
    def dispatch(self, workflow, ref, inputs):
        if not self.dispatch_status: raise RuntimeError("dispatch failed")
        self.dispatched.append((workflow, ref, inputs))
    def workflow_runs(self, workflow, ref): return self.runs
    def workflow_run(self, run_id): return self.terminal
    def run_artifacts(self, run_id): return self.artifacts
    def download_artifact(self, artifact_id): return self.artifact_bytes


class DispatchBridgeTests(unittest.TestCase):
    def test_github_api_origin_is_exact_https_boundary(self):
        self.assertEqual(GitHubApi(REPO, "token").api_url, "https://api.github.com")
        for bad in (
            "http://api.github.com", "file:///tmp/socket",
            "https://api.github.com@evil.example", "https://evil.example",
            "https://api.github.com:8443",
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(RuntimeError, "canonical HTTPS"):
                    GitHubApi(REPO, "token", bad)

    def test_positive_exact_request_dispatches_once(self):
        api = FakeApi(); receipt = execute(event(envelope()), api)
        self.assertEqual(receipt.expected_head, HEAD); self.assertEqual(receipt.github_api_result, "ACCEPTED_204")
        self.assertEqual(api.dispatched, [("f009-live-runtime-proof.yml", "master", {})]); self.assertEqual(len(api.patches), 1)

    def test_untrusted_actor_denied_before_claim(self):
        api = FakeApi(permission="read")
        with self.assertRaisesRegex(RuntimeError, "untrusted"): execute(event(envelope(), actor="outsider"), api)
        self.assertFalse(api.dispatched)

    def test_wrong_issue_and_malformed_dispatch_denied(self):
        with self.assertRaisesRegex(RuntimeError, "wrong control issue"): execute(event(envelope(), issue=145), FakeApi())
        with self.assertRaises(ValueError): parse_envelope("LION-DISPATCH v2", repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")

    def test_workflow_ref_inputs_and_shell_substitution_denied(self):
        for workflow in ("release.yml", "../evil.yml", "f005-runtime-reconciliation-ingestion.yml"):
            with self.assertRaises(ValueError): parse_envelope(envelope(workflow=workflow), repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")
        for ref in ("dev", "refs/heads/master", "../master"):
            with self.assertRaises(ValueError): parse_envelope(envelope(ref=ref), repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")
        for inputs in ('{"x":1}', '{ "x": 1 }', '[]', '{not-json}'):
            with self.assertRaises(ValueError): parse_envelope(envelope(inputs=inputs), repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")
        for request_id in ("x;rm", "$(id)", "x y", "x\nworkflow=evil.yml"):
            with self.assertRaises(ValueError): parse_envelope(envelope(request_id=request_id), repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")

    def test_stale_and_toctou_head_denied(self):
        with self.assertRaisesRegex(RuntimeError, "stale expected head"): execute(event(envelope()), FakeApi(heads=["1" * 40]))
        api = FakeApi(heads=[HEAD, "2" * 40])
        with self.assertRaisesRegex(RuntimeError, "ref moved"): execute(event(envelope()), api)
        self.assertFalse(api.dispatched); self.assertIn("DENIED_HEAD_MOVED_BEFORE_DISPATCH", api.patches[-1][1])

    def test_api_failure_consumes_claim_fail_closed(self):
        api = FakeApi(dispatch_status=False)
        with self.assertRaisesRegex(RuntimeError, "dispatch failed"): execute(event(envelope()), api)
        self.assertFalse(api.dispatched); self.assertIn("DISPATCH_API_FAILED_REQUEST_CONSUMED", api.patches[-1][1])

    def test_observation_envelope_is_exact(self):
        req = parse_observation_envelope(observe_envelope("f009-post-merge-r2"), repository=REPO, issue_number=144, comment_id=42, actor="DonkeyJJLove")
        self.assertEqual(req.request_id, "f009-post-merge-r2")
        for body in ("LION-OBSERVE v2\nrequest_id=x", "LION-OBSERVE v1\nworkflow=x\nrequest_id=y"):
            with self.assertRaises(ValueError): parse_observation_envelope(body, repository=REPO, issue_number=144, comment_id=42, actor="DonkeyJJLove")

    def test_observe_existing_dispatch_does_not_dispatch_again(self):
        api = FakeApi(comments=[dispatch_receipt_comment("f009-post-merge-r2")])
        receipt = observe(event(observe_envelope("f009-post-merge-r2"), comment_id=9100), api, discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)
        self.assertEqual(receipt.run_id, RUN_ID); self.assertEqual(receipt.expected_head, HEAD)
        self.assertEqual(receipt.observation_result, "OBSERVED_VERIFIED"); self.assertEqual(receipt.positive_reconciliation, "MATCHED")
        self.assertFalse(api.dispatched); self.assertTrue(any(OBSERVATION_RECEIPT_PREFIX in body for _, body in api.posted))

    def test_observe_rejects_wrong_event_old_head_or_pre_dispatch_run(self):
        base_comments = [dispatch_receipt_comment("req-1")]
        bad_runs = [
            [{"id": RUN_ID, "event": "pull_request", "head_branch": "master", "head_sha": HEAD, "created_at": "2026-08-23T17:25:00Z"}],
            [{"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master", "head_sha": "3" * 40, "created_at": "2026-08-23T17:25:00Z"}],
            [{"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD, "created_at": "2026-08-23T17:00:00Z"}],
        ]
        for runs in bad_runs:
            with self.assertRaisesRegex(RuntimeError, "not observed"):
                observe(event(observe_envelope("req-1")), FakeApi(comments=base_comments, runs=runs), discovery_timeout=0.0, terminal_timeout=0.01, poll_seconds=0.001)

    def test_observe_rejects_ambiguous_matching_runs(self):
        run = {"event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD, "created_at": "2026-08-23T17:25:00Z"}
        runs = [{**run, "id": RUN_ID}, {**run, "id": RUN_ID + 1}]
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            observe(event(observe_envelope("req-1")), FakeApi(comments=[dispatch_receipt_comment("req-1")], runs=runs), discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)

    def test_observe_rejects_terminal_failure(self):
        terminal = {"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD, "status": "completed", "conclusion": "failure", "run_attempt": 1}
        with self.assertRaisesRegex(RuntimeError, "not exact successful"):
            observe(event(observe_envelope("req-1")), FakeApi(comments=[dispatch_receipt_comment("req-1")], terminal=terminal), discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)

    def test_observe_rejects_artifact_digest_or_manifest_substitution(self):
        good = make_artifact(); good_digest = "sha256:" + sha256(good).hexdigest(); bad_bytes = good + b"x"
        artifacts_bad_digest = [{"id": ARTIFACT_ID, "name": f"f009-live-runtime-proof-{RUN_ID}-1", "size_in_bytes": len(good), "expired": False, "digest": good_digest}]
        api = FakeApi(comments=[dispatch_receipt_comment("req-1")], artifact_bytes=bad_bytes, artifacts=artifacts_bad_digest)
        with self.assertRaisesRegex(RuntimeError, "digest differs"):
            observe(event(observe_envelope("req-1")), api, discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)
        wrong_manifest = make_artifact(head="4" * 40); digest = "sha256:" + sha256(wrong_manifest).hexdigest()
        artifacts = [{"id": ARTIFACT_ID, "name": f"f009-live-runtime-proof-{RUN_ID}-1", "size_in_bytes": len(wrong_manifest), "expired": False, "digest": digest}]
        with self.assertRaisesRegex(RuntimeError, "head binding mismatch"):
            observe(event(observe_envelope("req-1")), FakeApi(comments=[dispatch_receipt_comment("req-1")], artifact_bytes=wrong_manifest, artifacts=artifacts), discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)

    def test_observe_rejects_duplicate_observation(self):
        existing = {"body": OBSERVATION_RECEIPT_PREFIX + "\nrequest_id=req-1\nobservation_result=OBSERVED_VERIFIED"}
        with self.assertRaisesRegex(RuntimeError, "already has"):
            observe(event(observe_envelope("req-1")), FakeApi(comments=[dispatch_receipt_comment("req-1"), existing]), discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)

    def test_workflow_contract_is_narrow_and_observation_enabled(self):
        text = Path(".github/workflows/lion-actions-dispatch-bridge.yml").read_text(encoding="utf-8")
        self.assertIn("issue_comment:", text); self.assertIn("types: [created]", text)
        self.assertIn("actions: write", text); self.assertIn("issues: write", text); self.assertIn("contents: read", text)
        self.assertIn("github.event.issue.number == 144", text); self.assertIn("LION-DISPATCH v1", text); self.assertIn("LION-OBSERVE v1", text)
        self.assertIn("concurrency:", text); self.assertNotIn("pull_request_target", text); self.assertNotIn("secrets.", text)
        self.assertNotIn("gh workflow run", text); self.assertNotIn("contents: write", text)

    def test_policy_does_not_accept_status_or_fleet_objects_as_authority(self):
        rendered = json.dumps(asdict(DEFAULT_POLICY), sort_keys=True).lower()
        for forbidden in ("status", "governor", "formation", "mosaic", "enterprisegraph"):
            self.assertNotIn(forbidden, rendered)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import unittest
import zipfile

from cyber_lion.contracts.group_channel import (
    GroupChannelEnvelope,
    GroupChannelReceipt,
    encode_envelope,
    receipt_json,
)
from cyber_lion.enterprise.actions_dispatch_bridge import (
    DEFAULT_POLICY,
    GROUP_OBSERVATION_RECEIPT_PREFIX,
    GitHubApi,
    OBSERVATION_RECEIPT_PREFIX,
    OBSERVE_PREFIX,
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


def envelope(
    *,
    workflow="f009-live-runtime-proof.yml",
    ref="master",
    expected_head=HEAD,
    request_id="req-1",
    inputs="{}",
) -> str:
    return "\n".join(
        (
            PREFIX,
            f"workflow={workflow}",
            f"ref={ref}",
            f"expected_head={expected_head}",
            f"request_id={request_id}",
            f"inputs={inputs}",
        )
    )


def observe_envelope(request_id="req-1") -> str:
    return "\n".join((OBSERVE_PREFIX, f"request_id={request_id}"))


def event(
    body: str,
    *,
    issue=144,
    comment_id=9001,
    actor="DonkeyJJLove",
    action="created",
) -> dict:
    return {
        "action": action,
        "issue": {"number": issue},
        "comment": {
            "id": comment_id,
            "body": body,
            "user": {"login": actor},
        },
        "repository": {"full_name": REPO},
    }


def dispatch_receipt_comment(
    request_id="req-1",
    *,
    accepted_at=ACCEPTED,
    expected_head=HEAD,
    workflow="f009-live-runtime-proof.yml",
    control_comment_id=8001,
    canonical_inputs="{}",
) -> dict:
    body = "\n".join(
        (
            RECEIPT_PREFIX,
            f"request_id={request_id}",
            f"control_comment_id={control_comment_id}",
            "actor=DonkeyJJLove",
            "permission=admin",
            f"workflow={workflow}",
            "ref=master",
            f"expected_head={expected_head}",
            "canonical_inputs_digest="
            + sha256(canonical_inputs.encode("utf-8")).hexdigest(),
            f"accepted_at={accepted_at}",
            "replay_key=" + "1" * 64,
            "bridge_implementation_digest=" + "2" * 64,
            "trust_decision=ALLOW",
            "github_api_result=ACCEPTED_204",
        )
    )
    return {"id": 8100, "body": body}


def make_f009_artifact(run_id=RUN_ID, head=HEAD):
    payloads = {
        "runtime-identity.json": b'{"runtime":"ok"}',
        "admission.json": b'{"admission":"ok"}',
        "effect-currentness.json": b'{"current":"ok"}',
        "sandbox-execution-receipt.json": b'{"receipt":"ok"}',
        "independent-observation.json": b'{"observation":"ok"}',
        "reconciliation-receipt.json": (
            b'{"disposition":"MATCHED","anomaly_codes":[]}'
        ),
        "replay-denial.json": b'{"replay_denied":true}',
    }
    manifest = {
        "github_run_id": str(run_id),
        "github_sha": head,
        "artifact_digests": {
            name: sha256(data).hexdigest() for name, data in payloads.items()
        },
        "positive": {
            "reconciliation": "MATCHED",
            "effect_executed_once": True,
            "effect_digest": "a" * 64,
            "independent_effect_digest": "a" * 64,
        },
        "negative_results": {
            "authority-revoked-after-admission-before-effect": True,
            "policy-changed-before-effect": True,
            "UNKNOWN-effect-state": True,
        },
        "runtime_can_mint_authority": False,
        "runtime_has_signing_secret": False,
        "f005_runtime_resumed": False,
        "production_effect": False,
    }
    payloads["proof-manifest.json"] = json.dumps(
        manifest, sort_keys=True, separators=(",", ":")
    ).encode()
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in payloads.items():
            zf.writestr(name, data)
    return out.getvalue()


def make_group_bundle(target="security", request_id="group-1"):
    accepted = datetime.fromisoformat(ACCEPTED)
    issued = accepted - timedelta(seconds=10)
    expires = issued + timedelta(minutes=30)
    group_envelope = GroupChannelEnvelope.build(
        repository=REPO,
        message_id=f"e003-channel-{target}-test",
        target=target,
        expected_master_head=HEAD,
        issued_at=issued.isoformat(),
        expires_at=expires.isoformat(),
        payload={
            "kind": "E003_CHANNEL_REPLACEMENT_PROOF",
            "no_authority": True,
            "sequence": 2,
            "transport": "actions-artifact",
        },
        now=accepted,
    )
    encoded = encode_envelope(group_envelope)
    canonical_inputs = json.dumps(
        {"envelope_b64": encoded}, sort_keys=True, separators=(",", ":")
    )
    control_id = 8001
    control = {
        "id": control_id,
        "body": envelope(
            workflow="lion-group-channel.yml",
            request_id=request_id,
            inputs=canonical_inputs,
        ),
        "user": {"login": "DonkeyJJLove"},
    }
    dispatch = dispatch_receipt_comment(
        request_id,
        workflow="lion-group-channel.yml",
        control_comment_id=control_id,
        canonical_inputs=canonical_inputs,
    )
    group_receipt = GroupChannelReceipt.build(
        envelope=group_envelope,
        emitted_at="2026-08-23T17:25:02+00:00",
        workflow_run_id=RUN_ID,
        workflow_run_attempt=1,
    )
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lion-group-channel-receipt.json", receipt_json(group_receipt))
    return control, dispatch, group_envelope, group_receipt, out.getvalue()


class FakeApi:
    def __init__(
        self,
        *,
        permission="admin",
        heads=None,
        comments=None,
        dispatch_status=True,
        workflow_exists=True,
        runs=None,
        terminal=None,
        artifacts=None,
        artifact_bytes=None,
    ):
        self.repository = REPO
        self.permission = permission
        self.heads = list(heads or [HEAD, HEAD])
        self.comments = list(comments or [])
        self.dispatch_status = dispatch_status
        self.workflow_present = workflow_exists
        self.patches = []
        self.dispatched = []
        self.posted = []
        self.runs = list(
            runs
            or [
                {
                    "id": RUN_ID,
                    "event": "workflow_dispatch",
                    "head_branch": "master",
                    "head_sha": HEAD,
                    "created_at": "2026-08-23T17:25:00Z",
                }
            ]
        )
        self.terminal = terminal or {
            "id": RUN_ID,
            "event": "workflow_dispatch",
            "head_branch": "master",
            "head_sha": HEAD,
            "status": "completed",
            "conclusion": "success",
            "run_attempt": 1,
            "actor": {"login": "github-actions[bot]"},
            "triggering_actor": {"login": "github-actions[bot]"},
        }
        self.artifact_bytes = artifact_bytes or make_f009_artifact()
        digest = "sha256:" + sha256(self.artifact_bytes).hexdigest()
        self.artifacts = list(
            artifacts
            or [
                {
                    "id": ARTIFACT_ID,
                    "name": f"f009-live-runtime-proof-{RUN_ID}-1",
                    "size_in_bytes": len(self.artifact_bytes),
                    "expired": False,
                    "digest": digest,
                    "created_at": "2026-08-23T17:25:03Z",
                }
            ]
        )

    def actor_permission(self, actor):
        return self.permission

    def ref_head(self, ref):
        return self.heads.pop(0) if self.heads else HEAD

    def workflow_exists(self, workflow, sha):
        return self.workflow_present

    def issue_comments(self, issue_number):
        return self.comments

    def post_issue_comment(self, issue_number, body):
        self.posted.append((issue_number, body))
        return 777 + len(self.posted)

    def patch_issue_comment(self, comment_id, body):
        self.patches.append((comment_id, body))

    def dispatch(self, workflow, ref, inputs):
        if not self.dispatch_status:
            raise RuntimeError("dispatch failed")
        self.dispatched.append((workflow, ref, inputs))

    def workflow_runs(self, workflow, ref):
        return self.runs

    def workflow_run(self, run_id):
        return self.terminal

    def run_artifacts(self, run_id):
        return self.artifacts

    def download_artifact(self, artifact_id):
        return self.artifact_bytes


class DispatchBridgeRegressionTests(unittest.TestCase):
    def test_exact_f009_dispatch_and_observation_still_work(self):
        api = FakeApi()
        dispatch = execute(event(envelope()), api)
        self.assertEqual(dispatch.github_api_result, "ACCEPTED_204")
        self.assertEqual(api.dispatched, [("f009-live-runtime-proof.yml", "master", {})])

        api = FakeApi(comments=[dispatch_receipt_comment("req-1")])
        receipt = observe(
            event(observe_envelope("req-1")),
            api,
            discovery_timeout=0.01,
            terminal_timeout=0.01,
            poll_seconds=0.001,
        )
        self.assertEqual(receipt.observation_result, "OBSERVED_VERIFIED")
        self.assertEqual(receipt.positive_reconciliation, "MATCHED")
        self.assertTrue(
            any(OBSERVATION_RECEIPT_PREFIX in body for _, body in api.posted)
        )

    def test_dispatch_policy_remains_narrow(self):
        for workflow in (
            "release.yml",
            "../evil.yml",
            "f005-runtime-reconciliation-ingestion.yml",
        ):
            with self.assertRaises(ValueError):
                parse_envelope(
                    envelope(workflow=workflow),
                    repository=REPO,
                    issue_number=144,
                    comment_id=1,
                    actor="DonkeyJJLove",
                )
        with self.assertRaisesRegex(RuntimeError, "untrusted"):
            execute(event(envelope(), actor="outsider"), FakeApi(permission="read"))

    def test_group_dispatch_requires_exact_input_set(self):
        request = parse_envelope(
            envelope(
                workflow="lion-group-channel.yml",
                inputs='{"envelope_b64":"YQ=="}',
            ),
            repository=REPO,
            issue_number=144,
            comment_id=1,
            actor="DonkeyJJLove",
        )
        self.assertEqual(request.inputs(), {"envelope_b64": "YQ=="})
        for bad in ("{}", '{"extra":"x"}'):
            with self.assertRaisesRegex(ValueError, "input key set mismatch"):
                parse_envelope(
                    envelope(workflow="lion-group-channel.yml", inputs=bad),
                    repository=REPO,
                    issue_number=144,
                    comment_id=1,
                    actor="DonkeyJJLove",
                )

    def test_observation_envelope_is_exact(self):
        request = parse_observation_envelope(
            observe_envelope("req-1"),
            repository=REPO,
            issue_number=144,
            comment_id=42,
            actor="DonkeyJJLove",
        )
        self.assertEqual(request.request_id, "req-1")
        with self.assertRaises(ValueError):
            parse_observation_envelope(
                "LION-OBSERVE v2\nrequest_id=x",
                repository=REPO,
                issue_number=144,
                comment_id=42,
                actor="DonkeyJJLove",
            )

    def test_workflow_contract_not_modified_or_widened(self):
        text = Path(".github/workflows/lion-actions-dispatch-bridge.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("github.event.issue.number == 144", text)
        self.assertIn("actions: write", text)
        self.assertIn("issues: write", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("pull_request_target", text)
        self.assertNotIn("contents: write", text)

    def test_policy_objects_are_not_authority(self):
        rendered = json.dumps(asdict(DEFAULT_POLICY), sort_keys=True).lower()
        for forbidden in ("status", "governor", "formation", "mosaic"):
            self.assertNotIn(forbidden, rendered)


class GroupChannelObservationTests(unittest.TestCase):
    def _api(self, *, target="security", request_id="group-1", **overrides):
        control, dispatch, envelope_obj, receipt, artifact = make_group_bundle(
            target, request_id
        )
        digest = "sha256:" + sha256(artifact).hexdigest()
        defaults = {
            "comments": [control, dispatch],
            "artifact_bytes": artifact,
            "artifacts": [
                {
                    "id": ARTIFACT_ID,
                    "name": f"lion-group-channel-receipt-{RUN_ID}-1",
                    "size_in_bytes": len(artifact),
                    "expired": False,
                    "digest": digest,
                    "created_at": "2026-08-23T17:25:03Z",
                }
            ],
        }
        defaults.update(overrides)
        return FakeApi(**defaults), envelope_obj, receipt

    def test_positive_architecture_security_and_runtime(self):
        for target in ("architecture", "security", "runtime"):
            with self.subTest(target=target):
                request_id = f"group-{target}"
                api, _, expected = self._api(
                    target=target, request_id=request_id
                )
                result = observe(
                    event(observe_envelope(request_id), comment_id=9100),
                    api,
                    discovery_timeout=0.01,
                    terminal_timeout=0.01,
                    poll_seconds=0.001,
                )
                self.assertEqual(result.target, target)
                self.assertEqual(
                    result.group_channel_receipt_digest, expected.receipt_digest
                )
                self.assertFalse(result.authority_effect)
                self.assertFalse(result.repository_effect)
                self.assertEqual(result.state, "EMITTED_EVIDENCE_ONLY")
                self.assertTrue(
                    any(
                        GROUP_OBSERVATION_RECEIPT_PREFIX in body
                        for _, body in api.posted
                    )
                )
                self.assertFalse(api.dispatched)

    def test_zero_and_multiple_matching_runs_fail_closed(self):
        api, _, _ = self._api(runs=[])
        api.runs = []
        with self.assertRaisesRegex(RuntimeError, "not observed"):
            observe(
                event(observe_envelope("group-1")),
                api,
                discovery_timeout=0.0,
                terminal_timeout=0.01,
                poll_seconds=0.001,
            )
        run = {
            "event": "workflow_dispatch",
            "head_branch": "master",
            "head_sha": HEAD,
            "created_at": "2026-08-23T17:25:00Z",
        }
        api, _, _ = self._api(runs=[{**run, "id": RUN_ID}, {**run, "id": RUN_ID + 1}])
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            observe(
                event(observe_envelope("group-1")),
                api,
                discovery_timeout=0.01,
                terminal_timeout=0.01,
                poll_seconds=0.001,
            )

    def test_wrong_event_head_and_terminal_failure_fail_closed(self):
        for terminal in (
            {
                "id": RUN_ID,
                "event": "pull_request",
                "head_branch": "master",
                "head_sha": HEAD,
                "status": "completed",
                "conclusion": "success",
                "run_attempt": 1,
                "actor": {"login": "github-actions[bot]"},
                "triggering_actor": {"login": "github-actions[bot]"},
            },
            {
                "id": RUN_ID,
                "event": "workflow_dispatch",
                "head_branch": "master",
                "head_sha": "3" * 40,
                "status": "completed",
                "conclusion": "success",
                "run_attempt": 1,
                "actor": {"login": "github-actions[bot]"},
                "triggering_actor": {"login": "github-actions[bot]"},
            },
            {
                "id": RUN_ID,
                "event": "workflow_dispatch",
                "head_branch": "master",
                "head_sha": HEAD,
                "status": "completed",
                "conclusion": "failure",
                "run_attempt": 1,
                "actor": {"login": "github-actions[bot]"},
                "triggering_actor": {"login": "github-actions[bot]"},
            },
        ):
            api, _, _ = self._api(terminal=terminal)
            with self.assertRaisesRegex(RuntimeError, "not exact successful"):
                observe(
                    event(observe_envelope("group-1")),
                    api,
                    discovery_timeout=0.01,
                    terminal_timeout=0.01,
                    poll_seconds=0.001,
                )

    def test_artifact_absence_duplicate_expiry_and_name_fail_closed(self):
        cases = ([],)
        for artifacts in cases:
            api, _, _ = self._api(artifacts=[{"name": "wrong"}])
            api.artifacts = artifacts
            with self.assertRaisesRegex(RuntimeError, "missing or ambiguous"):
                observe(
                    event(observe_envelope("group-1")),
                    api,
                    discovery_timeout=0.01,
                    terminal_timeout=0.01,
                    poll_seconds=0.001,
                )
        api, _, _ = self._api()
        api.artifacts = [api.artifacts[0], dict(api.artifacts[0])]
        with self.assertRaisesRegex(RuntimeError, "missing or ambiguous"):
            observe(event(observe_envelope("group-1")), api, discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)
        api, _, _ = self._api()
        api.artifacts[0]["expired"] = True
        with self.assertRaisesRegex(RuntimeError, "missing or ambiguous"):
            observe(event(observe_envelope("group-1")), api, discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)
        api, _, _ = self._api()
        api.artifacts[0]["name"] = "wrong-name"
        with self.assertRaisesRegex(RuntimeError, "missing or ambiguous"):
            observe(event(observe_envelope("group-1")), api, discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)

    def test_zero_size_and_download_digest_mismatch_fail_closed(self):
        api, _, _ = self._api()
        api.artifacts[0]["size_in_bytes"] = 0
        with self.assertRaisesRegex(RuntimeError, "metadata invalid"):
            observe(event(observe_envelope("group-1")), api, discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)
        api, _, _ = self._api()
        api.artifact_bytes += b"tamper"
        with self.assertRaisesRegex(RuntimeError, "digest differs"):
            observe(event(observe_envelope("group-1")), api, discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)

    def test_invalid_zip_extra_member_and_missing_receipt_fail_closed(self):
        api, _, _ = self._api(artifact_bytes=b"not-a-zip")
        api.artifacts[0]["size_in_bytes"] = len(api.artifact_bytes)
        api.artifacts[0]["digest"] = "sha256:" + sha256(api.artifact_bytes).hexdigest()
        with self.assertRaisesRegex(RuntimeError, "valid ZIP"):
            observe(event(observe_envelope("group-1")), api, discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)
        for names in (("lion-group-channel-receipt.json", "extra.json"), ("wrong.json",)):
            out = BytesIO()
            with zipfile.ZipFile(out, "w") as zf:
                for name in names:
                    zf.writestr(name, b"{}\n")
            data = out.getvalue()
            api, _, _ = self._api(artifact_bytes=data)
            api.artifacts[0]["size_in_bytes"] = len(data)
            api.artifacts[0]["digest"] = "sha256:" + sha256(data).hexdigest()
            with self.assertRaisesRegex(RuntimeError, "file set mismatch"):
                observe(event(observe_envelope("group-1")), api, discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)

    def test_original_control_comment_and_input_digest_fail_closed(self):
        api, _, _ = self._api()
        api.comments = [api.comments[1]]
        with self.assertRaisesRegex(RuntimeError, "control comment"):
            observe(event(observe_envelope("group-1")), api, discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)
        api, _, _ = self._api()
        dispatch_body = api.comments[1]["body"].replace(
            "canonical_inputs_digest=",
            "canonical_inputs_digest=" + "f" * 64 + "#",
        )
        api.comments[1]["body"] = dispatch_body
        with self.assertRaises(RuntimeError):
            observe(event(observe_envelope("group-1")), api, discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)

    def test_actor_substitution_and_duplicate_success_fail_closed(self):
        api, _, _ = self._api()
        api.terminal["actor"] = {"login": "unexpected"}
        with self.assertRaisesRegex(RuntimeError, "actor substitution"):
            observe(event(observe_envelope("group-1")), api, discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)
        api, _, _ = self._api()
        api.comments.append(
            {
                "body": "\n".join(
                    (
                        GROUP_OBSERVATION_RECEIPT_PREFIX,
                        "request_id=group-1",
                        "observation_result=OBSERVED_VERIFIED",
                    )
                )
            }
        )
        with self.assertRaisesRegex(RuntimeError, "already has"):
            observe(event(observe_envelope("group-1")), api, discovery_timeout=0.01, terminal_timeout=0.01, poll_seconds=0.001)


if __name__ == "__main__":
    unittest.main()

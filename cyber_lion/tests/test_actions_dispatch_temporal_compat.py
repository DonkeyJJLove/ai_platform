from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
import unittest
import zipfile

from cyber_lion.contracts.actions_dispatch_bridge import DispatchReceipt
from cyber_lion.contracts.group_channel import (
    GroupChannelEnvelope,
    GroupChannelReceipt,
    encode_envelope,
    receipt_json,
)
from cyber_lion.enterprise import actions_dispatch_bridge as bridge
from cyber_lion.enterprise.actions_dispatch_temporal_compat import (
    LEGACY_LOOKBACK_SECONDS,
    _discover_run_compat,
    _matching_runs_compat,
    _wait_terminal_diagnostic,
)


HEAD = "a" * 40
REPO = "DonkeyJJLove/ai_platform"
ACCEPTED = "2026-08-23T17:24:55+00:00"


def receipt() -> DispatchReceipt:
    return DispatchReceipt(
        schema_version="1.0.0",
        request_id="req-1",
        control_comment_id=1,
        actor="DonkeyJJLove",
        permission="admin",
        workflow="f009-live-runtime-proof.yml",
        ref="master",
        expected_head=HEAD,
        canonical_inputs_digest="1" * 64,
        accepted_at=ACCEPTED,
        replay_key="2" * 64,
        bridge_implementation_digest="3" * 64,
        trust_decision="ALLOW",
        github_api_result="ACCEPTED_204",
    ).validate()


def run(created_at: str, *, run_id=10, event="workflow_dispatch", branch="master", head=HEAD):
    return {"id": run_id, "created_at": created_at, "event": event, "head_branch": branch, "head_sha": head}


class _TerminalApi:
    def __init__(self, value: dict):
        self.value = value

    def workflow_run(self, run_id: int) -> dict:
        return dict(self.value)


def _group_fixture(run_ids=(10,), *, request_id="group-1"):
    accepted = datetime.fromisoformat(ACCEPTED)
    envelope = GroupChannelEnvelope.build(
        repository=REPO,
        message_id="e003-channel-architecture-test",
        target="architecture",
        expected_master_head=HEAD,
        issued_at=(accepted - timedelta(seconds=10)).isoformat(),
        expires_at=(accepted + timedelta(minutes=30)).isoformat(),
        payload={
            "kind": "E003_CHANNEL_REPLACEMENT_PROOF",
            "no_authority": True,
            "sequence": 1,
            "transport": "actions-artifact",
        },
        now=accepted,
    )
    encoded = encode_envelope(envelope)
    canonical_inputs = json.dumps({"envelope_b64": encoded}, sort_keys=True, separators=(",", ":"))
    control_id = 101
    control_body = "\n".join((
        bridge.PREFIX,
        "workflow=lion-group-channel.yml",
        "ref=master",
        f"expected_head={HEAD}",
        f"request_id={request_id}",
        f"inputs={canonical_inputs}",
    ))
    dispatch = DispatchReceipt(
        schema_version="1.0.0",
        request_id=request_id,
        control_comment_id=control_id,
        actor="DonkeyJJLove",
        permission="admin",
        workflow="lion-group-channel.yml",
        ref="master",
        expected_head=HEAD,
        canonical_inputs_digest=sha256(canonical_inputs.encode("utf-8")).hexdigest(),
        accepted_at=ACCEPTED,
        replay_key="4" * 64,
        bridge_implementation_digest="5" * 64,
        trust_decision="ALLOW",
        github_api_result="ACCEPTED_204",
    ).validate()
    artifacts = {}
    payloads = {}
    for index, run_id in enumerate(run_ids, start=1):
        group_receipt = GroupChannelReceipt.build(
            envelope=envelope,
            emitted_at=(accepted + timedelta(seconds=2 + index)).isoformat(),
            workflow_run_id=run_id,
            workflow_run_attempt=1,
        )
        out = BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            info = zipfile.ZipInfo("lion-group-channel-receipt.json")
            info.external_attr = 0o100600 << 16
            zf.writestr(info, receipt_json(group_receipt))
        data = out.getvalue()
        artifact_id = 1000 + run_id
        payloads[artifact_id] = data
        artifacts[run_id] = [{
            "id": artifact_id,
            "name": f"lion-group-channel-receipt-{run_id}-1",
            "expired": False,
            "size_in_bytes": len(data),
            "digest": "sha256:" + sha256(data).hexdigest(),
        }]
    comments = [{"id": control_id, "body": control_body, "user": {"login": "DonkeyJJLove"}}]
    return dispatch, comments, artifacts, payloads


class _GroupApi:
    def __init__(self, *, dispatch, comments, candidate_ids, artifacts, payloads, invalid_ids=()):
        self.repository = REPO
        self._dispatch = dispatch
        self._comments = comments
        self._candidate_ids = tuple(candidate_ids)
        self._artifacts = artifacts
        self._payloads = payloads
        self._invalid_ids = set(invalid_ids)

    def issue_comments(self, issue_number):
        return list(self._comments)

    def workflow_runs(self, workflow, ref):
        return [run("2026-08-23T17:24:54Z", run_id=value) for value in self._candidate_ids]

    def workflow_run(self, run_id):
        if run_id in self._invalid_ids:
            return {"id": run_id, "event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD,
                    "status": "completed", "conclusion": "failure", "run_attempt": 1}
        return {"id": run_id, "event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD,
                "status": "completed", "conclusion": "success", "run_attempt": 1}

    def run_artifacts(self, run_id):
        return list(self._artifacts.get(run_id, []))

    def download_artifact(self, artifact_id):
        return self._payloads[artifact_id]


class TemporalCompatibilityTests(unittest.TestCase):
    def test_exact_run_created_just_before_receipt_is_accepted(self):
        matches = _matching_runs_compat([run("2026-08-23T17:24:54Z")], receipt())
        self.assertEqual([item["id"] for item in matches], [10])

    def test_run_older_than_bounded_lookback_is_rejected(self):
        accepted = datetime(2026, 8, 23, 17, 24, 55, tzinfo=timezone.utc)
        old = accepted - timedelta(seconds=LEGACY_LOOKBACK_SECONDS + 1)
        matches = _matching_runs_compat([run(old.isoformat())], receipt())
        self.assertEqual(matches, [])

    def test_exact_event_branch_head_remain_mandatory(self):
        runs = [
            run("2026-08-23T17:24:54Z", run_id=1, event="pull_request"),
            run("2026-08-23T17:24:54Z", run_id=2, branch="dev"),
            run("2026-08-23T17:24:54Z", run_id=3, head="b" * 40),
        ]
        self.assertEqual(_matching_runs_compat(runs, receipt()), [])

    def test_multiple_exact_candidates_remain_visible_for_fail_closed_ambiguity(self):
        matches = _matching_runs_compat([
            run("2026-08-23T17:24:54Z", run_id=11),
            run("2026-08-23T17:24:56Z", run_id=12),
        ], receipt())
        self.assertEqual([item["id"] for item in matches], [11, 12])

    def test_group_collision_is_resolved_only_by_exact_artifact_envelope_binding(self):
        dispatch, comments, artifacts, payloads = _group_fixture((10,))
        api = _GroupApi(dispatch=dispatch, comments=comments, candidate_ids=(10, 11),
                        artifacts=artifacts, payloads=payloads)
        selected = _discover_run_compat(api, dispatch, timeout_seconds=0, poll_seconds=0)
        self.assertEqual(selected["id"], 10)

    def test_two_artifact_bound_group_candidates_remain_ambiguous(self):
        dispatch, comments, artifacts, payloads = _group_fixture((10, 11))
        api = _GroupApi(dispatch=dispatch, comments=comments, candidate_ids=(10, 11),
                        artifacts=artifacts, payloads=payloads)
        with self.assertRaisesRegex(RuntimeError, "ambiguous group-channel runs remain"):
            _discover_run_compat(api, dispatch, timeout_seconds=0, poll_seconds=0)

    def test_failed_candidate_does_not_substitute_for_artifact_bound_success(self):
        dispatch, comments, artifacts, payloads = _group_fixture((10,))
        api = _GroupApi(dispatch=dispatch, comments=comments, candidate_ids=(10, 11),
                        artifacts=artifacts, payloads=payloads, invalid_ids=(11,))
        selected = _discover_run_compat(api, dispatch, timeout_seconds=0, poll_seconds=0)
        self.assertEqual(selected["id"], 10)

    def test_failed_terminal_run_exposes_exact_non_success_identity(self):
        api = _TerminalApi({
            "id": 77,
            "event": "workflow_dispatch",
            "head_branch": "master",
            "head_sha": HEAD,
            "status": "completed",
            "conclusion": "failure",
        })
        with self.assertRaisesRegex(
            RuntimeError,
            r"run_id=77 .*head=" + HEAD + r" .*conclusion=failure",
        ):
            _wait_terminal_diagnostic(api, 77, timeout_seconds=0, poll_seconds=0)

    def test_successful_terminal_run_is_semantically_unchanged(self):
        value = {
            "id": 78,
            "event": "workflow_dispatch",
            "head_branch": "master",
            "head_sha": HEAD,
            "status": "completed",
            "conclusion": "success",
        }
        self.assertEqual(
            _wait_terminal_diagnostic(_TerminalApi(value), 78, timeout_seconds=0, poll_seconds=0),
            value,
        )


if __name__ == "__main__":
    unittest.main()

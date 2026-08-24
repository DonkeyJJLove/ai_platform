from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import unittest
import zipfile

from cyber_lion.contracts.actions_dispatch_bridge import CodePerceptionRunObservationReceipt
from cyber_lion.contracts.group_channel import (
    GroupChannelEnvelope,
    GroupChannelReceipt,
    encode_envelope,
    receipt_json,
)
from cyber_lion.enterprise.actions_dispatch_bridge import (
    CODE_PERCEPTION_OBSERVATION_RECEIPT_PREFIX,
    CODE_PERCEPTION_TARGET_PATH,
    CODE_PERCEPTION_TARGET_WORKFLOW_ID,
    CODE_PERCEPTION_WORKFLOW,
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
TREE = "8d321303807c170c8b813788a33bb2a0836aa876"
TARGET_HEAD = "e40abc8231d3c2e54faba0c8bd36969b4a251a56"
TARGET_TREE = TREE
SEMANTIC = "cea9d18d66f0165fb6a39fa55faf8f6369da6964aecd0452dec20637531e5c72"
PROJECTION = "d6a7576735d15b766a1f462ece54e69f73df06cd2b1ea43917b2feaf2bc72adf"
REPO = "DonkeyJJLove/ai_platform"
RUN_ID = 32660000001
TARGET_RUN_ID = 32660000002
TARGET_JOB_ID = 97557904992
OBSERVER_JOB_ID = 97557909999
ARTIFACT_ID = 9500000001
ACCEPTED = "2026-08-23T17:24:55+00:00"


def envelope(*, workflow="f009-live-runtime-proof.yml", ref="master", expected_head=HEAD,
             request_id="req-1", inputs="{}") -> str:
    return "\n".join((PREFIX, f"workflow={workflow}", f"ref={ref}",
        f"expected_head={expected_head}", f"request_id={request_id}", f"inputs={inputs}"))


def observe_envelope(request_id="req-1") -> str:
    return "\n".join((OBSERVE_PREFIX, f"request_id={request_id}"))


def event(body: str, *, issue=144, comment_id=9001, actor="DonkeyJJLove", action="created") -> dict:
    return {"action": action, "issue": {"number": issue},
        "comment": {"id": comment_id, "body": body, "user": {"login": actor}},
        "repository": {"full_name": REPO}}


def dispatch_receipt_comment(request_id="req-1", *, accepted_at=ACCEPTED,
                             expected_head=HEAD, workflow="f009-live-runtime-proof.yml",
                             control_comment_id=8001, canonical_inputs="{}") -> dict:
    body = "\n".join((RECEIPT_PREFIX, f"request_id={request_id}",
        f"control_comment_id={control_comment_id}", "actor=DonkeyJJLove", "permission=admin",
        f"workflow={workflow}", "ref=master", f"expected_head={expected_head}",
        "canonical_inputs_digest=" + sha256(canonical_inputs.encode("utf-8")).hexdigest(),
        f"accepted_at={accepted_at}", "replay_key=" + "1" * 64,
        "bridge_implementation_digest=" + "2" * 64, "trust_decision=ALLOW",
        "github_api_result=ACCEPTED_204"))
    return {"id": 8100, "body": body}


def make_f009_artifact(run_id=RUN_ID, head=HEAD):
    payloads = {
        "runtime-identity.json": b'{"runtime":"ok"}',
        "admission.json": b'{"admission":"ok"}',
        "effect-currentness.json": b'{"current":"ok"}',
        "sandbox-execution-receipt.json": b'{"receipt":"ok"}',
        "independent-observation.json": b'{"observation":"ok"}',
        "reconciliation-receipt.json": b'{"disposition":"MATCHED","anomaly_codes":[]}',
        "replay-denial.json": b'{"replay_denied":true}',
    }
    manifest = {"github_run_id": str(run_id), "github_sha": head,
        "artifact_digests": {name: sha256(data).hexdigest() for name, data in payloads.items()},
        "positive": {"reconciliation": "MATCHED", "effect_executed_once": True,
            "effect_digest": "a" * 64, "independent_effect_digest": "a" * 64},
        "negative_results": {"authority-revoked-after-admission-before-effect": True,
            "policy-changed-before-effect": True, "UNKNOWN-effect-state": True},
        "runtime_can_mint_authority": False, "runtime_has_signing_secret": False,
        "f005_runtime_resumed": False, "production_effect": False}
    payloads["proof-manifest.json"] = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in payloads.items():
            zf.writestr(name, data)
    return out.getvalue()


def make_group_bundle(target="security", request_id="group-1"):
    accepted = datetime.fromisoformat(ACCEPTED)
    issued, expires = accepted - timedelta(seconds=10), accepted + timedelta(minutes=29, seconds=50)
    group_envelope = GroupChannelEnvelope.build(repository=REPO,
        message_id=f"e003-channel-{target}-test", target=target, expected_master_head=HEAD,
        issued_at=issued.isoformat(), expires_at=expires.isoformat(),
        payload={"kind": "E003_CHANNEL_REPLACEMENT_PROOF", "no_authority": True,
                 "sequence": 2, "transport": "actions-artifact"}, now=accepted)
    encoded = encode_envelope(group_envelope)
    canonical_inputs = json.dumps({"envelope_b64": encoded}, sort_keys=True, separators=(",", ":"))
    control_id = 8001
    control = {"id": control_id,
        "body": envelope(workflow="lion-group-channel.yml", request_id=request_id, inputs=canonical_inputs),
        "user": {"login": "DonkeyJJLove"}}
    dispatch = dispatch_receipt_comment(request_id, workflow="lion-group-channel.yml",
        control_comment_id=control_id, canonical_inputs=canonical_inputs)
    group_receipt = GroupChannelReceipt.build(envelope=group_envelope,
        emitted_at="2026-08-23T17:25:02+00:00", workflow_run_id=RUN_ID, workflow_run_attempt=1)
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo("lion-group-channel-receipt.json")
        info.external_attr = 0o100600 << 16
        zf.writestr(info, receipt_json(group_receipt))
    return control, dispatch, group_envelope, group_receipt, out.getvalue()


def code_inputs(*, head=TARGET_HEAD, tree=TARGET_TREE, semantic=SEMANTIC,
                files="352", symbols="4404", edges="29096") -> str:
    return json.dumps({"expected_edges": edges, "expected_files": files, "expected_head": head,
        "expected_symbols": symbols, "expected_tree": tree,
        "expected_tree_semantic_digest": semantic}, sort_keys=True, separators=(",", ":"))


def projection_dict(**overrides) -> dict:
    value = {"run_id": TARGET_RUN_ID, "job_id": TARGET_JOB_ID,
        "workflow_name": "Cyber-Lion Core", "workflow_id": CODE_PERCEPTION_TARGET_WORKFLOW_ID,
        "workflow_path": CODE_PERCEPTION_TARGET_PATH, "event": "push", "branch": "master",
        "head_sha": TARGET_HEAD, "tree_sha": TARGET_TREE, "projection_digest": PROJECTION,
        "tree_semantic_digest": SEMANTIC, "file_count": 352, "symbol_count": 4404,
        "edge_count": 29096, "authority_effect": False}
    value.update(overrides)
    return value


def projection_log(value=None, *, duplicate=False, malformed=False) -> str:
    value = dict(value or projection_dict())
    structured = ("LION_CODE_PERCEPTION_OBSERVATION {bad" if malformed else
        "LION_CODE_PERCEPTION_OBSERVATION " + json.dumps(value, sort_keys=True, separators=(",", ":")))
    summary = ("CODE_PERCEPTION_POST_MERGE_PROJECTION "
        f"run_id={value.get('run_id', TARGET_RUN_ID)} job_id={value.get('job_id', TARGET_JOB_ID)} "
        f"workflow_id={value.get('workflow_id', CODE_PERCEPTION_TARGET_WORKFLOW_ID)} "
        f"workflow_path={value.get('workflow_path', CODE_PERCEPTION_TARGET_PATH)} "
        f"head={value.get('head_sha', TARGET_HEAD)} tree={value.get('tree_sha', TARGET_TREE)} "
        f"digest={value.get('projection_digest', PROJECTION)} "
        f"tree_semantic_digest={value.get('tree_semantic_digest', SEMANTIC)} "
        f"files={value.get('file_count', 352)} symbols={value.get('symbol_count', 4404)} "
        f"edges={value.get('edge_count', 29096)} authority_effect={'true' if value.get('authority_effect') else 'false'}")
    emitted = f"2026-08-24T19:00:00Z {structured}\n2026-08-24T19:00:01Z {summary}\n"
    if duplicate:
        emitted += f"2026-08-24T19:00:02Z {structured}\n2026-08-24T19:00:03Z {summary}\n"
    return emitted


def core_steps(*, failed=None):
    names = ["Set up job", "Parse JSON schemas", "Compile Cyber-Lion package",
             "Run Cyber-Lion tests", "Run Startup Evolution demo", "Complete job"]
    return [{"name": name, "status": "completed",
             "conclusion": "failure" if name == failed else "success"} for name in names]


def target_run(**overrides):
    value = {"id": TARGET_RUN_ID, "name": "Cyber-Lion Core",
        "workflow_id": CODE_PERCEPTION_TARGET_WORKFLOW_ID, "path": CODE_PERCEPTION_TARGET_PATH,
        "event": "push", "head_branch": "master", "head_sha": TARGET_HEAD,
        "status": "completed", "conclusion": "success"}
    value.update(overrides)
    return value


def code_comments(request_id="code-1", *, canonical_inputs=None):
    canonical_inputs = canonical_inputs or code_inputs()
    control_id = 8001
    control = {"id": control_id, "body": envelope(workflow=CODE_PERCEPTION_WORKFLOW,
        request_id=request_id, inputs=canonical_inputs), "user": {"login": "DonkeyJJLove"}}
    dispatch = dispatch_receipt_comment(request_id, workflow=CODE_PERCEPTION_WORKFLOW,
        control_comment_id=control_id, canonical_inputs=canonical_inputs)
    return [control, dispatch]


class FakeApi:
    def __init__(self, *, permission="admin", heads=None, comments=None, dispatch_status=True,
                 workflow_exists=True, runs=None, terminal=None, artifacts=None,
                 artifact_bytes=None, run_jobs_map=None, job_logs_map=None,
                 repository_runs_list=None, commit_payload=None, exact_target=None):
        self.repository, self.token, self.permission = REPO, "test-token", permission
        self.heads, self.comments = list(heads or [HEAD, HEAD]), list(comments or [])
        self.dispatch_status, self.workflow_present = dispatch_status, workflow_exists
        self.patches, self.dispatched, self.posted = [], [], []
        self.runs = list(runs or [{"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master",
            "head_sha": HEAD, "created_at": "2026-08-23T17:25:00Z"}])
        self.terminal = terminal or {"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master",
            "head_sha": HEAD, "status": "completed", "conclusion": "success", "run_attempt": 1,
            "path": ".github/workflows/f009-live-runtime-proof.yml", "actor": {"login": "github-actions[bot]"},
            "triggering_actor": {"login": "github-actions[bot]"}}
        data = artifact_bytes if artifact_bytes is not None else make_f009_artifact()
        self.artifact_bytes = data
        self.artifacts = list(artifacts or [{"id": ARTIFACT_ID, "name": f"f009-live-runtime-proof-{RUN_ID}-1",
            "expired": False, "size_in_bytes": len(data), "digest": "sha256:" + sha256(data).hexdigest(),
            "created_at": "2026-08-23T17:25:03Z"}])
        self.run_jobs_map, self.job_logs_map = dict(run_jobs_map or {}), dict(job_logs_map or {})
        self.repository_runs_list = list(repository_runs_list or [])
        self.commit_payload = commit_payload or {"sha": TARGET_HEAD, "commit": {"tree": {"sha": TARGET_TREE}}}
        self.exact_target = exact_target or target_run()

    def actor_permission(self, actor): return self.permission
    def ref_head(self, ref): return self.heads.pop(0) if self.heads else HEAD
    def workflow_exists(self, workflow, sha): return self.workflow_present
    def issue_comments(self, issue): return list(self.comments)
    def post_issue_comment(self, issue, body):
        self.posted.append((issue, body)); return 7777 + len(self.posted)
    def patch_issue_comment(self, comment_id, body): self.patches.append((comment_id, body))
    def dispatch(self, workflow, ref, inputs):
        if not self.dispatch_status: raise RuntimeError("dispatch failed")
        self.dispatched.append((workflow, ref, inputs))
    def workflow_runs(self, workflow, ref): return list(self.runs)
    def workflow_run(self, run_id): return dict(self.exact_target if run_id == TARGET_RUN_ID else self.terminal)
    def run_jobs(self, run_id): return [dict(item) for item in self.run_jobs_map.get(run_id, [])]
    def job_logs(self, job_id): return self.job_logs_map[job_id]
    def repository_runs(self, *, event, branch, head_sha): return [dict(item) for item in self.repository_runs_list]
    def commit(self, sha): return dict(self.commit_payload)
    def run_artifacts(self, run_id): return list(self.artifacts)
    def download_artifact(self, artifact_id): return self.artifact_bytes


def make_code_api(*, request_id="code-1", structured=None, duplicate=False, malformed=False,
                  repository_runs=None, target_jobs=None, target_exact=None, commit_payload=None,
                  observer_terminal=None, observer_jobs=None):
    comments = code_comments(request_id)
    observer_terminal = observer_terminal or {"id": RUN_ID, "event": "workflow_dispatch",
        "head_branch": "master", "head_sha": HEAD, "status": "completed", "conclusion": "success",
        "run_attempt": 1, "path": ".github/workflows/lion-code-perception-observation.yml"}
    observer_jobs = observer_jobs or [{"id": OBSERVER_JOB_ID, "name": "observe", "status": "completed",
        "conclusion": "success", "steps": []}]
    if target_jobs is None:
        target_jobs = [{"id": TARGET_JOB_ID, "name": "core", "status": "completed", "conclusion": "success",
            "steps": core_steps()}, {"id": TARGET_JOB_ID + 1, "name": "Cyber-Lion Merge Authority Admission",
            "status": "completed", "conclusion": "success", "steps": []}]
    return FakeApi(comments=comments, terminal=observer_terminal,
        run_jobs_map={RUN_ID: observer_jobs, TARGET_RUN_ID: target_jobs},
        job_logs_map={OBSERVER_JOB_ID: projection_log(structured, duplicate=duplicate, malformed=malformed)},
        repository_runs_list=[target_run()] if repository_runs is None else repository_runs,
        commit_payload=commit_payload, exact_target=target_exact)


class DispatchBridgeRegressionTests(unittest.TestCase):
    def test_policy_is_exactly_three_workflows_and_master_only(self):
        self.assertEqual(DEFAULT_POLICY.allowed_workflows,
            ("f009-live-runtime-proof.yml", "lion-group-channel.yml", "lion-code-perception-observation.yml"))
        self.assertEqual(DEFAULT_POLICY.allowed_refs, ("master",))
        self.assertEqual(set(DEFAULT_POLICY.input_keys_for(CODE_PERCEPTION_WORKFLOW)),
            {"expected_head", "expected_tree", "expected_tree_semantic_digest",
             "expected_files", "expected_symbols", "expected_edges"})

    def test_code_perception_dispatch_requires_exact_input_set(self):
        good = envelope(workflow=CODE_PERCEPTION_WORKFLOW, inputs=code_inputs())
        parsed = parse_envelope(good, repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")
        self.assertEqual(set(parsed.inputs()), set(DEFAULT_POLICY.input_keys_for(CODE_PERCEPTION_WORKFLOW)))
        missing = json.loads(code_inputs()); missing.pop("expected_edges")
        with self.assertRaises(ValueError):
            parse_envelope(envelope(workflow=CODE_PERCEPTION_WORKFLOW,
                inputs=json.dumps(missing, sort_keys=True, separators=(",", ":"))),
                repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")
        extra = json.loads(code_inputs()); extra["command"] = "arbitrary"
        with self.assertRaises(ValueError):
            parse_envelope(envelope(workflow=CODE_PERCEPTION_WORKFLOW,
                inputs=json.dumps(extra, sort_keys=True, separators=(",", ":"))),
                repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")

    def test_exact_f009_dispatch_and_observation_still_work(self):
        api = FakeApi(); receipt = execute(event(envelope()), api)
        self.assertEqual(receipt.workflow, "f009-live-runtime-proof.yml"); self.assertEqual(len(api.dispatched), 1)
        observer = FakeApi(comments=[dispatch_receipt_comment()])
        result = observe(event(observe_envelope(), comment_id=9002), observer,
                         discovery_timeout=0, terminal_timeout=0, poll_seconds=0)
        self.assertEqual(result.observation_result, "OBSERVED_VERIFIED")
        self.assertEqual(result.positive_reconciliation, "MATCHED")
        self.assertTrue(observer.posted[-1][1].startswith(OBSERVATION_RECEIPT_PREFIX))

    def test_group_channel_regression_remains_evidence_only(self):
        control, dispatch, _, _, data = make_group_bundle()
        api = FakeApi(comments=[control, dispatch], artifact_bytes=data,
            terminal={"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD,
                "status": "completed", "conclusion": "success", "run_attempt": 1,
                "path": ".github/workflows/lion-group-channel.yml", "actor": {"login": "github-actions[bot]"},
                "triggering_actor": {"login": "github-actions[bot]"}},
            artifacts=[{"id": ARTIFACT_ID, "name": f"lion-group-channel-receipt-{RUN_ID}-1", "expired": False,
                "size_in_bytes": len(data), "digest": "sha256:" + sha256(data).hexdigest(),
                "created_at": "2026-08-23T17:25:03Z"}])
        result = observe(event(observe_envelope("group-1"), comment_id=9002), api,
                         discovery_timeout=0, terminal_timeout=0, poll_seconds=0)
        self.assertFalse(result.authority_effect); self.assertFalse(result.repository_effect)
        self.assertTrue(api.posted[-1][1].startswith(GROUP_OBSERVATION_RECEIPT_PREFIX))

    def test_observation_envelope_is_exact(self):
        parsed = parse_observation_envelope(observe_envelope("x"), repository=REPO, issue_number=144,
                                            comment_id=1, actor="DonkeyJJLove")
        self.assertEqual(parsed.request_id, "x")
        for bad in ("LION-OBSERVE v1", "LION-OBSERVE v1\nrequest_id=x\nextra=y"):
            with self.assertRaises(ValueError):
                parse_observation_envelope(bad, repository=REPO, issue_number=144, comment_id=1, actor="DonkeyJJLove")

    def test_control_workflow_effect_surface_is_not_widened(self):
        text = Path(".github/workflows/lion-actions-dispatch-bridge.yml").read_text(encoding="utf-8")
        self.assertIn("contents: read", text); self.assertIn("actions: write", text); self.assertIn("issues: write", text)
        self.assertNotIn("contents: write", text); self.assertNotIn("pull_request_target", text)


class CodePerceptionObservationTests(unittest.TestCase):
    def run_observe(self, api, request_id="code-1"):
        return observe(event(observe_envelope(request_id), comment_id=9002), api,
                       discovery_timeout=0, terminal_timeout=0, poll_seconds=0)

    def test_exact_positive_observer_workflow(self):
        api = make_code_api(); result = self.run_observe(api)
        self.assertEqual(result.target_run_id, TARGET_RUN_ID); self.assertEqual(result.target_job_id, TARGET_JOB_ID)
        self.assertEqual(result.target_workflow_id, CODE_PERCEPTION_TARGET_WORKFLOW_ID)
        self.assertEqual(result.target_workflow_path, CODE_PERCEPTION_TARGET_PATH)
        self.assertEqual(result.target_head_sha, TARGET_HEAD); self.assertEqual(result.target_tree_sha, TARGET_TREE)
        self.assertEqual(result.tree_semantic_digest, SEMANTIC)
        self.assertEqual((result.file_count, result.symbol_count, result.edge_count), (352, 4404, 29096))
        self.assertFalse(result.authority_effect); self.assertFalse(result.repository_effect)
        self.assertTrue(api.posted[-1][1].startswith(CODE_PERCEPTION_OBSERVATION_RECEIPT_PREFIX))

    def test_wrong_workflow_id_and_path_are_rejected(self):
        for override in ({"workflow_id": 999}, {"workflow_path": ".github/workflows/impostor.yml"}):
            with self.subTest(override=override):
                with self.assertRaises(RuntimeError): self.run_observe(make_code_api(structured=projection_dict(**override)))

    def test_pr_target_is_rejected(self):
        with self.assertRaises(RuntimeError): self.run_observe(make_code_api(repository_runs=[target_run(event="pull_request")]))

    def test_wrong_target_head_is_rejected(self):
        with self.assertRaises(RuntimeError): self.run_observe(make_code_api(structured=projection_dict(head_sha="a" * 40)))

    def test_wrong_target_tree_is_rejected(self):
        with self.assertRaises(RuntimeError): self.run_observe(make_code_api(commit_payload={"sha": TARGET_HEAD, "commit": {"tree": {"sha": "a" * 40}}}))

    def test_duplicate_target_runs_are_rejected(self):
        with self.assertRaises(RuntimeError): self.run_observe(make_code_api(repository_runs=[target_run(), target_run(id=TARGET_RUN_ID + 1)]))

    def test_zero_target_runs_are_rejected(self):
        with self.assertRaises(RuntimeError): self.run_observe(make_code_api(repository_runs=[]))

    def test_failed_target_run_is_rejected(self):
        with self.assertRaises(RuntimeError): self.run_observe(make_code_api(repository_runs=[target_run(conclusion="failure")]))

    def test_missing_core_job_is_rejected(self):
        jobs = [{"id": TARGET_JOB_ID + 1, "name": "Cyber-Lion Merge Authority Admission", "status": "completed", "conclusion": "success", "steps": []}]
        with self.assertRaises(RuntimeError): self.run_observe(make_code_api(target_jobs=jobs))

    def test_failed_required_core_step_is_rejected(self):
        jobs = [{"id": TARGET_JOB_ID, "name": "core", "status": "completed", "conclusion": "success", "steps": core_steps(failed="Run Cyber-Lion tests")}]
        with self.assertRaises(RuntimeError): self.run_observe(make_code_api(target_jobs=jobs))

    def test_malformed_observer_structured_output_is_rejected(self):
        with self.assertRaises(RuntimeError): self.run_observe(make_code_api(malformed=True))

    def test_duplicate_projection_receipt_is_rejected(self):
        with self.assertRaises(RuntimeError): self.run_observe(make_code_api(duplicate=True))

    def test_authority_effect_true_is_rejected(self):
        with self.assertRaises(RuntimeError): self.run_observe(make_code_api(structured=projection_dict(authority_effect=True)))

    def test_repository_effect_true_is_rejected_by_receipt_contract(self):
        good = CodePerceptionRunObservationReceipt(schema_version="1.0.0", request_id="code-1",
            observation_comment_id=1, control_comment_id=2, actor="DonkeyJJLove", permission="admin",
            workflow=CODE_PERCEPTION_WORKFLOW, ref="master", expected_head=HEAD, dispatch_accepted_at=ACCEPTED,
            observer_run_id=RUN_ID, observer_run_attempt=1, observer_status="completed", observer_conclusion="success",
            target_workflow_name="Cyber-Lion Core", target_workflow_id=CODE_PERCEPTION_TARGET_WORKFLOW_ID,
            target_workflow_path=CODE_PERCEPTION_TARGET_PATH, target_event="push", target_branch="master",
            target_head_sha=TARGET_HEAD, target_tree_sha=TARGET_TREE, target_run_id=TARGET_RUN_ID,
            target_job_id=TARGET_JOB_ID, projection_digest=PROJECTION, tree_semantic_digest=SEMANTIC,
            file_count=352, symbol_count=4404, edge_count=29096, authority_effect=False, repository_effect=False,
            bridge_implementation_digest="f" * 64, trust_decision="ALLOW", observation_result="OBSERVED_VERIFIED").validate()
        with self.assertRaises(ValueError): replace(good, repository_effect=True).validate()

    def test_duplicate_successful_observation_ledger_is_rejected(self):
        api = make_code_api(); successful = "\n".join((CODE_PERCEPTION_OBSERVATION_RECEIPT_PREFIX, "request_id=code-1"))
        api.comments.extend([{"id": 9003, "body": successful}, {"id": 9004, "body": successful}])
        with self.assertRaises(RuntimeError): self.run_observe(api)

    def test_observer_workflow_path_substitution_is_rejected(self):
        terminal = {"id": RUN_ID, "event": "workflow_dispatch", "head_branch": "master", "head_sha": HEAD,
            "status": "completed", "conclusion": "success", "run_attempt": 1, "path": ".github/workflows/impostor.yml"}
        with self.assertRaises(RuntimeError): self.run_observe(make_code_api(observer_terminal=terminal))

    def test_target_exact_fetch_is_independently_rechecked(self):
        with self.assertRaises(RuntimeError): self.run_observe(make_code_api(target_exact=target_run(head_sha="b" * 40)))


class GitHubApiSurfaceTests(unittest.TestCase):
    def test_api_origin_is_strict(self):
        with self.assertRaises(RuntimeError): GitHubApi(REPO, "x", "http://api.github.com")
        with self.assertRaises(RuntimeError): GitHubApi(REPO, "x", "https://evil.example")


if __name__ == "__main__":
    unittest.main()

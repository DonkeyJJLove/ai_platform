"""Repository-native bounded GitHub Actions dispatch and observation bridge.

Dispatch is exact-head and replay bound. Observation is workflow-aware: F009 retains
its proof-manifest semantics, ``lion-group-channel.yml`` retains its evidence-only
artifact semantics, and code-perception observation has a separate evidence-only
receipt. Issue comments and receipts are evidence, never authority.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import argparse
import json
import os
from pathlib import Path
import re
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from cyber_lion.contracts.actions_dispatch_bridge import (
    CodePerceptionRunObservationReceipt,
    DispatchPolicy,
    DispatchReceipt,
    DispatchRequest,
    GroupChannelRunObservationReceipt,
    ObservationRequest,
    RunObservationReceipt,
    canonical_json,
)
from cyber_lion.contracts.group_channel import (
    GroupChannelContractError,
    GroupChannelReceipt,
    canonical_json as group_canonical_json,
    decode_envelope,
    strict_json_loads,
)

CONTROL_ISSUE = 144
PREFIX = "LION-DISPATCH v1"
OBSERVE_PREFIX = "LION-OBSERVE v1"
CLAIM_PREFIX = "LION-DISPATCH-CLAIM v1"
RECEIPT_PREFIX = "LION-DISPATCH-RECEIPT v1"
OBSERVATION_RECEIPT_PREFIX = "LION-RUN-OBSERVATION-RECEIPT v1"
GROUP_OBSERVATION_RECEIPT_PREFIX = "LION-GROUP-CHANNEL-OBSERVATION-RECEIPT v1"
CODE_PERCEPTION_OBSERVATION_RECEIPT_PREFIX = "LION-CODE-PERCEPTION-OBSERVATION-RECEIPT v1"

CODE_PERCEPTION_WORKFLOW = "lion-code-perception-observation.yml"
CODE_PERCEPTION_TARGET_NAME = "Cyber-Lion Core"
CODE_PERCEPTION_TARGET_WORKFLOW_ID = 337046823
CODE_PERCEPTION_TARGET_PATH = ".github/workflows/cyber-lion-contracts.yml"
CODE_PERCEPTION_TARGET_BRANCH = "master"

_CODE_INPUT_KEYS = (
    "expected_head",
    "expected_tree",
    "expected_tree_semantic_digest",
    "expected_files",
    "expected_symbols",
    "expected_edges",
)

DEFAULT_POLICY = DispatchPolicy(
    control_issue=CONTROL_ISSUE,
    allowed_workflows=(
        "f009-live-runtime-proof.yml",
        "lion-group-channel.yml",
        CODE_PERCEPTION_WORKFLOW,
    ),
    allowed_refs=("master",),
    allowed_inputs=(
        ("f009-live-runtime-proof.yml", ()),
        ("lion-group-channel.yml", ("envelope_b64",)),
        (CODE_PERCEPTION_WORKFLOW, _CODE_INPUT_KEYS),
    ),
).validate()

_FIELD_ORDER = ("workflow", "ref", "expected_head", "request_id", "inputs")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_F009_FILES = {
    "runtime-identity.json",
    "admission.json",
    "effect-currentness.json",
    "sandbox-execution-receipt.json",
    "independent-observation.json",
    "reconciliation-receipt.json",
    "replay-denial.json",
    "proof-manifest.json",
}
_GROUP_RECEIPT_FILE = "lion-group-channel-receipt.json"
_EXPECTED_GROUP_RUN_ACTOR = "github-actions[bot]"
_TIMESTAMP_TOLERANCE = timedelta(seconds=2)
_CODE_STRUCTURED_MARKER = "LION_CODE_PERCEPTION_OBSERVATION "
_CODE_SUMMARY_RE = re.compile(
    r"CODE_PERCEPTION_POST_MERGE_PROJECTION\s+"
    r"run_id=(?P<run_id>\d+)\s+"
    r"job_id=(?P<job_id>\d+)\s+"
    r"workflow_id=(?P<workflow_id>\d+)\s+"
    r"workflow_path=(?P<workflow_path>\S+)\s+"
    r"head=(?P<head>[0-9a-f]{40})\s+"
    r"tree=(?P<tree>[0-9a-f]{40})\s+"
    r"digest=(?P<digest>[0-9a-f]{64})\s+"
    r"tree_semantic_digest=(?P<tree_semantic_digest>[0-9a-f]{64})\s+"
    r"files=(?P<files>\d+)\s+"
    r"symbols=(?P<symbols>\d+)\s+"
    r"edges=(?P<edges>\d+)\s+"
    r"authority_effect=(?P<authority_effect>true|false)"
)
_CODE_STRUCTURED_KEYS = {
    "run_id", "job_id", "workflow_name", "workflow_id", "workflow_path",
    "event", "branch", "head_sha", "tree_sha", "projection_digest",
    "tree_semantic_digest", "file_count", "symbol_count", "edge_count",
    "authority_effect",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _implementation_digest() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RuntimeError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _kv_body(prefix: str, body: str) -> dict[str, str] | None:
    lines = body.splitlines()
    if not lines or lines[0] != prefix:
        return None
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if "=" not in line:
            raise RuntimeError(f"malformed {prefix} ledger entry")
        key, value = line.split("=", 1)
        if key in fields:
            raise RuntimeError(f"duplicate {prefix} field")
        fields[key] = value
    return fields


def parse_envelope(body: str, *, repository: str, issue_number: int, comment_id: int,
                   actor: str, policy: DispatchPolicy = DEFAULT_POLICY) -> DispatchRequest:
    lines = body.splitlines()
    if len(lines) != 1 + len(_FIELD_ORDER) or lines[0] != PREFIX:
        raise ValueError("malformed LION-DISPATCH envelope")
    values: dict[str, str] = {}
    for expected, line in zip(_FIELD_ORDER, lines[1:]):
        field_prefix = expected + "="
        if not line.startswith(field_prefix):
            raise ValueError(f"missing or reordered field: {expected}")
        values[expected] = line[len(field_prefix):]
    if not _REQUEST_ID.fullmatch(values["request_id"]):
        raise ValueError("invalid request id")
    try:
        inputs_obj = json.loads(values["inputs"])
    except json.JSONDecodeError as exc:
        raise ValueError("malformed JSON inputs") from exc
    if not isinstance(inputs_obj, dict):
        raise ValueError("inputs must be JSON object")
    canonical_inputs = canonical_json(inputs_obj).decode("utf-8")
    if canonical_inputs != values["inputs"]:
        raise ValueError("inputs must be canonical JSON")
    return DispatchRequest(
        schema_version="1", repository=repository, issue_number=issue_number,
        comment_id=comment_id, actor=actor, request_id=values["request_id"],
        workflow=values["workflow"], ref=values["ref"],
        expected_head=values["expected_head"], canonical_inputs=canonical_inputs,
    ).validate(policy)


def parse_observation_envelope(body: str, *, repository: str, issue_number: int,
                               comment_id: int, actor: str,
                               policy: DispatchPolicy = DEFAULT_POLICY) -> ObservationRequest:
    lines = body.splitlines()
    if len(lines) != 2 or lines[0] != OBSERVE_PREFIX or not lines[1].startswith("request_id="):
        raise ValueError("malformed LION-OBSERVE envelope")
    return ObservationRequest(
        schema_version="1", repository=repository, issue_number=issue_number,
        comment_id=comment_id, actor=actor,
        request_id=lines[1].removeprefix("request_id="),
    ).validate(policy)


class GitHubApi:
    def __init__(self, repository: str, token: str, api_url: str = "https://api.github.com") -> None:
        parsed = urllib.parse.urlsplit(api_url)
        if (parsed.scheme != "https" or parsed.hostname != "api.github.com"
                or parsed.port not in (None, 443) or parsed.username is not None
                or parsed.password is not None or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment):
            raise RuntimeError("GitHub API origin must be canonical HTTPS api.github.com")
        self.repository = repository
        self.token = token
        self.api_url = "https://api.github.com"
        from cyber_lion.enterprise.actions_control_ledger import ActionsControlLedgerBoundary
        self._control_ledger = ActionsControlLedgerBoundary(repository, token)

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "lion-actions-dispatch-bridge/5"}

    def _request(self, method: str, path: str, body: object | None = None) -> tuple[int, object | None]:
        if method != "GET" or body is not None:
            raise RuntimeError("generic GitHub transport is read-only")
        if not path.startswith("/") or ".." in path or "\\" in path:
            raise RuntimeError("unsafe GitHub API path")
        req = urllib.request.Request(self.api_url + path, data=None, method="GET", headers=self._headers())
        try:
            with urllib.request.build_opener(self._NoRedirect()).open(req, timeout=20) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"GitHub API GET {path} failed: {exc.code}: {detail}") from exc

    def actor_permission(self, actor: str) -> str:
        status, value = self._request("GET", f"/repos/{self.repository}/collaborators/{urllib.parse.quote(actor, safe='')}/permission")
        if status != 200 or not isinstance(value, dict) or not isinstance(value.get("permission"), str):
            raise RuntimeError("unable to resolve actor permission")
        return value["permission"]

    def ref_head(self, ref: str) -> str:
        status, value = self._request("GET", f"/repos/{self.repository}/git/ref/heads/{urllib.parse.quote(ref, safe='')}")
        try:
            sha = value["object"]["sha"]
        except Exception as exc:
            raise RuntimeError("unable to resolve ref head") from exc
        if status != 200 or not isinstance(sha, str):
            raise RuntimeError("unable to resolve ref head")
        return sha.lower()

    def workflow_exists(self, workflow: str, sha: str) -> bool:
        path = f"/repos/{self.repository}/contents/.github/workflows/{urllib.parse.quote(workflow, safe='')}?ref={urllib.parse.quote(sha, safe='')}"
        try:
            status, _ = self._request("GET", path)
        except RuntimeError:
            return False
        return status == 200

    def issue_comments(self, issue_number: int) -> list[dict]:
        result = []
        for page in range(1, 101):
            status, value = self._request("GET", f"/repos/{self.repository}/issues/{issue_number}/comments?per_page=100&page={page}")
            if status != 200 or not isinstance(value, list):
                raise RuntimeError("unable to read replay ledger")
            result.extend(v for v in value if isinstance(v, dict))
            if len(value) < 100:
                return result
        raise RuntimeError("replay ledger pagination limit exceeded")

    def post_issue_comment(self, issue_number: int, body: str) -> int:
        return self._control_ledger.create(issue_number, body)

    def patch_issue_comment(self, comment_id: int, body: str) -> None:
        self._control_ledger.update(comment_id, body)

    def dispatch(self, workflow: str, ref: str, inputs: dict[str, object]) -> None:
        if workflow not in DEFAULT_POLICY.allowed_workflows or ref not in DEFAULT_POLICY.allowed_refs:
            raise RuntimeError("workflow dispatch target not allowlisted")
        if workflow not in dict(DEFAULT_POLICY.allowed_inputs):
            raise RuntimeError("workflow dispatch input policy unavailable")
        expected_keys = set(dict(DEFAULT_POLICY.allowed_inputs)[workflow])
        if set(inputs) != expected_keys:
            raise RuntimeError("workflow dispatch input set mismatch")
        path = f"/repos/{self.repository}/actions/workflows/{urllib.parse.quote(workflow, safe='')}/dispatches"
        payload = canonical_json({"ref": ref, "inputs": inputs})
        headers = self._headers(); headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.api_url + path, data=payload, method="POST", headers=headers)
        try:
            with urllib.request.build_opener(self._NoRedirect()).open(req, timeout=20) as response:
                if response.status != 204:
                    raise RuntimeError(f"workflow dispatch not accepted: {response.status}")
                response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"workflow dispatch failed: {exc.code}: {detail}") from exc

    def workflow_runs(self, workflow: str, ref: str) -> list[dict]:
        result = []
        for page in range(1, 11):
            path = f"/repos/{self.repository}/actions/workflows/{urllib.parse.quote(workflow, safe='')}/runs?event=workflow_dispatch&branch={urllib.parse.quote(ref, safe='')}&per_page=100&page={page}"
            status, value = self._request("GET", path)
            if status != 200 or not isinstance(value, dict) or not isinstance(value.get("workflow_runs"), list):
                raise RuntimeError("unable to list target workflow runs")
            batch = [v for v in value["workflow_runs"] if isinstance(v, dict)]
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise RuntimeError("workflow run pagination limit exceeded")

    def repository_runs(self, *, event: str, branch: str, head_sha: str) -> list[dict]:
        if event != "push" or branch != "master" or _HEX40.fullmatch(head_sha) is None:
            raise RuntimeError("unsafe repository run query")
        result = []
        for page in range(1, 11):
            query = urllib.parse.urlencode({"event": event, "branch": branch, "head_sha": head_sha, "per_page": "100", "page": str(page)})
            status, value = self._request("GET", f"/repos/{self.repository}/actions/runs?{query}")
            if status != 200 or not isinstance(value, dict) or not isinstance(value.get("workflow_runs"), list):
                raise RuntimeError("unable to list repository workflow runs")
            batch = [v for v in value["workflow_runs"] if isinstance(v, dict)]
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise RuntimeError("repository run pagination limit exceeded")

    def workflow_run(self, run_id: int) -> dict:
        status, value = self._request("GET", f"/repos/{self.repository}/actions/runs/{run_id}")
        if status != 200 or not isinstance(value, dict):
            raise RuntimeError("unable to resolve workflow run")
        return value

    def run_jobs(self, run_id: int) -> list[dict]:
        result = []
        for page in range(1, 11):
            status, value = self._request("GET", f"/repos/{self.repository}/actions/runs/{run_id}/jobs?per_page=100&page={page}")
            if status != 200 or not isinstance(value, dict) or not isinstance(value.get("jobs"), list):
                raise RuntimeError("unable to enumerate workflow jobs")
            batch = [v for v in value["jobs"] if isinstance(v, dict)]
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise RuntimeError("workflow job pagination limit exceeded")

    def job_logs(self, job_id: int) -> str:
        if job_id <= 0:
            raise RuntimeError("job id invalid")
        from cyber_lion.enterprise.code_perception_observation import _github_get_text
        return _github_get_text(f"https://api.github.com/repos/{self.repository}/actions/jobs/{job_id}/logs", self.token)

    def commit(self, sha: str) -> dict:
        if _HEX40.fullmatch(sha) is None:
            raise RuntimeError("commit sha invalid")
        status, value = self._request("GET", f"/repos/{self.repository}/commits/{sha}")
        if status != 200 or not isinstance(value, dict):
            raise RuntimeError("unable to resolve commit")
        return value

    def run_artifacts(self, run_id: int) -> list[dict]:
        status, value = self._request("GET", f"/repos/{self.repository}/actions/runs/{run_id}/artifacts?per_page=100")
        if status != 200 or not isinstance(value, dict) or not isinstance(value.get("artifacts"), list):
            raise RuntimeError("unable to enumerate run artifacts")
        return [v for v in value["artifacts"] if isinstance(v, dict)]

    def download_artifact(self, artifact_id: int) -> bytes:
        from cyber_lion.enterprise.actions_dispatch_temporal_compat import _download_artifact_compat
        return _download_artifact_compat(self, artifact_id)


def _ledger_match(comments: list[dict], request: DispatchRequest) -> str | None:
    for item in comments:
        body = item.get("body")
        if not isinstance(body, str):
            continue
        if not (body.startswith(CLAIM_PREFIX) or body.startswith(RECEIPT_PREFIX)):
            continue
        fields = _kv_body(body.splitlines()[0], body)
        if fields and fields.get("request_id") == request.request_id:
            return "request-id-already-consumed"
        if fields and fields.get("replay_key") == request.replay_key():
            return "replay-key-already-consumed"
    return None


def _claim_body(request: DispatchRequest, permission: str) -> str:
    return "\n".join((CLAIM_PREFIX, f"request_id={request.request_id}", f"replay_key={request.replay_key()}",
        f"payload_digest={request.payload_digest()}", f"comment_id={request.comment_id}", f"actor={request.actor}",
        f"permission={permission}", f"workflow={request.workflow}", f"ref={request.ref}",
        f"expected_head={request.expected_head}", "state=CLAIMED_BEFORE_EFFECT"))


def _receipt_body(receipt: DispatchReceipt) -> str:
    values = asdict(receipt)
    keys = ("request_id", "control_comment_id", "actor", "permission", "workflow", "ref", "expected_head", "canonical_inputs_digest", "accepted_at", "replay_key", "bridge_implementation_digest", "trust_decision", "github_api_result")
    return "\n".join([RECEIPT_PREFIX, *(f"{key}={values[key]}" for key in keys)])


def _observation_receipt_body(receipt: RunObservationReceipt) -> str:
    values = asdict(receipt)
    keys = ("request_id", "observation_comment_id", "actor", "permission", "workflow", "ref", "expected_head", "dispatch_accepted_at", "run_id", "run_attempt", "event", "status", "conclusion", "artifact_id", "artifact_name", "artifact_digest", "artifact_size", "proof_manifest_digest", "positive_reconciliation", "bridge_implementation_digest", "trust_decision", "observation_result")
    return "\n".join([OBSERVATION_RECEIPT_PREFIX, *(f"{key}={values[key]}" for key in keys)])


def _group_observation_receipt_body(receipt: GroupChannelRunObservationReceipt) -> str:
    values = asdict(receipt)
    keys = ("request_id", "observation_comment_id", "control_comment_id", "actor", "permission", "workflow", "ref", "expected_head", "dispatch_accepted_at", "run_id", "run_attempt", "event", "status", "conclusion", "run_actor", "triggering_actor", "artifact_id", "artifact_name", "artifact_digest", "artifact_size", "message_id", "target", "envelope_digest", "payload_digest", "group_channel_receipt_digest", "emitted_at", "state", "authority_effect", "repository_effect", "bridge_implementation_digest", "trust_decision", "observation_result")
    return "\n".join([GROUP_OBSERVATION_RECEIPT_PREFIX, *(f"{key}={values[key]}" for key in keys)])


def _code_perception_observation_receipt_body(receipt: CodePerceptionRunObservationReceipt) -> str:
    values = asdict(receipt)
    keys = ("request_id", "observation_comment_id", "control_comment_id", "actor", "permission", "workflow", "ref", "expected_head", "dispatch_accepted_at", "observer_run_id", "observer_run_attempt", "observer_status", "observer_conclusion", "target_workflow_name", "target_workflow_id", "target_workflow_path", "target_event", "target_branch", "target_head_sha", "target_tree_sha", "target_run_id", "target_job_id", "projection_digest", "tree_semantic_digest", "file_count", "symbol_count", "edge_count", "authority_effect", "repository_effect", "bridge_implementation_digest", "trust_decision", "observation_result")
    return "\n".join([CODE_PERCEPTION_OBSERVATION_RECEIPT_PREFIX, *(f"{key}={values[key]}" for key in keys)])


def _event_parts(event: dict, api: GitHubApi, policy: DispatchPolicy) -> tuple[int, int, str, str, str]:
    if event.get("action") != "created":
        raise RuntimeError("only newly created issue comments are accepted")
    issue, comment, repository_obj = event.get("issue"), event.get("comment"), event.get("repository")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(repository_obj, dict):
        raise RuntimeError("malformed issue_comment event")
    issue_number, comment_id, body = issue.get("number"), comment.get("id"), comment.get("body")
    actor_obj = comment.get("user")
    actor = actor_obj.get("login") if isinstance(actor_obj, dict) else None
    full_name = repository_obj.get("full_name")
    if full_name != api.repository:
        raise RuntimeError("repository binding mismatch")
    if issue_number != policy.control_issue:
        raise RuntimeError("wrong control issue")
    if not isinstance(comment_id, int) or not isinstance(body, str) or not isinstance(actor, str):
        raise RuntimeError("malformed control comment")
    return issue_number, comment_id, body, actor, full_name


def execute(event: dict, api: GitHubApi, *, policy: DispatchPolicy = DEFAULT_POLICY) -> DispatchReceipt:
    issue_number, comment_id, body, actor, _ = _event_parts(event, api, policy)
    request = parse_envelope(body, repository=api.repository, issue_number=issue_number, comment_id=comment_id, actor=actor, policy=policy)
    permission = api.actor_permission(actor)
    if permission not in policy.trusted_permissions:
        raise RuntimeError("untrusted actor permission")
    if api.ref_head(request.ref) != request.expected_head:
        raise RuntimeError("stale expected head")
    if not api.workflow_exists(request.workflow, request.expected_head):
        raise RuntimeError("allowlisted workflow missing at expected head")
    replay = _ledger_match(api.issue_comments(policy.control_issue), request)
    if replay:
        raise RuntimeError(replay)
    claim_id = api.post_issue_comment(policy.control_issue, _claim_body(request, permission))
    if api.ref_head(request.ref) != request.expected_head:
        api.patch_issue_comment(claim_id, _claim_body(request, permission) + "\nstate=DENIED_HEAD_MOVED_BEFORE_DISPATCH")
        raise RuntimeError("ref moved before dispatch")
    try:
        api.dispatch(request.workflow, request.ref, dict(request.inputs()))
    except Exception:
        api.patch_issue_comment(claim_id, _claim_body(request, permission) + "\nstate=DISPATCH_API_FAILED_REQUEST_CONSUMED")
        raise
    receipt = DispatchReceipt(schema_version="1.0.0", request_id=request.request_id,
        control_comment_id=request.comment_id, actor=request.actor, permission=permission,
        workflow=request.workflow, ref=request.ref, expected_head=request.expected_head,
        canonical_inputs_digest=sha256(request.canonical_inputs.encode("utf-8")).hexdigest(),
        accepted_at=_now(), replay_key=request.replay_key(), bridge_implementation_digest=_implementation_digest(),
        trust_decision="ALLOW", github_api_result="ACCEPTED_204").validate()
    api.patch_issue_comment(claim_id, _receipt_body(receipt))
    return receipt


def _dispatch_receipt_for(comments: list[dict], request_id: str, policy: DispatchPolicy) -> DispatchReceipt:
    found = []
    for item in comments:
        body = item.get("body")
        if not isinstance(body, str) or not body.startswith(RECEIPT_PREFIX):
            continue
        fields = _kv_body(RECEIPT_PREFIX, body)
        if fields is None or fields.get("request_id") != request_id:
            continue
        try:
            receipt = DispatchReceipt(schema_version="1.0.0", request_id=fields["request_id"],
                control_comment_id=int(fields["control_comment_id"]), actor=fields["actor"], permission=fields["permission"],
                workflow=fields["workflow"], ref=fields["ref"], expected_head=fields["expected_head"],
                canonical_inputs_digest=fields["canonical_inputs_digest"], accepted_at=fields["accepted_at"],
                replay_key=fields["replay_key"], bridge_implementation_digest=fields["bridge_implementation_digest"],
                trust_decision=fields["trust_decision"], github_api_result=fields["github_api_result"]).validate()
        except (KeyError, ValueError) as exc:
            raise RuntimeError("malformed bound dispatch receipt") from exc
        if receipt.workflow not in policy.allowed_workflows or receipt.ref not in policy.allowed_refs:
            raise RuntimeError("dispatch receipt target is no longer allowlisted")
        found.append(receipt)
    if len(found) != 1:
        raise RuntimeError("dispatch receipt binding is missing or ambiguous")
    return found[0]


def _already_observed(comments: list[dict], request_id: str) -> bool:
    matches = 0
    for item in comments:
        body = item.get("body")
        if not isinstance(body, str):
            continue
        for prefix in (OBSERVATION_RECEIPT_PREFIX, GROUP_OBSERVATION_RECEIPT_PREFIX, CODE_PERCEPTION_OBSERVATION_RECEIPT_PREFIX):
            if body.startswith(prefix):
                fields = _kv_body(prefix, body)
                if fields and fields.get("request_id") == request_id:
                    matches += 1
    if matches > 1:
        raise RuntimeError("observation ledger is ambiguous")
    return matches == 1


def _matching_runs(runs: list[dict], receipt: DispatchReceipt) -> list[dict]:
    accepted = _parse_time(receipt.accepted_at)
    matches = []
    for run in runs:
        try:
            created, run_id = _parse_time(str(run["created_at"])), int(run["id"])
        except (KeyError, ValueError, TypeError):
            continue
        if (run.get("event") == "workflow_dispatch" and run.get("head_branch") == receipt.ref
                and str(run.get("head_sha", "")).lower() == receipt.expected_head
                and created >= accepted and run_id > 0):
            matches.append(run)
    matches.sort(key=lambda item: int(item["id"]))
    return matches


def _discover_run(api: GitHubApi, receipt: DispatchReceipt, *, timeout_seconds: float, poll_seconds: float) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while True:
        matches = _matching_runs(api.workflow_runs(receipt.workflow, receipt.ref), receipt)
        if len(matches) > 1:
            raise RuntimeError("ambiguous matching workflow_dispatch runs")
        if len(matches) == 1:
            return matches[0]
        if time.monotonic() >= deadline:
            raise RuntimeError("matching workflow_dispatch run not observed before timeout")
        time.sleep(poll_seconds)


def _wait_terminal(api: GitHubApi, run_id: int, *, timeout_seconds: float, poll_seconds: float) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while True:
        run = api.workflow_run(run_id)
        status_value = run.get("status")
        if status_value == "completed":
            return run
        if status_value not in {"queued", "in_progress", "waiting", "pending", "requested"}:
            raise RuntimeError("workflow run entered unknown non-terminal state")
        if time.monotonic() >= deadline:
            raise RuntimeError("workflow run did not reach terminal state")
        time.sleep(poll_seconds)


def _artifact_digest_bytes(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


def _verify_f009_artifact(data: bytes, *, run_id: int, expected_head: str) -> tuple[str, str]:
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise RuntimeError("F009 artifact is not a valid ZIP") from exc
    names = {name.rstrip("/") for name in archive.namelist() if not name.endswith("/")}
    if names != _REQUIRED_F009_FILES:
        raise RuntimeError("F009 artifact file set mismatch")
    payloads = {name: archive.read(name) for name in _REQUIRED_F009_FILES}
    try:
        manifest, reconciliation = json.loads(payloads["proof-manifest.json"]), json.loads(payloads["reconciliation-receipt.json"])
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("F009 artifact JSON invalid") from exc
    if not isinstance(manifest, dict) or not isinstance(reconciliation, dict):
        raise RuntimeError("F009 artifact JSON shape invalid")
    if str(manifest.get("github_run_id")) != str(run_id):
        raise RuntimeError("F009 proof manifest run binding mismatch")
    if str(manifest.get("github_sha", "")).lower() != expected_head:
        raise RuntimeError("F009 proof manifest head binding mismatch")
    artifact_digests = manifest.get("artifact_digests")
    if not isinstance(artifact_digests, dict):
        raise RuntimeError("F009 internal artifact digest set missing")
    for name in _REQUIRED_F009_FILES - {"proof-manifest.json"}:
        if artifact_digests.get(name) != sha256(payloads[name]).hexdigest():
            raise RuntimeError(f"F009 internal artifact digest mismatch: {name}")
    positive, negative = manifest.get("positive"), manifest.get("negative_results")
    if not isinstance(positive, dict) or not isinstance(negative, dict) or not negative:
        raise RuntimeError("F009 positive/negative proof summary missing")
    if positive.get("reconciliation") != "MATCHED" or positive.get("effect_executed_once") is not True:
        raise RuntimeError("F009 positive proof invalid")
    if positive.get("effect_digest") != positive.get("independent_effect_digest"):
        raise RuntimeError("F009 independent effect digest mismatch")
    if not all(value is True for value in negative.values()):
        raise RuntimeError("F009 negative case did not fail closed")
    if manifest.get("runtime_can_mint_authority") is not False or manifest.get("runtime_has_signing_secret") is not False:
        raise RuntimeError("F009 runtime authority/signing invariant failed")
    if manifest.get("f005_runtime_resumed") is not False or manifest.get("production_effect") is not False:
        raise RuntimeError("F009 prohibited runtime/production effect detected")
    if reconciliation.get("disposition") != "MATCHED" or reconciliation.get("anomaly_codes") not in ([], ()):
        raise RuntimeError("F009 reconciliation receipt invalid")
    return sha256(payloads["proof-manifest.json"]).hexdigest(), "MATCHED"


def _original_dispatch_request(comments: list[dict], receipt: DispatchReceipt,
                               policy: DispatchPolicy, repository: str) -> DispatchRequest:
    matches = []
    for item in comments:
        try:
            item_id = int(item.get("id", 0))
        except (TypeError, ValueError):
            continue
        if item_id == receipt.control_comment_id:
            matches.append(item)
    if len(matches) != 1:
        raise RuntimeError("original control comment is missing or ambiguous")
    item = matches[0]
    body, user = item.get("body"), item.get("user")
    actor = user.get("login") if isinstance(user, dict) else None
    if not isinstance(body, str) or not isinstance(actor, str):
        raise RuntimeError("original control comment malformed")
    request = parse_envelope(body, repository=repository, issue_number=policy.control_issue,
                             comment_id=receipt.control_comment_id, actor=actor, policy=policy)
    if (request.request_id, request.actor, request.workflow, request.ref, request.expected_head) != (receipt.request_id, receipt.actor, receipt.workflow, receipt.ref, receipt.expected_head):
        raise RuntimeError("original dispatch request differs from dispatch receipt")
    if sha256(request.canonical_inputs.encode("utf-8")).hexdigest() != receipt.canonical_inputs_digest:
        raise RuntimeError("canonical inputs digest mismatch")
    return request


def _zip_single_group_receipt(data: bytes) -> bytes:
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise RuntimeError("group-channel artifact is not a valid ZIP") from exc
    infos, names = archive.infolist(), [info.filename for info in archive.infolist()]
    if names != [_GROUP_RECEIPT_FILE] or len(set(names)) != 1:
        raise RuntimeError("group-channel artifact file set mismatch")
    info = infos[0]
    mode = (info.external_attr >> 16) & 0xFFFF
    if info.is_dir() or (mode and not stat.S_ISREG(mode)):
        raise RuntimeError("group-channel receipt member is not a regular file")
    return archive.read(info)


def _verify_group_artifact(data: bytes, *, envelope, run_id: int, run_attempt: int) -> GroupChannelReceipt:
    raw = _zip_single_group_receipt(data)
    try:
        value = strict_json_loads(raw.rstrip(b"\n"))
    except GroupChannelContractError as exc:
        raise RuntimeError("group-channel receipt JSON invalid") from exc
    if not isinstance(value, dict) or group_canonical_json(value) + b"\n" != raw:
        raise RuntimeError("group-channel receipt JSON is not canonical")
    try:
        receipt = GroupChannelReceipt(**value).validate()
    except (TypeError, GroupChannelContractError) as exc:
        raise RuntimeError("group-channel receipt contract invalid") from exc
    required = (receipt.repository == envelope.repository, receipt.message_id == envelope.message_id,
        receipt.target == envelope.target, receipt.expected_master_head == envelope.expected_master_head,
        receipt.envelope_digest == envelope.envelope_digest, receipt.payload_digest == envelope.payload_digest,
        receipt.workflow_run_id == run_id, receipt.workflow_run_attempt == run_attempt,
        receipt.state == "EMITTED_EVIDENCE_ONLY", receipt.authority_effect is False, receipt.repository_effect is False)
    if not all(required):
        raise RuntimeError("group-channel receipt binding mismatch")
    return receipt


def _actor_login(value: object) -> str:
    if not isinstance(value, dict) or not isinstance(value.get("login"), str):
        raise RuntimeError("workflow run actor binding missing")
    return value["login"]


def _observe_group_channel(*, request: ObservationRequest, permission: str, comments: list[dict],
                           dispatch_receipt: DispatchReceipt, candidate: dict, terminal: dict,
                           api: GitHubApi) -> GroupChannelRunObservationReceipt:
    original = _original_dispatch_request(comments, dispatch_receipt, DEFAULT_POLICY, api.repository)
    inputs = dict(original.inputs())
    if set(inputs) != {"envelope_b64"} or not isinstance(inputs["envelope_b64"], str):
        raise RuntimeError("group-channel original input set invalid")
    accepted = _parse_time(dispatch_receipt.accepted_at)
    try:
        envelope = decode_envelope(inputs["envelope_b64"], now=accepted)
    except GroupChannelContractError as exc:
        raise RuntimeError("historical group-channel envelope invalid at dispatch time") from exc
    if envelope.repository != api.repository or envelope.expected_master_head != dispatch_receipt.expected_head:
        raise RuntimeError("historical group-channel envelope binding mismatch")
    run_id, run_attempt = int(candidate["id"]), int(terminal.get("run_attempt", 0))
    expected_name = f"lion-group-channel-receipt-{run_id}-{run_attempt}"
    artifacts = [item for item in api.run_artifacts(run_id) if item.get("name") == expected_name and item.get("expired") is False]
    if len(artifacts) != 1:
        raise RuntimeError("target group-channel artifact is missing or ambiguous")
    artifact = artifacts[0]
    try:
        artifact_id, artifact_size, artifact_digest = int(artifact["id"]), int(artifact["size_in_bytes"]), str(artifact["digest"])
        artifact_created = _parse_time(str(artifact["created_at"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("target group-channel artifact metadata invalid") from exc
    if artifact_id <= 0 or artifact_size <= 0 or not artifact_digest.startswith("sha256:"):
        raise RuntimeError("target group-channel artifact metadata invalid")
    data = api.download_artifact(artifact_id)
    if _artifact_digest_bytes(data) != artifact_digest:
        raise RuntimeError("downloaded group-channel artifact digest differs from GitHub artifact digest")
    receipt = _verify_group_artifact(data, envelope=envelope, run_id=run_id, run_attempt=run_attempt)
    run_created, emitted, issued = _parse_time(str(candidate["created_at"])), _parse_time(receipt.emitted_at), _parse_time(envelope.issued_at)
    if issued > accepted + _TIMESTAMP_TOLERANCE:
        raise RuntimeError("group-channel envelope issued after dispatch acceptance")
    if accepted > run_created + _TIMESTAMP_TOLERANCE:
        raise RuntimeError("group-channel run predates dispatch beyond timestamp tolerance")
    if run_created > emitted + _TIMESTAMP_TOLERANCE or emitted > artifact_created + _TIMESTAMP_TOLERANCE:
        raise RuntimeError("group-channel evidence temporal ordering invalid")
    run_actor, triggering_actor = _actor_login(terminal.get("actor")), _actor_login(terminal.get("triggering_actor"))
    if run_actor != _EXPECTED_GROUP_RUN_ACTOR or triggering_actor != _EXPECTED_GROUP_RUN_ACTOR:
        raise RuntimeError("unexpected group-channel workflow actor substitution")
    result = GroupChannelRunObservationReceipt(schema_version="1.0.0", request_id=request.request_id,
        observation_comment_id=request.comment_id, control_comment_id=dispatch_receipt.control_comment_id,
        actor=request.actor, permission=permission, workflow=dispatch_receipt.workflow, ref=dispatch_receipt.ref,
        expected_head=dispatch_receipt.expected_head, dispatch_accepted_at=dispatch_receipt.accepted_at,
        run_id=run_id, run_attempt=run_attempt, event="workflow_dispatch", status="completed", conclusion="success",
        run_actor=run_actor, triggering_actor=triggering_actor, artifact_id=artifact_id, artifact_name=expected_name,
        artifact_digest=artifact_digest, artifact_size=artifact_size, message_id=receipt.message_id, target=receipt.target,
        envelope_digest=receipt.envelope_digest, payload_digest=receipt.payload_digest,
        group_channel_receipt_digest=receipt.receipt_digest, emitted_at=receipt.emitted_at, state=receipt.state,
        authority_effect=False, repository_effect=False, bridge_implementation_digest=_implementation_digest(),
        trust_decision="ALLOW", observation_result="OBSERVED_VERIFIED").validate()
    api.post_issue_comment(DEFAULT_POLICY.control_issue, _group_observation_receipt_body(result))
    return result


def _parse_code_inputs(original: DispatchRequest) -> dict[str, object]:
    inputs = dict(original.inputs())
    if set(inputs) != set(_CODE_INPUT_KEYS) or any(not isinstance(inputs[key], str) for key in _CODE_INPUT_KEYS):
        raise RuntimeError("code-perception original input set invalid")
    head, tree, semantic = str(inputs["expected_head"]), str(inputs["expected_tree"]), str(inputs["expected_tree_semantic_digest"])
    if _HEX40.fullmatch(head) is None or _HEX40.fullmatch(tree) is None or _HEX64.fullmatch(semantic) is None:
        raise RuntimeError("code-perception expected identity invalid")
    try:
        files, symbols, edges = int(str(inputs["expected_files"])), int(str(inputs["expected_symbols"])), int(str(inputs["expected_edges"]))
    except ValueError as exc:
        raise RuntimeError("code-perception expected counts invalid") from exc
    if str(files) != inputs["expected_files"] or str(symbols) != inputs["expected_symbols"] or str(edges) != inputs["expected_edges"] or min(files, symbols, edges) <= 0:
        raise RuntimeError("code-perception expected counts are not canonical positive integers")
    return {"expected_head": head, "expected_tree": tree, "expected_tree_semantic_digest": semantic,
            "expected_files": files, "expected_symbols": symbols, "expected_edges": edges}


def _structured_projection_from_log(log_text: str) -> dict[str, object]:
    structured, summaries = [], []
    for line in log_text.splitlines():
        marker_index = line.find(_CODE_STRUCTURED_MARKER)
        if marker_index >= 0:
            suffix = line[marker_index + len(_CODE_STRUCTURED_MARKER):].strip()
            if suffix.startswith("{"):
                try:
                    value = json.loads(suffix)
                except json.JSONDecodeError as exc:
                    raise RuntimeError("malformed observer structured output") from exc
                if not isinstance(value, dict) or set(value) != _CODE_STRUCTURED_KEYS:
                    raise RuntimeError("observer structured output shape invalid")
                if canonical_json(value).decode("utf-8") != suffix:
                    raise RuntimeError("observer structured output is not canonical JSON")
                structured.append(value)
        found = _CODE_SUMMARY_RE.search(line)
        if found:
            summaries.append(found.groupdict())
    if len(structured) != 1 or len(summaries) != 1:
        raise RuntimeError("observer structured projection receipt is missing or ambiguous")
    value, summary = structured[0], summaries[0]
    try:
        summary_values = {"run_id": int(summary["run_id"]), "job_id": int(summary["job_id"]),
            "workflow_id": int(summary["workflow_id"]), "workflow_path": summary["workflow_path"],
            "head_sha": summary["head"], "tree_sha": summary["tree"], "projection_digest": summary["digest"],
            "tree_semantic_digest": summary["tree_semantic_digest"], "file_count": int(summary["files"]),
            "symbol_count": int(summary["symbols"]), "edge_count": int(summary["edges"]),
            "authority_effect": summary["authority_effect"] == "true"}
    except (KeyError, ValueError) as exc:
        raise RuntimeError("observer projection summary invalid") from exc
    for key, expected in summary_values.items():
        if value.get(key) != expected:
            raise RuntimeError("observer structured output and projection summary disagree")
    return value


def _canonical_target_job(jobs: list[dict], target_job_id: int) -> dict:
    core = [job for job in jobs if job.get("name") == "core"]
    if len(core) != 1:
        raise RuntimeError("target canonical core job is missing or ambiguous")
    job = core[0]
    try:
        job_id = int(job["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("target core job identity invalid") from exc
    if job_id != target_job_id or job.get("status") != "completed" or job.get("conclusion") != "success":
        raise RuntimeError("target canonical core job binding invalid")
    steps = job.get("steps")
    if not isinstance(steps, list):
        raise RuntimeError("target core job steps missing")
    step_map = {}
    for step in steps:
        if isinstance(step, dict) and isinstance(step.get("name"), str):
            name = step["name"]
            if name in step_map:
                raise RuntimeError("duplicate target core step name")
            step_map[name] = step
    for required in ("Parse JSON schemas", "Compile Cyber-Lion package", "Run Cyber-Lion tests"):
        step = step_map.get(required)
        if not isinstance(step, dict) or step.get("status") != "completed" or step.get("conclusion") != "success":
            raise RuntimeError(f"target required core step not successful: {required}")
    startup = step_map.get("Run Startup Evolution demo")
    if startup is not None and (startup.get("status") != "completed" or startup.get("conclusion") != "success"):
        raise RuntimeError("target Startup Evolution demo is not successful")
    admissions = [item for item in jobs if item.get("name") == "Cyber-Lion Merge Authority Admission"]
    if len(admissions) > 1:
        raise RuntimeError("target merge admission job is ambiguous")
    if admissions and (admissions[0].get("status") != "completed" or admissions[0].get("conclusion") != "success"):
        raise RuntimeError("target merge admission job is not successful")
    return job


def _observe_code_perception(*, request: ObservationRequest, permission: str, comments: list[dict],
                             dispatch_receipt: DispatchReceipt, candidate: dict, terminal: dict,
                             api: GitHubApi) -> CodePerceptionRunObservationReceipt:
    if dispatch_receipt.workflow != CODE_PERCEPTION_WORKFLOW:
        raise RuntimeError("code-perception observer workflow substitution")
    if terminal.get("path") != f".github/workflows/{CODE_PERCEPTION_WORKFLOW}":
        raise RuntimeError("code-perception observer workflow path substitution")
    observer_run_id, observer_run_attempt = int(candidate["id"]), int(terminal.get("run_attempt", 0))
    if observer_run_id <= 0 or observer_run_attempt <= 0:
        raise RuntimeError("code-perception observer run identity invalid")
    original = _original_dispatch_request(comments, dispatch_receipt, DEFAULT_POLICY, api.repository)
    expected = _parse_code_inputs(original)
    observer_jobs = api.run_jobs(observer_run_id)
    observe_jobs = [job for job in observer_jobs if job.get("name") == "observe" and job.get("status") == "completed" and job.get("conclusion") == "success"]
    if len(observe_jobs) != 1:
        raise RuntimeError("successful code-perception observer job is missing or ambiguous")
    try:
        observer_job_id = int(observe_jobs[0]["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("code-perception observer job identity invalid") from exc
    projection = _structured_projection_from_log(api.job_logs(observer_job_id))
    try:
        target_run_id, target_job_id, target_workflow_id = int(projection["run_id"]), int(projection["job_id"]), int(projection["workflow_id"])
        file_count, symbol_count, edge_count = int(projection["file_count"]), int(projection["symbol_count"]), int(projection["edge_count"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("code-perception structured projection types invalid") from exc
    if (projection.get("workflow_name") != CODE_PERCEPTION_TARGET_NAME or target_workflow_id != CODE_PERCEPTION_TARGET_WORKFLOW_ID
            or projection.get("workflow_path") != CODE_PERCEPTION_TARGET_PATH or projection.get("event") != "push"
            or projection.get("branch") != CODE_PERCEPTION_TARGET_BRANCH or projection.get("head_sha") != expected["expected_head"]
            or projection.get("tree_sha") != expected["expected_tree"] or projection.get("tree_semantic_digest") != expected["expected_tree_semantic_digest"]
            or file_count != expected["expected_files"] or symbol_count != expected["expected_symbols"] or edge_count != expected["expected_edges"]
            or projection.get("authority_effect") is not False or target_run_id <= 0 or target_job_id <= 0):
        raise RuntimeError("code-perception structured projection binding mismatch")
    projection_digest = str(projection.get("projection_digest", ""))
    if _HEX64.fullmatch(projection_digest) is None:
        raise RuntimeError("code-perception projection digest invalid")
    from cyber_lion.enterprise.code_perception_observation import (
        CodePerceptionObservationError, ObservationRequest as CodeObservationRequest,
        select_exact_run, validate_commit_identity,
    )
    native_expected = CodeObservationRequest(repository=api.repository, workflow_name=CODE_PERCEPTION_TARGET_NAME,
        workflow_id=CODE_PERCEPTION_TARGET_WORKFLOW_ID, workflow_path=CODE_PERCEPTION_TARGET_PATH,
        branch=CODE_PERCEPTION_TARGET_BRANCH, head_sha=str(expected["expected_head"]), tree_sha=str(expected["expected_tree"]),
        tree_semantic_digest=str(expected["expected_tree_semantic_digest"]), file_count=int(expected["expected_files"]),
        symbol_count=int(expected["expected_symbols"]), edge_count=int(expected["expected_edges"]))
    try:
        selected = select_exact_run({"workflow_runs": api.repository_runs(event="push", branch=CODE_PERCEPTION_TARGET_BRANCH, head_sha=str(expected["expected_head"]))}, native_expected)
        validate_commit_identity(api.commit(str(expected["expected_head"])), native_expected)
    except CodePerceptionObservationError as exc:
        raise RuntimeError("repository-native target observation failed closed") from exc
    if int(selected.get("id", 0)) != target_run_id:
        raise RuntimeError("observer target run differs from independent canonical selection")
    exact_target = api.workflow_run(target_run_id)
    if (int(exact_target.get("id", 0)) != target_run_id or exact_target.get("name") != CODE_PERCEPTION_TARGET_NAME
            or int(exact_target.get("workflow_id", 0)) != CODE_PERCEPTION_TARGET_WORKFLOW_ID or exact_target.get("path") != CODE_PERCEPTION_TARGET_PATH
            or exact_target.get("event") != "push" or exact_target.get("head_branch") != CODE_PERCEPTION_TARGET_BRANCH
            or str(exact_target.get("head_sha", "")).lower() != expected["expected_head"] or exact_target.get("status") != "completed"
            or exact_target.get("conclusion") != "success"):
        raise RuntimeError("independently fetched target run binding mismatch")
    _canonical_target_job(api.run_jobs(target_run_id), target_job_id)
    result = CodePerceptionRunObservationReceipt(schema_version="1.0.0", request_id=request.request_id,
        observation_comment_id=request.comment_id, control_comment_id=dispatch_receipt.control_comment_id,
        actor=request.actor, permission=permission, workflow=dispatch_receipt.workflow, ref=dispatch_receipt.ref,
        expected_head=dispatch_receipt.expected_head, dispatch_accepted_at=dispatch_receipt.accepted_at,
        observer_run_id=observer_run_id, observer_run_attempt=observer_run_attempt, observer_status="completed", observer_conclusion="success",
        target_workflow_name=CODE_PERCEPTION_TARGET_NAME, target_workflow_id=CODE_PERCEPTION_TARGET_WORKFLOW_ID,
        target_workflow_path=CODE_PERCEPTION_TARGET_PATH, target_event="push", target_branch=CODE_PERCEPTION_TARGET_BRANCH,
        target_head_sha=str(expected["expected_head"]), target_tree_sha=str(expected["expected_tree"]), target_run_id=target_run_id,
        target_job_id=target_job_id, projection_digest=projection_digest, tree_semantic_digest=str(expected["expected_tree_semantic_digest"]),
        file_count=file_count, symbol_count=symbol_count, edge_count=edge_count, authority_effect=False, repository_effect=False,
        bridge_implementation_digest=_implementation_digest(), trust_decision="ALLOW", observation_result="OBSERVED_VERIFIED").validate()
    api.post_issue_comment(DEFAULT_POLICY.control_issue, _code_perception_observation_receipt_body(result))
    return result


def observe(event: dict, api: GitHubApi, *, policy: DispatchPolicy = DEFAULT_POLICY,
            discovery_timeout: float = 180.0, terminal_timeout: float = 300.0,
            poll_seconds: float = 2.0) -> RunObservationReceipt | GroupChannelRunObservationReceipt | CodePerceptionRunObservationReceipt:
    issue_number, comment_id, body, actor, _ = _event_parts(event, api, policy)
    request = parse_observation_envelope(body, repository=api.repository, issue_number=issue_number, comment_id=comment_id, actor=actor, policy=policy)
    permission = api.actor_permission(actor)
    if permission not in policy.trusted_permissions:
        raise RuntimeError("untrusted actor permission")
    comments = api.issue_comments(policy.control_issue)
    if _already_observed(comments, request.request_id):
        raise RuntimeError("request already has a verified observation receipt")
    dispatch_receipt = _dispatch_receipt_for(comments, request.request_id, policy)
    candidate = _discover_run(api, dispatch_receipt, timeout_seconds=discovery_timeout, poll_seconds=poll_seconds)
    run_id = int(candidate["id"])
    terminal = _wait_terminal(api, run_id, timeout_seconds=terminal_timeout, poll_seconds=poll_seconds)
    if (terminal.get("event") != "workflow_dispatch" or terminal.get("head_branch") != dispatch_receipt.ref
            or str(terminal.get("head_sha", "")).lower() != dispatch_receipt.expected_head
            or terminal.get("status") != "completed" or terminal.get("conclusion") != "success"):
        raise RuntimeError("target workflow_dispatch run is not exact successful terminal run")
    if dispatch_receipt.workflow == "lion-group-channel.yml":
        return _observe_group_channel(request=request, permission=permission, comments=comments,
            dispatch_receipt=dispatch_receipt, candidate=candidate, terminal=terminal, api=api)
    if dispatch_receipt.workflow == CODE_PERCEPTION_WORKFLOW:
        return _observe_code_perception(request=request, permission=permission, comments=comments,
            dispatch_receipt=dispatch_receipt, candidate=candidate, terminal=terminal, api=api)
    if dispatch_receipt.workflow != "f009-live-runtime-proof.yml":
        raise RuntimeError("no observer implementation for allowlisted workflow")
    run_attempt = int(terminal.get("run_attempt", 0))
    expected_artifact_name = f"f009-live-runtime-proof-{run_id}-{run_attempt}"
    artifacts = [item for item in api.run_artifacts(run_id) if item.get("name") == expected_artifact_name and item.get("expired") is False]
    if len(artifacts) != 1:
        raise RuntimeError("target run artifact is missing or ambiguous")
    artifact = artifacts[0]
    try:
        artifact_id, artifact_size, github_digest = int(artifact["id"]), int(artifact["size_in_bytes"]), str(artifact["digest"])
    except (KeyError, ValueError, TypeError) as exc:
        raise RuntimeError("target run artifact metadata invalid") from exc
    if artifact_id <= 0 or artifact_size <= 0 or not github_digest.startswith("sha256:"):
        raise RuntimeError("target run artifact metadata invalid")
    data = api.download_artifact(artifact_id)
    if _artifact_digest_bytes(data) != github_digest:
        raise RuntimeError("downloaded artifact digest differs from GitHub artifact digest")
    proof_manifest_digest, reconciliation = _verify_f009_artifact(data, run_id=run_id, expected_head=dispatch_receipt.expected_head)
    result = RunObservationReceipt(schema_version="1.0.0", request_id=request.request_id, observation_comment_id=request.comment_id,
        actor=request.actor, permission=permission, workflow=dispatch_receipt.workflow, ref=dispatch_receipt.ref,
        expected_head=dispatch_receipt.expected_head, dispatch_accepted_at=dispatch_receipt.accepted_at,
        run_id=run_id, run_attempt=run_attempt, event="workflow_dispatch", status="completed", conclusion="success",
        artifact_id=artifact_id, artifact_name=expected_artifact_name, artifact_digest=github_digest, artifact_size=artifact_size,
        proof_manifest_digest=proof_manifest_digest, positive_reconciliation=reconciliation,
        bridge_implementation_digest=_implementation_digest(), trust_decision="ALLOW", observation_result="OBSERVED_VERIFIED").validate()
    api.post_issue_comment(policy.control_issue, _observation_receipt_body(result))
    return result


def run_event(event_path: Path, repository: str, token: str) -> DispatchReceipt | RunObservationReceipt | GroupChannelRunObservationReceipt | CodePerceptionRunObservationReceipt:
    event = json.loads(event_path.read_text(encoding="utf-8"))
    if not isinstance(event, dict):
        raise RuntimeError("event must be an object")
    body = event.get("comment", {}).get("body") if isinstance(event.get("comment"), dict) else None
    api = GitHubApi(repository, token)
    if isinstance(body, str) and body.startswith(OBSERVE_PREFIX):
        return observe(event, api)
    return execute(event, api)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args(argv)
    token = os.environ.get(args.token_env, "")
    if not token:
        raise SystemExit("GitHub token unavailable")
    receipt = run_event(Path(args.event), args.repository, token)
    print(canonical_json(asdict(receipt)).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
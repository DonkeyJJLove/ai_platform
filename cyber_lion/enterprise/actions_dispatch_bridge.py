"""Repository-native bounded GitHub Actions dispatch and observation bridge.

Dispatch is exact-head and replay bound. Observation is workflow-aware: F009 retains
its dedicated proof-manifest semantics while ``lion-group-channel.yml`` uses a
separate evidence-only receipt contract. Issue comments and receipts are evidence,
never authority.
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
DEFAULT_POLICY = DispatchPolicy(
    control_issue=CONTROL_ISSUE,
    allowed_workflows=("f009-live-runtime-proof.yml", "lion-group-channel.yml"),
    allowed_refs=("master",),
    allowed_inputs=(
        ("f009-live-runtime-proof.yml", ()),
        ("lion-group-channel.yml", ("envelope_b64",)),
    ),
).validate()

_FIELD_ORDER = ("workflow", "ref", "expected_head", "request_id", "inputs")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
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


def parse_envelope(
    body: str,
    *,
    repository: str,
    issue_number: int,
    comment_id: int,
    actor: str,
    policy: DispatchPolicy = DEFAULT_POLICY,
) -> DispatchRequest:
    lines = body.splitlines()
    if len(lines) != 1 + len(_FIELD_ORDER) or lines[0] != PREFIX:
        raise ValueError("malformed LION-DISPATCH envelope")
    values: dict[str, str] = {}
    for expected, line in zip(_FIELD_ORDER, lines):
        if expected == "workflow":
            continue
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
        schema_version="1",
        repository=repository,
        issue_number=issue_number,
        comment_id=comment_id,
        actor=actor,
        request_id=values["request_id"],
        workflow=values["workflow"],
        ref=values["ref"],
        expected_head=values["expected_head"],
        canonical_inputs=canonical_inputs,
    ).validate(policy)


def parse_observation_envelope(
    body: str,
    *,
    repository: str,
    issue_number: int,
    comment_id: int,
    actor: str,
    policy: DispatchPolicy = DEFAULT_POLICY,
) -> ObservationRequest:
    lines = body.splitlines()
    if len(lines) != 2 or lines[0] != OBSERVE_PREFIX or not lines[1].startswith("request_id="):
        raise ValueError("malformed LION-OBSERVE envelope")
    return ObservationRequest(
        schema_version="1",
        repository=repository,
        issue_number=issue_number,
        comment_id=comment_id,
        actor=actor,
        request_id=lines[1].removeprefix("request_id="),
    ).validate(policy)


class GitHubApi:
    def __init__(self, repository: str, token: str, api_url: str = "https://api.github.com") -> None:
        parsed = urllib.parse.urlsplit(api_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.github.com"
            or parsed.port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError("GitHub API origin must be canonical HTTPS api.github.com")
        self.repository = repository
        self.token = token
        self.api_url = "https://api.github.com"

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lion-actions-dispatch-bridge/3",
        }

    def _request(self, method: str, path: str, body: object | None = None) -> tuple[int, object | None]:
        if not path.startswith("/") or ".." in path:
            raise RuntimeError("unsafe GitHub API path")
        data = canonical_json(body) if body is not None else None
        headers = self._headers()
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.api_url + path, data=data, method=method, headers=headers)
        try:
            opener = urllib.request.build_opener(self._NoRedirect())
            with opener.open(req, timeout=20) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"GitHub API {method} {path} failed: {exc.code}: {detail}") from exc

    def actor_permission(self, actor: str) -> str:
        status, value = self._request("GET", f"/repos/{self.repository}/collaborators/{urllib.parse.quote(actor, safe='')}/permission")
        if status != 200 or not isinstance(value, dict) or not isinstance(value.get("permission"), str):
            raise RuntimeError("unable to resolve actor permission")
        return value["permission"]

    def ref_head(self, ref: str) -> str:
        status, value = self._request("GET", f"/repos/{self.repository}/git/ref/heads/{urllib.parse.quote(ref, safe='')}")
        try:
            sha = value["object"]["sha"]  # type: ignore[index]
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
        result: list[dict] = []
        for page in range(1, 101):
            status, value = self._request("GET", f"/repos/{self.repository}/issues/{issue_number}/comments?per_page=100&page={page}")
            if status != 200 or not isinstance(value, list):
                raise RuntimeError("unable to read replay ledger")
            result.extend(v for v in value if isinstance(v, dict))
            if len(value) < 100:
                return result
        raise RuntimeError("replay ledger pagination limit exceeded")

    def post_issue_comment(self, issue_number: int, body: str) -> int:
        status, value = self._request("POST", f"/repos/{self.repository}/issues/{issue_number}/comments", {"body": body})
        if status != 201 or not isinstance(value, dict) or not isinstance(value.get("id"), int):
            raise RuntimeError("failed to create durable issue receipt")
        return value["id"]

    def patch_issue_comment(self, comment_id: int, body: str) -> None:
        status, _ = self._request("PATCH", f"/repos/{self.repository}/issues/comments/{comment_id}", {"body": body})
        if status != 200:
            raise RuntimeError("failed to update issue receipt")

    def dispatch(self, workflow: str, ref: str, inputs: dict[str, object]) -> None:
        status, _ = self._request("POST", f"/repos/{self.repository}/actions/workflows/{urllib.parse.quote(workflow, safe='')}/dispatches", {"ref": ref, "inputs": inputs})
        if status != 204:
            raise RuntimeError(f"workflow dispatch not accepted: {status}")

    def workflow_runs(self, workflow: str, ref: str) -> list[dict]:
        result: list[dict] = []
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

    def workflow_run(self, run_id: int) -> dict:
        status, value = self._request("GET", f"/repos/{self.repository}/actions/runs/{run_id}")
        if status != 200 or not isinstance(value, dict):
            raise RuntimeError("unable to resolve workflow run")
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
    return "\n".join((
        CLAIM_PREFIX,
        f"request_id={request.request_id}",
        f"replay_key={request.replay_key()}",
        f"payload_digest={request.payload_digest()}",
        f"comment_id={request.comment_id}",
        f"actor={request.actor}",
        f"permission={permission}",
        f"workflow={request.workflow}",
        f"ref={request.ref}",
        f"expected_head={request.expected_head}",
        "state=CLAIMED_BEFORE_EFFECT",
    ))


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
    keys = (
        "request_id", "observation_comment_id", "control_comment_id", "actor", "permission",
        "workflow", "ref", "expected_head", "dispatch_accepted_at", "run_id", "run_attempt",
        "event", "status", "conclusion", "run_actor", "triggering_actor", "artifact_id",
        "artifact_name", "artifact_digest", "artifact_size", "message_id", "target",
        "envelope_digest", "payload_digest", "group_channel_receipt_digest", "emitted_at",
        "state", "authority_effect", "repository_effect", "bridge_implementation_digest",
        "trust_decision", "observation_result",
    )
    return "\n".join([GROUP_OBSERVATION_RECEIPT_PREFIX, *(f"{key}={values[key]}" for key in keys)])


def _event_parts(event: dict, api: GitHubApi, policy: DispatchPolicy) -> tuple[int, int, str, str, str]:
    if event.get("action") != "created":
        raise RuntimeError("only newly created issue comments are accepted")
    issue = event.get("issue")
    comment = event.get("comment")
    repository_obj = event.get("repository")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(repository_obj, dict):
        raise RuntimeError("malformed issue_comment event")
    issue_number = issue.get("number")
    comment_id = comment.get("id")
    body = comment.get("body")
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
    receipt = DispatchReceipt(
        schema_version="1.0.0", request_id=request.request_id, control_comment_id=request.comment_id,
        actor=request.actor, permission=permission, workflow=request.workflow, ref=request.ref,
        expected_head=request.expected_head,
        canonical_inputs_digest=sha256(request.canonical_inputs.encode("utf-8")).hexdigest(),
        accepted_at=_now(), replay_key=request.replay_key(),
        bridge_implementation_digest=_implementation_digest(), trust_decision="ALLOW",
        github_api_result="ACCEPTED_204",
    ).validate()
    api.patch_issue_comment(claim_id, _receipt_body(receipt))
    return receipt


def _dispatch_receipt_for(comments: list[dict], request_id: str, policy: DispatchPolicy) -> DispatchReceipt:
    found: list[DispatchReceipt] = []
    for item in comments:
        body = item.get("body")
        if not isinstance(body, str) or not body.startswith(RECEIPT_PREFIX):
            continue
        fields = _kv_body(RECEIPT_PREFIX, body)
        if fields is None or fields.get("request_id") != request_id:
            continue
        try:
            receipt = DispatchReceipt(
                schema_version="1.0.0", request_id=fields["request_id"],
                control_comment_id=int(fields["control_comment_id"]), actor=fields["actor"],
                permission=fields["permission"], workflow=fields["workflow"], ref=fields["ref"],
                expected_head=fields["expected_head"], canonical_inputs_digest=fields["canonical_inputs_digest"],
                accepted_at=fields["accepted_at"], replay_key=fields["replay_key"],
                bridge_implementation_digest=fields["bridge_implementation_digest"],
                trust_decision=fields["trust_decision"], github_api_result=fields["github_api_result"],
            ).validate()
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
        for prefix in (OBSERVATION_RECEIPT_PREFIX, GROUP_OBSERVATION_RECEIPT_PREFIX):
            if body.startswith(prefix):
                fields = _kv_body(prefix, body)
                if fields and fields.get("request_id") == request_id:
                    matches += 1
    if matches > 1:
        raise RuntimeError("observation ledger is ambiguous")
    return matches == 1


def _matching_runs(runs: list[dict], receipt: DispatchReceipt) -> list[dict]:
    accepted = _parse_time(receipt.accepted_at)
    matches: list[dict] = []
    for run in runs:
        try:
            created = _parse_time(str(run["created_at"]))
            run_id = int(run["id"])
        except (KeyError, ValueError, TypeError):
            continue
        if run.get("event") == "workflow_dispatch" and run.get("head_branch") == receipt.ref and str(run.get("head_sha", "")).lower() == receipt.expected_head and created >= accepted and run_id > 0:
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
        manifest = json.loads(payloads["proof-manifest.json"])
        reconciliation = json.loads(payloads["reconciliation-receipt.json"])
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
    positive = manifest.get("positive")
    negative = manifest.get("negative_results")
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


def _original_dispatch_request(comments: list[dict], receipt: DispatchReceipt, policy: DispatchPolicy) -> DispatchRequest:
    matches: list[dict] = []
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
    body = item.get("body")
    user = item.get("user")
    actor = user.get("login") if isinstance(user, dict) else None
    if not isinstance(body, str) or not isinstance(actor, str):
        raise RuntimeError("original control comment malformed")
    request = parse_envelope(body, repository=receipt.workflow and "DonkeyJJLove/ai_platform", issue_number=policy.control_issue, comment_id=receipt.control_comment_id, actor=actor, policy=policy)
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
    infos = archive.infolist()
    names = [info.filename for info in infos]
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
    required = (
        receipt.repository == envelope.repository,
        receipt.message_id == envelope.message_id,
        receipt.target == envelope.target,
        receipt.expected_master_head == envelope.expected_master_head,
        receipt.envelope_digest == envelope.envelope_digest,
        receipt.payload_digest == envelope.payload_digest,
        receipt.workflow_run_id == run_id,
        receipt.workflow_run_attempt == run_attempt,
        receipt.state == "EMITTED_EVIDENCE_ONLY",
        receipt.authority_effect is False,
        receipt.repository_effect is False,
    )
    if not all(required):
        raise RuntimeError("group-channel receipt binding mismatch")
    return receipt


def _actor_login(value: object) -> str:
    if not isinstance(value, dict) or not isinstance(value.get("login"), str):
        raise RuntimeError("workflow run actor binding missing")
    return value["login"]


def _observe_group_channel(
    *, request: ObservationRequest, permission: str, comments: list[dict],
    dispatch_receipt: DispatchReceipt, candidate: dict, terminal: dict, api: GitHubApi,
) -> GroupChannelRunObservationReceipt:
    original = _original_dispatch_request(comments, dispatch_receipt, DEFAULT_POLICY)
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
    run_id = int(candidate["id"])
    run_attempt = int(terminal.get("run_attempt", 0))
    expected_name = f"lion-group-channel-receipt-{run_id}-{run_attempt}"
    artifacts = [item for item in api.run_artifacts(run_id) if item.get("name") == expected_name and item.get("expired") is False]
    if len(artifacts) != 1:
        raise RuntimeError("target group-channel artifact is missing or ambiguous")
    artifact = artifacts[0]
    try:
        artifact_id = int(artifact["id"])
        artifact_size = int(artifact["size_in_bytes"])
        artifact_digest = str(artifact["digest"])
        artifact_created = _parse_time(str(artifact["created_at"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("target group-channel artifact metadata invalid") from exc
    if artifact_id <= 0 or artifact_size <= 0 or not artifact_digest.startswith("sha256:"):
        raise RuntimeError("target group-channel artifact metadata invalid")
    data = api.download_artifact(artifact_id)
    if _artifact_digest_bytes(data) != artifact_digest:
        raise RuntimeError("downloaded group-channel artifact digest differs from GitHub artifact digest")
    receipt = _verify_group_artifact(data, envelope=envelope, run_id=run_id, run_attempt=run_attempt)
    run_created = _parse_time(str(candidate["created_at"]))
    emitted = _parse_time(receipt.emitted_at)
    issued = _parse_time(envelope.issued_at)
    if issued > accepted + _TIMESTAMP_TOLERANCE:
        raise RuntimeError("group-channel envelope issued after dispatch acceptance")
    if accepted > run_created + _TIMESTAMP_TOLERANCE:
        raise RuntimeError("group-channel run predates dispatch beyond timestamp tolerance")
    if run_created > emitted + _TIMESTAMP_TOLERANCE or emitted > artifact_created + _TIMESTAMP_TOLERANCE:
        raise RuntimeError("group-channel evidence temporal ordering invalid")
    run_actor = _actor_login(terminal.get("actor"))
    triggering_actor = _actor_login(terminal.get("triggering_actor"))
    if run_actor != _EXPECTED_GROUP_RUN_ACTOR or triggering_actor != _EXPECTED_GROUP_RUN_ACTOR:
        raise RuntimeError("unexpected group-channel workflow actor substitution")
    result = GroupChannelRunObservationReceipt(
        schema_version="1.0.0", request_id=request.request_id,
        observation_comment_id=request.comment_id, control_comment_id=dispatch_receipt.control_comment_id,
        actor=request.actor, permission=permission, workflow=dispatch_receipt.workflow, ref=dispatch_receipt.ref,
        expected_head=dispatch_receipt.expected_head, dispatch_accepted_at=dispatch_receipt.accepted_at,
        run_id=run_id, run_attempt=run_attempt, event="workflow_dispatch", status="completed",
        conclusion="success", run_actor=run_actor, triggering_actor=triggering_actor,
        artifact_id=artifact_id, artifact_name=expected_name, artifact_digest=artifact_digest,
        artifact_size=artifact_size, message_id=receipt.message_id, target=receipt.target,
        envelope_digest=receipt.envelope_digest, payload_digest=receipt.payload_digest,
        group_channel_receipt_digest=receipt.receipt_digest, emitted_at=receipt.emitted_at,
        state=receipt.state, authority_effect=False, repository_effect=False,
        bridge_implementation_digest=_implementation_digest(), trust_decision="ALLOW",
        observation_result="OBSERVED_VERIFIED",
    ).validate()
    api.post_issue_comment(DEFAULT_POLICY.control_issue, _group_observation_receipt_body(result))
    return result


def observe(
    event: dict,
    api: GitHubApi,
    *,
    policy: DispatchPolicy = DEFAULT_POLICY,
    discovery_timeout: float = 180.0,
    terminal_timeout: float = 300.0,
    poll_seconds: float = 2.0,
) -> RunObservationReceipt | GroupChannelRunObservationReceipt:
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
    if terminal.get("event") != "workflow_dispatch" or terminal.get("head_branch") != dispatch_receipt.ref or str(terminal.get("head_sha", "")).lower() != dispatch_receipt.expected_head or terminal.get("status") != "completed" or terminal.get("conclusion") != "success":
        raise RuntimeError("target workflow_dispatch run is not exact successful terminal run")
    if dispatch_receipt.workflow == "lion-group-channel.yml":
        return _observe_group_channel(request=request, permission=permission, comments=comments, dispatch_receipt=dispatch_receipt, candidate=candidate, terminal=terminal, api=api)
    if dispatch_receipt.workflow != "f009-live-runtime-proof.yml":
        raise RuntimeError("no observer implementation for allowlisted workflow")
    run_attempt = int(terminal.get("run_attempt", 0))
    expected_artifact_name = f"f009-live-runtime-proof-{run_id}-{run_attempt}"
    artifacts = [item for item in api.run_artifacts(run_id) if item.get("name") == expected_artifact_name and item.get("expired") is False]
    if len(artifacts) != 1:
        raise RuntimeError("target run artifact is missing or ambiguous")
    artifact = artifacts[0]
    try:
        artifact_id = int(artifact["id"])
        artifact_size = int(artifact["size_in_bytes"])
        github_digest = str(artifact["digest"])
    except (KeyError, ValueError, TypeError) as exc:
        raise RuntimeError("target run artifact metadata invalid") from exc
    if artifact_id <= 0 or artifact_size <= 0 or not github_digest.startswith("sha256:"):
        raise RuntimeError("target run artifact metadata invalid")
    data = api.download_artifact(artifact_id)
    if _artifact_digest_bytes(data) != github_digest:
        raise RuntimeError("downloaded artifact digest differs from GitHub artifact digest")
    proof_manifest_digest, reconciliation = _verify_f009_artifact(data, run_id=run_id, expected_head=dispatch_receipt.expected_head)
    result = RunObservationReceipt(
        schema_version="1.0.0", request_id=request.request_id, observation_comment_id=request.comment_id,
        actor=request.actor, permission=permission, workflow=dispatch_receipt.workflow, ref=dispatch_receipt.ref,
        expected_head=dispatch_receipt.expected_head, dispatch_accepted_at=dispatch_receipt.accepted_at,
        run_id=run_id, run_attempt=run_attempt, event="workflow_dispatch", status="completed",
        conclusion="success", artifact_id=artifact_id, artifact_name=expected_artifact_name,
        artifact_digest=github_digest, artifact_size=artifact_size, proof_manifest_digest=proof_manifest_digest,
        positive_reconciliation=reconciliation, bridge_implementation_digest=_implementation_digest(),
        trust_decision="ALLOW", observation_result="OBSERVED_VERIFIED",
    ).validate()
    api.post_issue_comment(policy.control_issue, _observation_receipt_body(result))
    return result


def run_event(event_path: Path, repository: str, token: str) -> DispatchReceipt | RunObservationReceipt | GroupChannelRunObservationReceipt:
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

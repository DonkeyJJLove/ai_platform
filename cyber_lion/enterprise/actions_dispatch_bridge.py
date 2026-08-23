"""Repository-native bounded GitHub Actions dispatch and observation bridge.

The bridge accepts deterministic issue comments on one control issue. Dispatch and
observation receipts are evidence only; neither comments nor receipts mint authority.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import io
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from cyber_lion.contracts.actions_dispatch_bridge import (
    DispatchPolicy,
    DispatchReceipt,
    DispatchRequest,
    ObservationReceipt,
    ObservationRequest,
    canonical_json,
)

CONTROL_ISSUE = 144
PREFIX = "LION-DISPATCH v1"
OBSERVE_PREFIX = "LION-OBSERVE v1"
CLAIM_PREFIX = "LION-DISPATCH-CLAIM v1"
RECEIPT_PREFIX = "LION-DISPATCH-RECEIPT v1"
OBSERVATION_PREFIX = "LION-OBSERVATION-RECEIPT v1"
DEFAULT_POLICY = DispatchPolicy(
    control_issue=CONTROL_ISSUE,
    allowed_workflows=("f009-live-runtime-proof.yml",),
    allowed_refs=("master",),
    allowed_inputs=(("f009-live-runtime-proof.yml", ()),),
).validate()

_FIELD_ORDER = ("workflow", "ref", "expected_head", "request_id", "inputs")
_OBSERVE_FIELD_ORDER = ("request_id", "require_success")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_REQUIRED_F009_ARTIFACT_FILES = {
    "runtime-identity.json",
    "admission.json",
    "effect-currentness.json",
    "sandbox-execution-receipt.json",
    "independent-observation.json",
    "reconciliation-receipt.json",
    "replay-denial.json",
    "proof-manifest.json",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RuntimeError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _implementation_digest() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


def _fields(body: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in body.splitlines()[1:]:
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def parse_envelope(body: str, *, repository: str, issue_number: int, comment_id: int, actor: str, policy: DispatchPolicy = DEFAULT_POLICY) -> DispatchRequest:
    lines = body.splitlines()
    if len(lines) != 1 + len(_FIELD_ORDER) or lines[0] != PREFIX:
        raise ValueError("malformed LION-DISPATCH envelope")
    values: dict[str, str] = {}
    for expected, line in zip(_FIELD_ORDER, lines[1:]):
        prefix = expected + "="
        if not line.startswith(prefix):
            raise ValueError(f"missing or reordered field: {expected}")
        values[expected] = line[len(prefix):]
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


def parse_observe_envelope(body: str, *, repository: str, issue_number: int, comment_id: int, actor: str, policy: DispatchPolicy = DEFAULT_POLICY) -> ObservationRequest:
    lines = body.splitlines()
    if len(lines) != 1 + len(_OBSERVE_FIELD_ORDER) or lines[0] != OBSERVE_PREFIX:
        raise ValueError("malformed LION-OBSERVE envelope")
    values: dict[str, str] = {}
    for expected, line in zip(_OBSERVE_FIELD_ORDER, lines[1:]):
        prefix = expected + "="
        if not line.startswith(prefix):
            raise ValueError(f"missing or reordered observation field: {expected}")
        values[expected] = line[len(prefix):]
    if values["require_success"] not in {"true", "false"}:
        raise ValueError("require_success must be true or false")
    return ObservationRequest(
        schema_version="1", repository=repository, issue_number=issue_number,
        comment_id=comment_id, actor=actor, request_id=values["request_id"],
        require_success=values["require_success"] == "true",
    ).validate(policy)


class GitHubApi:
    def __init__(self, repository: str, token: str, api_url: str = "https://api.github.com") -> None:
        self.repository = repository
        self.token = token
        self.api_url = api_url.rstrip("/")

    def _request(self, method: str, path: str, body: object | None = None) -> tuple[int, object | None]:
        if not path.startswith("/") or ".." in path:
            raise RuntimeError("unsafe GitHub API path")
        data = canonical_json(body) if body is not None else None
        req = urllib.request.Request(
            self.api_url + path, data=data, method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "lion-actions-dispatch-bridge/2",
                **({"Content-Type": "application/json"} if data is not None else {}),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"GitHub API {method} {path} failed: {exc.code}: {detail}") from exc

    def _request_bytes(self, path: str) -> bytes:
        if not path.startswith("/") or ".." in path:
            raise RuntimeError("unsafe GitHub API path")
        req = urllib.request.Request(
            self.api_url + path, method="GET",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "lion-actions-dispatch-bridge/2",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read()
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
        result: list[dict] = []
        for page in range(1, 101):
            status, value = self._request("GET", f"/repos/{self.repository}/issues/{issue_number}/comments?per_page=100&page={page}")
            if status != 200 or not isinstance(value, list):
                raise RuntimeError("unable to read control issue ledger")
            result.extend(v for v in value if isinstance(v, dict))
            if len(value) < 100:
                return result
        raise RuntimeError("control issue ledger pagination limit exceeded")

    def post_issue_comment(self, issue_number: int, body: str) -> int:
        status, value = self._request("POST", f"/repos/{self.repository}/issues/{issue_number}/comments", {"body": body})
        if status != 201 or not isinstance(value, dict) or not isinstance(value.get("id"), int):
            raise RuntimeError("failed to create durable control receipt")
        return value["id"]

    def patch_issue_comment(self, comment_id: int, body: str) -> None:
        status, _ = self._request("PATCH", f"/repos/{self.repository}/issues/comments/{comment_id}", {"body": body})
        if status != 200:
            raise RuntimeError("failed to update control receipt")

    def dispatch(self, workflow: str, ref: str, inputs: dict[str, object]) -> None:
        status, _ = self._request("POST", f"/repos/{self.repository}/actions/workflows/{urllib.parse.quote(workflow, safe='')}/dispatches", {"ref": ref, "inputs": inputs})
        if status != 204:
            raise RuntimeError(f"workflow dispatch not accepted: {status}")

    def workflow_runs(self, workflow: str, ref: str) -> list[dict]:
        query = urllib.parse.urlencode({"event": "workflow_dispatch", "branch": ref, "per_page": "100"})
        status, value = self._request("GET", f"/repos/{self.repository}/actions/workflows/{urllib.parse.quote(workflow, safe='')}/runs?{query}")
        if status != 200 or not isinstance(value, dict) or not isinstance(value.get("workflow_runs"), list):
            raise RuntimeError("unable to list target workflow runs")
        return [item for item in value["workflow_runs"] if isinstance(item, dict)]

    def workflow_run(self, run_id: int) -> dict:
        status, value = self._request("GET", f"/repos/{self.repository}/actions/runs/{run_id}")
        if status != 200 or not isinstance(value, dict):
            raise RuntimeError("unable to resolve target workflow run")
        return value

    def run_artifacts(self, run_id: int) -> list[dict]:
        status, value = self._request("GET", f"/repos/{self.repository}/actions/runs/{run_id}/artifacts?per_page=100")
        if status != 200 or not isinstance(value, dict) or not isinstance(value.get("artifacts"), list):
            raise RuntimeError("unable to enumerate workflow artifacts")
        return [item for item in value["artifacts"] if isinstance(item, dict)]

    def artifact_zip(self, artifact_id: int) -> bytes:
        return self._request_bytes(f"/repos/{self.repository}/actions/artifacts/{artifact_id}/zip")


def _ledger_match(comments: list[dict], request: DispatchRequest) -> str | None:
    for item in comments:
        body = item.get("body")
        if not isinstance(body, str) or not (body.startswith(CLAIM_PREFIX) or body.startswith(RECEIPT_PREFIX)):
            continue
        fields = _fields(body)
        if fields.get("request_id") == request.request_id:
            return "request-id-already-consumed"
        if fields.get("replay_key") == request.replay_key():
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
    lines = [RECEIPT_PREFIX]
    for key in ("request_id", "control_comment_id", "actor", "permission", "workflow", "ref", "expected_head", "canonical_inputs_digest", "accepted_at", "replay_key", "bridge_implementation_digest", "trust_decision", "github_api_result"):
        lines.append(f"{key}={values[key]}")
    return "\n".join(lines)


def _observation_body(receipt: ObservationReceipt) -> str:
    values = asdict(receipt)
    lines = [OBSERVATION_PREFIX]
    for key in ("request_id", "observation_comment_id", "dispatch_comment_id", "actor", "permission", "workflow", "ref", "expected_head", "dispatch_accepted_at", "run_id", "run_event", "run_status", "run_conclusion", "artifact_id", "artifact_name", "artifact_digest", "manifest_digest", "observed_at", "bridge_implementation_digest", "trust_decision", "observation_result"):
        lines.append(f"{key}={values[key]}")
    return "\n".join(lines)


def _dispatch_receipt_from_ledger(comments: list[dict], request_id: str, policy: DispatchPolicy) -> DispatchReceipt:
    matches: list[DispatchReceipt] = []
    for item in comments:
        body = item.get("body")
        if not isinstance(body, str) or not body.startswith(RECEIPT_PREFIX):
            continue
        fields = _fields(body)
        if fields.get("request_id") != request_id:
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
            raise RuntimeError("dispatch receipt outside observation allowlist")
        _dt(receipt.accepted_at)
        matches.append(receipt)
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one dispatch receipt, found {len(matches)}")
    return matches[0]


def _select_run(runs: list[dict], receipt: DispatchReceipt) -> dict:
    accepted = _dt(receipt.accepted_at)
    matches: list[dict] = []
    for run in runs:
        try:
            created = _dt(str(run["created_at"]))
        except (KeyError, ValueError, TypeError):
            continue
        if run.get("event") == "workflow_dispatch" and run.get("head_branch") == receipt.ref and str(run.get("head_sha", "")).lower() == receipt.expected_head and created >= accepted:
            matches.append(run)
    if len(matches) != 1:
        raise RuntimeError(f"ambiguous or missing target workflow run: {len(matches)} candidates")
    if not isinstance(matches[0].get("id"), int):
        raise RuntimeError("target workflow run id invalid")
    return matches[0]


def _wait_terminal(api: GitHubApi, run_id: int, *, timeout_seconds: int = 240) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while True:
        run = api.workflow_run(run_id)
        if run.get("status") == "completed":
            return run
        if time.monotonic() >= deadline:
            raise RuntimeError("target workflow run did not reach terminal state")
        time.sleep(2)


def _select_f009_artifact(artifacts: list[dict], run_id: int, expected_head: str) -> dict:
    matches: list[dict] = []
    prefix = f"f009-live-runtime-proof-{run_id}-"
    for artifact in artifacts:
        workflow_run = artifact.get("workflow_run")
        if artifact.get("expired") is False and isinstance(artifact.get("id"), int) and isinstance(artifact.get("name"), str) and artifact["name"].startswith(prefix) and isinstance(artifact.get("digest"), str) and artifact["digest"].startswith("sha256:") and isinstance(workflow_run, dict) and str(workflow_run.get("head_sha", "")).lower() == expected_head:
            matches.append(artifact)
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one F009 artifact, found {len(matches)}")
    return matches[0]


def _verify_f009_artifact(zip_bytes: bytes, artifact: dict, run_id: int, expected_head: str) -> str:
    expected_archive_digest = str(artifact["digest"])
    actual_archive_digest = "sha256:" + sha256(zip_bytes).hexdigest()
    if actual_archive_digest != expected_archive_digest:
        raise RuntimeError("artifact archive digest mismatch")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = {name.rstrip("/") for name in archive.namelist() if not name.endswith("/")}
        if names != _REQUIRED_F009_ARTIFACT_FILES:
            raise RuntimeError("artifact file set mismatch")
        payloads = {name: archive.read(name) for name in names}
    try:
        manifest = json.loads(payloads["proof-manifest.json"])
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("proof manifest invalid JSON") from exc
    if not isinstance(manifest, dict):
        raise RuntimeError("proof manifest must be object")
    if str(manifest.get("github_sha", "")).lower() != expected_head:
        raise RuntimeError("proof manifest head mismatch")
    if str(manifest.get("github_run_id", "")) != str(run_id):
        raise RuntimeError("proof manifest run id mismatch")
    artifact_digests = manifest.get("artifact_digests")
    expected_payload_names = _REQUIRED_F009_ARTIFACT_FILES - {"proof-manifest.json"}
    if not isinstance(artifact_digests, dict) or set(artifact_digests) != expected_payload_names:
        raise RuntimeError("artifact digest map file set mismatch")
    for name in expected_payload_names:
        if artifact_digests[name] != sha256(payloads[name]).hexdigest():
            raise RuntimeError(f"internal artifact digest mismatch: {name}")
    positive = manifest.get("positive")
    negatives = manifest.get("negative_results")
    if not isinstance(positive, dict) or positive.get("reconciliation") != "MATCHED":
        raise RuntimeError("positive reconciliation is not MATCHED")
    if positive.get("effect_executed_once") is not True:
        raise RuntimeError("positive effect was not exactly once")
    if positive.get("effect_digest") != positive.get("independent_effect_digest"):
        raise RuntimeError("independent effect digest mismatch")
    if not isinstance(negatives, dict) or not negatives or not all(value is True for value in negatives.values()):
        raise RuntimeError("one or more negative cases did not fail closed")
    if manifest.get("runtime_can_mint_authority") is not False:
        raise RuntimeError("runtime authority minting not denied")
    if manifest.get("runtime_has_signing_secret") is not False:
        raise RuntimeError("runtime signing secret present")
    if manifest.get("f005_runtime_resumed") is not False:
        raise RuntimeError("F005 runtime resumed")
    if manifest.get("production_effect") is not False:
        raise RuntimeError("production effect observed")
    return sha256(payloads["proof-manifest.json"]).hexdigest()


def _event_bindings(event: dict, api: GitHubApi, policy: DispatchPolicy) -> tuple[int, dict, str, str]:
    if event.get("action") != "created":
        raise RuntimeError("only newly created issue comments are accepted")
    issue = event.get("issue")
    comment = event.get("comment")
    repository_obj = event.get("repository")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(repository_obj, dict):
        raise RuntimeError("malformed issue_comment event")
    issue_number = issue.get("number")
    body = comment.get("body")
    actor_obj = comment.get("user")
    actor = actor_obj.get("login") if isinstance(actor_obj, dict) else None
    if repository_obj.get("full_name") != api.repository:
        raise RuntimeError("repository binding mismatch")
    if issue_number != policy.control_issue:
        raise RuntimeError("wrong control issue")
    if not isinstance(comment.get("id"), int) or not isinstance(body, str) or not isinstance(actor, str):
        raise RuntimeError("malformed control comment")
    return int(issue_number), comment, actor, body


def execute_dispatch(event: dict, api: GitHubApi, *, policy: DispatchPolicy = DEFAULT_POLICY) -> DispatchReceipt:
    issue, comment, actor, body = _event_bindings(event, api, policy)
    request = parse_envelope(body, repository=api.repository, issue_number=issue, comment_id=int(comment["id"]), actor=actor, policy=policy)
    permission = api.actor_permission(actor)
    if permission not in policy.trusted_permissions:
        raise RuntimeError("untrusted actor permission")
    current_head = api.ref_head(request.ref)
    if current_head != request.expected_head:
        raise RuntimeError("stale expected head")
    if not api.workflow_exists(request.workflow, request.expected_head):
        raise RuntimeError("allowlisted workflow missing at expected head")
    replay = _ledger_match(api.issue_comments(policy.control_issue), request)
    if replay:
        raise RuntimeError(replay)
    claim_id = api.post_issue_comment(policy.control_issue, _claim_body(request, permission))
    second_head = api.ref_head(request.ref)
    if second_head != request.expected_head:
        api.patch_issue_comment(claim_id, _claim_body(request, permission) + "\nstate=DENIED_HEAD_MOVED_BEFORE_DISPATCH")
        raise RuntimeError("ref moved before dispatch")
    try:
        api.dispatch(request.workflow, request.ref, dict(request.inputs()))
    except Exception:
        api.patch_issue_comment(claim_id, _claim_body(request, permission) + "\nstate=DISPATCH_API_FAILED_REQUEST_CONSUMED")
        raise
    receipt = DispatchReceipt(
        schema_version="1.0.0", request_id=request.request_id,
        control_comment_id=request.comment_id, actor=request.actor, permission=permission,
        workflow=request.workflow, ref=request.ref, expected_head=request.expected_head,
        canonical_inputs_digest=sha256(request.canonical_inputs.encode("utf-8")).hexdigest(),
        accepted_at=_now(), replay_key=request.replay_key(),
        bridge_implementation_digest=_implementation_digest(), trust_decision="ALLOW",
        github_api_result="ACCEPTED_204",
    ).validate()
    api.patch_issue_comment(claim_id, _receipt_body(receipt))
    return receipt


def execute_observation(event: dict, api: GitHubApi, *, policy: DispatchPolicy = DEFAULT_POLICY, timeout_seconds: int = 240) -> ObservationReceipt:
    issue, comment, actor, body = _event_bindings(event, api, policy)
    request = parse_observe_envelope(body, repository=api.repository, issue_number=issue, comment_id=int(comment["id"]), actor=actor, policy=policy)
    permission = api.actor_permission(actor)
    if permission not in policy.trusted_permissions:
        raise RuntimeError("untrusted observer permission")
    comments = api.issue_comments(policy.control_issue)
    dispatch_receipt = _dispatch_receipt_from_ledger(comments, request.request_id, policy)
    current_head = api.ref_head(dispatch_receipt.ref)
    if current_head != dispatch_receipt.expected_head:
        raise RuntimeError("target ref no longer equals dispatched head")
    selected = _select_run(api.workflow_runs(dispatch_receipt.workflow, dispatch_receipt.ref), dispatch_receipt)
    run_id = int(selected["id"])
    terminal = _wait_terminal(api, run_id, timeout_seconds=timeout_seconds)
    if terminal.get("event") != "workflow_dispatch":
        raise RuntimeError("target run event substitution")
    if terminal.get("head_branch") != dispatch_receipt.ref:
        raise RuntimeError("target run branch substitution")
    if str(terminal.get("head_sha", "")).lower() != dispatch_receipt.expected_head:
        raise RuntimeError("target run head substitution")
    conclusion = str(terminal.get("conclusion") or "")
    if request.require_success and conclusion != "success":
        raise RuntimeError(f"target workflow conclusion is {conclusion or 'UNKNOWN'}")
    artifact = _select_f009_artifact(api.run_artifacts(run_id), run_id, dispatch_receipt.expected_head)
    artifact_id = int(artifact["id"])
    zip_bytes = api.artifact_zip(artifact_id)
    manifest_digest = _verify_f009_artifact(zip_bytes, artifact, run_id, dispatch_receipt.expected_head)
    receipt = ObservationReceipt(
        schema_version="1.0.0", request_id=request.request_id,
        observation_comment_id=request.comment_id, dispatch_comment_id=dispatch_receipt.control_comment_id,
        actor=request.actor, permission=permission, workflow=dispatch_receipt.workflow,
        ref=dispatch_receipt.ref, expected_head=dispatch_receipt.expected_head,
        dispatch_accepted_at=dispatch_receipt.accepted_at, run_id=run_id,
        run_event="workflow_dispatch", run_status="completed", run_conclusion=conclusion,
        artifact_id=artifact_id, artifact_name=str(artifact["name"]),
        artifact_digest=str(artifact["digest"]), manifest_digest=manifest_digest,
        observed_at=_now(), bridge_implementation_digest=_implementation_digest(),
        trust_decision="ALLOW", observation_result="OBSERVED_VERIFIED",
    ).validate()
    api.post_issue_comment(policy.control_issue, _observation_body(receipt))
    return receipt


def execute(event: dict, api: GitHubApi, *, policy: DispatchPolicy = DEFAULT_POLICY) -> DispatchReceipt | ObservationReceipt:
    comment = event.get("comment")
    body = comment.get("body") if isinstance(comment, dict) else None
    if isinstance(body, str) and body.startswith(PREFIX):
        return execute_dispatch(event, api, policy=policy)
    if isinstance(body, str) and body.startswith(OBSERVE_PREFIX):
        return execute_observation(event, api, policy=policy)
    raise RuntimeError("unsupported control envelope")


def run_event(event_path: Path, repository: str, token: str) -> DispatchReceipt | ObservationReceipt:
    event = json.loads(event_path.read_text(encoding="utf-8"))
    if not isinstance(event, dict):
        raise RuntimeError("event must be an object")
    return execute(event, GitHubApi(repository, token))


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

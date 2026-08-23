"""Repository-native bounded GitHub Actions dispatch bridge.

The bridge consumes one exact machine-readable issue comment, performs fresh GitHub-side
permission/ref checks, claims the request durably in the control issue, revalidates the
ref immediately before dispatch, and invokes only a statically allowlisted workflow.
Issue comments are replay/evidence records only and are never authority sources.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from cyber_lion.contracts.actions_dispatch_bridge import (
    DispatchPolicy,
    DispatchReceipt,
    DispatchRequest,
    canonical_json,
)

CONTROL_ISSUE = 144
PREFIX = "LION-DISPATCH v1"
CLAIM_PREFIX = "LION-DISPATCH-CLAIM v1"
RECEIPT_PREFIX = "LION-DISPATCH-RECEIPT v1"
DEFAULT_POLICY = DispatchPolicy(
    control_issue=CONTROL_ISSUE,
    allowed_workflows=("f009-live-runtime-proof.yml",),
    allowed_refs=("master",),
    allowed_inputs=(("f009-live-runtime-proof.yml", ()),),
).validate()

_FIELD_ORDER = ("workflow", "ref", "expected_head", "request_id", "inputs")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _implementation_digest() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


def parse_envelope(body: str, *, repository: str, issue_number: int, comment_id: int, actor: str, policy: DispatchPolicy = DEFAULT_POLICY) -> DispatchRequest:
    lines = body.splitlines()
    if len(lines) != 1 + len(_FIELD_ORDER) or lines[0] != PREFIX:
        raise ValueError("malformed LION-DISPATCH envelope")
    values: dict[str, str] = {}
    for expected, line in zip(_FIELD_ORDER, lines[1:]):
        prefix = expected + "="
        if not line.startswith(prefix) or line.count("=") < 1:
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
    request = DispatchRequest(
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
    )
    return request.validate(policy)


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
            self.api_url + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "lion-actions-dispatch-bridge/1",
                **({"Content-Type": "application/json"} if data is not None else {}),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            detail = raw.decode("utf-8", errors="replace")[:1000]
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
            raise RuntimeError("failed to create durable dispatch claim")
        return value["id"]

    def patch_issue_comment(self, comment_id: int, body: str) -> None:
        status, _ = self._request("PATCH", f"/repos/{self.repository}/issues/comments/{comment_id}", {"body": body})
        if status != 200:
            raise RuntimeError("failed to update dispatch receipt")

    def dispatch(self, workflow: str, ref: str, inputs: dict[str, object]) -> None:
        status, _ = self._request(
            "POST",
            f"/repos/{self.repository}/actions/workflows/{urllib.parse.quote(workflow, safe='')}/dispatches",
            {"ref": ref, "inputs": inputs},
        )
        if status != 204:
            raise RuntimeError(f"workflow dispatch not accepted: {status}")


def _ledger_match(comments: list[dict], request: DispatchRequest) -> str | None:
    for item in comments:
        body = item.get("body")
        if not isinstance(body, str):
            continue
        if not (body.startswith(CLAIM_PREFIX) or body.startswith(RECEIPT_PREFIX)):
            continue
        fields: dict[str, str] = {}
        for line in body.splitlines()[1:]:
            if "=" in line:
                key, value = line.split("=", 1)
                fields[key] = value
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
    for key in (
        "request_id", "control_comment_id", "actor", "permission", "workflow", "ref",
        "expected_head", "canonical_inputs_digest", "accepted_at", "replay_key",
        "bridge_implementation_digest", "trust_decision", "github_api_result",
    ):
        lines.append(f"{key}={values[key]}")
    return "\n".join(lines)


def execute(event: dict, api: GitHubApi, *, policy: DispatchPolicy = DEFAULT_POLICY) -> DispatchReceipt:
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
    request = parse_envelope(body, repository=api.repository, issue_number=issue_number, comment_id=comment_id, actor=actor, policy=policy)

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

    # TOCTOU barrier: exact ref is resolved again immediately before the effect.
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
        schema_version="1.0.0",
        request_id=request.request_id,
        control_comment_id=request.comment_id,
        actor=request.actor,
        permission=permission,
        workflow=request.workflow,
        ref=request.ref,
        expected_head=request.expected_head,
        canonical_inputs_digest=sha256(request.canonical_inputs.encode("utf-8")).hexdigest(),
        accepted_at=_now(),
        replay_key=request.replay_key(),
        bridge_implementation_digest=_implementation_digest(),
        trust_decision="ALLOW",
        github_api_result="ACCEPTED_204",
    ).validate()
    api.patch_issue_comment(claim_id, _receipt_body(receipt))
    return receipt


def run_event(event_path: Path, repository: str, token: str) -> DispatchReceipt:
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

"""Slash-safe, authority-bound execution adapter for repository branch cleanup."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from cyber_lion.contracts.repository_maintenance_sandbox import (
    REPOSITORY,
    RepositoryMaintenanceOperation,
    RepositoryMaintenancePolicy,
    validate_branch_name,
)
from cyber_lion.enterprise.repository_maintenance_sandbox import (
    GitHubRepositoryMaintenanceBackend,
    RepositoryMaintenanceContractError,
    RepositoryMaintenanceError,
    RepositoryMaintenanceSandbox,
    _build_operation,
)

_CONTROL_ISSUE = 144
_COMMAND = "LION-BRANCH-CLEANUP v1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class RepositoryDeleteAuthorityEvidence:
    repository: str
    control_comment_id: int
    actor_login: str
    owner_login: str
    workflow_run_id: int
    workflow_run_attempt: int
    checked_out_sha: str
    event_digest: str

    def validate(self) -> "RepositoryDeleteAuthorityEvidence":
        if self.repository != REPOSITORY:
            raise RepositoryMaintenanceError("authority repository substitution denied")
        if not isinstance(self.control_comment_id, int) or isinstance(self.control_comment_id, bool) or self.control_comment_id <= 0:
            raise RepositoryMaintenanceError("authority control comment invalid")
        if not self.actor_login or self.actor_login != self.owner_login:
            raise RepositoryMaintenanceError("repository-owner control authority required")
        if not isinstance(self.workflow_run_id, int) or isinstance(self.workflow_run_id, bool) or self.workflow_run_id <= 0:
            raise RepositoryMaintenanceError("authority workflow run invalid")
        if not isinstance(self.workflow_run_attempt, int) or isinstance(self.workflow_run_attempt, bool) or self.workflow_run_attempt <= 0:
            raise RepositoryMaintenanceError("authority workflow attempt invalid")
        if _SHA40.fullmatch(self.checked_out_sha) is None:
            raise RepositoryMaintenanceError("authority checkout identity invalid")
        if re.fullmatch(r"[0-9a-f]{64}", self.event_digest) is None:
            raise RepositoryMaintenanceError("authority event digest invalid")
        return self

    def digest(self) -> str:
        self.validate()
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(b"LION/REPOSITORY-DELETE-AUTHORITY/1\0" + raw).hexdigest()


def load_repository_delete_authority(*, event_path: Path, repository: str, workflow_run_id: int,
                                     workflow_run_attempt: int, checked_out_sha: str) -> RepositoryDeleteAuthorityEvidence:
    try:
        raw = event_path.read_bytes()
        event = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise RepositoryMaintenanceError("repository maintenance control event unavailable") from exc
    if not isinstance(event, dict) or event.get("action") != "created":
        raise RepositoryMaintenanceError("only created issue_comment authority is accepted")
    issue, comment, repo = event.get("issue"), event.get("comment"), event.get("repository")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(repo, dict):
        raise RepositoryMaintenanceError("malformed repository maintenance control event")
    if issue.get("number") != _CONTROL_ISSUE or repo.get("full_name") != repository or repository != REPOSITORY:
        raise RepositoryMaintenanceError("maintenance authority issue/repository binding mismatch")
    owner = repo.get("owner") or {}
    actor = comment.get("user") or {}
    comment_id = comment.get("id")
    if comment.get("body") != _COMMAND or not isinstance(comment_id, int) or comment_id <= 0:
        raise RepositoryMaintenanceError("maintenance authority command binding mismatch")
    evidence = RepositoryDeleteAuthorityEvidence(
        repository=repository,
        control_comment_id=comment_id,
        actor_login=str(actor.get("login") or ""),
        owner_login=str(owner.get("login") or ""),
        workflow_run_id=workflow_run_id,
        workflow_run_attempt=workflow_run_attempt,
        checked_out_sha=checked_out_sha.lower(),
        event_digest=sha256(raw).hexdigest(),
    )
    return evidence.validate()


class SlashSafeGitHubRepositoryMaintenanceBackend(GitHubRepositoryMaintenanceBackend):
    """Closed GitHub ref-delete boundary; DELETE requires a fresh exact admission."""

    _GET_PREFIXES = (
        f"/repos/{REPOSITORY}/git/ref/heads/",
        f"/repos/{REPOSITORY}/branches",
        f"/repos/{REPOSITORY}/compare/",
        f"/repos/{REPOSITORY}/pulls",
        f"/repos/{REPOSITORY}/contents/",
        f"/repos/{REPOSITORY}/issues/{_CONTROL_ISSUE}/comments",
    )
    _DELETE_PREFIX = f"/repos/{REPOSITORY}/git/refs/heads/"

    def __init__(self, repository: str, token: str, api_url: str = "https://api.github.com") -> None:
        super().__init__(repository, token, api_url)
        self._pending_delete: tuple[str, str, str, str, str] | None = None
        self._consumed_delete_admissions: set[str] = set()

    @staticmethod
    def _branch_path(branch: str) -> str:
        validate_branch_name(branch)
        return urllib.parse.quote(branch, safe="/")

    @classmethod
    def _validate_api_path(cls, method: str, path: str) -> None:
        if not isinstance(path, str) or not path.startswith("/") or "\\" in path:
            raise RepositoryMaintenanceError("unsafe GitHub API path")
        parsed = urllib.parse.urlsplit(path)
        if parsed.scheme or parsed.netloc or parsed.fragment:
            raise RepositoryMaintenanceError("unsafe GitHub API path")
        decoded_path = urllib.parse.unquote(parsed.path)
        if "\\" in decoded_path or any(segment == ".." for segment in decoded_path.split("/")):
            raise RepositoryMaintenanceError("unsafe GitHub API path")
        if method == "GET":
            if not any(parsed.path.startswith(prefix) for prefix in cls._GET_PREFIXES):
                raise RepositoryMaintenanceError("GitHub read route not allowlisted")
            return
        if method == "DELETE":
            if parsed.query or not parsed.path.startswith(cls._DELETE_PREFIX):
                raise RepositoryMaintenanceError("GitHub delete route not allowlisted")
            branch = urllib.parse.unquote(parsed.path[len(cls._DELETE_PREFIX):])
            try:
                validate_branch_name(branch)
            except RepositoryMaintenanceContractError as exc:
                raise RepositoryMaintenanceError("GitHub delete ref outside mission allowlist") from exc
            if not (branch.startswith("docs/") or branch.startswith("mission/")):
                raise RepositoryMaintenanceError("GitHub delete ref outside mission allowlist")
            return
        raise RepositoryMaintenanceError("GitHub method not allowlisted")

    def _request(self, method: str, path: str, body: object | None = None, *, allow_404: bool = False) -> tuple[int, object | None]:
        self._validate_api_path(method, path)
        data = None if body is None else json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers = self._headers()
        if data is not None:
            headers["Content-Type"] = "application/json"
        if method == "GET":
            request = urllib.request.Request(self.api_url + path, data=data, method="GET", headers=headers)
        elif method == "DELETE":
            request = urllib.request.Request(self.api_url + path, data=data, method="DELETE", headers=headers)
        else:
            raise RepositoryMaintenanceError("GitHub method not allowlisted")
        try:
            with urllib.request.build_opener(self._NoRedirect()).open(request, timeout=30) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            if allow_404 and exc.code == 404:
                return 404, None
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RepositoryMaintenanceError(f"GitHub API {method} {path} failed: {exc.code}: {detail}") from exc

    def branch_sha(self, branch: str) -> str | None:
        encoded = self._branch_path(branch)
        status, value = self._request("GET", f"/repos/{self.repository}/git/ref/heads/{encoded}", allow_404=True)
        if status == 404:
            return None
        try:
            sha = value["object"]["sha"]
        except Exception as exc:
            raise RepositoryMaintenanceError("unable to resolve branch") from exc
        if status != 200 or not isinstance(sha, str) or _SHA40.fullmatch(sha) is None:
            raise RepositoryMaintenanceError("invalid branch observation")
        return sha

    def compare_branch_to_master(self, branch: str) -> dict[str, object]:
        encoded = self._branch_path(branch)
        status, value = self._request("GET", f"/repos/{self.repository}/compare/{encoded}...master")
        if status != 200 or not isinstance(value, dict):
            raise RepositoryMaintenanceError("compare unavailable")
        required = ("status", "ahead_by", "behind_by")
        if any(key not in value for key in required):
            raise RepositoryMaintenanceError("compare response incomplete")
        return {key: value[key] for key in required}

    def _completed_control_comments(self) -> set[int]:
        completed: set[int] = set()
        for page in range(1, 101):
            status, value = self._request("GET", f"/repos/{self.repository}/issues/{_CONTROL_ISSUE}/comments?per_page=100&page={page}")
            if status != 200 or not isinstance(value, list):
                raise RepositoryMaintenanceError("durable maintenance replay ledger unavailable")
            for item in value:
                body = item.get("body") if isinstance(item, dict) else None
                if not isinstance(body, str) or "LION-REPOSITORY-MAINTENANCE-OBSERVATION-RECEIPT v1" not in body:
                    continue
                for line in body.splitlines():
                    if line.startswith("control_comment_id="):
                        try:
                            completed.add(int(line.split("=", 1)[1]))
                        except ValueError:
                            raise RepositoryMaintenanceError("durable maintenance replay ledger malformed")
            if len(value) < 100:
                return completed
        raise RepositoryMaintenanceError("durable maintenance replay ledger pagination exceeded")

    def authorize_delete(self, *, operation: RepositoryMaintenanceOperation, policy: RepositoryMaintenancePolicy,
                         authority: RepositoryDeleteAuthorityEvidence) -> str:
        operation.validate(); policy.validate(); authority.validate()
        if operation.repository != self.repository or policy.repository != self.repository:
            raise RepositoryMaintenanceError("delete admission repository mismatch")
        if operation.policy_digest != policy.digest():
            raise RepositoryMaintenanceError("delete admission policy mismatch")
        if authority.checked_out_sha != operation.protected_master_sha:
            raise RepositoryMaintenanceError("delete authority/currentness mismatch")
        if authority.control_comment_id in self._completed_control_comments():
            raise RepositoryMaintenanceError("durable repository maintenance replay denied")
        master = self.master_sha()
        head = self.branch_sha(operation.branch_name)
        if master != operation.protected_master_sha or head != operation.expected_branch_head:
            raise RepositoryMaintenanceError("delete admission currentness failed")
        compare = self.compare_branch_to_master(operation.branch_name)
        prs = self.open_prs_for_branch(operation.branch_name)
        ownership = self.ownership_observation(operation.branch_name, master)
        if not (operation.classification == "A" and compare["status"] in {"ahead", "identical"} and int(compare["behind_by"]) == 0 and not prs and ownership.ownership_state == "UNOWNED"):
            raise RepositoryMaintenanceError("delete admission eligibility failed")
        admission_digest = sha256(
            b"LION/REPOSITORY-REF-DELETE-ADMISSION/1\0" + "\0".join((
                authority.digest(), operation.operation_digest(), policy.digest(), self.backend_identity_digest,
                self.repository, operation.branch_name, operation.expected_branch_head, operation.protected_master_sha,
            )).encode("utf-8")
        ).hexdigest()
        if admission_digest in self._consumed_delete_admissions:
            raise RepositoryMaintenanceError("repository delete admission replay denied")
        self._pending_delete = (operation.branch_name, operation.expected_branch_head, operation.protected_master_sha, admission_digest, authority.digest())
        return admission_digest

    def delete_exact_branch_ref(self, branch: str, expected_head: str) -> None:
        pending = self._pending_delete
        self._pending_delete = None
        if pending is None or pending[0] != branch or pending[1] != expected_head:
            raise RepositoryMaintenanceError("direct backend delete denied: exact admission required")
        expected_master, admission_digest = pending[2], pending[3]
        if admission_digest in self._consumed_delete_admissions:
            raise RepositoryMaintenanceError("repository delete admission replay denied")
        observed_master = self.master_sha()
        observed_head = self.branch_sha(branch)
        if observed_master != expected_master or observed_head != expected_head:
            raise RepositoryMaintenanceError("delete currentness changed after admission")
        encoded = self._branch_path(branch)
        status, _ = self._request("DELETE", f"/repos/{self.repository}/git/refs/heads/{encoded}")
        if status != 204:
            raise RepositoryMaintenanceError(f"branch deletion not accepted: {status}")
        self._consumed_delete_admissions.add(admission_digest)


def run_cleanup(*, token: str, expected_master: str, event_path: Path, repository: str,
                workflow_run_id: int, workflow_run_attempt: int, checked_out_sha: str) -> dict[str, object]:
    authority = load_repository_delete_authority(
        event_path=event_path, repository=repository, workflow_run_id=workflow_run_id,
        workflow_run_attempt=workflow_run_attempt, checked_out_sha=checked_out_sha,
    )
    backend = SlashSafeGitHubRepositoryMaintenanceBackend(REPOSITORY, token)
    master = backend.master_sha()
    if master != expected_master or master != authority.checked_out_sha:
        raise RepositoryMaintenanceError("expected master/authority binding failed")
    policy = RepositoryMaintenancePolicy(
        schema_version="1.0.0", repository=REPOSITORY,
        mission_id="E003-BRANCH-ZERO-SANDBOX-AUTONOMIZATION", protected_ref="master",
        allowed_prefixes=("docs/", "mission/"), max_deletions=100,
    ).validate()
    sandbox = RepositoryMaintenanceSandbox(policy=policy, backend=backend)
    branches = [name for name in backend.list_branches() if name != "master"]
    observations: list[dict[str, object]] = []
    receipts: list[dict[str, object]] = []
    retained: list[dict[str, object]] = []
    for index, branch in enumerate(branches, start=1):
        if not (branch.startswith("docs/") or branch.startswith("mission/")):
            retained.append({"branch": branch, "reason": "OUTSIDE_MISSION_ALLOWLIST"})
            continue
        try:
            operation, observation = _build_operation(sandbox=sandbox, branch=branch, index=index, master_sha=master)
            observations.append(observation.canonical())
            backend.authorize_delete(operation=operation, policy=policy, authority=authority)
            receipt = sandbox.execute_delete(operation)
            receipts.append(asdict(receipt))
        except (RepositoryMaintenanceError, RepositoryMaintenanceContractError) as exc:
            retained.append({"branch": branch, "reason": str(exc)})
    final_master = backend.master_sha()
    if final_master != master:
        raise RepositoryMaintenanceError("master changed during cleanup mission")
    final_branches = backend.list_branches()
    return {
        "schema_version": "1.0.0", "mission_id": policy.mission_id,
        "authority_digest": authority.digest(), "control_comment_id": authority.control_comment_id,
        "master_before": master, "master_after": final_master,
        "initial_non_master_count": len(branches), "deleted_count": len(receipts),
        "retained_count": len([b for b in final_branches if b != "master"]),
        "deleted": [r["branch_name"] for r in receipts], "retained": retained,
        "final_branches": final_branches, "receipts": receipts,
        "authority_effect": False, "master_effect": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-cleanup", action="store_true")
    parser.add_argument("--expected-master", required=True)
    args = parser.parse_args(argv)
    if not args.execute_cleanup:
        parser.error("--execute-cleanup required")
    try:
        result = run_cleanup(
            token=os.environ.get("GITHUB_TOKEN", ""),
            expected_master=args.expected_master,
            event_path=Path(os.environ.get("GITHUB_EVENT_PATH", "")),
            repository=os.environ.get("GITHUB_REPOSITORY", ""),
            workflow_run_id=int(os.environ.get("GITHUB_RUN_ID", "0")),
            workflow_run_attempt=int(os.environ.get("GITHUB_RUN_ATTEMPT", "0")),
            checked_out_sha=os.environ.get("GITHUB_SHA", ""),
        )
    except Exception as exc:
        print(f"LION_REPOSITORY_MAINTENANCE_FAILED type={type(exc).__name__} detail={exc}", file=sys.stderr)
        return 1
    print("LION_REPOSITORY_MAINTENANCE_RESULT " + json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

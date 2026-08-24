"""Slash-safe execution adapter for the bounded branch cleanup sandbox."""
from __future__ import annotations

from dataclasses import asdict
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from cyber_lion.contracts.repository_maintenance_sandbox import REPOSITORY, RepositoryMaintenancePolicy, validate_branch_name
from cyber_lion.enterprise.repository_maintenance_sandbox import (
    GitHubRepositoryMaintenanceBackend,
    RepositoryMaintenanceContractError,
    RepositoryMaintenanceError,
    RepositoryMaintenanceSandbox,
    _build_operation,
)


class SlashSafeGitHubRepositoryMaintenanceBackend(GitHubRepositoryMaintenanceBackend):
    """Preserve slashes inside Git ref names while escaping unsafe characters."""

    _GET_PREFIXES = (
        f"/repos/{REPOSITORY}/git/ref/heads/",
        f"/repos/{REPOSITORY}/branches",
        f"/repos/{REPOSITORY}/compare/",
        f"/repos/{REPOSITORY}/pulls",
        f"/repos/{REPOSITORY}/contents/",
    )
    _DELETE_PREFIX = f"/repos/{REPOSITORY}/git/refs/heads/"

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
        data = None
        if body is not None:
            data = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers = self._headers()
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.api_url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.build_opener(self._NoRedirect()).open(request, timeout=30) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            if allow_404 and exc.code == 404:
                return 404, None
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RepositoryMaintenanceError(
                f"GitHub API {method} {path} failed: {exc.code}: {detail}"
            ) from exc

    def branch_sha(self, branch: str) -> str | None:
        encoded = self._branch_path(branch)
        status, value = self._request(
            "GET",
            f"/repos/{self.repository}/git/ref/heads/{encoded}",
            allow_404=True,
        )
        if status == 404:
            return None
        try:
            sha = value["object"]["sha"]
        except Exception as exc:
            raise RepositoryMaintenanceError("unable to resolve branch") from exc
        if status != 200 or not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
            raise RepositoryMaintenanceError("invalid branch observation")
        return sha

    def compare_branch_to_master(self, branch: str) -> dict[str, object]:
        encoded = self._branch_path(branch)
        status, value = self._request(
            "GET", f"/repos/{self.repository}/compare/{encoded}...master"
        )
        if status != 200 or not isinstance(value, dict):
            raise RepositoryMaintenanceError("compare unavailable")
        required = ("status", "ahead_by", "behind_by")
        if any(key not in value for key in required):
            raise RepositoryMaintenanceError("compare response incomplete")
        return {key: value[key] for key in required}

    def delete_exact_branch_ref(self, branch: str, expected_head: str) -> None:
        encoded = self._branch_path(branch)
        observed = self.branch_sha(branch)
        if observed != expected_head:
            raise RepositoryMaintenanceError("branch head changed before delete")
        status, _ = self._request(
            "DELETE", f"/repos/{self.repository}/git/refs/heads/{encoded}"
        )
        if status != 204:
            raise RepositoryMaintenanceError(f"branch deletion not accepted: {status}")


def run_cleanup(*, token: str, expected_master: str | None = None) -> dict[str, object]:
    backend = SlashSafeGitHubRepositoryMaintenanceBackend(REPOSITORY, token)
    master = backend.master_sha()
    if expected_master is not None and master != expected_master:
        raise RepositoryMaintenanceError("expected master binding failed")
    policy = RepositoryMaintenancePolicy(
        schema_version="1.0.0",
        repository=REPOSITORY,
        mission_id="E003-BRANCH-ZERO-SANDBOX-AUTONOMIZATION",
        protected_ref="master",
        allowed_prefixes=("docs/", "mission/"),
        max_deletions=100,
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
            operation, observation = _build_operation(
                sandbox=sandbox, branch=branch, index=index, master_sha=master
            )
            observations.append(observation.canonical())
            receipt = sandbox.execute_delete(operation)
            receipts.append(asdict(receipt))
        except (RepositoryMaintenanceError, RepositoryMaintenanceContractError) as exc:
            retained.append({"branch": branch, "reason": str(exc)})
    final_master = backend.master_sha()
    if final_master != master:
        raise RepositoryMaintenanceError("master changed during cleanup mission")
    final_branches = backend.list_branches()
    return {
        "schema_version": "1.0.0",
        "mission_id": policy.mission_id,
        "master_before": master,
        "master_after": final_master,
        "initial_non_master_count": len(branches),
        "deleted_count": len(receipts),
        "retained_count": len([b for b in final_branches if b != "master"]),
        "deleted": [r["branch_name"] for r in receipts],
        "retained": retained,
        "final_branches": final_branches,
        "receipts": receipts,
        "authority_effect": False,
        "master_effect": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-cleanup", action="store_true")
    parser.add_argument("--expected-master")
    args = parser.parse_args(argv)
    if not args.execute_cleanup:
        parser.error("--execute-cleanup required")
    try:
        result = run_cleanup(
            token=os.environ.get("GITHUB_TOKEN", ""),
            expected_master=args.expected_master or None,
        )
    except Exception as exc:
        print(
            f"LION_REPOSITORY_MAINTENANCE_FAILED type={type(exc).__name__} detail={exc}",
            file=sys.stderr,
        )
        return 1
    print(
        "LION_REPOSITORY_MAINTENANCE_RESULT "
        + json.dumps(result, sort_keys=True, separators=(",", ":"))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Read-only observer for exact post-merge Code Perception evidence.

This module queries GitHub Actions with an already-provided token, binds observation
to the canonical Cyber-Lion Core workflow identity, independently binds the expected
Git tree to the exact observed head commit, and extracts one exact
CODE_PERCEPTION_CANDIDATE_PROJECTION line from the selected run's job logs.

It never writes repository state and never grants authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Iterable
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import urlencode

from cyber_lion.enterprise.actions_dispatch_temporal_compat import (
    _REDIRECT_CODES,
    _download_signed_archive,
    _validate_archive_location,
)

_PROJECTION_RE = re.compile(
    r"CODE_PERCEPTION_CANDIDATE_PROJECTION\s+"
    r"head=(?P<head>[0-9a-f]{40})\s+"
    r"tree=(?P<tree>[0-9a-f]{40})\s+"
    r"digest=(?P<digest>[0-9a-f]{64})\s+"
    r"tree_semantic_digest=(?P<tree_semantic_digest>[0-9a-f]{64})\s+"
    r"files=(?P<files>\d+)\s+symbols=(?P<symbols>\d+)\s+edges=(?P<edges>\d+)"
)


class CodePerceptionObservationError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validated_api_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise CodePerceptionObservationError("GitHub API URL boundary denied")
    return url


@dataclass(frozen=True)
class ObservationRequest:
    repository: str
    workflow_name: str
    workflow_id: int
    workflow_path: str
    branch: str
    head_sha: str
    tree_sha: str
    tree_semantic_digest: str
    file_count: int
    symbol_count: int
    edge_count: int


@dataclass(frozen=True)
class ProjectionReceipt:
    run_id: int
    job_id: int
    workflow_name: str
    workflow_id: int
    workflow_path: str
    event: str
    branch: str
    head_sha: str
    tree_sha: str
    projection_digest: str
    tree_semantic_digest: str
    file_count: int
    symbol_count: int
    edge_count: int
    authority_effect: bool = False


def _github_get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(
        _validated_api_url(url),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lion-code-perception-observer",
        },
        method="GET",
    )
    try:
        with urllib.request.build_opener(_NoRedirect()).open(req, timeout=30) as response:
            if response.status != 200:
                raise CodePerceptionObservationError("GitHub API returned non-terminal status")
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise CodePerceptionObservationError(f"GitHub API request failed: {exc.code}") from exc


def _github_get_text(url: str, token: str) -> str:
    req = urllib.request.Request(
        _validated_api_url(url),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lion-code-perception-observer",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(req, timeout=30) as response:
            code = response.status
            location = response.headers.get("Location")
    except urllib.error.HTTPError as exc:
        if exc.code not in _REDIRECT_CODES:
            raise CodePerceptionObservationError(f"GitHub logs request failed: {exc.code}") from exc
        code = exc.code
        location = exc.headers.get("Location")
    if code not in _REDIRECT_CODES or not location:
        raise CodePerceptionObservationError("GitHub logs endpoint did not return a signed redirect")
    try:
        safe_location = _validate_archive_location(location)
        data = _download_signed_archive(safe_location)
    except RuntimeError as exc:
        raise CodePerceptionObservationError("GitHub logs redirect boundary denied") from exc
    return data.decode("utf-8", errors="replace")


def _matching_runs(payload: dict, expected: ObservationRequest) -> tuple[dict, ...]:
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise CodePerceptionObservationError("workflow_runs payload missing")
    matches = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        if run.get("name") != expected.workflow_name:
            continue
        try:
            workflow_id = int(run.get("workflow_id"))
        except (TypeError, ValueError):
            continue
        if workflow_id != expected.workflow_id:
            continue
        if run.get("path") != expected.workflow_path:
            continue
        if run.get("event") != "push":
            continue
        if run.get("head_branch") != expected.branch:
            continue
        if str(run.get("head_sha", "")).lower() != expected.head_sha:
            continue
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            continue
        matches.append(run)
    return tuple(matches)


def select_exact_run(payload: dict, expected: ObservationRequest) -> dict:
    matches = _matching_runs(payload, expected)
    if len(matches) != 1:
        raise CodePerceptionObservationError(
            f"expected exactly one successful exact canonical push run, found {len(matches)}"
        )
    return matches[0]


def validate_commit_identity(payload: dict, expected: ObservationRequest) -> str:
    """Bind expected head/tree to GitHub's exact commit object, not to log self-report."""
    if not isinstance(payload, dict):
        raise CodePerceptionObservationError("commit payload missing")
    commit_sha = str(payload.get("sha", "")).lower()
    if commit_sha != expected.head_sha:
        raise CodePerceptionObservationError("commit head substitution detected")
    commit = payload.get("commit")
    if not isinstance(commit, dict):
        raise CodePerceptionObservationError("commit object missing")
    tree = commit.get("tree")
    if not isinstance(tree, dict):
        raise CodePerceptionObservationError("commit tree object missing")
    tree_sha = str(tree.get("sha", "")).lower()
    if tree_sha != expected.tree_sha:
        raise CodePerceptionObservationError("commit tree substitution detected")
    return tree_sha


def parse_projection_lines(lines: Iterable[str], expected: ObservationRequest) -> tuple[dict, ...]:
    matches = []
    for line in lines:
        found = _PROJECTION_RE.search(line)
        if not found:
            continue
        item = found.groupdict()
        item["files"] = int(item["files"])
        item["symbols"] = int(item["symbols"])
        item["edges"] = int(item["edges"])
        if item["head"] != expected.head_sha:
            continue
        if item["tree"] != expected.tree_sha:
            continue
        if item["tree_semantic_digest"] != expected.tree_semantic_digest:
            continue
        if item["files"] != expected.file_count:
            continue
        if item["symbols"] != expected.symbol_count:
            continue
        if item["edges"] != expected.edge_count:
            continue
        matches.append(item)
    return tuple(matches)


def _projection_cardinality_error(run_id: int, successful_job_ids: tuple[int, ...], count: int) -> CodePerceptionObservationError:
    """Expose bounded run/job identity without weakening exact projection verification."""
    job_ids = ",".join(str(value) for value in successful_job_ids) or "none"
    return CodePerceptionObservationError(
        "expected exactly one exact projection line, "
        f"found {count}; selected_run_id={run_id}; successful_job_ids={job_ids}"
    )


def observe_exact_projection(expected: ObservationRequest, token: str) -> ProjectionReceipt:
    owner, repo = expected.repository.split("/", 1)

    # Git identity is observed independently from workflow logs. A projection line
    # cannot self-assert the source tree without this exact commit-object binding.
    commit_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{expected.head_sha}"
    observed_tree = validate_commit_identity(_github_get_json(commit_url, token), expected)

    query = urlencode({
        "event": "push",
        "branch": expected.branch,
        "head_sha": expected.head_sha,
        "per_page": "100",
    })
    runs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?{query}"
    run = select_exact_run(_github_get_json(runs_url, token), expected)
    run_id = int(run["id"])

    jobs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs?per_page=100"
    jobs_payload = _github_get_json(jobs_url, token)
    jobs = jobs_payload.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise CodePerceptionObservationError("selected run has no observable jobs")

    receipts = []
    successful_job_ids = []
    for job in jobs:
        if not isinstance(job, dict) or job.get("conclusion") != "success":
            continue
        job_id = int(job["id"])
        successful_job_ids.append(job_id)
        logs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
        log_text = _github_get_text(logs_url, token)
        for projection in parse_projection_lines(log_text.splitlines(), expected):
            if projection["tree"] != observed_tree:
                continue
            if projection["head"] != str(run.get("head_sha", "")).lower():
                continue
            receipts.append((job_id, projection))

    if len(receipts) != 1:
        raise _projection_cardinality_error(run_id, tuple(successful_job_ids), len(receipts))

    job_id, projection = receipts[0]
    return ProjectionReceipt(
        run_id=run_id,
        job_id=job_id,
        workflow_name=expected.workflow_name,
        workflow_id=expected.workflow_id,
        workflow_path=expected.workflow_path,
        event="push",
        branch=expected.branch,
        head_sha=expected.head_sha,
        tree_sha=observed_tree,
        projection_digest=projection["digest"],
        tree_semantic_digest=projection["tree_semantic_digest"],
        file_count=projection["files"],
        symbol_count=projection["symbols"],
        edge_count=projection["edges"],
        authority_effect=False,
    )

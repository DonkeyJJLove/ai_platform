"""Read-only observer for exact post-merge Code Perception evidence.

This module queries GitHub Actions with an already-provided token, selects exactly one
successful push run for an exact workflow/branch/head tuple, and extracts one exact
CODE_PERCEPTION_CANDIDATE_PROJECTION line from the selected run's job logs.

It never writes repository state and never grants authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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


@dataclass(frozen=True)
class ObservationRequest:
    repository: str
    workflow_name: str
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
    req = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lion-code-perception-observer",
        },
        method="GET",
    )
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _github_get_text(url: str, token: str) -> str:
    req = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lion-code-perception-observer",
        },
        method="GET",
    )
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


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
            f"expected exactly one successful exact push run, found {len(matches)}"
        )
    return matches[0]


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


def observe_exact_projection(expected: ObservationRequest, token: str) -> ProjectionReceipt:
    owner, repo = expected.repository.split("/", 1)
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
    for job in jobs:
        if not isinstance(job, dict) or job.get("conclusion") != "success":
            continue
        job_id = int(job["id"])
        logs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
        log_text = _github_get_text(logs_url, token)
        for projection in parse_projection_lines(log_text.splitlines(), expected):
            receipts.append((job_id, projection))

    if len(receipts) != 1:
        raise CodePerceptionObservationError(
            f"expected exactly one exact projection line, found {len(receipts)}"
        )

    job_id, projection = receipts[0]
    return ProjectionReceipt(
        run_id=run_id,
        job_id=job_id,
        workflow_name=expected.workflow_name,
        event="push",
        branch=expected.branch,
        head_sha=expected.head_sha,
        tree_sha=expected.tree_sha,
        projection_digest=projection["digest"],
        tree_semantic_digest=projection["tree_semantic_digest"],
        file_count=projection["files"],
        symbol_count=projection["symbols"],
        edge_count=projection["edges"],
        authority_effect=False,
    )

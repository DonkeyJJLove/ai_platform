"""Always-on, read-only PR merge currentness check for LION.

This is evidence, never merge authorization or a replacement for source/Core/
Bandit/R24 checks. The synthetic GitHub merge must bind the *live* PR base and
head. Missing identity, currentness, or source-truth evidence fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCHEMA = "lion.pr-merge-currentness-gate/v1"
_SHA = re.compile(r"^[0-9a-f]{40}$")
DOMAIN = b"LION/PR-MERGE-GATE/1\0"
_ALLOWED_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MAX_HTTP_BYTES = 2 * 1024 * 1024


class MergeGateError(ValueError):
    """A required piece of exact-source evidence is unavailable or invalid."""


def sha40(value, name):
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise MergeGateError(name + ":invalid_sha40")
    return value


def git(repository, *args, binary=False):
    proc = subprocess.run(
        ["git", "-C", str(repository), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30,
    )
    if proc.returncode:
        raise MergeGateError("git_failed:" + " ".join(args) + ":" +
                             proc.stderr.decode("utf-8", "replace")[-280:])
    return proc.stdout if binary else proc.stdout.decode("ascii", "strict").strip()


def parse_commit(raw: bytes):
    if type(raw) is not bytes or b"\n\n" not in raw:
        raise MergeGateError("commit_header_missing")
    header = raw.split(b"\n\n", 1)[0]
    trees, parents = [], []
    for line in header.splitlines():
        if line.startswith(b"tree "):
            trees.append(line[5:])
        elif line.startswith(b"parent "):
            parents.append(line[7:])
        elif line.startswith((b"tree", b"parent")):
            raise MergeGateError("commit_header_malformed")
    if len(trees) != 1 or len(parents) != 2:
        raise MergeGateError("synthetic_parent_tree_cardinality")
    try:
        tree = trees[0].decode("ascii")
        resolved = [p.decode("ascii") for p in parents]
    except UnicodeError as exc:
        raise MergeGateError("commit_header_nonascii") from exc
    sha40(tree, "merge_tree")
    for i, value in enumerate(resolved):
        sha40(value, "merge_parent_" + str(i))
    return {"tree": tree, "parents": resolved}


def extract_event(event, repository):
    if type(event) is not dict:
        raise MergeGateError("event_not_object")
    if type(repository) is not str or not _ALLOWED_REPO.fullmatch(repository):
        raise MergeGateError("repository_not_canonical")
    pr = event.get("pull_request")
    if type(pr) is not dict:
        raise MergeGateError("pull_request_missing")
    number = pr.get("number")
    if type(number) is not int or number < 1:
        raise MergeGateError("pr_number_invalid")
    base, head = pr.get("base"), pr.get("head")
    if type(base) is not dict or type(head) is not dict:
        raise MergeGateError("pr_refs_missing")
    if base.get("ref") != "master" or (base.get("repo") or {}).get("full_name") != repository:
        raise MergeGateError("pr_base_scope_invalid")
    return {
        "repository": repository, "pr_number": number,
        "base_sha": sha40(base.get("sha"), "base_sha"),
        "head_sha": sha40(head.get("sha"), "head_sha"),
    }


def validate_live(event_identity, live_pr, live_branch, execution_sha, commit, checkout_tree, head_tree):
    if type(live_pr) is not dict or type(live_branch) is not dict:
        raise MergeGateError("live_api_unavailable")
    if live_pr.get("number") != event_identity["pr_number"] or live_pr.get("state") != "open":
        raise MergeGateError("live_pr_not_open")
    live_base, live_head = live_pr.get("base"), live_pr.get("head")
    if type(live_base) is not dict or type(live_head) is not dict:
        raise MergeGateError("live_pr_refs_missing")
    if live_base.get("ref") != "master":
        raise MergeGateError("live_base_ref_drift")
    if live_base.get("sha") != event_identity["base_sha"] or live_head.get("sha") != event_identity["head_sha"]:
        raise MergeGateError("live_pr_head_or_base_drift")
    if (live_branch.get("commit") or {}).get("sha") != event_identity["base_sha"]:
        raise MergeGateError("default_branch_drift")
    sha40(execution_sha, "execution_sha")
    if commit["parents"] != [event_identity["base_sha"], event_identity["head_sha"]]:
        raise MergeGateError("synthetic_parent_drift")
    if commit["tree"] != sha40(checkout_tree, "checkout_tree"):
        raise MergeGateError("synthetic_checkout_tree_drift")
    sha40(head_tree, "candidate_tree")
    return {
        **event_identity, "execution_sha": execution_sha,
        "execution_tree": checkout_tree, "candidate_tree": head_tree,
        "synthetic_parents": commit["parents"],
    }


def github_get(url, token):
    if type(token) is not str or not token:
        raise MergeGateError("github_read_token_missing")
    req = Request(url, headers={
        "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "LION-PR-MERGE-GATE/1",
    })
    try:
        with urlopen(req, timeout=18) as response:
            if response.status != 200:
                raise MergeGateError("github_status:" + str(response.status))
            data = response.read(MAX_HTTP_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise MergeGateError("github_read_failed:" + type(exc).__name__) from exc
    if len(data) > MAX_HTTP_BYTES:
        raise MergeGateError("github_response_oversized")
    try:
        result = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise MergeGateError("github_invalid_json") from exc
    if type(result) is not dict:
        raise MergeGateError("github_response_not_object")
    return result


def truth_currentness(repository):
    # Source truth is the canonical implementation; RAG/old carrier records are not live.
    from cyber_lion.architecture_projection.truth_plane import SubjectEntry, subject_digest
    raw = git(repository, "ls-tree", "-r", "-z", "HEAD", binary=True)
    leaves = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        try:
            meta, path = item.split(b"\t", 1)
            mode, object_type, sha = meta.decode("ascii").split()
            leaves.append(SubjectEntry(path.decode("utf-8"), mode, object_type, sha))
        except (UnicodeError, ValueError) as exc:
            raise MergeGateError("git_tree_entry_invalid") from exc
    result = subject_digest(leaves)
    canonical = json.loads((Path(repository) / "LION/architecture/canonical-state-v1-3-candidate.json").read_text(encoding="utf-8"))
    registry = json.loads((Path(repository) / "cyber_lion/registry/repositories.json").read_text(encoding="utf-8"))
    if (canonical.get("baseline") or {}).get("subject_digest") != result:
        raise MergeGateError("canonical_truth_subject_drift")
    if registry.get("generated_from") != "truth-subject-v1@" + result:
        raise MergeGateError("repository_registry_subject_drift")
    return {"subject_digest": result, "tracked_git_leaves": len(leaves)}


def evaluate(repository, event, env, api_get=github_get):
    ident = extract_event(event, env.get("GITHUB_REPOSITORY"))
    expected = sha40(env.get("GITHUB_SHA"), "github_sha")
    checkout = sha40(git(repository, "rev-parse", "HEAD"), "checked_out_head")
    if checkout != expected:
        raise MergeGateError("checkout_does_not_match_github_sha")
    commit = parse_commit(git(repository, "cat-file", "-p", "HEAD", binary=True))
    checkout_tree = git(repository, "rev-parse", "HEAD^{tree}")
    head_tree = git(repository, "rev-parse", "HEAD^2^{tree}")
    api_base = "https://api.github.com/repos/" + ident["repository"]
    live_pr = api_get(api_base + "/pulls/" + str(ident["pr_number"]), env.get("GITHUB_TOKEN"))
    live_branch = api_get(api_base + "/branches/master", env.get("GITHUB_TOKEN"))
    identity = validate_live(ident, live_pr, live_branch, checkout, commit, checkout_tree, head_tree)
    from tools.lion_workflow_homeostasis import audit
    homeostasis = audit(repository)
    if homeostasis.get("blocking_defect_count") != 0:
        raise MergeGateError("workflow_homeostasis_blocking_defect")
    truth = truth_currentness(repository)
    return {
        "source": identity, "truth": truth,
        "workflow_audit_digest": homeostasis["audit_digest"],
        "workflow_count": homeostasis["workflow_count"],
        "other_workflows_aggregated": False,
        "meaning": "Exact PR Git+source currentness evidence only. Not merge authority or all-CI approval.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=".")
    parser.add_argument("--event", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    record = {
        "schema": SCHEMA,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "authority_effect": "NONE",
        "runtime_effect": "NONE",
        "merge_executed": False,
    }
    exit_code = 0
    try:
        event = json.loads(Path(args.event).read_text(encoding="utf-8"))
        record.update(evaluate(Path(args.repository).resolve(), event, os.environ))
        record["result"] = "PASS"
    except Exception as exc:
        record["result"] = "FAIL_CLOSED"
        record["reason"] = type(exc).__name__ + ":" + str(exc)[:450]
        exit_code = 2
    digest = hashlib.sha256(DOMAIN + json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    record["evidence_digest"] = digest
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".lion-merge-gate-", dir=target.parent, delete=False) as file:
        json.dump(record, file, sort_keys=True, indent=2, ensure_ascii=False)
        file.write("\n")
        file.flush()
        os.fsync(file.fileno())
        temporary = Path(file.name)
    os.replace(temporary, target)
    print(json.dumps({k: record[k] for k in ("schema", "result", "evidence_digest", "authority_effect")}, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

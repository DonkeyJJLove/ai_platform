#!/usr/bin/env python3
"""Build an exact, compact LION federation snapshot and reconciliation baseline.

The snapshot remains source-bound to exact Git HEAD/TREE identities. High-volume
tracked research-output prefixes may be represented by a coverage group bound to
an exact Git subtree SHA instead of repeating every descendant blob entry.

This tool is read-only with respect to source repositories.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from typing import Any

REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")

COVERAGE_RULES = (
    {
        "repository": "DonkeyJJLove/writeups",
        "path_prefix": "badania/heuristic-causal-lab-final-4.3/hcl_final_4_3/runs/",
        "generated_output_class": "ARCHIVED_RUN",
        "min_files": 10000,
    },
)

def git(repo: Path, *args: str, binary: bool=False) -> str | bytes:
    out = subprocess.check_output(["git", "-C", str(repo), *args])
    return out if binary else out.decode().strip()

def _tracked_blob_rows(repo: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    text = git(repo, "ls-tree", "-r", "--full-tree", "HEAD")
    assert isinstance(text, str)
    for line in text.splitlines():
        meta, path = line.split("\t", 1)
        _mode, object_type, sha = meta.split(" ", 2)
        if object_type == "blob":
            rows.append({"path": path, "blob": sha})
    return rows

def _coverage_groups(repository: str, repo: Path, files: list[dict[str, str]]) -> tuple[list[dict[str, Any]], set[str]]:
    groups: list[dict[str, Any]] = []
    covered: set[str] = set()
    for rule in COVERAGE_RULES:
        if rule["repository"] != repository:
            continue
        prefix = str(rule["path_prefix"])
        matched = [row["path"] for row in files if row["path"].startswith(prefix)]
        if len(matched) < int(rule["min_files"]):
            continue
        tree_path = prefix.rstrip("/")
        tree_sha = git(repo, "rev-parse", f"HEAD:{tree_path}")
        assert isinstance(tree_sha, str) and SHA40_RE.fullmatch(tree_sha)
        groups.append({
            "path_prefix": prefix,
            "git_tree_sha": tree_sha,
            "file_count": len(matched),
            "generated_output_class": rule["generated_output_class"],
            "coverage_semantics": "ALL_TRACKED_FILES_UNDER_PREFIX_AT_BOUND_HEAD",
        })
        covered.update(matched)
    return groups, covered

def build_repository(repository: str, repo: Path) -> dict[str, Any]:
    if not REPOSITORY_RE.fullmatch(repository):
        raise ValueError("invalid repository")
    manifest_path = repo / "cyber-lion.repository.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    branch = manifest["repository"]["default_branch"]
    head = git(repo, "rev-parse", "HEAD")
    tree = git(repo, "rev-parse", "HEAD^{tree}")
    manifest_blob = git(repo, "rev-parse", "HEAD:cyber-lion.repository.json")
    assert isinstance(head, str) and SHA40_RE.fullmatch(head)
    assert isinstance(tree, str) and SHA40_RE.fullmatch(tree)
    assert isinstance(manifest_blob, str) and SHA40_RE.fullmatch(manifest_blob)

    files = _tracked_blob_rows(repo)
    groups, covered = _coverage_groups(repository, repo, files)
    explicit = [row for row in files if row["path"] not in covered]
    return {
        "repository": repository,
        "branch": branch,
        "head": head,
        "tree": tree,
        "open_prs": 0,
        "manifest_blob": manifest_blob,
        "manifest": manifest,
        "file_inventory_mode": "FULL_EXCEPT_EXACT_COVERAGE_GROUPS" if groups else "FULL",
        "files": explicit,
        "file_coverage_groups": groups,
        "tracked_file_count": len(files),
        "explicit_file_count": len(explicit),
        "coverage_group_file_count": len(covered),
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="append", default=[], help="repository=local_checkout")
    ap.add_argument("--snapshot-output", required=True)
    ap.add_argument("--baseline-output", required=True)
    ap.add_argument("--baseline-id", required=True)
    ap.add_argument("--architecture-epoch", default="1.5")
    ap.add_argument("--observed-at")
    args = ap.parse_args()

    roots: dict[str, Path] = {}
    for item in args.repo:
        repository, path = item.split("=", 1)
        roots[repository] = Path(path).resolve()
    if len(roots) != 10:
        raise SystemExit("exactly ten repositories required")

    observed_at = args.observed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    repositories = [build_repository(rid, roots[rid]) for rid in sorted(roots)]
    snapshot = {
        "schema": "lion.federation-live-snapshot/v1",
        "observed_at": observed_at,
        "observation_mode": "EXACT_SWEEP_CUTOFF_WITH_COVERAGE_GROUPS",
        "authority_effect": "NONE",
        "repositories": repositories,
    }
    baseline = {
        "schema": "lion.global-repository-reconciliation-baseline/v1",
        "baseline_id": args.baseline_id,
        "architecture_epoch": args.architecture_epoch,
        "observed_at": observed_at,
        "observation_mode": "EXACT_SWEEP_CUTOFF_WITH_COVERAGE_GROUPS",
        "authority_effect": "NONE",
        "repositories": [
            {
                "repository": row["repository"],
                "branch": row["branch"],
                "head": row["head"],
                "tree": row["tree"],
            }
            for row in repositories
        ],
    }
    Path(args.snapshot_output).write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(args.baseline_output).write_text(json.dumps(baseline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "repositories": len(repositories),
        "tracked_files": sum(row["tracked_file_count"] for row in repositories),
        "explicit_files": sum(row["explicit_file_count"] for row in repositories),
        "coverage_group_files": sum(row["coverage_group_file_count"] for row in repositories),
        "coverage_groups": sum(len(row["file_coverage_groups"]) for row in repositories),
    }, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate source-bound maintenance projections for the LION federation.

The generator is read-only with respect to repository history and working-tree
content. It emits test taxonomy, workflow taxonomy and branch reconciliation.
It never deletes refs or mutates a repository.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
from typing import Any

def git(repo: Path, *args: str, binary: bool=False, check: bool=True):
    p=subprocess.run(["git","-C",str(repo),*args],capture_output=True)
    if check and p.returncode:
        raise RuntimeError(p.stderr.decode(errors="ignore").strip() or "git failed")
    return p.stdout if binary else p.stdout.decode().strip()

def read_blob(repo: Path, revision: str, path: str) -> str:
    return git(repo,"show",f"{revision}:{path}")

def test_class(path: str) -> str:
    p=path.lower()
    if "compat" in p or "legacy" in p:
        return "COMPATIBILITY"
    if re.search(r"test_(r\d+|e\d+|f\d+|t\d+|epoch\d+|vkt)",p):
        return "HISTORICAL_REGRESSION"
    if "security" in p or "authority" in p or "admission" in p:
        return "CURRENT_SECURITY"
    if "currentness" in p or "truth" in p or "reconcil" in p:
        return "CURRENT_CURRENTNESS"
    if "runtime" in p or "docker" in p or "host_" in p:
        return "CURRENT_RUNTIME"
    if "integration" in p or "e2e" in p or "whole" in p:
        return "CURRENT_INTEGRATION"
    if "contract" in p or "schema" in p:
        return "CURRENT_CONTRACT"
    return "CURRENT_UNIT"

def branch_refs_from_workflow(text: str) -> list[str]:
    relevant="\n".join(
        line for line in text.splitlines()
        if "branches:" in line or "github.ref" in line or "head_ref" in line
    )
    return sorted(set(re.findall(
        r"(?:mission|fix|ci|test|docs|process-upgrade|actions-health|maintenance)/[A-Za-z0-9_.\-/]+",
        relevant,
    )))

def workflow_class(path: str, text: str) -> str:
    low=(path+" "+text).lower()
    if "bandit" in low or "security" in path.lower():
        return "SECURITY_GATE"
    if "live-runtime-proof" in low or "runtime proof" in low:
        return "LIVE_RUNTIME_PROOF"
    if "maintenance" in low or "file-write" in low:
        return "MAINTENANCE_EFFECT"
    if "currentness" in low or "whole-integration" in low or "r22c" in low:
        return "CURRENTNESS_GATE"
    if re.search(r"mission/r\d|mission/e\d|r2e\d|r9d\d|f00\d",text,re.I):
        return "PERMANENT_PLATFORM_GATE_WITH_HISTORICAL_MARKERS"
    return "PERMANENT_PLATFORM_GATE"

def is_ancestor(repo: Path, a: str, b: str) -> bool:
    return subprocess.run(
        ["git","-C",str(repo),"merge-base","--is-ancestor",a,b],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
    ).returncode==0

def default_branch_references(repo: Path, revision: str, needle: str) -> list[str]:
    p=subprocess.run(
        ["git","-C",str(repo),"grep","-I","-l","-F","-e",needle,revision],
        capture_output=True,
    )
    if p.returncode not in (0,1):
        raise RuntimeError(p.stderr.decode(errors="ignore").strip() or "git grep failed")
    prefix=revision+":"
    hits=[]
    for line in p.stdout.decode(errors="ignore").splitlines():
        path=line[len(prefix):] if line.startswith(prefix) else line
        if path:
            hits.append(path)
    return hits[:50]

def branch_census(
    baseline: dict[str,Any],
    roots: dict[str,Path],
    previous: dict[str,Any] | None,
) -> dict[str,Any]:
    previous_rows={}
    if previous:
        for row in previous.get("rows",[]):
            previous_rows[(row.get("repository"),row.get("branch"),row.get("head"))]=row
    rows=[]
    for item in baseline["repositories"]:
        rid=item["repository"]; repo=roots[rid]; default=item["branch"]
        default_head=item["head"]
        remote_ref=f"refs/remotes/origin/{default}"
        observed_default=git(repo,"rev-parse",remote_ref)
        if observed_default!=default_head:
            raise SystemExit(f"default branch drift: {rid}")
        raw=git(repo,"for-each-ref","--format=%(refname:short) %(objectname)","refs/remotes/origin")
        for line in raw.splitlines():
            if not line:
                continue
            short,head=line.split(" ",1)
            if short=="origin/HEAD" or short=="origin":
                continue
            branch=short[len("origin/"):] if short.startswith("origin/") else short
            tree=git(repo,"rev-parse",head+"^{tree}")
            if branch==default:
                cls="ACTIVE"; ahead=behind=0; mb=head; hits=[]
            else:
                behind_s,ahead_s=git(repo,"rev-list","--left-right","--count",f"{remote_ref}...{short}").split()
                behind=int(behind_s); ahead=int(ahead_s)
                mb=git(repo,"merge-base",remote_ref,short,check=False) or None
                hits=default_branch_references(repo,default_head,branch)
                prev=previous_rows.get((rid,branch,head))
                if prev and prev.get("classification") not in {None,"UNKNOWN","ACTIVE"}:
                    cls=prev["classification"]
                elif head==default_head or (is_ancestor(repo,short,remote_ref) and ahead==0):
                    cls="HISTORICAL_EVIDENCE" if hits else "DELETE_ELIGIBLE"
                elif is_ancestor(repo,remote_ref,short) and ahead>0 and behind==0:
                    cls="UNMERGED_UNIQUE"
                elif ahead>0:
                    cls="UNKNOWN"
                else:
                    cls="SUPERSEDED"
            rows.append({
                "repository":rid,"default_branch":default,"branch":branch,
                "head":head,"tree":tree,"merge_base":mb,
                "ahead_by":ahead,"behind_by":behind,
                "classification":cls,
                "default_branch_references":hits,
            })
    counts={}
    for row in rows:
        counts[row["classification"]]=counts.get(row["classification"],0)+1
    return {
        "schema":"lion.branch-reconciliation/v1",
        "generator":"tools/lion_global_maintenance_projection.py",
        "invalidators":["REPOSITORY_CONTENT_CHANGE","DEPENDENCY_CHANGE"],
        "baseline_id":baseline["baseline_id"],
        "rows":rows,
        "counts":dict(sorted(counts.items())),
        "delete_policy":"DELETE_ELIGIBLE requires no unique commits, ancestor/equal default state and no tracked default-branch reference.",
        "unknown_policy":"UNKNOWN remains preserved until additional PR/history/runtime evidence resolves it.",
        "authority_effect":"NONE",
    }

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--baseline",required=True)
    ap.add_argument("--content-census",required=True)
    ap.add_argument("--previous-branch-census")
    ap.add_argument("--repo",action="append",default=[])
    ap.add_argument("--test-output",required=True)
    ap.add_argument("--workflow-output",required=True)
    ap.add_argument("--branch-output",required=True)
    args=ap.parse_args()

    baseline=json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    census=json.loads(Path(args.content_census).read_text(encoding="utf-8"))
    roots={}
    for item in args.repo:
        rid,path=item.split("=",1)
        roots[rid]=Path(path).resolve()
    expected={r["repository"] for r in baseline["repositories"]}
    if set(roots)!=expected:
        raise SystemExit("repository root set does not match baseline")

    revision={r["repository"]:r["head"] for r in census["repositories"]}
    tests=[]
    for row in census["files"]:
        if row["classification"]!="CURRENT_TEST":
            continue
        tests.append({
            "repository":row["repository"],"path":row["path"],
            "test_class":test_class(row["path"]),
            "revision_named":"REVISION_NAMED" in row["flags"],
            "sha256":row["sha256"],
        })
    test_out={
        "schema":"lion.test-census/v1",
        "generator":"tools/lion_global_maintenance_projection.py",
        "invalidators":["REPOSITORY_CONTENT_CHANGE","NAMING_STANDARD_CHANGE"],
        "baseline_id":baseline["baseline_id"],
        "projection_mode":census["generated_from"]["projection_mode"],
        "tests":tests,"counts":{},"authority_effect":"NONE",
    }
    for row in tests:
        test_out["counts"][row["test_class"]]=test_out["counts"].get(row["test_class"],0)+1

    workflows=[]
    for row in census["files"]:
        if not row["path"].startswith(".github/workflows/"):
            continue
        rid=row["repository"]
        text=read_blob(roots[rid],revision[rid],row["path"])
        refs=branch_refs_from_workflow(text)
        workflows.append({
            "repository":rid,"path":row["path"],
            "workflow_class":workflow_class(row["path"],text),
            "branch_specific_refs":refs,
            "has_branch_specific_refs":bool(refs),
            "contents_write_permission":bool(re.search(r"contents:\s*write",text,re.I)),
            "sha256":row["sha256"],
        })
    workflow_out={
        "schema":"lion.workflow-census/v1",
        "generator":"tools/lion_global_maintenance_projection.py",
        "invalidators":["REPOSITORY_CONTENT_CHANGE","DEPENDENCY_CHANGE"],
        "baseline_id":baseline["baseline_id"],
        "projection_mode":census["generated_from"]["projection_mode"],
        "workflows":workflows,"counts":{},"authority_effect":"NONE",
    }
    for row in workflows:
        workflow_out["counts"][row["workflow_class"]]=workflow_out["counts"].get(row["workflow_class"],0)+1

    previous=None
    if args.previous_branch_census:
        p=Path(args.previous_branch_census)
        if p.is_file():
            previous=json.loads(p.read_text(encoding="utf-8"))
    branch_out=branch_census(baseline,roots,previous)

    Path(args.test_output).write_text(json.dumps(test_out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    Path(args.workflow_output).write_text(json.dumps(workflow_out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    Path(args.branch_output).write_text(json.dumps(branch_out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({
        "tests":len(tests),
        "workflows":len(workflows),
        "branches":len(branch_out["rows"]),
        "branch_counts":branch_out["counts"],
        "branch_specific_workflows":[w["repository"]+":"+w["path"] for w in workflows if w["has_branch_specific_refs"]],
    },indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())

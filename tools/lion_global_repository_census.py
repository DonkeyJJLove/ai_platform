#!/usr/bin/env python3
"""Generate the source-bound LION federation content census.

This tool is read-only with respect to source repositories. It classifies tracked
files, records naming signals, exact content digests, duplicate-content groups,
and bounded static-reference signals. It does not infer DELETE from lack of a
Python import alone.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any

CLASSES = {
    "CURRENT_SOURCE","CURRENT_CONTRACT","CURRENT_CONFIG","CURRENT_TEST",
    "CURRENT_DOCUMENTATION","CURRENT_GENERATED","CURRENT_RUNTIME","CURRENT_UI",
    "CURRENT_TOOL","VERSIONED_STATIC","COMPATIBILITY_LAYER","HISTORICAL",
    "HISTORICAL_EVIDENCE","ARCHIVED","GENERATED_BUT_STALE",
    "SOURCE_BUT_UNREFERENCED","DOCUMENTED_BUT_UNIMPLEMENTED",
    "IMPLEMENTED_BUT_UNDOCUMENTED","DUPLICATE_SEMANTICS",
    "DUPLICATE_IMPLEMENTATION","DUPLICATE_DOCUMENTATION","DEPRECATED",
    "DELETE_CANDIDATE","UNKNOWN",
}
README_RE = re.compile(r"(^|/)readme(?:\.md)?$", re.I)
REVISION_RE = re.compile(r"(^|[/_.-])(r\d+|e\d+|f\d+|t\d+|epoch\d+|candidate)([/_.-]|$)", re.I)

COVERAGE_RULES = (
    {
        "repository": "DonkeyJJLove/writeups",
        "path_prefix": "badania/heuristic-causal-lab-final-4.3/hcl_final_4_3/runs/",
        "classification": "CURRENT_GENERATED",
        "classification_basis": "high-volume tracked research-run output covered by generated-output policy",
        "generated_output_class": "ARCHIVED_RUN",
        "min_files": 10000,
    },
)

CURRENT_V14 = {
    "LION/architecture/v1_4/federation_current_vector.json": "CURRENT_GENERATED",
    "LION/architecture/v1_4/contract_catalog.json": "CURRENT_CONTRACT",
    "LION/architecture/v1_4/capability_catalog.json": "CURRENT_CONTRACT",
    "LION/architecture/v1_4/AUTHORIZATION_LIFECYCLE_CONTRACT.json": "VERSIONED_STATIC",
    "LION/architecture/v1_4/LION_PROCESS_CONTRACT_PLANE.md": "VERSIONED_STATIC",
}

def git(repo: Path, *args: str, binary: bool=False):
    out = subprocess.check_output(["git","-C",str(repo),*args])
    return out if binary else out.decode().strip()

def tracked(repo: Path) -> list[str]:
    raw=git(repo,"ls-files","-z",binary=True)
    return [x.decode("utf-8") for x in raw.split(b"\0") if x]

def classify(repository: str, path: str) -> tuple[str,str,list[str]]:
    p=path.lower()
    name=Path(path).name
    flags=[]
    if README_RE.search(path):
        flags.append("README")
        if name != "README.md":
            flags.append("README_CASE_NONCANONICAL")
    if REVISION_RE.search(path):
        flags.append("REVISION_NAMED")
    if path in CURRENT_V14:
        return CURRENT_V14[path], "explicit-current-v1.4-compatibility-surface", flags
    if p.startswith("lion/archive/"):
        return "ARCHIVED","archive-path",flags
    if p.startswith("lion/evidence/"):
        return "HISTORICAL_EVIDENCE","evidence-path",flags
    if p.startswith("lion/maintenance/"):
        return "HISTORICAL_EVIDENCE","maintenance-evidence-path",flags
    if p.startswith("lion/runtime_compat/") or "/compat/" in p or "legacy" in name.lower():
        return "COMPATIBILITY_LAYER","compatibility-or-legacy-path",flags
    if p.startswith("lion/architecture/v1_4/"):
        return "HISTORICAL","v1.4-noncurrent-lineage",flags
    if p.startswith(".github/workflows/"):
        return "CURRENT_CONFIG","workflow-config",flags
    if "/tests/" in "/"+p or name.startswith("test_") or name.endswith((".test.js",".test.cjs",".test.mjs")):
        return "CURRENT_TEST","test-path",flags
    if p.startswith("browser_broker/"):
        if p.endswith((".js",".cjs",".mjs",".html",".css")):
            return "CURRENT_UI","operator-shell-source",flags
        if p.endswith((".md",)):
            return "CURRENT_DOCUMENTATION","operator-shell-documentation",flags
        if p.endswith((".json",)):
            return "CURRENT_CONFIG","operator-shell-config",flags
    if p.startswith("cyber_lion/mission_control/static/") or p.startswith("cyber_lion/app_coordination/") and p.endswith((".html",".css",".js")):
        return "CURRENT_UI","panel-ui-source",flags
    if p.startswith("cyber_lion/contracts/") or "schema" in name.lower() or p.endswith(".ebnf"):
        return "CURRENT_CONTRACT","contract-or-schema-path",flags
    if p.startswith("tools/"):
        return "CURRENT_TOOL","tool-path",flags
    if p.startswith("deploy/"):
        return "CURRENT_RUNTIME","deployment-path",flags
    if p.startswith("outputs/") or "/outputs/" in "/"+p or "/generated/" in "/"+p:
        return "CURRENT_GENERATED","generated-output-path",flags
    if p.startswith("docs/"):
        return "CURRENT_DOCUMENTATION","documentation-path",flags
    if p.startswith("lion/rag/"):
        return "VERSIONED_STATIC","versioned-rag-path",flags
    if p.startswith("lion/architecture/v1_5/"):
        if p.endswith((".json",".yaml",".yml")):
            return "CURRENT_GENERATED","v1.5-architecture-machine-surface",flags
        return "CURRENT_DOCUMENTATION","v1.5-architecture-documentation",flags
    if p.startswith("lion/panel/") or p.startswith("lion/standards/"):
        if p.endswith(".json"):
            return "CURRENT_CONFIG","standard-or-panel-machine-surface",flags
        return "CURRENT_DOCUMENTATION","standard-or-panel-documentation",flags
    if p.endswith((".md",".txt",".prompt")):
        return "CURRENT_DOCUMENTATION","documentation-or-research-text",flags
    if p.endswith((".py",".js",".cjs",".mjs",".ps1",".sh",".sql")):
        return "CURRENT_SOURCE","source-extension",flags
    if p.endswith((".json",".yaml",".yml",".toml",".ini",".conf",".service",".socket",".timer",".pipeline",".lab")):
        return "CURRENT_CONFIG","config-or-data-extension",flags
    if p.endswith((".png",".jpg",".jpeg",".svg",".pdf",".xlsx",".csv",".mat",".fig",".zip")):
        return "UNKNOWN","binary-or-research-data-needs-policy",flags
    return "UNKNOWN","no-safe-classification-rule",flags

def static_python_reference_signals(repo: Path, files: list[str]) -> dict[str, Any]:
    py=[p for p in files if p.endswith(".py")]
    modules={}
    for p in py:
        m=p[:-3].replace("/",".")
        if m.endswith(".__init__"):
            m=m[:-9]
        modules[m]=p
    referenced=set()
    parse_errors=[]
    for p in py:
        try:
            tree=ast.parse((repo/p).read_text(encoding="utf-8",errors="ignore"), filename=p)
        except Exception:
            parse_errors.append(p)
            continue
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                names=[a.name for a in node.names]
            elif isinstance(node,ast.ImportFrom):
                names=[node.module or ""]
            else:
                continue
            for n in names:
                for mod,path in modules.items():
                    if n==mod or n.startswith(mod+".") or mod.startswith(n+"."):
                        referenced.add(path)
    candidates=[
        p for p in py
        if p not in referenced
        and not re.search(r"(^|/)__init__\.py$",p)
        and "/tests/" not in "/"+p
        and not Path(p).name.startswith("test_")
    ]
    return {
        "python_files":len(py),
        "statically_unreferenced_candidates":candidates,
        "parse_errors":parse_errors,
        "policy":"SIGNAL_ONLY_NOT_DELETE_PROOF",
    }

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--baseline",required=True)
    ap.add_argument("--repo",action="append",default=[],help="repository=local_checkout")
    ap.add_argument("--output",required=True)
    ap.add_argument("--overlay-repository",action="append",default=[])
    args=ap.parse_args()
    baseline=json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    roots={}
    for item in args.repo:
        rid,path=item.split("=",1)
        roots[rid]=Path(path).resolve()
    expected={r["repository"]:r for r in baseline["repositories"]}
    overlays=set(args.overlay_repository)
    if set(roots)!=set(expected):
        raise SystemExit("repository root set does not match baseline")
    if not overlays.issubset(expected):
        raise SystemExit("overlay repository escapes baseline")
    rows=[]
    repo_summary=[]
    coverage_groups=[]
    duplicates=defaultdict(list)
    output_path=Path(args.output).resolve()
    static_signals={}
    for rid in sorted(roots):
        repo=roots[rid]
        exp=expected[rid]
        head=git(repo,"rev-parse","HEAD")
        tree=git(repo,"rev-parse","HEAD^{tree}")
        if rid not in overlays and (head!=exp["head"] or tree!=exp["tree"]):
            raise SystemExit(f"baseline drift {rid}: {head}/{tree}")
        files=tracked(repo)
        counts=Counter()
        readmes=[]
        workflows=[]
        tests=[]
        grouped_paths=set()
        for rule in COVERAGE_RULES:
            if rule["repository"] != rid:
                continue
            prefix=rule["path_prefix"]
            matched=[path for path in files if path.startswith(prefix)]
            if len(matched) < int(rule["min_files"]):
                continue
            tree_path=prefix.rstrip("/")
            tree_sha=git(repo,"rev-parse",f"HEAD:{tree_path}")
            extension_counts=Counter((Path(path).suffix.lower() or "<none>") for path in matched)
            total_bytes=sum((repo/path).stat().st_size for path in matched)
            coverage_groups.append({
                "repository":rid,
                "path_prefix":prefix,
                "classification":rule["classification"],
                "classification_basis":rule["classification_basis"],
                "generated_output_class":rule["generated_output_class"],
                "file_count":len(matched),
                "total_bytes":total_bytes,
                "git_tree_sha":tree_sha,
                "extension_counts":dict(sorted(extension_counts.items())),
                "coverage_semantics":"ALL_TRACKED_FILES_UNDER_PREFIX_AT_BOUND_HEAD",
            })
            grouped_paths.update(matched)
            counts[rule["classification"]]+=len(matched)
        for path in files:
            if path in grouped_paths:
                continue
            raw=(repo/path).read_bytes()
            is_self=(repo/path).resolve()==output_path
            digest="SELF_REFERENTIAL" if is_self else sha256(raw).hexdigest()
            cls,basis,flags=classify(rid,path)
            if is_self:
                cls,basis="CURRENT_GENERATED","self-referential-generated-census-carrier"
                flags=list(flags)+["SELF_REFERENTIAL_HASH_EXEMPTION"]
            counts[cls]+=1
            if "README" in flags:
                readmes.append(path)
            if path.startswith(".github/workflows/"):
                workflows.append(path)
            if cls=="CURRENT_TEST":
                tests.append(path)
            if not is_self:
                duplicates[digest].append({"repository":rid,"path":path,"size_bytes":len(raw)})
            rows.append({
                "repository":rid,
                "path":path,
                "classification":cls,
                "classification_basis":basis,
                "size_bytes":len(raw),
                "sha256":digest,
                "naming_conformance":"NONCANONICAL_README_CASE" if "README_CASE_NONCANONICAL" in flags else "NO_KNOWN_VIOLATION",
                "flags":flags,
            })
        static_signals[rid]=static_python_reference_signals(repo,files)
        repo_summary.append({
            "repository":rid,"branch":exp["branch"],"head":head,"tree":tree,
            "baseline_head":exp["head"],"baseline_tree":exp["tree"],
            "identity_mode":"EXACT_OVERLAY" if rid in overlays else "EXACT_BASELINE",
            "tracked_files":len(files),"class_counts":dict(sorted(counts.items())),
            "materialized_file_rows":sum(1 for row in rows if row["repository"]==rid),
            "coverage_group_file_count":sum(group["file_count"] for group in coverage_groups if group["repository"]==rid),
            "readmes":readmes,"workflows":workflows,"tests_count":len(tests),
        })
    dup_groups=[]
    for digest,items in duplicates.items():
        if len(items)<2:
            continue
        repos=sorted({x["repository"] for x in items})
        if len(repos)>1 or len(items)>=3:
            dup_groups.append({"sha256":digest,"count":len(items),"repositories":repos,"items":items})
    dup_groups.sort(key=lambda x:(-len(x["repositories"]),-x["count"],x["sha256"]))
    output={
        "schema":"lion.repository-content-census/v1",
        "generator":"tools/lion_global_repository_census.py",
        "invalidators":["REPOSITORY_CONTENT_CHANGE","NAMING_STANDARD_CHANGE","DEPENDENCY_CHANGE"],
        "generated_from":{
            "baseline_id":baseline["baseline_id"],
            "architecture_epoch":baseline["architecture_epoch"],
            "repository_count":len(repo_summary),
            "tracked_file_count":sum(row["tracked_files"] for row in repo_summary),
            "materialized_file_row_count":len(rows),
            "coverage_group_file_count":sum(group["file_count"] for group in coverage_groups),
            "coverage_group_count":len(coverage_groups),
            "projection_mode":"BASELINE_PLUS_EXACT_REPOSITORY_OVERLAY" if overlays else "EXACT_BASELINE",
            "overlay_repositories":sorted(overlays),
        },
        "repositories":repo_summary,
        "files":rows,
        "coverage_groups":coverage_groups,
        "duplicate_content_groups":dup_groups,
        "static_python_reference_signals":static_signals,
        "classification_policy":{
            "unknown_is_legal":True,
            "static_unreferenced_is_delete_proof":False,
            "delete_requires":"independent consumer/runtime/history/compatibility absence evidence",
            "coverage_group_semantics":"A coverage group classifies every tracked file under its exact path prefix at the bound repository HEAD; individual rows are intentionally omitted only for those files.",
        },
        "authority_effect":"NONE",
    }
    Path(args.output).write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({
        "repositories":len(repo_summary),
        "tracked_files":sum(row["tracked_files"] for row in repo_summary),
        "materialized_rows":len(rows),
        "coverage_group_files":sum(group["file_count"] for group in coverage_groups),
        "coverage_groups":len(coverage_groups),
        "duplicates":len(dup_groups),
        "unknown":sum(1 for r in rows if r["classification"]=="UNKNOWN"),
        "noncanonical_readmes":sum(1 for r in rows if r["naming_conformance"]!="NO_KNOWN_VIOLATION"),
    },indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())

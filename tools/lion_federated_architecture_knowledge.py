#!/usr/bin/env python3
"""Deterministic federation architecture-knowledge projection.

The tool consumes a previously reacquired exact federation snapshot. It never
contacts GitHub, executes repository source, grants authority, or mutates runtime.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

DOMAIN = b"LION/FEDERATED-ARCHITECTURE-SNAPSHOT/1\0"
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")

PATH_CLASSES = (
    (re.compile(r"(^|/)AGENTS\.md$", re.I), "HUMAN_ARCHITECTURE_DOCUMENT"),
    (re.compile(r"cyber-lion\.repository\.json$", re.I), "REPOSITORY_MANIFEST"),
    (re.compile(r"semantic_owners\.json$", re.I), "SEMANTIC_OWNER_MAP"),
    (re.compile(r"contract_catalog\.json$", re.I), "CONTRACT_CATALOG"),
    (re.compile(r"capability_catalog\.json$", re.I), "CAPABILITY_CATALOG"),
    (re.compile(r"federation_current_vector\.json$", re.I), "FEDERATION_MANIFEST"),
    (re.compile(r"canonical-state.*\.json$", re.I), "TRUTH_CARRIER"),
    (re.compile(r"roadmap", re.I), "ROADMAP"),
    (re.compile(r"(^|/)ADR[-_/]", re.I), "ADR"),
    (re.compile(r"architecture", re.I), "HUMAN_ARCHITECTURE_DOCUMENT"),
    (re.compile(r"contract|schema", re.I), "MACHINE_READABLE_ARCHITECTURE"),
    (re.compile(r"rag", re.I), "RAG_ROUTING"),
    (re.compile(r"provenance", re.I), "SOURCE_PROVENANCE"),
    (re.compile(r"README(?:\.md)?$", re.I), "HUMAN_ARCHITECTURE_DOCUMENT"),
    (re.compile(r"PROCESS_GUARD\.md$", re.I), "PROCESS_CONTRACT"),
)

INFLUENCE_BY_CLASS = {
    "REPOSITORY_MANIFEST": "EVOLUTION_CONSTRAINT",
    "FEDERATION_MANIFEST": "EVOLUTION_CONSTRAINT",
    "TRUTH_CARRIER": "EVOLUTION_VALIDATION",
    "SEMANTIC_OWNER_MAP": "EVOLUTION_CONSTRAINT",
    "CONTRACT_CATALOG": "EVOLUTION_CONSTRAINT",
    "CAPABILITY_CATALOG": "EVOLUTION_CONSTRAINT",
    "ROADMAP": "EVOLUTION_MEMORY",
    "ADR": "EVOLUTION_MEMORY",
    "RAG_ROUTING": "DISCOVERABILITY_ONLY",
    "SOURCE_PROVENANCE": "EVOLUTION_VALIDATION",
    "PROCESS_CONTRACT": "EVOLUTION_CONSTRAINT",
    "MACHINE_READABLE_ARCHITECTURE": "EVOLUTION_PROJECTION",
    "HUMAN_ARCHITECTURE_DOCUMENT": "DISCOVERABILITY_ONLY",
}


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return sha256(DOMAIN + canonical_json(value)).hexdigest()


def classify_path(path: str) -> str | None:
    for pattern, artifact_class in PATH_CLASSES:
        if pattern.search(path):
            return artifact_class
    return None


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("schema") != "lion.federation-live-snapshot/v1":
        raise ValueError("unsupported snapshot schema")
    repos = snapshot.get("repositories")
    if not isinstance(repos, list) or not repos:
        raise ValueError("repositories required")
    ids = []
    for repo in repos:
        rid = repo.get("repository")
        if not isinstance(rid, str) or not REPOSITORY_RE.fullmatch(rid):
            raise ValueError("invalid repository")
        ids.append(rid)
        if not SHA40_RE.fullmatch(str(repo.get("head", ""))) or not SHA40_RE.fullmatch(str(repo.get("tree", ""))):
            raise ValueError("exact repository head/tree required")
        if not isinstance(repo.get("manifest"), dict):
            raise ValueError("decoded manifest required")
        files = repo.get("files")
        if not isinstance(files, list):
            raise ValueError("repository files required")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate repository")
    if len(repos) != 10:
        raise ValueError("expected ten-repository federation")


def federation_identity(snapshot: dict[str, Any]) -> dict[str, Any]:
    _validate_snapshot(snapshot)
    rows = [
        {
            "repository": repo["repository"],
            "branch": repo["branch"],
            "head": repo["head"],
            "tree": repo["tree"],
            "manifest_blob": repo["manifest_blob"],
        }
        for repo in sorted(snapshot["repositories"], key=lambda row: row["repository"])
    ]
    return {"repositories": rows, "digest": digest(rows)}


def build_census(snapshot: dict[str, Any]) -> dict[str, Any]:
    federation = federation_identity(snapshot)
    rows = []
    for repo in sorted(snapshot["repositories"], key=lambda row: row["repository"]):
        manifest = repo["manifest"]
        declared = {
            item["path"]: item
            for item in manifest.get("architecture_knowledge", {}).get("architecture_artifacts", [])
        }
        for file in sorted(repo["files"], key=lambda row: row["path"]):
            path = file["path"]
            artifact_class = classify_path(path)
            if artifact_class is None and path not in declared:
                continue
            meta = declared.get(path, {})
            if path in declared:
                class_map = {
                    "HUMAN_ARCHITECTURE_DOCUMENT": "HUMAN_ARCHITECTURE_DOCUMENT",
                    "MACHINE_READABLE_ARCHITECTURE": "MACHINE_READABLE_ARCHITECTURE",
                    "CONTRACT": "MACHINE_READABLE_ARCHITECTURE",
                    "SCHEMA": "MACHINE_READABLE_ARCHITECTURE",
                    "ROADMAP": "ROADMAP",
                    "PROCESS_GUARD": "PROCESS_CONTRACT",
                    "RESEARCH_ARCHITECTURE": "HUMAN_ARCHITECTURE_DOCUMENT",
                    "GENERATED_PROJECTION": "GENERATED_DOCUMENTATION",
                }
                artifact_class = class_map.get(meta.get("class"), artifact_class)
            artifact_class = artifact_class or "HUMAN_ARCHITECTURE_DOCUMENT"
            currentness_hint = meta.get("currentness", "SOURCE_BOUND")
            currentness = "HISTORICAL" if currentness_hint == "HISTORICAL" else "CURRENT"
            rows.append({
                "artifact_id": f"{repo['repository']}:{path}",
                "repository": repo["repository"],
                "repository_head": repo["head"],
                "repository_tree": repo["tree"],
                "path": path,
                "blob": file.get("blob"),
                "artifact_class": artifact_class,
                "currentness": currentness,
                "declared_by_manifest": path in declared,
                "influence_class": INFLUENCE_BY_CLASS.get(artifact_class, "HUMAN_ONLY"),
            })
    return {
        "schema": "lion.architecture-document-census/v1",
        "federation_digest": federation["digest"],
        "artifact_count": len(rows),
        "artifacts": rows,
        "authority_effect": "NONE",
        "census_digest": digest(rows),
    }


def build_role_matrix(snapshot: dict[str, Any]) -> dict[str, Any]:
    federation = federation_identity(snapshot)
    rows = []
    for repo in sorted(snapshot["repositories"], key=lambda row: row["repository"]):
        manifest = repo["manifest"]
        knowledge = manifest.get("architecture_knowledge", {})
        rows.append({
            "repository": repo["repository"],
            "branch": repo["branch"],
            "head": repo["head"],
            "tree": repo["tree"],
            "tile_id": manifest["cyber_lion"]["tile_id"],
            "roles": manifest["cyber_lion"]["roles"],
            "layers": manifest["cyber_lion"]["layers"],
            "capabilities": manifest["capabilities"],
            "maximum_authority": manifest["authority"]["maximum_level"],
            "semantic_exports": knowledge.get("semantic_exports", []),
            "semantic_imports": knowledge.get("semantic_imports", []),
            "global_owner": knowledge.get("global_owner"),
        })
    return {
        "schema": "lion.repository-role-matrix/v1",
        "federation_digest": federation["digest"],
        "repositories": rows,
        "authority_effect": "NONE",
        "matrix_digest": digest(rows),
    }


def build_dependency_graph(snapshot: dict[str, Any]) -> dict[str, Any]:
    federation = federation_identity(snapshot)
    known = {repo["repository"] for repo in snapshot["repositories"]}
    edges = []
    for repo in sorted(snapshot["repositories"], key=lambda row: row["repository"]):
        source = repo["repository"]
        knowledge = repo["manifest"].get("architecture_knowledge", {})
        for target in sorted(knowledge.get("repository_dependencies", [])):
            if target not in known:
                raise ValueError(f"dependency escapes federation: {source}->{target}")
            edges.append({
                "source": source,
                "target": target,
                "relation": "DEPENDS_ON",
                "evidence_ref": f"{source}:cyber-lion.repository.json#architecture_knowledge.repository_dependencies",
            })
        owner = knowledge.get("global_owner")
        if owner and owner != source:
            if owner not in known:
                raise ValueError("global owner escapes federation")
            edges.append({
                "source": source,
                "target": owner,
                "relation": "GLOBAL_ARCHITECTURE_OWNER",
                "evidence_ref": f"{source}:cyber-lion.repository.json#architecture_knowledge.global_owner",
            })
    unique = {(e["source"], e["target"], e["relation"]): e for e in edges}
    rows = [unique[key] for key in sorted(unique)]
    return {
        "schema": "lion.cross-repository-dependency-graph/v1",
        "federation_digest": federation["digest"],
        "nodes": sorted(known),
        "edges": rows,
        "cycle_policy": "typed provider/control feedback cycles are allowed; execution DAGs remain separately acyclic",
        "authority_effect": "NONE",
        "graph_digest": digest(rows),
    }


def build_document_graph(snapshot: dict[str, Any], census: dict[str, Any]) -> dict[str, Any]:
    by_repo: dict[str, dict[str, dict[str, Any]]] = {}
    for artifact in census["artifacts"]:
        by_repo.setdefault(artifact["repository"], {})[artifact["path"]] = artifact
    edges = []
    global_vector = by_repo.get("DonkeyJJLove/ai_platform", {}).get("LION/architecture/v1_4/federation_current_vector.json")
    global_v15 = by_repo.get("DonkeyJJLove/ai_platform", {}).get("LION/architecture/v1_5/README.md")
    for repo in snapshot["repositories"]:
        rid = repo["repository"]
        docs = by_repo.get(rid, {})
        manifest = docs.get("cyber-lion.repository.json")
        agents = docs.get("AGENTS.md")
        if agents and manifest:
            edges.append({"source": agents["artifact_id"], "target": manifest["artifact_id"], "relation": "ROUTED_BY", "evidence_ref": f"{rid}:AGENTS.md"})
        if manifest and global_vector and rid != "DonkeyJJLove/ai_platform":
            edges.append({"source": manifest["artifact_id"], "target": global_vector["artifact_id"], "relation": "REFERENCES", "evidence_ref": f"{rid}:cyber-lion.repository.json"})
        if agents and global_v15 and rid != "DonkeyJJLove/ai_platform":
            edges.append({"source": agents["artifact_id"], "target": global_v15["artifact_id"], "relation": "DISCOVERED_FROM", "evidence_ref": f"{rid}:AGENTS.md"})
        knowledge = repo["manifest"].get("architecture_knowledge", {})
        for declared in knowledge.get("architecture_artifacts", []):
            target = docs.get(declared["path"])
            if manifest and target and manifest["artifact_id"] != target["artifact_id"]:
                edges.append({"source": manifest["artifact_id"], "target": target["artifact_id"], "relation": "PROJECTS", "evidence_ref": f"{rid}:cyber-lion.repository.json"})
    rows = sorted(edges, key=lambda row: (row["source"], row["target"], row["relation"], row["evidence_ref"]))
    return {
        "schema": "lion.architecture-document-graph/v1",
        "federation_digest": census["federation_digest"],
        "nodes": [row["artifact_id"] for row in census["artifacts"]],
        "edges": rows,
        "authority_effect": "NONE",
        "graph_digest": digest(rows),
    }


def build_reconciliation(snapshot: dict[str, Any], census: dict[str, Any]) -> dict[str, Any]:
    observed = {
        (artifact["repository"], artifact["path"]): artifact
        for artifact in census["artifacts"]
    }
    rows = []
    contradictions = []
    for repo in sorted(snapshot["repositories"], key=lambda row: row["repository"]):
        rid = repo["repository"]
        knowledge = repo["manifest"].get("architecture_knowledge")
        if not knowledge:
            rows.append({"repository": rid, "concept": "architecture_knowledge", "classification": "CODE_UNDOCUMENTED", "evidence_refs": [f"{rid}:cyber-lion.repository.json"]})
            continue
        for declared in knowledge.get("architecture_artifacts", []):
            key = (rid, declared["path"])
            state = "ALIGNED_CURRENT" if key in observed else "DOCUMENTATION_STALE"
            rows.append({"repository": rid, "concept": declared["path"], "classification": state, "evidence_refs": [f"{rid}:cyber-lion.repository.json", f"{rid}:{declared['path']}"]})
            if state != "ALIGNED_CURRENT":
                contradictions.append({"repository": rid, "path": declared["path"], "classification": state})
        entry = knowledge.get("discoverability", {}).get("entrypoint")
        if entry and (rid, entry) not in observed:
            contradictions.append({"repository": rid, "path": entry, "classification": "DISCOVERABILITY_MISSING"})
    return {
        "schema": "lion.architecture-reconciliation/v1",
        "federation_digest": census["federation_digest"],
        "results": rows,
        "contradictions": contradictions,
        "unknowns": [],
        "authority_effect": "NONE",
        "reconciliation_digest": digest({"results": rows, "contradictions": contradictions}),
    }


def project(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    census = build_census(snapshot)
    return {
        "ARCHITECTURE_DOCUMENT_CENSUS.json": census,
        "ARCHITECTURE_DOCUMENT_GRAPH.json": build_document_graph(snapshot, census),
        "REPOSITORY_ROLE_MATRIX.json": build_role_matrix(snapshot),
        "CROSS_REPOSITORY_DEPENDENCY_GRAPH.json": build_dependency_graph(snapshot),
        "ARCHITECTURE_RECONCILIATION.json": build_reconciliation(snapshot, census),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    outputs = project(snapshot)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, value in outputs.items():
        (out / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"outputs": sorted(outputs), "federation_digest": federation_identity(snapshot)["digest"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

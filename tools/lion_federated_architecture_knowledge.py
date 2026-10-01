#!/usr/bin/env python3
"""Deterministic federation architecture-knowledge projection.

The tool consumes a previously reacquired exact federation snapshot. It never
contacts GitHub, executes repository source, grants authority, or mutates
runtime. For the global owner it may overlay an exact local Git commit so a
candidate does not reason about its own stale manifest from the federation
baseline snapshot.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any

DOMAIN = b"LION/FEDERATED-ARCHITECTURE-SNAPSHOT/1\0"
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
GLOBAL_OWNER = "DonkeyJJLove/ai_platform"
META_CENSUS_PATHS = frozenset({
    "LION/architecture/v1_5/REPOSITORY_CONTENT_CENSUS.json",
    "LION/architecture/v1_5/BRANCH_RECONCILIATION_R1.json",
    "LION/architecture/v1_5/TEST_CENSUS.json",
    "LION/architecture/v1_5/WORKFLOW_CENSUS.json",
})

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
    "GENERATED_DOCUMENTATION": "EVOLUTION_PROJECTION",
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


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return sha1(header + raw).hexdigest()


def overlay_repository_snapshot(snapshot: dict[str, Any], replacement: dict[str, Any]) -> dict[str, Any]:
    """Replace one exact repository observation without mutating the baseline object."""
    result = deepcopy(snapshot)
    repos = result.get("repositories", [])
    rid = replacement.get("repository")
    matches = [i for i, row in enumerate(repos) if row.get("repository") == rid]
    if len(matches) != 1:
        raise ValueError("overlay repository must exist exactly once")
    repos[matches[0]] = deepcopy(replacement)
    result["projection_mode"] = "FEDERATION_BASELINE_PLUS_EXACT_REPOSITORY_OVERLAY"
    result["overlay_repository"] = rid
    _validate_snapshot(result)
    return result


def overlay_local_owner(snapshot: dict[str, Any], source_root: str | Path) -> dict[str, Any]:
    """Overlay ai_platform from an exact local Git commit.

    This fixes the bootstrap paradox where the federation baseline is older
    than the global owner's architecture-knowledge change. Generated artifacts
    bind to this explicit source commit; they are not interpreted as live
    authority or runtime truth.
    """
    root = Path(source_root).resolve()
    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    branch = git("branch", "--show-current")
    baseline = next(row for row in snapshot["repositories"] if row["repository"] == GLOBAL_OWNER)
    if not branch:
        branch = baseline["branch"]

    manifest_path = root / "cyber-lion.repository.json"
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw.decode("utf-8"))

    files: list[dict[str, str]] = []
    tree_text = git("ls-tree", "-r", "--full-tree", "HEAD")
    for line in tree_text.splitlines():
        meta, path = line.split("\t", 1)
        _mode, object_type, object_sha = meta.split(" ", 2)
        if object_type == "blob":
            files.append({"path": path, "blob": object_sha})

    replacement = {
        "repository": GLOBAL_OWNER,
        "branch": branch,
        "head": head,
        "tree": tree,
        "manifest_blob": _git_blob_sha(manifest_raw),
        "manifest": manifest,
        "files": sorted(files, key=lambda row: row["path"]),
    }
    return overlay_repository_snapshot(snapshot, replacement)


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
            if repo["repository"] == GLOBAL_OWNER and path in META_CENSUS_PATHS:
                continue
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
            generated_projection = artifact_class == "GENERATED_DOCUMENTATION"
            blob_binding = "GENERATOR_OWNED" if generated_projection else file.get("blob")
            currentness_hint = meta.get("currentness", "SOURCE_BOUND")
            if currentness_hint == "HISTORICAL":
                currentness = "HISTORICAL"
            elif currentness_hint == "VERSIONED_STATIC":
                currentness = "VERSIONED_STATIC"
            else:
                currentness = "CURRENT"
            rows.append({
                "artifact_id": f"{repo['repository']}:{path}",
                "repository": repo["repository"],
                "repository_head": repo["head"],
                "repository_tree": repo["tree"],
                "path": path,
                "blob": blob_binding,
                "content_binding": "GENERATOR_OWNED" if generated_projection else "EXACT_GIT_BLOB",
                "artifact_class": artifact_class,
                "currentness": currentness,
                "declared_currentness": currentness_hint,
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
    owner_docs = by_repo.get(GLOBAL_OWNER, {})
    global_vector = owner_docs.get("LION/architecture/v1_4/federation_current_vector.json")
    global_v15 = owner_docs.get("LION/architecture/v1_5/README.md")
    public_readme = owner_docs.get("README.md")
    project_readme = owner_docs.get("LION/README.md")

    def add_ref(source: dict[str, Any] | None, target: dict[str, Any] | None, evidence: str) -> None:
        if source and target and source["artifact_id"] != target["artifact_id"]:
            edges.append({
                "source": source["artifact_id"],
                "target": target["artifact_id"],
                "relation": "REFERENCES",
                "evidence_ref": evidence,
            })

    add_ref(public_readme, project_readme, f"{GLOBAL_OWNER}:README.md")
    add_ref(public_readme, global_v15, f"{GLOBAL_OWNER}:README.md")
    add_ref(project_readme, global_v15, f"{GLOBAL_OWNER}:LION/README.md")

    for repo in snapshot["repositories"]:
        rid = repo["repository"]
        docs = by_repo.get(rid, {})
        manifest = docs.get("cyber-lion.repository.json")
        agents = docs.get("AGENTS.md")
        if agents and manifest:
            edges.append({"source": agents["artifact_id"], "target": manifest["artifact_id"], "relation": "ROUTED_BY", "evidence_ref": f"{rid}:AGENTS.md"})
        if manifest and global_vector and rid != GLOBAL_OWNER:
            edges.append({"source": manifest["artifact_id"], "target": global_vector["artifact_id"], "relation": "REFERENCES", "evidence_ref": f"{rid}:cyber-lion.repository.json"})
        if agents and global_v15 and rid != GLOBAL_OWNER:
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


def build_reconciliation(
    snapshot: dict[str, Any],
    census: dict[str, Any],
    code_derived: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observed = {
        (artifact["repository"], artifact["path"]): artifact
        for artifact in census["artifacts"]
    }
    rows = []
    contradictions = []
    unknowns = []
    for repo in sorted(snapshot["repositories"], key=lambda row: row["repository"]):
        rid = repo["repository"]
        knowledge = repo["manifest"].get("architecture_knowledge")
        if not knowledge:
            rows.append({"repository": rid, "concept": "architecture_knowledge", "classification": "CODE_UNDOCUMENTED", "evidence_refs": [f"{rid}:cyber-lion.repository.json"]})
            continue
        for declared in knowledge.get("architecture_artifacts", []):
            key = (rid, declared["path"])
            if key not in observed:
                state = "DOCUMENTATION_STALE"
            elif declared.get("currentness") == "HISTORICAL":
                state = "ALIGNED_HISTORICAL"
            elif declared.get("currentness") == "VERSIONED_STATIC":
                state = "ALIGNED_VERSIONED_STATIC"
            else:
                state = "ALIGNED_CURRENT"
            rows.append({"repository": rid, "concept": declared["path"], "classification": state, "evidence_refs": [f"{rid}:cyber-lion.repository.json", f"{rid}:{declared['path']}"]})
            if state == "DOCUMENTATION_STALE":
                contradictions.append({"repository": rid, "path": declared["path"], "classification": state})
        entry = knowledge.get("discoverability", {}).get("entrypoint")
        if entry and (rid, entry) not in observed:
            contradictions.append({"repository": rid, "path": entry, "classification": "DISCOVERABILITY_MISSING"})

    owner = next(repo for repo in snapshot["repositories"] if repo["repository"] == GLOBAL_OWNER)
    if code_derived is None:
        unknowns.append({
            "repository": GLOBAL_OWNER,
            "concept": "CODE_DERIVED_ARCHITECTURE.json",
            "classification": "CODE_PROJECTION_UNBOUND",
            "evidence_refs": [f"{GLOBAL_OWNER}:LION/architecture/v1_5/CODE_DERIVED_ARCHITECTURE.json"],
        })
    else:
        projection_tree = code_derived.get("projection_input_tree")
        model_digest = code_derived.get("model_digest")
        if (
            code_derived.get("schema") != "lion.code-derived-architecture/v1"
            or not SHA40_RE.fullmatch(str(projection_tree or ""))
            or not re.fullmatch(r"[0-9a-f]{64}", str(model_digest or ""))
        ):
            raise ValueError("invalid code-derived architecture projection")
        state = "ALIGNED_CURRENT" if projection_tree == owner["tree"] else "CODE_PROJECTION_STALE"
        row = {
            "repository": GLOBAL_OWNER,
            "concept": "CODE_DERIVED_ARCHITECTURE.json#projection_input_tree",
            "classification": state,
            "evidence_refs": [
                f"{GLOBAL_OWNER}:LION/architecture/v1_5/CODE_DERIVED_ARCHITECTURE.json",
                f"{GLOBAL_OWNER}:tree:{owner['tree']}",
            ],
        }
        rows.append(row)
        if state != "ALIGNED_CURRENT":
            contradictions.append({
                "repository": GLOBAL_OWNER,
                "path": "LION/architecture/v1_5/CODE_DERIVED_ARCHITECTURE.json",
                "classification": state,
                "expected_tree": owner["tree"],
                "observed_tree": projection_tree,
            })

    reconciliation_payload = {
        "results": rows,
        "contradictions": contradictions,
        "unknowns": unknowns,
    }
    return {
        "schema": "lion.architecture-reconciliation/v1",
        "federation_digest": census["federation_digest"],
        **reconciliation_payload,
        "authority_effect": "NONE",
        "reconciliation_digest": digest(reconciliation_payload),
    }


def build_currentness_model(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "lion.documentation-currentness-model/v1",
        "federation_digest": federation_identity(snapshot)["digest"],
        "projection_mode": snapshot.get("projection_mode", "EXACT_FEDERATION_SNAPSHOT"),
        "evidence_identity_types": {
            "LIVE_REPOSITORY_OBSERVATION": "freshly reacquired default-branch Git identity for the claim being made",
            "EPOCH_CURRENTNESS_CARRIER": "immutable carrier binding a stabilized epoch subject",
            "SOURCE_BOUND_PROJECTION": "deterministic projection bound to explicit source identities",
            "CANDIDATE_BINDING": "pre-integration candidate identity used by formalization/verification",
            "HISTORICAL_EVIDENCE": "immutable evidence of a past event or architecture epoch",
        },
        "evidence_invariants": [
            "STORED_SNAPSHOT_IS_NOT_SELF_REFRESHING_LIVE_TRUTH",
            "HISTORICAL_CARRIERS_ARE_NOT_REWRITTEN_TO_LATER_HEADS",
            "CURRENT_CLAIMS_REQUIRE_REACQUISITION",
            "PROJECTIONS_DECLARE_EXACT_INPUT_IDENTITY",
        ],
        "dimensions": {
            "REPOSITORY_CURRENT": {
                "owner": "exact Git observation",
                "rule": "repository state must be reacquired for the claim being made; stored snapshots are source-bound evidence, not self-refreshing live truth",
            },
            "DOCUMENT_CURRENT": {
                "owner": "artifact source binding + semantic owner",
                "rule": "document source dependencies and invalidators must be current for the document claim",
            },
            "PUBLIC_ENTRYPOINT_CURRENT": {
                "owner": "README.md + LION/README.md + v1.5 architecture root",
                "rule": "public/project entrypoints are declared architecture artifacts and must route to the current architecture epoch",
            },
            "PROJECTION_CURRENT": {
                "owner": "deterministic generator",
                "rule": "projection digest derives from exact source-bound inputs; generator ownership must match the actual generator",
            },
            "FEDERATION_CURRENT": {
                "owner": "federation_current_vector",
                "rule": "all required repository observations are exact and reconciled for the bound epoch",
            },
            "RUNTIME_CURRENT": {
                "owner": "runtime observation",
                "rule": "never inferred from Git or documentation",
            },
            "RAG_CURRENT": {
                "owner": "versioned RAG release/current source set",
                "rule": "RAG is versioned knowledge, never live truth",
            },
            "FORMALIZATION_CURRENT": {
                "owner": "AFM/RFS/FCR + federated binding",
                "rule": "exact candidate and all required surfaces close without UNKNOWN",
            },
        },
        "states": [
            "CURRENT", "STALE", "UNKNOWN", "SUPERSEDED", "TARGET_ONLY",
            "CONTRACT_ONLY", "PARTIALLY_IMPLEMENTED", "VERSIONED_STATIC",
        ],
        "invalidation_pipeline": [
            "repository/source change",
            "affected semantic exports/imports",
            "global semantic owner lookup",
            "cross-repository dependency traversal",
            "RequiredFormalizationSet",
            "architecture documents/projections invalidated",
            "public/project entrypoints invalidated when architecture epoch or routed currentness changes",
            "regenerate machine projections from exact source-bound inputs",
            "refresh public/project entrypoints before discoverability closes",
            "RAG/discoverability invalidated when required",
            "federation vector regenerated after integration",
            "truth carriers regenerated last",
        ],
        "historical_surfaces": {
            "LION/architecture/v1_4/current_state.json": "SUPERSEDED_AS_LIVE_CURRENTNESS_OWNER",
            "LION/architecture/v1_4/semantic_owners.json": "HISTORICAL_COMPATIBILITY_PROJECTION",
            "AI_NATIVE_ROADMAP.md": "HISTORICAL_ROADMAP_INPUT",
        },
        "authority_effect": "NONE",
    }


def build_document_derived(
    snapshot: dict[str, Any],
    census: dict[str, Any],
    role_matrix: dict[str, Any],
    semantic_owners: dict[str, Any],
) -> dict[str, Any]:
    owners = semantic_owners.get("owners")
    if not isinstance(owners, list):
        raise ValueError("semantic owner map must contain owners")
    by_repo = Counter(row["repository"] for row in census["artifacts"])
    by_class = Counter(row["artifact_class"] for row in census["artifacts"])
    owner_row = next(row for row in snapshot["repositories"] if row["repository"] == GLOBAL_OWNER)
    payload = {
        "projection_input_tree": owner_row["tree"],
        "source_federation_digest": census["federation_digest"],
        "semantic_owners": owners,
        "repository_roles": role_matrix["repositories"],
        "architecture_documents": {
            "artifact_count": census["artifact_count"],
            "by_repository": dict(sorted(by_repo.items())),
            "by_class": dict(sorted(by_class.items())),
        },
        "projection_mode": snapshot.get("projection_mode", "EXACT_FEDERATION_SNAPSHOT"),
        "authority_effect": "NONE",
    }
    return {
        "schema": "lion.document-derived-architecture/v1",
        **payload,
        "projection_digest": digest(payload),
    }


def project(
    snapshot: dict[str, Any],
    *,
    semantic_owners: dict[str, Any] | None = None,
    code_derived: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    census = build_census(snapshot)
    role_matrix = build_role_matrix(snapshot)
    outputs = {
        "ARCHITECTURE_DOCUMENT_CENSUS.json": census,
        "ARCHITECTURE_DOCUMENT_GRAPH.json": build_document_graph(snapshot, census),
        "REPOSITORY_ROLE_MATRIX.json": role_matrix,
        "CROSS_REPOSITORY_DEPENDENCY_GRAPH.json": build_dependency_graph(snapshot),
        "ARCHITECTURE_RECONCILIATION.json": build_reconciliation(snapshot, census, code_derived),
        "DOCUMENTATION_CURRENTNESS_MODEL.json": build_currentness_model(snapshot),
    }
    if semantic_owners is not None:
        outputs["DOCUMENT_DERIVED_ARCHITECTURE.json"] = build_document_derived(
            snapshot, census, role_matrix, semantic_owners
        )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--local-owner-root")
    parser.add_argument("--semantic-owners")
    parser.add_argument("--code-derived")
    args = parser.parse_args()
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    if args.local_owner_root:
        snapshot = overlay_local_owner(snapshot, args.local_owner_root)

    semantic_owners = None
    if args.semantic_owners:
        semantic_owners = json.loads(Path(args.semantic_owners).read_text(encoding="utf-8"))
    elif args.local_owner_root:
        semantic_owners = json.loads(
            (Path(args.local_owner_root) / "LION/architecture/v1_5/semantic_owners.json").read_text(encoding="utf-8")
        )

    code_derived = None
    if args.code_derived:
        code_derived = json.loads(Path(args.code_derived).read_text(encoding="utf-8"))
    elif args.local_owner_root:
        code_path = Path(args.local_owner_root) / "LION/architecture/v1_5/CODE_DERIVED_ARCHITECTURE.json"
        if code_path.is_file():
            code_derived = json.loads(code_path.read_text(encoding="utf-8"))

    outputs = project(snapshot, semantic_owners=semantic_owners, code_derived=code_derived)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, value in outputs.items():
        (out / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "outputs": sorted(outputs),
        "federation_digest": federation_identity(snapshot)["digest"],
        "projection_mode": snapshot.get("projection_mode", "EXACT_FEDERATION_SNAPSHOT"),
        "overlay_repository": snapshot.get("overlay_repository"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

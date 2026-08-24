"""CLI for deterministic Code Perception P1 projection generation."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from cyber_lion.contracts.enterprise_graph import canonical_json
from cyber_lion.enterprise.code_perception import (
    build_from_git,
    empty_analysis_document,
    graph_schema_document,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(payload) + b"\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic LION code perception projection")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    graph, manifest = build_from_git(
        args.repo_root,
        args.repository,
        args.commit,
        expected_tree=args.expected_tree,
    )
    out = Path(args.out_dir)
    _write(out / "schema.json", graph_schema_document())
    _write(out / "code_graph.json", graph.logical_payload())
    _write(out / "analysis_graph.json", empty_analysis_document(graph.source, graph.digest()))
    _write(out / "manifest.json", asdict(manifest))
    print(graph.digest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

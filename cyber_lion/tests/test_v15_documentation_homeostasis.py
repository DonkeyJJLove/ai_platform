import json
from pathlib import Path
import unittest

from tools.lion_federated_architecture_knowledge import (
    build_census,
    build_currentness_model,
    build_document_graph,
    build_reconciliation,
    build_role_matrix,
    build_document_derived,
    overlay_repository_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
V15 = ROOT / "LION/architecture/v1_5"


def _base_snapshot():
    snapshot = json.loads((V15 / "FEDERATION_LIVE_SNAPSHOT.json").read_text(encoding="utf-8"))
    owner = next(row for row in snapshot["repositories"] if row["repository"] == "DonkeyJJLove/ai_platform")
    current_manifest = json.loads((ROOT / "cyber-lion.repository.json").read_text(encoding="utf-8"))
    replacement = dict(owner)
    replacement["manifest"] = current_manifest
    replacement["manifest_blob"] = "f" * 40
    current_files = {row["path"]: row for row in owner["files"]}
    for declared in current_manifest["architecture_knowledge"]["architecture_artifacts"]:
        path = declared["path"]
        if (ROOT / path).is_file():
            current_files.setdefault(path, {"path": path, "blob": "e" * 40})
    replacement["files"] = sorted(current_files.values(), key=lambda row: row["path"])
    return overlay_repository_snapshot(snapshot, replacement)


class V15DocumentationHomeostasisTests(unittest.TestCase):
    def test_public_entrypoints_are_declared_architecture_artifacts(self):
        manifest = json.loads((ROOT / "cyber-lion.repository.json").read_text(encoding="utf-8"))
        artifacts = {
            row["path"]: row for row in manifest["architecture_knowledge"]["architecture_artifacts"]
        }
        self.assertEqual(artifacts["README.md"]["currentness"], "LOCAL_OWNER")
        self.assertEqual(artifacts["LION/README.md"]["currentness"], "LOCAL_OWNER")
        self.assertEqual(artifacts["LION/architecture/v1_5/README.md"]["currentness"], "LOCAL_OWNER")

    def test_public_entrypoints_route_to_v15(self):
        root = (ROOT / "README.md").read_text(encoding="utf-8")
        lion = (ROOT / "LION/README.md").read_text(encoding="utf-8")
        self.assertIn("LION/architecture/v1_5/README.md", root)
        self.assertIn("DOCUMENTATION_CURRENTNESS_MODEL.json", root)
        self.assertIn("Bieżąca dokumentacja v1.5", lion)
        self.assertIn("architecture/v1_5/README.md", lion)
        self.assertNotIn("## Bieżąca dokumentacja v1.4", lion)

    def test_owner_overlay_removes_false_code_undocumented(self):
        snapshot = _base_snapshot()
        census = build_census(snapshot)
        reconciliation = build_reconciliation(snapshot, census)
        owner_rows = [
            row for row in reconciliation["results"]
            if row["repository"] == "DonkeyJJLove/ai_platform"
        ]
        self.assertTrue(owner_rows)
        self.assertFalse(any(row["classification"] == "CODE_UNDOCUMENTED" for row in owner_rows))
        self.assertFalse(any(
            row["repository"] == "DonkeyJJLove/ai_platform"
            for row in reconciliation["contradictions"]
        ))

    def test_code_projection_tree_mismatch_fails_closed(self):
        snapshot = _base_snapshot()
        census = build_census(snapshot)
        stale_projection = {
            "schema": "lion.code-derived-architecture/v1",
            "projection_input_tree": "0" * 40,
            "model_digest": "a" * 64,
        }
        reconciliation = build_reconciliation(snapshot, census, stale_projection)
        self.assertTrue(any(
            row["classification"] == "CODE_PROJECTION_STALE"
            for row in reconciliation["contradictions"]
        ))

    def test_document_graph_contains_public_entrypoint_routes(self):
        snapshot = _base_snapshot()
        census = build_census(snapshot)
        graph = build_document_graph(snapshot, census)
        edges = {
            (row["source"], row["target"], row["relation"])
            for row in graph["edges"]
        }
        self.assertIn((
            "DonkeyJJLove/ai_platform:README.md",
            "DonkeyJJLove/ai_platform:LION/README.md",
            "REFERENCES",
        ), edges)
        self.assertIn((
            "DonkeyJJLove/ai_platform:LION/README.md",
            "DonkeyJJLove/ai_platform:LION/architecture/v1_5/README.md",
            "REFERENCES",
        ), edges)

    def test_materialized_v15_documentation_state_is_closed(self):
        reconciliation = json.loads(
            (V15 / "ARCHITECTURE_RECONCILIATION.json").read_text(encoding="utf-8")
        )
        code = json.loads((V15 / "CODE_DERIVED_ARCHITECTURE.json").read_text(encoding="utf-8"))
        document = json.loads(
            (V15 / "DOCUMENT_DERIVED_ARCHITECTURE.json").read_text(encoding="utf-8")
        )
        graph = json.loads((V15 / "ARCHITECTURE_DOCUMENT_GRAPH.json").read_text(encoding="utf-8"))
        census = json.loads((V15 / "ARCHITECTURE_DOCUMENT_CENSUS.json").read_text(encoding="utf-8"))

        self.assertEqual(reconciliation["contradictions"], [])
        self.assertEqual(reconciliation["unknowns"], [])
        self.assertEqual(code["projection_input_tree"], document["projection_input_tree"])
        self.assertRegex(code["projection_input_tree"], r"^[0-9a-f]{40}$")
        self.assertTrue(any(
            row["classification"] == "ALIGNED_CURRENT"
            and row["concept"] == "CODE_DERIVED_ARCHITECTURE.json#projection_input_tree"
            for row in reconciliation["results"]
        ))
        ids = {row["artifact_id"] for row in census["artifacts"]}
        self.assertIn("DonkeyJJLove/ai_platform:README.md", ids)
        self.assertIn("DonkeyJJLove/ai_platform:LION/README.md", ids)
        self.assertIn("DonkeyJJLove/ai_platform:LION/architecture/v1_5/README.md", ids)
        edges = {(row["source"], row["target"], row["relation"]) for row in graph["edges"]}
        self.assertIn((
            "DonkeyJJLove/ai_platform:README.md",
            "DonkeyJJLove/ai_platform:LION/README.md",
            "REFERENCES",
        ), edges)

    def test_generator_owns_currentness_and_document_projection_for_real(self):
        snapshot = _base_snapshot()
        census = build_census(snapshot)
        roles = build_role_matrix(snapshot)
        owners = json.loads((V15 / "semantic_owners.json").read_text(encoding="utf-8"))
        currentness = build_currentness_model(snapshot)
        derived = build_document_derived(snapshot, census, roles, owners)
        self.assertIn("PUBLIC_ENTRYPOINT_CURRENT", currentness["dimensions"])
        self.assertEqual(derived["schema"], "lion.document-derived-architecture/v1")
        self.assertEqual(derived["source_federation_digest"], census["federation_digest"])
        self.assertEqual(derived["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()

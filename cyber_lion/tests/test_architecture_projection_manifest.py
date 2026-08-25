import unittest
from dataclasses import replace
from cyber_lion.architecture_projection.model import CanonicalDiagramModel, DiagramNode
from cyber_lion.architecture_projection.manifest import build_manifest
from cyber_lion.architecture_projection.plantuml import serialize_plantuml


class ArchitectureProjectionManifestTests(unittest.TestCase):
    def test_manifest_binds_tree_model_tool_and_artifact(self):
        model = CanonicalDiagramModel(
            "lion-system-component-map",
            "component",
            "f" * 40,
            (DiagramNode("n_a", "A", "component", "a.py", "a" * 64),),
            (),
        ).validate()
        puml = serialize_plantuml(model)
        manifest = build_manifest(
            model=model,
            artifact=puml,
            plantuml_version="1.2026.6",
            plantuml_binary_digest="a" * 64,
            rendering_mode="PUML_ONLY",
        )
        self.assertEqual(manifest.source_tree_sha, "f" * 40)
        self.assertEqual(manifest.diagram_source_digest, model.source_digest())
        self.assertEqual(manifest.authority_effect, "NONE")
        self.assertEqual(manifest.runtime_evidence, "NONE")

    def test_manifest_rejects_non_sha40_tree_and_authority(self):
        model = CanonicalDiagramModel(
            "x", "component", "f" * 40,
            (DiagramNode("n_a", "A", "component", "a.py", "a" * 64),), (),
        ).validate()
        manifest = build_manifest(model=model, artifact=b"x", plantuml_version="1.2026.6", plantuml_binary_digest="a" * 64, rendering_mode="PUML_ONLY")
        with self.assertRaises(ValueError):
            replace(manifest, source_tree_sha="not-a-sha").validate()
        with self.assertRaises(ValueError):
            replace(manifest, authority_effect="ALLOW").validate()

if __name__ == "__main__":
    unittest.main()

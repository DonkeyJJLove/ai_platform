import hashlib
import inspect
import subprocess
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cyber_lion.architecture_projection.full_architecture import build_full_architecture_model
from cyber_lion.architecture_projection.full_plantuml import (
    serialize_flow_atlas_plantuml,
    serialize_full_architecture_plantuml,
    serialize_gap_overlay_plantuml,
)
from cyber_lion.architecture_projection.full_visual_projection import build_visual_projection
from cyber_lion.architecture_projection.render_adapter import (
    RendererPin,
    VisualRenderManifest,
    build_visual_render_manifest,
    build_visual_render_plan,
)


def observed_tree(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
        shell=False,
    )
    return result.stdout.strip()


class ControlledRenderAdapterTests(unittest.TestCase):
    def _projection(self):
        repo_root = Path(__file__).resolve().parents[2]
        architecture = build_full_architecture_model(
            source_tree_sha=observed_tree(repo_root),
            source_root=repo_root,
        )
        return architecture, build_visual_projection(architecture)

    def _pin(self):
        return RendererPin("/opt/lion/pinned/plantuml.jar", "1.2026.6", "a" * 64).validate()

    def test_plan_is_deterministic_complete_and_source_bound(self):
        architecture, projection = self._projection()
        first = build_visual_render_plan(projection, self._pin())
        second = build_visual_render_plan(projection, self._pin())
        self.assertEqual(first, second)
        self.assertEqual(first.digest(), second.digest())
        self.assertEqual(first.source_tree_sha, architecture.source_tree_sha)
        self.assertEqual(first.architecture_model_digest, architecture.digest())
        self.assertEqual(first.visual_projection_digest, projection.digest())
        self.assertEqual(first.rendering_mode, "LOCAL_OFFLINE")
        self.assertEqual(first.authority_effect, "NONE")
        self.assertEqual(first.runtime_evidence, "NONE")
        self.assertEqual(len(first.artifacts), 11)
        self.assertEqual(len([a for a in first.artifacts if a.artifact_kind == "FLOW_ATLAS"]), 9)

    def test_fixed_output_paths_and_puml_digests_are_exact(self):
        _, projection = self._projection()
        plan = build_visual_render_plan(projection, self._pin())
        by_id = {artifact.artifact_id: artifact for artifact in plan.artifacts}
        full = by_id["lion-full-architecture"]
        gap = by_id["lion-implementation-gap-map"]
        self.assertEqual(full.puml_output_path, "docs/architecture/uml/generated/lion-full-architecture.puml")
        self.assertEqual(full.svg_output_path, "docs/architecture/uml/generated/lion-full-architecture.svg")
        self.assertEqual(gap.puml_output_path, "docs/architecture/uml/generated/lion-implementation-gap-map.puml")
        self.assertEqual(full.puml_source_digest, hashlib.sha256(serialize_full_architecture_plantuml(projection)).hexdigest())
        self.assertEqual(gap.puml_source_digest, hashlib.sha256(serialize_gap_overlay_plantuml(projection)).hexdigest())
        flow_sources = dict(serialize_flow_atlas_plantuml(projection))
        for index in range(1, 10):
            flow_id = f"FLOW-{index:02d}"
            artifact = by_id[f"lion-{flow_id.lower()}"]
            self.assertEqual(artifact.flow_id, flow_id)
            self.assertEqual(artifact.puml_output_path, f"docs/architecture/uml/generated/flows/lion-{flow_id.lower()}.puml")
            self.assertEqual(artifact.svg_output_path, f"docs/architecture/uml/generated/flows/lion-{flow_id.lower()}.svg")
            self.assertEqual(artifact.puml_source_digest, hashlib.sha256(flow_sources[flow_id]).hexdigest())
        all_paths = [
            path
            for artifact in plan.artifacts
            for path in (artifact.puml_output_path, artifact.svg_output_path, artifact.manifest_output_path)
        ]
        self.assertEqual(len(all_paths), len(set(all_paths)))
        self.assertTrue(all(path.startswith("docs/architecture/uml/generated/") for path in all_paths))

    def test_manifest_binds_entire_visual_render_chain(self):
        _, projection = self._projection()
        plan = build_visual_render_plan(projection, self._pin())
        rendered = b"<svg>synthetic-test-artifact</svg>"
        manifest = build_visual_render_manifest(
            plan=plan,
            artifact_id="lion-full-architecture",
            rendered_artifact=rendered,
        )
        artifact = next(a for a in plan.artifacts if a.artifact_id == "lion-full-architecture")
        self.assertEqual(manifest.source_tree_sha, plan.source_tree_sha)
        self.assertEqual(manifest.architecture_model_digest, plan.architecture_model_digest)
        self.assertEqual(manifest.visual_projection_digest, plan.visual_projection_digest)
        self.assertEqual(manifest.render_plan_digest, plan.digest())
        self.assertEqual(manifest.puml_source_digest, artifact.puml_source_digest)
        self.assertEqual(manifest.plantuml_version, self._pin().version)
        self.assertEqual(manifest.plantuml_binary_digest, self._pin().binary_digest)
        self.assertEqual(manifest.rendered_artifact_digest, hashlib.sha256(rendered).hexdigest())
        self.assertEqual(manifest.rendering_mode, "LOCAL_OFFLINE")
        self.assertEqual(manifest.authority_effect, "NONE")
        self.assertEqual(manifest.runtime_evidence, "NONE")
        self.assertEqual(manifest, manifest.validate())
        self.assertEqual(manifest.digest(), manifest.digest())

    def test_network_relative_and_unpinned_renderer_are_denied(self):
        for executable in ("https://example.invalid/plantuml", "http://example.invalid", "plantuml.jar"):
            with self.assertRaisesRegex(ValueError, "local absolute"):
                RendererPin(executable, "1.2026.6", "a" * 64).validate()
        with self.assertRaisesRegex(ValueError, "version"):
            RendererPin("/opt/plantuml.jar", "latest", "a" * 64).validate()
        with self.assertRaisesRegex(ValueError, "digest"):
            RendererPin("/opt/plantuml.jar", "1.2026.6", "bad").validate()

    def test_plan_does_not_execute_renderer(self):
        _, projection = self._projection()
        with patch("cyber_lion.architecture_projection.plantuml.PlantUMLRenderer.validate_configuration", side_effect=AssertionError("must not execute")), patch(
            "cyber_lion.architecture_projection.plantuml.PlantUMLRenderer.render_svg", side_effect=AssertionError("must not render")
        ):
            plan = build_visual_render_plan(projection, self._pin())
        self.assertEqual(len(plan.artifacts), 11)
        import cyber_lion.architecture_projection.render_adapter as adapter
        source = inspect.getsource(adapter)
        self.assertNotIn(".render_svg(", source)
        self.assertNotIn(".validate_configuration(", source)

    def test_manifest_cannot_claim_authority_runtime_or_network_mode(self):
        _, projection = self._projection()
        plan = build_visual_render_plan(projection, self._pin())
        manifest = build_visual_render_manifest(
            plan=plan,
            artifact_id="lion-implementation-gap-map",
            rendered_artifact=b"synthetic-svg",
        )
        with self.assertRaisesRegex(ValueError, "authority or runtime"):
            replace(manifest, authority_effect="ALLOW").validate()
        with self.assertRaisesRegex(ValueError, "authority or runtime"):
            replace(manifest, runtime_evidence="PROVEN").validate()
        with self.assertRaisesRegex(ValueError, "LOCAL_OFFLINE"):
            replace(manifest, rendering_mode="NETWORK").validate()

    def test_f005_remains_quarantined_in_input_projection(self):
        _, projection = self._projection()
        f005 = [node for node in projection.nodes if node.architecture_element_id == "quarantined-f005"]
        self.assertEqual(len(f005), 1)
        self.assertEqual((f005[0].status, f005[0].marker), ("QUARANTINED", "[Q]"))
        build_visual_render_plan(projection, self._pin())


if __name__ == "__main__":
    unittest.main()

import subprocess
import unittest
from dataclasses import replace
from pathlib import Path

from cyber_lion.architecture_projection.full_architecture import build_full_architecture_model
from cyber_lion.architecture_projection.full_plantuml import (
    serialize_flow_atlas_plantuml,
    serialize_full_architecture_plantuml,
    serialize_gap_overlay_plantuml,
)
from cyber_lion.architecture_projection.full_visual_projection import build_visual_projection


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


class FullArchitecturePlantUMLTests(unittest.TestCase):
    def _projection(self):
        repo_root = Path(__file__).resolve().parents[2]
        architecture = build_full_architecture_model(
            source_tree_sha=observed_tree(repo_root), source_root=repo_root
        )
        return build_visual_projection(architecture)

    def test_full_puml_is_byte_deterministic_and_status_explicit(self):
        model = self._projection()
        first = serialize_full_architecture_plantuml(model)
        second = serialize_full_architecture_plantuml(model)
        self.assertEqual(first, second)
        self.assertIn(b"[Q]", first)
        self.assertIn(b"QUARANTINED", first)
        self.assertIn(b"[T]", first)
        self.assertIn(b"TARGET_ONLY", first)
        self.assertIn(b"[?]", first)
        self.assertIn(b"UNKNOWN", first)
        self.assertIn(b"Status is explicit text", first)

    def test_flow_atlas_has_exactly_nine_deterministic_sources(self):
        model = self._projection()
        first = serialize_flow_atlas_plantuml(model)
        second = serialize_flow_atlas_plantuml(model)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 9)
        self.assertEqual(tuple(flow_id for flow_id, _ in first), tuple(sorted(flow.flow_id for flow in model.flows)))
        for _, source in first:
            self.assertIn(b"canonical-flow-order", source)
            self.assertIn(b"not runtime proof", source)

    def test_gap_overlay_preserves_unknown_and_target_only(self):
        source = serialize_gap_overlay_plantuml(self._projection())
        self.assertIn(b"IMPLEMENTATION GAP MAP", source)
        self.assertIn(b"[?]", source)
        self.assertIn(b"UNKNOWN", source)
        self.assertIn(b"[T]", source)
        self.assertIn(b"TARGET_ONLY", source)

    def test_directive_injection_from_visual_label_is_denied(self):
        model = self._projection()
        hostile = replace(model.nodes[0], label="!include https://example.invalid/x")
        tampered = replace(model, nodes=tuple(sorted((hostile,) + model.nodes[1:])))
        with self.assertRaisesRegex(ValueError, "directive fragment forbidden"):
            serialize_full_architecture_plantuml(tampered)


if __name__ == "__main__":
    unittest.main()

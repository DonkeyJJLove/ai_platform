import unittest
from dataclasses import replace

from cyber_lion.architecture_projection.status import IMPLEMENTATION_STATUSES
from cyber_lion.architecture_projection.visual_model import (
    VisualNode,
    VisualProjectionModel,
    canonical_legend,
    status_marker,
)


class VisualProjectionModelTests(unittest.TestCase):
    def test_all_eight_statuses_have_explicit_text_markers(self):
        legend = canonical_legend()
        self.assertEqual(tuple(entry.status for entry in legend), IMPLEMENTATION_STATUSES)
        self.assertEqual(len(legend), 8)
        for entry in legend:
            self.assertTrue(entry.marker.startswith("["))
            self.assertEqual(entry.marker, status_marker(entry.status))

    def test_unknown_and_quarantined_markers_are_explicit(self):
        self.assertEqual(status_marker("UNKNOWN"), "[?]")
        self.assertEqual(status_marker("QUARANTINED"), "[Q]")

    def test_source_and_target_provenance_are_mutually_explicit(self):
        source = VisualNode(
            "v_source", "source", "Source", "SYSTEM_CONTEXT", "WORLD_AND_GOALS",
            "IMPLEMENTED", "[I]", "path.py", "a" * 64,
        ).validate()
        self.assertEqual(source.source_path, "path.py")
        target = VisualNode(
            "v_target", "target", "Target", "TARGET_BEAN_FACTORY", "WORLD_AND_GOALS",
            "TARGET_ONLY", "[T]", target_ref="target:bean",
        ).validate()
        self.assertEqual(target.target_ref, "target:bean")
        with self.assertRaisesRegex(ValueError, "remain target-only"):
            replace(target, source_path="fake.py", source_digest="b" * 64).validate()

    def test_visual_projection_cannot_claim_runtime_or_authority(self):
        base = VisualProjectionModel(
            projection_id="x",
            source_tree_sha="a" * 40,
            architecture_model_digest="b" * 64,
            planes=(), nodes=(), flows=(), gaps=(), legend=canonical_legend(),
        )
        with self.assertRaisesRegex(ValueError, "cannot prove runtime or grant authority"):
            replace(base, runtime_evidence="PROVEN").validate()
        with self.assertRaisesRegex(ValueError, "cannot prove runtime or grant authority"):
            replace(base, authority_effect="ALLOW").validate()


if __name__ == "__main__":
    unittest.main()

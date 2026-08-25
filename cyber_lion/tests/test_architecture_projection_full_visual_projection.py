import subprocess
import unittest
from pathlib import Path

from cyber_lion.architecture_projection.full_architecture import build_full_architecture_model
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


class FullVisualProjectionTests(unittest.TestCase):
    def _models(self):
        repo_root = Path(__file__).resolve().parents[2]
        architecture = build_full_architecture_model(
            source_tree_sha=observed_tree(repo_root), source_root=repo_root
        )
        return architecture, build_visual_projection(architecture)

    def test_projection_is_deterministic_and_complete(self):
        architecture, first = self._models()
        second = build_visual_projection(architecture)
        self.assertEqual(first, second)
        self.assertEqual(first.digest(), second.digest())
        self.assertEqual(first.architecture_model_digest, architecture.digest())
        self.assertEqual(len(first.planes), 9)
        self.assertEqual(len({node.layer for node in first.nodes}), 15)
        self.assertEqual(len(first.flows), 9)
        self.assertEqual(len(first.legend), 8)

    def test_as_is_target_gap_and_f005_are_visibly_distinct(self):
        _, projection = self._models()
        self.assertTrue(any(node.status == "TARGET_ONLY" and node.marker == "[T]" for node in projection.nodes))
        self.assertTrue(any(gap.status == "UNKNOWN" and gap.marker == "[?]" for gap in projection.gaps))
        f005 = [node for node in projection.nodes if node.architecture_element_id == "quarantined-f005"]
        self.assertEqual(len(f005), 1)
        self.assertEqual((f005[0].status, f005[0].marker), ("QUARANTINED", "[Q]"))

    def test_source_provenance_is_preserved_exactly(self):
        architecture, projection = self._models()
        by_id = {element.element_id: element for element in architecture.elements}
        for node in projection.nodes:
            source = by_id[node.architecture_element_id]
            self.assertEqual(node.source_path, source.source_path)
            self.assertEqual(node.source_digest, source.status.source_digest)
            self.assertEqual(node.target_ref, source.target_ref)

    def test_all_canonical_flow_steps_are_preserved(self):
        architecture, projection = self._models()
        expected = {flow.flow_id: tuple(flow.steps) for flow in architecture.flows}
        actual = {flow.flow_id: flow.steps for flow in projection.flows}
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()

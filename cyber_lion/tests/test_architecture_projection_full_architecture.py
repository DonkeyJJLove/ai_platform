import subprocess
import unittest
from pathlib import Path

from cyber_lion.architecture_projection.full_architecture import build_full_architecture_model


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


class FullArchitectureProjectionTests(unittest.TestCase):
    def test_exact_canonical_tree_binding_and_determinism(self):
        repo_root = Path(__file__).resolve().parents[2]
        tree = observed_tree(repo_root)
        first = build_full_architecture_model(source_tree_sha=tree, source_root=repo_root)
        second = build_full_architecture_model(source_tree_sha=tree, source_root=repo_root)
        self.assertEqual(first, second)
        self.assertEqual(first.digest(), second.digest())
        self.assertEqual(first.source_tree_sha, tree)
        self.assertEqual(len({element.layer for element in first.elements}), 15)
        self.assertEqual(len(first.flows), 9)

    def test_wrong_source_tree_fails_closed(self):
        repo_root = Path(__file__).resolve().parents[2]
        actual = observed_tree(repo_root)
        wrong = "0" * 40 if actual != "0" * 40 else "1" * 40
        with self.assertRaisesRegex(ValueError, "source tree mismatch"):
            build_full_architecture_model(source_tree_sha=wrong, source_root=repo_root)

    def test_all_non_target_nodes_have_source_provenance(self):
        repo_root = Path(__file__).resolve().parents[2]
        model = build_full_architecture_model(source_tree_sha=observed_tree(repo_root), source_root=repo_root)
        for element in model.elements:
            if element.status.status == "TARGET_ONLY":
                self.assertTrue(element.target_ref)
                self.assertFalse(element.status.source_digest)
            else:
                self.assertTrue(element.source_path)
                self.assertEqual(len(element.status.source_digest), 64)

    def test_model_remains_derived_non_authoritative(self):
        repo_root = Path(__file__).resolve().parents[2]
        model = build_full_architecture_model(source_tree_sha=observed_tree(repo_root), source_root=repo_root)
        self.assertTrue(model.derived_only)
        self.assertEqual(model.authority_effect, "NONE")
        self.assertEqual(model.runtime_evidence, "NONE")


if __name__ == "__main__":
    unittest.main()

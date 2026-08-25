import unittest
from dataclasses import replace
from cyber_lion.architecture_projection.model import (
    CanonicalDiagramModel, DiagramNode, DiagramEdge, DiagramGroup,
    canonical_projection_identity,
)

D = "a" * 64


class ArchitectureProjectionModelTests(unittest.TestCase):
    def test_model_is_deterministic_and_non_authoritative(self):
        a = DiagramNode("n_a", "A", "component", "a.py", D)
        b = DiagramNode("n_b", "B", "component", "b.py", D)
        edges = (DiagramEdge("n_a", "n_b", "UNKNOWN"),)
        model = CanonicalDiagramModel("x", "component", "a" * 40, (a, b), edges).validate()
        self.assertEqual(model.source_digest(), model.source_digest())
        with self.assertRaises(ValueError):
            replace(model, authority_effect="ALLOW").validate()

    def test_unknown_edge_is_not_runtime_proof(self):
        with self.assertRaises(ValueError):
            DiagramEdge("n_a", "n_b", "UNKNOWN", runtime_proof=True).validate()

    def test_projection_identity_is_safe_and_path_sensitive(self):
        left = canonical_projection_identity(relation_domain="module", canonical_source_path="a-b.py", semantic_kind="module", qualified_name="A")
        right = canonical_projection_identity(relation_domain="module", canonical_source_path="a_b.py", semantic_kind="module", qualified_name="A")
        self.assertNotEqual(left, right)
        self.assertRegex(left, r"^[A-Za-z][A-Za-z0-9_]{0,127}$")

    def test_malicious_identifiers_are_denied(self):
        for bad in ("n_a\n!include x", "n_a;skinparam", "n_a!pragma", "n_a/path", "n_a space"):
            with self.assertRaises(ValueError):
                DiagramNode(bad, "A", "component", "a.py", D).validate()
            with self.assertRaises(ValueError):
                DiagramGroup(bad, "G", ()).validate()
        with self.assertRaises(ValueError):
            DiagramEdge("n_a\n!include", "n_b", "UNKNOWN").validate()

    def test_canonical_fact_requires_source_provenance(self):
        with self.assertRaises(ValueError):
            DiagramNode("n_a", "A", "component").validate()
        frontier = DiagramNode("n_f", "Future", "frontier", "design:R22K", "", "DECLARED_NEXT_FRONTIER")
        frontier.validate()

if __name__ == "__main__":
    unittest.main()

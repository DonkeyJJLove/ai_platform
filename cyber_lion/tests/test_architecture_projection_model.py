import unittest
from dataclasses import replace
from cyber_lion.architecture_projection.model import CanonicalDiagramModel,DiagramNode,DiagramEdge

class ArchitectureProjectionModelTests(unittest.TestCase):
    def test_model_is_deterministic_and_non_authoritative(self):
        nodes=(DiagramNode("a","A","component"),DiagramNode("b","B","component"))
        edges=(DiagramEdge("a","b","UNKNOWN"),)
        m=CanonicalDiagramModel("x","component","a"*40,nodes,edges).validate()
        self.assertEqual(m.source_digest(),m.source_digest())
        with self.assertRaises(ValueError): replace(m,authority_effect="ALLOW").validate()
    def test_unknown_edge_is_not_runtime_proof(self):
        with self.assertRaises(ValueError): DiagramEdge("a","b","UNKNOWN",runtime_proof=True).validate()

if __name__=="__main__":unittest.main()

import unittest
from cyber_lion.architecture_projection.flows import ARCHITECTURE_LAYERS
from cyber_lion.architecture_projection.full_architecture import _ELEMENT_SPECS
class CognitiveEvolutionArchitectureTests(unittest.TestCase):
    def test_no_new_top_level_layer(self):
        self.assertEqual(len(ARCHITECTURE_LAYERS),15)
        self.assertNotIn("COGNITIVE_INVOCATION_PLANE",ARCHITECTURE_LAYERS)
        self.assertNotIn("LEARNING_PLANE",ARCHITECTURE_LAYERS)
    def test_cognitive_concepts_bind_existing_layers(self):
        rows={x[0]:x[1] for x in _ELEMENT_SPECS}
        self.assertEqual(rows["cognitive-invocation"],"EVOLUTIONARY_EPOCH")
        self.assertEqual(rows["evidence-bound-learning"],"EVIDENCE_AND_EPISTEMIC_PLANE")
        self.assertEqual(rows["model-release"],"TRUSTED_RUNTIME")
        self.assertEqual(rows["model-call-v2"],"FLEET_AND_SWARM")
        self.assertEqual(rows["coordinator-competency"],"EVIDENCE_AND_EPISTEMIC_PLANE")
if __name__=="__main__":unittest.main()

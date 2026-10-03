import unittest
from cyber_lion.tests.experiments.semantic_cloud_r1 import run_fixture

class SemanticCloudR1ExperimentTests(unittest.TestCase):
    def test_no_effect_fixture_preserves_provenance_and_rejects_stale_state(self):
        a,b=run_fixture()
        self.assertFalse(a.task_success)
        self.assertFalse(a.stale_state_rejection)
        self.assertTrue(b.task_success)
        self.assertTrue(b.epistemic_success)
        self.assertTrue(b.provenance_preservation)
        self.assertTrue(b.stale_state_rejection)
        self.assertLess(b.semantic_state_size,a.semantic_state_size)
        self.assertLess(b.communication_units,a.communication_units)

if __name__=="__main__":
    unittest.main()

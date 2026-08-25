import unittest
from cyber_lion.architecture_projection.extractor import ArchitectureProjectionExtractor,available_projection_names

class ArchitectureProjectionExtractorTests(unittest.TestCase):
    def test_same_input_same_projection_and_order_independent(self):
        e=ArchitectureProjectionExtractor(source_tree_sha="b"*40)
        a=e.extract_python({"b.py":"import os\ndef z(): pass\n","a.py":"class A: pass\n"})
        b=e.extract_python({"a.py":"class A: pass\n","b.py":"import os\ndef z(): pass\n"})
        self.assertEqual(a,b); self.assertEqual(a.source_digest(),b.source_digest())
    def test_required_projection_set_and_r17_r22_chain(self):
        names=available_projection_names(); self.assertEqual(len(names),10)
        e=ArchitectureProjectionExtractor(source_tree_sha="c"*40)
        m=e.named_projection("authority-and-effect-chain-R17-R22")
        labels=[n.label for n in m.nodes]
        for label in ("BuilderEntryPermit","BuilderInvocationPermit","BuilderInvocationConsumptionPermit","BuilderStartAdmission","BuilderProcessLaunchBoundary","BuilderProcessCompletionObservation"):
            self.assertIn(label,labels)
    def test_fleet_and_epoch_projections(self):
        e=ArchitectureProjectionExtractor(source_tree_sha="d"*40)
        self.assertTrue(e.named_projection("fleet-topology").edges)
        self.assertTrue(e.named_projection("evolutionary-epoch-loop").edges)

if __name__=="__main__":unittest.main()

import json, unittest
from pathlib import Path
class ProcessContractShadowTests(unittest.TestCase):
    def test_shadow_recall_is_one(self):
        p=Path(__file__).resolve().parents[2]/"LION/architecture/v1_5/PROCESS_CONTRACT_SHADOW_REPORT.json"; r=json.loads(p.read_text(encoding="utf-8")); self.assertEqual(r["required_formalization_set_recall"],1.0)
    def test_historical_gaps_are_preserved(self):
        p=Path(__file__).resolve().parents[2]/"LION/architecture/v1_5/PROCESS_CONTRACT_SHADOW_REPORT.json"; r=json.loads(p.read_text(encoding="utf-8")); self.assertTrue(r["historical_closure_gaps"]); self.assertLess(r["required_formalization_set_precision"],1.0)
if __name__=="__main__": unittest.main()

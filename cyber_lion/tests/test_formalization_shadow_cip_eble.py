import json, unittest
from pathlib import Path
class CipEbleShadowTests(unittest.TestCase):
    def test_required_detection_labels_all_found(self):
        p=Path(__file__).resolve().parents[2]/"LION/architecture/v1_5/CIP_EBLE_SHADOW_REPORT.json"; r=json.loads(p.read_text(encoding="utf-8")); self.assertEqual(r["required_formalization_set_recall"],1.0); self.assertEqual(r["required_formalization_set_precision"],1.0); self.assertEqual(set(r["expected_detection_labels"]),set(r["detected_labels"]))
    def test_no_authority_effect(self):
        p=Path(__file__).resolve().parents[2]/"LION/architecture/v1_5/CIP_EBLE_SHADOW_REPORT.json"; r=json.loads(p.read_text(encoding="utf-8")); self.assertEqual(r["authority_effect"],"NONE")
if __name__=="__main__": unittest.main()

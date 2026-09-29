import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]/"LION/architecture/v1_5"
class RAGV15Task3InputsTests(unittest.TestCase):
    FILES=("RAG_V15_SOURCE_SET.json","RAG_V15_SEMANTIC_OWNER_SET.json","RAG_V15_RECORD_MIGRATION_MAP.json","RAG_V15_SUPERSESSION_MAP.json","RAG_V15_REQUIRED_RETRIEVAL_PROBES.json","RAG_V15_CURRENTNESS_BOUNDARIES.json")
    def test_machine_inputs_present_and_non_authoritative(self):
        for name in self.FILES:
            data=json.loads((ROOT/name).read_text(encoding="utf-8"))
            self.assertEqual(data["authority_effect"],"NONE")
            self.assertIn(data["currentness"],{"PRE_CLOSURE","CURRENT_CANDIDATE"})
    def test_required_retrieval_probes_cover_task2(self):
        data=json.loads((ROOT/"RAG_V15_REQUIRED_RETRIEVAL_PROBES.json").read_text(encoding="utf-8"))
        ids={x["id"] for x in data["probes"]}
        self.assertTrue({"V15-CIP-OWNER","V15-EBLE-TIME","V15-MODEL-RELEASE","V15-MODEL-CALL","V15-COMPETENCY","V15-LAYERS"}<=ids)
    def test_source_set_forbids_training_and_promotion(self):
        data=json.loads((ROOT/"RAG_V15_SOURCE_SET.json").read_text(encoding="utf-8"))
        self.assertEqual(data["training_effect"],"NONE")
        self.assertEqual(data["model_promotion_effect"],"NONE")
if __name__=="__main__":unittest.main()

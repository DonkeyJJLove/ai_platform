import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class CognitiveEvolutionDiscoverabilityTests(unittest.TestCase):
    def test_root_routes_v15_candidate(self):
        root=(ROOT/"AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("LION/architecture/v1_5/README.md",root)
    def test_v15_readme_routes_owner_map(self):
        text=(ROOT/"LION/architecture/v1_5/README.md").read_text(encoding="utf-8")
        self.assertIn("semantic_owners.json",text)
    def test_five_primary_owners_unique(self):
        data=json.loads((ROOT/"LION/architecture/v1_5/semantic_owners.json").read_text(encoding="utf-8"))
        wanted={"CognitiveInvocation","EvidenceBoundLearningEpisode","ModelRelease","CoordinatorCompetencyProfile","ModelCallV2"}
        rows=[x for x in data["owners"] if x["concept"] in wanted]
        self.assertEqual({x["concept"] for x in rows},wanted)
        self.assertEqual(len({x["primary"] for x in rows}),5)
if __name__=="__main__":unittest.main()

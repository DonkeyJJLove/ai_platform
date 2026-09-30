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
        self.assertIn("FORMALIZATION_REGISTRY_FEDERATION_R1.json",text)
        self.assertIn("ARCHITECTURE_DOCUMENT_GRAPH.json",text)

    def test_currentness_and_roadmap_owners_are_v15_current_surfaces(self):
        data=json.loads((ROOT/"LION/architecture/v1_5/semantic_owners.json").read_text(encoding="utf-8"))
        owners={row["concept"]:row["primary"] for row in data["owners"]}
        self.assertEqual(owners["currentness"],"LION/architecture/canonical-state-v1-3-candidate.json")
        self.assertEqual(owners["roadmap"],"LION/architecture/v1_5/AI_NATIVE_ROADMAP_NEXT.md")
        self.assertNotEqual(owners["models"],"LION/architecture/v1_4/current_state.json")

    def test_rag_bootstrap_routes_federated_architecture_candidate_without_promoting_release(self):
        bootstrap=json.loads((ROOT/"LION/rag/RAG_BOOTSTRAP.json").read_text(encoding="utf-8"))
        self.assertEqual(bootstrap["preferred_release"],"lion-rag32-v1.4-r9-auth-lifecycle-candidate")
        self.assertEqual(
            bootstrap["v15_federated_architecture_source_set"],
            "LION/architecture/v1_5/RAG_V15_FEDERATED_ARCHITECTURE_SOURCE_SET.json",
        )
        self.assertEqual(bootstrap["v15_federated_architecture_currentness"],"CURRENT_CANDIDATE_SOURCE_CLOSED")
    def test_five_primary_owners_unique(self):
        data=json.loads((ROOT/"LION/architecture/v1_5/semantic_owners.json").read_text(encoding="utf-8"))
        wanted={"CognitiveInvocation","EvidenceBoundLearningEpisode","ModelRelease","CoordinatorCompetencyProfile","ModelCallV2"}
        rows=[x for x in data["owners"] if x["concept"] in wanted]
        self.assertEqual({x["concept"] for x in rows},wanted)
        self.assertEqual(len({x["primary"] for x in rows}),5)
if __name__=="__main__":unittest.main()

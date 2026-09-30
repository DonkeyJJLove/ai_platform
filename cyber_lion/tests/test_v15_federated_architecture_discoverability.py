import json
from pathlib import Path
import unittest

from cyber_lion.architecture_projection.flows import FLOW_SPECS

ROOT=Path(__file__).resolve().parents[2]
V15=ROOT/"LION/architecture/v1_5"


class V15FederatedArchitectureDiscoverabilityTests(unittest.TestCase):
    def test_event_state_catalog_matches_canonical_flows(self):
        data=json.loads((ROOT/"LION/architecture/v1_4/event_state_catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(data["canonical_flows"],{key:list(value) for key,value in FLOW_SPECS.items()})
        self.assertEqual(len(data["canonical_flows"]),10)
        self.assertEqual(data["v15_federated_architecture_reconciliation"]["canonical_flow_change"],"FLOW_10_ADDED")

    def test_contract_catalog_discovers_federated_formalization(self):
        data=json.loads((ROOT/"LION/architecture/v1_4/contract_catalog.json").read_text(encoding="utf-8"))
        rows={row["contract_id"]:row for row in data["contracts"]}
        self.assertIn("federated-formalization-binding",rows)
        self.assertIn("repository-manifest-architecture-knowledge",rows)
        self.assertIn("formalized-governed-change-admission",rows)
        self.assertEqual(
            rows["federated-formalization-binding"]["canonical_path"],
            "cyber_lion/contracts/federated_formalization_binding.py",
        )

    def test_federated_rag_source_set_is_bounded_and_non_authoritative(self):
        data=json.loads((V15/"RAG_V15_FEDERATED_ARCHITECTURE_SOURCE_SET.json").read_text(encoding="utf-8"))
        self.assertEqual(data["authority_effect"],"NONE")
        self.assertEqual(data["currentness"],"CURRENT_CANDIDATE")
        self.assertEqual(data["federation"]["repository_count"],10)
        self.assertEqual(len(data["federation"]["repositories"]),10)
        self.assertEqual(data["live_truth_policy"],"RAG_NE_LIVE_TRUTH")
        binding=data["candidate_binding"]
        self.assertEqual(binding["head"],"c11f1acec701dc6372d24c81640d5fdcb7361b9f")
        self.assertEqual(binding["tree"],"f668210b46599d0a4f0f68c989689c92c24dc83e")
        self.assertRegex(binding["formalization_manifest_digest"],r"^[0-9a-f]{64}$")
        self.assertRegex(binding["federated_binding_digest"],r"^[0-9a-f]{64}$")
        for source in data["source_paths"]:
            self.assertTrue((ROOT/source).is_file(),source)

    def test_rag_probes_cover_owner_formalization_currentness_and_frontier(self):
        data=json.loads((V15/"RAG_V15_FEDERATED_ARCHITECTURE_PROBES.json").read_text(encoding="utf-8"))
        ids={row["id"] for row in data["probes"]}
        self.assertEqual(ids,{
            "V15-FED-OWNER",
            "V15-FED-FORMALIZATION",
            "V15-DOC-CURRENTNESS",
            "V15-DOC-GRAPH",
            "V15-NEXT-FRONTIER",
        })
        self.assertTrue(all(row["must_route_to"] for row in data["probes"]))

    def test_new_registry_is_current_and_historical_registry_is_preserved(self):
        current=json.loads((V15/"FORMALIZATION_REGISTRY_FEDERATION_R1.json").read_text(encoding="utf-8"))
        historical=json.loads((V15/"FORMALIZATION_REGISTRY_CANDIDATE.json").read_text(encoding="utf-8"))
        self.assertEqual(current["registry_id"],"formalization-registry:v1.5-federation-r1")
        self.assertNotEqual(current["registry_digest"],historical["registry_digest"])
        current_paths={row["artifact_id"]:row["path"] for row in current["entries"]}
        self.assertEqual(current_paths["semantic-owners"],"LION/architecture/v1_5/semantic_owners.json")
        self.assertEqual(
            current_paths["documentation-currentness-model"],
            "LION/architecture/v1_5/DOCUMENTATION_CURRENTNESS_MODEL.json",
        )

    def test_repository_documentation_plans_cover_exact_federation(self):
        data=json.loads((V15/"REPOSITORY_DOCUMENTATION_PLANS.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["plans"]),10)
        self.assertEqual(len({row["repository"] for row in data["plans"]}),10)
        self.assertTrue(all(row["global_architecture_copy"]=="FORBIDDEN" for row in data["plans"]))


if __name__=="__main__":
    unittest.main()

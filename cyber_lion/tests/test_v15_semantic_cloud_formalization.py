import json
from pathlib import Path
import unittest

from cyber_lion.architecture_projection.formalization import derive_required_formalization_set
from cyber_lion.contracts.architecture_formalization_manifest import ArchitectureFormalizationManifest
from cyber_lion.contracts.evolutionary_rnd import EvolutionDelta
from cyber_lion.contracts.formalization_manifest_types import (
    BaselineIdentity,DiscoverabilityPlan,EvolutionDeltaRef,FormalizationUpdate,
    LayerBinding,MigrationPlan,RagDelta,SemanticOwnerDelta,
)
from cyber_lion.contracts.formalization_registry import FormalizationRegistry

ROOT=Path(__file__).resolve().parents[2]
V15=ROOT/"LION/architecture/v1_5"

def load(name):
    return json.loads((V15/name).read_text(encoding="utf-8"))

def registry():
    return FormalizationRegistry.from_dict(load("FORMALIZATION_REGISTRY_FEDERATION_R1.json"))

def manifest():
    value=load("ARCHITECTURE_FORMALIZATION_MANIFEST_SEMANTIC_CLOUD_R1.json")
    reg=registry()
    return ArchitectureFormalizationManifest(
        manifest_id=value["manifest_id"],
        baseline=BaselineIdentity(**value["baseline"]),
        source_evolution_delta=EvolutionDeltaRef(**value["source_evolution_delta"]),
        change_class=value["change_class"],
        affected_concepts=tuple(value["affected_concepts"]),
        layer_bindings=tuple(
            LayerBinding(x["concept"],tuple(x["layers"]),x["new_top_level_layer_required"])
            for x in value["layer_bindings"]
        ),
        semantic_owner_delta=tuple(
            SemanticOwnerDelta(x["concept"],x["primary"],tuple(x["secondary"]),x["operation"])
            for x in value["semantic_owner_delta"]
        ),
        formalization_updates=tuple(
            FormalizationUpdate(x["artifact_id"],x["operation"],x["reason"])
            for x in value["formalization_updates"]
        ),
        currentness_invalidations=tuple(value["currentness_invalidations"]),
        migration=MigrationPlan(tuple(value["migration"]["steps"]),value["migration"]["compatibility_adapter"],value["migration"]["exit_condition"]),
        rollback=MigrationPlan(tuple(value["rollback"]["steps"]),value["rollback"]["compatibility_adapter"],value["rollback"]["exit_condition"]),
        tests_required=tuple(value["tests_required"]),
        evals_required=tuple(value["evals_required"]),
        falsifiers=tuple(value["falsifiers"]),
        discoverability=DiscoverabilityPlan(
            tuple(value["discoverability"]["bootstrap_routes"]),
            tuple(value["discoverability"]["probe_questions"]),
            value["discoverability"]["max_reads_to_owner"],
        ),
        rag_delta=RagDelta(
            value["rag_delta"]["required"],
            tuple(value["rag_delta"]["record_ids"]),
            tuple(value["rag_delta"]["retrieval_probes"]),
        ),
        authority_effect=value["authority_effect"],
        execution_effect=value["execution_effect"],
        manifest_digest=value["manifest_digest"],
        schema_id=value["schema_id"],
    ).validate(reg)

class SemanticCloudFormalizationTests(unittest.TestCase):
    def test_evolution_delta_is_non_effectful_and_bound(self):
        value=load("EVOLUTION_DELTA_SEMANTIC_CLOUD_R1.json")
        delta=EvolutionDelta(
            delta_id=value["delta_id"],target_component=value["target_component"],
            motivation=value["motivation"],evidence_refs=tuple(value["evidence_refs"]),
            expected_outcome=value["expected_outcome"],
            falsification_conditions=tuple(value["falsification_conditions"]),
            candidate_scope=tuple(value["candidate_scope"]),
            dependency_ids=tuple(value["dependency_ids"]),risk_class=value["risk_class"],
            authority_effect=value["authority_effect"],execution_effect=value["execution_effect"],
            delta_digest=value["delta_digest"],schema_version=value["schema_version"],
        ).validate()
        self.assertEqual(delta.authority_effect,"NONE")
        self.assertEqual(delta.execution_effect,"NONE")

    def test_manifest_and_required_set_are_deterministic(self):
        reg=registry(); afm=manifest()
        expected=load("REQUIRED_FORMALIZATION_SET_SEMANTIC_CLOUD_R1.json")
        actual=json.loads(json.dumps(derive_required_formalization_set(afm,reg).to_dict(),sort_keys=True))
        self.assertEqual(actual,expected)
        self.assertEqual(afm.authority_effect,"NONE")
        self.assertEqual(afm.execution_effect,"NONE")

    def test_semantic_owner_delta_is_unique(self):
        afm=manifest()
        concepts=[x.concept for x in afm.semantic_owner_delta]
        self.assertEqual(len(concepts),len(set(concepts)))
        self.assertEqual(
            set(concepts),
            {"MissionIntent","QueryPlan","RagContextEnvelope","SemanticScaffold","SemanticRelevance"},
        )

    def test_contract_catalog_contains_semantic_cloud_contracts(self):
        catalog=json.loads((ROOT/"LION/architecture/v1_4/contract_catalog.json").read_text(encoding="utf-8"))
        ids={x["contract_id"] for x in catalog["contracts"]}
        self.assertTrue({
            "mission-intent","query-plan","rag-context-envelope",
            "semantic-scaffold","semantic-relevance","semantic-cloud-episode-binding",
        }<=ids)
        for row in catalog["contracts"]:
            if row["contract_id"] in {
                "mission-intent","query-plan","rag-context-envelope",
                "semantic-scaffold","semantic-relevance","semantic-cloud-episode-binding",
            }:
                self.assertIn("NON_EFFECTFUL",row["compatibility_status"])

    def test_required_evals_exist(self):
        cases=json.loads((ROOT/"LION/evals/evolution/evolution_cases.yaml").read_text(encoding="utf-8"))["cases"]
        ids={x["id"] for x in cases}
        self.assertTrue(set(manifest().evals_required)<=ids)

    def test_rag_candidate_does_not_claim_live_truth(self):
        source=load("RAG_V15_SEMANTIC_CLOUD_SOURCE_SET.json")
        self.assertEqual(source["authority_effect"],"NONE")
        self.assertIn("does not replace live",source["rule"])

if __name__=="__main__":
    unittest.main()

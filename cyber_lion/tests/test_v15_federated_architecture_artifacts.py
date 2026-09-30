import json
from pathlib import Path
import unittest

from cyber_lion.contracts.architecture_formalization_manifest import ArchitectureFormalizationManifest
from cyber_lion.contracts.formalization_manifest_types import (
    BaselineIdentity,DiscoverabilityPlan,EvolutionDeltaRef,FormalizationUpdate,
    LayerBinding,MigrationPlan,RagDelta,SemanticOwnerDelta,
)
from cyber_lion.contracts.formalization_registry import FormalizationRegistry
from cyber_lion.architecture_projection.formalization import derive_required_formalization_set
from cyber_lion.contracts.repository_expansion import (
    FleetBaseline,RegisteredRepository,RepositoryBaseline,RepositoryDependencyEdge,
)
from cyber_lion.contracts.federated_formalization_binding import (
    FederatedFormalizationBinding,RepositoryFormalizationDisposition,
)

ROOT=Path(__file__).resolve().parents[2]
V15=ROOT/"LION/architecture/v1_5"


def registry():
    return FormalizationRegistry.from_dict(json.loads((V15/"FORMALIZATION_REGISTRY_FEDERATION_R1.json").read_text()))


def manifest(reg):
    value=json.loads((V15/"ARCHITECTURE_FORMALIZATION_MANIFEST_FEDERATION_R1.json").read_text())
    return ArchitectureFormalizationManifest(
        manifest_id=value["manifest_id"],
        baseline=BaselineIdentity(**value["baseline"]),
        source_evolution_delta=EvolutionDeltaRef(**value["source_evolution_delta"]),
        change_class=value["change_class"],
        affected_concepts=tuple(value["affected_concepts"]),
        layer_bindings=tuple(LayerBinding(x["concept"],tuple(x["layers"]),x["new_top_level_layer_required"]) for x in value["layer_bindings"]),
        semantic_owner_delta=tuple(SemanticOwnerDelta(x["concept"],x["primary"],tuple(x["secondary"]),x["operation"]) for x in value["semantic_owner_delta"]),
        formalization_updates=tuple(FormalizationUpdate(x["artifact_id"],x["operation"],x["reason"]) for x in value["formalization_updates"]),
        currentness_invalidations=tuple(value["currentness_invalidations"]),
        migration=MigrationPlan(tuple(value["migration"]["steps"]),value["migration"]["compatibility_adapter"],value["migration"]["exit_condition"]),
        rollback=MigrationPlan(tuple(value["rollback"]["steps"]),value["rollback"]["compatibility_adapter"],value["rollback"]["exit_condition"]),
        tests_required=tuple(value["tests_required"]),
        evals_required=tuple(value["evals_required"]),
        falsifiers=tuple(value["falsifiers"]),
        discoverability=DiscoverabilityPlan(tuple(value["discoverability"]["bootstrap_routes"]),tuple(value["discoverability"]["probe_questions"]),value["discoverability"]["max_reads_to_owner"]),
        rag_delta=RagDelta(value["rag_delta"]["required"],tuple(value["rag_delta"]["record_ids"]),tuple(value["rag_delta"]["retrieval_probes"])),
        authority_effect=value["authority_effect"],execution_effect=value["execution_effect"],
        manifest_digest=value["manifest_digest"],schema_id=value["schema_id"],
    ).validate(reg)


def fleet():
    raw=json.loads((V15/"FLEET_BASELINE_FEDERATION_R1.json").read_text())
    return FleetBaseline(
        raw["schema_version"],raw["baseline_id"],
        tuple(RegisteredRepository(**x) for x in raw["registered"]),
        tuple(RepositoryBaseline(
            x["schema_version"],x["repository"],x["branch"],x["head"],x["tree"],x["dirty"],
            x["build_result"],x["test_result"],x["failure_classification"],
            tuple(x["known_preexisting_failures"]),tuple(x["dependencies"]),tuple(x["dependents"]),
            tuple(x["public_contracts"]),tuple(x["security_boundaries"]),x["manifest_present"],(),
        ) for x in raw["observations"]),
        tuple(RepositoryDependencyEdge(**x) for x in raw["edges"]),
    ).validate()


class V15FederatedArchitectureArtifactsTests(unittest.TestCase):
    def test_registry_afm_and_required_set_are_exactly_bound(self):
        reg=registry(); afm=manifest(reg)
        expected=json.loads((V15/"REQUIRED_FORMALIZATION_SET_FEDERATION_R1.json").read_text())
        observed=derive_required_formalization_set(afm,reg).to_dict()
        normalized=json.loads(json.dumps(observed,sort_keys=True))
        self.assertEqual(normalized,expected)
        self.assertEqual(len(normalized["items"]),36)

    def test_fleet_baseline_exactly_covers_ten_repositories_and_gate0_passes(self):
        f=fleet()
        raw=json.loads((V15/"FLEET_BASELINE_FEDERATION_R1.json").read_text())
        self.assertEqual(len(f.registered),10)
        self.assertEqual(f.baseline_digest(),raw["baseline_digest"])
        self.assertEqual(f.gate0().result,"PASS")
        swarm=next(x for x in f.observations if x.repository=="DonkeyJJLove/swarm")
        self.assertEqual(swarm.failure_classification,"KNOWN_PREEXISTING_FAILURES")
        self.assertEqual(len(swarm.known_preexisting_failures),5)

    def test_federated_binding_matches_afm_and_fleet(self):
        reg=registry();afm=manifest(reg);f=fleet()
        value=json.loads((V15/"FEDERATED_FORMALIZATION_BINDING_R1.json").read_text())
        binding=FederatedFormalizationBinding(
            value["binding_id"],value["formalization_manifest_digest"],value["fleet_baseline_digest"],
            value["dependency_graph_digest"],
            tuple(RepositoryFormalizationDisposition(
                x["repository"],x["baseline_head"],x["baseline_tree"],x["disposition"],tuple(x["required_artifact_ids"])
            ) for x in value["repositories"]),
            value["authority_effect"],value["execution_effect"],value["binding_digest"],value["schema_id"],
        ).validate(f)
        self.assertEqual(binding.formalization_manifest_digest,afm.manifest_digest)
        self.assertEqual(sum(x.disposition=="UPDATE" for x in binding.repositories),1)
        self.assertEqual(sum(x.disposition=="VALIDATE_ONLY" for x in binding.repositories),9)
        self.assertEqual(next(x for x in binding.repositories if x.disposition=="UPDATE").repository,"DonkeyJJLove/ai_platform")

    def test_rag_source_set_uses_current_registry_and_does_not_promote_release(self):
        rag=json.loads((V15/"RAG_V15_FEDERATED_ARCHITECTURE_SOURCE_SET.json").read_text())
        bootstrap=json.loads((ROOT/"LION/rag/RAG_BOOTSTRAP.json").read_text())
        self.assertEqual(rag["formalization_registry"]["registry_digest"],registry().registry_digest)
        self.assertEqual(rag["currentness"],"CANDIDATE_PRE_CLOSURE")
        self.assertEqual(bootstrap["preferred_release"],"lion-rag32-v1.4-r9-auth-lifecycle-candidate")

    def test_current_owner_map_has_no_v14_current_state_primary(self):
        owners=json.loads((V15/"semantic_owners.json").read_text())["owners"]
        self.assertFalse(any(x["primary"]=="LION/architecture/v1_4/current_state.json" for x in owners))
        self.assertEqual(len({x["concept"] for x in owners}),len(owners))


if __name__=="__main__":
    unittest.main()

import hashlib
import json
from pathlib import Path
import unittest

from cyber_lion.architecture_projection.formalization import derive_required_formalization_set
from cyber_lion.architecture_projection.full_architecture import build_full_architecture_model
from cyber_lion.architecture_projection.gap import canonical_gap_projection
from cyber_lion.tests.architecture_projection_candidate import staged_sources, staged_tree
from cyber_lion.contracts.architecture_formalization_manifest import ArchitectureFormalizationManifest
from cyber_lion.contracts.formalization_manifest_types import BaselineIdentity,DiscoverabilityPlan,EvolutionDeltaRef,FormalizationUpdate,LayerBinding,MigrationPlan,RagDelta,SemanticOwnerDelta
from cyber_lion.contracts.formalization_registry import FormalizationRegistry
from cyber_lion.contracts.repository_expansion import FleetBaseline,RegisteredRepository,RepositoryBaseline,RepositoryDependencyEdge
from cyber_lion.contracts.federated_formalization_binding import FederatedFormalizationBinding,RepositoryFormalizationDisposition

ROOT=Path(__file__).resolve().parents[2]
V15=ROOT/"LION/architecture/v1_5"
INTEGRATION_BASE_HEAD="3f0f3a01e0d42c190983a0dea32b5b4abb07b589"
INTEGRATION_BASE_TREE="3ac45ea1329938fdcd7f3c3d4705c78907533949"
CURRENT_OWNER_BASELINE_HEAD="c064e6aca1c5be8187ae7fd856b9f7950adfa7a4"

def load(name):
    return json.loads((V15/name).read_text(encoding="utf-8"))

def registry():
    return FormalizationRegistry.from_dict(load("FORMALIZATION_REGISTRY_FEDERATION_R1.json"))

def manifest():
    v=load("ARCHITECTURE_FORMALIZATION_MANIFEST_COMMUNICATION_ENVELOPE_R1.json"); r=registry()
    return ArchitectureFormalizationManifest(
        manifest_id=v["manifest_id"],baseline=BaselineIdentity(**v["baseline"]),source_evolution_delta=EvolutionDeltaRef(**v["source_evolution_delta"]),
        change_class=v["change_class"],affected_concepts=tuple(v["affected_concepts"]),
        layer_bindings=tuple(LayerBinding(x["concept"],tuple(x["layers"]),x["new_top_level_layer_required"]) for x in v["layer_bindings"]),
        semantic_owner_delta=tuple(SemanticOwnerDelta(x["concept"],x["primary"],tuple(x["secondary"]),x["operation"]) for x in v["semantic_owner_delta"]),
        formalization_updates=tuple(FormalizationUpdate(x["artifact_id"],x["operation"],x["reason"]) for x in v["formalization_updates"]),
        currentness_invalidations=tuple(v["currentness_invalidations"]),
        migration=MigrationPlan(tuple(v["migration"]["steps"]),v["migration"]["compatibility_adapter"],v["migration"]["exit_condition"]),
        rollback=MigrationPlan(tuple(v["rollback"]["steps"]),v["rollback"]["compatibility_adapter"],v["rollback"]["exit_condition"]),
        tests_required=tuple(v["tests_required"]),evals_required=tuple(v["evals_required"]),falsifiers=tuple(v["falsifiers"]),
        discoverability=DiscoverabilityPlan(tuple(v["discoverability"]["bootstrap_routes"]),tuple(v["discoverability"]["probe_questions"]),v["discoverability"]["max_reads_to_owner"]),
        rag_delta=RagDelta(v["rag_delta"]["required"],tuple(v["rag_delta"]["record_ids"]),tuple(v["rag_delta"]["retrieval_probes"])),
        authority_effect=v["authority_effect"],execution_effect=v["execution_effect"],manifest_digest=v["manifest_digest"],schema_id=v["schema_id"],
    ).validate(r)

def fleet():
    v=load("FLEET_BASELINE_COMMUNICATION_ENVELOPE_R1.json")
    return FleetBaseline(v["schema_version"],v["baseline_id"],tuple(RegisteredRepository(**x) for x in v["registered"]),
        tuple(RepositoryBaseline(x["schema_version"],x["repository"],x["branch"],x["head"],x["tree"],x["dirty"],x["build_result"],x["test_result"],x["failure_classification"],tuple(x["known_preexisting_failures"]),tuple(x["dependencies"]),tuple(x["dependents"]),tuple(x["public_contracts"]),tuple(x["security_boundaries"]),x["manifest_present"],()) for x in v["observations"]),
        tuple(RepositoryDependencyEdge(**x) for x in v["edges"])).validate()

class CommunicationEnvelopeFormalizationTests(unittest.TestCase):
    def test_selective_port_core_is_exact_and_non_effectful(self):
        files={
            "cyber_lion/contracts/communication_envelope.py":"e426874d50a6a21f29a1f2b913f0d4780ec4c482a6fcf54df5e2c10af5684017",
            "cyber_lion/tests/test_communication_envelope.py":"4dd3a0973f6c137a2446876c8d873d7a300b19b03a510efffc3920796c11d369",
        }
        for rel,expected in files.items():
            self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),expected)
        text=(ROOT/"cyber_lion/contracts/communication_envelope.py").read_text()
        self.assertIn('AUTHORITY_EFFECT = "NONE"',text)
        self.assertIn('EFFECT = "NONE"',text)

    def test_current_owner_catalog_architecture_and_gap_are_rebound(self):
        owners=load("semantic_owners.json")
        self.assertEqual(owners["baseline_head"],CURRENT_OWNER_BASELINE_HEAD)
        rows=[x for x in owners["owners"] if x["concept"]=="CommunicationEnvelope"]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["primary"],"cyber_lion/contracts/communication_envelope.py")
        catalog=json.loads((ROOT/"LION/architecture/v1_4/contract_catalog.json").read_text())
        entry=next(x for x in catalog["contracts"] if x["contract_id"]=="communication-envelope")
        self.assertEqual(entry["version"],"lion.communication-envelope/v1")
        model=build_full_architecture_model(source_tree_sha=staged_tree(ROOT),source_files=staged_sources(ROOT))
        ce=next(x for x in model.elements if x.element_id=="communication-envelope")
        self.assertEqual(ce.layer,"FLEET_AND_SWARM")
        self.assertEqual(ce.status.status,"CONTRACT_ONLY")
        gap=next(x for x in canonical_gap_projection() if x.target_id=="CommunicationEnvelope")
        self.assertEqual(gap.status,"CONTRACT_ONLY")
        self.assertIn("MissionIntent",gap.next_minimal_gap)

    def test_afm_rfs_and_exact_federation_binding_validate(self):
        r=registry(); a=manifest(); f=fleet()
        self.assertEqual((a.baseline.head,a.baseline.tree),(INTEGRATION_BASE_HEAD,INTEGRATION_BASE_TREE))
        expected=load("REQUIRED_FORMALIZATION_SET_COMMUNICATION_ENVELOPE_R1.json")
        self.assertEqual(json.loads(json.dumps(derive_required_formalization_set(a,r).to_dict(),sort_keys=True)),expected)
        self.assertEqual(len(expected["items"]),36)
        raw=load("FLEET_BASELINE_COMMUNICATION_ENVELOPE_R1.json")
        self.assertEqual(f.baseline_digest(),raw["baseline_digest"])
        self.assertEqual(f.gate0().result,"PASS")
        self.assertEqual(len(f.registered),10)
        b=load("FEDERATED_FORMALIZATION_BINDING_COMMUNICATION_ENVELOPE_R1.json")
        binding=FederatedFormalizationBinding(b["binding_id"],b["formalization_manifest_digest"],b["fleet_baseline_digest"],b["dependency_graph_digest"],tuple(RepositoryFormalizationDisposition(x["repository"],x["baseline_head"],x["baseline_tree"],x["disposition"],tuple(x["required_artifact_ids"])) for x in b["repositories"]),b["authority_effect"],b["execution_effect"],b["binding_digest"],b["schema_id"]).validate(f)
        self.assertEqual(binding.formalization_manifest_digest,a.manifest_digest)
        self.assertEqual(sum(x.disposition=="UPDATE" for x in binding.repositories),1)
        self.assertEqual(sum(x.disposition=="VALIDATE_ONLY" for x in binding.repositories),9)
        self.assertEqual(next(x.repository for x in binding.repositories if x.disposition=="UPDATE"),"DonkeyJJLove/ai_platform")

    def test_eval_and_rag_boundaries_are_materialized_without_release_promotion(self):
        cases=json.loads((ROOT/"LION/evals/evolution/evolution_cases.yaml").read_text())["cases"]
        ids={x["id"] for x in cases}
        required=set(manifest().evals_required)
        self.assertTrue(required<=ids)
        source=load("RAG_V15_COMMUNICATION_ENVELOPE_SOURCE_SET.json")
        probes=load("RAG_V15_COMMUNICATION_ENVELOPE_PROBES.json")
        bootstrap=json.loads((ROOT/"LION/rag/RAG_BOOTSTRAP.json").read_text())
        if "candidate_binding" in source:
            self.assertEqual(source["currentness"],"CURRENT_CANDIDATE")
            self.assertEqual(probes["currentness"],"CURRENT_CANDIDATE")
            self.assertEqual(probes["candidate_binding"],source["candidate_binding"])
            closure=load("FORMALIZATION_CLOSURE_RECORD_COMMUNICATION_ENVELOPE_R1.json")
            self.assertEqual(source["candidate_binding"]["head"],closure["candidate"]["head"])
            self.assertEqual(source["candidate_binding"]["tree"],closure["candidate"]["tree"])
            self.assertEqual(source["candidate_binding"]["candidate_digest"],closure["candidate"]["candidate_digest"])
        else:
            self.assertEqual(source["currentness"],"FORMALIZATION_PENDING")
            self.assertEqual(probes["currentness"],"FORMALIZATION_PENDING")
        self.assertEqual(source["live_truth_policy"],"RAG_NE_LIVE_TRUTH")
        self.assertEqual(source["preferred_release_unchanged"],bootstrap["preferred_release"])
        self.assertEqual(probes["source_set_digest"],source["source_set_digest"])
        self.assertIn("RAG != live truth",probes["probes"][0]["must_preserve"])

if __name__=="__main__":
    unittest.main()

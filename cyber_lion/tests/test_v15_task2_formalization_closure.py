import json, unittest
from pathlib import Path
from cyber_lion.contracts.formalization_registry import FormalizationRegistry
from cyber_lion.contracts.architecture_formalization_manifest import ArchitectureFormalizationManifest
from cyber_lion.contracts.formalization_manifest_types import BaselineIdentity,EvolutionDeltaRef,LayerBinding,SemanticOwnerDelta,FormalizationUpdate,MigrationPlan,DiscoverabilityPlan,RagDelta
from cyber_lion.contracts.formalization_closure import FormalizationClosureRecord,CandidateBinding,ArtifactResult,GateResult
ROOT=Path(__file__).resolve().parents[2]
V15=ROOT/"LION/architecture/v1_5"
def registry():
    return FormalizationRegistry.from_dict(json.loads((V15/"FORMALIZATION_REGISTRY_CANDIDATE.json").read_text(encoding="utf-8")))
def manifest(reg):
    d=json.loads((V15/"ARCHITECTURE_FORMALIZATION_MANIFEST_TASK2.json").read_text(encoding="utf-8"))
    return ArchitectureFormalizationManifest(
        manifest_id=d["manifest_id"],
        baseline=BaselineIdentity(**d["baseline"]),
        source_evolution_delta=EvolutionDeltaRef(**d["source_evolution_delta"]),
        change_class=d["change_class"],
        affected_concepts=tuple(d["affected_concepts"]),
        layer_bindings=tuple(LayerBinding(x["concept"],tuple(x["layers"]),x["new_top_level_layer_required"]) for x in d["layer_bindings"]),
        semantic_owner_delta=tuple(SemanticOwnerDelta(x["concept"],x["primary"],tuple(x["secondary"]),x["operation"]) for x in d["semantic_owner_delta"]),
        formalization_updates=tuple(FormalizationUpdate(x["artifact_id"],x["operation"],x["reason"]) for x in d["formalization_updates"]),
        currentness_invalidations=tuple(d["currentness_invalidations"]),
        migration=MigrationPlan(tuple(d["migration"]["steps"]),d["migration"]["compatibility_adapter"],d["migration"]["exit_condition"]),
        rollback=MigrationPlan(tuple(d["rollback"]["steps"]),d["rollback"]["compatibility_adapter"],d["rollback"]["exit_condition"]),
        tests_required=tuple(d["tests_required"]),evals_required=tuple(d["evals_required"]),falsifiers=tuple(d["falsifiers"]),
        discoverability=DiscoverabilityPlan(tuple(d["discoverability"]["bootstrap_routes"]),tuple(d["discoverability"]["probe_questions"]),d["discoverability"]["max_reads_to_owner"]),
        rag_delta=RagDelta(d["rag_delta"]["required"],tuple(d["rag_delta"]["record_ids"]),tuple(d["rag_delta"]["retrieval_probes"])),
        authority_effect=d["authority_effect"],execution_effect=d["execution_effect"],manifest_digest=d["manifest_digest"],schema_id=d["schema_id"],
    ).validate(reg)
def closure():
    d=json.loads((V15/"RAG_V15_FORMALIZATION_CLOSURE.json").read_text(encoding="utf-8"))
    return FormalizationClosureRecord(
        closure_id=d["closure_id"],candidate=CandidateBinding(**d["candidate"]),
        formalization_manifest_digest=d["formalization_manifest_digest"],
        artifact_results=tuple(ArtifactResult(x["artifact_id"],x["classification"],x["state"],tuple(x["evidence_refs"])) for x in d["artifact_results"]),
        semantic_owner_uniqueness=d["semantic_owner_uniqueness"],catalog_coverage=d["catalog_coverage"],
        discoverability_result=d["discoverability_result"],rag_result=d["rag_result"],
        required_test_results=tuple(GateResult(x["id"],x["result"],tuple(x["evidence_refs"])) for x in d["required_test_results"]),
        required_eval_results=tuple(GateResult(x["id"],x["result"],tuple(x["evidence_refs"])) for x in d["required_eval_results"]),
        currentness_result=d["currentness_result"],unknowns=tuple(d["unknowns"]),decision=d["decision"],
        authority_effect=d["authority_effect"],closure_digest=d["closure_digest"],schema_id=d["schema_id"],
    )
class Task2FormalizationClosureTests(unittest.TestCase):
    def test_actual_closure_validates_pass(self):
        reg=registry();man=manifest(reg);c=closure().validate(man,reg)
        self.assertEqual(c.decision,"PASS");self.assertEqual(c.currentness_result,"CURRENT_CANDIDATE");self.assertFalse(c.unknowns)
    def test_closure_binds_exact_source_candidate(self):
        c=closure()
        boundary=json.loads((V15/"RAG_V15_CURRENTNESS_BOUNDARIES.json").read_text(encoding="utf-8"))["boundaries"]["task2"]
        self.assertEqual(c.candidate.head,boundary["source_head"])
        self.assertEqual(c.candidate.tree,boundary["source_tree"])
        self.assertEqual(c.closure_digest,boundary["formalization_closure_digest"])
    def test_all_task3_inputs_are_current_candidate(self):
        for name in ("RAG_V15_SOURCE_SET.json","RAG_V15_SEMANTIC_OWNER_SET.json","RAG_V15_RECORD_MIGRATION_MAP.json","RAG_V15_SUPERSESSION_MAP.json","RAG_V15_REQUIRED_RETRIEVAL_PROBES.json","RAG_V15_CURRENTNESS_BOUNDARIES.json"):
            self.assertEqual(json.loads((V15/name).read_text(encoding="utf-8"))["currentness"],"CURRENT_CANDIDATE")
if __name__=="__main__":unittest.main()

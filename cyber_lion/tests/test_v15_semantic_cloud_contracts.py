import unittest
from dataclasses import replace

from cyber_lion.contracts.mission_intent import MissionIntent, MissionIntentError
from cyber_lion.contracts.query_plan import QueryPlan
from cyber_lion.contracts.rag_context_envelope import RagContextEnvelope, RagContextSource, RagContextEnvelopeError
from cyber_lion.contracts.semantic_scaffold import SemanticScaffoldIR, ScaffoldRelation
from cyber_lion.contracts.semantic_relevance import (
    EvidenceInstance, SemanticAtom, SemanticDelta, RelevanceGraph,
    RelevanceProjection, SemanticRelevanceError,
)
from cyber_lion.contracts.semantic_cloud_episode_binding import SemanticCloudEpisodeBinding

H="a"*64
H2="b"*64

class SemanticCloudContractTests(unittest.TestCase):
    def mission(self):
        return MissionIntent(
            intent_id="intent:1",mission_ref="mission:1",conversation_ref="conversation:1",
            source_envelope_ref="envelope:1",source_envelope_digest=H,
            correlation_ref="corr:1",causation_ref=None,causal_group_ref="causal:1",
            intent_class="RESEARCH",goal_ref="goal:1",goal_digest=H2,
            required_capabilities=("research.read",),constraints=("no-effect",),
            preconditions=("current-source",),evidence_requirements=("evidence:grounded",),
            currentness_requirements=("currentness:source-bound",),next_representation="query-plan",
        ).sealed()

    def query(self):
        m=self.mission()
        return QueryPlan(
            plan_id="query:1",mission_intent_ref=m.intent_id,mission_intent_digest=m.intent_digest,
            question_refs=("question:1",),retrieval_semantics=("retrieval:source-bound",),
            evidence_requirements=("evidence:grounded",),scope=("scope:research",),budget_limit=1024,
            stop_conditions=("stop:sufficient-evidence",),currentness_requirements=("currentness:source-bound",),
        ).sealed()

    def context(self):
        q=self.query()
        source=RagContextSource(
            source_ref="source:1",content_digest=H,currentness="CURRENT",
            observed_at="2026-10-03T10:00:00Z",available_at="2026-10-03T10:01:00Z",
            provenance_refs=("prov:1",),
        )
        return RagContextEnvelope(
            envelope_id="rag:1",query_plan_ref=q.plan_id,query_plan_digest=q.plan_digest,
            knowledge_release_ref="rag-release:1",retrieval_time="2026-10-03T10:02:00Z",
            input_cutoff="2026-10-03T10:03:00Z",sources=(source,),
        ).sealed()

    def scaffold(self):
        m=self.mission();q=self.query();ctx=self.context()
        rel=ScaffoldRelation("rel:1","entity:a","supports","entity:b",("evidence:1",))
        return SemanticScaffoldIR(
            scaffold_id="scaffold:1",mission_intent_ref=m.intent_id,mission_intent_digest=m.intent_digest,
            query_plan_ref=q.plan_id,query_plan_digest=q.plan_digest,
            rag_context_ref=ctx.envelope_id,rag_context_digest=ctx.context_digest,
            entity_refs=("entity:a","entity:b"),relations=(rel,),
            gap_refs=(),dependency_refs=(),constraint_refs=("constraint:no-effect",),
            hypothesis_refs=("hypothesis:1",),counter_hypothesis_refs=("hypothesis:2",),
            falsifier_refs=("falsifier:1",),unknown_refs=("unknown:1",),
            capability_need_refs=(),representation_candidates=("representation:graph",),
            evidence_bindings=("evidence:1",),currentness_basis=("currentness:1",),
            next_frontier="relevance-graph",
        ).sealed()

    def test_mission_intent_is_non_effectful_and_digest_bound(self):
        m=self.mission()
        self.assertEqual(m.authority_effect,"NONE")
        self.assertEqual(m.effect,"NONE")
        with self.assertRaises(MissionIntentError):
            replace(m,goal_ref="goal:other").validate()

    def test_rag_context_rejects_future_information(self):
        q=self.query()
        source=RagContextSource(
            "source:future",H,"CURRENT","2026-10-03T10:00:00Z",
            "2026-10-03T10:05:00Z",("prov:1",)
        )
        with self.assertRaisesRegex(RagContextEnvelopeError,"post-cutoff"):
            RagContextEnvelope(
                "rag:future",q.plan_id,q.plan_digest,"rag-release:1",
                "2026-10-03T10:01:00Z","2026-10-03T10:03:00Z",(source,)
            ).sealed()

    def test_scaffold_is_non_effectful(self):
        s=self.scaffold()
        self.assertEqual(s.authority_effect,"NONE")
        self.assertEqual(s.effect,"NONE")

    def test_semantic_atom_collapses_duplicate_lineage_roots_without_losing_provenance(self):
        e1=EvidenceInstance("evidence:1","root:shared",H,"2026-10-03T10:00:00Z","CURRENT")
        e2=EvidenceInstance("evidence:2","root:shared",H2,"2026-10-03T10:01:00Z","CURRENT")
        atom=SemanticAtom(
            "atom:1","semantic:system-state","system is healthy",
            ("relation:state",),("scope:system",),"CURRENT",(e1,e2),
            ("representation:1","representation:2"),
        ).sealed()
        self.assertEqual(atom.independent_root_count(),1)
        self.assertEqual(len(atom.evidence),2)

    def test_semantic_delta_cannot_carry_credentials_or_authority_grant(self):
        for predicate in ("credentials","authority_grant","runtime_admission"):
            with self.assertRaisesRegex(SemanticRelevanceError,"denied"):
                SemanticDelta(
                    "delta:1",H,"ADD","entity:a",predicate,"entity:b",
                    ("evidence:1",),("currentness:1",),
                ).sealed()

    def test_relevance_projection_cannot_widen_graph_or_capability(self):
        graph=RelevanceGraph(
            "graph:1","intent:1","scaffold:1",
            ("atom:1","atom:2"),("edge:1",),("currentness:1",)
        ).sealed()
        ok=RelevanceProjection(
            "projection:1",graph.graph_id,graph.graph_digest,"consumer:1",
            ("capability:read",),("atom:1",),("edge:1",),(),10
        ).sealed()
        ok.validate_against(graph,("capability:read","capability:verify"))
        bad=replace(ok,required_capability_refs=("capability:write",)).sealed()
        with self.assertRaisesRegex(SemanticRelevanceError,"capability widening"):
            bad.validate_against(graph,("capability:read",))

    def test_episode_binding_is_non_effectful(self):
        b=SemanticCloudEpisodeBinding(
            binding_id="binding:1",eble_episode_ref="episode:1",eble_episode_digest=H,
            mission_intent_ref="intent:1",query_plan_ref="query:1",rag_context_ref="rag:1",
            semantic_scaffold_ref="scaffold:1",semantic_delta_refs=("delta:1",),
            relevance_graph_ref="graph:1",relevance_projection_refs=("projection:1",),
            capability_need_refs=(),composition_refs=(),mosaic_refs=(),
            decision_candidate_refs=("decision:1",),action_ir_candidate_ref=None,
        ).sealed()
        self.assertEqual(b.authority_effect,"NONE")
        self.assertEqual(b.effect,"NONE")

if __name__=="__main__":
    unittest.main()

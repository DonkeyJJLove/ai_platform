import inspect
import unittest
from dataclasses import replace
from hashlib import sha256

from cyber_lion.contracts.evolutionary_epoch import EpochTransition, RnDEventProjection
from cyber_lion.contracts.evolutionary_rnd import EvolutionDelta, PromotionDecision, RnDMemoryRecord
from cyber_lion.contracts.policy_gate import GateApplied
from cyber_lion.enterprise.evolutionary_epoch import EvolutionaryEpochEngine
from cyber_lion.enterprise.governed_change_proposal import (
    GovernedChangeProposalEngine,
    GovernedChangeProposalError,
)

H0 = "0" * 64
H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64


class GovernedChangeProposalEngineTests(unittest.TestCase):
    def build_lineage(self, *, target_component="epistemic-scoring", dependencies=("dep:alpha",), gate_decision="ALLOW", gate_authority="none", transition_state="NEXT_EPOCH_CANDIDATE_READY"):
        delta = EvolutionDelta(
            delta_id="delta:e004:1",
            target_component=target_component,
            motivation="Improve deterministic internal epistemic scoring",
            evidence_refs=("obs:1",),
            expected_outcome="Reduce scoring ambiguity",
            falsification_conditions=("no regression in deterministic scoring",),
            candidate_scope=("cyber_lion/scoring.py", "cyber_lion/tests/test_scoring.py"),
            dependency_ids=dependencies,
            risk_class="AMBER",
        ).sealed()
        gate = GateApplied(
            gate_event_id="gate:e004:1",
            request_id="request:e004:1",
            proposal_id="promotion:e004:1",
            decision=gate_decision,
            effective_authority=gate_authority,
            policy_binding="policy:e004@1:sha256:" + H1,
            authority_lineage_digest=H1,
            enterprise_graph_digest=H2,
            status_digest=H3,
            observability_state="HEALTHY",
            lane="AMBER",
            rationale="synthetic knowledge promotion gate",
        ).sealed()
        promotion = PromotionDecision(
            promotion_id="promotion:e004:1",
            hypothesis_digest=H1,
            hypothesis_state="SUPPORTED",
            falsification_digest=H2,
            falsification_disposition="SUPPORTED",
            evolution_delta_digest=delta.delta_digest,
            policy_decision_ref=f"pdp:{gate.decision_digest}",
            unresolved_contradictions=0,
            contrary_evidence_complete=True,
            decision="PROMOTE_KNOWLEDGE",
            rationale="bounded synthetic promotion",
        ).sealed()
        memory = RnDMemoryRecord(
            memory_id="memory:e004:1",
            revision=1,
            record_kind="PROMOTED_KNOWLEDGE",
            subject_id="delta:e004:1",
            source_digests=(promotion.promotion_digest,),
            negative_evidence_refs=("obs:counter",),
            supersedes_memory_digest=None,
            epistemic_status="SUPPORTED",
            committed_event_ref="event:memory-commit",
            previous_memory_head="GENESIS",
        ).sealed()
        memory_head = sha256(
            b"LION/E004-RND-MEMORY-CHAIN/1\0" + b"GENESIS" + memory.memory_digest.encode("ascii")
        ).hexdigest()
        transition = EpochTransition(
            epoch_id="E004",
            previous_epoch_id="E003",
            rnd_engine_state_digest=H0,
            memory_head=memory_head,
            promotion_digest=promotion.promotion_digest,
            evolution_delta_digest=delta.delta_digest,
            event_projection_digest=H3,
            graph_projection_digest=H4,
            state=transition_state,
        ).sealed()
        epoch_engine = EvolutionaryEpochEngine()
        epoch_engine.register_delta_lineage(delta, "E004")
        if gate.decision == "ALLOW" and gate.effective_authority == "none":
            epoch_engine.verify_promotion_gate(promotion, gate)
        candidate = RnDEventProjection(
            projection_id="projection:memory-candidate",
            record_type="RnDMemoryRecord",
            record_id=memory.memory_id,
            record_digest=memory.memory_digest,
            event_id="event:memory-candidate",
            event_type="MemoryCandidateCreated",
            correlation_id="corr:e004",
            causation_id=None,
            epistemic_state="DERIVED",
            provenance_refs=tuple(memory.source_digests) + tuple(memory.negative_evidence_refs),
        ).sealed()
        commit = RnDEventProjection(
            projection_id="projection:memory-commit",
            record_type="RnDMemoryRecord",
            record_id=memory.memory_id,
            record_digest=memory.memory_digest,
            event_id="event:memory-commit",
            event_type="MemoryCommitted",
            correlation_id="corr:e004",
            causation_id="event:memory-candidate",
            epistemic_state="DERIVED",
            provenance_refs=tuple(memory.source_digests) + tuple(memory.negative_evidence_refs),
        ).sealed()
        epoch_engine.bind_memory_candidate(memory, candidate)
        epoch_engine.bind_memory_commit(memory, "event:memory-candidate", commit, memory_head)
        return delta, transition, promotion, gate, memory, epoch_engine

    def derive(self, **kwargs):
        delta, transition, promotion, gate, memory, epoch_engine = self.build_lineage(**kwargs)
        engine = GovernedChangeProposalEngine()
        proposal = engine.derive(
            delta=delta,
            transition=transition,
            promotion=promotion,
            gate=gate,
            memory_record=memory,
            epoch_engine=epoch_engine,
        )
        return proposal, engine, (delta, transition, promotion, gate, memory, epoch_engine)

    def test_verified_lineage_derives_exact_non_effectful_proposal(self):
        proposal, engine, values = self.derive()
        delta = values[0]
        self.assertEqual(proposal.candidate_scope, delta.candidate_scope)
        self.assertEqual(proposal.target_component, delta.target_component)
        self.assertEqual(proposal.dependency_ids, delta.dependency_ids)
        self.assertEqual(proposal.falsification_conditions, delta.falsification_conditions)
        self.assertEqual(proposal.evidence_refs, delta.evidence_refs)
        self.assertEqual(proposal.authority_effect, "NONE")
        self.assertEqual(proposal.execution_effect, "NONE")
        self.assertEqual(len(engine.state_digest()), 64)

    def test_exact_source_replay_is_denied(self):
        proposal, engine, values = self.derive()
        delta, transition, promotion, gate, memory, epoch_engine = values
        with self.assertRaises(GovernedChangeProposalError):
            engine.derive(delta=delta, transition=transition, promotion=promotion, gate=gate, memory_record=memory, epoch_engine=epoch_engine)
        self.assertTrue(proposal.proposal_digest)

    def test_stale_or_substituted_lineage_is_denied(self):
        delta, transition, promotion, gate, memory, epoch_engine = self.build_lineage()
        engine = GovernedChangeProposalEngine()
        stale = replace(transition, transition_digest="", state="DELTA_SYNTHESIZED").sealed()
        with self.assertRaises(GovernedChangeProposalError):
            engine.derive(delta=delta, transition=stale, promotion=promotion, gate=gate, memory_record=memory, epoch_engine=epoch_engine)
        wrong_delta = replace(transition, transition_digest="", evolution_delta_digest=H4).sealed()
        with self.assertRaises(GovernedChangeProposalError):
            engine.derive(delta=delta, transition=wrong_delta, promotion=promotion, gate=gate, memory_record=memory, epoch_engine=epoch_engine)
        wrong_promotion = replace(transition, transition_digest="", promotion_digest=H4).sealed()
        with self.assertRaises(GovernedChangeProposalError):
            engine.derive(delta=delta, transition=wrong_promotion, promotion=promotion, gate=gate, memory_record=memory, epoch_engine=epoch_engine)
        wrong_head = replace(transition, transition_digest="", memory_head=H4).sealed()
        with self.assertRaises(GovernedChangeProposalError):
            engine.derive(delta=delta, transition=wrong_head, promotion=promotion, gate=gate, memory_record=memory, epoch_engine=epoch_engine)

    def test_unsealed_delta_and_unverified_pdp_are_denied(self):
        delta, transition, promotion, gate, memory, epoch_engine = self.build_lineage()
        engine = GovernedChangeProposalEngine()
        with self.assertRaises(GovernedChangeProposalError):
            engine.derive(delta=replace(delta, delta_digest=""), transition=transition, promotion=promotion, gate=gate, memory_record=memory, epoch_engine=epoch_engine)
        d2, t2, p2, deny_gate, m2, e2 = self.build_lineage(gate_decision="DENY")
        with self.assertRaises(GovernedChangeProposalError):
            engine.derive(delta=d2, transition=t2, promotion=p2, gate=deny_gate, memory_record=m2, epoch_engine=e2)
        d3, t3, p3, authority_gate, m3, e3 = self.build_lineage(gate_authority="write")
        with self.assertRaises(GovernedChangeProposalError):
            engine.derive(delta=d3, transition=t3, promotion=p3, gate=authority_gate, memory_record=m3, epoch_engine=e3)

    def test_f005_target_or_dependency_is_denied(self):
        for kwargs in ({"target_component": "F005-execution-mesh"}, {"dependencies": ("F005",)}):
            delta, transition, promotion, gate, memory, epoch_engine = self.build_lineage(**kwargs)
            with self.assertRaises(GovernedChangeProposalError):
                GovernedChangeProposalEngine().derive(delta=delta, transition=transition, promotion=promotion, gate=gate, memory_record=memory, epoch_engine=epoch_engine)

    def test_scope_and_semantics_are_not_caller_supplied(self):
        parameters = inspect.signature(GovernedChangeProposalEngine.derive).parameters
        for forbidden in ("candidate_scope", "target_component", "dependency_ids", "evidence_refs", "falsification_conditions", "authority_effect", "execution_effect"):
            self.assertNotIn(forbidden, parameters)

    def test_no_effect_surface_is_exposed(self):
        public = {name for name, _ in inspect.getmembers(GovernedChangeProposalEngine, inspect.isfunction) if not name.startswith("_")}
        for forbidden in ("execute", "write", "push", "merge", "deploy", "release", "create_branch", "create_pr", "dispatch"):
            self.assertNotIn(forbidden, public)


if __name__ == "__main__":
    unittest.main()

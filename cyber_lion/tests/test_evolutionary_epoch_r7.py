from hashlib import sha256
import unittest

from cyber_lion.contracts.events import Authority, EventEnvelope, Provenance
from cyber_lion.contracts.policy_gate import GateApplied
from cyber_lion.contracts.evolutionary_rnd import EvolutionDelta, PromotionDecision, RnDMemoryRecord
from cyber_lion.contracts.evolutionary_epoch import EpochTransition
from cyber_lion.enterprise.evolutionary_epoch import EvolutionaryEpochEngine, EvolutionaryEpochError

H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64


def envelope(record_id, record_digest, event_id, event_type, upstream, causation_id=None, policy_ids=None):
    return EventEnvelope(
        schema_version="1.0.0",
        event_id=event_id,
        event_type=event_type,
        occurred_at="2026-08-25T00:00:00Z",
        correlation_id="corr:e004:r7",
        entity={"entity_id": record_id},
        source={"component": "evolutionary_epoch_r7_test"},
        provenance=Provenance(
            epistemic_status="DERIVED",
            upstream=list(upstream),
            transformation_chain=["R7"],
        ),
        authority=Authority(
            requested="none",
            effective="none",
            policy_ids=list(policy_ids or []),
        ),
        epistemic_state="FORMALISED",
        payload={"record_digest": record_digest},
        causation_id=causation_id,
    )


class EvolutionaryEpochR7LineageBindingTests(unittest.TestCase):
    def _ready_fixture(self):
        engine = EvolutionaryEpochEngine()
        delta = EvolutionDelta(
            delta_id="delta:r7",
            target_component="rnd-loop",
            motivation="bounded knowledge",
            evidence_refs=("evidence:r7",),
            expected_outcome="candidate only",
            falsification_conditions=("regression",),
            candidate_scope=("cyber_lion/contracts/example.py",),
            dependency_ids=(),
            risk_class="GREEN",
        ).sealed()
        gate = GateApplied(
            gate_event_id="gate:r7",
            request_id="request:r7",
            proposal_id="promotion:r7",
            decision="ALLOW",
            effective_authority="none",
            policy_binding="rnd-policy@1:sha256:" + H1,
            authority_lineage_digest=H1,
            enterprise_graph_digest=H2,
            status_digest=H3,
            observability_state="HEALTHY",
            lane="GREEN",
            rationale="knowledge promotion only",
        ).sealed()
        promotion = PromotionDecision(
            promotion_id="promotion:r7",
            hypothesis_digest=H1,
            hypothesis_state="SUPPORTED",
            falsification_digest=H2,
            falsification_disposition="SUPPORTED",
            evolution_delta_digest=delta.delta_digest,
            policy_decision_ref="pdp:" + gate.decision_digest,
            unresolved_contradictions=0,
            contrary_evidence_complete=True,
            decision="PROMOTE_KNOWLEDGE",
            rationale="bounded",
        ).sealed()
        engine.verify_promotion_gate(promotion, gate)

        memory = RnDMemoryRecord(
            memory_id="mem:r7",
            revision=1,
            record_kind="PROMOTED_KNOWLEDGE",
            subject_id="promotion:r7",
            source_digests=(promotion.promotion_digest,),
            negative_evidence_refs=(),
            supersedes_memory_digest=None,
            epistemic_status="SUPPORTED",
            committed_event_ref="evt:r7:mem:commit",
            previous_memory_head="GENESIS",
        ).sealed()
        candidate = engine.project_event(
            memory,
            envelope(
                "mem:r7",
                memory.memory_digest,
                "evt:r7:mem:candidate",
                "MemoryCandidateCreated",
                (promotion.promotion_digest,),
            ),
            "proj:r7:mem:candidate",
        )
        engine.bind_memory_candidate(memory, candidate)
        commit = engine.project_event(
            memory,
            envelope(
                "mem:r7",
                memory.memory_digest,
                "evt:r7:mem:commit",
                "MemoryCommitted",
                (promotion.promotion_digest,),
                causation_id="evt:r7:mem:candidate",
                policy_ids=["rnd-memory-policy"],
            ),
            "proj:r7:mem:commit",
        )
        head = sha256(
            b"LION/E004-RND-MEMORY-CHAIN/1\0"
            + b"GENESIS"
            + memory.memory_digest.encode("ascii")
        ).hexdigest()
        engine.bind_memory_commit(memory, "evt:r7:mem:candidate", commit, head)

        transition = EpochTransition(
            epoch_id="E004",
            previous_epoch_id="E003",
            rnd_engine_state_digest=H1,
            memory_head=head,
            promotion_digest=promotion.promotion_digest,
            evolution_delta_digest=delta.delta_digest,
            event_projection_digest=H3,
            graph_projection_digest=H4,
            state="EPOCH_OPEN",
        ).sealed()
        for state in (
            "OBSERVING",
            "HYPOTHESIS_SPACE_ACTIVE",
            "TESTING",
            "FALSIFICATION_COMPLETE",
            "KNOWLEDGE_PROMOTION_READY",
            "KNOWLEDGE_PROMOTED",
            "MEMORY_COMMITTED",
            "DELTA_SYNTHESIZED",
            "NEXT_EPOCH_CANDIDATE_READY",
        ):
            transition = engine.transition_epoch(transition, state)
        return engine, delta, promotion, memory, transition

    def test_readiness_requires_prior_delta_lineage_admission(self):
        engine, delta, promotion, memory, transition = self._ready_fixture()
        with self.assertRaisesRegex(EvolutionaryEpochError, "NEXT_EPOCH_DELTA_LINEAGE_MISSING"):
            engine.assert_next_epoch_ready(transition, delta, promotion, memory)

    def test_readiness_requires_exact_epoch_lineage_binding(self):
        engine, delta, promotion, memory, transition = self._ready_fixture()
        engine.register_delta_lineage(delta, "E003")
        with self.assertRaisesRegex(EvolutionaryEpochError, "NEXT_EPOCH_DELTA_LINEAGE_EPOCH_MISMATCH"):
            engine.assert_next_epoch_ready(transition, delta, promotion, memory)

    def test_exact_current_epoch_delta_lineage_allows_readiness(self):
        engine, delta, promotion, memory, transition = self._ready_fixture()
        before = engine.state_digest()
        engine.register_delta_lineage(delta, "E004")
        after = engine.state_digest()
        self.assertNotEqual(before, after)
        engine.assert_next_epoch_ready(transition, delta, promotion, memory)

    def test_delta_lineage_replay_and_cross_epoch_replay_remain_denied(self):
        engine, delta, _, _, _ = self._ready_fixture()
        engine.register_delta_lineage(delta, "E004")
        with self.assertRaisesRegex(EvolutionaryEpochError, "same-epoch"):
            engine.register_delta_lineage(delta, "E004")
        with self.assertRaisesRegex(EvolutionaryEpochError, "cross-epoch"):
            engine.register_delta_lineage(delta, "E005")


if __name__ == "__main__":
    unittest.main()

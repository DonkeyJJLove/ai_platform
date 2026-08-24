from dataclasses import replace
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


def envelope(record, event_id, event_type, causation_id=None):
    return EventEnvelope(
        schema_version="1.0.0",
        event_id=event_id,
        event_type=event_type,
        occurred_at="2026-08-25T00:00:00Z",
        correlation_id="corr:e004:r5-r4",
        entity={"entity_id": record.memory_id},
        source={"component": "e004_r5_r4_test"},
        provenance=Provenance(
            epistemic_status="DERIVED",
            upstream=list(record.source_digests) + list(record.negative_evidence_refs),
            transformation_chain=["R5-R4"],
        ),
        authority=Authority(requested="none", effective="none", policy_ids=["rnd-memory-policy"]),
        epistemic_state="FORMALISED",
        payload={"record_digest": record.memory_digest, "candidate_event_id": "evt:mem:candidate"},
        causation_id=causation_id,
    )


class EvolutionaryEpochMemoryHeadBindingTests(unittest.TestCase):
    def setUp(self):
        self.engine = EvolutionaryEpochEngine()
        self.gate = GateApplied(
            gate_event_id="gate:r5-r4", request_id="request:r5-r4", proposal_id="promotion:r5-r4",
            decision="ALLOW", effective_authority="none", policy_binding="rnd-policy@1:sha256:" + H1,
            authority_lineage_digest=H1, enterprise_graph_digest=H2, status_digest=H3,
            observability_state="HEALTHY", lane="GREEN", rationale="knowledge promotion only",
        ).sealed()
        self.delta = EvolutionDelta(
            delta_id="delta:r5-r4", target_component="rnd-loop", motivation="bounded knowledge delta",
            evidence_refs=("evidence:r5-r4",), expected_outcome="candidate only",
            falsification_conditions=("memory lineage mismatch",),
            candidate_scope=("cyber_lion/contracts/example.py",), dependency_ids=(), risk_class="GREEN",
        ).sealed()
        self.promotion = PromotionDecision(
            promotion_id="promotion:r5-r4", hypothesis_digest=H1, hypothesis_state="SUPPORTED",
            falsification_digest=H2, falsification_disposition="SUPPORTED",
            evolution_delta_digest=self.delta.delta_digest,
            policy_decision_ref="pdp:" + self.gate.decision_digest,
            unresolved_contradictions=0, contrary_evidence_complete=True,
            decision="PROMOTE_KNOWLEDGE", rationale="supported evidence",
        ).sealed()
        self.engine.verify_promotion_gate(self.promotion, self.gate)
        self.engine.register_delta_lineage(self.delta, "E004")

    def _commit_memory(self, memory_id, previous_head="GENESIS", revision=1):
        record = RnDMemoryRecord(
            memory_id=memory_id,
            revision=revision,
            record_kind="PROMOTED_KNOWLEDGE",
            subject_id=self.promotion.promotion_id,
            source_digests=(self.promotion.promotion_digest,),
            negative_evidence_refs=(),
            supersedes_memory_digest=None,
            epistemic_status="SUPPORTED",
            committed_event_ref="evt:mem:commit",
            previous_memory_head=previous_head,
        ).sealed()
        candidate = self.engine.project_event(
            record,
            envelope(record, "evt:mem:candidate", "MemoryCandidateCreated"),
            "proj:mem:candidate",
        )
        self.engine.bind_memory_candidate(record, candidate)
        commit = self.engine.project_event(
            record,
            envelope(record, "evt:mem:commit", "MemoryCommitted", causation_id="evt:mem:candidate"),
            "proj:mem:commit",
        )
        head = sha256(
            b"LION/E004-RND-MEMORY-CHAIN/1\0"
            + previous_head.encode("ascii")
            + record.memory_digest.encode("ascii")
        ).hexdigest()
        self.engine.bind_memory_commit(record, "evt:mem:candidate", commit, head)
        return record, head

    def _ready_transition(self, memory_head):
        return EpochTransition(
            epoch_id="E004", previous_epoch_id="E003", rnd_engine_state_digest=H1,
            memory_head=memory_head, promotion_digest=self.promotion.promotion_digest,
            evolution_delta_digest=self.delta.delta_digest,
            event_projection_digest=H3, graph_projection_digest=H4,
            state="NEXT_EPOCH_CANDIDATE_READY",
        ).sealed()

    def test_exact_committed_memory_head_is_required_and_accepted(self):
        memory, head = self._commit_memory("mem:r5-r4")
        self.engine.assert_next_epoch_ready(
            self._ready_transition(head), self.delta, self.promotion, memory
        )

    def test_substituted_previous_genesis_and_arbitrary_heads_are_denied(self):
        memory, head = self._commit_memory("mem:r5-r4")
        self.assertNotEqual(head, H4)
        for bad_head in (H4, "GENESIS"):
            with self.subTest(memory_head=bad_head):
                with self.assertRaisesRegex(EvolutionaryEpochError, "NEXT_EPOCH_MEMORY_HEAD_MISMATCH"):
                    self.engine.assert_next_epoch_ready(
                        self._ready_transition(bad_head), self.delta, self.promotion, memory
                    )

    def test_head_from_another_committed_memory_record_is_denied(self):
        first, first_head = self._commit_memory("mem:r5-r4:first")
        second = RnDMemoryRecord(
            memory_id="mem:r5-r4:second", revision=2, record_kind="PROMOTED_KNOWLEDGE",
            subject_id=self.promotion.promotion_id, source_digests=(self.promotion.promotion_digest,),
            negative_evidence_refs=(), supersedes_memory_digest=first.memory_digest,
            epistemic_status="SUPPORTED", committed_event_ref="evt:mem2:commit",
            previous_memory_head=first_head,
        ).sealed()
        candidate_evt = EventEnvelope(
            schema_version="1.0.0", event_id="evt:mem2:candidate", event_type="MemoryCandidateCreated",
            occurred_at="2026-08-25T00:00:01Z", correlation_id="corr:e004:r5-r4:2",
            entity={"entity_id": second.memory_id}, source={"component": "e004_r5_r4_test"},
            provenance=Provenance(epistemic_status="DERIVED", upstream=[self.promotion.promotion_digest], transformation_chain=["R5-R4"]),
            authority=Authority(requested="none", effective="none", policy_ids=["rnd-memory-policy"]),
            epistemic_state="FORMALISED", payload={"record_digest": second.memory_digest},
        )
        candidate = self.engine.project_event(second, candidate_evt, "proj:mem2:candidate")
        self.engine.bind_memory_candidate(second, candidate)
        commit_evt = replace(
            candidate_evt,
            event_id="evt:mem2:commit",
            event_type="MemoryCommitted",
            causation_id="evt:mem2:candidate",
            payload={"record_digest": second.memory_digest, "candidate_event_id": "evt:mem2:candidate"},
        )
        commit = self.engine.project_event(second, commit_evt, "proj:mem2:commit")
        second_head = sha256(
            b"LION/E004-RND-MEMORY-CHAIN/1\0"
            + first_head.encode("ascii")
            + second.memory_digest.encode("ascii")
        ).hexdigest()
        self.engine.bind_memory_commit(second, "evt:mem2:candidate", commit, second_head)
        with self.assertRaisesRegex(EvolutionaryEpochError, "NEXT_EPOCH_MEMORY_HEAD_MISMATCH"):
            self.engine.assert_next_epoch_ready(
                self._ready_transition(second_head), self.delta, self.promotion, first
            )


if __name__ == "__main__":
    unittest.main()
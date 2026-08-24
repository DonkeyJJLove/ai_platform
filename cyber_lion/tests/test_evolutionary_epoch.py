from dataclasses import replace
from hashlib import sha256
import unittest

from cyber_lion.contracts.enterprise_graph import GraphEdge, GraphNode
from cyber_lion.contracts.events import Authority, EventEnvelope, Provenance
from cyber_lion.contracts.policy_gate import GateApplied
from cyber_lion.contracts.evolutionary_rnd import (
    EvidenceObservation, EvolutionDelta, PromotionDecision, RnDMemoryRecord,
)
from cyber_lion.contracts.evolutionary_epoch import EpochTransition
from cyber_lion.enterprise.evolutionary_epoch import (
    EvolutionaryEpochEngine, EvolutionaryEpochError, assert_no_effect_surface,
)

H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64


def envelope(record_id, record_digest, event_id, event_type, upstream=("src:1",), causation_id=None,
             requested="none", effective="none", policy_ids=None, extra_payload=None):
    payload = {"record_digest": record_digest}
    if extra_payload:
        payload.update(extra_payload)
    return EventEnvelope(
        schema_version="1.0.0",
        event_id=event_id,
        event_type=event_type,
        occurred_at="2026-08-25T00:00:00Z",
        correlation_id="corr:e004",
        entity={"entity_id": record_id},
        source={"component": "evolutionary_epoch_test"},
        provenance=Provenance(epistemic_status="DERIVED", upstream=list(upstream), transformation_chain=["R4"]),
        authority=Authority(requested=requested, effective=effective, policy_ids=list(policy_ids or [])),
        epistemic_state="FORMALISED",
        payload=payload,
        causation_id=causation_id,
    )


class EvolutionaryEpochIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = EvolutionaryEpochEngine()
        self.obs = EvidenceObservation(
            observation_id="obs:1",
            observation_kind="TEST",
            source_ref="source:test",
            source_digest=H1,
            observed_at="2026-08-25T00:00:00Z",
            epistemic_class="OBSERVED",
            provenance_refs=("src:1",),
            content_digest=H2,
        ).sealed()

    @staticmethod
    def _gate(proposal_id="promotion:gate", decision="ALLOW", effective_authority="none",
              request_id="request:gate", rationale="knowledge promotion only"):
        return GateApplied(
            gate_event_id="gate:" + request_id, request_id=request_id, proposal_id=proposal_id,
            decision=decision, effective_authority=effective_authority,
            policy_binding="rnd-policy@1:sha256:" + H1,
            authority_lineage_digest=H1, enterprise_graph_digest=H2, status_digest=H3,
            observability_state="HEALTHY", lane="GREEN", rationale=rationale,
        ).sealed()

    @staticmethod
    def _promotion(gate, promotion_id=None, hypothesis_digest=H1, rationale="supported evidence"):
        return PromotionDecision(
            promotion_id=promotion_id or gate.proposal_id,
            hypothesis_digest=hypothesis_digest, hypothesis_state="SUPPORTED",
            falsification_digest=H2, falsification_disposition="SUPPORTED", evolution_delta_digest=H3,
            policy_decision_ref="pdp:" + gate.decision_digest, unresolved_contradictions=0,
            contrary_evidence_complete=True, decision="PROMOTE_KNOWLEDGE", rationale=rationale,
        ).sealed()

    def test_event_and_graph_projection_are_exact_and_deterministic(self):
        evt = envelope("obs:1", self.obs.observation_digest, "evt:obs:1", "ObservationCreated")
        projection = self.engine.project_event(self.obs, evt, "proj:event:1")
        node = GraphNode(
            node_id="obs:1",
            node_type="EVIDENCE",
            version="1",
            payload={"record_digest": self.obs.observation_digest, "event_id": "evt:obs:1"},
            provenance_refs=("src:1",),
        )
        edge = GraphEdge(
            edge_id="edge:obs:1",
            plane="DATA_PROVENANCE",
            edge_type="DERIVED_FROM",
            source_id="obs:1",
            target_id="source:1",
            provenance_refs=("src:1",),
        )
        graph = self.engine.project_graph(self.obs, projection, node, (edge,), "proj:graph:1")
        graph2 = EvolutionaryEpochEngine().project_graph(
            self.obs,
            EvolutionaryEpochEngine().project_event(self.obs, evt, "proj:event:1"),
            node, (edge,), "proj:graph:1"
        )
        self.assertEqual(graph.projection_digest, graph2.projection_digest)

    def test_event_authority_and_digest_substitution_denied(self):
        bad_auth = envelope("obs:1", self.obs.observation_digest, "evt:1", "ObservationCreated", effective="write")
        with self.assertRaises(EvolutionaryEpochError):
            self.engine.project_event(self.obs, bad_auth, "proj:1")
        bad_digest = envelope("obs:1", H4, "evt:2", "ObservationCreated")
        with self.assertRaises(EvolutionaryEpochError):
            self.engine.project_event(self.obs, bad_digest, "proj:2")

    def test_action_event_mapping_is_denied(self):
        evt = envelope("obs:1", self.obs.observation_digest, "evt:action", "ActionAuthorized")
        with self.assertRaises(EvolutionaryEpochError):
            self.engine.project_event(self.obs, evt, "proj:action")

    def test_authority_plane_graph_edge_denied(self):
        evt = envelope("obs:1", self.obs.observation_digest, "evt:obs", "ObservationCreated")
        projection = self.engine.project_event(self.obs, evt, "proj:event")
        node = GraphNode(
            node_id="obs:1", node_type="EVIDENCE", version="1",
            payload={"record_digest": self.obs.observation_digest, "event_id": "evt:obs"},
            provenance_refs=("src:1",),
        )
        edge = GraphEdge(
            edge_id="edge:authority", plane="AUTHORITY_REFERENCE",
            edge_type="AUTHORITY_REFERENCED_BY", source_id="obs:1", target_id="auth:1",
            provenance_refs=("src:1",),
        )
        with self.assertRaises(EvolutionaryEpochError):
            self.engine.project_graph(self.obs, projection, node, (edge,), "proj:graph")

    def test_memory_candidate_commit_and_replay_denial(self):
        record = RnDMemoryRecord(
            memory_id="mem:1", revision=1, record_kind="OBSERVATION", subject_id="obs:1",
            source_digests=(self.obs.observation_digest,), negative_evidence_refs=(),
            supersedes_memory_digest=None, epistemic_status="OBSERVED",
            committed_event_ref="evt:mem:commit", previous_memory_head="GENESIS",
        ).sealed()
        upstream = (self.obs.observation_digest,)
        candidate_evt = envelope("mem:1", record.memory_digest, "evt:mem:candidate", "MemoryCandidateCreated", upstream=upstream)
        candidate = self.engine.project_event(record, candidate_evt, "proj:mem:candidate")
        self.engine.bind_memory_candidate(record, candidate)
        commit_evt = envelope(
            "mem:1", record.memory_digest, "evt:mem:commit", "MemoryCommitted",
            upstream=upstream, causation_id="evt:mem:candidate", policy_ids=["rnd-memory-policy"],
            extra_payload={"candidate_event_id": "evt:mem:candidate"},
        )
        commit = self.engine.project_event(record, commit_evt, "proj:mem:commit")
        expected_head = sha256(
            b"LION/E004-RND-MEMORY-CHAIN/1\0" + b"GENESIS" + record.memory_digest.encode("ascii")
        ).hexdigest()
        self.engine.bind_memory_commit(record, "evt:mem:candidate", commit, expected_head)
        with self.assertRaises(EvolutionaryEpochError):
            self.engine.bind_memory_commit(record, "evt:mem:candidate", commit, expected_head)

    def test_memory_head_mismatch_denied(self):
        record = RnDMemoryRecord(
            memory_id="mem:2", revision=1, record_kind="NEGATIVE_RESULT", subject_id="hyp:bad",
            source_digests=(H1,), negative_evidence_refs=("negative:1",), supersedes_memory_digest=None,
            epistemic_status="FALSIFIED", committed_event_ref="evt:mem2:commit", previous_memory_head="GENESIS",
        ).sealed()
        upstream = (H1, "negative:1")
        candidate = self.engine.project_event(
            record, envelope("mem:2", record.memory_digest, "evt:mem2:candidate", "MemoryCandidateCreated", upstream=upstream), "proj:c2"
        )
        self.engine.bind_memory_candidate(record, candidate)
        commit = self.engine.project_event(
            record,
            envelope("mem:2", record.memory_digest, "evt:mem2:commit", "MemoryCommitted",
                     upstream=upstream, causation_id="evt:mem2:candidate", policy_ids=["rnd-memory-policy"],
                     extra_payload={"candidate_event_id": "evt:mem2:candidate"}),
            "proj:m2",
        )
        with self.assertRaises(EvolutionaryEpochError):
            self.engine.bind_memory_commit(record, "evt:mem2:candidate", commit, H4)

    def test_memory_event_omitted_provenance_is_denied(self):
        record = RnDMemoryRecord(
            memory_id="mem:prov", revision=1, record_kind="NEGATIVE_RESULT", subject_id="hyp:prov",
            source_digests=(H1,), negative_evidence_refs=("negative:prov",), supersedes_memory_digest=None,
            epistemic_status="FALSIFIED", committed_event_ref="evt:prov", previous_memory_head="GENESIS",
        ).sealed()
        incomplete = envelope("mem:prov", record.memory_digest, "evt:prov:candidate", "MemoryCandidateCreated", upstream=(H1,))
        with self.assertRaisesRegex(EvolutionaryEpochError, "provenance"):
            self.engine.project_event(record, incomplete, "proj:prov")

    def test_promotion_requires_exact_allow_gate_evidence(self):
        gate = GateApplied(
            gate_event_id="gate:1", request_id="request:1", proposal_id="promotion:1",
            decision="ALLOW", effective_authority="none", policy_binding="rnd-policy@1:sha256:" + H1,
            authority_lineage_digest=H1, enterprise_graph_digest=H2, status_digest=H3,
            observability_state="HEALTHY", lane="GREEN", rationale="knowledge promotion only",
        ).sealed()
        decision = PromotionDecision(
            promotion_id="promotion:1", hypothesis_digest=H1, hypothesis_state="SUPPORTED",
            falsification_digest=H2, falsification_disposition="SUPPORTED", evolution_delta_digest=H3,
            policy_decision_ref="pdp:" + gate.decision_digest, unresolved_contradictions=0,
            contrary_evidence_complete=True, decision="PROMOTE_KNOWLEDGE", rationale="supported evidence",
        ).sealed()
        self.engine.verify_promotion_gate(decision, gate)
        denied = replace(gate, decision="DENY", effective_authority="none", decision_digest="").sealed()
        with self.assertRaises(EvolutionaryEpochError):
            self.engine.verify_promotion_gate(decision, denied)

    def test_promotion_gate_verification_is_state_bound_and_digest_bound(self):
        gate = self._gate()
        decision = self._promotion(gate)
        before = self.engine.state_digest()
        self.engine.verify_promotion_gate(decision, gate)
        after = self.engine.state_digest()
        self.assertNotEqual(before, after)
        self.engine.verify_promotion_gate(decision, gate)
        self.assertEqual(after, self.engine.state_digest())

    def test_promotion_gate_negative_matrix(self):
        gate = self._gate()
        decision = self._promotion(gate)
        denied_gate = self._gate(decision="DENY", request_id="request:deny")
        with self.assertRaisesRegex(EvolutionaryEpochError, "DENY"):
            EvolutionaryEpochEngine().verify_promotion_gate(
                replace(decision, policy_decision_ref="pdp:" + denied_gate.decision_digest, promotion_digest="").sealed(),
                denied_gate,
            )
        wrong_proposal_gate = self._gate(proposal_id="promotion:other", request_id="request:other")
        wrong_proposal_decision = replace(
            decision, policy_decision_ref="pdp:" + wrong_proposal_gate.decision_digest, promotion_digest=""
        ).sealed()
        with self.assertRaisesRegex(EvolutionaryEpochError, "proposal"):
            EvolutionaryEpochEngine().verify_promotion_gate(wrong_proposal_decision, wrong_proposal_gate)
        wrong_ref_decision = replace(decision, policy_decision_ref="pdp:" + H4, promotion_digest="").sealed()
        with self.assertRaisesRegex(EvolutionaryEpochError, "digest"):
            EvolutionaryEpochEngine().verify_promotion_gate(wrong_ref_decision, gate)
        authority_gate = self._gate(effective_authority="write", request_id="request:authority")
        authority_decision = replace(
            decision, policy_decision_ref="pdp:" + authority_gate.decision_digest, promotion_digest=""
        ).sealed()
        with self.assertRaisesRegex(EvolutionaryEpochError, "authority"):
            EvolutionaryEpochEngine().verify_promotion_gate(authority_decision, authority_gate)

    def test_gate_decision_cannot_be_rebound_to_incompatible_promotion(self):
        gate = self._gate(proposal_id="promotion:shared")
        first = self._promotion(gate, hypothesis_digest=H1, rationale="first")
        second = self._promotion(gate, hypothesis_digest=H4, rationale="second")
        self.engine.verify_promotion_gate(first, gate)
        with self.assertRaisesRegex(EvolutionaryEpochError, "rebound"):
            self.engine.verify_promotion_gate(second, gate)

    def test_promotion_control_record_provenance_and_graph_projection(self):
        decision = PromotionDecision(
            promotion_id="promotion:prov", hypothesis_digest=H1, hypothesis_state="SUPPORTED",
            falsification_digest=H2, falsification_disposition="SUPPORTED", evolution_delta_digest=H3,
            policy_decision_ref="pdp:" + H4, unresolved_contradictions=0, contrary_evidence_complete=True,
            decision="PROMOTE_KNOWLEDGE", rationale="knowledge only",
        ).sealed()
        upstream = (H1, H2, H3, "pdp:" + H4)
        evt = envelope("promotion:prov", decision.promotion_digest, "evt:promotion:prov", "DecisionProposed", upstream=upstream)
        projection = self.engine.project_event(decision, evt, "proj:promotion:prov")
        node = GraphNode(
            node_id="promotion:prov", node_type="ARTIFACT", version="1",
            payload={"record_digest": decision.promotion_digest, "event_id": "evt:promotion:prov"},
            provenance_refs=upstream,
        )
        edge = GraphEdge(
            edge_id="edge:promotion:prov", plane="DATA_PROVENANCE", edge_type="DERIVED_FROM",
            source_id="promotion:prov", target_id="hypothesis:source", provenance_refs=upstream,
        )
        graph = self.engine.project_graph(decision, projection, node, (edge,), "proj:graph:promotion")
        self.assertEqual(graph.node_type, "ARTIFACT")
        for bad_upstream in ((H2, H3, "pdp:" + H4), (H1, H2, H3, "pdp:" + H3), (H2, H1, H3, "pdp:" + H4)):
            with self.subTest(upstream=bad_upstream):
                bad = envelope("promotion:prov", decision.promotion_digest, "evt:promotion:bad:" + str(len(bad_upstream)), "DecisionProposed", upstream=bad_upstream)
                with self.assertRaisesRegex(EvolutionaryEpochError, "provenance"):
                    EvolutionaryEpochEngine().project_event(decision, bad, "proj:promotion:bad")
        effect_evt = envelope("promotion:prov", decision.promotion_digest, "evt:promotion:effect", "ActionAuthorized", upstream=upstream)
        with self.assertRaises(EvolutionaryEpochError):
            EvolutionaryEpochEngine().project_event(decision, effect_evt, "proj:promotion:effect")

    def test_evolution_delta_control_record_provenance_and_graph_projection(self):
        delta = EvolutionDelta(
            delta_id="delta:prov", target_component="rnd-loop", motivation="bounded knowledge",
            evidence_refs=("evidence:1", "evidence:2"), expected_outcome="candidate only",
            falsification_conditions=("regression",), candidate_scope=("cyber_lion/contracts/example.py",),
            dependency_ids=("dependency:metadata",), risk_class="GREEN",
        ).sealed()
        upstream = delta.evidence_refs
        evt = envelope("delta:prov", delta.delta_digest, "evt:delta:prov", "DeltaDetected", upstream=upstream)
        projection = self.engine.project_event(delta, evt, "proj:delta:prov")
        node = GraphNode(
            node_id="delta:prov", node_type="ARTIFACT", version="1",
            payload={"record_digest": delta.delta_digest, "event_id": "evt:delta:prov"},
            provenance_refs=upstream,
        )
        edge = GraphEdge(
            edge_id="edge:delta:prov", plane="DATA_PROVENANCE", edge_type="DERIVED_FROM",
            source_id="delta:prov", target_id="evidence:1", provenance_refs=upstream,
        )
        graph = self.engine.project_graph(delta, projection, node, (edge,), "proj:graph:delta")
        self.assertEqual(graph.node_type, "ARTIFACT")
        for bad_upstream in (("evidence:1",), ("evidence:1", "evidence:2", "injected:extra")):
            with self.subTest(upstream=bad_upstream):
                bad = envelope("delta:prov", delta.delta_digest, "evt:delta:bad:" + str(len(bad_upstream)), "DeltaDetected", upstream=bad_upstream)
                with self.assertRaisesRegex(EvolutionaryEpochError, "provenance"):
                    EvolutionaryEpochEngine().project_event(delta, bad, "proj:delta:bad")
        bad_auth = envelope("delta:prov", delta.delta_digest, "evt:delta:auth", "DeltaDetected", upstream=upstream, effective="write")
        with self.assertRaises(EvolutionaryEpochError):
            EvolutionaryEpochEngine().project_event(delta, bad_auth, "proj:delta:auth")
        effect_evt = envelope("delta:prov", delta.delta_digest, "evt:delta:effect", "ActionExecuted", upstream=upstream)
        with self.assertRaises(EvolutionaryEpochError):
            EvolutionaryEpochEngine().project_event(delta, effect_evt, "proj:delta:effect")

    def test_epoch_transitions_forward_only(self):
        current = EpochTransition(
            epoch_id="E004", previous_epoch_id="E003", rnd_engine_state_digest=H1,
            memory_head=H2, promotion_digest=H3, evolution_delta_digest=H4,
            event_projection_digest=H1, graph_projection_digest=H2, state="EPOCH_OPEN",
        ).sealed()
        nxt = self.engine.transition_epoch(current, "OBSERVING")
        self.assertEqual(nxt.state, "OBSERVING")
        with self.assertRaises(EvolutionaryEpochError):
            self.engine.transition_epoch(nxt, "TESTING")
        with self.assertRaises(EvolutionaryEpochError):
            self.engine.transition_epoch(nxt, "EPOCH_OPEN")

    def test_delta_lineage_same_epoch_and_cross_epoch_replay_denied(self):
        delta = EvolutionDelta(
            delta_id="delta:replay", target_component="rnd-loop", motivation="bounded knowledge",
            evidence_refs=("evidence:1",), expected_outcome="candidate only",
            falsification_conditions=("regression",), candidate_scope=("cyber_lion/contracts/example.py",),
            dependency_ids=(), risk_class="GREEN",
        ).sealed()
        self.engine.register_delta_lineage(delta, "E004")
        with self.assertRaisesRegex(EvolutionaryEpochError, "same-epoch"):
            self.engine.register_delta_lineage(delta, "E004")
        with self.assertRaisesRegex(EvolutionaryEpochError, "cross-epoch"):
            self.engine.register_delta_lineage(delta, "E005")

    def test_next_epoch_delta_lineage_missing_and_epoch_mismatch_denied(self):
        gate = self._gate(proposal_id="promotion:lineage")
        promotion = self._promotion(gate, promotion_id="promotion:lineage")
        delta = EvolutionDelta(
            delta_id="delta:lineage", target_component="rnd-loop", motivation="bounded knowledge",
            evidence_refs=("evidence:lineage",), expected_outcome="candidate only",
            falsification_conditions=("regression",), candidate_scope=("cyber_lion/contracts/example.py",),
            dependency_ids=(), risk_class="GREEN",
        ).sealed()
        promotion = replace(promotion, evolution_delta_digest=delta.delta_digest, promotion_digest="").sealed()
        memory = RnDMemoryRecord(
            memory_id="mem:lineage", revision=1, record_kind="PROMOTED_KNOWLEDGE",
            subject_id=promotion.promotion_id, source_digests=(promotion.promotion_digest,),
            negative_evidence_refs=(), supersedes_memory_digest=None, epistemic_status="SUPPORTED",
            committed_event_ref="evt:lineage:mem:commit", previous_memory_head="GENESIS",
        ).sealed()
        transition = EpochTransition(
            epoch_id="E004", previous_epoch_id="E003", rnd_engine_state_digest=H1,
            memory_head=H2, promotion_digest=promotion.promotion_digest,
            evolution_delta_digest=delta.delta_digest, event_projection_digest=H3,
            graph_projection_digest=H4, state="NEXT_EPOCH_CANDIDATE_READY",
        ).sealed()
        with self.assertRaisesRegex(EvolutionaryEpochError, "NEXT_EPOCH_DELTA_LINEAGE_MISSING"):
            self.engine.assert_next_epoch_ready(transition, delta, promotion, memory)

        mismatch_engine = EvolutionaryEpochEngine()
        mismatch_engine.register_delta_lineage(delta, "E003")
        with self.assertRaisesRegex(EvolutionaryEpochError, "NEXT_EPOCH_DELTA_LINEAGE_EPOCH_MISMATCH"):
            mismatch_engine.assert_next_epoch_ready(transition, delta, promotion, memory)

    def test_next_epoch_requires_verified_pdp_and_exact_binding(self):
        gate = self._gate(proposal_id="promotion:ready")
        promotion = PromotionDecision(
            promotion_id="promotion:ready", hypothesis_digest=H1, hypothesis_state="SUPPORTED",
            falsification_digest=H2, falsification_disposition="SUPPORTED", evolution_delta_digest=H3,
            policy_decision_ref="pdp:" + gate.decision_digest, unresolved_contradictions=0,
            contrary_evidence_complete=True, decision="PROMOTE_KNOWLEDGE", rationale="ready knowledge",
        ).sealed()
        delta = EvolutionDelta(
            delta_id="delta:ready", target_component="rnd-loop", motivation="bounded knowledge delta",
            evidence_refs=("evidence:ready",), expected_outcome="candidate only",
            falsification_conditions=("regression",), candidate_scope=("cyber_lion/contracts/example.py",),
            dependency_ids=(), risk_class="GREEN",
        ).sealed()
        promotion = replace(promotion, evolution_delta_digest=delta.delta_digest, promotion_digest="").sealed()
        memory = RnDMemoryRecord(
            memory_id="mem:ready", revision=1, record_kind="PROMOTED_KNOWLEDGE", subject_id="promotion:ready",
            source_digests=(promotion.promotion_digest,), negative_evidence_refs=(), supersedes_memory_digest=None,
            epistemic_status="SUPPORTED", committed_event_ref="evt:ready:mem:commit", previous_memory_head="GENESIS",
        ).sealed()
        candidate = self.engine.project_event(
            memory,
            envelope("mem:ready", memory.memory_digest, "evt:ready:mem:candidate", "MemoryCandidateCreated",
                     upstream=(promotion.promotion_digest,)),
            "proj:ready:mem:candidate",
        )
        self.engine.bind_memory_candidate(memory, candidate)
        commit = self.engine.project_event(
            memory,
            envelope("mem:ready", memory.memory_digest, "evt:ready:mem:commit", "MemoryCommitted",
                     upstream=(promotion.promotion_digest,), causation_id="evt:ready:mem:candidate",
                     policy_ids=["rnd-memory-policy"], extra_payload={"candidate_event_id": "evt:ready:mem:candidate"}),
            "proj:ready:mem:commit",
        )
        head = sha256(
            b"LION/E004-RND-MEMORY-CHAIN/1\0" + b"GENESIS" + memory.memory_digest.encode("ascii")
        ).hexdigest()
        self.engine.bind_memory_commit(memory, "evt:ready:mem:candidate", commit, head)
        transition = EpochTransition(
            epoch_id="E004", previous_epoch_id="E003", rnd_engine_state_digest=H1, memory_head=head,
            promotion_digest=promotion.promotion_digest, evolution_delta_digest=delta.delta_digest,
            event_projection_digest=H3, graph_projection_digest=H4, state="EPOCH_OPEN",
        ).sealed()
        for state in (
            "OBSERVING", "HYPOTHESIS_SPACE_ACTIVE", "TESTING", "FALSIFICATION_COMPLETE",
            "KNOWLEDGE_PROMOTION_READY", "KNOWLEDGE_PROMOTED", "MEMORY_COMMITTED",
            "DELTA_SYNTHESIZED", "NEXT_EPOCH_CANDIDATE_READY",
        ):
            transition = self.engine.transition_epoch(transition, state)
        self.engine.register_delta_lineage(delta, "E004")
        with self.assertRaisesRegex(EvolutionaryEpochError, "PROMOTION_WITHOUT_VERIFIED_PDP"):
            self.engine.assert_next_epoch_ready(transition, delta, promotion, memory)
        self.engine.verify_promotion_gate(promotion, gate)
        self.engine.assert_next_epoch_ready(transition, delta, promotion, memory)

        fabricated = replace(promotion, policy_decision_ref="pdp:" + H4, promotion_digest="").sealed()
        fabricated_transition = replace(transition, promotion_digest=fabricated.promotion_digest, transition_digest="").sealed()
        with self.assertRaisesRegex(EvolutionaryEpochError, "PROMOTION_WITHOUT_VERIFIED_PDP"):
            self.engine.assert_next_epoch_ready(fabricated_transition, delta, fabricated, memory)

    def test_next_epoch_boundary_remains_non_effectful_and_f005_denied(self):
        delta = EvolutionDelta(
            delta_id="delta:1", target_component="F005-runtime", motivation="bounded knowledge delta",
            evidence_refs=("evidence:1",), expected_outcome="improve model", falsification_conditions=("fails",),
            candidate_scope=("cyber_lion/contracts/example.py",), dependency_ids=(), risk_class="GREEN",
        ).sealed()
        gate = self._gate(proposal_id="promotion:2", request_id="request:f005")
        promotion = PromotionDecision(
            promotion_id="promotion:2", hypothesis_digest=H1, hypothesis_state="SUPPORTED",
            falsification_digest=H2, falsification_disposition="SUPPORTED", evolution_delta_digest=delta.delta_digest,
            policy_decision_ref="pdp:" + gate.decision_digest, unresolved_contradictions=0, contrary_evidence_complete=True,
            decision="PROMOTE_KNOWLEDGE", rationale="knowledge only",
        ).sealed()
        self.engine.verify_promotion_gate(promotion, gate)
        memory = RnDMemoryRecord(
            memory_id="mem:3", revision=1, record_kind="PROMOTED_KNOWLEDGE", subject_id="promotion:2",
            source_digests=(promotion.promotion_digest,), negative_evidence_refs=(), supersedes_memory_digest=None,
            epistemic_status="SUPPORTED", committed_event_ref="evt:mem3", previous_memory_head="GENESIS",
        ).sealed()
        transition = EpochTransition(
            epoch_id="E004", previous_epoch_id="E003", rnd_engine_state_digest=H1, memory_head=H2,
            promotion_digest=promotion.promotion_digest, evolution_delta_digest=delta.delta_digest,
            event_projection_digest=H3, graph_projection_digest=H4, state="NEXT_EPOCH_CANDIDATE_READY",
        ).sealed()
        with self.assertRaises(EvolutionaryEpochError):
            self.engine.assert_next_epoch_ready(transition, delta, promotion, memory)
        assert_no_effect_surface()


if __name__ == "__main__":
    unittest.main()
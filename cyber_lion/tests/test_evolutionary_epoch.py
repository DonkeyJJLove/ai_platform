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

    def test_next_epoch_boundary_remains_non_effectful_and_f005_denied(self):
        delta = EvolutionDelta(
            delta_id="delta:1", target_component="F005-runtime", motivation="bounded knowledge delta",
            evidence_refs=("evidence:1",), expected_outcome="improve model", falsification_conditions=("fails",),
            candidate_scope=("cyber_lion/contracts/example.py",), dependency_ids=(), risk_class="GREEN",
        ).sealed()
        promotion = PromotionDecision(
            promotion_id="promotion:2", hypothesis_digest=H1, hypothesis_state="SUPPORTED",
            falsification_digest=H2, falsification_disposition="SUPPORTED", evolution_delta_digest=delta.delta_digest,
            policy_decision_ref="pdp:" + H3, unresolved_contradictions=0, contrary_evidence_complete=True,
            decision="PROMOTE_KNOWLEDGE", rationale="knowledge only",
        ).sealed()
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

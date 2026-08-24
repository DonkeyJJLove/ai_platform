from hashlib import sha256
import json
import unittest

from cyber_lion.contracts.enterprise_graph import GraphEdge, GraphNode
from cyber_lion.contracts.events import Authority, EventEnvelope, Provenance
from cyber_lion.contracts.policy_gate import GateApplied
from cyber_lion.contracts.evolutionary_epoch import EpochTransition
from cyber_lion.contracts.evolutionary_rnd import (
    EvidenceObservation,
    EvolutionDelta,
    ExperimentProposal,
    ExperimentResult,
    FalsificationResult,
    Hypothesis,
    PromotionDecision,
    RnDMemoryRecord,
    SimulationPlan,
)
from cyber_lion.enterprise.evolutionary_epoch import EvolutionaryEpochEngine
from cyber_lion.enterprise.evolutionary_rnd import EvolutionaryRnDEngine

H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64


def envelope(record_id, record_digest, event_id, event_type, upstream, *, causation_id=None,
             policy_ids=(), extra_payload=None):
    payload = {"record_digest": record_digest}
    if extra_payload:
        payload.update(extra_payload)
    return EventEnvelope(
        schema_version="1.0.0",
        event_id=event_id,
        event_type=event_type,
        occurred_at="2026-08-25T00:00:00+02:00",
        correlation_id="corr:e004:r5:e2e",
        entity={"entity_id": record_id},
        source={"component": "e004-r5-self-evaluation"},
        provenance=Provenance(
            epistemic_status="DERIVED",
            upstream=list(upstream),
            transformation_chain=["E004-R5"],
        ),
        authority=Authority(requested="none", effective="none", policy_ids=list(policy_ids)),
        epistemic_state="FORMALISED",
        payload=payload,
        causation_id=causation_id,
    )


def gate_for(promotion_id):
    return GateApplied(
        gate_event_id="gate:e004:r5",
        request_id="request:e004:r5",
        proposal_id=promotion_id,
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


class E004R5EpochSelfEvaluationTests(unittest.TestCase):
    def test_complete_non_consequential_epoch_reaches_next_candidate_ready(self):
        rnd = EvolutionaryRnDEngine()
        epoch = EvolutionaryEpochEngine()

        observation = EvidenceObservation(
            observation_id="obs:e004:r5:positive",
            observation_kind="SYNTHETIC_EPISTEMIC_SCORE",
            source_ref="fixture:e004:r5",
            source_digest=H1,
            observed_at="2026-08-25T00:00:00+02:00",
            epistemic_class="OBSERVED",
            provenance_refs=("fixture:e004:r5",),
            content_digest=H2,
        ).sealed()
        counter = EvidenceObservation(
            observation_id="obs:e004:r5:counter",
            observation_kind="SYNTHETIC_COUNTEREVIDENCE",
            source_ref="fixture:e004:r5:counter",
            source_digest=H2,
            observed_at="2026-08-25T00:00:00+02:00",
            epistemic_class="OBSERVED",
            provenance_refs=("fixture:e004:r5:counter",),
            content_digest=H3,
        ).sealed()
        rnd.register_evidence(observation)
        rnd.register_evidence(counter)

        observation_event = envelope(
            observation.observation_id,
            observation.observation_digest,
            "evt:e004:r5:observation",
            "ObservationCreated",
            observation.provenance_refs,
        )
        observation_projection = epoch.project_event(
            observation, observation_event, "projection:e004:r5:observation"
        )

        hypothesis = Hypothesis(
            hypothesis_id="hyp:e004:r5",
            revision=1,
            claim="A bounded deterministic scoring adjustment improves synthetic consistency",
            evidence_refs=(observation.observation_id,),
            counter_evidence_refs=(counter.observation_id,),
            falsifiers=("synthetic-regression",),
            alternative_explanations=("no-material-change",),
            state="PROPOSED",
            provenance_refs=(observation_event.event_id,),
        ).sealed()
        rnd.register_hypothesis(hypothesis)
        admitted = rnd.transition_hypothesis(hypothesis, "ADMITTED_FOR_TEST")
        testing = rnd.transition_hypothesis(admitted, "TESTING")

        proposal = ExperimentProposal(
            experiment_id="exp:e004:r5",
            hypothesis_digest=testing.hypothesis_digest,
            evidence_refs=(observation.observation_id,),
            method="deterministic synthetic comparison",
            expected_observables=("stable-score",),
            falsification_conditions=("synthetic-regression",),
            risk_class="GREEN",
            provenance_refs=("evt:e004:r5:experiment",),
        ).sealed()
        rnd.register_experiment(proposal)

        simulation = SimulationPlan(
            simulation_id="sim:e004:r5",
            experiment_digest=proposal.experiment_digest,
            model_id="synthetic-score-model",
            model_version="1",
            scenario_digest=H1,
            parameter_distribution_digest=H2,
            seed_strategy="fixed:004",
            assumption_refs=("assumption:synthetic-only",),
            requested_metrics=("stable-score",),
            stress_conditions=("counterfactual",),
            provenance_refs=(proposal.experiment_digest,),
        ).sealed()
        rnd.register_simulation(simulation)

        simulation_event = envelope(
            simulation.simulation_id,
            simulation.simulation_digest,
            "evt:e004:r5:simulation-requested",
            "SimulationRequested",
            simulation.provenance_refs,
        )
        epoch.project_event(simulation, simulation_event, "projection:e004:r5:simulation")

        result = ExperimentResult(
            result_id="result:e004:r5",
            experiment_digest=proposal.experiment_digest,
            input_digest=H1,
            output_digest=H2,
            result_class="SIMULATED",
            observer_evidence_ref="observer:e004:r5",
            limitations=("synthetic-only",),
            observed_at="2026-08-25T00:00:00+02:00",
            provenance_refs=(simulation.simulation_digest,),
        ).sealed()
        rnd.register_result(result)

        result_event = envelope(
            result.result_id,
            result.result_digest,
            "evt:e004:r5:simulation-completed",
            "SimulationCompleted",
            result.provenance_refs,
        )
        epoch.project_event(result, result_event, "projection:e004:r5:result")

        supported = rnd.transition_hypothesis(testing, "SUPPORTED")
        falsification = FalsificationResult(
            falsification_id="falsification:e004:r5",
            hypothesis_digest=supported.hypothesis_digest,
            experiment_result_digests=(result.result_digest,),
            attempted_falsifiers=("synthetic-regression",),
            contrary_evidence_refs=(counter.observation_id,),
            anomaly_codes=(),
            disposition="SUPPORTED",
            provenance_refs=(result.result_digest, counter.observation_digest),
        ).sealed()
        rnd.register_falsification(falsification)

        delta = EvolutionDelta(
            delta_id="delta:e004:r5",
            target_component="rnd-loop",
            motivation="bounded synthetic knowledge improvement",
            evidence_refs=(observation.observation_id,),
            expected_outcome="separately governed candidate only",
            falsification_conditions=("synthetic-regression",),
            candidate_scope=("cyber_lion/contracts/synthetic_candidate.py",),
            dependency_ids=(),
            risk_class="GREEN",
        ).sealed()
        rnd.register_delta(delta)
        epoch.register_delta_lineage(delta, "E004")

        gate = gate_for("promotion:e004:r5")
        promotion = PromotionDecision(
            promotion_id="promotion:e004:r5",
            hypothesis_digest=supported.hypothesis_digest,
            hypothesis_state="SUPPORTED",
            falsification_digest=falsification.falsification_digest,
            falsification_disposition="SUPPORTED",
            evolution_delta_digest=delta.delta_digest,
            policy_decision_ref="pdp:" + gate.decision_digest,
            unresolved_contradictions=0,
            contrary_evidence_complete=True,
            decision="PROMOTE_KNOWLEDGE",
            rationale="synthetic evidence survived declared falsification",
        ).sealed()
        rnd.promote(promotion)
        epoch.verify_promotion_gate(promotion, gate)

        memory = RnDMemoryRecord(
            memory_id="memory:e004:r5",
            revision=1,
            record_kind="PROMOTED_KNOWLEDGE",
            subject_id=promotion.promotion_id,
            source_digests=(promotion.promotion_digest,),
            negative_evidence_refs=(counter.observation_id,),
            supersedes_memory_digest=None,
            epistemic_status="SUPPORTED",
            committed_event_ref="evt:e004:r5:memory-committed",
            previous_memory_head="GENESIS",
        ).sealed()
        memory_head = rnd.append_memory(memory)

        memory_upstream = tuple(memory.source_digests) + tuple(memory.negative_evidence_refs)
        memory_candidate_event = envelope(
            memory.memory_id,
            memory.memory_digest,
            "evt:e004:r5:memory-candidate",
            "MemoryCandidateCreated",
            memory_upstream,
        )
        memory_candidate_projection = epoch.project_event(
            memory, memory_candidate_event, "projection:e004:r5:memory-candidate"
        )
        epoch.bind_memory_candidate(memory, memory_candidate_projection)
        memory_commit_event = envelope(
            memory.memory_id,
            memory.memory_digest,
            "evt:e004:r5:memory-committed",
            "MemoryCommitted",
            memory_upstream,
            causation_id=memory_candidate_event.event_id,
            policy_ids=("rnd-memory-policy",),
            extra_payload={"candidate_event_id": memory_candidate_event.event_id},
        )
        memory_commit_projection = epoch.project_event(
            memory, memory_commit_event, "projection:e004:r5:memory-commit"
        )
        epoch.bind_memory_commit(
            memory,
            memory_candidate_event.event_id,
            memory_commit_projection,
            memory_head,
        )

        delta_event = envelope(
            delta.delta_id,
            delta.delta_digest,
            "evt:e004:r5:delta",
            "DeltaDetected",
            delta.evidence_refs,
        )
        delta_event_projection = epoch.project_event(
            delta, delta_event, "projection:e004:r5:delta-event"
        )
        delta_node = GraphNode(
            node_id=delta.delta_id,
            node_type="ARTIFACT",
            version="1",
            payload={"record_digest": delta.delta_digest, "event_id": delta_event.event_id},
            provenance_refs=delta.evidence_refs,
        )
        delta_edge = GraphEdge(
            edge_id="edge:e004:r5:delta",
            plane="DATA_PROVENANCE",
            edge_type="DERIVED_FROM",
            source_id=delta.delta_id,
            target_id=observation.observation_id,
            provenance_refs=delta.evidence_refs,
        )
        delta_graph_projection = epoch.project_graph(
            delta,
            delta_event_projection,
            delta_node,
            (delta_edge,),
            "projection:e004:r5:delta-graph",
        )

        transition = EpochTransition(
            epoch_id="E004",
            previous_epoch_id="E003",
            rnd_engine_state_digest=rnd.state_digest(),
            memory_head=memory_head,
            promotion_digest=promotion.promotion_digest,
            evolution_delta_digest=delta.delta_digest,
            event_projection_digest=delta_event_projection.projection_digest,
            graph_projection_digest=delta_graph_projection.projection_digest,
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
            transition = epoch.transition_epoch(transition, state)

        epoch.assert_next_epoch_ready(transition, delta, promotion, memory)

        receipt_payload = {
            "schema": "E004-R5-EPOCH-SELF-EVALUATION-RECEIPT-v1",
            "evidence_digest": observation.observation_digest,
            "hypothesis_digest": supported.hypothesis_digest,
            "experiment_digest": proposal.experiment_digest,
            "result_digest": result.result_digest,
            "falsification_digest": falsification.falsification_digest,
            "promotion_digest": promotion.promotion_digest,
            "memory_head": memory_head,
            "event_projection_digest": delta_event_projection.projection_digest,
            "graph_projection_digest": delta_graph_projection.projection_digest,
            "evolution_delta_digest": delta.delta_digest,
            "epoch_transition_digest": transition.transition_digest,
            "authority_effect": False,
            "repository_effect": False,
            "runtime_effect": False,
        }
        canonical = json.dumps(receipt_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        receipt_digest = sha256(b"LION/E004-R5-SELF-EVAL-RECEIPT/1\0" + canonical).hexdigest()
        receipt_digest_again = sha256(b"LION/E004-R5-SELF-EVAL-RECEIPT/1\0" + canonical).hexdigest()

        self.assertEqual(receipt_digest, receipt_digest_again)
        self.assertEqual(len(receipt_digest), 64)
        self.assertEqual(transition.state, "NEXT_EPOCH_CANDIDATE_READY")
        self.assertEqual(delta.authority_effect, "NONE")
        self.assertEqual(delta.execution_effect, "NONE")
        self.assertEqual(observation_projection.record_digest, observation.observation_digest)


if __name__ == "__main__":
    unittest.main()

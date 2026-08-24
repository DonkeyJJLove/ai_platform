import dataclasses
import unittest

from cyber_lion.contracts.evolutionary_rnd import (
    EvolutionDelta,
    ExperimentProposal,
    ExperimentResult,
    FalsificationResult,
    Hypothesis,
    PromotionDecision,
    RnDMemoryRecord,
    SimulationPlan,
)
from cyber_lion.enterprise.evolutionary_rnd import (
    EvolutionaryRnDEngine,
    EvolutionaryRnDError,
    assert_no_effect_surface,
)

D1 = "a" * 64
D2 = "b" * 64
D3 = "c" * 64


class EvolutionaryRnDEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = EvolutionaryRnDEngine()
        self.hyp = Hypothesis(
            hypothesis_id="hyp-1", revision=1, claim="bounded claim",
            evidence_refs=("obs:1",), counter_evidence_refs=("obs:contra",),
            falsifiers=("falsifier-a",), alternative_explanations=("alt",),
            state="PROPOSED", provenance_refs=("event:hyp",),
        ).sealed()
        self.engine.register_hypothesis(self.hyp)

    def admitted_testing(self):
        admitted = self.engine.transition_hypothesis(self.hyp, "ADMITTED_FOR_TEST")
        testing = self.engine.transition_hypothesis(admitted, "TESTING")
        return testing

    def proposal(self, hyp):
        proposal = ExperimentProposal(
            experiment_id="exp-1", hypothesis_digest=hyp.hypothesis_digest,
            evidence_refs=("obs:1",), method="deterministic",
            expected_observables=("x",), falsification_conditions=("falsifier-a",),
            risk_class="GREEN", provenance_refs=("event:exp",),
        ).sealed()
        self.engine.register_experiment(proposal)
        return proposal

    def result(self, proposal, *, klass="OBSERVED", result_id="res-1"):
        result = ExperimentResult(
            result_id=result_id, experiment_digest=proposal.experiment_digest,
            input_digest=D1, output_digest=D2, result_class=klass,
            observer_evidence_ref="observer:independent", limitations=(),
            observed_at="2026-08-25T00:00:00+02:00", provenance_refs=("event:result",),
        ).sealed()
        self.engine.register_result(result)
        return result

    def supported_chain(self):
        testing = self.admitted_testing()
        proposal = self.proposal(testing)
        result = self.result(proposal)
        supported = self.engine.transition_hypothesis(testing, "SUPPORTED")
        fals = FalsificationResult(
            falsification_id="fal-1", hypothesis_digest=supported.hypothesis_digest,
            experiment_result_digests=(result.result_digest,), attempted_falsifiers=("falsifier-a",),
            contrary_evidence_refs=("obs:contra",), anomaly_codes=(), disposition="SUPPORTED",
            provenance_refs=("event:fal",),
        ).sealed()
        self.engine.register_falsification(fals)
        delta = EvolutionDelta(
            delta_id="delta-1", target_component="rnd-loop", motivation="bounded knowledge delta",
            evidence_refs=("obs:1",), expected_outcome="candidate contract improvement",
            falsification_conditions=("regression",), candidate_scope=("cyber_lion/contracts/x.py",),
            dependency_ids=(), risk_class="AMBER",
        ).sealed()
        self.engine.register_delta(delta)
        return supported, fals, delta

    def test_exact_hypothesis_lifecycle_is_forward_only(self):
        testing = self.admitted_testing()
        final = self.engine.transition_hypothesis(testing, "FALSIFIED")
        self.assertEqual(final.state, "FALSIFIED")
        with self.assertRaisesRegex(EvolutionaryRnDError, "transition denied"):
            self.engine.transition_hypothesis(final, "SUPPORTED")

    def test_changed_payload_under_same_identity_denied(self):
        changed = dataclasses.replace(self.hyp, claim="changed", hypothesis_digest="").sealed()
        with self.assertRaises(EvolutionaryRnDError):
            self.engine.register_hypothesis(changed)

    def test_orphan_result_denied(self):
        orphan = ExperimentResult(
            result_id="orphan", experiment_digest=D3, input_digest=D1, output_digest=D2,
            result_class="OBSERVED", observer_evidence_ref="observer:x", limitations=(),
            observed_at="2026-08-25T00:00:00+02:00", provenance_refs=("event:o",),
        ).sealed()
        with self.assertRaisesRegex(EvolutionaryRnDError, "orphan result"):
            self.engine.register_result(orphan)

    def test_experiment_must_bind_exact_falsifiers_and_evidence(self):
        testing = self.admitted_testing()
        bad = ExperimentProposal(
            experiment_id="bad", hypothesis_digest=testing.hypothesis_digest,
            evidence_refs=("fabricated",), method="x", expected_observables=("x",),
            falsification_conditions=("other",), risk_class="GREEN", provenance_refs=("e",),
        ).sealed()
        with self.assertRaises(EvolutionaryRnDError):
            self.engine.register_experiment(bad)

    def test_simulation_cannot_be_relabelled_observed(self):
        testing = self.admitted_testing(); proposal = self.proposal(testing)
        plan = SimulationPlan(
            simulation_id="sim", experiment_digest=proposal.experiment_digest,
            model_id="m", model_version="1", scenario_digest=D1,
            parameter_distribution_digest=D2, seed_strategy="fixed",
            assumption_refs=("a",), requested_metrics=("x",), stress_conditions=(),
            provenance_refs=("event:sim",),
        ).sealed()
        self.engine.register_simulation(plan)
        with self.assertRaisesRegex(EvolutionaryRnDError, "cannot be relabeled"):
            self.result(proposal, klass="OBSERVED")
        simulated = self.result(proposal, klass="SIMULATED", result_id="sim-res")
        self.assertEqual(simulated.result_class, "SIMULATED")

    def test_falsification_requires_exact_contrary_evidence_and_attempts(self):
        testing = self.admitted_testing(); proposal = self.proposal(testing); result = self.result(proposal)
        supported = self.engine.transition_hypothesis(testing, "SUPPORTED")
        bad = FalsificationResult(
            falsification_id="bad", hypothesis_digest=supported.hypothesis_digest,
            experiment_result_digests=(result.result_digest,), attempted_falsifiers=("falsifier-a",),
            contrary_evidence_refs=(), anomaly_codes=(), disposition="SUPPORTED", provenance_refs=("e",),
        ).sealed()
        with self.assertRaisesRegex(EvolutionaryRnDError, "contrary evidence"):
            self.engine.register_falsification(bad)

    def test_inconclusive_falsified_unknown_cannot_promote(self):
        for state, disposition in (("INCONCLUSIVE", "INCONCLUSIVE"), ("FALSIFIED", "FALSIFIED")):
            with self.subTest(state=state):
                eng = EvolutionaryRnDEngine()
                hyp = dataclasses.replace(self.hyp, hypothesis_id=f"h-{state}", state="PROPOSED", hypothesis_digest="").sealed()
                eng.register_hypothesis(hyp)
                admitted = eng.transition_hypothesis(hyp, "ADMITTED_FOR_TEST")
                testing = eng.transition_hypothesis(admitted, "TESTING")
                proposal = ExperimentProposal(
                    experiment_id=f"e-{state}", hypothesis_digest=testing.hypothesis_digest,
                    evidence_refs=("obs:1",), method="x", expected_observables=("x",),
                    falsification_conditions=("falsifier-a",), risk_class="GREEN", provenance_refs=("e",),
                ).sealed(); eng.register_experiment(proposal)
                result = ExperimentResult(
                    result_id=f"r-{state}", experiment_digest=proposal.experiment_digest,
                    input_digest=D1, output_digest=D2, result_class="OBSERVED",
                    observer_evidence_ref="o", limitations=(), observed_at="2026-08-25T00:00:00+02:00",
                    provenance_refs=("e",),
                ).sealed(); eng.register_result(result)
                terminal = eng.transition_hypothesis(testing, state)
                fals = FalsificationResult(
                    falsification_id=f"f-{state}", hypothesis_digest=terminal.hypothesis_digest,
                    experiment_result_digests=(result.result_digest,), attempted_falsifiers=("falsifier-a",),
                    contrary_evidence_refs=("obs:contra",), anomaly_codes=(), disposition=disposition,
                    provenance_refs=("e",),
                ).sealed(); eng.register_falsification(fals)
                delta = EvolutionDelta(
                    delta_id=f"d-{state}", target_component="x", motivation="safe", evidence_refs=("e",),
                    expected_outcome="safe", falsification_conditions=("f",), candidate_scope=("x.py",),
                    dependency_ids=(), risk_class="GREEN",
                ).sealed(); eng.register_delta(delta)
                with self.assertRaises(Exception):
                    PromotionDecision(
                        promotion_id=f"p-{state}", hypothesis_digest=terminal.hypothesis_digest,
                        hypothesis_state=state, falsification_digest=fals.falsification_digest,
                        falsification_disposition=disposition, evolution_delta_digest=delta.delta_digest,
                        policy_decision_ref="pdp:g", unresolved_contradictions=0,
                        contrary_evidence_complete=True, decision="PROMOTE_KNOWLEDGE", rationale="no",
                    ).validate()

    def test_positive_promotion_is_replay_denied_and_has_no_effect_surface(self):
        supported, fals, delta = self.supported_chain()
        promotion = PromotionDecision(
            promotion_id="prom-1", hypothesis_digest=supported.hypothesis_digest,
            hypothesis_state="SUPPORTED", falsification_digest=fals.falsification_digest,
            falsification_disposition="SUPPORTED", evolution_delta_digest=delta.delta_digest,
            policy_decision_ref="pdp:gate-1", unresolved_contradictions=0,
            contrary_evidence_complete=True, decision="PROMOTE_KNOWLEDGE", rationale="bounded",
        ).sealed()
        self.engine.promote(promotion)
        with self.assertRaisesRegex(EvolutionaryRnDError, "replay"):
            self.engine.promote(promotion)
        assert_no_effect_surface()
        self.assertNotIn("execute", {x.lower() for x in dir(self.engine)})

    def test_append_only_memory_detects_rewrite_and_broken_head(self):
        record1 = RnDMemoryRecord(
            memory_id="m1", revision=1, record_kind="NEGATIVE_RESULT", subject_id="h1",
            source_digests=(D1,), negative_evidence_refs=("neg:1",), supersedes_memory_digest=None,
            epistemic_status="FALSIFIED", committed_event_ref="event:m1", previous_memory_head="GENESIS",
        ).sealed()
        head1 = self.engine.append_memory(record1)
        record2 = RnDMemoryRecord(
            memory_id="m2", revision=2, record_kind="SUPPORTED_RESULT", subject_id="h2",
            source_digests=(D2,), negative_evidence_refs=(), supersedes_memory_digest=None,
            epistemic_status="SUPPORTED", committed_event_ref="event:m2", previous_memory_head=head1,
        ).sealed()
        head2 = self.engine.append_memory(record2)
        self.assertEqual(head2, self.engine.verify_memory(self.engine.memory_records))
        rewritten = dataclasses.replace(record1, source_digests=(D3,), memory_digest="").sealed()
        with self.assertRaisesRegex(EvolutionaryRnDError, "rewrite/break"):
            self.engine.verify_memory((rewritten, record2))
        self.assertEqual(len(self.engine.memory_records), 2)

    def test_state_digest_is_deterministic(self):
        self.assertEqual(self.engine.state_digest(), self.engine.state_digest())


if __name__ == "__main__":
    unittest.main()

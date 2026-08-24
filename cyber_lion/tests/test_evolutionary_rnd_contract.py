import unittest

from cyber_lion.contracts.evolutionary_rnd import (
    EvidenceObservation,
    EvolutionDelta,
    EvolutionaryRnDContractError,
    ExperimentProposal,
    ExperimentResult,
    FalsificationResult,
    Hypothesis,
    PromotionDecision,
    RnDMemoryRecord,
    SimulationPlan,
    domain_digest,
)

D1 = "a" * 64
D2 = "b" * 64
D3 = "c" * 64


class EvolutionaryRnDContractTests(unittest.TestCase):
    def evidence(self):
        return EvidenceObservation(
            observation_id="obs-1", observation_kind="test", source_ref="artifact:1",
            source_digest=D1, observed_at="2026-08-25T00:00:00+02:00",
            epistemic_class="OBSERVED", provenance_refs=("source:1",), content_digest=D2,
        ).sealed()

    def hypothesis(self, state="PROPOSED"):
        return Hypothesis(
            hypothesis_id="hyp-1", revision=1, claim="candidate claim",
            evidence_refs=("obs:1",), counter_evidence_refs=("obs:contra",),
            falsifiers=("fails-test-x",), alternative_explanations=("alt-1",), state=state,
            provenance_refs=("event:hyp-1",),
        ).sealed()

    def experiment(self, hyp_digest):
        return ExperimentProposal(
            experiment_id="exp-1", hypothesis_digest=hyp_digest,
            evidence_refs=("obs:1",), method="deterministic-test",
            expected_observables=("metric-x",), falsification_conditions=("fails-test-x",),
            risk_class="GREEN", provenance_refs=("event:exp-1",),
        ).sealed()

    def result(self, exp_digest, result_class="OBSERVED"):
        return ExperimentResult(
            result_id="res-1", experiment_digest=exp_digest, input_digest=D1,
            output_digest=D2, result_class=result_class, observer_evidence_ref="observer:independent",
            limitations=("bounded-fixture",), observed_at="2026-08-25T00:01:00+02:00",
            provenance_refs=("event:res-1",),
        ).sealed()

    def test_all_contracts_are_sealable_and_domain_separated(self):
        ev = self.evidence(); hyp = self.hypothesis(); exp = self.experiment(hyp.hypothesis_digest)
        sim = SimulationPlan(
            simulation_id="sim-1", experiment_digest=exp.experiment_digest,
            model_id="m", model_version="1", scenario_digest=D1, parameter_distribution_digest=D2,
            seed_strategy="fixed:1", assumption_refs=("assumption:1",), requested_metrics=("metric-x",),
            stress_conditions=("edge",), provenance_refs=("event:sim-1",),
        ).sealed()
        res = self.result(exp.experiment_digest)
        fals = FalsificationResult(
            falsification_id="fal-1", hypothesis_digest=hyp.hypothesis_digest,
            experiment_result_digests=(res.result_digest,), attempted_falsifiers=("fails-test-x",),
            contrary_evidence_refs=("obs:contra",), anomaly_codes=(), disposition="SUPPORTED",
            provenance_refs=("event:fal-1",),
        ).sealed()
        delta = EvolutionDelta(
            delta_id="delta-1", target_component="rnd", motivation="validated bounded candidate",
            evidence_refs=("obs:1",), expected_outcome="machine-readable R&D state",
            falsification_conditions=("regression fails",), candidate_scope=("cyber_lion/contracts/x.py",),
            dependency_ids=(), risk_class="AMBER",
        ).sealed()
        promotion = PromotionDecision(
            promotion_id="prom-1", hypothesis_digest=hyp.hypothesis_digest,
            hypothesis_state="SUPPORTED", falsification_digest=fals.falsification_digest,
            falsification_disposition="SUPPORTED", evolution_delta_digest=delta.delta_digest,
            policy_decision_ref="pdp:gate-1", unresolved_contradictions=0,
            contrary_evidence_complete=True, decision="PROMOTE_KNOWLEDGE", rationale="evidence complete",
        ).sealed()
        mem = RnDMemoryRecord(
            memory_id="mem-1", revision=1, record_kind="PROMOTED_KNOWLEDGE", subject_id="hyp-1",
            source_digests=(promotion.promotion_digest,), negative_evidence_refs=("obs:contra",),
            supersedes_memory_digest=None, epistemic_status="SUPPORTED",
            committed_event_ref="event:memory-1", previous_memory_head="GENESIS",
        ).sealed()
        values = {
            ev.observation_digest, hyp.hypothesis_digest, exp.experiment_digest, sim.simulation_digest,
            res.result_digest, fals.falsification_digest, delta.delta_digest,
            promotion.promotion_digest, mem.memory_digest,
        }
        self.assertEqual(len(values), 9)

    def test_cross_type_digest_substitution_fails(self):
        hyp = self.hypothesis()
        exp = self.experiment(hyp.hypothesis_digest)
        tampered = ExperimentProposal(**{**exp.__dict__, "experiment_digest": hyp.hypothesis_digest})
        with self.assertRaisesRegex(EvolutionaryRnDContractError, "experiment_digest mismatch"):
            tampered.validate()

    def test_evolution_delta_denies_authority_and_effect_material(self):
        with self.assertRaisesRegex(EvolutionaryRnDContractError, "effect authority"):
            EvolutionDelta(
                delta_id="d", target_component="x", motivation="safe", evidence_refs=("e",),
                expected_outcome="safe", falsification_conditions=("f",), candidate_scope=("x.py",),
                dependency_ids=(), risk_class="GREEN", authority_effect="WRITE",
            ).validate()
        with self.assertRaisesRegex(EvolutionaryRnDContractError, "prohibited"):
            EvolutionDelta(
                delta_id="d2", target_component="x", motivation="token=secret",
                evidence_refs=("e",), expected_outcome="safe", falsification_conditions=("f",),
                candidate_scope=("x.py",), dependency_ids=(), risk_class="GREEN",
            ).validate()

    def test_promotion_is_knowledge_only_and_requires_positive_falsification(self):
        with self.assertRaisesRegex(EvolutionaryRnDContractError, "supported hypothesis"):
            PromotionDecision(
                promotion_id="p", hypothesis_digest=D1, hypothesis_state="INCONCLUSIVE",
                falsification_digest=D2, falsification_disposition="SUPPORTED",
                evolution_delta_digest=D3, policy_decision_ref="pdp:g", unresolved_contradictions=0,
                contrary_evidence_complete=True, decision="PROMOTE_KNOWLEDGE", rationale="no",
            ).validate()
        with self.assertRaisesRegex(EvolutionaryRnDContractError, "supported falsification"):
            PromotionDecision(
                promotion_id="p2", hypothesis_digest=D1, hypothesis_state="SUPPORTED",
                falsification_digest=D2, falsification_disposition="FALSIFIED",
                evolution_delta_digest=D3, policy_decision_ref="pdp:g", unresolved_contradictions=0,
                contrary_evidence_complete=True, decision="PROMOTE_KNOWLEDGE", rationale="no",
            ).validate()

    def test_memory_first_record_requires_genesis(self):
        with self.assertRaisesRegex(EvolutionaryRnDContractError, "GENESIS"):
            RnDMemoryRecord(
                memory_id="m", revision=1, record_kind="NEGATIVE_RESULT", subject_id="h",
                source_digests=(D1,), negative_evidence_refs=("e",), supersedes_memory_digest=None,
                epistemic_status="FALSIFIED", committed_event_ref="event:m", previous_memory_head=D2,
            ).validate()

    def test_simulated_and_observed_are_distinct_classes(self):
        hyp = self.hypothesis(); exp = self.experiment(hyp.hypothesis_digest)
        self.assertNotEqual(
            self.result(exp.experiment_digest, "SIMULATED").result_digest,
            self.result(exp.experiment_digest, "OBSERVED").result_digest,
        )

    def test_digest_domain_rejects_unknown_kind(self):
        with self.assertRaises(EvolutionaryRnDContractError):
            domain_digest("runtime-authority", {"x": 1})


if __name__ == "__main__":
    unittest.main()

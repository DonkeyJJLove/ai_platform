from __future__ import annotations

import json
from pathlib import Path
import unittest

from cyber_lion.architecture_projection.evolution_fitness import (
    DEFAULT_BENEFIT_WEIGHTS,
    DEFAULT_COST_WEIGHTS,
    EvolutionFitnessCandidate,
    EvolutionFitnessError,
    EvolutionFitnessOptimizer,
    EvolutionFitnessVector,
    EvolutionGateState,
    EvolutionPressure,
)


ROOT = Path(__file__).resolve().parents[2]
STANDARD = ROOT / "LION/standards/LION_EVOLUTION_FITNESS_STANDARD.json"


def gates(**overrides):
    values = {
        "source_current": True,
        "semantic_owner_bound": True,
        "dependency_closure": True,
        "authority_nonexpanding": True,
        "effect_state_reconciled": True,
        "collision_free": True,
        "bounded_scope": True,
        "evidence_bound": True,
        "owner_resolved": True,
    }
    values.update(overrides)
    return EvolutionGateState(**values).validate()


def vector(**overrides):
    values = {
        "capability_gain": 500,
        "federation_leverage": 400,
        "functional_value": 500,
        "generativity_gain": 400,
        "integration_closure": 500,
        "knowledge_feedback": 300,
        "recovery_strength": 400,
        "reuse_leverage": 400,
        "verification_strength": 500,
        "authority_risk": 100,
        "blast_radius": 100,
        "change_surface": 200,
        "currentness_debt": 100,
        "implementation_cost": 300,
        "operational_cost": 200,
    }
    values.update(overrides)
    return EvolutionFitnessVector(**values).validate()


def candidate(candidate_id: str, *, v=None, g=None, families=1):
    return EvolutionFitnessCandidate(
        candidate_id=candidate_id,
        vector=v or vector(),
        gates=g or gates(),
        evidence_refs=(f"evidence:{candidate_id}",),
        repository_scope=("DonkeyJJLove/ai_platform",),
        task_family_count=families,
    ).validate()


class EvolutionFitnessTests(unittest.TestCase):
    def setUp(self):
        self.optimizer = EvolutionFitnessOptimizer()

    def test_generative_integration_candidate_beats_one_off_candidate(self):
        one_off = candidate(
            "a-one-off",
            v=vector(
                capability_gain=600,
                functional_value=700,
                generativity_gain=100,
                integration_closure=300,
                federation_leverage=100,
                knowledge_feedback=100,
            ),
        )
        generative = candidate(
            "b-generative-foundry",
            v=vector(
                capability_gain=750,
                functional_value=700,
                generativity_gain=900,
                integration_closure=850,
                federation_leverage=700,
                knowledge_feedback=700,
                implementation_cost=450,
                change_surface=350,
            ),
            families=3,
        )
        result = self.optimizer.select((one_off, generative))
        self.assertEqual(result.selected_candidate_id, "b-generative-foundry")
        self.assertEqual(result.critical_path_wip_limit, 1)
        self.assertEqual(result.authority_effect, "NONE")
        self.assertEqual(result.execution_effect, "NONE")

    def test_hard_gate_blocks_high_scoring_candidate(self):
        blocked = candidate(
            "a-blocked-supercandidate",
            v=vector(
                capability_gain=1000,
                functional_value=1000,
                generativity_gain=1000,
                integration_closure=1000,
                federation_leverage=1000,
                implementation_cost=0,
                authority_risk=0,
            ),
            g=gates(effect_state_reconciled=False),
        )
        bounded = candidate("b-bounded")
        result = self.optimizer.select((blocked, bounded))
        self.assertEqual(result.selected_candidate_id, "b-bounded")
        assessed = {item.candidate_id: item for item in result.assessments}
        self.assertFalse(assessed["a-blocked-supercandidate"].eligible)
        self.assertIn("UNRECONCILED_EFFECT_DENIED", assessed["a-blocked-supercandidate"].blockers)

    def test_dynamic_pressure_can_reprioritize_currentness_debt(self):
        high_value_stale = candidate(
            "a-high-value-currentness-debt",
            v=vector(
                capability_gain=850,
                generativity_gain=750,
                functional_value=800,
                currentness_debt=850,
            ),
        )
        clean_foundation = candidate(
            "b-clean-foundation",
            v=vector(
                capability_gain=650,
                generativity_gain=600,
                functional_value=650,
                currentness_debt=50,
            ),
        )
        baseline = self.optimizer.select((high_value_stale, clean_foundation))
        pressured = self.optimizer.select(
            (high_value_stale, clean_foundation),
            pressures=(
                EvolutionPressure(
                    "currentness_debt",
                    1000,
                    "evidence:currentness-bottleneck",
                ).validate(),
            ),
        )
        self.assertIn(baseline.selected_candidate_id, {"a-high-value-currentness-debt", "b-clean-foundation"})
        self.assertEqual(pressured.selected_candidate_id, "b-clean-foundation")

    def test_pareto_frontier_excludes_strictly_dominated_candidate(self):
        dominated = candidate(
            "a-dominated",
            v=vector(
                capability_gain=300,
                generativity_gain=200,
                integration_closure=300,
                authority_risk=200,
                blast_radius=200,
                implementation_cost=500,
            ),
        )
        dominant = candidate(
            "b-dominant",
            v=vector(
                capability_gain=600,
                generativity_gain=500,
                integration_closure=600,
                authority_risk=100,
                blast_radius=100,
                implementation_cost=300,
            ),
        )
        result = self.optimizer.select((dominated, dominant))
        self.assertEqual(result.pareto_frontier, ("b-dominant",))

    def test_same_inputs_are_digest_deterministic(self):
        c = candidate("candidate-deterministic")
        left = self.optimizer.select((c,))
        right = self.optimizer.select((c,))
        self.assertEqual(left.selection_digest, right.selection_digest)
        self.assertEqual(left.assessments[0].assessment_digest, right.assessments[0].assessment_digest)

    def test_candidate_order_and_pressure_order_fail_closed(self):
        a = candidate("a")
        b = candidate("b")
        with self.assertRaisesRegex(EvolutionFitnessError, "sorted unique"):
            self.optimizer.select((b, a))
        with self.assertRaisesRegex(EvolutionFitnessError, "sorted unique"):
            self.optimizer.select(
                (a,),
                pressures=(
                    EvolutionPressure("reuse_leverage", 10, "e:r").validate(),
                    EvolutionPressure("capability_gain", 10, "e:c").validate(),
                ),
            )

    def test_standard_json_matches_code_weights_and_non_effectful_contract(self):
        raw = json.loads(STANDARD.read_text(encoding="utf-8"))
        self.assertEqual(raw["schema"], "lion.evolution-fitness-standard/v1")
        self.assertEqual(
            tuple((row["dimension"], row["weight"]) for row in raw["benefit_dimensions"]),
            DEFAULT_BENEFIT_WEIGHTS,
        )
        self.assertEqual(
            tuple((row["dimension"], row["weight"]) for row in raw["cost_dimensions"]),
            DEFAULT_COST_WEIGHTS,
        )
        self.assertEqual(raw["selection"]["critical_path_wip_limit"], 1)
        self.assertEqual(raw["authority_effect"], "NONE")
        self.assertEqual(raw["execution_effect"], "NONE")
        EvolutionFitnessOptimizer.assert_no_effect_surface()

    def test_evolution_eval_cases_cover_fitness_failure_modes(self):
        cases = json.loads(
            (ROOT / "LION/evals/evolution/evolution_cases.yaml").read_text(encoding="utf-8")
        )["cases"]
        ids = {item["id"] for item in cases}
        self.assertTrue(
            {
                "EVOLUTION_FITNESS_HARD_GATE_BEATS_SCORE",
                "EVOLUTION_FITNESS_PRESSURE_REQUIRES_EVIDENCE",
                "EVOLUTION_FITNESS_GENERATIVITY_IS_NOT_AUTHORITY",
            }
            <= ids
        )


if __name__ == "__main__":
    unittest.main()

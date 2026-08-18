from __future__ import annotations

import unittest
from datetime import datetime, timezone

from cyber_lion.startup_agent import (
    AIDrivenStartupAgent,
    ExperimentOutcome,
    MarketObservation,
    ProductHypothesis,
    VentureVector,
)


NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)


def hypothesis() -> ProductHypothesis:
    return ProductHypothesis(
        "h1",
        "AI-native software team",
        "agentic workflow validation is slow and risky",
        "path-aware AI execution control plane",
        "B2B",
        VentureVector(0.45, 0.25, 0.62, 0.55, 0.32, 0.68, 0.72, 0.45, 0.72),
    )


class OrchestratorTests(unittest.TestCase):
    def test_plan_returns_state_experiment_build_and_authority(self):
        agent = AIDrivenStartupAgent("startup")
        agent.evidence.add(MarketObservation(
            "o1", "h1", "customer-1", "customer", NOW, NOW,
            "pain", "pain", "supports", 0.9, 0.9,
            "manual agent review consumes engineering time",
        ))
        plan = agent.plan([hypothesis()])
        self.assertEqual(plan.hypothesis.hypothesis_id, "h1")
        self.assertTrue(plan.scaffold)
        self.assertTrue(plan.build_spec.acceptance_tests)
        self.assertIn(plan.authority.decision, {"ALLOW", "REQUIRE_APPROVAL", "ALLOW_WITH_GATE"})

    def test_failed_market_experiment_reduces_relevant_dimension(self):
        agent = AIDrivenStartupAgent("startup")
        plan = agent.plan([hypothesis()])
        before = plan.state.vector.market_pull
        outcome = ExperimentOutcome(plan.experiment.experiment_id, False, 1.0, 1.0, 10.0, 0.1)
        corrected = agent.apply_outcome(plan.state, plan.experiment, outcome)
        if plan.experiment.experiment_type in {"customer_interviews", "problem_smoke_test", "landing_page", "pricing_test", "paid_pilot", "retention_test"}:
            self.assertLess(corrected.vector.market_pull, before)

    def test_successful_experiment_does_not_promote_every_dimension(self):
        agent = AIDrivenStartupAgent("startup")
        plan = agent.plan([hypothesis()])
        before_security = plan.state.vector.security_readiness
        outcome = ExperimentOutcome(plan.experiment.experiment_id, True, 1.0, 1.0, 8.0, 0.1)
        corrected = agent.apply_outcome(plan.state, plan.experiment, outcome)
        self.assertEqual(corrected.vector.security_readiness, before_security)

    def test_learning_velocity_rises_from_high_quality_negative_result(self):
        agent = AIDrivenStartupAgent("startup")
        plan = agent.plan([hypothesis()])
        before = plan.state.vector.learning_velocity
        outcome = ExperimentOutcome(plan.experiment.experiment_id, False, 1.0, 0.9, 8.0, 0.1)
        corrected = agent.apply_outcome(plan.state, plan.experiment, outcome)
        self.assertGreaterEqual(corrected.vector.learning_velocity, before)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from cyber_lion.startup_agent import (
    MarketSignal,
    ProductHypothesis,
    StartupAuthorityGate,
    StartupEvolutionAgent,
    VentureVector,
)
from cyber_lion.startup_agent.models import StartupModelError


NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)


def baseline(**overrides):
    values = dict(
        market_pull=0.4,
        evidence_strength=0.2,
        technical_feasibility=0.7,
        differentiation=0.5,
        distribution_access=0.3,
        delivery_velocity=0.7,
        security_readiness=0.8,
        unit_economics=0.5,
        learning_velocity=0.5,
    )
    values.update(overrides)
    return VentureVector(**values)


def hypothesis(hid="h1", **vector_overrides):
    return ProductHypothesis(
        hypothesis_id=hid,
        customer="AI-native team",
        problem="Slow validation of agentic software",
        solution="Evolution control loop",
        revenue_model="B2B",
        baseline=baseline(**vector_overrides),
    )


class StartupAgentTests(unittest.TestCase):
    def test_vector_rejects_out_of_range(self):
        with self.assertRaises(StartupModelError):
            baseline(market_pull=1.2).validate()

    def test_stale_signal_is_not_used(self):
        agent = StartupEvolutionAgent("s", max_signal_age_days=30)
        old = MarketSignal("s1", "old research", NOW - timedelta(days=40), "demand", 1.0, 1.0)
        self.assertEqual(agent.filter_fresh_signals([old], now=NOW), [])

    def test_fresh_market_evidence_moves_market_pull(self):
        agent = StartupEvolutionAgent("s")
        sig = MarketSignal("s1", "interview", NOW - timedelta(days=1), "demand", 1.0, 1.0)
        result = agent.evaluate(hypothesis(), [sig], now=NOW)
        self.assertGreater(result.market_pull, 0.4)

    def test_no_fresh_evidence_becomes_blocker(self):
        agent = StartupEvolutionAgent("s", max_signal_age_days=5)
        old = MarketSignal("s1", "old", NOW - timedelta(days=10), "demand", 1.0, 1.0)
        state = agent.next_state(None, hypothesis(), [old], now=NOW)
        self.assertIn("NO_FRESH_MARKET_EVIDENCE", state.blockers)

    def test_rank_prefers_better_evidence_weighted_hypothesis(self):
        agent = StartupEvolutionAgent("s")
        h1 = hypothesis("h1", market_pull=0.3)
        h2 = hypothesis("h2", market_pull=0.3)
        sig1 = MarketSignal("s1", "interview", NOW, "demand", 0.2, 0.9)
        sig2 = MarketSignal("s2", "paid inquiry", NOW, "demand", 0.95, 0.95)
        ranked = agent.rank_hypotheses([h1, h2], {"h1": [sig1], "h2": [sig2]}, now=NOW)
        self.assertEqual(ranked[0][0].hypothesis_id, "h2")

    def test_explore_stage_chooses_customer_evidence(self):
        agent = StartupEvolutionAgent("s")
        h = hypothesis()
        vector = baseline(market_pull=0.2, evidence_strength=0.1)
        exp = agent.choose_experiment(h, vector)
        self.assertEqual(exp.experiment_type, "customer_interviews")
        self.assertEqual(exp.authority_class, "analysis")

    def test_external_experiment_requires_gate(self):
        agent = StartupEvolutionAgent("s")
        h = hypothesis(differentiation=0.1, market_pull=0.7, evidence_strength=0.5)
        exp = agent.choose_experiment(h, h.baseline)
        decision = StartupAuthorityGate().decide(exp)
        self.assertEqual(decision.decision, "REQUIRE_APPROVAL")

    def test_gate_allows_external_experiment_only_with_event(self):
        agent = StartupEvolutionAgent("s")
        h = hypothesis(differentiation=0.1, market_pull=0.7, evidence_strength=0.5)
        exp = agent.choose_experiment(h, h.baseline)
        decision = StartupAuthorityGate().decide(exp, gate_event_id="gate-123")
        self.assertEqual(decision.decision, "ALLOW_WITH_GATE")
        self.assertEqual(decision.gate_event_id, "gate-123")

    def test_cycle_preserves_delta(self):
        agent = StartupEvolutionAgent("s")
        h = hypothesis()
        s1 = MarketSignal("s1", "interview", NOW, "demand", 0.6, 0.8)
        state1 = agent.next_state(None, h, [s1], now=NOW)
        s2 = MarketSignal("s2", "interview2", NOW, "demand", 1.0, 1.0)
        state2 = agent.next_state(state1, h, [s1, s2], now=NOW)
        self.assertEqual(state2.cycle, 1)
        self.assertNotEqual(state2.delta()["market_pull"], 0.0)


if __name__ == "__main__":
    unittest.main()

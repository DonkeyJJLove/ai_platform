from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timezone

from cyber_lion.startup_agent import (
    AIDrivenStartupAgent,
    MarketObservation,
    ProductHypothesis,
    ProviderContext,
    ProviderCoordinator,
    StaticHypothesisProvider,
    StaticMarketProvider,
    VentureVector,
)
from cyber_lion.startup_agent.models import StartupModelError


NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
BASE = VentureVector(0.45, 0.25, 0.7, 0.2, 0.35, 0.7, 0.8, 0.5, 0.7)
H = ProductHypothesis(
    "h1", "AI-native team", "slow agent validation", "bounded runtime control", "B2B", BASE
)
OBS = MarketObservation(
    "o1", "h1", "customer-1", "customer", NOW, NOW,
    "pain", "pain", "supports", 0.9, 0.9,
    "team spends engineering time manually reviewing agent actions",
)


class ProviderTests(unittest.TestCase):
    def test_static_providers_produce_end_to_end_plan_and_receipts(self):
        agent = AIDrivenStartupAgent("startup")
        context = ProviderContext("startup", "find current market product", created_at=NOW)
        result = agent.plan_from_providers(
            context,
            [StaticMarketProvider([OBS])],
            [StaticHypothesisProvider([H])],
        )
        self.assertEqual(result.plan.hypothesis.hypothesis_id, "h1")
        self.assertEqual(result.market_receipts[0].provider_kind, "market_source")
        self.assertEqual(result.hypothesis_receipts[0].provider_kind, "hypothesis")
        self.assertEqual(result.market_receipts[0].output_ids, ("o1",))

    def test_provider_receipts_are_timezone_aware(self):
        coordinator = ProviderCoordinator()
        context = ProviderContext("startup", "objective", created_at=NOW)
        _, receipts = coordinator.collect_market(context, [StaticMarketProvider([OBS])])
        self.assertIsNotNone(receipts[0].generated_at.tzinfo)

    def test_conflicting_hypothesis_content_under_same_id_is_rejected(self):
        coordinator = ProviderCoordinator()
        other = replace(H, solution="different solution")
        with self.assertRaises(StartupModelError):
            coordinator.deduplicate_hypotheses([H, other])

    def test_provider_output_does_not_grant_external_authority(self):
        # Low differentiation and enough evidence drives a smoke-test/external-write path.
        h = replace(H, baseline=VentureVector(0.75, 0.60, 0.8, 0.1, 0.7, 0.8, 0.8, 0.7, 0.8))
        agent = AIDrivenStartupAgent("startup")
        context = ProviderContext("startup", "objective", created_at=NOW)
        result = agent.plan_from_providers(
            context,
            [StaticMarketProvider([OBS])],
            [StaticHypothesisProvider([h])],
        )
        if result.plan.experiment.authority_class in {"external_write", "deploy", "financial"}:
            self.assertEqual(result.plan.authority.decision, "REQUIRE_APPROVAL")
            self.assertIsNone(result.plan.authority.gate_event_id)

    def test_authority_can_only_enter_through_explicit_caller_gate(self):
        h = replace(H, baseline=VentureVector(0.75, 0.60, 0.8, 0.1, 0.7, 0.8, 0.8, 0.7, 0.8))
        context = ProviderContext("startup", "objective", created_at=NOW)
        agent = AIDrivenStartupAgent("startup")
        result = agent.plan_from_providers(
            context,
            [StaticMarketProvider([OBS])],
            [StaticHypothesisProvider([h])],
            gate_event_id="gate-explicit-1",
        )
        if result.plan.experiment.authority_class in {"external_write", "deploy", "financial"}:
            self.assertEqual(result.plan.authority.decision, "ALLOW_WITH_GATE")
            self.assertEqual(result.plan.authority.gate_event_id, "gate-explicit-1")

    def test_invalid_market_provider_observation_is_rejected(self):
        invalid = replace(OBS, observed_at=OBS.observed_at.replace(tzinfo=None))
        agent = AIDrivenStartupAgent("startup")
        context = ProviderContext("startup", "objective", created_at=NOW)
        with self.assertRaises(StartupModelError):
            agent.plan_from_providers(
                context,
                [StaticMarketProvider([invalid])],
                [StaticHypothesisProvider([H])],
            )


if __name__ == "__main__":
    unittest.main()

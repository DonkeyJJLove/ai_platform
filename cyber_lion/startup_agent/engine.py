"""Deterministic evolution engine for an AI-driven startup agent.

The engine ranks hypotheses and experiments from explicit market evidence. It does not
perform external side effects. External writes, deployment and financial actions require
an applied gate in a higher execution layer.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .models import (
    DIMENSIONS,
    EvolutionState,
    Experiment,
    MarketSignal,
    ProductHypothesis,
    StartupModelError,
    VentureVector,
)


SIGNAL_TO_DIMENSION = {
    "demand": "market_pull",
    "pain": "market_pull",
    "competition": "differentiation",
    "pricing": "unit_economics",
    "distribution": "distribution_access",
    "technical": "technical_feasibility",
    "security": "security_readiness",
    "retention": "evidence_strength",
    "conversion": "evidence_strength",
    "cost": "unit_economics",
}

DEFAULT_WEIGHTS = {
    "market_pull": 1.35,
    "evidence_strength": 1.40,
    "technical_feasibility": 0.90,
    "differentiation": 0.90,
    "distribution_access": 1.05,
    "delivery_velocity": 1.10,
    "security_readiness": 0.75,
    "unit_economics": 1.00,
    "learning_velocity": 1.25,
}


class StartupEvolutionAgent:
    """A bounded reasoning/control loop for rapid product evolution."""

    def __init__(
        self,
        startup_id: str,
        *,
        max_signal_age_days: float = 90.0,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:
        if not startup_id:
            raise StartupModelError("startup_id is required")
        if max_signal_age_days <= 0:
            raise StartupModelError("max_signal_age_days must be positive")
        self.startup_id = startup_id
        self.max_signal_age_days = float(max_signal_age_days)
        self.weights = dict(weights or DEFAULT_WEIGHTS)
        unknown = set(self.weights) - set(DIMENSIONS)
        if unknown:
            raise StartupModelError(f"unknown weights: {sorted(unknown)}")

    def filter_fresh_signals(
        self,
        signals: Iterable[MarketSignal],
        *,
        now: Optional[datetime] = None,
    ) -> List[MarketSignal]:
        result = []
        for signal in signals:
            signal.validate()
            if signal.age_days(now) <= self.max_signal_age_days:
                result.append(signal)
        return result

    def evidence_profile(
        self,
        signals: Sequence[MarketSignal],
        *,
        now: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """Aggregate fresh evidence by venture dimension.

        Aggregation is deliberately conservative: dimensions not supported by external
        evidence remain absent rather than being invented from the model's intuition.
        """
        fresh = self.filter_fresh_signals(signals, now=now)
        buckets: Dict[str, List[float]] = {}
        for signal in fresh:
            dimension = SIGNAL_TO_DIMENSION[signal.kind]
            buckets.setdefault(dimension, []).append(signal.evidence_weight(now))
        return {
            dimension: min(1.0, sum(values) / max(1, len(values)))
            for dimension, values in buckets.items()
        }

    def evaluate(
        self,
        hypothesis: ProductHypothesis,
        signals: Sequence[MarketSignal],
        *,
        now: Optional[datetime] = None,
    ) -> VentureVector:
        """Blend a hypothesis baseline with independent market evidence.

        Evidence can move a dimension both up and down only when the signal itself is
        encoded accordingly. `strength` is interpreted as support intensity, therefore
        negative evidence should be represented by a low strength with high confidence.
        """
        hypothesis.validate()
        profile = self.evidence_profile(signals, now=now)
        base = hypothesis.baseline.to_dict()
        updated: Dict[str, float] = {}
        for name in DIMENSIONS:
            if name in profile:
                # External evidence receives 65% weight; baseline is retained for 35%.
                updated[name] = min(1.0, max(0.0, 0.35 * base[name] + 0.65 * profile[name]))
            else:
                updated[name] = base[name]

        fresh_count = len(self.filter_fresh_signals(signals, now=now))
        # Evidence strength and learning velocity reflect the amount of fresh, independent input.
        if fresh_count:
            evidence_density = min(1.0, fresh_count / 8.0)
            updated["evidence_strength"] = max(updated["evidence_strength"], evidence_density)
            updated["learning_velocity"] = max(updated["learning_velocity"], min(1.0, fresh_count / 6.0))
        return VentureVector(**updated).validate()

    def rank_hypotheses(
        self,
        hypotheses: Sequence[ProductHypothesis],
        signal_map: Dict[str, Sequence[MarketSignal]],
        *,
        now: Optional[datetime] = None,
    ) -> List[Tuple[ProductHypothesis, VentureVector, float]]:
        ranked = []
        for hypothesis in hypotheses:
            vector = self.evaluate(hypothesis, signal_map.get(hypothesis.hypothesis_id, ()), now=now)
            score = vector.weighted_score(self.weights)
            ranked.append((hypothesis, vector, score))
        return sorted(ranked, key=lambda item: item[2], reverse=True)

    @staticmethod
    def infer_stage(vector: VentureVector) -> str:
        vector.validate()
        if vector.market_pull < 0.45 or vector.evidence_strength < 0.35:
            return "EXPLORE"
        if vector.evidence_strength < 0.55 or vector.differentiation < 0.40:
            return "DISTILL"
        if vector.technical_feasibility < 0.62 or vector.delivery_velocity < 0.55:
            return "BUILD"
        if vector.market_pull < 0.72 or vector.unit_economics < 0.55 or vector.distribution_access < 0.50:
            return "VALIDATE"
        return "SCALE"

    @staticmethod
    def weakest_dimensions(vector: VentureVector, n: int = 3) -> List[str]:
        vector.validate()
        return [name for name, _ in sorted(vector.to_dict().items(), key=lambda item: item[1])[:n]]

    def choose_experiment(
        self,
        hypothesis: ProductHypothesis,
        vector: VentureVector,
    ) -> Experiment:
        """Choose the fastest high-information experiment for the current bottleneck."""
        stage = self.infer_stage(vector)
        weakest = self.weakest_dimensions(vector, 3)
        prefix = f"{hypothesis.hypothesis_id}-{stage.lower()}"

        if "market_pull" in weakest or stage == "EXPLORE":
            return Experiment(
                f"{prefix}-interviews", hypothesis.hypothesis_id, "customer_interviews",
                "Does the target customer repeatedly experience the stated problem strongly enough to act?",
                0.88, 12.0, 0.05, "analysis", "5+ independent problem confirmations with concrete current workaround",
                "Stop or reformulate if fewer than 3/10 interviews show recurring pain and existing spend/time cost.",
            )
        if "differentiation" in weakest or stage == "DISTILL":
            return Experiment(
                f"{prefix}-smoke", hypothesis.hypothesis_id, "problem_smoke_test",
                "Does a sharply differentiated promise create materially higher intent than the generic alternative?",
                0.82, 24.0, 0.12, "external_write", "qualified intent rate vs control",
                "Stop the positioning if uplift is below the predefined minimum after sufficient traffic.",
            )
        if "technical_feasibility" in weakest or "delivery_velocity" in weakest or stage == "BUILD":
            return Experiment(
                f"{prefix}-prototype", hypothesis.hypothesis_id, "prototype",
                "Can the smallest end-to-end workflow deliver the promised outcome inside the latency/cost envelope?",
                0.80, 36.0, 0.18, "local_prototype", "end-to-end task completion, latency and cost per successful run",
                "Stop architecture path if critical workflow cannot meet the explicit feasibility envelope.",
            )
        if "unit_economics" in weakest:
            return Experiment(
                f"{prefix}-pricing", hypothesis.hypothesis_id, "pricing_test",
                "Will a real buyer accept a price that supports the target gross-margin envelope?",
                0.86, 48.0, 0.20, "external_write", "price acceptance and gross-margin estimate",
                "Stop pricing model if accepted willingness-to-pay remains below delivery cost plus margin floor.",
            )
        if "distribution_access" in weakest:
            return Experiment(
                f"{prefix}-pilot", hypothesis.hypothesis_id, "paid_pilot",
                "Can the startup acquire and close a narrow customer segment through a repeatable channel?",
                0.90, 72.0, 0.30, "financial", "qualified lead→paid pilot conversion and acquisition effort",
                "Stop channel if repeated outreach fails to produce paid conversion inside the effort budget.",
            )
        return Experiment(
            f"{prefix}-retention", hypothesis.hypothesis_id, "retention_test",
            "Does repeated use create measurable retained value rather than one-off curiosity?",
            0.92, 168.0, 0.35, "external_write", "week-over-week retained usage / repeated value event",
            "Stop scaling if retained value remains below the explicit retention threshold.",
        )

    def next_state(
        self,
        previous: Optional[EvolutionState],
        hypothesis: ProductHypothesis,
        signals: Sequence[MarketSignal],
        *,
        now: Optional[datetime] = None,
    ) -> EvolutionState:
        vector = self.evaluate(hypothesis, signals, now=now)
        fresh = self.filter_fresh_signals(signals, now=now)
        previous_vector = previous.vector if previous else None
        blockers = []
        if not fresh:
            blockers.append("NO_FRESH_MARKET_EVIDENCE")
        if vector.security_readiness < 0.35 and self.infer_stage(vector) in {"VALIDATE", "SCALE"}:
            blockers.append("SECURITY_READINESS_BELOW_EXTERNAL_EFFECT_THRESHOLD")
        unknowns = self.weakest_dimensions(vector, 3)
        return EvolutionState(
            startup_id=self.startup_id,
            cycle=(previous.cycle + 1 if previous else 0),
            stage=self.infer_stage(vector),
            vector=vector,
            active_hypothesis_id=hypothesis.hypothesis_id,
            evidence_ids=[signal.signal_id for signal in fresh],
            previous_vector=previous_vector,
            unknowns=unknowns,
            blockers=blockers,
            created_at=now or datetime.now().astimezone(),
        ).validate()

    def plan_cycle(
        self,
        previous: Optional[EvolutionState],
        hypotheses: Sequence[ProductHypothesis],
        signal_map: Dict[str, Sequence[MarketSignal]],
        *,
        now: Optional[datetime] = None,
    ) -> Tuple[EvolutionState, ProductHypothesis, Experiment, float]:
        ranked = self.rank_hypotheses(hypotheses, signal_map, now=now)
        if not ranked:
            raise StartupModelError("at least one hypothesis is required")
        hypothesis, _, score = ranked[0]
        state = self.next_state(previous, hypothesis, signal_map.get(hypothesis.hypothesis_id, ()), now=now)
        experiment = self.choose_experiment(hypothesis, state.vector).validate()
        return state, hypothesis, experiment, score

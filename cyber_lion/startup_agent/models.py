"""Domain model for the Cyber-Lion Startup Evolution Agent.

The model separates market evidence, probabilistic judgement and execution authority.
All venture dimensions are normalized to [0, 1] so deltas remain explicit and auditable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional


DIMENSIONS = (
    "market_pull",
    "evidence_strength",
    "technical_feasibility",
    "differentiation",
    "distribution_access",
    "delivery_velocity",
    "security_readiness",
    "unit_economics",
    "learning_velocity",
)

Stage = Literal["EXPLORE", "DISTILL", "BUILD", "VALIDATE", "SCALE"]
AuthorityClass = Literal["analysis", "local_prototype", "external_write", "deploy", "financial"]


class StartupModelError(ValueError):
    pass


def _bounded(value: float, name: str) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise StartupModelError(f"{name} must be in [0,1], got {value}")
    return value


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class VentureVector:
    market_pull: float
    evidence_strength: float
    technical_feasibility: float
    differentiation: float
    distribution_access: float
    delivery_velocity: float
    security_readiness: float
    unit_economics: float
    learning_velocity: float

    def validate(self) -> "VentureVector":
        for name in DIMENSIONS:
            _bounded(getattr(self, name), name)
        return self

    def delta(self, previous: "VentureVector") -> Dict[str, float]:
        self.validate(); previous.validate()
        return {name: round(getattr(self, name) - getattr(previous, name), 6) for name in DIMENSIONS}

    def weighted_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        self.validate()
        weights = weights or {name: 1.0 for name in DIMENSIONS}
        unknown = set(weights) - set(DIMENSIONS)
        if unknown:
            raise StartupModelError(f"unknown dimensions in weights: {sorted(unknown)}")
        denominator = sum(float(weights.get(name, 0.0)) for name in DIMENSIONS)
        if denominator <= 0:
            raise StartupModelError("sum of weights must be positive")
        return sum(getattr(self, name) * float(weights.get(name, 0.0)) for name in DIMENSIONS) / denominator

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class MarketSignal:
    signal_id: str
    source: str
    observed_at: datetime
    kind: Literal[
        "demand", "pain", "competition", "pricing", "distribution",
        "technical", "security", "retention", "conversion", "cost"
    ]
    strength: float
    confidence: float
    note: str = ""

    def validate(self) -> "MarketSignal":
        if not self.signal_id or not self.source:
            raise StartupModelError("market signal requires signal_id and source")
        _bounded(self.strength, "signal.strength")
        _bounded(self.confidence, "signal.confidence")
        if self.observed_at.tzinfo is None:
            raise StartupModelError("observed_at must be timezone-aware")
        return self

    def age_days(self, now: Optional[datetime] = None) -> float:
        self.validate()
        now = now or utc_now()
        return max(0.0, (now - self.observed_at).total_seconds() / 86400.0)

    def freshness(self, now: Optional[datetime] = None, half_life_days: float = 30.0) -> float:
        if half_life_days <= 0:
            raise StartupModelError("half_life_days must be positive")
        return 0.5 ** (self.age_days(now) / half_life_days)

    def evidence_weight(self, now: Optional[datetime] = None) -> float:
        return self.strength * self.confidence * self.freshness(now)


@dataclass(frozen=True)
class ProductHypothesis:
    hypothesis_id: str
    customer: str
    problem: str
    solution: str
    revenue_model: str
    baseline: VentureVector
    assumptions: List[str] = field(default_factory=list)

    def validate(self) -> "ProductHypothesis":
        if not all([self.hypothesis_id, self.customer, self.problem, self.solution]):
            raise StartupModelError("hypothesis id/customer/problem/solution are required")
        self.baseline.validate()
        return self


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    hypothesis_id: str
    experiment_type: Literal[
        "customer_interviews", "problem_smoke_test", "landing_page",
        "concierge", "prototype", "paid_pilot", "retention_test", "pricing_test"
    ]
    question: str
    expected_information_gain: float
    time_to_evidence_hours: float
    cost_units: float
    authority_class: AuthorityClass
    success_metric: str
    stop_condition: str

    def validate(self) -> "Experiment":
        if not self.experiment_id or not self.question or not self.success_metric or not self.stop_condition:
            raise StartupModelError("experiment identity/question/metric/stop condition required")
        _bounded(self.expected_information_gain, "expected_information_gain")
        if self.time_to_evidence_hours <= 0 or self.cost_units < 0:
            raise StartupModelError("experiment time must be >0 and cost >=0")
        return self

    @property
    def velocity_value(self) -> float:
        self.validate()
        return self.expected_information_gain / (1.0 + self.time_to_evidence_hours / 24.0 + self.cost_units)


@dataclass
class EvolutionState:
    startup_id: str
    cycle: int
    stage: Stage
    vector: VentureVector
    active_hypothesis_id: Optional[str]
    evidence_ids: List[str] = field(default_factory=list)
    previous_vector: Optional[VentureVector] = None
    unknowns: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)

    def validate(self) -> "EvolutionState":
        if not self.startup_id or self.cycle < 0:
            raise StartupModelError("startup_id required and cycle must be non-negative")
        self.vector.validate()
        if self.created_at.tzinfo is None:
            raise StartupModelError("created_at must be timezone-aware")
        return self

    def delta(self) -> Dict[str, float]:
        if self.previous_vector is None:
            return {name: 0.0 for name in DIMENSIONS}
        return self.vector.delta(self.previous_vector)

"""Provenance-aware market intelligence for the Startup Evolution Agent.

This module deliberately does not scrape the internet itself. It defines the contract that
any live connector, analyst, CRM export, product telemetry feed or web researcher must satisfy
before observations are allowed to influence venture state.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Literal, Optional, Tuple

from .models import MarketSignal, StartupModelError


Direction = Literal["supports", "contradicts", "neutral"]
SourceClass = Literal[
    "customer", "sales", "product_telemetry", "competitor", "pricing",
    "developer_ecosystem", "public_research", "vendor", "regulatory", "internal"
]


@dataclass(frozen=True)
class MarketObservation:
    observation_id: str
    hypothesis_id: str
    source: str
    source_class: SourceClass
    observed_at: datetime
    captured_at: datetime
    topic: str
    signal_kind: Literal[
        "demand", "pain", "competition", "pricing", "distribution",
        "technical", "security", "retention", "conversion", "cost"
    ]
    direction: Direction
    magnitude: float
    confidence: float
    claim: str
    evidence_ref: str = ""

    def validate(self) -> "MarketObservation":
        if not all([self.observation_id, self.hypothesis_id, self.source, self.topic, self.claim]):
            raise StartupModelError("market observation identity/source/topic/claim required")
        if self.observed_at.tzinfo is None or self.captured_at.tzinfo is None:
            raise StartupModelError("market observation timestamps must be timezone-aware")
        if not 0 <= self.magnitude <= 1 or not 0 <= self.confidence <= 1:
            raise StartupModelError("magnitude/confidence must be in [0,1]")
        if self.captured_at < self.observed_at:
            raise StartupModelError("captured_at cannot precede observed_at")
        return self

    @property
    def fingerprint(self) -> str:
        material = "|".join([
            self.hypothesis_id,
            self.source.strip().lower(),
            self.topic.strip().lower(),
            self.claim.strip().lower(),
            self.observed_at.isoformat(),
        ])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def to_market_signal(self) -> MarketSignal:
        self.validate()
        strength = self.magnitude
        if self.direction == "contradicts":
            # Low strength + high confidence represents strong negative evidence in the
            # existing MarketSignal contract without introducing signed values.
            strength = 1.0 - self.magnitude
        elif self.direction == "neutral":
            strength = 0.5
        return MarketSignal(
            signal_id=self.observation_id,
            source=f"{self.source_class}:{self.source}",
            observed_at=self.observed_at,
            kind=self.signal_kind,
            strength=strength,
            confidence=self.confidence,
            note=self.claim,
        ).validate()


@dataclass(frozen=True)
class Contradiction:
    hypothesis_id: str
    topic: str
    supporting_ids: Tuple[str, ...]
    contradicting_ids: Tuple[str, ...]


@dataclass
class MarketEvidenceBook:
    """Append-only logical evidence set with deduplication and contradiction visibility."""

    _observations: Dict[str, MarketObservation] = field(default_factory=dict)
    _fingerprints: Dict[str, str] = field(default_factory=dict)

    def add(self, observation: MarketObservation) -> bool:
        observation.validate()
        if observation.observation_id in self._observations:
            if self._observations[observation.observation_id] != observation:
                raise StartupModelError(f"observation changed under same id: {observation.observation_id}")
            return False
        if observation.fingerprint in self._fingerprints:
            return False
        self._observations[observation.observation_id] = observation
        self._fingerprints[observation.fingerprint] = observation.observation_id
        return True

    def extend(self, observations: Iterable[MarketObservation]) -> int:
        return sum(1 for observation in observations if self.add(observation))

    def observations(self, hypothesis_id: Optional[str] = None) -> List[MarketObservation]:
        values = self._observations.values()
        if hypothesis_id is not None:
            values = (obs for obs in values if obs.hypothesis_id == hypothesis_id)
        return sorted(values, key=lambda obs: (obs.observed_at, obs.observation_id))

    def signals(self, hypothesis_id: str) -> List[MarketSignal]:
        return [obs.to_market_signal() for obs in self.observations(hypothesis_id)]

    def contradictions(self, hypothesis_id: Optional[str] = None) -> List[Contradiction]:
        groups: Dict[Tuple[str, str], Dict[str, List[str]]] = {}
        for obs in self.observations(hypothesis_id):
            key = (obs.hypothesis_id, obs.topic.strip().lower())
            bucket = groups.setdefault(key, {"supports": [], "contradicts": []})
            if obs.direction in bucket:
                bucket[obs.direction].append(obs.observation_id)
        result = []
        for (hid, topic), bucket in groups.items():
            if bucket["supports"] and bucket["contradicts"]:
                result.append(Contradiction(
                    hid,
                    topic,
                    tuple(sorted(bucket["supports"])),
                    tuple(sorted(bucket["contradicts"])),
                ))
        return result

    def freshness_report(self, *, now: Optional[datetime] = None, fresh_days: float = 30.0) -> Dict[str, float]:
        if fresh_days <= 0:
            raise StartupModelError("fresh_days must be positive")
        now = now or datetime.now(timezone.utc)
        observations = self.observations()
        if not observations:
            return {"total": 0, "fresh": 0, "fresh_ratio": 0.0, "oldest_age_days": 0.0}
        ages = [max(0.0, (now - obs.observed_at).total_seconds() / 86400.0) for obs in observations]
        fresh = sum(1 for age in ages if age <= fresh_days)
        return {
            "total": float(len(observations)),
            "fresh": float(fresh),
            "fresh_ratio": fresh / len(observations),
            "oldest_age_days": max(ages),
        }

    def source_diversity(self, hypothesis_id: Optional[str] = None) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for obs in self.observations(hypothesis_id):
            counts[obs.source_class] = counts.get(obs.source_class, 0) + 1
        return counts

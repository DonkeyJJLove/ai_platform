"""Provider contracts for plugging live market sources and AI models into Startup Evolution.

Providers may observe and propose. Registration/discovery never grants execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol, Sequence, runtime_checkable

from .build_planner import SoftwareBuildSpec
from .market_intelligence import MarketObservation
from .models import EvolutionState, ProductHypothesis, StartupModelError


@dataclass(frozen=True)
class ProviderContext:
    startup_id: str
    objective: str
    current_state: Optional[EvolutionState] = None
    constraints: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def validate(self) -> "ProviderContext":
        if not self.startup_id or not self.objective:
            raise StartupModelError("provider context requires startup_id and objective")
        if self.created_at.tzinfo is None:
            raise StartupModelError("provider context timestamp must be timezone-aware")
        return self


@dataclass(frozen=True)
class ProviderReceipt:
    provider_id: str
    provider_kind: str
    provider_version: str
    generated_at: datetime
    output_ids: tuple[str, ...]
    notes: tuple[str, ...] = ()

    def validate(self) -> "ProviderReceipt":
        if not all([self.provider_id, self.provider_kind, self.provider_version]):
            raise StartupModelError("provider receipt identity required")
        if self.generated_at.tzinfo is None:
            raise StartupModelError("provider receipt timestamp must be timezone-aware")
        return self


@runtime_checkable
class MarketSourceProvider(Protocol):
    provider_id: str
    provider_version: str

    def collect(self, context: ProviderContext) -> Sequence[MarketObservation]: ...


@runtime_checkable
class HypothesisProvider(Protocol):
    provider_id: str
    provider_version: str

    def propose(
        self,
        context: ProviderContext,
        observations: Sequence[MarketObservation],
    ) -> Sequence[ProductHypothesis]: ...


@runtime_checkable
class SoftwareProposalProvider(Protocol):
    provider_id: str
    provider_version: str

    def propose_files(
        self,
        context: ProviderContext,
        spec: SoftwareBuildSpec,
    ) -> Dict[str, str]: ...


@dataclass
class StaticMarketProvider:
    """Deterministic provider useful for tests, fixtures and imported analyst research."""

    observations: List[MarketObservation]
    provider_id: str = "static-market"
    provider_version: str = "1.0.0"

    def collect(self, context: ProviderContext) -> Sequence[MarketObservation]:
        context.validate()
        return list(self.observations)


@dataclass
class StaticHypothesisProvider:
    """Deterministic hypothesis provider; does not infer anything beyond supplied objects."""

    hypotheses: List[ProductHypothesis]
    provider_id: str = "static-hypotheses"
    provider_version: str = "1.0.0"

    def propose(
        self,
        context: ProviderContext,
        observations: Sequence[MarketObservation],
    ) -> Sequence[ProductHypothesis]:
        context.validate()
        for observation in observations:
            observation.validate()
        return list(self.hypotheses)


class ProviderCoordinator:
    """Collect provider outputs while preserving provenance receipts."""

    def collect_market(
        self,
        context: ProviderContext,
        providers: Sequence[MarketSourceProvider],
    ) -> tuple[List[MarketObservation], List[ProviderReceipt]]:
        context.validate()
        observations: List[MarketObservation] = []
        receipts: List[ProviderReceipt] = []
        for provider in providers:
            batch = list(provider.collect(context))
            for item in batch:
                item.validate()
            observations.extend(batch)
            receipts.append(ProviderReceipt(
                provider.provider_id,
                "market_source",
                provider.provider_version,
                datetime.now(timezone.utc),
                tuple(item.observation_id for item in batch),
            ).validate())
        return observations, receipts

    def propose_hypotheses(
        self,
        context: ProviderContext,
        observations: Sequence[MarketObservation],
        providers: Sequence[HypothesisProvider],
    ) -> tuple[List[ProductHypothesis], List[ProviderReceipt]]:
        context.validate()
        hypotheses: List[ProductHypothesis] = []
        receipts: List[ProviderReceipt] = []
        for provider in providers:
            batch = list(provider.propose(context, observations))
            for item in batch:
                item.validate()
            hypotheses.extend(batch)
            receipts.append(ProviderReceipt(
                provider.provider_id,
                "hypothesis",
                provider.provider_version,
                datetime.now(timezone.utc),
                tuple(item.hypothesis_id for item in batch),
            ).validate())
        return hypotheses, receipts

    @staticmethod
    def deduplicate_hypotheses(hypotheses: Sequence[ProductHypothesis]) -> List[ProductHypothesis]:
        by_id: Dict[str, ProductHypothesis] = {}
        for hypothesis in hypotheses:
            hypothesis.validate()
            existing = by_id.get(hypothesis.hypothesis_id)
            if existing is not None and existing != hypothesis:
                raise StartupModelError(
                    f"hypothesis changed under same id: {hypothesis.hypothesis_id}"
                )
            by_id[hypothesis.hypothesis_id] = hypothesis
        return list(by_id.values())

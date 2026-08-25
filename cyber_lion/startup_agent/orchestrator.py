"""End-to-end orchestration for the Cyber-Lion Startup Evolution Agent."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .authority import GateDecision, StartupAuthorityGate
from .build_planner import SafeTemplateBuilder, SoftwareBuildPlanner, SoftwareBuildSpec
from .engine import StartupEvolutionAgent
from .local_build import BoundedLocalBuildRunner, BuildReceipt, LocalBuildExecutionGate
from .market_intelligence import MarketEvidenceBook
from .models import EvolutionState, Experiment, ProductHypothesis, StartupModelError, VentureVector
from .providers import (
    HypothesisProvider,
    MarketSourceProvider,
    ProviderContext,
    ProviderCoordinator,
    ProviderReceipt,
)


@dataclass(frozen=True)
class CyclePlan:
    state: EvolutionState
    hypothesis: ProductHypothesis
    experiment: Experiment
    build_spec: SoftwareBuildSpec
    scaffold: Dict[str, str]
    authority: GateDecision
    score: float


@dataclass(frozen=True)
class ProviderCyclePlan:
    """Cycle plan plus immutable provider provenance for the observations/hypotheses used."""

    plan: CyclePlan
    market_receipts: tuple[ProviderReceipt, ...]
    hypothesis_receipts: tuple[ProviderReceipt, ...]


@dataclass(frozen=True)
class ExperimentOutcome:
    experiment_id: str
    success: bool
    evidence_quality: float
    observed_value: float
    time_hours: float
    cost_units: float
    note: str = ""

    def validate(self) -> "ExperimentOutcome":
        if not self.experiment_id:
            raise StartupModelError("experiment_id is required")
        for name, value in {
            "evidence_quality": self.evidence_quality,
            "observed_value": self.observed_value,
        }.items():
            if not 0.0 <= float(value) <= 1.0:
                raise StartupModelError(f"{name} must be in [0,1]")
        if self.time_hours < 0 or self.cost_units < 0:
            raise StartupModelError("outcome time/cost must be non-negative")
        return self


class AIDrivenStartupAgent:
    """Facade combining market evidence, product evolution, build planning and authority."""

    def __init__(self, startup_id: str, *, max_signal_age_days: float = 90.0) -> None:
        self.evolution = StartupEvolutionAgent(startup_id, max_signal_age_days=max_signal_age_days)
        self.build_planner = SoftwareBuildPlanner()
        self.builder = SafeTemplateBuilder()
        self.authority_gate = StartupAuthorityGate()
        self.local_build_runner = BoundedLocalBuildRunner()
        self.provider_coordinator = ProviderCoordinator()
        self.evidence = MarketEvidenceBook()

    def plan(
        self,
        hypotheses: Sequence[ProductHypothesis],
        *,
        previous: Optional[EvolutionState] = None,
        gate_event_id: Optional[str] = None,
    ) -> CyclePlan:
        if not hypotheses:
            raise StartupModelError("at least one hypothesis is required")
        signal_map = {
            hypothesis.hypothesis_id: self.evidence.signals(hypothesis.hypothesis_id)
            for hypothesis in hypotheses
        }
        state, hypothesis, experiment, score = self.evolution.plan_cycle(previous, hypotheses, signal_map)
        build_spec = self.build_planner.from_experiment(hypothesis, experiment)
        scaffold = self.builder.render(build_spec)
        authority = self.authority_gate.decide(experiment, gate_event_id=gate_event_id)
        return CyclePlan(state, hypothesis, experiment, build_spec, scaffold, authority, score)

    def plan_from_providers(
        self,
        context: ProviderContext,
        market_providers: Sequence[MarketSourceProvider],
        hypothesis_providers: Sequence[HypothesisProvider],
        *,
        previous: Optional[EvolutionState] = None,
        gate_event_id: Optional[str] = None,
    ) -> ProviderCyclePlan:
        """Collect observations/proposals through provider contracts, then use the normal plan path.

        Provider outputs are inputs only. `gate_event_id` can be supplied only by the caller
        representing the authority plane; no provider interface contains a way to grant it.
        """
        context.validate()
        observations, market_receipts = self.provider_coordinator.collect_market(context, market_providers)
        self.evidence.extend(observations)
        hypotheses, hypothesis_receipts = self.provider_coordinator.propose_hypotheses(
            context, observations, hypothesis_providers
        )
        hypotheses = self.provider_coordinator.deduplicate_hypotheses(hypotheses)
        if not hypotheses:
            raise StartupModelError("hypothesis providers produced no valid hypotheses")
        plan = self.plan(hypotheses, previous=previous, gate_event_id=gate_event_id)
        return ProviderCyclePlan(plan, tuple(market_receipts), tuple(hypothesis_receipts))

    def build_local(self, plan: CyclePlan, *, execution_gate_event_id: str) -> BuildReceipt:
        """Execute a local-only plan only after policy ALLOW plus explicit effect-gate evidence."""
        if plan.authority.decision != "ALLOW":
            raise StartupModelError(
                f"local build requires autonomous ALLOW decision, got {plan.authority.decision}"
            )
        if not isinstance(execution_gate_event_id, str) or not execution_gate_event_id.strip():
            raise StartupModelError("local build requires explicit execution gate evidence")
        gate = LocalBuildExecutionGate.seal(
            gate_event_id=execution_gate_event_id,
            spec_id=plan.build_spec.spec_id,
            authority_class=plan.build_spec.authority_class,
            nonce=f"{plan.state.cycle}:{plan.experiment.experiment_id}",
        )
        return self.local_build_runner.run(plan.build_spec, plan.scaffold, gate=gate)

    @staticmethod
    def apply_outcome(state: EvolutionState, experiment: Experiment, outcome: ExperimentOutcome) -> EvolutionState:
        """Apply a bounded deterministic correction from observed experiment outcome.

        The correction intentionally changes only dimensions directly related to the
        experiment class. It never promotes all dimensions because one experiment succeeded.
        """
        state.validate(); experiment.validate(); outcome.validate()
        if outcome.experiment_id != experiment.experiment_id:
            raise StartupModelError("outcome/experiment mismatch")

        values = state.vector.to_dict()
        direction = 1.0 if outcome.success else -1.0
        evidence_step = direction * min(0.18, 0.18 * outcome.evidence_quality)
        value_step = direction * min(0.15, 0.15 * outcome.observed_value)

        affected: List[str]
        if experiment.experiment_type in {"customer_interviews", "problem_smoke_test", "landing_page"}:
            affected = ["market_pull", "evidence_strength", "differentiation"]
        elif experiment.experiment_type == "prototype":
            affected = ["technical_feasibility", "delivery_velocity", "evidence_strength"]
        elif experiment.experiment_type == "pricing_test":
            affected = ["unit_economics", "market_pull", "evidence_strength"]
        elif experiment.experiment_type == "paid_pilot":
            affected = ["distribution_access", "unit_economics", "market_pull", "evidence_strength"]
        elif experiment.experiment_type == "retention_test":
            affected = ["market_pull", "evidence_strength", "unit_economics"]
        else:
            affected = ["evidence_strength", "learning_velocity"]

        for dimension in affected:
            delta = evidence_step if dimension == "evidence_strength" else value_step
            values[dimension] = min(1.0, max(0.0, values[dimension] + delta))

        values["learning_velocity"] = min(
            1.0,
            max(values["learning_velocity"], values["learning_velocity"] + 0.08 * outcome.evidence_quality),
        )

        corrected = VentureVector(**values).validate()
        return EvolutionState(
            startup_id=state.startup_id,
            cycle=state.cycle + 1,
            stage=StartupEvolutionAgent.infer_stage(corrected),
            vector=corrected,
            previous_vector=state.vector,
            active_hypothesis_id=state.active_hypothesis_id,
            evidence_ids=list(state.evidence_ids),
            unknowns=StartupEvolutionAgent.weakest_dimensions(corrected, 3),
            blockers=list(state.blockers),
        ).validate()

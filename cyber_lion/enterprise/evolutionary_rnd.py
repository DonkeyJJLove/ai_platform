"""Deterministic state engine for the Cyber-Lion evolutionary R&D loop.

This module never executes repository/runtime/deploy effects. It only validates and
materializes epistemic transitions, append-only memory, and knowledge promotion.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from typing import Dict, Iterable

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
    TERMINAL_HYPOTHESIS_STATES,
    canonical_json,
)


class EvolutionaryRnDError(RuntimeError):
    pass


_ALLOWED_TRANSITIONS = {
    "PROPOSED": {"ADMITTED_FOR_TEST"},
    "ADMITTED_FOR_TEST": {"TESTING"},
    "TESTING": {"SUPPORTED", "FALSIFIED", "INCONCLUSIVE", "CONTRADICTED"},
    "SUPPORTED": set(),
    "FALSIFIED": set(),
    "INCONCLUSIVE": set(),
    "CONTRADICTED": set(),
}


class EvolutionaryRnDEngine:
    """In-memory deterministic composition root for one bounded R&D mission."""

    def __init__(self) -> None:
        self._identity_payloads: Dict[tuple[str, str], str] = {}
        self._evidence_by_id: Dict[str, EvidenceObservation] = {}
        self._evidence_by_digest: Dict[str, str] = {}
        self._hypotheses: Dict[str, Hypothesis] = {}
        self._experiments: Dict[str, ExperimentProposal] = {}
        self._simulations: Dict[str, SimulationPlan] = {}
        self._results: Dict[str, ExperimentResult] = {}
        self._falsifications: Dict[str, FalsificationResult] = {}
        self._deltas: Dict[str, EvolutionDelta] = {}
        self._promotions: Dict[str, PromotionDecision] = {}
        self._promotion_by_hypothesis: Dict[str, str] = {}
        self._memory: list[RnDMemoryRecord] = []
        self._memory_head = "GENESIS"

    @staticmethod
    def _record_key(value: object) -> tuple[str, str]:
        for attr in (
            "observation_id", "hypothesis_id", "experiment_id", "simulation_id",
            "result_id", "falsification_id", "promotion_id", "memory_id", "delta_id",
        ):
            if hasattr(value, attr):
                return type(value).__name__, str(getattr(value, attr))
        raise EvolutionaryRnDError("record identity unavailable")

    def _bind_identity(self, value: object, digest_value: str) -> None:
        key = self._record_key(value)
        previous = self._identity_payloads.get(key)
        if previous is not None and previous != digest_value:
            raise EvolutionaryRnDError("stable identity payload substitution denied")
        self._identity_payloads[key] = digest_value

    def register_evidence(self, observation: EvidenceObservation) -> EvidenceObservation:
        observation.validate()
        if not observation.observation_digest:
            raise EvolutionaryRnDError("evidence must be sealed")

        prior_observation = self._evidence_by_id.get(observation.observation_id)
        if prior_observation is not None:
            if prior_observation.observation_digest != observation.observation_digest:
                raise EvolutionaryRnDError("evidence identity payload substitution denied")
            return prior_observation

        prior_id = self._evidence_by_digest.get(observation.observation_digest)
        if prior_id is not None and prior_id != observation.observation_id:
            raise EvolutionaryRnDError("evidence digest rebound to incompatible identity denied")

        self._bind_identity(observation, observation.observation_digest)
        self._evidence_by_id[observation.observation_id] = observation
        self._evidence_by_digest[observation.observation_digest] = observation.observation_id
        return observation

    def _require_evidence_refs(self, refs: Iterable[str], *, role: str) -> None:
        for ref in refs:
            if ref not in self._evidence_by_id:
                raise EvolutionaryRnDError(f"unknown {role} evidence reference: {ref}")

    def register_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        hypothesis.validate()
        if not hypothesis.hypothesis_digest:
            raise EvolutionaryRnDError("hypothesis must be sealed")
        self._require_evidence_refs(hypothesis.evidence_refs, role="supporting")
        self._require_evidence_refs(hypothesis.counter_evidence_refs, role="counter")
        self._bind_identity(hypothesis, hypothesis.hypothesis_digest)
        previous = self._hypotheses.get(hypothesis.hypothesis_id)
        if previous is not None:
            if hypothesis.revision <= previous.revision:
                raise EvolutionaryRnDError("hypothesis revision replay/rollback denied")
            if previous.state not in TERMINAL_HYPOTHESIS_STATES:
                raise EvolutionaryRnDError("cannot supersede non-terminal hypothesis")
            if hypothesis.revision != previous.revision + 1:
                raise EvolutionaryRnDError("hypothesis revision must increment exactly once")
            if hypothesis.supersedes_hypothesis_digest != previous.hypothesis_digest:
                raise EvolutionaryRnDError("hypothesis supersession lineage mismatch")
        self._hypotheses[hypothesis.hypothesis_id] = hypothesis
        return hypothesis

    def transition_hypothesis(self, current: Hypothesis, next_state: str) -> Hypothesis:
        current.validate()
        stored = self._hypotheses.get(current.hypothesis_id)
        if stored is None or stored.hypothesis_digest != current.hypothesis_digest:
            raise EvolutionaryRnDError("unknown or substituted hypothesis")
        if next_state not in _ALLOWED_TRANSITIONS.get(current.state, set()):
            raise EvolutionaryRnDError("hypothesis transition denied")
        transitioned = Hypothesis(
            hypothesis_id=current.hypothesis_id,
            revision=current.revision,
            claim=current.claim,
            evidence_refs=current.evidence_refs,
            counter_evidence_refs=current.counter_evidence_refs,
            falsifiers=current.falsifiers,
            alternative_explanations=current.alternative_explanations,
            state=next_state,
            provenance_refs=current.provenance_refs,
            supersedes_hypothesis_digest=current.supersedes_hypothesis_digest,
        ).sealed()
        self._hypotheses[current.hypothesis_id] = transitioned
        self._identity_payloads[(type(current).__name__, current.hypothesis_id)] = transitioned.hypothesis_digest
        return transitioned

    def register_experiment(self, proposal: ExperimentProposal) -> ExperimentProposal:
        proposal.validate()
        if not proposal.experiment_digest:
            raise EvolutionaryRnDError("experiment must be sealed")
        hypothesis = self._find_hypothesis_by_digest(proposal.hypothesis_digest)
        if hypothesis.state not in {"ADMITTED_FOR_TEST", "TESTING"}:
            raise EvolutionaryRnDError("experiment requires admitted/testing hypothesis")
        if not set(proposal.evidence_refs).issubset(set(hypothesis.evidence_refs) | set(hypothesis.counter_evidence_refs)):
            raise EvolutionaryRnDError("experiment evidence not bound to hypothesis")
        if set(proposal.falsification_conditions) != set(hypothesis.falsifiers):
            raise EvolutionaryRnDError("experiment must bind exact hypothesis falsifiers")
        self._bind_identity(proposal, proposal.experiment_digest)
        self._experiments[proposal.experiment_digest] = proposal
        return proposal

    def register_simulation(self, plan: SimulationPlan) -> SimulationPlan:
        plan.validate()
        if not plan.simulation_digest:
            raise EvolutionaryRnDError("simulation must be sealed")
        if plan.experiment_digest not in self._experiments:
            raise EvolutionaryRnDError("orphan simulation denied")
        self._bind_identity(plan, plan.simulation_digest)
        self._simulations[plan.simulation_digest] = plan
        return plan

    def register_result(self, result: ExperimentResult) -> ExperimentResult:
        result.validate()
        if not result.result_digest:
            raise EvolutionaryRnDError("result must be sealed")
        if result.experiment_digest not in self._experiments:
            raise EvolutionaryRnDError("orphan result denied")
        if result.result_class == "OBSERVED" and any(
            plan.experiment_digest == result.experiment_digest for plan in self._simulations.values()
        ):
            raise EvolutionaryRnDError("simulation result cannot be relabeled OBSERVED")
        self._bind_identity(result, result.result_digest)
        if result.result_digest in self._results:
            raise EvolutionaryRnDError("result replay denied")
        self._results[result.result_digest] = result
        return result

    def register_falsification(self, result: FalsificationResult) -> FalsificationResult:
        result.validate()
        if not result.falsification_digest:
            raise EvolutionaryRnDError("falsification must be sealed")
        hypothesis = self._find_hypothesis_by_digest(result.hypothesis_digest)
        if hypothesis.state not in TERMINAL_HYPOTHESIS_STATES:
            raise EvolutionaryRnDError("falsification requires terminal hypothesis state")
        if any(digest not in self._results for digest in result.experiment_result_digests):
            raise EvolutionaryRnDError("falsification references unknown result")
        if set(result.attempted_falsifiers) != set(hypothesis.falsifiers):
            raise EvolutionaryRnDError("falsification attempt set incomplete")
        expected = {
            "SUPPORTED": "SUPPORTED",
            "FALSIFIED": "FALSIFIED",
            "INCONCLUSIVE": "INCONCLUSIVE",
            "CONTRADICTED": "CONTRADICTED",
        }[hypothesis.state]
        if result.disposition != expected:
            raise EvolutionaryRnDError("falsification disposition contradicts hypothesis state")
        if set(result.contrary_evidence_refs) != set(hypothesis.counter_evidence_refs):
            raise EvolutionaryRnDError("contrary evidence declaration incomplete")
        self._bind_identity(result, result.falsification_digest)
        self._falsifications[result.falsification_digest] = result
        return result

    def register_delta(self, delta: EvolutionDelta) -> EvolutionDelta:
        delta.validate()
        if not delta.delta_digest:
            raise EvolutionaryRnDError("delta must be sealed")
        self._require_evidence_refs(delta.evidence_refs, role="delta")
        if delta.delta_digest in self._deltas:
            raise EvolutionaryRnDError("EvolutionDelta replay denied")
        self._bind_identity(delta, delta.delta_digest)
        self._deltas[delta.delta_digest] = delta
        return delta

    def promote(self, decision: PromotionDecision) -> PromotionDecision:
        decision.validate()
        if not decision.promotion_digest:
            raise EvolutionaryRnDError("promotion must be sealed")
        hypothesis = self._find_hypothesis_by_digest(decision.hypothesis_digest)
        falsification = self._falsifications.get(decision.falsification_digest)
        delta = self._deltas.get(decision.evolution_delta_digest)
        if falsification is None or delta is None:
            raise EvolutionaryRnDError("promotion dependency missing")
        if falsification.hypothesis_digest != hypothesis.hypothesis_digest:
            raise EvolutionaryRnDError("promotion falsification binding mismatch")
        if decision.hypothesis_state != hypothesis.state or decision.falsification_disposition != falsification.disposition:
            raise EvolutionaryRnDError("promotion state substitution denied")
        if decision.decision == "PROMOTE_KNOWLEDGE":
            if set(falsification.contrary_evidence_refs) != set(hypothesis.counter_evidence_refs):
                raise EvolutionaryRnDError("hidden contrary evidence denied")
        if decision.promotion_id in self._promotions:
            raise EvolutionaryRnDError("promotion replay denied")
        if decision.hypothesis_digest in self._promotion_by_hypothesis:
            raise EvolutionaryRnDError("duplicate hypothesis promotion denied")
        self._bind_identity(decision, decision.promotion_digest)
        self._promotions[decision.promotion_id] = decision
        self._promotion_by_hypothesis[decision.hypothesis_digest] = decision.promotion_digest
        return decision

    def append_memory(self, record: RnDMemoryRecord) -> str:
        record.validate()
        if not record.memory_digest:
            raise EvolutionaryRnDError("memory record must be sealed")
        expected_revision = len(self._memory) + 1
        if record.revision != expected_revision:
            raise EvolutionaryRnDError("memory revision must increase exactly once")
        if record.previous_memory_head != self._memory_head:
            raise EvolutionaryRnDError("broken memory head denied")
        self._bind_identity(record, record.memory_digest)
        self._memory.append(record)
        self._memory_head = sha256(
            b"LION/E004-RND-MEMORY-CHAIN/1\0"
            + self._memory_head.encode("ascii")
            + record.memory_digest.encode("ascii")
        ).hexdigest()
        return self._memory_head

    @property
    def memory_head(self) -> str:
        return self._memory_head

    @property
    def memory_records(self) -> tuple[RnDMemoryRecord, ...]:
        return tuple(self._memory)

    def verify_memory(self, records: Iterable[RnDMemoryRecord]) -> str:
        head = "GENESIS"
        expected_revision = 1
        for record in records:
            record.validate()
            if record.revision != expected_revision or record.previous_memory_head != head:
                raise EvolutionaryRnDError("memory history rewrite/break detected")
            head = sha256(
                b"LION/E004-RND-MEMORY-CHAIN/1\0"
                + head.encode("ascii")
                + record.memory_digest.encode("ascii")
            ).hexdigest()
            expected_revision += 1
        return head

    def _find_hypothesis_by_digest(self, digest_value: str) -> Hypothesis:
        for hypothesis in self._hypotheses.values():
            if hypothesis.hypothesis_digest == digest_value:
                return hypothesis
        raise EvolutionaryRnDError("unknown hypothesis digest")

    def state_digest(self) -> str:
        payload = {
            "evidence": sorted(
                (observation_id, observation.observation_digest)
                for observation_id, observation in self._evidence_by_id.items()
            ),
            "hypotheses": sorted(h.hypothesis_digest for h in self._hypotheses.values()),
            "experiments": sorted(self._experiments),
            "simulations": sorted(self._simulations),
            "results": sorted(self._results),
            "falsifications": sorted(self._falsifications),
            "deltas": sorted(self._deltas),
            "promotions": sorted(p.promotion_digest for p in self._promotions.values()),
            "memory_head": self._memory_head,
        }
        return sha256(b"LION/E004-RND-ENGINE-STATE/1\0" + canonical_json(payload)).hexdigest()


def assert_no_effect_surface() -> None:
    """Static invariant helper used by tests/verification."""
    forbidden = {
        "execute", "deploy", "release", "push", "merge", "delete_ref",
        "repository_effect", "runtime_authority", "credentials",
    }
    public = {name.lower() for name in dir(EvolutionaryRnDEngine) if not name.startswith("_")}
    if public & forbidden:
        raise EvolutionaryRnDError("direct cognition-to-effect surface exposed")

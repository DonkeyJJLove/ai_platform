"""Deterministic fitness projection for choosing the next LION evolution candidate.

This module is intentionally non-effectful.  It ranks already-described,
source-bound evolution candidates; it does not authorize, schedule, mutate,
merge, deploy, or execute them.

Selection is deliberately two-stage:

1. hard architectural gates remove candidates that cannot be reasoned about
   safely from the current source/effect state;
2. the remaining set is reduced to a Pareto frontier and a deterministic
   dynamic utility score chooses one critical-path candidate.

Dynamic pressure changes the relative weight of an existing dimension but
cannot create authority, waive a hard gate, or introduce a new dimension.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping, Tuple

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_SCALE = 1000
_DOMAIN_VECTOR = b"LION/EVOLUTION-FITNESS-VECTOR/1\0"
_DOMAIN_ASSESSMENT = b"LION/EVOLUTION-FITNESS-ASSESSMENT/1\0"
_DOMAIN_SELECTION = b"LION/EVOLUTION-FITNESS-SELECTION/1\0"
_EFFECT_METHOD_NAMES = frozenset(
    {"authorize", "admit", "execute", "write", "push", "merge", "deploy", "release", "schedule", "dispatch"}
)

BENEFIT_DIMENSIONS: Tuple[str, ...] = (
    "capability_gain",
    "federation_leverage",
    "functional_value",
    "generativity_gain",
    "integration_closure",
    "knowledge_feedback",
    "recovery_strength",
    "reuse_leverage",
    "verification_strength",
)
COST_DIMENSIONS: Tuple[str, ...] = (
    "authority_risk",
    "blast_radius",
    "change_surface",
    "currentness_debt",
    "implementation_cost",
    "operational_cost",
)
ALL_DIMENSIONS = frozenset(BENEFIT_DIMENSIONS + COST_DIMENSIONS)

HARD_GATE_FIELDS: Tuple[tuple[str, str], ...] = (
    ("source_current", "SOURCE_CURRENT_REQUIRED"),
    ("semantic_owner_bound", "SEMANTIC_OWNER_REQUIRED"),
    ("dependency_closure", "DEPENDENCY_CLOSURE_REQUIRED"),
    ("authority_nonexpanding", "AUTHORITY_EXPANSION_DENIED"),
    ("effect_state_reconciled", "UNRECONCILED_EFFECT_DENIED"),
    ("collision_free", "COLLISION_OR_COMPETING_WRITER"),
    ("bounded_scope", "UNBOUNDED_SCOPE_DENIED"),
    ("evidence_bound", "EVIDENCE_BINDING_REQUIRED"),
    ("owner_resolved", "IMPLEMENTATION_OWNER_REQUIRED"),
)

DEFAULT_BENEFIT_WEIGHTS: Tuple[tuple[str, int], ...] = (
    ("capability_gain", 6),
    ("federation_leverage", 4),
    ("functional_value", 5),
    ("generativity_gain", 7),
    ("integration_closure", 6),
    ("knowledge_feedback", 3),
    ("recovery_strength", 4),
    ("reuse_leverage", 4),
    ("verification_strength", 4),
)
DEFAULT_COST_WEIGHTS: Tuple[tuple[str, int], ...] = (
    ("authority_risk", 8),
    ("blast_radius", 6),
    ("change_surface", 3),
    ("currentness_debt", 5),
    ("implementation_cost", 3),
    ("operational_cost", 2),
)


class EvolutionFitnessError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _scaled(value: int, name: str) -> int:
    if type(value) is not int or not 0 <= value <= _SCALE:
        raise EvolutionFitnessError(f"{name} must be integer 0..{_SCALE}")
    return value


def _sorted_unique(values: Tuple[str, ...], name: str, *, required: bool = True) -> Tuple[str, ...]:
    if type(values) is not tuple or (required and not values):
        raise EvolutionFitnessError(f"{name} must be {'non-empty ' if required else ''}tuple")
    for value in values:
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise EvolutionFitnessError(f"{name} invalid")
    if values != tuple(sorted(set(values))):
        raise EvolutionFitnessError(f"{name} must be sorted unique")
    return values


@dataclass(frozen=True, order=True)
class EvolutionFitnessVector:
    capability_gain: int
    federation_leverage: int
    functional_value: int
    generativity_gain: int
    integration_closure: int
    knowledge_feedback: int
    recovery_strength: int
    reuse_leverage: int
    verification_strength: int
    authority_risk: int
    blast_radius: int
    change_surface: int
    currentness_debt: int
    implementation_cost: int
    operational_cost: int

    def validate(self) -> "EvolutionFitnessVector":
        for name in BENEFIT_DIMENSIONS + COST_DIMENSIONS:
            _scaled(getattr(self, name), name)
        return self

    def benefits(self) -> dict[str, int]:
        self.validate()
        return {name: getattr(self, name) for name in BENEFIT_DIMENSIONS}

    def costs(self) -> dict[str, int]:
        self.validate()
        return {name: getattr(self, name) for name in COST_DIMENSIONS}

    def digest(self) -> str:
        self.validate()
        return sha256(_DOMAIN_VECTOR + _canonical_bytes(asdict(self))).hexdigest()


@dataclass(frozen=True)
class EvolutionGateState:
    source_current: bool
    semantic_owner_bound: bool
    dependency_closure: bool
    authority_nonexpanding: bool
    effect_state_reconciled: bool
    collision_free: bool
    bounded_scope: bool
    evidence_bound: bool
    owner_resolved: bool

    def validate(self) -> "EvolutionGateState":
        for field_name, _ in HARD_GATE_FIELDS:
            if type(getattr(self, field_name)) is not bool:
                raise EvolutionFitnessError(f"{field_name} must be bool")
        return self

    def blockers(self) -> Tuple[str, ...]:
        self.validate()
        return tuple(code for field_name, code in HARD_GATE_FIELDS if not getattr(self, field_name))


@dataclass(frozen=True, order=True)
class EvolutionPressure:
    dimension: str
    value: int
    evidence_ref: str

    def validate(self) -> "EvolutionPressure":
        if self.dimension not in ALL_DIMENSIONS:
            raise EvolutionFitnessError("unknown pressure dimension")
        _scaled(self.value, "pressure")
        if not isinstance(self.evidence_ref, str) or not self.evidence_ref.strip() or "\x00" in self.evidence_ref:
            raise EvolutionFitnessError("pressure evidence_ref invalid")
        return self


@dataclass(frozen=True)
class EvolutionFitnessPolicy:
    benefit_weights: Tuple[tuple[str, int], ...] = DEFAULT_BENEFIT_WEIGHTS
    cost_weights: Tuple[tuple[str, int], ...] = DEFAULT_COST_WEIGHTS
    critical_path_wip_limit: int = 1
    max_pressure: int = _SCALE
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"

    def validate(self) -> "EvolutionFitnessPolicy":
        if tuple(name for name, _ in self.benefit_weights) != BENEFIT_DIMENSIONS:
            raise EvolutionFitnessError("benefit weights must cover canonical dimensions in order")
        if tuple(name for name, _ in self.cost_weights) != COST_DIMENSIONS:
            raise EvolutionFitnessError("cost weights must cover canonical dimensions in order")
        for _, weight in self.benefit_weights + self.cost_weights:
            if type(weight) is not int or not 1 <= weight <= 100:
                raise EvolutionFitnessError("weights must be integer 1..100")
        if self.critical_path_wip_limit != 1:
            raise EvolutionFitnessError("R1 critical path WIP limit must remain 1")
        if self.max_pressure != _SCALE:
            raise EvolutionFitnessError("R1 pressure scale mismatch")
        if self.authority_effect != "NONE" or self.execution_effect != "NONE":
            raise EvolutionFitnessError("fitness policy cannot carry authority/effect")
        return self


DEFAULT_POLICY = EvolutionFitnessPolicy().validate()


@dataclass(frozen=True)
class EvolutionFitnessCandidate:
    candidate_id: str
    vector: EvolutionFitnessVector
    gates: EvolutionGateState
    evidence_refs: Tuple[str, ...]
    repository_scope: Tuple[str, ...]
    task_family_count: int
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"

    def validate(self) -> "EvolutionFitnessCandidate":
        if not isinstance(self.candidate_id, str) or not _SAFE_ID.fullmatch(self.candidate_id):
            raise EvolutionFitnessError("candidate_id invalid")
        self.vector.validate()
        self.gates.validate()
        _sorted_unique(self.evidence_refs, "evidence_refs")
        _sorted_unique(self.repository_scope, "repository_scope")
        if type(self.task_family_count) is not int or self.task_family_count < 1:
            raise EvolutionFitnessError("task_family_count must be positive integer")
        if self.authority_effect != "NONE" or self.execution_effect != "NONE":
            raise EvolutionFitnessError("fitness candidate is a proposal projection, not authority/effect")
        return self


@dataclass(frozen=True)
class EvolutionFitnessAssessment:
    candidate_id: str
    eligible: bool
    blockers: Tuple[str, ...]
    benefit_score: int
    cost_score: int
    utility_score: int
    vector_digest: str
    pressure_digest: str
    assessment_digest: str
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"


@dataclass(frozen=True)
class EvolutionFitnessSelection:
    selected_candidate_id: str
    pareto_frontier: Tuple[str, ...]
    eligible_candidates: Tuple[str, ...]
    assessments: Tuple[EvolutionFitnessAssessment, ...]
    selection_digest: str
    critical_path_wip_limit: int = 1
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"


class EvolutionFitnessOptimizer:
    @classmethod
    def assert_no_effect_surface(cls) -> None:
        for name in _EFFECT_METHOD_NAMES:
            if hasattr(cls, name):
                raise EvolutionFitnessError(f"effect surface present: {name}")

    @staticmethod
    def _pressure_map(pressures: Tuple[EvolutionPressure, ...]) -> dict[str, int]:
        if type(pressures) is not tuple:
            raise EvolutionFitnessError("pressures must be tuple")
        validated = tuple(p.validate() for p in pressures)
        dimensions = tuple(p.dimension for p in validated)
        if dimensions != tuple(sorted(set(dimensions))):
            raise EvolutionFitnessError("pressures must be sorted unique by dimension")
        return {p.dimension: p.value for p in validated}

    @staticmethod
    def _pressure_digest(pressures: Tuple[EvolutionPressure, ...]) -> str:
        payload = [asdict(p.validate()) for p in pressures]
        return sha256(b"LION/EVOLUTION-PRESSURE/1\0" + _canonical_bytes(payload)).hexdigest()

    @staticmethod
    def _weighted(value: int, weight: int, pressure: int) -> int:
        return value * weight * (_SCALE + pressure) // _SCALE

    def assess(
        self,
        candidate: EvolutionFitnessCandidate,
        *,
        pressures: Tuple[EvolutionPressure, ...] = (),
        policy: EvolutionFitnessPolicy = DEFAULT_POLICY,
    ) -> EvolutionFitnessAssessment:
        self.assert_no_effect_surface()
        candidate.validate()
        policy.validate()
        pressure_map = self._pressure_map(pressures)
        benefits = candidate.vector.benefits()
        costs = candidate.vector.costs()
        benefit_score = sum(
            self._weighted(benefits[name], weight, pressure_map.get(name, 0))
            for name, weight in policy.benefit_weights
        )
        cost_score = sum(
            self._weighted(costs[name], weight, pressure_map.get(name, 0))
            for name, weight in policy.cost_weights
        )
        blockers = candidate.gates.blockers()
        eligible = not blockers
        utility_score = benefit_score - cost_score
        vector_digest = candidate.vector.digest()
        pressure_digest = self._pressure_digest(pressures)
        payload = {
            "candidate_id": candidate.candidate_id,
            "eligible": eligible,
            "blockers": blockers,
            "benefit_score": benefit_score,
            "cost_score": cost_score,
            "utility_score": utility_score,
            "vector_digest": vector_digest,
            "pressure_digest": pressure_digest,
            "task_family_count": candidate.task_family_count,
            "repository_scope": candidate.repository_scope,
            "evidence_refs": candidate.evidence_refs,
            "authority_effect": "NONE",
            "execution_effect": "NONE",
        }
        digest = sha256(_DOMAIN_ASSESSMENT + _canonical_bytes(payload)).hexdigest()
        return EvolutionFitnessAssessment(
            candidate_id=candidate.candidate_id,
            eligible=eligible,
            blockers=blockers,
            benefit_score=benefit_score,
            cost_score=cost_score,
            utility_score=utility_score,
            vector_digest=vector_digest,
            pressure_digest=pressure_digest,
            assessment_digest=digest,
        )

    @staticmethod
    def _dominates(left: EvolutionFitnessCandidate, right: EvolutionFitnessCandidate) -> bool:
        lb, rb = left.vector.benefits(), right.vector.benefits()
        lc, rc = left.vector.costs(), right.vector.costs()
        weak = all(lb[k] >= rb[k] for k in BENEFIT_DIMENSIONS) and all(
            lc[k] <= rc[k] for k in COST_DIMENSIONS
        )
        strict = any(lb[k] > rb[k] for k in BENEFIT_DIMENSIONS) or any(
            lc[k] < rc[k] for k in COST_DIMENSIONS
        )
        return weak and strict

    def select(
        self,
        candidates: Tuple[EvolutionFitnessCandidate, ...],
        *,
        pressures: Tuple[EvolutionPressure, ...] = (),
        policy: EvolutionFitnessPolicy = DEFAULT_POLICY,
    ) -> EvolutionFitnessSelection:
        self.assert_no_effect_surface()
        policy.validate()
        if type(candidates) is not tuple or not candidates:
            raise EvolutionFitnessError("candidates must be non-empty tuple")
        validated = tuple(candidate.validate() for candidate in candidates)
        ids = tuple(candidate.candidate_id for candidate in validated)
        if ids != tuple(sorted(set(ids))):
            raise EvolutionFitnessError("candidates must be sorted unique by candidate_id")
        assessments = tuple(
            self.assess(candidate, pressures=pressures, policy=policy) for candidate in validated
        )
        assessment_by_id = {a.candidate_id: a for a in assessments}
        eligible = tuple(c for c in validated if assessment_by_id[c.candidate_id].eligible)
        if not eligible:
            raise EvolutionFitnessError("no eligible evolution candidate")
        frontier = tuple(
            candidate
            for candidate in eligible
            if not any(
                other.candidate_id != candidate.candidate_id and self._dominates(other, candidate)
                for other in eligible
            )
        )
        selected = sorted(
            frontier,
            key=lambda c: (-assessment_by_id[c.candidate_id].utility_score, c.candidate_id),
        )[0]
        frontier_ids = tuple(sorted(c.candidate_id for c in frontier))
        eligible_ids = tuple(sorted(c.candidate_id for c in eligible))
        payload = {
            "selected_candidate_id": selected.candidate_id,
            "pareto_frontier": frontier_ids,
            "eligible_candidates": eligible_ids,
            "assessment_digests": tuple(
                assessment_by_id[candidate_id].assessment_digest for candidate_id in eligible_ids
            ),
            "critical_path_wip_limit": policy.critical_path_wip_limit,
            "authority_effect": "NONE",
            "execution_effect": "NONE",
        }
        selection_digest = sha256(_DOMAIN_SELECTION + _canonical_bytes(payload)).hexdigest()
        return EvolutionFitnessSelection(
            selected_candidate_id=selected.candidate_id,
            pareto_frontier=frontier_ids,
            eligible_candidates=eligible_ids,
            assessments=tuple(sorted(assessments, key=lambda item: item.candidate_id)),
            selection_digest=selection_digest,
            critical_path_wip_limit=policy.critical_path_wip_limit,
        )

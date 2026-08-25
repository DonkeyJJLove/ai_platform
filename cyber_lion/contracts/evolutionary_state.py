"""Canonical WORLD / SYSTEM / GOAL state contracts for governed evolution.

This module is deliberately non-effectful.  It provides immutable, digest-bound
objects used to derive an explicit Gap.  None of the contracts carries execution
credentials, grants, authority effects, or repository/external effects.

The core epistemic rule is fail-closed preservation of uncertainty: UNKNOWN is a
legal state and cannot be promoted merely because a caller is confident.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Tuple


class EvolutionaryStateError(ValueError):
    """Raised when a canonical evolutionary-state invariant is violated."""


EPISTEMIC_STATES = {"CURRENT", "STALE", "UNKNOWN", "CONFLICTED"}


def _required_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise EvolutionaryStateError(f"{name} is required")


def _unique(name: str, values: Tuple[str, ...]) -> None:
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise EvolutionaryStateError(f"{name} entries must be non-empty strings")
    if len(set(values)) != len(values):
        raise EvolutionaryStateError(f"{name} entries must be unique")


def _state(value: str) -> None:
    if value not in EPISTEMIC_STATES:
        raise EvolutionaryStateError(f"invalid epistemic state: {value}")


def _canonical(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {str(key): _canonical(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value


def _digest(domain: bytes, payload: Any) -> str:
    encoded = json.dumps(_canonical(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(domain + b"\0" + encoded).hexdigest()


@dataclass(frozen=True)
class GoalContract:
    """Immutable root/sub-goal declaration; a goal never grants authority."""

    goal_id: str
    revision: int
    objective: str
    constraints: Tuple[str, ...]
    success_conditions: Tuple[str, ...]
    stop_conditions: Tuple[str, ...]
    defer_conditions: Tuple[str, ...] = ()
    authority_ceiling: str = "none"
    source_ref: str = ""
    parent_goal_digest: str = ""

    def validate(self) -> "GoalContract":
        _required_text("goal_id", self.goal_id)
        _required_text("objective", self.objective)
        _required_text("source_ref", self.source_ref)
        if self.revision <= 0:
            raise EvolutionaryStateError("revision must be positive")
        _unique("constraints", self.constraints)
        _unique("success_conditions", self.success_conditions)
        _unique("stop_conditions", self.stop_conditions)
        _unique("defer_conditions", self.defer_conditions)
        if not self.success_conditions:
            raise EvolutionaryStateError("goal requires at least one success condition")
        if not self.stop_conditions:
            raise EvolutionaryStateError("goal requires at least one stop condition")
        if self.revision > 1 and len(self.parent_goal_digest) != 64:
            raise EvolutionaryStateError("goal revision > 1 requires exact parent_goal_digest")
        if self.revision == 1 and self.parent_goal_digest:
            raise EvolutionaryStateError("root goal revision must not invent a parent digest")
        return self

    def digest(self) -> str:
        self.validate()
        return _digest(b"LION/GOAL-CONTRACT/1", self)


@dataclass(frozen=True)
class WorldSnapshot:
    """Source-bound observation of external state at a declared observation time."""

    snapshot_id: str
    observed_at: str
    captured_at: str
    epistemic_state: str
    observations: Tuple[Tuple[str, str], ...]
    source_refs: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    freshness_deadline: str = ""
    limitations: Tuple[str, ...] = ()
    contradictions: Tuple[str, ...] = ()

    def validate(self) -> "WorldSnapshot":
        _required_text("snapshot_id", self.snapshot_id)
        _required_text("observed_at", self.observed_at)
        _required_text("captured_at", self.captured_at)
        _state(self.epistemic_state)
        if not self.observations:
            raise EvolutionaryStateError("world snapshot requires observations")
        keys = tuple(key for key, _ in self.observations)
        _unique("observation keys", keys)
        if any(not value.strip() for _, value in self.observations):
            raise EvolutionaryStateError("world observation values must be non-empty")
        _unique("source_refs", self.source_refs)
        _unique("evidence_refs", self.evidence_refs)
        _unique("limitations", self.limitations)
        _unique("contradictions", self.contradictions)
        if not self.source_refs or not self.evidence_refs:
            raise EvolutionaryStateError("world snapshot requires source and evidence provenance")
        if self.epistemic_state == "CURRENT" and not self.freshness_deadline:
            raise EvolutionaryStateError("CURRENT world snapshot requires freshness_deadline")
        if self.epistemic_state == "CONFLICTED" and not self.contradictions:
            raise EvolutionaryStateError("CONFLICTED world snapshot requires contradictions")
        return self

    def digest(self) -> str:
        self.validate()
        return _digest(b"LION/WORLD-SNAPSHOT/1", self)


@dataclass(frozen=True)
class SystemSnapshot:
    """Exact observation of the implementation/runtime state LION is reasoning about."""

    snapshot_id: str
    observed_at: str
    captured_at: str
    epistemic_state: str
    repository: str
    revision: str
    tree_digest: str
    implementation_facts: Tuple[Tuple[str, str], ...]
    test_evidence_refs: Tuple[str, ...]
    observation_refs: Tuple[str, ...]
    freshness_deadline: str = ""
    unknowns: Tuple[str, ...] = ()
    contradictions: Tuple[str, ...] = ()

    def validate(self) -> "SystemSnapshot":
        _required_text("snapshot_id", self.snapshot_id)
        _required_text("observed_at", self.observed_at)
        _required_text("captured_at", self.captured_at)
        _required_text("repository", self.repository)
        _required_text("revision", self.revision)
        _required_text("tree_digest", self.tree_digest)
        _state(self.epistemic_state)
        facts = tuple(key for key, _ in self.implementation_facts)
        _unique("implementation fact keys", facts)
        if any(not value.strip() for _, value in self.implementation_facts):
            raise EvolutionaryStateError("implementation fact values must be non-empty")
        _unique("test_evidence_refs", self.test_evidence_refs)
        _unique("observation_refs", self.observation_refs)
        _unique("unknowns", self.unknowns)
        _unique("contradictions", self.contradictions)
        if not self.observation_refs:
            raise EvolutionaryStateError("system snapshot requires independent observation references")
        if self.epistemic_state == "CURRENT" and not self.freshness_deadline:
            raise EvolutionaryStateError("CURRENT system snapshot requires freshness_deadline")
        if self.epistemic_state == "UNKNOWN" and not self.unknowns:
            raise EvolutionaryStateError("UNKNOWN system snapshot must name unresolved unknowns")
        if self.epistemic_state == "CONFLICTED" and not self.contradictions:
            raise EvolutionaryStateError("CONFLICTED system snapshot requires contradictions")
        return self

    def digest(self) -> str:
        self.validate()
        return _digest(b"LION/SYSTEM-SNAPSHOT/1", self)


@dataclass(frozen=True)
class Gap:
    """Exact WORLD/SYSTEM/GOAL difference; descriptive only, never a solution grant."""

    gap_id: str
    goal_digest: str
    world_snapshot_digest: str
    system_snapshot_digest: str
    epistemic_state: str
    missing_capabilities: Tuple[str, ...]
    unsatisfied_conditions: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    falsification_conditions: Tuple[str, ...]
    substitution_guard: str
    unknowns: Tuple[str, ...] = ()

    def validate(self) -> "Gap":
        _required_text("gap_id", self.gap_id)
        _state(self.epistemic_state)
        for name, value in (
            ("goal_digest", self.goal_digest),
            ("world_snapshot_digest", self.world_snapshot_digest),
            ("system_snapshot_digest", self.system_snapshot_digest),
        ):
            if len(value) != 64:
                raise EvolutionaryStateError(f"{name} must be an exact 64-character digest")
        _unique("missing_capabilities", self.missing_capabilities)
        _unique("unsatisfied_conditions", self.unsatisfied_conditions)
        _unique("evidence_refs", self.evidence_refs)
        _unique("falsification_conditions", self.falsification_conditions)
        _unique("unknowns", self.unknowns)
        _required_text("substitution_guard", self.substitution_guard)
        if not self.unsatisfied_conditions and not self.missing_capabilities and not self.unknowns:
            raise EvolutionaryStateError("gap must contain an explicit difference or unknown")
        if not self.evidence_refs:
            raise EvolutionaryStateError("gap requires evidence_refs")
        if not self.falsification_conditions:
            raise EvolutionaryStateError("gap requires falsification_conditions")
        if self.epistemic_state == "UNKNOWN" and not self.unknowns:
            raise EvolutionaryStateError("UNKNOWN gap must preserve unresolved unknowns")
        return self

    def digest(self) -> str:
        self.validate()
        return _digest(b"LION/GAP/1", self)


def derive_gap(
    *,
    gap_id: str,
    goal: GoalContract,
    world: WorldSnapshot,
    system: SystemSnapshot,
    missing_capabilities: Tuple[str, ...],
    unsatisfied_conditions: Tuple[str, ...],
    evidence_refs: Tuple[str, ...],
    falsification_conditions: Tuple[str, ...],
    unknowns: Tuple[str, ...] = (),
) -> Gap:
    """Derive a gap while preserving uncertainty from upstream snapshots.

    The function intentionally does not select a solution.  The substitution guard binds
    the exact three input digests so a caller cannot silently replace world/system/goal
    state after deriving the gap.
    """

    goal.validate()
    world.validate()
    system.validate()
    input_states = {world.epistemic_state, system.epistemic_state}
    preserved_unknowns = list(unknowns)
    if world.epistemic_state == "UNKNOWN":
        preserved_unknowns.append(f"world:{world.snapshot_id}")
    if system.epistemic_state == "UNKNOWN":
        preserved_unknowns.extend(f"system:{item}" for item in system.unknowns)

    if "CONFLICTED" in input_states:
        state = "CONFLICTED"
    elif "UNKNOWN" in input_states or preserved_unknowns:
        state = "UNKNOWN"
    elif "STALE" in input_states:
        state = "STALE"
    else:
        state = "CURRENT"

    binding = {
        "goal": goal.digest(),
        "world": world.digest(),
        "system": system.digest(),
    }
    guard = _digest(b"LION/GAP-SUBSTITUTION-GUARD/1", binding)
    return Gap(
        gap_id=gap_id,
        goal_digest=binding["goal"],
        world_snapshot_digest=binding["world"],
        system_snapshot_digest=binding["system"],
        epistemic_state=state,
        missing_capabilities=missing_capabilities,
        unsatisfied_conditions=unsatisfied_conditions,
        evidence_refs=evidence_refs,
        falsification_conditions=falsification_conditions,
        substitution_guard=guard,
        unknowns=tuple(dict.fromkeys(preserved_unknowns)),
    ).validate()


def assert_exact_gap_binding(*, gap: Gap, goal: GoalContract, world: WorldSnapshot, system: SystemSnapshot) -> None:
    """Reject stable-ID/payload substitution between derivation and use."""

    expected = {
        "goal": goal.digest(),
        "world": world.digest(),
        "system": system.digest(),
    }
    if gap.goal_digest != expected["goal"]:
        raise EvolutionaryStateError("goal substitution detected")
    if gap.world_snapshot_digest != expected["world"]:
        raise EvolutionaryStateError("world snapshot substitution detected")
    if gap.system_snapshot_digest != expected["system"]:
        raise EvolutionaryStateError("system snapshot substitution detected")
    expected_guard = _digest(b"LION/GAP-SUBSTITUTION-GUARD/1", expected)
    if gap.substitution_guard != expected_guard:
        raise EvolutionaryStateError("gap substitution guard mismatch")

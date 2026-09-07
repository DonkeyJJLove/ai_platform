"""Canonical, deterministic and non-effectful LION Process IR.

The process layer describes legal process-state transitions. It never grants
authority, evaluates the PDP, constructs runtime admission, selects an effect
provider, or executes an effect.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping

SCHEMA_ID = "cyberlion://schemas/process-ir/v1"
SCHEMA_VERSION = "1.0.0"
DIGEST_DOMAIN = b"LION/PROCESS-IR/1\0"

TRANSITION_CLASSES = frozenset({"INTERNAL", "ACTION_REQUIRED"})
OPERATORS = frozenset({
    "OBSERVE", "REACQUIRE", "ASSERT", "REQUIRE", "PROHIBIT",
    "DERIVE", "PREPARE", "VERIFY", "FALSIFY",
    "REQUEST_AUTHORITY_CONTEXT", "VERIFY_AUTHORITY_CONTEXT",
    "EMIT_ACTION_INTENT", "READBACK", "RECONCILE",
    "DEGRADE", "SUPERSEDE", "DEFER", "CONTINUE", "HANDOFF", "STOP",
})
OUTCOME_LABELS = frozenset({
    "PASS", "FAIL", "UNKNOWN", "DRIFT", "BLOCKED",
    "AUTHORITY_BOUNDARY", "COMPLETE",
})
NEXT_DIRECTIVES = frozenset({"CONTINUE", "DEFER", "HANDOFF", "STOP", "COMPLETE"})
REPLAY_POLICIES = frozenset({"DENY", "IDEMPOTENT", "RECONCILE_FIRST"})
IDEMPOTENCY_CLASSES = frozenset({"PURE", "IDEMPOTENT", "NON_IDEMPOTENT"})
SCHEDULING_STRATEGIES = frozenset({"DECLARED_ORDER", "EXPLICIT_PRIORITY"})

_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:/-]{0,255}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_ROOT_FIELDS = frozenset({
    "schema_version", "process_id", "mission_ref", "goal_ref", "scope",
    "initial_state", "states", "dependencies", "transitions",
    "scheduling_policy", "termination_policy", "lineage",
})
_TRANSITION_FIELDS = frozenset({
    "transition_id", "transition_class", "source_states", "trigger",
    "dependencies", "guards", "evidence_requirements",
    "currentness_requirements", "authority_requirements", "operator",
    "expected_postconditions", "outcome_map", "retry_policy",
    "replay_policy", "idempotency_class", "resource_claims",
})


class ProcessIRContractError(ValueError):
    pass


def _reject_constant(value: str) -> None:
    raise ProcessIRContractError(f"non-RFC8259 constant is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProcessIRContractError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _parse_json(raw: bytes | str) -> Mapping[str, Any]:
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise ProcessIRContractError("Process IR JSON must be UTF-8") from exc
    if type(raw) is not str:
        raise ProcessIRContractError("Process IR JSON must be bytes or str")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except ProcessIRContractError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ProcessIRContractError("Process IR JSON is invalid") from exc
    if type(value) is not dict:
        raise ProcessIRContractError("Process IR root must be an object")
    return value


def _exact_object(value: Any, expected: set[str] | frozenset[str], name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ProcessIRContractError(f"{name} must be an object")
    if set(value) != set(expected):
        raise ProcessIRContractError(f"{name} keys are not canonical")
    return value


def _text(value: Any, name: str, *, allow_empty: bool = False, maximum: int = 4096) -> str:
    if type(value) is not str or len(value) > maximum or "\x00" in value:
        raise ProcessIRContractError(f"{name} must be a bounded string")
    if not allow_empty and not value:
        raise ProcessIRContractError(f"{name} must not be empty")
    return value


def _id(value: Any, name: str) -> str:
    value = _text(value, name, maximum=256)
    if _ID.fullmatch(value) is None:
        raise ProcessIRContractError(f"{name} has invalid identifier syntax")
    return value


def _unique_strings(value: Any, name: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if type(value) is not list:
        raise ProcessIRContractError(f"{name} must be an array")
    result = tuple(_text(item, name) for item in value)
    if not allow_empty and not result:
        raise ProcessIRContractError(f"{name} must not be empty")
    if len(result) != len(set(result)):
        raise ProcessIRContractError(f"{name} must contain unique values")
    return result


def _states(value: Any) -> tuple[str, ...]:
    states = _unique_strings(value, "states", allow_empty=False)
    for state in states:
        _id(state, "state")
    return states


def _scope(value: Any) -> dict[str, Any]:
    value = _exact_object(value, {"domains", "resources", "widening_allowed"}, "scope")
    _unique_strings(value["domains"], "scope.domains", allow_empty=False)
    _unique_strings(value["resources"], "scope.resources")
    if value["widening_allowed"] is not False:
        raise ProcessIRContractError("scope.widening_allowed must be false")
    return value


def _dependencies(value: Any) -> tuple[dict[str, Any], ...]:
    if type(value) is not list:
        raise ProcessIRContractError("dependencies must be an array")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        item = _exact_object(item, {"dependency_id", "required", "description"}, "dependency")
        dep_id = _id(item["dependency_id"], "dependency.dependency_id")
        if dep_id in seen:
            raise ProcessIRContractError("duplicate dependency_id")
        seen.add(dep_id)
        if type(item["required"]) is not bool:
            raise ProcessIRContractError("dependency.required must be boolean")
        _text(item["description"], "dependency.description")
        result.append(item)
    return tuple(result)


def _retry_policy(value: Any) -> dict[str, Any]:
    value = _exact_object(value, {"max_attempts", "on_exhausted"}, "retry_policy")
    if type(value["max_attempts"]) is not int or isinstance(value["max_attempts"], bool):
        raise ProcessIRContractError("retry_policy.max_attempts must be integer")
    if value["max_attempts"] < 0 or value["max_attempts"] > 100:
        raise ProcessIRContractError("retry_policy.max_attempts out of range")
    if value["on_exhausted"] not in {"BLOCKED", "HANDOFF", "STOP", "UNKNOWN"}:
        raise ProcessIRContractError("retry_policy.on_exhausted invalid")
    return value


def _resource_claims(value: Any) -> dict[str, Any]:
    value = _exact_object(value, {"read_scopes", "write_scopes", "authority_budgets", "currentness_subjects", "replay_domain", "reconciliation_group"}, "resource_claims")
    for key in ("read_scopes", "write_scopes", "authority_budgets", "currentness_subjects"):
        _unique_strings(value[key], f"resource_claims.{key}")
    _text(value["replay_domain"], "resource_claims.replay_domain", allow_empty=True)
    _text(value["reconciliation_group"], "resource_claims.reconciliation_group", allow_empty=True)
    return value


def _transition(value: Any, *, state_set: set[str], dependency_set: set[str]) -> dict[str, Any]:
    value = _exact_object(value, _TRANSITION_FIELDS, "transition")
    _id(value["transition_id"], "transition.transition_id")
    if value["transition_class"] not in TRANSITION_CLASSES:
        raise ProcessIRContractError("transition.transition_class invalid")
    sources = _unique_strings(value["source_states"], "transition.source_states", allow_empty=False)
    if not set(sources) <= state_set:
        raise ProcessIRContractError("transition references undefined source state")
    _text(value["trigger"], "transition.trigger")
    deps = _unique_strings(value["dependencies"], "transition.dependencies")
    if not set(deps) <= dependency_set:
        raise ProcessIRContractError("transition references undefined dependency")
    _unique_strings(value["guards"], "transition.guards")
    evidence = _unique_strings(value["evidence_requirements"], "transition.evidence_requirements")
    currentness = _unique_strings(value["currentness_requirements"], "transition.currentness_requirements")
    authority = _unique_strings(value["authority_requirements"], "transition.authority_requirements")
    operator = value["operator"]
    if operator not in OPERATORS:
        raise ProcessIRContractError("transition.operator invalid")
    _unique_strings(value["expected_postconditions"], "transition.expected_postconditions")
    outcome_map = value["outcome_map"]
    if type(outcome_map) is not dict or not outcome_map:
        raise ProcessIRContractError("transition.outcome_map must be a non-empty object")
    for outcome, target in outcome_map.items():
        if outcome not in OUTCOME_LABELS:
            raise ProcessIRContractError("transition.outcome_map has unknown outcome")
        _text(target, "transition.outcome_map target")
        if target not in state_set and target not in NEXT_DIRECTIVES:
            raise ProcessIRContractError("transition.outcome_map target invalid")
    retry = _retry_policy(value["retry_policy"])
    if value["replay_policy"] not in REPLAY_POLICIES:
        raise ProcessIRContractError("transition.replay_policy invalid")
    if value["idempotency_class"] not in IDEMPOTENCY_CLASSES:
        raise ProcessIRContractError("transition.idempotency_class invalid")
    _resource_claims(value["resource_claims"])
    if value["transition_class"] == "ACTION_REQUIRED":
        if operator != "EMIT_ACTION_INTENT":
            raise ProcessIRContractError("ACTION_REQUIRED transition must use EMIT_ACTION_INTENT")
        if not evidence or not currentness or not authority:
            raise ProcessIRContractError("ACTION_REQUIRED transition requires evidence, currentness and authority requirements")
    elif operator == "EMIT_ACTION_INTENT":
        raise ProcessIRContractError("INTERNAL transition cannot emit ActionIntent")
    if value["idempotency_class"] == "NON_IDEMPOTENT" and retry["max_attempts"] > 0 and value["replay_policy"] != "RECONCILE_FIRST":
        raise ProcessIRContractError("non-idempotent retry requires RECONCILE_FIRST replay policy")
    return value


def _scheduling(value: Any, transition_ids: set[str]) -> dict[str, Any]:
    value = _exact_object(value, {"strategy", "order", "priorities", "max_wip", "parallel_safe_groups"}, "scheduling_policy")
    if value["strategy"] not in SCHEDULING_STRATEGIES:
        raise ProcessIRContractError("scheduling_policy.strategy invalid")
    order = _unique_strings(value["order"], "scheduling_policy.order", allow_empty=False)
    if set(order) != transition_ids or len(order) != len(transition_ids):
        raise ProcessIRContractError("scheduling_policy.order must contain every transition exactly once")
    priorities = value["priorities"]
    if type(priorities) is not dict or set(priorities) != transition_ids:
        raise ProcessIRContractError("scheduling_policy.priorities must cover all transitions")
    for key, priority in priorities.items():
        _id(key, "scheduling_policy.priorities key")
        if type(priority) is not int or isinstance(priority, bool) or priority < 0:
            raise ProcessIRContractError("scheduling priority invalid")
    max_wip = value["max_wip"]
    if type(max_wip) is not int or isinstance(max_wip, bool) or not 1 <= max_wip <= 128:
        raise ProcessIRContractError("scheduling_policy.max_wip invalid")
    groups = value["parallel_safe_groups"]
    if type(groups) is not list:
        raise ProcessIRContractError("parallel_safe_groups must be an array")
    for group in groups:
        items = _unique_strings(group, "parallel_safe_group", allow_empty=False)
        if len(items) < 2 or not set(items) <= transition_ids:
            raise ProcessIRContractError("parallel safe group invalid")
    return value


def _termination(value: Any, state_set: set[str]) -> dict[str, Any]:
    value = _exact_object(value, {"terminal_states", "allow_no_legal_transition", "on_unknown"}, "termination_policy")
    terminal = _unique_strings(value["terminal_states"], "termination_policy.terminal_states", allow_empty=False)
    if not set(terminal) <= state_set:
        raise ProcessIRContractError("termination_policy references undefined terminal state")
    if type(value["allow_no_legal_transition"]) is not bool:
        raise ProcessIRContractError("allow_no_legal_transition must be boolean")
    if value["on_unknown"] not in {"HANDOFF", "STOP", "DEFER"}:
        raise ProcessIRContractError("termination_policy.on_unknown invalid")
    return value


def _lineage(value: Any) -> dict[str, Any]:
    value = _exact_object(value, {"parent_process_digests", "generation", "source_refs"}, "lineage")
    parents = _unique_strings(value["parent_process_digests"], "lineage.parent_process_digests")
    for parent in parents:
        if _SHA256.fullmatch(parent) is None:
            raise ProcessIRContractError("parent process digest invalid")
    if type(value["generation"]) is not int or isinstance(value["generation"], bool) or value["generation"] < 0:
        raise ProcessIRContractError("lineage.generation invalid")
    _unique_strings(value["source_refs"], "lineage.source_refs")
    return value


def validate_process_ir(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise ProcessIRContractError("Process IR must be an object")
    value = _exact_object(value, _ROOT_FIELDS, "ProcessIR")
    if value["schema_version"] != SCHEMA_VERSION:
        raise ProcessIRContractError("schema_version mismatch")
    _id(value["process_id"], "process_id")
    _text(value["mission_ref"], "mission_ref")
    _text(value["goal_ref"], "goal_ref")
    _scope(value["scope"])
    states = _states(value["states"])
    state_set = set(states)
    if value["initial_state"] not in state_set:
        raise ProcessIRContractError("initial_state is undefined")
    dependencies = _dependencies(value["dependencies"])
    dependency_set = {item["dependency_id"] for item in dependencies}
    transitions_raw = value["transitions"]
    if type(transitions_raw) is not list or not transitions_raw:
        raise ProcessIRContractError("transitions must be a non-empty array")
    transition_ids: set[str] = set()
    for transition in transitions_raw:
        checked = _transition(transition, state_set=state_set, dependency_set=dependency_set)
        tid = checked["transition_id"]
        if tid in transition_ids:
            raise ProcessIRContractError("duplicate transition_id")
        transition_ids.add(tid)
    _scheduling(value["scheduling_policy"], transition_ids)
    _termination(value["termination_policy"], state_set)
    _lineage(value["lineage"])
    return value


def canonical_process_ir_bytes(value: Mapping[str, Any]) -> bytes:
    validate_process_ir(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def process_ir_digest(value: Mapping[str, Any]) -> str:
    return sha256(DIGEST_DOMAIN + canonical_process_ir_bytes(value)).hexdigest()


@dataclass(frozen=True)
class CanonicalProcessIR:
    canonical_bytes: bytes
    process_digest: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CanonicalProcessIR":
        raw = canonical_process_ir_bytes(value)
        return cls(raw, sha256(DIGEST_DOMAIN + raw).hexdigest()).validate()

    @classmethod
    def from_json(cls, raw: bytes | str) -> "CanonicalProcessIR":
        return cls.from_mapping(_parse_json(raw))

    def validate(self) -> "CanonicalProcessIR":
        if type(self.canonical_bytes) is not bytes:
            raise ProcessIRContractError("canonical_bytes must be bytes")
        value = _parse_json(self.canonical_bytes)
        expected = canonical_process_ir_bytes(value)
        if expected != self.canonical_bytes:
            raise ProcessIRContractError("canonical_bytes are not canonical")
        if type(self.process_digest) is not str or _SHA256.fullmatch(self.process_digest) is None:
            raise ProcessIRContractError("process_digest must be lowercase SHA-256")
        if self.process_digest != sha256(DIGEST_DOMAIN + self.canonical_bytes).hexdigest():
            raise ProcessIRContractError("process_digest mismatch")
        return self

    def as_dict(self) -> dict[str, Any]:
        return dict(_parse_json(self.canonical_bytes))


@dataclass(frozen=True)
class ProcessContextSnapshot:
    """Non-authoritative evaluation input for process transition selection."""
    process_ir_digest: str
    process_state: str
    completed_transitions: tuple[str, ...] = ()
    satisfied_dependencies: tuple[str, ...] = ()
    satisfied_guards: tuple[str, ...] = ()
    satisfied_evidence_requirements: tuple[str, ...] = ()
    satisfied_currentness_requirements: tuple[str, ...] = ()
    verified_authority_context_refs: tuple[str, ...] = ()
    action_result_refs: tuple[str, ...] = ()
    observation_refs: tuple[str, ...] = ()
    reconciliation_refs: tuple[str, ...] = ()
    attempt_counts: tuple[tuple[str, int], ...] = ()
    observed_at: str = ""

    def validate_for(self, process_ir: CanonicalProcessIR) -> "ProcessContextSnapshot":
        process_ir.validate()
        if self.process_ir_digest != process_ir.process_digest:
            raise ProcessIRContractError("process context does not bind Process IR")
        model = process_ir.as_dict()
        if self.process_state not in set(model["states"]):
            raise ProcessIRContractError("process context state is undefined")
        transition_ids = {item["transition_id"] for item in model["transitions"]}
        if not set(self.completed_transitions) <= transition_ids:
            raise ProcessIRContractError("process context references unknown completed transition")
        dependency_ids = {item["dependency_id"] for item in model["dependencies"]}
        if not set(self.satisfied_dependencies) <= dependency_ids:
            raise ProcessIRContractError("process context references unknown dependency")
        seen_attempts: set[str] = set()
        for tid, count in self.attempt_counts:
            if tid not in transition_ids or tid in seen_attempts:
                raise ProcessIRContractError("attempt_counts reference invalid transition")
            if type(count) is not int or isinstance(count, bool) or count < 0:
                raise ProcessIRContractError("attempt count invalid")
            seen_attempts.add(tid)
        if not self.observed_at:
            raise ProcessIRContractError("process context requires observed_at")
        return self

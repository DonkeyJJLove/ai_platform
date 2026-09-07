"""Fail-closed, non-effectful selector for canonical LION Process IR transitions."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from cyber_lion.contracts.process_action import ProcessTransitionOutcome
from cyber_lion.contracts.process_ir import CanonicalProcessIR, ProcessContextSnapshot, ProcessIRContractError

DECISIONS = frozenset({"SELECTED", "BLOCKED", "HANDOFF_REQUIRED", "COMPLETE", "UNKNOWN"})


class ProcessSemanticError(RuntimeError):
    pass


@dataclass(frozen=True)
class TransitionDecision:
    decision: str
    transition_id: str = ""
    reason: str = ""

    def validate(self) -> "TransitionDecision":
        if self.decision not in DECISIONS:
            raise ProcessSemanticError("invalid transition decision")
        if self.decision == "SELECTED" and not self.transition_id:
            raise ProcessSemanticError("SELECTED requires transition_id")
        if self.decision != "SELECTED" and self.transition_id:
            raise ProcessSemanticError("non-selected decision cannot carry transition_id")
        return self


def _attempt_map(context: ProcessContextSnapshot) -> dict[str, int]:
    return dict(context.attempt_counts)


class TransitionSelector:
    """Selects the next legal transition. It cannot execute or grant authority."""
    def __init__(self, process_ir: CanonicalProcessIR) -> None:
        self._ir = process_ir.validate()
        self._model = self._ir.as_dict()
        self._transitions = {item["transition_id"]: item for item in self._model["transitions"]}
        self._order = tuple(self._model["scheduling_policy"]["order"])
        self._priority = dict(self._model["scheduling_policy"]["priorities"])

    def _ordered(self) -> tuple[dict, ...]:
        if self._model["scheduling_policy"]["strategy"] == "EXPLICIT_PRIORITY":
            ids = sorted(self._order, key=lambda tid: (self._priority[tid], self._order.index(tid)))
        else:
            ids = list(self._order)
        return tuple(self._transitions[tid] for tid in ids)

    @staticmethod
    def _missing(required: Iterable[str], satisfied: Iterable[str]) -> set[str]:
        return set(required) - set(satisfied)

    def select(self, context: ProcessContextSnapshot) -> TransitionDecision:
        try:
            context.validate_for(self._ir)
        except ProcessIRContractError as exc:
            raise ProcessSemanticError(str(exc)) from exc
        if context.process_state in set(self._model["termination_policy"]["terminal_states"]):
            return TransitionDecision("COMPLETE", reason="terminal process state").validate()
        attempts = _attempt_map(context)
        blocked_by_dependency = False
        unknown = False
        handoff = False
        for transition in self._ordered():
            tid = transition["transition_id"]
            if tid in context.completed_transitions or context.process_state not in set(transition["source_states"]):
                continue
            if self._missing(transition["dependencies"], context.satisfied_dependencies):
                blocked_by_dependency = True
                continue
            if self._missing(transition["guards"], context.satisfied_guards):
                unknown = True
                continue
            if self._missing(transition["evidence_requirements"], context.satisfied_evidence_requirements):
                unknown = True
                continue
            if self._missing(transition["currentness_requirements"], context.satisfied_currentness_requirements):
                unknown = True
                continue
            if self._missing(transition["authority_requirements"], context.verified_authority_context_refs):
                handoff = True
                continue
            if attempts.get(tid, 0) > transition["retry_policy"]["max_attempts"]:
                blocked_by_dependency = True
                continue
            return TransitionDecision("SELECTED", transition_id=tid, reason="first legal unfinished transition").validate()
        if handoff:
            return TransitionDecision("HANDOFF_REQUIRED", reason="authority context is not independently verified").validate()
        if unknown:
            return TransitionDecision("UNKNOWN", reason="evidence/currentness/guard requirements are unresolved").validate()
        if blocked_by_dependency:
            return TransitionDecision("BLOCKED", reason="dependency or retry boundary blocks remaining transition").validate()
        if self._model["termination_policy"]["allow_no_legal_transition"]:
            return TransitionDecision("COMPLETE", reason="no legal unfinished transition remains").validate()
        return TransitionDecision("BLOCKED", reason="no legal transition and implicit completion is forbidden").validate()

    def select_parallel(self, context: ProcessContextSnapshot) -> tuple[str, ...]:
        context.validate_for(self._ir)
        policy = self._model["scheduling_policy"]
        max_wip = policy["max_wip"]
        if max_wip <= 1:
            return ()
        legal: list[str] = []
        attempts = _attempt_map(context)
        for transition in self._ordered():
            tid = transition["transition_id"]
            if tid in context.completed_transitions or context.process_state not in transition["source_states"]:
                continue
            if set(transition["dependencies"]) - set(context.satisfied_dependencies):
                continue
            if set(transition["guards"]) - set(context.satisfied_guards):
                continue
            if set(transition["evidence_requirements"]) - set(context.satisfied_evidence_requirements):
                continue
            if set(transition["currentness_requirements"]) - set(context.satisfied_currentness_requirements):
                continue
            if set(transition["authority_requirements"]) - set(context.verified_authority_context_refs):
                continue
            if attempts.get(tid, 0) > transition["retry_policy"]["max_attempts"]:
                continue
            legal.append(tid)
        allowed_groups = [set(group) for group in policy["parallel_safe_groups"]]
        candidates = legal[:max_wip]
        if len(candidates) < 2:
            return tuple(candidates)
        if not any(set(candidates) <= group for group in allowed_groups):
            return (candidates[0],)
        selected: list[str] = []
        for tid in candidates:
            candidate = self._transitions[tid]
            if all(self._independent(candidate, self._transitions[other]) for other in selected):
                selected.append(tid)
        return tuple(selected)

    @staticmethod
    def _independent(left: dict, right: dict) -> bool:
        l, r = left["resource_claims"], right["resource_claims"]
        l_read, l_write = set(l["read_scopes"]), set(l["write_scopes"])
        r_read, r_write = set(r["read_scopes"]), set(r["write_scopes"])
        if l_write & (r_write | r_read) or r_write & l_read:
            return False
        if set(l["authority_budgets"]) & set(r["authority_budgets"]):
            return False
        if l["replay_domain"] and l["replay_domain"] == r["replay_domain"]:
            return False
        if l["reconciliation_group"] and l["reconciliation_group"] == r["reconciliation_group"]:
            return False
        if (l_write or r_write) and set(l["currentness_subjects"]) & set(r["currentness_subjects"]):
            return False
        return True


def apply_transition_outcome(process_ir: CanonicalProcessIR, context: ProcessContextSnapshot, outcome: ProcessTransitionOutcome) -> ProcessContextSnapshot:
    """Apply one already-evidenced downstream outcome; this function performs no effect."""
    process_ir.validate(); context.validate_for(process_ir); outcome.validate()
    if outcome.process_ir_digest != process_ir.process_digest:
        raise ProcessSemanticError("outcome Process IR binding mismatch")
    if outcome.process_id != process_ir.as_dict()["process_id"]:
        raise ProcessSemanticError("outcome process identity mismatch")
    transition = next((item for item in process_ir.as_dict()["transitions"] if item["transition_id"] == outcome.transition_id), None)
    if transition is None:
        raise ProcessSemanticError("outcome transition is undefined")
    if context.process_state not in transition["source_states"]:
        raise ProcessSemanticError("outcome source-state substitution denied")
    expected_next = transition["outcome_map"].get(outcome.outcome)
    if expected_next is None:
        raise ProcessSemanticError("outcome label is not declared by transition")
    if expected_next in {"CONTINUE", "DEFER", "HANDOFF", "STOP", "COMPLETE"}:
        if outcome.next_state not in process_ir.as_dict()["states"]:
            raise ProcessSemanticError("directive outcome requires explicit valid next process state")
    elif outcome.next_state != expected_next:
        raise ProcessSemanticError("outcome next-state substitution denied")
    completed = context.completed_transitions
    if outcome.outcome == "PASS" and outcome.transition_id not in completed:
        completed = completed + (outcome.transition_id,)
    action_refs = context.action_result_refs + ((outcome.action_ref,) if outcome.action_ref else ())
    obs_refs = context.observation_refs + ((outcome.observation_ref,) if outcome.observation_ref else ())
    rec_refs = context.reconciliation_refs + ((outcome.reconciliation_ref,) if outcome.reconciliation_ref else ())
    return replace(context, process_state=outcome.next_state, completed_transitions=completed, action_result_refs=tuple(dict.fromkeys(action_refs)), observation_refs=tuple(dict.fromkeys(obs_refs)), reconciliation_refs=tuple(dict.fromkeys(rec_refs))).validate_for(process_ir)

"""Fail-closed, non-effectful selector and dynamic closure for canonical LION Process IR."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from cyber_lion.contracts.process_action import (
    ProcessActionContractError,
    ProcessTransitionOutcome,
    TransitionDecisionRecord,
)
from cyber_lion.contracts.process_ir import (
    AttemptRecord,
    CanonicalProcessIR,
    CurrentnessBasis,
    NEXT_DIRECTIVES,
    ProcessContextSnapshot,
    ProcessIRContractError,
)

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


def _current_basis_map(context: ProcessContextSnapshot) -> dict[str, CurrentnessBasis]:
    return {basis.requirement_id: basis for basis in context.currentness_bases}


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

    @staticmethod
    def _currentness_satisfied(transition: dict, context: ProcessContextSnapshot) -> bool:
        bases = _current_basis_map(context)
        allowed_subjects = set(transition["resource_claims"]["currentness_subjects"])
        for requirement in transition["currentness_requirements"]:
            basis = bases.get(requirement)
            if basis is None:
                return False
            basis.validate()
            if basis.state != "CURRENT" or basis.subject != requirement or basis.subject not in allowed_subjects or not basis.evidence_ref or not basis.observed_identity or not basis.observed_at or not basis.basis_digest:
                return False
        return True

    @staticmethod
    def _retry_reconciled(transition: dict, context: ProcessContextSnapshot) -> bool:
        count = _attempt_map(context).get(transition["transition_id"], 0)
        if count == 0:
            return True
        if transition["idempotency_class"] != "NON_IDEMPOTENT":
            return True
        if transition["replay_policy"] != "RECONCILE_FIRST":
            return False
        prior = [record for record in context.attempt_records if record.transition_id == transition["transition_id"] and record.attempt_number == count]
        return len(prior) == 1 and bool(prior[0].reconciliation_ref)

    def select(self, context: ProcessContextSnapshot) -> TransitionDecision:
        try:
            context.validate_for(self._ir)
        except ProcessIRContractError as exc:
            raise ProcessSemanticError(str(exc)) from exc
        if context.process_control == "COMPLETE":
            return TransitionDecision("COMPLETE", reason="process control is complete").validate()
        if context.process_control == "HANDOFF_REQUIRED":
            return TransitionDecision("HANDOFF_REQUIRED", reason="process control requires handoff").validate()
        if context.process_control == "DEFERRED":
            return TransitionDecision("BLOCKED", reason="process control is deferred").validate()
        if context.process_control == "TERMINATED":
            return TransitionDecision("BLOCKED", reason="process control is terminated").validate()
        if context.process_state in set(self._model["termination_policy"]["terminal_states"]):
            return TransitionDecision("COMPLETE", reason="terminal process state").validate()

        attempts = _attempt_map(context)
        blocked_by_dependency = False
        blocked_by_retry = False
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
            if not self._currentness_satisfied(transition, context):
                unknown = True
                continue
            if self._missing(transition["authority_requirements"], context.verified_authority_context_refs):
                handoff = True
                continue
            # max_attempts means additional attempts after the initial attempt.
            if attempts.get(tid, 0) > transition["retry_policy"]["max_attempts"]:
                blocked_by_retry = True
                continue
            if not self._retry_reconciled(transition, context):
                blocked_by_retry = True
                continue
            return TransitionDecision("SELECTED", transition_id=tid, reason="first legal unfinished transition").validate()

        if handoff:
            return TransitionDecision("HANDOFF_REQUIRED", reason="authority context is not independently verified").validate()
        if unknown:
            return TransitionDecision("UNKNOWN", reason="evidence/currentness/guard requirements are unresolved").validate()
        if blocked_by_dependency or blocked_by_retry:
            return TransitionDecision("BLOCKED", reason="dependency, retry or reconciliation boundary blocks remaining transition").validate()
        if self._model["termination_policy"]["allow_no_legal_transition"]:
            return TransitionDecision("COMPLETE", reason="no legal unfinished transition remains").validate()
        return TransitionDecision("BLOCKED", reason="no legal transition and implicit completion is forbidden").validate()

    def bind_selected(self, context: ProcessContextSnapshot) -> TransitionDecisionRecord:
        decision = self.select(context)
        if decision.decision != "SELECTED":
            raise ProcessSemanticError(f"cannot bind non-selected transition decision: {decision.decision}")
        transition = self._transitions[decision.transition_id]
        return TransitionDecisionRecord(
            process_id=self._model["process_id"],
            process_ir_digest=self._ir.process_digest,
            process_context_digest=context.context_digest(self._ir),
            transition_id=decision.transition_id,
            transition_class=transition["transition_class"],
            decision="SELECTED",
            decision_basis=decision.reason,
            selected_at=context.observed_at,
        ).sealed()

    def select_parallel(self, context: ProcessContextSnapshot) -> tuple[str, ...]:
        context.validate_for(self._ir)
        if context.process_control != "ACTIVE":
            return ()
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
            if not self._currentness_satisfied(transition, context):
                continue
            if set(transition["authority_requirements"]) - set(context.verified_authority_context_refs):
                continue
            if attempts.get(tid, 0) > transition["retry_policy"]["max_attempts"]:
                continue
            if not self._retry_reconciled(transition, context):
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


def _required_currentness_basis_digests(transition: dict, context: ProcessContextSnapshot) -> set[str]:
    bases = _current_basis_map(context)
    return {bases[requirement].basis_digest for requirement in transition["currentness_requirements"] if requirement in bases and bases[requirement].state == "CURRENT"}


def apply_transition_outcome(process_ir: CanonicalProcessIR, context: ProcessContextSnapshot, decision_record: TransitionDecisionRecord, outcome: ProcessTransitionOutcome) -> ProcessContextSnapshot:
    """Apply one evidence-bound selected outcome; this function performs no effect."""
    process_ir.validate(); context.validate_for(process_ir)
    try:
        decision_record.validate(); outcome.validate()
    except ProcessActionContractError as exc:
        raise ProcessSemanticError(str(exc)) from exc
    model = process_ir.as_dict()
    if decision_record.process_id != model["process_id"]:
        raise ProcessSemanticError("decision process identity mismatch")
    if decision_record.process_ir_digest != process_ir.process_digest:
        raise ProcessSemanticError("decision Process IR binding mismatch")
    if decision_record.process_context_digest != context.context_digest(process_ir):
        raise ProcessSemanticError("decision ProcessContext binding mismatch")
    current_decision = TransitionSelector(process_ir).select(context)
    if current_decision.decision != "SELECTED" or current_decision.transition_id != decision_record.transition_id:
        raise ProcessSemanticError("outcome lacks a currently legal selected transition")
    transition = next((item for item in model["transitions"] if item["transition_id"] == decision_record.transition_id), None)
    if transition is None:
        raise ProcessSemanticError("decision transition is undefined")
    if decision_record.transition_class != transition["transition_class"]:
        raise ProcessSemanticError("decision transition class mismatch")
    if decision_record.transition_decision_digest != outcome.transition_decision_digest:
        raise ProcessSemanticError("outcome transition decision binding mismatch")
    if outcome.process_ir_digest != process_ir.process_digest:
        raise ProcessSemanticError("outcome Process IR binding mismatch")
    if outcome.process_id != model["process_id"]:
        raise ProcessSemanticError("outcome process identity mismatch")
    if outcome.transition_id != transition["transition_id"]:
        raise ProcessSemanticError("outcome transition identity mismatch")
    if context.process_state not in transition["source_states"]:
        raise ProcessSemanticError("outcome source-state substitution denied")
    attempts = _attempt_map(context)
    expected_attempt = attempts.get(transition["transition_id"], 0) + 1
    if outcome.attempt_number != expected_attempt:
        raise ProcessSemanticError("outcome attempt number is not the next legal attempt")
    expected_next = transition["outcome_map"].get(outcome.outcome)
    if expected_next is None:
        raise ProcessSemanticError("outcome label is not declared by transition")
    if transition["transition_class"] == "ACTION_REQUIRED" and outcome.outcome == "PASS":
        required = (outcome.action_ref, outcome.proposal_digest, outcome.admission_ref, outcome.effect_ref, outcome.observation_ref, outcome.reconciliation_ref, outcome.currentness_basis_ref)
        if any(not item for item in required):
            raise ProcessSemanticError("ACTION_REQUIRED PASS requires action, proposal, admission, effect, observation, reconciliation and currentness evidence")
        valid_currentness = _required_currentness_basis_digests(transition, context)
        if outcome.currentness_basis_ref not in valid_currentness:
            raise ProcessSemanticError("ACTION_REQUIRED PASS currentness basis does not bind selected context")
    next_state = outcome.next_state
    next_control = "ACTIVE"
    if expected_next in NEXT_DIRECTIVES:
        if next_state != context.process_state:
            raise ProcessSemanticError("directive outcome cannot substitute arbitrary process state")
        next_control = {"CONTINUE":"ACTIVE","DEFER":"DEFERRED","HANDOFF":"HANDOFF_REQUIRED","STOP":"TERMINATED","COMPLETE":"COMPLETE"}[expected_next]
    elif next_state != expected_next:
        raise ProcessSemanticError("outcome next-state substitution denied")
    attempt_record = AttemptRecord(
        transition_id=transition["transition_id"], attempt_number=expected_attempt,
        outcome=outcome.outcome, effect_ref=outcome.effect_ref,
        observation_ref=outcome.observation_ref, reconciliation_ref=outcome.reconciliation_ref,
    ).sealed()
    completed = context.completed_transitions
    if outcome.outcome == "PASS" and outcome.transition_id not in completed:
        completed = completed + (outcome.transition_id,)
    action_refs = context.action_result_refs + ((outcome.action_ref,) if outcome.action_ref else ())
    obs_refs = context.observation_refs + ((outcome.observation_ref,) if outcome.observation_ref else ())
    rec_refs = context.reconciliation_refs + ((outcome.reconciliation_ref,) if outcome.reconciliation_ref else ())
    new_counts = dict(attempts); new_counts[outcome.transition_id] = expected_attempt
    return replace(
        context,
        process_state=next_state,
        process_control=next_control,
        completed_transitions=completed,
        action_result_refs=tuple(dict.fromkeys(action_refs)),
        observation_refs=tuple(dict.fromkeys(obs_refs)),
        reconciliation_refs=tuple(dict.fromkeys(rec_refs)),
        attempt_counts=tuple(sorted(new_counts.items())),
        attempt_records=context.attempt_records + (attempt_record,),
    ).validate_for(process_ir)

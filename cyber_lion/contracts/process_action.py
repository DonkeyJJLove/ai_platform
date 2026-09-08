"""Non-authoritative boundary contracts between Process IR and the Action plane."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re

_ACTION_DOMAIN = b"LION/PROCESS-ACTION-INTENT/1\0"
_DECISION_DOMAIN = b"LION/PROCESS-TRANSITION-DECISION/1\0"
_OUTCOME_DOMAIN = b"LION/PROCESS-TRANSITION-OUTCOME/1\0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:/-]{0,255}$")
OUTCOMES = frozenset({"PASS", "FAIL", "UNKNOWN", "DRIFT", "BLOCKED", "AUTHORITY_BOUNDARY", "COMPLETE"})
TRANSITION_CLASSES = frozenset({"INTERNAL", "ACTION_REQUIRED"})


class ProcessActionContractError(ValueError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _id(value: str, name: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ProcessActionContractError(f"{name} invalid")
    return value


def _text(value: str, name: str, *, optional: bool = False) -> str:
    if type(value) is not str or "\x00" in value or len(value) > 4096:
        raise ProcessActionContractError(f"{name} invalid")
    if not optional and not value:
        raise ProcessActionContractError(f"{name} required")
    return value


def _digest(value: str, name: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ProcessActionContractError(f"{name} invalid")
    return value


def _unique(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    if type(values) is not tuple or len(values) != len(set(values)):
        raise ProcessActionContractError(f"{name} invalid")
    for value in values:
        _text(value, name)
    return values


@dataclass(frozen=True)
class ActionIntentCandidate:
    """A process request for Action-plane materialization; never a grant or execution order."""
    process_id: str
    process_ir_digest: str
    transition_id: str
    mission_ref: str
    intent: str
    target_class: str
    required_capability: str
    authority_requirement: str
    process_scope_digest: str
    expected_process_outcome: str
    evidence_context_refs: tuple[str, ...]
    currentness_context_refs: tuple[str, ...]
    action_intent_digest: str = ""
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"

    def canonical_payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("action_intent_digest")
        value["evidence_context_refs"] = list(self.evidence_context_refs)
        value["currentness_context_refs"] = list(self.currentness_context_refs)
        return value

    def compute_digest(self) -> str:
        return sha256(_ACTION_DOMAIN + _canonical(self.canonical_payload())).hexdigest()

    def sealed(self) -> "ActionIntentCandidate":
        value = asdict(self)
        value["action_intent_digest"] = self.compute_digest()
        return ActionIntentCandidate(**value).validate()

    def validate(self) -> "ActionIntentCandidate":
        _id(self.process_id, "process_id")
        _digest(self.process_ir_digest, "process_ir_digest")
        _id(self.transition_id, "transition_id")
        for name in ("mission_ref", "intent", "target_class", "required_capability", "authority_requirement", "expected_process_outcome"):
            _text(getattr(self, name), name)
        _digest(self.process_scope_digest, "process_scope_digest")
        _unique(self.evidence_context_refs, "evidence_context_refs")
        _unique(self.currentness_context_refs, "currentness_context_refs")
        if self.authority_effect != "NONE" or self.execution_effect != "NONE":
            raise ProcessActionContractError("ActionIntentCandidate must be non-authoritative and non-effectful")
        if self.action_intent_digest:
            _digest(self.action_intent_digest, "action_intent_digest")
            if self.action_intent_digest != self.compute_digest():
                raise ProcessActionContractError("action_intent_digest mismatch")
        return self


@dataclass(frozen=True)
class TransitionDecisionRecord:
    """Digest-bound evidence that one transition was legally selected from one ProcessContextSnapshot."""
    process_id: str
    process_ir_digest: str
    process_context_digest: str
    transition_id: str
    transition_class: str
    decision: str
    decision_basis: str
    selected_at: str
    transition_decision_digest: str = ""
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"

    def canonical_payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("transition_decision_digest")
        return value

    def compute_digest(self) -> str:
        return sha256(_DECISION_DOMAIN + _canonical(self.canonical_payload())).hexdigest()

    def sealed(self) -> "TransitionDecisionRecord":
        value = asdict(self)
        value["transition_decision_digest"] = self.compute_digest()
        return TransitionDecisionRecord(**value).validate()

    def validate(self) -> "TransitionDecisionRecord":
        _id(self.process_id, "process_id")
        _digest(self.process_ir_digest, "process_ir_digest")
        _digest(self.process_context_digest, "process_context_digest")
        _id(self.transition_id, "transition_id")
        if self.transition_class not in TRANSITION_CLASSES:
            raise ProcessActionContractError("transition_class invalid")
        if self.decision != "SELECTED":
            raise ProcessActionContractError("transition decision record must be SELECTED")
        _text(self.decision_basis, "decision_basis")
        _text(self.selected_at, "selected_at")
        if self.authority_effect != "NONE" or self.execution_effect != "NONE":
            raise ProcessActionContractError("TransitionDecisionRecord must be non-authoritative and non-effectful")
        if self.transition_decision_digest:
            _digest(self.transition_decision_digest, "transition_decision_digest")
            if self.transition_decision_digest != self.compute_digest():
                raise ProcessActionContractError("transition_decision_digest mismatch")
        return self


@dataclass(frozen=True)
class ProcessTransitionOutcome:
    """Evidence carrier for one selected transition; never self-attesting proof."""
    process_id: str
    process_ir_digest: str
    transition_id: str
    transition_decision_digest: str
    attempt_number: int
    outcome: str
    next_state: str
    action_ref: str = ""
    proposal_digest: str = ""
    admission_ref: str = ""
    effect_ref: str = ""
    observation_ref: str = ""
    reconciliation_ref: str = ""
    currentness_basis_ref: str = ""
    transition_outcome_digest: str = ""

    def canonical_payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("transition_outcome_digest")
        return value

    def compute_digest(self) -> str:
        return sha256(_OUTCOME_DOMAIN + _canonical(self.canonical_payload())).hexdigest()

    def sealed(self) -> "ProcessTransitionOutcome":
        value = asdict(self)
        value["transition_outcome_digest"] = self.compute_digest()
        return ProcessTransitionOutcome(**value).validate()

    def validate(self) -> "ProcessTransitionOutcome":
        _id(self.process_id, "process_id")
        _digest(self.process_ir_digest, "process_ir_digest")
        _id(self.transition_id, "transition_id")
        _digest(self.transition_decision_digest, "transition_decision_digest")
        if type(self.attempt_number) is not int or isinstance(self.attempt_number, bool) or self.attempt_number < 1:
            raise ProcessActionContractError("attempt_number invalid")
        if self.outcome not in OUTCOMES:
            raise ProcessActionContractError("outcome invalid")
        _text(self.next_state, "next_state")
        for name in ("action_ref", "proposal_digest", "admission_ref", "effect_ref", "observation_ref", "reconciliation_ref", "currentness_basis_ref"):
            _text(getattr(self, name), name, optional=True)
        if self.proposal_digest:
            _digest(self.proposal_digest, "proposal_digest")
        if self.currentness_basis_ref:
            _digest(self.currentness_basis_ref, "currentness_basis_ref")
        if self.transition_outcome_digest:
            _digest(self.transition_outcome_digest, "transition_outcome_digest")
            if self.transition_outcome_digest != self.compute_digest():
                raise ProcessActionContractError("transition_outcome_digest mismatch")
        return self

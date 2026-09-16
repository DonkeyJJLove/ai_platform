"""Contracts for human operator participation and bounded mission intervention."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

SCHEMA_ID = "lion.operator-intervention/v1"
PRIMARY_OPERATOR = "OPERATOR_PRIMARY"
PRIMARY_PARTICIPANT = "operator:primary"

COMMUNICATION_ACTIONS = frozenset({"MESSAGE", "REQUEST_STATUS", "ANNOTATE"})
CONTEXT_ACTIONS = frozenset({"AMEND_CONTEXT", "AMEND_PLAN", "REASSIGN", "APPROVE_PROPOSAL"})
CONTROL_ACTIONS = frozenset({
    "PAUSE_SCOPE", "STOP_SCOPE", "CANCEL_ASSIGNMENT", "REVOKE_CAPABILITY",
    "TAKE_CONTROL", "RELEASE_CONTROL", "RESUME_SCOPE",
})
ACTIONS = COMMUNICATION_ACTIONS | CONTEXT_ACTIONS | CONTROL_ACTIONS
TARGET_RE = re.compile(r"^(?:mission|drone|swarm|group|operator):[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, name: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValueError(name)
    value = value.strip()
    if not value or len(value) > maximum:
        raise ValueError(name)
    return value


def validate_target(value: Any) -> str:
    value = _text(value, "target", maximum=200)
    if not TARGET_RE.fullmatch(value):
        raise ValueError("target")
    return value


def mission_target(mission_id: str) -> str:
    if not isinstance(mission_id, str) or not ID_RE.fullmatch(mission_id):
        raise ValueError("mission_id")
    return "mission:" + mission_id


@dataclass(frozen=True)
class OperatorCommand:
    command_id: str
    mission_id: str
    action: str
    target: str
    payload: dict[str, Any]
    expected_revision: int | None = None
    deadline_at: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None

    @classmethod
    def from_dict(cls, value: Any) -> "OperatorCommand":
        if type(value) is not dict:
            raise ValueError("command object")
        allowed = {
            "command_id", "mission_id", "action", "target", "payload",
            "expected_revision", "deadline_at", "correlation_id", "causation_id",
        }
        if set(value) - allowed:
            raise ValueError("command fields")
        command_id = _text(value.get("command_id"), "command_id", maximum=192)
        mission_id = _text(value.get("mission_id"), "mission_id", maximum=128)
        if not ID_RE.fullmatch(command_id) or not ID_RE.fullmatch(mission_id):
            raise ValueError("command identity")
        action = _text(value.get("action"), "action", maximum=64).upper()
        if action not in ACTIONS:
            raise ValueError("action")
        target = validate_target(value.get("target") or mission_target(mission_id))
        payload = value.get("payload")
        if payload is None:
            payload = {}
        if type(payload) is not dict:
            raise ValueError("payload")
        if len(canonical(payload).encode("utf-8")) > 32768:
            raise ValueError("payload too large")
        expected = value.get("expected_revision")
        if expected is not None and (type(expected) is not int or expected < 0):
            raise ValueError("expected_revision")
        deadline = value.get("deadline_at")
        if deadline is not None and (not isinstance(deadline, str) or len(deadline) > 64):
            raise ValueError("deadline_at")
        corr = value.get("correlation_id")
        cause = value.get("causation_id")
        for name, item in (("correlation_id", corr), ("causation_id", cause)):
            if item is not None and (not isinstance(item, str) or not ID_RE.fullmatch(item)):
                raise ValueError(name)
        return cls(command_id, mission_id, action, target, payload, expected, deadline, corr, cause)

    def as_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "mission_id": self.mission_id,
            "action": self.action,
            "target": self.target,
            "payload": self.payload,
            "expected_revision": self.expected_revision,
            "deadline_at": self.deadline_at,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }

    @property
    def payload_digest(self) -> str:
        return digest(self.as_dict())


def action_effect(action: str) -> str:
    action = str(action).upper()
    if action in COMMUNICATION_ACTIONS:
        return "COMMUNICATION"
    if action in {"AMEND_CONTEXT", "AMEND_PLAN", "APPROVE_PROPOSAL"}:
        return "CONTROL_METADATA"
    if action == "REASSIGN":
        return "ASSIGNMENT_CONTROL"
    if action in CONTROL_ACTIONS:
        return "CONTROL_STATE"
    raise ValueError("action")


def command_receipt_digest(value: dict[str, Any]) -> str:
    return digest({k: v for k, v in value.items() if k != "receipt_digest"})

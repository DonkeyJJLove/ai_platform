"""Strict LPCL v1 surface syntax over CanonicalProcessIR.

LPCL is never executed directly. It parses into the canonical Process IR.
"""
from __future__ import annotations

import json
from typing import Any

from cyber_lion.contracts.process_ir import CanonicalProcessIR, ProcessIRContractError

_HEADER = "LPCL 1.0"
_STATEMENTS = (
    ("PROCESS", "process_id"),
    ("MISSION", "mission_ref"),
    ("GOAL", "goal_ref"),
    ("SCOPE", "scope"),
    ("INITIAL", "initial_state"),
    ("STATES", "states"),
    ("DEPENDENCIES", "dependencies"),
    ("TRANSITIONS", "transitions"),
    ("SCHEDULING", "scheduling_policy"),
    ("TERMINATION", "termination_policy"),
    ("LINEAGE", "lineage"),
)


class LPCLParseError(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise LPCLParseError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _parse_value(raw: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=lambda value: (_ for _ in ()).throw(LPCLParseError(f"non-RFC8259 constant is forbidden: {value}")))
    except LPCLParseError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LPCLParseError("LPCL statement payload must be strict JSON") from exc


def parse_lpcl(text: str) -> CanonicalProcessIR:
    if type(text) is not str:
        raise LPCLParseError("LPCL source must be text")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0] != _HEADER or lines[-1] != "END":
        raise LPCLParseError("LPCL header or END marker missing")
    seen: dict[str, Any] = {}
    allowed = {name: field for name, field in _STATEMENTS}
    for line in lines[1:-1]:
        name, separator, raw = line.partition(" ")
        if not separator or name not in allowed:
            raise LPCLParseError(f"unknown or malformed LPCL statement: {name}")
        field = allowed[name]
        if field in seen:
            raise LPCLParseError(f"duplicate LPCL statement: {name}")
        seen[field] = _parse_value(raw)
    expected_fields = {field for _, field in _STATEMENTS}
    if set(seen) != expected_fields:
        missing = sorted(expected_fields - set(seen))
        raise LPCLParseError(f"missing LPCL statements: {missing}")
    mapping = {"schema_version": "1.0.0", **seen}
    try:
        return CanonicalProcessIR.from_mapping(mapping)
    except ProcessIRContractError as exc:
        raise LPCLParseError(str(exc)) from exc


def render_lpcl(process_ir: CanonicalProcessIR) -> str:
    process_ir.validate()
    value = process_ir.as_dict()
    lines = [_HEADER]
    for statement, field in _STATEMENTS:
        lines.append(statement + " " + json.dumps(value[field], sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))
    lines.append("END")
    return "\n".join(lines) + "\n"

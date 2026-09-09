"""Canonical RUN/PHASE authoring surface for LPCL v1.1 candidates.

This module does not execute RUN text. It parses a human/model authoring
surface into a bounded AST and compiles that AST into the existing
CanonicalProcessIR plus a non-authoritative FleetMissionIR.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Mapping

from cyber_lion.contracts.process_ir import CanonicalProcessIR, ProcessIRContractError
from cyber_lion.process_language.fleet_mission import (
    FleetMissionContractError,
    FleetMissionIR,
    FleetRoleSpec,
)

CANONICAL_SURFACE_VERSION = "1.1"
MISSION_CLASSES = frozenset({
    "LOGICAL_FLEET_MISSION",
    "LOCAL_FLEET_MISSION",
    "HYBRID_FLEET_MISSION",
})
_PHASE_KEY = re.compile(r"^PHASE_(0|[1-9][0-9]*)$")
_KEY = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:/-]{0,255}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

GLOBAL_KEYS = frozenset({
    "RUN", "PROJECT", "METAARCHITECTURE", "ARCHITECTURE_EPOCH",
    "PROCESS_LANGUAGE", "LPCL_VERSION", "PROCESS_CLASS", "MISSION_CLASS",
    "MISSION_ID", "PRIMARY_GOAL", "SCOPE_DOMAINS", "SCOPE_RESOURCES",
    "WIDENING_ALLOWED", "DEPENDENCIES", "LOGICAL_FLEET_ROLES",
    "LOCAL_FLEET_ROLES", "FLEET_ROLES", "ROLE_SEPARATION", "MAX_WIP", "ON_UNKNOWN",
    "PARENT_PROCESS_DIGESTS", "LINEAGE", "PRODUCTION_AUTHORITY",
    "MERGE_AUTHORITY", "DELETE_AUTHORITY", "RUNTIME_AUTHORITY",
    "AUTHORITY_EFFECT", "RUNTIME_EFFECT", "TERMINATION", "NEXT_PROCESS",
})
REQUIRED_GLOBAL_KEYS = frozenset({
    "RUN", "PROCESS_LANGUAGE", "LPCL_VERSION", "MISSION_CLASS", "MISSION_ID",
    "PRIMARY_GOAL", "SCOPE_DOMAINS", "SCOPE_RESOURCES", "WIDENING_ALLOWED",
})
REQUIRED_PHASE_KEYS = frozenset({
    "TRANSITION_CLASS", "OPERATOR", "ROLE", "EVIDENCE_REQUIREMENTS",
    "CURRENTNESS_REQUIREMENTS", "AUTHORITY_REQUIREMENTS",
    "EXPECTED_POSTCONDITIONS", "REPLAY_POLICY", "IDEMPOTENCY_CLASS",
    "RETRY_MAX_ATTEMPTS", "RETRY_ON_EXHAUSTED",
})
PHASE_CONTROL_KEYS = frozenset({
    *REQUIRED_PHASE_KEYS,
    "DEPENDENCIES", "GUARDS", "READ_SCOPES", "WRITE_SCOPES",
    "AUTHORITY_BUDGETS", "CURRENTNESS_SUBJECTS", "REPLAY_DOMAIN",
    "RECONCILIATION_GROUP", "TRIGGER", "ON_PASS", "ON_FAIL",
    "ON_UNKNOWN", "ON_DRIFT", "ON_BLOCKED", "ON_AUTHORITY_BOUNDARY",
    "ON_COMPLETE", "PRIORITY",
})
CONTROL_PREFIXES = (
    "LPCL_", "MISSION_", "SCOPE_", "TRANSITION_", "OPERATOR", "ROLE",
    "EVIDENCE_", "CURRENTNESS_", "AUTHORITY_", "EXPECTED_", "REPLAY_",
    "RETRY_", "ON_", "PARENT_PROCESS_", "MAX_WIP",
)


class CanonicalRunError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalRunPhase:
    index: int
    name: str
    fields: Mapping[str, tuple[str, ...]]
    annotations: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class CanonicalRunAST:
    globals: Mapping[str, tuple[str, ...]]
    global_annotations: Mapping[str, tuple[str, ...]]
    phases: tuple[CanonicalRunPhase, ...]

    @property
    def run_id(self) -> str:
        return _one(self.globals, "RUN")


@dataclass(frozen=True)
class CanonicalRunCompilation:
    surface: CanonicalRunAST
    process_ir: CanonicalProcessIR
    fleet_mission_ir: FleetMissionIR


def _one(mapping: Mapping[str, tuple[str, ...]], key: str) -> str:
    values = mapping.get(key)
    if values is None:
        raise CanonicalRunError(f"missing required field: {key}")
    if len(values) != 1 or not values[0]:
        raise CanonicalRunError(f"{key} must contain exactly one non-empty value")
    return values[0]


def _items(mapping: Mapping[str, tuple[str, ...]], key: str) -> tuple[str, ...]:
    return tuple(item for item in mapping.get(key, ()) if item)


def _strict_control_name(key: str) -> bool:
    return key in GLOBAL_KEYS or key in PHASE_CONTROL_KEYS or key.startswith(CONTROL_PREFIXES)


def _blocks(text: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if type(text) is not str:
        raise CanonicalRunError("canonical RUN source must be text")
    meaningful = [
        line.strip() for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not meaningful or meaningful[-1] != "END":
        raise CanonicalRunError("END marker missing")

    result: list[tuple[str, tuple[str, ...]]] = []
    key: str | None = None
    values: list[str] = []

    def flush() -> None:
        nonlocal key, values
        if key is not None:
            result.append((key, tuple(value.strip() for value in values if value.strip())))
        key = None
        values = []

    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "END":
            flush()
            break
        if "=" in stripped:
            candidate, inline = stripped.split("=", 1)
            if _KEY.fullmatch(candidate):
                flush()
                key = candidate
                if inline.strip():
                    values.append(inline.strip())
                continue
        if key is None:
            raise CanonicalRunError(f"value without field: {stripped}")
        values.append(stripped)
    return tuple(result)


def parse_canonical_run(text: str) -> CanonicalRunAST:
    globals_out: dict[str, tuple[str, ...]] = {}
    global_annotations: dict[str, tuple[str, ...]] = {}
    phases: list[CanonicalRunPhase] = []
    phase_name: str | None = None
    phase_index: int | None = None
    phase_fields: dict[str, tuple[str, ...]] = {}
    phase_annotations: dict[str, tuple[str, ...]] = {}

    def flush_phase() -> None:
        nonlocal phase_name, phase_index, phase_fields, phase_annotations
        if phase_index is None:
            return
        phases.append(CanonicalRunPhase(
            index=phase_index,
            name=phase_name or "",
            fields=dict(phase_fields),
            annotations=dict(phase_annotations),
        ))
        phase_name = None
        phase_index = None
        phase_fields = {}
        phase_annotations = {}

    for key, values in _blocks(text):
        phase_match = _PHASE_KEY.fullmatch(key)
        if phase_match:
            flush_phase()
            index = int(phase_match.group(1))
            if index != len(phases):
                raise CanonicalRunError("PHASE indexes must be contiguous from PHASE_0")
            if len(values) != 1:
                raise CanonicalRunError(f"{key} must contain exactly one phase name")
            phase_index = index
            phase_name = values[0]
            continue

        if phase_index is not None and key in PHASE_CONTROL_KEYS:
            if key in phase_fields:
                raise CanonicalRunError(f"duplicate PHASE_{phase_index} field: {key}")
            phase_fields[key] = values
            continue

        if key in GLOBAL_KEYS:
            if key in globals_out:
                raise CanonicalRunError(f"duplicate global field: {key}")
            globals_out[key] = values
            continue

        if phase_index is None:
            if _strict_control_name(key):
                raise CanonicalRunError(f"unknown top-level control field: {key}")
            if key in global_annotations:
                raise CanonicalRunError(f"duplicate top-level annotation: {key}")
            global_annotations[key] = values
            continue

        if _strict_control_name(key):
            raise CanonicalRunError(f"unknown PHASE_{phase_index} control field: {key}")
        if key in phase_annotations:
            raise CanonicalRunError(f"duplicate PHASE_{phase_index} annotation: {key}")
        phase_annotations[key] = values

    flush_phase()
    if not phases:
        raise CanonicalRunError("at least one PHASE_N block is required")

    missing = sorted(REQUIRED_GLOBAL_KEYS - set(globals_out))
    if missing:
        raise CanonicalRunError(f"missing required global fields: {missing}")
    for phase in phases:
        missing_phase = sorted(REQUIRED_PHASE_KEYS - set(phase.fields))
        if missing_phase:
            raise CanonicalRunError(f"PHASE_{phase.index} missing fields: {missing_phase}")

    if _one(globals_out, "PROCESS_LANGUAGE") != "LPCL":
        raise CanonicalRunError("PROCESS_LANGUAGE must be LPCL")
    if _one(globals_out, "LPCL_VERSION") != CANONICAL_SURFACE_VERSION:
        raise CanonicalRunError("LPCL_VERSION mismatch")
    if _one(globals_out, "MISSION_CLASS") not in MISSION_CLASSES:
        raise CanonicalRunError("MISSION_CLASS invalid")
    if _one(globals_out, "WIDENING_ALLOWED").upper() != "FALSE":
        raise CanonicalRunError("WIDENING_ALLOWED must be FALSE")
    for key in ("RUN", "MISSION_ID"):
        if _ID.fullmatch(_one(globals_out, key)) is None:
            raise CanonicalRunError(f"{key} has invalid identifier syntax")
    return CanonicalRunAST(
        globals=globals_out,
        global_annotations=global_annotations,
        phases=tuple(phases),
    )


def _role_specs(ast: CanonicalRunAST) -> tuple[FleetRoleSpec, ...]:
    mission_class = _one(ast.globals, "MISSION_CLASS")
    raw_roles: list[tuple[str, str]] = []

    def add(values: tuple[str, ...], domain: str) -> None:
        for role_id in values:
            raw_roles.append((role_id, domain))

    if mission_class == "LOGICAL_FLEET_MISSION":
        add(_items(ast.globals, "FLEET_ROLES") or _items(ast.globals, "LOGICAL_FLEET_ROLES"), "LOGICAL")
    elif mission_class == "LOCAL_FLEET_MISSION":
        add(_items(ast.globals, "FLEET_ROLES") or _items(ast.globals, "LOCAL_FLEET_ROLES"), "LOCAL")
    else:
        add(_items(ast.globals, "LOGICAL_FLEET_ROLES"), "LOGICAL")
        add(_items(ast.globals, "LOCAL_FLEET_ROLES"), "LOCAL")
    if not raw_roles:
        raise CanonicalRunError("fleet mission requires at least one declared role")
    role_ids = {role_id for role_id, _ in raw_roles}
    independent: dict[str, set[str]] = {role_id: set() for role_id in role_ids}
    for rule in _items(ast.globals, "ROLE_SEPARATION"):
        if rule.count("!=") != 1:
            raise CanonicalRunError("ROLE_SEPARATION entries must use ROLE_A!=ROLE_B")
        left, right = (item.strip() for item in rule.split("!=", 1))
        if left not in role_ids or right not in role_ids or left == right:
            raise CanonicalRunError("ROLE_SEPARATION references invalid roles")
        independent[left].add(right)
        independent[right].add(left)
    return tuple(
        FleetRoleSpec(
            role_id=role_id,
            execution_domain=domain,
            capabilities=(),
            independent_from=tuple(sorted(independent[role_id])),
        )
        for role_id, domain in raw_roles
    )


def _target(value: str, states: set[str]) -> str:
    directives = {"CONTINUE", "DEFER", "HANDOFF", "STOP", "COMPLETE"}
    if value in states or value in directives:
        return value
    raise CanonicalRunError(f"invalid outcome target: {value}")


def _integer(mapping: Mapping[str, tuple[str, ...]], key: str) -> int:
    raw = _one(mapping, key)
    try:
        return int(raw)
    except ValueError as exc:
        raise CanonicalRunError(f"{key} must be an integer") from exc


def compile_canonical_run(text: str) -> CanonicalRunCompilation:
    ast = parse_canonical_run(text)
    roles = _role_specs(ast)
    role_ids = {role.role_id for role in roles}
    role_domains = {role.role_id: role.execution_domain for role in roles}
    fleet_class = _one(ast.globals, "MISSION_CLASS").removesuffix("_FLEET_MISSION")

    phase_states = {f"PHASE_{phase.index}" for phase in ast.phases}
    state_targets = set(phase_states) | {"DONE"}
    states = [f"PHASE_{phase.index}" for phase in ast.phases] + ["DONE"]
    dependency_ids = _items(ast.globals, "DEPENDENCIES")
    if len(dependency_ids) != len(set(dependency_ids)):
        raise CanonicalRunError("DEPENDENCIES must be unique")
    dependencies = [
        {"dependency_id": dep, "required": True, "description": dep}
        for dep in dependency_ids
    ]
    dependency_set = set(dependency_ids)

    transitions: list[dict[str, object]] = []
    routing: list[tuple[str, str]] = []
    priorities: dict[str, int] = {}

    for position, phase in enumerate(ast.phases):
        fields = phase.fields
        transition_class = _one(fields, "TRANSITION_CLASS")
        operator = _one(fields, "OPERATOR")
        role = _one(fields, "ROLE")
        if role not in role_ids:
            raise CanonicalRunError(f"PHASE_{phase.index} references undeclared role: {role}")
        if transition_class not in {"INTERNAL", "ACTION_REQUIRED"}:
            raise CanonicalRunError(f"PHASE_{phase.index} TRANSITION_CLASS invalid")
        if transition_class == "ACTION_REQUIRED" and fleet_class == "LOGICAL":
            raise CanonicalRunError("ACTION_REQUIRED phase cannot use LOGICAL-only fleet mission")
        if transition_class == "ACTION_REQUIRED" and role_domains[role] != "LOCAL":
            raise CanonicalRunError("ACTION_REQUIRED phase must route to a LOCAL role")
        if transition_class == "ACTION_REQUIRED" and operator != "EMIT_ACTION_INTENT":
            raise CanonicalRunError("ACTION_REQUIRED phase must use EMIT_ACTION_INTENT")
        if transition_class == "INTERNAL" and operator == "EMIT_ACTION_INTENT":
            raise CanonicalRunError("INTERNAL phase cannot emit ActionIntent")

        transition_id = f"phase-{phase.index}"
        routing.append((transition_id, role))
        phase_dependencies = _items(fields, "DEPENDENCIES")
        if not set(phase_dependencies) <= dependency_set:
            raise CanonicalRunError(f"PHASE_{phase.index} references undefined dependency")

        evidence = list(_items(fields, "EVIDENCE_REQUIREMENTS"))
        currentness = list(_items(fields, "CURRENTNESS_REQUIREMENTS"))
        authority = list(_items(fields, "AUTHORITY_REQUIREMENTS"))
        expected = list(_items(fields, "EXPECTED_POSTCONDITIONS"))
        if not expected:
            raise CanonicalRunError(f"PHASE_{phase.index} EXPECTED_POSTCONDITIONS must not be empty")
        if transition_class == "ACTION_REQUIRED" and (not evidence or not currentness or not authority):
            raise CanonicalRunError(
                "ACTION_REQUIRED phase requires evidence, currentness and authority requirements"
            )

        default_pass = f"PHASE_{phase.index + 1}" if position + 1 < len(ast.phases) else "DONE"
        outcome_map = {
            "PASS": _target(_one(fields, "ON_PASS") if "ON_PASS" in fields else default_pass, state_targets),
            "FAIL": _target(_one(fields, "ON_FAIL") if "ON_FAIL" in fields else "STOP", state_targets),
            "UNKNOWN": _target(_one(fields, "ON_UNKNOWN") if "ON_UNKNOWN" in fields else "HANDOFF", state_targets),
            "DRIFT": _target(_one(fields, "ON_DRIFT") if "ON_DRIFT" in fields else "HANDOFF", state_targets),
            "BLOCKED": _target(_one(fields, "ON_BLOCKED") if "ON_BLOCKED" in fields else "DEFER", state_targets),
        }
        if transition_class == "ACTION_REQUIRED" or "ON_AUTHORITY_BOUNDARY" in fields:
            outcome_map["AUTHORITY_BOUNDARY"] = _target(
                _one(fields, "ON_AUTHORITY_BOUNDARY")
                if "ON_AUTHORITY_BOUNDARY" in fields else "HANDOFF",
                state_targets,
            )
        if "ON_COMPLETE" in fields:
            outcome_map["COMPLETE"] = _target(_one(fields, "ON_COMPLETE"), state_targets)

        currentness_subjects = list(_items(fields, "CURRENTNESS_SUBJECTS") or tuple(currentness))
        if not set(currentness) <= set(currentness_subjects):
            raise CanonicalRunError(
                f"PHASE_{phase.index} CURRENTNESS_SUBJECTS do not cover requirements"
            )
        authority_budgets = list(_items(fields, "AUTHORITY_BUDGETS") or tuple(authority))
        read_scopes = list(_items(fields, "READ_SCOPES") or _items(ast.globals, "SCOPE_RESOURCES"))
        write_scopes = list(_items(fields, "WRITE_SCOPES"))
        retry_max = _integer(fields, "RETRY_MAX_ATTEMPTS")
        priority = _integer(fields, "PRIORITY") if "PRIORITY" in fields else position
        priorities[transition_id] = priority

        transitions.append({
            "transition_id": transition_id,
            "transition_class": transition_class,
            "source_states": [f"PHASE_{phase.index}"],
            "trigger": _one(fields, "TRIGGER") if "TRIGGER" in fields else phase.name,
            "dependencies": list(phase_dependencies),
            "guards": list(_items(fields, "GUARDS")),
            "evidence_requirements": evidence,
            "currentness_requirements": currentness,
            "authority_requirements": authority,
            "operator": operator,
            "expected_postconditions": expected,
            "outcome_map": outcome_map,
            "retry_policy": {
                "max_attempts": retry_max,
                "on_exhausted": _one(fields, "RETRY_ON_EXHAUSTED"),
            },
            "replay_policy": _one(fields, "REPLAY_POLICY"),
            "idempotency_class": _one(fields, "IDEMPOTENCY_CLASS"),
            "resource_claims": {
                "read_scopes": read_scopes,
                "write_scopes": write_scopes,
                "authority_budgets": authority_budgets,
                "currentness_subjects": currentness_subjects,
                "replay_domain": (
                    _one(fields, "REPLAY_DOMAIN")
                    if "REPLAY_DOMAIN" in fields else ast.run_id
                ),
                "reconciliation_group": (
                    _one(fields, "RECONCILIATION_GROUP")
                    if "RECONCILIATION_GROUP" in fields else ast.run_id
                ),
            },
        })

    parent_digests = list(_items(ast.globals, "PARENT_PROCESS_DIGESTS"))
    for digest in parent_digests:
        if _SHA256.fullmatch(digest) is None:
            raise CanonicalRunError("PARENT_PROCESS_DIGESTS contains invalid SHA-256")

    primary_goal = "\n".join(_items(ast.globals, "PRIMARY_GOAL"))
    if not primary_goal:
        raise CanonicalRunError("PRIMARY_GOAL must not be empty")
    process_model = {
        "schema_version": "1.0.0",
        "process_id": ast.run_id,
        "mission_ref": "mission:" + _one(ast.globals, "MISSION_ID"),
        "goal_ref": "goal:" + sha256(primary_goal.encode("utf-8")).hexdigest(),
        "scope": {
            "domains": list(_items(ast.globals, "SCOPE_DOMAINS")),
            "resources": list(_items(ast.globals, "SCOPE_RESOURCES")),
            "widening_allowed": False,
        },
        "initial_state": "PHASE_0",
        "states": states,
        "dependencies": dependencies,
        "transitions": transitions,
        "scheduling_policy": {
            "strategy": "DECLARED_ORDER",
            "order": [str(item["transition_id"]) for item in transitions],
            "priorities": priorities,
            "max_wip": _integer(ast.globals, "MAX_WIP") if "MAX_WIP" in ast.globals else 1,
            "parallel_safe_groups": [],
        },
        "termination_policy": {
            "terminal_states": ["DONE"],
            "allow_no_legal_transition": True,
            "on_unknown": _one(ast.globals, "ON_UNKNOWN") if "ON_UNKNOWN" in ast.globals else "HANDOFF",
        },
        "lineage": {
            "parent_process_digests": parent_digests,
            "generation": 0 if not parent_digests else 1,
            "source_refs": list(_items(ast.globals, "LINEAGE")) or ["canonical-run:" + ast.run_id],
        },
    }

    fleet = FleetMissionIR(
        schema_version="1.0.0",
        mission_id=_one(ast.globals, "MISSION_ID"),
        fleet_class=fleet_class,
        roles=roles,
        routing=tuple(routing),
        authority_effect="NONE",
        runtime_effect="NONE",
        effect_provider_effect="NONE",
    )
    try:
        process_ir = CanonicalProcessIR.from_mapping(process_model)
        fleet.validate()
    except (ProcessIRContractError, FleetMissionContractError, ValueError) as exc:
        raise CanonicalRunError(str(exc)) from exc
    return CanonicalRunCompilation(
        surface=ast,
        process_ir=process_ir,
        fleet_mission_ir=fleet,
    )

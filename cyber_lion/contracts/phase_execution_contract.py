"""Canonical non-authoritative execution contract for one LION process phase.

A PhaseExecutionContract sits between process intent and runtime capability
binding.  It constrains what kind of execution may satisfy a phase; it never
mints authority, selects a concrete effect provider, or proves completion.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_ID = "lion.phase-execution-contract/v1"
CONTRACT_VERSION = "1.0.0"
COMPILER_VERSION = "lion.phase-contract-compiler/1.0"

EXECUTION_CLASSES = frozenset({
    "OBSERVE", "VERIFY", "COGNITIVE", "VERIFY_THEN_REPAIR", "MUTATE",
    "VALIDATE", "CONTROL",
})
BINDING_MODES = frozenset({"STATIC", "DYNAMIC"})
MISSING_CAPABILITY_POLICIES = frozenset({"FAIL", "WAIT", "WAIT_AND_DISCOVER", "ESCALATE"})
EFFECT_CEILINGS = frozenset({"NONE", "CONTROL_STATE", "BOUNDED_LOCAL", "BOUNDED_REPOSITORY", "BOUNDED_MATERIAL"})
CONTRACT_SOURCES = frozenset({"DECLARED", "MIGRATED_EXPLICIT", "LEGACY_INFERRED_SAFE"})
PHASE_CONTRACT_STATES = frozenset({"VALID_BOUND", "VALID_DYNAMIC", "VALID_UNBOUND_WAITING", "LEGACY_INFERRED_SAFE", "INVALID"})
MISSION_READINESS_STATES = frozenset({"READY_BOUND", "VALID_WITH_DYNAMIC_BINDING", "WAITING_FOR_CAPABILITIES", "INVALID"})

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_.:-]{0,255}$")
_PREDICATE = re.compile(r"^[A-Z][A-Z0-9_.:-]{0,255}=[A-Z][A-Z0-9_.:-]{0,255}$")
_EFFECT_ORDER = {"NONE": 0, "CONTROL_STATE": 1, "BOUNDED_LOCAL": 2, "BOUNDED_REPOSITORY": 3, "BOUNDED_MATERIAL": 4}


class PhaseExecutionContractError(ValueError):
    pass


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return sha256(_canon(value).encode("utf-8")).hexdigest()


def _tokens(value: str | Iterable[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        items = [x.strip() for x in re.split(r"[,;]", value) if x.strip()]
    else:
        items = [str(x).strip() for x in value if str(x).strip()]
    return tuple(items)


def _bool(value: str | bool | None, name: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().upper()
    if text == "TRUE":
        return True
    if text == "FALSE":
        return False
    raise PhaseExecutionContractError(f"{name} must be TRUE or FALSE")


@dataclass(frozen=True)
class PhaseExecutionContract:
    mission_id: str
    phase_id: str
    ordinal: int
    execution_class: str
    capability_classes: tuple[str, ...]
    effect_ceiling: str
    binding_mode: str
    on_missing_capability: str
    auto_resume: bool
    verify_before_mutate: bool
    currentness_requirements: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    completion_predicates: tuple[str, ...]
    contract_source: str
    contract_version: str = CONTRACT_VERSION
    compiler_version: str = COMPILER_VERSION

    def validate(self) -> "PhaseExecutionContract":
        if not isinstance(self.mission_id, str) or _ID.fullmatch(self.mission_id) is None:
            raise PhaseExecutionContractError("mission_id invalid")
        if not isinstance(self.phase_id, str) or _ID.fullmatch(self.phase_id) is None:
            raise PhaseExecutionContractError("phase_id invalid")
        if type(self.ordinal) is not int or self.ordinal < 1:
            raise PhaseExecutionContractError("ordinal invalid")
        if self.contract_version != CONTRACT_VERSION:
            raise PhaseExecutionContractError("contract_version mismatch")
        if self.execution_class not in EXECUTION_CLASSES:
            raise PhaseExecutionContractError("execution_class invalid")
        if self.effect_ceiling not in EFFECT_CEILINGS:
            raise PhaseExecutionContractError("effect_ceiling invalid")
        if self.binding_mode not in BINDING_MODES:
            raise PhaseExecutionContractError("binding_mode invalid")
        if self.on_missing_capability not in MISSING_CAPABILITY_POLICIES:
            raise PhaseExecutionContractError("on_missing_capability invalid")
        if self.contract_source not in CONTRACT_SOURCES:
            raise PhaseExecutionContractError("contract_source invalid")
        if not self.capability_classes or len(set(self.capability_classes)) != len(self.capability_classes):
            raise PhaseExecutionContractError("capability_classes must be non-empty and unique")
        for collection, name in (
            (self.capability_classes, "capability_class"),
            (self.currentness_requirements, "currentness_requirement"),
            (self.evidence_requirements, "evidence_requirement"),
        ):
            for item in collection:
                if not isinstance(item, str) or _TOKEN.fullmatch(item) is None:
                    raise PhaseExecutionContractError(f"{name} invalid: {item!r}")
        for item in self.completion_predicates:
            if not isinstance(item, str) or _PREDICATE.fullmatch(item) is None:
                raise PhaseExecutionContractError(f"completion_predicate invalid: {item!r}")
        if self.execution_class == "OBSERVE" and self.effect_ceiling != "NONE":
            raise PhaseExecutionContractError("OBSERVE effect ceiling must be NONE")
        if self.execution_class == "VERIFY_THEN_REPAIR" and not self.verify_before_mutate:
            raise PhaseExecutionContractError("VERIFY_THEN_REPAIR requires verify_before_mutate")
        if self.execution_class == "MUTATE" and not self.evidence_requirements:
            raise PhaseExecutionContractError("MUTATE requires evidence requirements")
        if self.execution_class in {"VERIFY", "VERIFY_THEN_REPAIR", "VALIDATE"} and not self.completion_predicates:
            raise PhaseExecutionContractError("verification execution class requires completion predicates")
        if self.auto_resume and self.on_missing_capability not in {"WAIT", "WAIT_AND_DISCOVER"}:
            raise PhaseExecutionContractError("auto_resume requires deterministic waiting policy")
        return self

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        value = {
            "schema": SCHEMA_ID,
            "mission_id": self.mission_id,
            "phase_id": self.phase_id,
            "ordinal": self.ordinal,
            "contract_version": self.contract_version,
            "execution_class": self.execution_class,
            "capability_classes": list(self.capability_classes),
            "effect_ceiling": self.effect_ceiling,
            "binding_mode": self.binding_mode,
            "on_missing_capability": self.on_missing_capability,
            "auto_resume": self.auto_resume,
            "verify_before_mutate": self.verify_before_mutate,
            "currentness_requirements": list(self.currentness_requirements),
            "evidence_requirements": list(self.evidence_requirements),
            "completion_predicates": list(self.completion_predicates),
            "contract_source": self.contract_source,
            "compiler_version": self.compiler_version,
        }
        value["contract_digest"] = _digest(value)
        return value

    @property
    def contract_digest(self) -> str:
        return self.as_dict()["contract_digest"]


@dataclass(frozen=True)
class ExecutionPreflight:
    phase_count: int
    contract_count: int
    bound_count: int
    dynamic_count: int
    unbound_count: int
    invalid_count: int
    authority_closure: str
    currentness_closure: str
    evidence_closure: str
    capability_closure: str
    mission_readiness: str
    phases: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        value = {
            "schema": "lion.mission-execution-preflight/v1",
            "phase_count": self.phase_count,
            "contract_count": self.contract_count,
            "bound_count": self.bound_count,
            "dynamic_count": self.dynamic_count,
            "unbound_count": self.unbound_count,
            "invalid_count": self.invalid_count,
            "authority_closure": self.authority_closure,
            "currentness_closure": self.currentness_closure,
            "evidence_closure": self.evidence_closure,
            "capability_closure": self.capability_closure,
            "mission_readiness": self.mission_readiness,
            "phases": [dict(x) for x in self.phases],
        }
        value["preflight_digest"] = _digest(value)
        return value


def _completion_values(pairs: Mapping[str, str], prefix: str) -> tuple[str, ...]:
    rows: list[tuple[int, str]] = []
    pattern = re.compile(re.escape(prefix) + r"_COMPLETION_([0-9]{2})$")
    for key, value in pairs.items():
        match = pattern.fullmatch(key)
        if match and str(value).strip():
            rows.append((int(match.group(1)), str(value).strip()))
    rows.sort()
    return tuple(value for _, value in rows)


def _legacy_safe_contract(mission_id: str, phase_id: str, ordinal: int) -> PhaseExecutionContract:
    return PhaseExecutionContract(
        mission_id=mission_id,
        phase_id=phase_id,
        ordinal=ordinal,
        execution_class="COGNITIVE",
        capability_classes=("LEGACY_SAFE_PHASE",),
        effect_ceiling="NONE",
        binding_mode="DYNAMIC",
        on_missing_capability="WAIT_AND_DISCOVER",
        auto_resume=True,
        verify_before_mutate=True,
        currentness_requirements=(),
        evidence_requirements=(),
        completion_predicates=(),
        contract_source="LEGACY_INFERRED_SAFE",
    ).validate()


def compile_panel_phase_contracts(
    pairs: Mapping[str, str],
    mission_id: str,
    phases: Sequence[Mapping[str, Any]],
    control_language: str,
) -> tuple[PhaseExecutionContract, ...]:
    """Compile Mission-Control key/value LPCL phase contracts.

    LPCL/1.1 remains fail-closed compatible and receives non-effectful legacy
    contracts. LPCL/1.2 requires an explicit contract for every phase.
    """
    if control_language not in {"LPCL/1.1", "LPCL/1.2"}:
        raise PhaseExecutionContractError("unsupported CONTROL_LANGUAGE")
    result: list[PhaseExecutionContract] = []
    for ordinal, phase in enumerate(phases, 1):
        phase_id = str(phase["id"])
        if control_language == "LPCL/1.1":
            result.append(_legacy_safe_contract(mission_id, phase_id, ordinal))
            continue
        prefix = f"PHASE_{ordinal:02d}"
        required = {
            "EXECUTION_CLASS", "CAPABILITY_CLASS", "EFFECT_CEILING", "BINDING_MODE",
            "ON_MISSING_CAPABILITY", "AUTO_RESUME", "VERIFY_BEFORE_MUTATE",
            "CURRENTNESS", "EVIDENCE",
        }
        missing = [name for name in sorted(required) if not str(pairs.get(prefix + "_" + name, "")).strip()]
        completion = _completion_values(pairs, prefix)
        if not completion:
            missing.append("COMPLETION_NN")
        if missing:
            raise PhaseExecutionContractError(f"{prefix} missing execution contract fields: {','.join(missing)}")
        contract = PhaseExecutionContract(
            mission_id=mission_id,
            phase_id=phase_id,
            ordinal=ordinal,
            execution_class=str(pairs[prefix + "_EXECUTION_CLASS"]).strip().upper(),
            capability_classes=_tokens(pairs[prefix + "_CAPABILITY_CLASS"]),
            effect_ceiling=str(pairs[prefix + "_EFFECT_CEILING"]).strip().upper(),
            binding_mode=str(pairs[prefix + "_BINDING_MODE"]).strip().upper(),
            on_missing_capability=str(pairs[prefix + "_ON_MISSING_CAPABILITY"]).strip().upper(),
            auto_resume=_bool(pairs[prefix + "_AUTO_RESUME"], prefix + "_AUTO_RESUME"),
            verify_before_mutate=_bool(pairs[prefix + "_VERIFY_BEFORE_MUTATE"], prefix + "_VERIFY_BEFORE_MUTATE"),
            currentness_requirements=_tokens(pairs[prefix + "_CURRENTNESS"]),
            evidence_requirements=_tokens(pairs[prefix + "_EVIDENCE"]),
            completion_predicates=completion,
            contract_source="DECLARED",
        ).validate()
        result.append(contract)
    return tuple(result)


def compile_canonical_run_phase_contract(
    *, mission_id: str, phase_id: str, ordinal: int, fields: Mapping[str, Sequence[str]], lpcl_version: str
) -> PhaseExecutionContract:
    if lpcl_version == "1.1":
        return _legacy_safe_contract(mission_id, phase_id, ordinal)
    if lpcl_version != "1.2":
        raise PhaseExecutionContractError("unsupported LPCL_VERSION")
    def one(name: str) -> str:
        values = tuple(str(x).strip() for x in fields.get(name, ()) if str(x).strip())
        if len(values) != 1:
            raise PhaseExecutionContractError(f"{name} must contain exactly one value")
        return values[0]
    completion = tuple(str(x).strip() for x in fields.get("COMPLETION", ()) if str(x).strip())
    if not completion:
        raise PhaseExecutionContractError("COMPLETION is required for LPCL 1.2")
    return PhaseExecutionContract(
        mission_id=mission_id,
        phase_id=phase_id,
        ordinal=ordinal,
        execution_class=one("EXECUTION_CLASS").upper(),
        capability_classes=tuple(str(x).strip() for x in fields.get("CAPABILITY_CLASS", ()) if str(x).strip()),
        effect_ceiling=one("EFFECT_CEILING").upper(),
        binding_mode=one("BINDING_MODE").upper(),
        on_missing_capability=one("ON_MISSING_CAPABILITY").upper(),
        auto_resume=_bool(one("AUTO_RESUME"), "AUTO_RESUME"),
        verify_before_mutate=_bool(one("VERIFY_BEFORE_MUTATE"), "VERIFY_BEFORE_MUTATE"),
        currentness_requirements=tuple(str(x).strip() for x in fields.get("CURRENTNESS_CONTRACT", ()) if str(x).strip()),
        evidence_requirements=tuple(str(x).strip() for x in fields.get("EVIDENCE_CONTRACT", ()) if str(x).strip()),
        completion_predicates=completion,
        contract_source="DECLARED",
    ).validate()


def preflight_execution_contracts(
    contracts: Sequence[PhaseExecutionContract],
    capability_registry: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> ExecutionPreflight:
    registry = capability_registry or {}
    phases: list[dict[str, Any]] = []
    bound = dynamic = unbound = invalid = 0
    authority_ok = currentness_ok = evidence_ok = True
    for contract in contracts:
        try:
            contract.validate()
        except PhaseExecutionContractError as exc:
            invalid += 1
            phases.append({"phase_id": contract.phase_id, "state": "INVALID", "reason": str(exc)})
            continue
        capability_matches: list[Mapping[str, Any]] = []
        for cls in contract.capability_classes:
            for item in registry.get(cls, ()):
                max_effect = str(item.get("effect_ceiling") or "NONE")
                if max_effect not in _EFFECT_ORDER:
                    continue
                if _EFFECT_ORDER[max_effect] <= _EFFECT_ORDER[contract.effect_ceiling]:
                    capability_matches.append(item)
        if contract.contract_source == "LEGACY_INFERRED_SAFE":
            state = "LEGACY_INFERRED_SAFE"
            dynamic += 1
            unbound += 1
        elif capability_matches:
            state = "VALID_BOUND"
            bound += 1
            if contract.binding_mode == "DYNAMIC":
                dynamic += 1
        elif contract.binding_mode == "DYNAMIC" and contract.on_missing_capability in {"WAIT", "WAIT_AND_DISCOVER", "ESCALATE"}:
            state = "VALID_UNBOUND_WAITING"
            dynamic += 1
            unbound += 1
        else:
            state = "INVALID"
            invalid += 1
        authority_ok = authority_ok and bool(contract.effect_ceiling)
        currentness_ok = currentness_ok and (bool(contract.currentness_requirements) or contract.contract_source == "LEGACY_INFERRED_SAFE")
        evidence_ok = evidence_ok and (bool(contract.evidence_requirements) or contract.execution_class == "COGNITIVE" or contract.contract_source == "LEGACY_INFERRED_SAFE")
        phases.append({
            "phase_id": contract.phase_id,
            "contract_digest": contract.contract_digest,
            "contract_source": contract.contract_source,
            "state": state,
            "binding_mode": contract.binding_mode,
            "capability_classes": list(contract.capability_classes),
            "matching_capabilities": [str(x.get("capability_id")) for x in capability_matches],
            "effect_ceiling": contract.effect_ceiling,
        })
    if invalid:
        readiness = "INVALID"
    elif unbound and bound:
        readiness = "VALID_WITH_DYNAMIC_BINDING"
    elif unbound:
        readiness = "WAITING_FOR_CAPABILITIES"
    elif contracts:
        readiness = "READY_BOUND"
    else:
        readiness = "INVALID"
    capability_closure = "INVALID" if invalid else ("PARTIAL" if unbound else "PASS")
    return ExecutionPreflight(
        phase_count=len(contracts),
        contract_count=len(contracts),
        bound_count=bound,
        dynamic_count=dynamic,
        unbound_count=unbound,
        invalid_count=invalid,
        authority_closure="PASS" if authority_ok and not invalid else "FAIL",
        currentness_closure="PASS" if currentness_ok and not invalid else "PARTIAL" if not invalid else "FAIL",
        evidence_closure="PASS" if evidence_ok and not invalid else "PARTIAL" if not invalid else "FAIL",
        capability_closure=capability_closure,
        mission_readiness=readiness,
        phases=tuple(phases),
    )


def migrated_explicit_contract(
    *, mission_id: str, phase_id: str, ordinal: int, execution_class: str,
    capability_classes: Sequence[str], effect_ceiling: str, binding_mode: str,
    on_missing_capability: str, auto_resume: bool, verify_before_mutate: bool,
    currentness_requirements: Sequence[str], evidence_requirements: Sequence[str],
    completion_predicates: Sequence[str],
) -> PhaseExecutionContract:
    return PhaseExecutionContract(
        mission_id=mission_id, phase_id=phase_id, ordinal=ordinal,
        execution_class=execution_class, capability_classes=tuple(capability_classes),
        effect_ceiling=effect_ceiling, binding_mode=binding_mode,
        on_missing_capability=on_missing_capability, auto_resume=auto_resume,
        verify_before_mutate=verify_before_mutate,
        currentness_requirements=tuple(currentness_requirements),
        evidence_requirements=tuple(evidence_requirements),
        completion_predicates=tuple(completion_predicates),
        contract_source="MIGRATED_EXPLICIT",
    ).validate()

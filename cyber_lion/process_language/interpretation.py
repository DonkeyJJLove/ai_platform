"""One fail-closed interpretation entrypoint for LION process-language sources.

The interpreter classifies source syntax and returns semantic candidates. It is
non-effectful and never turns process text into authority or execution.
"""
from __future__ import annotations

from dataclasses import dataclass

from cyber_lion.contracts.process_ir import CanonicalProcessIR
from cyber_lion.process_language.canonical_run import (
    CanonicalRunCompilation,
    CanonicalRunError,
    compile_canonical_run,
    parse_canonical_run,
)
from cyber_lion.process_language.fleet_mission import FleetMissionIR
from cyber_lion.process_language.legacy_run import LegacyRunAdapter, LegacyRunResult
from cyber_lion.process_language.lpcl import LPCLParseError, parse_lpcl

SURFACE_CLASSES = frozenset({
    "LPCL_1_0_STRICT",
    "LPCL_1_1_CANONICAL_RUN",
    "LEGACY_RUN_DATA",
    "UNREPRESENTABLE",
})
_REQUIRED_V11_PROFILE = frozenset({"TERMINATION", "LINEAGE"})
_NON_EFFECT_CONTROLS = ("AUTHORITY_EFFECT", "RUNTIME_EFFECT", "EXECUTION_EFFECT", "EFFECT_PROVIDER_EFFECT")


class ProcessSourceInterpretationError(ValueError):
    pass


@dataclass(frozen=True)
class ProcessSourceInterpretation:
    surface_class: str
    process_ir: CanonicalProcessIR | None
    fleet_mission_ir: FleetMissionIR | None
    legacy: LegacyRunResult | None
    process_candidate: bool
    authority_effect: str = "NONE"
    runtime_effect: str = "NONE"
    execution_effect: str = "NONE"

    def validate(self) -> "ProcessSourceInterpretation":
        if self.surface_class not in SURFACE_CLASSES:
            raise ProcessSourceInterpretationError("surface_class invalid")
        if (self.authority_effect, self.runtime_effect, self.execution_effect) != ("NONE", "NONE", "NONE"):
            raise ProcessSourceInterpretationError("process source interpretation must remain non-effectful")
        if self.surface_class == "LPCL_1_1_CANONICAL_RUN":
            if self.process_ir is None or self.fleet_mission_ir is None or not self.process_candidate:
                raise ProcessSourceInterpretationError("LPCL 1.1 requires ProcessIR and FleetMissionIR candidate")
        elif self.surface_class == "LPCL_1_0_STRICT":
            if self.process_ir is None or self.fleet_mission_ir is not None or not self.process_candidate:
                raise ProcessSourceInterpretationError("LPCL 1.0 requires ProcessIR-only compatibility candidate")
        else:
            if self.process_ir is not None or self.fleet_mission_ir is not None or self.process_candidate:
                raise ProcessSourceInterpretationError("legacy/unrepresentable source cannot be a process candidate")
        return self


def _looks_like_versioned_run(text: str) -> bool:
    return "RUN=" in text and "LPCL_VERSION=" in text


def _one(values: tuple[str, ...] | None, name: str) -> str:
    if values is None or len(values) != 1 or not values[0]:
        raise ProcessSourceInterpretationError(f"{name} must contain exactly one non-empty value")
    return values[0]


def _validate_v11_profile(text: str) -> None:
    try:
        ast = parse_canonical_run(text)
    except CanonicalRunError as exc:
        raise ProcessSourceInterpretationError(str(exc)) from exc
    missing = sorted(_REQUIRED_V11_PROFILE - set(ast.globals))
    if missing:
        raise ProcessSourceInterpretationError(f"missing required v1.1 profile fields: {missing}")
    termination = _one(ast.globals.get("TERMINATION"), "TERMINATION")
    if termination != "COMPLETE_ON_DONE":
        raise ProcessSourceInterpretationError("TERMINATION must be COMPLETE_ON_DONE")
    if not tuple(item for item in ast.globals.get("LINEAGE", ()) if item):
        raise ProcessSourceInterpretationError("LINEAGE must not be empty")
    for key in _NON_EFFECT_CONTROLS:
        values = ast.globals.get(key)
        if values is None:
            values = ast.global_annotations.get(key)
        if values is not None and _one(values, key) != "NONE":
            raise ProcessSourceInterpretationError(f"{key} must be NONE")


def interpret_process_source(text: str) -> ProcessSourceInterpretation:
    if type(text) is not str:
        raise ProcessSourceInterpretationError("process source must be text")

    if text.lstrip().startswith("LPCL 1.0"):
        try:
            process_ir = parse_lpcl(text)
        except LPCLParseError as exc:
            raise ProcessSourceInterpretationError(str(exc)) from exc
        return ProcessSourceInterpretation(
            surface_class="LPCL_1_0_STRICT",
            process_ir=process_ir,
            fleet_mission_ir=None,
            legacy=None,
            process_candidate=True,
        ).validate()

    if _looks_like_versioned_run(text):
        _validate_v11_profile(text)
        try:
            compiled: CanonicalRunCompilation = compile_canonical_run(text)
        except CanonicalRunError as exc:
            raise ProcessSourceInterpretationError(str(exc)) from exc
        return ProcessSourceInterpretation(
            surface_class="LPCL_1_1_CANONICAL_RUN",
            process_ir=compiled.process_ir,
            fleet_mission_ir=compiled.fleet_mission_ir,
            legacy=None,
            process_candidate=True,
        ).validate()

    legacy = LegacyRunAdapter().parse(text)
    if legacy.classification == "UNREPRESENTABLE":
        return ProcessSourceInterpretation(
            surface_class="UNREPRESENTABLE",
            process_ir=None,
            fleet_mission_ir=None,
            legacy=legacy,
            process_candidate=False,
        ).validate()
    return ProcessSourceInterpretation(
        surface_class="LEGACY_RUN_DATA",
        process_ir=None,
        fleet_mission_ir=None,
        legacy=legacy,
        process_candidate=False,
    ).validate()

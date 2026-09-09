"""Derived LPCL process-orchestration projection for LION architecture v1.4.

The projection is descriptive and non-authoritative. It binds the integrated
CanonicalProcessIR to the v1.1 candidate FleetMissionIR without creating a new
PDP, RuntimeAdmission engine or effect provider.
"""
from __future__ import annotations

from dataclasses import dataclass

PROCESS_ORCHESTRATION_CHAIN = (
    "INTENT_OR_GOAL",
    "LPCL_CANONICAL_SURFACE",
    "CANONICAL_RUN_AST",
    "CANONICAL_PROCESS_IR",
    "FLEET_MISSION_IR",
    "BOUNDED_ROLE_ROUTING",
    "ACTION_INTENT_IF_REQUIRED",
    "EXISTING_AUTHORITY_DECISION",
    "EXISTING_RUNTIME_ADMISSION",
    "EXISTING_EFFECT_BOUNDARY",
    "INDEPENDENT_OBSERVATION",
    "RECONCILIATION",
)

FLEET_MISSION_CLASSES = ("LOGICAL", "LOCAL", "HYBRID")
ARCHITECTURE_LAYER_BINDINGS = (
    ("LPCL_CANONICAL_SURFACE", "EVOLUTIONARY_EPOCH"),
    ("CANONICAL_RUN_AST", "EVOLUTIONARY_EPOCH"),
    ("CANONICAL_PROCESS_IR", "EVOLUTIONARY_EPOCH"),
    ("FLEET_MISSION_IR", "FLEET_AND_SWARM"),
    ("BOUNDED_ROLE_ROUTING", "FLEET_AND_SWARM"),
    ("ACTION_INTENT_IF_REQUIRED", "GOVERNED_SELF_IMPLEMENTATION"),
    ("EXISTING_AUTHORITY_DECISION", "AUTHORITY_AND_EFFECT"),
    ("EXISTING_RUNTIME_ADMISSION", "TRUSTED_RUNTIME"),
    ("EXISTING_EFFECT_BOUNDARY", "AUTHORITY_AND_EFFECT"),
    ("INDEPENDENT_OBSERVATION", "OBSERVABILITY_AND_RECONCILIATION"),
    ("RECONCILIATION", "OBSERVABILITY_AND_RECONCILIATION"),
)


@dataclass(frozen=True)
class ProcessOrchestrationProjection:
    chain: tuple[str, ...] = PROCESS_ORCHESTRATION_CHAIN
    fleet_mission_classes: tuple[str, ...] = FLEET_MISSION_CLASSES
    layer_bindings: tuple[tuple[str, str], ...] = ARCHITECTURE_LAYER_BINDINGS
    process_contract: str = "cyber_lion/contracts/process_ir.py:CanonicalProcessIR"
    surface_contract: str = "cyber_lion/process_language/canonical_run.py:compile_canonical_run"
    fleet_contract: str = "cyber_lion/process_language/fleet_mission.py:FleetMissionIR"
    authority_effect: str = "NONE"
    runtime_effect: str = "NONE"
    effect_provider_effect: str = "NONE"
    adds_top_level_layer: bool = False

    def validate(self) -> "ProcessOrchestrationProjection":
        if self.chain != PROCESS_ORCHESTRATION_CHAIN:
            raise ValueError("process orchestration chain is not canonical")
        if self.fleet_mission_classes != FLEET_MISSION_CLASSES:
            raise ValueError("fleet mission classes are not canonical")
        if self.layer_bindings != ARCHITECTURE_LAYER_BINDINGS:
            raise ValueError("architecture layer bindings are not canonical")
        if len(dict(self.layer_bindings)) != len(self.layer_bindings):
            raise ValueError("process orchestration layer bindings must be unique")
        if (self.authority_effect, self.runtime_effect, self.effect_provider_effect) != ("NONE", "NONE", "NONE"):
            raise ValueError("process orchestration projection must remain non-authoritative and non-effectful")
        if self.adds_top_level_layer:
            raise ValueError("process orchestration projection must preserve the existing top-level layer set")
        return self


def canonical_process_orchestration_projection() -> ProcessOrchestrationProjection:
    return ProcessOrchestrationProjection().validate()

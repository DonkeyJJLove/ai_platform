from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json


@dataclass(frozen=True, order=True)
class GapRecord:
    target_id: str
    status: str
    missing_contract: str = ""
    missing_runtime: str = ""
    missing_observation: str = ""
    missing_authority_boundary: str = ""
    missing_complete_mediation: str = ""
    next_minimal_gap: str = ""

    def validate(self) -> "GapRecord":
        if not self.target_id.strip() or not self.status.strip():
            raise ValueError("gap target_id and status are required")
        return self

    def digest(self) -> str:
        payload = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(b"LION/UML/GAP/1\0" + payload).hexdigest()


def classify_historical_projection(*, observed_commit: str, current_commit: str) -> str:
    if observed_commit == current_commit:
        return "VERIFIED_REFERENCE"
    return "SUPERSEDED"


def canonical_target_gaps() -> tuple[GapRecord, ...]:
    return (
        GapRecord("GoalContract", "TARGET_ONLY", missing_contract="canonical domain-independent root goal contract", next_minimal_gap="define GoalContract").validate(),
        GapRecord("WorldSnapshot", "TARGET_ONLY", missing_contract="canonical world-state snapshot", next_minimal_gap="define source-bound WorldSnapshot").validate(),
        GapRecord("SystemSnapshot", "TARGET_ONLY", missing_contract="canonical machine-readable system-state snapshot", next_minimal_gap="define SystemSnapshot").validate(),
        GapRecord("Gap", "TARGET_ONLY", missing_contract="canonical WORLD/SYSTEM/GOAL difference contract", next_minimal_gap="define Gap contract").validate(),
        GapRecord("BeanSpec", "TARGET_ONLY", missing_contract="domain-independent evolvable capability unit", next_minimal_gap="define immutable BeanSpec").validate(),
        GapRecord("BeanCandidate", "TARGET_ONLY", missing_contract="exact BeanSpec-to-implementation binding", next_minimal_gap="define BeanCandidate").validate(),
        GapRecord("BeanInstance", "TARGET_ONLY", missing_runtime="heterogeneous canonical Bean lifecycle", next_minimal_gap="define BeanInstance after candidate contract").validate(),
        GapRecord("CompositionContract", "TARGET_ONLY", missing_contract="generic Bean composition contract", next_minimal_gap="define CompositionContract").validate(),
        GapRecord("CompositionEngine", "TARGET_ONLY", missing_runtime="generic capability/authority/epistemic-aware composition engine", next_minimal_gap="implement deterministic composition after contract").validate(),
        GapRecord("GlobalCompleteMediation", "UNKNOWN", missing_complete_mediation="repository/runtime reference implementations do not prove system-wide coverage", next_minimal_gap="enumerate consequential effect surfaces").validate(),
    )

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json

from .status import IMPLEMENTATION_STATUSES, require_closed_status


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
        require_closed_status(self.status)
        return self

    def digest(self) -> str:
        self.validate()
        payload = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(b"LION/UML/GAP/1\0" + payload).hexdigest()


def transition_gap_status(
    record: GapRecord,
    *,
    new_status: str,
    evidence_class: str = "",
    evidence_ref: str = "",
) -> GapRecord:
    record.validate()
    require_closed_status(new_status)
    if record.status == "UNKNOWN" and new_status != "UNKNOWN":
        if evidence_class not in {"LIVE_CODE", "CURRENT_TEST", "EXACT_GIT_STATE", "MACHINE_EVIDENCE"}:
            raise ValueError("UNKNOWN gap promotion requires explicit observed evidence class")
        if not evidence_ref.strip():
            raise ValueError("UNKNOWN gap promotion requires explicit evidence_ref")
    if new_status == "TARGET_ONLY" and record.status not in {"TARGET_ONLY", "UNKNOWN"}:
        raise ValueError("implemented gap cannot be silently demoted to TARGET_ONLY")
    return replace(record, status=new_status).validate()


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

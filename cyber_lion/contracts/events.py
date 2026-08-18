"""Cyber-Lion event envelope and cross-system invariants."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

EVENT_TYPES = {
    "ObservationCreated",
    "DeltaDetected",
    "StructureExtracted",
    "HypothesisGenerated",
    "HypothesisUpdated",
    "EvidenceAttached",
    "AnomalyDetected",
    "SimulationRequested",
    "SimulationCompleted",
    "DecisionProposed",
    "GateRequested",
    "GateApplied",
    "ActionAuthorized",
    "ActionExecuted",
    "OutcomeObserved",
    "MemoryCandidateCreated",
    "MemoryCommitted",
    "AuthorityDegraded",
    "ArtifactSuperseded",
    "ReplayRequested",
    "ReplayCompleted",
}

EPISTEMIC_STATES = {"UNKNOWN", "UNDERSTOOD", "FORMALISED"}


class EventValidationError(ValueError):
    """Raised when a cross-system event violates a Cyber-Lion invariant."""


@dataclass(frozen=True)
class Provenance:
    epistemic_status: str
    upstream: List[str] = field(default_factory=list)
    transformation_chain: List[str] = field(default_factory=list)
    content_hash: Optional[str] = None

    def validate(self) -> "Provenance":
        if not self.epistemic_status:
            raise EventValidationError("epistemic_status is required")
        if self.epistemic_status == "DERIVED" and not self.upstream:
            raise EventValidationError("DERIVED provenance requires upstream evidence")
        return self


@dataclass(frozen=True)
class Authority:
    requested: str = "none"
    effective: str = "none"
    policy_ids: List[str] = field(default_factory=list)
    gate_event_id: Optional[str] = None

    def validate(self) -> "Authority":
        if not self.requested or not self.effective:
            raise EventValidationError("requested/effective authority must be explicit")
        return self


@dataclass(frozen=True)
class EventEnvelope:
    schema_version: str
    event_id: str
    event_type: str
    occurred_at: str
    correlation_id: str
    entity: Dict[str, Any]
    source: Dict[str, Any]
    provenance: Provenance
    authority: Authority
    epistemic_state: str
    payload: Dict[str, Any]
    causation_id: Optional[str] = None

    def validate(self) -> "EventEnvelope":
        if self.schema_version != "1.0.0":
            raise EventValidationError("unsupported schema_version")
        if not self.event_id:
            raise EventValidationError("event_id is required")
        if self.event_type not in EVENT_TYPES:
            raise EventValidationError("unsupported event_type")
        if not self.occurred_at:
            raise EventValidationError("occurred_at is required")
        if not self.correlation_id:
            raise EventValidationError("correlation_id is required")
        if not isinstance(self.entity, dict) or not self.entity.get("entity_id"):
            raise EventValidationError("cross-system event requires entity identity")
        if self.epistemic_state not in EPISTEMIC_STATES:
            raise EventValidationError("invalid epistemic_state")

        self.provenance.validate()
        self.authority.validate()

        if self.event_type == "ActionExecuted":
            consequential = bool(self.payload.get("consequential", True))
            if consequential and not self.authority.gate_event_id:
                raise EventValidationError(
                    "consequential ActionExecuted requires applied gate_event_id"
                )

        if self.event_type == "MemoryCommitted":
            if not self.authority.policy_ids:
                raise EventValidationError("MemoryCommitted requires policy_ids")
            if not self.provenance.upstream:
                raise EventValidationError("MemoryCommitted requires upstream provenance")
            if not self.payload.get("candidate_event_id"):
                raise EventValidationError("MemoryCommitted requires candidate_event_id")

        if self.event_type == "AuthorityDegraded":
            if self.authority.effective == self.authority.requested:
                raise EventValidationError(
                    "AuthorityDegraded must reduce or alter effective authority"
                )

        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)

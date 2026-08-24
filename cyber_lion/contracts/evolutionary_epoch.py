"""Contracts for projecting evolutionary R&D state into events, graph evidence, and epoch state."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Tuple

SCHEMA_VERSION = "1.0.0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")

RND_RECORD_TYPES = frozenset({
    "EvidenceObservation", "Hypothesis", "SimulationPlan", "ExperimentResult",
    "FalsificationResult", "PromotionDecision", "RnDMemoryRecord", "EvolutionDelta",
    "Supersession",
})
RND_EVENT_TYPES = frozenset({
    "ObservationCreated", "EvidenceAttached", "HypothesisGenerated", "HypothesisUpdated",
    "SimulationRequested", "SimulationCompleted", "DecisionProposed",
    "MemoryCandidateCreated", "MemoryCommitted", "DeltaDetected", "ArtifactSuperseded",
})
GRAPH_NODE_TYPES = frozenset({"EVIDENCE", "ARTIFACT", "OBSERVATION"})
GRAPH_EDGE_TYPES = frozenset({
    "DERIVED_FROM", "SUPPORTS", "CONTRADICTS", "OBSERVED_FROM", "SUPERSEDES",
    "CORRELATED_WITH", "CAUSED_BY",
})
EPOCH_STATES = frozenset({
    "EPOCH_OPEN", "OBSERVING", "HYPOTHESIS_SPACE_ACTIVE", "TESTING",
    "FALSIFICATION_COMPLETE", "KNOWLEDGE_PROMOTION_READY", "KNOWLEDGE_PROMOTED",
    "MEMORY_COMMITTED", "DELTA_SYNTHESIZED", "NEXT_EPOCH_CANDIDATE_READY",
    "BLOCKED", "UNKNOWN",
})

class EvolutionaryEpochContractError(ValueError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest_payload(domain: bytes, payload: Mapping[str, Any]) -> str:
    return sha256(domain + canonical_json(dict(payload))).hexdigest()


def _text(value: Any, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise EvolutionaryEpochContractError(f"{name} invalid")
    return value


def _id(value: Any, name: str) -> str:
    value = _text(value, name, 256)
    if not _SAFE_ID.fullmatch(value):
        raise EvolutionaryEpochContractError(f"{name} invalid")
    return value


def _digest(value: Any, name: str) -> str:
    value = _text(value, name, 64)
    if not _SHA256.fullmatch(value):
        raise EvolutionaryEpochContractError(f"{name} must be sha256 hex")
    return value


def _refs(value: Any, name: str, nonempty: bool = False) -> Tuple[str, ...]:
    if type(value) is not tuple or (nonempty and not value):
        raise EvolutionaryEpochContractError(f"{name} must be tuple")
    for item in value:
        _text(item, name, 1024)
    if len(value) != len(set(value)):
        raise EvolutionaryEpochContractError(f"{name} must be unique")
    return value


@dataclass(frozen=True)
class RnDEventProjection:
    projection_id: str
    record_type: str
    record_id: str
    record_digest: str
    event_id: str
    event_type: str
    correlation_id: str
    causation_id: str | None
    epistemic_state: str
    provenance_refs: Tuple[str, ...]
    authority_requested: str = "none"
    authority_effective: str = "none"
    projection_digest: str = ""
    schema_version: str = SCHEMA_VERSION

    def canonical_payload(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("projection_digest")
        data["provenance_refs"] = list(self.provenance_refs)
        return data

    def compute_digest(self) -> str:
        return _digest_payload(b"LION/E004-RND-EVENT-PROJECTION/1\0", self.canonical_payload())

    def validate(self):
        if self.schema_version != SCHEMA_VERSION:
            raise EvolutionaryEpochContractError("unsupported event projection schema")
        for name in ("projection_id", "record_id", "event_id", "correlation_id"):
            _id(getattr(self, name), name)
        _digest(self.record_digest, "record_digest")
        _refs(self.provenance_refs, "provenance_refs", nonempty=True)
        if self.record_type not in RND_RECORD_TYPES:
            raise EvolutionaryEpochContractError("unsupported R&D record type")
        if self.event_type not in RND_EVENT_TYPES:
            raise EvolutionaryEpochContractError("unsupported R&D event type")
        if self.authority_requested != "none" or self.authority_effective != "none":
            raise EvolutionaryEpochContractError("R&D projection cannot carry authority")
        if self.causation_id is not None:
            _id(self.causation_id, "causation_id")
        if self.projection_digest:
            _digest(self.projection_digest, "projection_digest")
            if self.projection_digest != self.compute_digest():
                raise EvolutionaryEpochContractError("event projection digest mismatch")
        return self

    def sealed(self):
        self.validate()
        return RnDEventProjection(**{**asdict(self), "projection_digest": self.compute_digest()}).validate()


@dataclass(frozen=True)
class RnDGraphProjection:
    projection_id: str
    record_type: str
    record_id: str
    record_digest: str
    event_id: str
    node_id: str
    node_type: str
    edge_ids: Tuple[str, ...]
    edge_types: Tuple[str, ...]
    provenance_refs: Tuple[str, ...]
    projection_digest: str = ""
    schema_version: str = SCHEMA_VERSION

    def canonical_payload(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("projection_digest")
        for key in ("edge_ids", "edge_types", "provenance_refs"):
            data[key] = list(data[key])
        return data

    def compute_digest(self) -> str:
        return _digest_payload(b"LION/E004-RND-GRAPH-PROJECTION/1\0", self.canonical_payload())

    def validate(self):
        if self.schema_version != SCHEMA_VERSION:
            raise EvolutionaryEpochContractError("unsupported graph projection schema")
        for name in ("projection_id", "record_id", "event_id", "node_id"):
            _id(getattr(self, name), name)
        _digest(self.record_digest, "record_digest")
        if self.record_type not in RND_RECORD_TYPES:
            raise EvolutionaryEpochContractError("unsupported R&D record type")
        if self.node_type not in GRAPH_NODE_TYPES:
            raise EvolutionaryEpochContractError("R&D objects cannot project to authority nodes")
        _refs(self.edge_ids, "edge_ids")
        _refs(self.edge_types, "edge_types")
        _refs(self.provenance_refs, "provenance_refs", nonempty=True)
        if len(self.edge_ids) != len(self.edge_types):
            raise EvolutionaryEpochContractError("graph edge ids/types mismatch")
        if any(edge not in GRAPH_EDGE_TYPES for edge in self.edge_types):
            raise EvolutionaryEpochContractError("unsupported R&D graph edge")
        if self.projection_digest:
            _digest(self.projection_digest, "projection_digest")
            if self.projection_digest != self.compute_digest():
                raise EvolutionaryEpochContractError("graph projection digest mismatch")
        return self

    def sealed(self):
        self.validate()
        return RnDGraphProjection(**{**asdict(self), "projection_digest": self.compute_digest()}).validate()


@dataclass(frozen=True)
class EpochTransition:
    epoch_id: str
    previous_epoch_id: str
    rnd_engine_state_digest: str
    memory_head: str
    promotion_digest: str
    evolution_delta_digest: str
    event_projection_digest: str
    graph_projection_digest: str
    state: str
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    transition_digest: str = ""
    schema_version: str = SCHEMA_VERSION

    def canonical_payload(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("transition_digest")
        return data

    def compute_digest(self) -> str:
        return _digest_payload(b"LION/E004-EPOCH-TRANSITION/1\0", self.canonical_payload())

    def validate(self):
        if self.schema_version != SCHEMA_VERSION:
            raise EvolutionaryEpochContractError("unsupported epoch transition schema")
        _id(self.epoch_id, "epoch_id"); _id(self.previous_epoch_id, "previous_epoch_id")
        for name in (
            "rnd_engine_state_digest", "promotion_digest", "evolution_delta_digest",
            "event_projection_digest", "graph_projection_digest",
        ):
            _digest(getattr(self, name), name)
        if self.memory_head != "GENESIS":
            _digest(self.memory_head, "memory_head")
        if self.state not in EPOCH_STATES:
            raise EvolutionaryEpochContractError("invalid epoch state")
        if self.authority_effect != "NONE" or self.execution_effect != "NONE":
            raise EvolutionaryEpochContractError("epoch transition cannot carry effect authority")
        if self.transition_digest:
            _digest(self.transition_digest, "transition_digest")
            if self.transition_digest != self.compute_digest():
                raise EvolutionaryEpochContractError("transition digest mismatch")
        return self

    def sealed(self):
        self.validate()
        return EpochTransition(**{**asdict(self), "transition_digest": self.compute_digest()}).validate()

"""Deterministic adapter between evolutionary R&D records and existing event/graph/PDP surfaces."""
from __future__ import annotations

from hashlib import sha256
from typing import Dict, Iterable

from cyber_lion.contracts.enterprise_graph import GraphEdge, GraphNode
from cyber_lion.contracts.events import EventEnvelope
from cyber_lion.contracts.policy_gate import GateApplied
from cyber_lion.contracts.evolutionary_rnd import (
    EvidenceObservation, EvolutionDelta, ExperimentResult, FalsificationResult,
    Hypothesis, PromotionDecision, RnDMemoryRecord, SimulationPlan,
)
from cyber_lion.contracts.evolutionary_epoch import (
    EpochTransition, RnDEventProjection, RnDGraphProjection, canonical_json,
)


class EvolutionaryEpochError(RuntimeError):
    pass


_EVENT_MAP = {
    "EvidenceObservation": {"ObservationCreated", "EvidenceAttached"},
    "Hypothesis": {"HypothesisGenerated", "HypothesisUpdated"},
    "SimulationPlan": {"SimulationRequested"},
    "ExperimentResult": {"SimulationCompleted"},
    "FalsificationResult": {"DecisionProposed"},
    "PromotionDecision": {"DecisionProposed"},
    "RnDMemoryRecord": {"MemoryCandidateCreated", "MemoryCommitted"},
    "EvolutionDelta": {"DeltaDetected"},
}
_NODE_MAP = {
    "EvidenceObservation": "EVIDENCE",
    "Hypothesis": "ARTIFACT",
    "SimulationPlan": "ARTIFACT",
    "ExperimentResult": "OBSERVATION",
    "FalsificationResult": "EVIDENCE",
    "PromotionDecision": "ARTIFACT",
    "RnDMemoryRecord": "ARTIFACT",
    "EvolutionDelta": "ARTIFACT",
}
_EPOCH_FORWARD = {
    "EPOCH_OPEN": "OBSERVING",
    "OBSERVING": "HYPOTHESIS_SPACE_ACTIVE",
    "HYPOTHESIS_SPACE_ACTIVE": "TESTING",
    "TESTING": "FALSIFICATION_COMPLETE",
    "FALSIFICATION_COMPLETE": "KNOWLEDGE_PROMOTION_READY",
    "KNOWLEDGE_PROMOTION_READY": "KNOWLEDGE_PROMOTED",
    "KNOWLEDGE_PROMOTED": "MEMORY_COMMITTED",
    "MEMORY_COMMITTED": "DELTA_SYNTHESIZED",
    "DELTA_SYNTHESIZED": "NEXT_EPOCH_CANDIDATE_READY",
    "NEXT_EPOCH_CANDIDATE_READY": None,
    "BLOCKED": None,
    "UNKNOWN": None,
}


class EvolutionaryEpochEngine:
    """Fail-closed, non-effectful integration state machine for one epoch lineage."""

    def __init__(self) -> None:
        self._event_bindings: Dict[str, tuple[str, str]] = {}
        self._record_event_types: Dict[tuple[str, str], set[str]] = {}
        self._memory_candidates: Dict[str, str] = {}
        self._memory_commits: Dict[str, tuple[str, str, int]] = {}
        self._memory_children: Dict[str, str] = {}
        self._epoch_transitions: Dict[str, str] = {}
        self._delta_lineage: Dict[str, str] = {}

    @staticmethod
    def _record_identity(record: object) -> tuple[str, str, str]:
        spec = {
            "EvidenceObservation": ("observation_id", "observation_digest"),
            "Hypothesis": ("hypothesis_id", "hypothesis_digest"),
            "SimulationPlan": ("simulation_id", "simulation_digest"),
            "ExperimentResult": ("result_id", "result_digest"),
            "FalsificationResult": ("falsification_id", "falsification_digest"),
            "PromotionDecision": ("promotion_id", "promotion_digest"),
            "RnDMemoryRecord": ("memory_id", "memory_digest"),
            "EvolutionDelta": ("delta_id", "delta_digest"),
        }
        record_type = type(record).__name__
        if record_type not in spec:
            raise EvolutionaryEpochError("unsupported R&D record type")
        id_attr, digest_attr = spec[record_type]
        record_id = str(getattr(record, id_attr))
        record_digest = str(getattr(record, digest_attr))
        if not record_digest:
            raise EvolutionaryEpochError("R&D record must be sealed")
        return record_type, record_id, record_digest

    def project_event(self, record: object, envelope: EventEnvelope, projection_id: str) -> RnDEventProjection:
        record.validate(); envelope.validate()
        record_type, record_id, record_digest = self._record_identity(record)
        if envelope.event_type not in _EVENT_MAP[record_type]:
            raise EvolutionaryEpochError("event type incompatible with R&D record")
        if envelope.event_type in {"ActionAuthorized", "ActionExecuted"}:
            raise EvolutionaryEpochError("R&D event cannot map to effect event")
        if envelope.authority.requested != "none" or envelope.authority.effective != "none":
            raise EvolutionaryEpochError("R&D event authority must remain none")
        if envelope.entity.get("entity_id") != record_id:
            raise EvolutionaryEpochError("event entity does not bind record identity")
        if envelope.payload.get("record_digest") != record_digest:
            raise EvolutionaryEpochError("event payload digest substitution denied")
        record_provenance = tuple(getattr(record, "provenance_refs", ()))
        if not envelope.provenance.upstream or set(envelope.provenance.upstream) != set(record_provenance):
            raise EvolutionaryEpochError("event provenance does not bind R&D record")
        if record_type == "ExperimentResult":
            if record.result_class != "SIMULATED" or envelope.event_type != "SimulationCompleted":
                raise EvolutionaryEpochError("only SIMULATED result maps to SimulationCompleted")

        binding = (record_type, record_digest)
        prior = self._event_bindings.get(envelope.event_id)
        if prior is not None and prior != binding:
            raise EvolutionaryEpochError("event replay/substitution denied")
        record_key = (record_type, record_digest)
        prior_types = self._record_event_types.setdefault(record_key, set())
        if prior_types and envelope.event_type not in prior_types:
            allowed_pair = record_type == "RnDMemoryRecord" and (
                prior_types | {envelope.event_type}
            ) <= {"MemoryCandidateCreated", "MemoryCommitted"}
            if not allowed_pair:
                raise EvolutionaryEpochError("same record projected under incompatible event type")

        projection = RnDEventProjection(
            projection_id=projection_id,
            record_type=record_type,
            record_id=record_id,
            record_digest=record_digest,
            event_id=envelope.event_id,
            event_type=envelope.event_type,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            epistemic_state=envelope.epistemic_state,
            provenance_refs=tuple(envelope.provenance.upstream),
        ).sealed()
        self._event_bindings[envelope.event_id] = binding
        prior_types.add(envelope.event_type)
        return projection

    def project_graph(self, record: object, event_projection: RnDEventProjection,
                      node: GraphNode, edges: Iterable[GraphEdge], projection_id: str) -> RnDGraphProjection:
        record.validate(); event_projection.validate(); node.validate()
        record_type, record_id, record_digest = self._record_identity(record)
        if (event_projection.record_type, event_projection.record_digest) != (record_type, record_digest):
            raise EvolutionaryEpochError("event projection does not bind graph record")
        if node.node_type != _NODE_MAP[record_type] or node.node_type == "AUTHORITY_RECORD":
            raise EvolutionaryEpochError("R&D record projected to invalid graph node")
        if node.node_id != record_id:
            raise EvolutionaryEpochError("graph node identity mismatch")
        if node.payload.get("record_digest") != record_digest or node.payload.get("event_id") != event_projection.event_id:
            raise EvolutionaryEpochError("graph node record/event binding mismatch")
        if set(node.provenance_refs) != set(event_projection.provenance_refs):
            raise EvolutionaryEpochError("graph provenance binding mismatch")
        edge_list = tuple(edges)
        allowed_edges = {"DERIVED_FROM", "SUPPORTS", "CONTRADICTS", "OBSERVED_FROM", "SUPERSEDES", "CORRELATED_WITH", "CAUSED_BY"}
        for edge in edge_list:
            edge.validate()
            if edge.plane != "DATA_PROVENANCE":
                raise EvolutionaryEpochError("R&D projection cannot create authority-plane edge")
            if edge.edge_type not in allowed_edges:
                raise EvolutionaryEpochError("unsupported R&D graph edge")
            if edge.source_id != node.node_id and edge.target_id != node.node_id:
                raise EvolutionaryEpochError("graph edge not connected to projected node")
        return RnDGraphProjection(
            projection_id=projection_id,
            record_type=record_type,
            record_id=record_id,
            record_digest=record_digest,
            event_id=event_projection.event_id,
            node_id=node.node_id,
            node_type=node.node_type,
            edge_ids=tuple(edge.edge_id for edge in edge_list),
            edge_types=tuple(edge.edge_type for edge in edge_list),
            provenance_refs=tuple(node.provenance_refs),
        ).sealed()

    def bind_memory_candidate(self, record: RnDMemoryRecord, event_projection: RnDEventProjection) -> None:
        record.validate(); event_projection.validate()
        if event_projection.record_type != "RnDMemoryRecord" or event_projection.event_type != "MemoryCandidateCreated":
            raise EvolutionaryEpochError("memory candidate event required")
        if event_projection.record_digest != record.memory_digest:
            raise EvolutionaryEpochError("memory candidate digest mismatch")
        self._memory_candidates[event_projection.event_id] = record.memory_digest

    def bind_memory_commit(self, record: RnDMemoryRecord, candidate_event_id: str,
                           commit_projection: RnDEventProjection, computed_new_head: str) -> None:
        record.validate(); commit_projection.validate()
        if self._memory_candidates.get(candidate_event_id) != record.memory_digest:
            raise EvolutionaryEpochError("MemoryCommitted without matching candidate denied")
        if commit_projection.record_digest != record.memory_digest or commit_projection.event_type != "MemoryCommitted":
            raise EvolutionaryEpochError("memory commit projection mismatch")
        if commit_projection.causation_id != candidate_event_id:
            raise EvolutionaryEpochError("memory commit causation mismatch")
        previous_head = record.previous_memory_head
        existing_child = self._memory_children.get(previous_head)
        if existing_child is not None and existing_child != record.memory_digest:
            raise EvolutionaryEpochError("MEMORY_FORK")
        expected_head = sha256(
            b"LION/E004-RND-MEMORY-CHAIN/1\0" + previous_head.encode("ascii") + record.memory_digest.encode("ascii")
        ).hexdigest()
        if computed_new_head != expected_head:
            raise EvolutionaryEpochError("memory head mismatch")
        if record.memory_digest in self._memory_commits:
            raise EvolutionaryEpochError("duplicate memory commit denied")
        if record.revision > 1 and previous_head == "GENESIS":
            raise EvolutionaryEpochError("skipped memory revision denied")
        self._memory_children[previous_head] = record.memory_digest
        self._memory_commits[record.memory_digest] = (previous_head, computed_new_head, record.revision)

    @staticmethod
    def verify_promotion_gate(decision: PromotionDecision, gate: GateApplied) -> None:
        decision.validate(); gate.validate()
        if gate.decision != "ALLOW":
            raise EvolutionaryEpochError("PDP DENY cannot support knowledge promotion")
        if gate.proposal_id != decision.promotion_id:
            raise EvolutionaryEpochError("promotion/gate proposal binding mismatch")
        expected_ref = f"pdp:{gate.decision_digest}"
        if decision.policy_decision_ref != expected_ref:
            raise EvolutionaryEpochError("promotion PDP decision digest mismatch")

    def transition_epoch(self, current: EpochTransition, next_state: str) -> EpochTransition:
        current.validate()
        if _EPOCH_FORWARD.get(current.state) != next_state:
            raise EvolutionaryEpochError("stale, reverse, or skipped epoch transition denied")
        transitioned = EpochTransition(
            epoch_id=current.epoch_id,
            previous_epoch_id=current.previous_epoch_id,
            rnd_engine_state_digest=current.rnd_engine_state_digest,
            memory_head=current.memory_head,
            promotion_digest=current.promotion_digest,
            evolution_delta_digest=current.evolution_delta_digest,
            event_projection_digest=current.event_projection_digest,
            graph_projection_digest=current.graph_projection_digest,
            state=next_state,
        ).sealed()
        if transitioned.transition_digest in self._epoch_transitions:
            raise EvolutionaryEpochError("duplicate epoch transition denied")
        self._epoch_transitions[transitioned.transition_digest] = next_state
        return transitioned

    def assert_next_epoch_ready(self, transition: EpochTransition, delta: EvolutionDelta,
                                promotion: PromotionDecision, memory_record: RnDMemoryRecord) -> None:
        transition.validate(); delta.validate(); promotion.validate(); memory_record.validate()
        if transition.state != "NEXT_EPOCH_CANDIDATE_READY":
            raise EvolutionaryEpochError("epoch not ready")
        if delta.authority_effect != "NONE" or delta.execution_effect != "NONE":
            raise EvolutionaryEpochError("EvolutionDelta effect assertion denied")
        if transition.evolution_delta_digest != delta.delta_digest:
            raise EvolutionaryEpochError("epoch delta binding mismatch")
        if transition.promotion_digest != promotion.promotion_digest:
            raise EvolutionaryEpochError("epoch promotion binding mismatch")
        if memory_record.memory_digest not in self._memory_commits:
            raise EvolutionaryEpochError("next epoch requires committed R&D memory")
        if "F005" in delta.target_component.upper() or any("F005" in dep.upper() for dep in delta.dependency_ids):
            raise EvolutionaryEpochError("F005 activation reference denied")

    def register_delta_lineage(self, delta: EvolutionDelta, epoch_id: str) -> None:
        delta.validate()
        prior = self._delta_lineage.get(delta.delta_digest)
        if prior is not None and prior != epoch_id:
            raise EvolutionaryEpochError("prior-epoch EvolutionDelta replay denied")
        self._delta_lineage[delta.delta_digest] = epoch_id

    def state_digest(self) -> str:
        payload = {
            "events": sorted((key, value[0], value[1]) for key, value in self._event_bindings.items()),
            "memory_commits": sorted((key, *value) for key, value in self._memory_commits.items()),
            "epoch_transitions": sorted(self._epoch_transitions.items()),
            "delta_lineage": sorted(self._delta_lineage.items()),
        }
        return sha256(b"LION/E004-EPOCH-ENGINE-STATE/1\0" + canonical_json(payload)).hexdigest()


def assert_no_effect_surface() -> None:
    forbidden = {"execute", "deploy", "release", "push", "merge", "delete_ref", "dispatch", "repository_write", "runtime_authority", "activate_agent"}
    public = {name.lower() for name in dir(EvolutionaryEpochEngine) if not name.startswith("_")}
    if public & forbidden:
        raise EvolutionaryEpochError("direct effect surface exposed")

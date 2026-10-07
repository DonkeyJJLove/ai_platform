"""Source-bound project reality and claim projections for LION evolution.

The module composes existing canonical observations instead of creating a second
truth store.  A ProjectRealitySnapshot binds WorldSnapshot/SystemSnapshot
digests, exact Git identity, federation/currentness evidence and the existing
EnterpriseGraph projection.  A ProjectClaimProjection is a read-only view over
existing SemanticAtom and DATA_PROVENANCE graph records.

Reality can feed Dynamic Evolution Fitness only through explicit evidence-bound
gate and pressure observations.  UNKNOWN fails closed.  Nothing in this module
grants authority, schedules work or performs an effect.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import re
from typing import Tuple

from cyber_lion.contracts.enterprise_graph import EnterpriseGraphProjection
from cyber_lion.contracts.evolutionary_state import SystemSnapshot, WorldSnapshot
from cyber_lion.contracts.semantic_relevance import SemanticAtom
from .evolution_fitness import (
    ALL_DIMENSIONS,
    HARD_GATE_FIELDS,
    EvolutionFitnessCandidate,
    EvolutionGateState,
    EvolutionPressure,
)

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

REALITY_STATES = frozenset({"CURRENT", "STALE", "UNKNOWN", "CONFLICTED"})
GATE_OBSERVATION_STATES = frozenset({"PASS", "FAIL", "UNKNOWN"})
PRESSURE_SOURCE_CLASSES = frozenset({
    "OBSERVED_STATE",
    "MEASURED_METRIC",
    "DERIVED_CURRENTNESS",
    "OPERATOR_OBJECTIVE",
})
CLAIM_EDGE_TYPES = frozenset({
    "DERIVED_FROM",
    "SUPPORTS",
    "CONTRADICTS",
    "OBSERVED_FROM",
    "SUPERSEDES",
    "CORRELATED_WITH",
    "CAUSED_BY",
})

_PROJECT_REALITY_DOMAIN = b"LION/PROJECT-REALITY-SNAPSHOT/1\0"
_PROJECT_CLAIM_DOMAIN = b"LION/PROJECT-CLAIM-PROJECTION/1\0"
_CANDIDATE_REALITY_DOMAIN = b"LION/CANDIDATE-REALITY-BINDING/1\0"
_EVOLUTION_REALITY_DOMAIN = b"LION/EVOLUTION-REALITY-CONTEXT/1\0"

_FORBIDDEN_EFFECT_METHODS = frozenset({
    "authorize", "admit", "execute", "write", "push", "merge",
    "deploy", "release", "schedule", "dispatch",
})


class ProjectRealityError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _id(value: str, name: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ProjectRealityError(f"{name} invalid")
    return value


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ProjectRealityError(f"{name} invalid")
    return value


def _sha40(value: str, name: str) -> str:
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise ProjectRealityError(f"{name} must be exact sha40")
    return value


def _sha256(value: str, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ProjectRealityError(f"{name} must be sha256")
    return value


def _sorted_unique(values: Tuple[str, ...], name: str, *, required: bool = False) -> Tuple[str, ...]:
    if type(values) is not tuple or (required and not values):
        raise ProjectRealityError(f"{name} must be {'non-empty ' if required else ''}tuple")
    for value in values:
        _text(value, name)
    if values != tuple(sorted(set(values))):
        raise ProjectRealityError(f"{name} must be sorted unique")
    return values


@dataclass(frozen=True, order=True)
class ProjectSystemSnapshotBinding:
    repository: str
    snapshot_id: str
    snapshot_digest: str

    def validate(self) -> "ProjectSystemSnapshotBinding":
        _text(self.repository, "repository")
        _id(self.snapshot_id, "snapshot_id")
        _sha256(self.snapshot_digest, "snapshot_digest")
        return self


@dataclass(frozen=True)
class ProjectRealitySnapshot:
    snapshot_id: str
    observed_at: str
    epistemic_state: str
    source_repository: str
    source_head: str
    source_tree: str
    world_snapshot_ref: str
    world_snapshot_digest: str
    system_snapshots: Tuple[ProjectSystemSnapshotBinding, ...]
    federation_snapshot_ref: str
    federation_digest: str
    architecture_knowledge_ref: str
    architecture_knowledge_digest: str
    enterprise_graph_ref: str
    enterprise_graph_digest: str
    currentness_refs: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    unknowns: Tuple[str, ...] = ()
    contradictions: Tuple[str, ...] = ()
    snapshot_digest: str = ""
    authority_effect: str = "NONE"
    effect: str = "NONE"

    def payload(self) -> dict:
        data = asdict(self)
        data.pop("snapshot_digest", None)
        return data

    def compute_digest(self) -> str:
        return sha256(_PROJECT_REALITY_DOMAIN + _canonical_bytes(self.payload())).hexdigest()

    def validate(self, *, require_digest: bool = True) -> "ProjectRealitySnapshot":
        _id(self.snapshot_id, "snapshot_id")
        _text(self.observed_at, "observed_at")
        _text(self.source_repository, "source_repository")
        _sha40(self.source_head, "source_head")
        _sha40(self.source_tree, "source_tree")
        _id(self.world_snapshot_ref, "world_snapshot_ref")
        _sha256(self.world_snapshot_digest, "world_snapshot_digest")
        _id(self.federation_snapshot_ref, "federation_snapshot_ref")
        _sha256(self.federation_digest, "federation_digest")
        _id(self.architecture_knowledge_ref, "architecture_knowledge_ref")
        _sha256(self.architecture_knowledge_digest, "architecture_knowledge_digest")
        _id(self.enterprise_graph_ref, "enterprise_graph_ref")
        _sha256(self.enterprise_graph_digest, "enterprise_graph_digest")
        if self.epistemic_state not in REALITY_STATES:
            raise ProjectRealityError("epistemic_state invalid")
        if type(self.system_snapshots) is not tuple or not self.system_snapshots:
            raise ProjectRealityError("system_snapshots required")
        for item in self.system_snapshots:
            item.validate()
        repositories = tuple(item.repository for item in self.system_snapshots)
        if repositories != tuple(sorted(set(repositories))):
            raise ProjectRealityError("system_snapshots must be sorted unique by repository")
        _sorted_unique(self.currentness_refs, "currentness_refs", required=True)
        _sorted_unique(self.evidence_refs, "evidence_refs", required=True)
        _sorted_unique(self.unknowns, "unknowns")
        _sorted_unique(self.contradictions, "contradictions")
        if self.epistemic_state == "CURRENT" and (self.unknowns or self.contradictions):
            raise ProjectRealityError("CURRENT project reality cannot carry unknowns/contradictions")
        if self.epistemic_state == "UNKNOWN" and not self.unknowns:
            raise ProjectRealityError("UNKNOWN project reality requires unknowns")
        if self.epistemic_state == "CONFLICTED" and not self.contradictions:
            raise ProjectRealityError("CONFLICTED project reality requires contradictions")
        if self.authority_effect != "NONE" or self.effect != "NONE":
            raise ProjectRealityError("project reality cannot carry authority/effect")
        if require_digest:
            _sha256(self.snapshot_digest, "snapshot_digest")
            if self.snapshot_digest != self.compute_digest():
                raise ProjectRealityError("snapshot_digest mismatch")
        elif self.snapshot_digest:
            _sha256(self.snapshot_digest, "snapshot_digest")
        return self

    def sealed(self) -> "ProjectRealitySnapshot":
        self.validate(require_digest=False)
        return replace(self, snapshot_digest=self.compute_digest()).validate()


def system_snapshot_from_control_plane_observations(
    *,
    snapshot_id: str,
    observed_at: str,
    captured_at: str,
    freshness_deadline: str,
    repository: str,
    current_head: str,
    current_tree: str,
    observations: dict,
    observation_ref: str,
) -> SystemSnapshot:
    """Normalize existing read-only control-plane reconnaissance evidence.

    This function performs no I/O.  It consumes the already-produced
    lion.control-plane-reconnaissance/v1 observation bundle and derives one
    SystemSnapshot.  Missing required domains remain UNKNOWN; exact source
    substitution becomes CONFLICTED.
    """
    _id(snapshot_id, "snapshot_id")
    _text(observed_at, "observed_at")
    _text(captured_at, "captured_at")
    _text(freshness_deadline, "freshness_deadline")
    _text(repository, "repository")
    _sha40(current_head, "current_head")
    _sha40(current_tree, "current_tree")
    _text(observation_ref, "observation_ref")
    if not isinstance(observations, dict):
        raise ProjectRealityError("control-plane observations must be object")
    if observations.get("schema") != "lion.control-plane-reconnaissance/v1":
        raise ProjectRealityError("unsupported control-plane observation schema")
    domains = observations.get("domains")
    if not isinstance(domains, dict):
        raise ProjectRealityError("control-plane observation domains missing")

    unknowns: list[str] = []
    contradictions: list[str] = []
    facts: dict[str, str] = {}

    panel = domains.get("panel")
    if not isinstance(panel, dict):
        unknowns.append("panel_observation_missing")
    else:
        repo = panel.get("repo") if isinstance(panel.get("repo"), dict) else {}
        github = repo.get("github_master") if isinstance(repo.get("github_master"), dict) else {}
        gh_head, gh_tree = github.get("head"), github.get("tree")
        local_head, local_tree = repo.get("local_head"), repo.get("local_tree")
        if isinstance(gh_head, str):
            facts["github_master_head"] = gh_head
        else:
            unknowns.append("github_master_head_missing")
        if isinstance(gh_tree, str):
            facts["github_master_tree"] = gh_tree
        else:
            unknowns.append("github_master_tree_missing")
        if isinstance(local_head, str):
            facts["runtime_local_head"] = local_head
        if isinstance(local_tree, str):
            facts["runtime_local_tree"] = local_tree
        if gh_head is not None and gh_head != current_head:
            contradictions.append("observed GitHub master head differs from current source identity")
        if gh_tree is not None and gh_tree != current_tree:
            contradictions.append("observed GitHub master tree differs from current source identity")

        thread = panel.get("thread_db") if isinstance(panel.get("thread_db"), dict) else None
        if thread is None:
            unknowns.append("thread_db_observation_missing")
        else:
            facts["thread_db_integrity"] = str(thread.get("integrity") or "UNKNOWN")
            if thread.get("identity_digest"):
                facts["thread_db_identity_digest"] = str(thread["identity_digest"])
            else:
                unknowns.append("thread_db_identity_digest_missing")
            if str(thread.get("integrity") or "").lower() != "ok":
                unknowns.append("thread_db_integrity_not_confirmed")

        saas = panel.get("saas_projection")
        if isinstance(saas, dict):
            if saas.get("transport") is not None:
                facts["saas_transport"] = str(saas.get("transport"))
            if saas.get("pending_count") is not None:
                facts["saas_pending_count"] = str(saas.get("pending_count"))
        else:
            unknowns.append("saas_projection_missing")

    mission_control = domains.get("mission_control")
    if not isinstance(mission_control, dict):
        unknowns.append("mission_control_observation_missing")
    else:
        mission = mission_control.get("mission") if isinstance(mission_control.get("mission"), dict) else {}
        process = mission_control.get("process") if isinstance(mission_control.get("process"), dict) else {}
        db = mission_control.get("db") if isinstance(mission_control.get("db"), dict) else {}
        if mission.get("mission_id") is not None:
            facts["focus_mission_id"] = str(mission.get("mission_id"))
        if mission.get("state") is not None:
            facts["focus_mission_state"] = str(mission.get("state"))
        if mission.get("runtime_state") is not None:
            facts["focus_mission_runtime_state"] = str(mission.get("runtime_state"))
        if mission.get("source_head") is not None:
            facts["focus_mission_source_head"] = str(mission.get("source_head"))
            facts["focus_mission_source_current"] = str(
                mission.get("source_head") == current_head
                and mission.get("source_tree") == current_tree
            ).lower()
        if process.get("current_phase") is not None:
            facts["focus_mission_phase"] = str(process.get("current_phase"))
        if db.get("integrity") is not None:
            facts["mission_control_db_integrity"] = str(db.get("integrity"))

    broker = domains.get("broker")
    if isinstance(broker, dict):
        if broker.get("pending_count") is not None:
            facts["broker_pending_count"] = str(broker.get("pending_count"))
        if broker.get("responded_count") is not None:
            facts["broker_responded_count"] = str(broker.get("responded_count"))
        if broker.get("receipt_count") is not None:
            facts["broker_receipt_count"] = str(broker.get("receipt_count"))
        binding = broker.get("active_binding")
        if isinstance(binding, dict):
            facts["saas_binding_status"] = str(binding.get("status") or "UNKNOWN")
            facts["saas_binding_authority_effect"] = str(binding.get("authority_effect") or "UNKNOWN")

    if contradictions:
        state = "CONFLICTED"
    elif unknowns:
        state = "UNKNOWN"
    else:
        state = "CURRENT"

    observation_digest = sha256(
        b"LION/CONTROL-PLANE-OBSERVATION-NORMALIZATION/1\0"
        + _canonical_bytes(observations)
    ).hexdigest()
    return SystemSnapshot(
        snapshot_id=snapshot_id,
        observed_at=observed_at,
        captured_at=captured_at,
        epistemic_state=state,
        repository=repository,
        revision=current_head,
        tree_digest=current_tree,
        implementation_facts=tuple(sorted(facts.items())),
        test_evidence_refs=(f"control-plane-observation:{observation_digest}",),
        observation_refs=(observation_ref,),
        freshness_deadline=freshness_deadline if state == "CURRENT" else "",
        unknowns=tuple(sorted(set(unknowns))),
        contradictions=tuple(sorted(set(contradictions))),
    ).validate()


def build_project_reality_snapshot(
    *,
    snapshot_id: str,
    observed_at: str,
    epistemic_state: str,
    source_repository: str,
    source_head: str,
    source_tree: str,
    world: WorldSnapshot,
    systems: Tuple[SystemSnapshot, ...],
    federation_snapshot_ref: str,
    federation_digest: str,
    architecture_knowledge_ref: str,
    architecture_knowledge_digest: str,
    enterprise_graph: EnterpriseGraphProjection,
    currentness_refs: Tuple[str, ...],
    evidence_refs: Tuple[str, ...],
    unknowns: Tuple[str, ...] = (),
    contradictions: Tuple[str, ...] = (),
) -> ProjectRealitySnapshot:
    """Compose canonical observations without copying their payloads."""
    world.validate()
    if type(systems) is not tuple or not systems:
        raise ProjectRealityError("systems must be non-empty tuple")
    for system in systems:
        system.validate()
    enterprise_graph.verify_digest()
    bindings = tuple(sorted(
        (
            ProjectSystemSnapshotBinding(
                repository=system.repository,
                snapshot_id=system.snapshot_id,
                snapshot_digest=system.digest(),
            ).validate()
            for system in systems
        ),
        key=lambda item: item.repository,
    ))
    return ProjectRealitySnapshot(
        snapshot_id=snapshot_id,
        observed_at=observed_at,
        epistemic_state=epistemic_state,
        source_repository=source_repository,
        source_head=source_head,
        source_tree=source_tree,
        world_snapshot_ref=world.snapshot_id,
        world_snapshot_digest=world.digest(),
        system_snapshots=bindings,
        federation_snapshot_ref=federation_snapshot_ref,
        federation_digest=federation_digest,
        architecture_knowledge_ref=architecture_knowledge_ref,
        architecture_knowledge_digest=architecture_knowledge_digest,
        enterprise_graph_ref=enterprise_graph.graph_id,
        enterprise_graph_digest=enterprise_graph.projection_digest,
        currentness_refs=currentness_refs,
        evidence_refs=evidence_refs,
        unknowns=unknowns,
        contradictions=contradictions,
    ).sealed()


@dataclass(frozen=True, order=True)
class ClaimAtomBinding:
    atom_id: str
    atom_digest: str
    temporal_state: str
    independent_root_count: int

    def validate(self) -> "ClaimAtomBinding":
        _id(self.atom_id, "atom_id")
        _sha256(self.atom_digest, "atom_digest")
        _text(self.temporal_state, "temporal_state")
        if (
            isinstance(self.independent_root_count, bool)
            or not isinstance(self.independent_root_count, int)
            or self.independent_root_count < 1
        ):
            raise ProjectRealityError("independent_root_count invalid")
        return self


@dataclass(frozen=True)
class ProjectClaimProjection:
    projection_id: str
    project_reality_ref: str
    project_reality_digest: str
    enterprise_graph_ref: str
    enterprise_graph_digest: str
    atom_bindings: Tuple[ClaimAtomBinding, ...]
    graph_node_refs: Tuple[str, ...]
    graph_edge_refs: Tuple[str, ...]
    evidence_root_refs: Tuple[str, ...]
    projection_digest: str = ""
    authority_effect: str = "NONE"
    effect: str = "NONE"

    def payload(self) -> dict:
        data = asdict(self)
        data.pop("projection_digest", None)
        return data

    def compute_digest(self) -> str:
        return sha256(_PROJECT_CLAIM_DOMAIN + _canonical_bytes(self.payload())).hexdigest()

    def validate(self, *, require_digest: bool = True) -> "ProjectClaimProjection":
        _id(self.projection_id, "projection_id")
        _id(self.project_reality_ref, "project_reality_ref")
        _sha256(self.project_reality_digest, "project_reality_digest")
        _id(self.enterprise_graph_ref, "enterprise_graph_ref")
        _sha256(self.enterprise_graph_digest, "enterprise_graph_digest")
        if type(self.atom_bindings) is not tuple or not self.atom_bindings:
            raise ProjectRealityError("atom_bindings required")
        for item in self.atom_bindings:
            item.validate()
        atom_ids = tuple(item.atom_id for item in self.atom_bindings)
        if atom_ids != tuple(sorted(set(atom_ids))):
            raise ProjectRealityError("atom_bindings must be sorted unique by atom_id")
        _sorted_unique(self.graph_node_refs, "graph_node_refs", required=True)
        _sorted_unique(self.graph_edge_refs, "graph_edge_refs")
        _sorted_unique(self.evidence_root_refs, "evidence_root_refs", required=True)
        if self.authority_effect != "NONE" or self.effect != "NONE":
            raise ProjectRealityError("claim projection cannot carry authority/effect")
        if require_digest:
            _sha256(self.projection_digest, "projection_digest")
            if self.projection_digest != self.compute_digest():
                raise ProjectRealityError("claim projection digest mismatch")
        return self

    def sealed(self) -> "ProjectClaimProjection":
        self.validate(require_digest=False)
        return replace(self, projection_digest=self.compute_digest()).validate()


def build_project_claim_projection(
    *,
    projection_id: str,
    reality: ProjectRealitySnapshot,
    graph: EnterpriseGraphProjection,
    atoms: Tuple[SemanticAtom, ...],
    graph_node_refs: Tuple[str, ...],
    graph_edge_refs: Tuple[str, ...],
) -> ProjectClaimProjection:
    """Build a claim view over existing graph/semantic records; no second graph store."""
    reality.validate()
    graph.verify_digest()
    if graph.graph_id != reality.enterprise_graph_ref or graph.projection_digest != reality.enterprise_graph_digest:
        raise ProjectRealityError("enterprise graph substitution denied")
    if type(atoms) is not tuple or not atoms:
        raise ProjectRealityError("atoms required")
    sealed_atoms = tuple(sorted((atom.validate() for atom in atoms), key=lambda atom: atom.atom_id))
    known_nodes = {node.node_id for node in graph.nodes}
    known_edges = {edge.edge_id: edge for edge in graph.edges}
    if not set(graph_node_refs).issubset(known_nodes):
        raise ProjectRealityError("claim node widening denied")
    if not set(graph_edge_refs).issubset(set(known_edges)):
        raise ProjectRealityError("claim edge widening denied")
    for edge_ref in graph_edge_refs:
        edge = known_edges[edge_ref]
        if edge.plane != "DATA_PROVENANCE" or edge.edge_type not in CLAIM_EDGE_TYPES:
            raise ProjectRealityError("claim projection may only use data-provenance evidence edges")
    bindings = tuple(
        ClaimAtomBinding(
            atom_id=atom.atom_id,
            atom_digest=atom.atom_digest,
            temporal_state=atom.temporal_state,
            independent_root_count=atom.independent_root_count(),
        ).validate()
        for atom in sealed_atoms
    )
    roots = tuple(sorted({
        evidence.root_ref
        for atom in sealed_atoms
        for evidence in atom.evidence
    }))
    return ProjectClaimProjection(
        projection_id=projection_id,
        project_reality_ref=reality.snapshot_id,
        project_reality_digest=reality.snapshot_digest,
        enterprise_graph_ref=graph.graph_id,
        enterprise_graph_digest=graph.projection_digest,
        atom_bindings=bindings,
        graph_node_refs=tuple(sorted(graph_node_refs)),
        graph_edge_refs=tuple(sorted(graph_edge_refs)),
        evidence_root_refs=roots,
    ).sealed()


@dataclass(frozen=True, order=True)
class GateObservation:
    candidate_id: str
    gate_name: str
    state: str
    evidence_ref: str
    source_digest: str
    observed_at: str

    def validate(self) -> "GateObservation":
        _id(self.candidate_id, "candidate_id")
        if self.gate_name not in {name for name, _ in HARD_GATE_FIELDS}:
            raise ProjectRealityError("unknown fitness hard gate")
        if self.state not in GATE_OBSERVATION_STATES:
            raise ProjectRealityError("gate observation state invalid")
        _text(self.evidence_ref, "evidence_ref")
        _sha256(self.source_digest, "source_digest")
        _text(self.observed_at, "observed_at")
        return self


@dataclass(frozen=True)
class CandidateRealityBinding:
    candidate_id: str
    project_reality_ref: str
    project_reality_digest: str
    gate_observations: Tuple[GateObservation, ...]
    evidence_refs: Tuple[str, ...]
    binding_digest: str = ""
    authority_effect: str = "NONE"
    effect: str = "NONE"

    def payload(self) -> dict:
        data = asdict(self)
        data.pop("binding_digest", None)
        return data

    def compute_digest(self) -> str:
        return sha256(_CANDIDATE_REALITY_DOMAIN + _canonical_bytes(self.payload())).hexdigest()

    def validate(self, *, require_digest: bool = True) -> "CandidateRealityBinding":
        _id(self.candidate_id, "candidate_id")
        _id(self.project_reality_ref, "project_reality_ref")
        _sha256(self.project_reality_digest, "project_reality_digest")
        if type(self.gate_observations) is not tuple:
            raise ProjectRealityError("gate_observations must be tuple")
        for item in self.gate_observations:
            item.validate()
            if item.candidate_id != self.candidate_id:
                raise ProjectRealityError("gate observation candidate mismatch")
        names = tuple(item.gate_name for item in self.gate_observations)
        required_names = tuple(sorted(name for name, _ in HARD_GATE_FIELDS))
        if names != required_names:
            raise ProjectRealityError("gate observations must cover every hard gate exactly once in sorted order")
        _sorted_unique(self.evidence_refs, "evidence_refs", required=True)
        if self.authority_effect != "NONE" or self.effect != "NONE":
            raise ProjectRealityError("candidate reality binding cannot carry authority/effect")
        if require_digest:
            _sha256(self.binding_digest, "binding_digest")
            if self.binding_digest != self.compute_digest():
                raise ProjectRealityError("candidate reality binding digest mismatch")
        return self

    def sealed(self) -> "CandidateRealityBinding":
        self.validate(require_digest=False)
        return replace(self, binding_digest=self.compute_digest()).validate()


@dataclass(frozen=True, order=True)
class PressureObservation:
    dimension: str
    value: int
    evidence_ref: str
    source_digest: str
    source_class: str
    observed_at: str

    def validate(self) -> "PressureObservation":
        if self.dimension not in ALL_DIMENSIONS:
            raise ProjectRealityError("unknown fitness dimension")
        if isinstance(self.value, bool) or not isinstance(self.value, int) or not 0 <= self.value <= 1000:
            raise ProjectRealityError("pressure value must be integer 0..1000")
        _text(self.evidence_ref, "evidence_ref")
        _sha256(self.source_digest, "source_digest")
        if self.source_class not in PRESSURE_SOURCE_CLASSES:
            raise ProjectRealityError("pressure source_class invalid")
        _text(self.observed_at, "observed_at")
        return self


@dataclass(frozen=True)
class EvolutionRealityContext:
    candidate_id: str
    project_reality_ref: str
    project_reality_digest: str
    candidate_reality_binding_digest: str
    gates: EvolutionGateState
    pressures: Tuple[EvolutionPressure, ...]
    unknown_gates: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    context_digest: str = ""
    authority_effect: str = "NONE"
    effect: str = "NONE"

    def payload(self) -> dict:
        data = asdict(self)
        data.pop("context_digest", None)
        return data

    def compute_digest(self) -> str:
        return sha256(_EVOLUTION_REALITY_DOMAIN + _canonical_bytes(self.payload())).hexdigest()

    def validate(self, *, require_digest: bool = True) -> "EvolutionRealityContext":
        _id(self.candidate_id, "candidate_id")
        _id(self.project_reality_ref, "project_reality_ref")
        _sha256(self.project_reality_digest, "project_reality_digest")
        _sha256(self.candidate_reality_binding_digest, "candidate_reality_binding_digest")
        self.gates.validate()
        if type(self.pressures) is not tuple:
            raise ProjectRealityError("pressures must be tuple")
        for item in self.pressures:
            item.validate()
        dimensions = tuple(item.dimension for item in self.pressures)
        if dimensions != tuple(sorted(set(dimensions))):
            raise ProjectRealityError("pressures must be sorted unique by dimension")
        _sorted_unique(self.unknown_gates, "unknown_gates")
        _sorted_unique(self.evidence_refs, "evidence_refs", required=True)
        if self.authority_effect != "NONE" or self.effect != "NONE":
            raise ProjectRealityError("evolution reality context cannot carry authority/effect")
        if require_digest:
            _sha256(self.context_digest, "context_digest")
            if self.context_digest != self.compute_digest():
                raise ProjectRealityError("evolution reality context digest mismatch")
        return self

    def sealed(self) -> "EvolutionRealityContext":
        self.validate(require_digest=False)
        return replace(self, context_digest=self.compute_digest()).validate()


class ProjectRealityAdapter:
    @classmethod
    def assert_no_effect_surface(cls) -> None:
        for name in _FORBIDDEN_EFFECT_METHODS:
            if hasattr(cls, name):
                raise ProjectRealityError(f"effect surface present: {name}")

    def build_evolution_context(
        self,
        *,
        reality: ProjectRealitySnapshot,
        binding: CandidateRealityBinding,
        pressure_observations: Tuple[PressureObservation, ...] = (),
    ) -> EvolutionRealityContext:
        self.assert_no_effect_surface()
        reality.validate()
        binding.validate()
        if (
            binding.project_reality_ref != reality.snapshot_id
            or binding.project_reality_digest != reality.snapshot_digest
        ):
            raise ProjectRealityError("project reality substitution denied")
        by_name = {item.gate_name: item for item in binding.gate_observations}
        if reality.epistemic_state != "CURRENT" and by_name["source_current"].state == "PASS":
            raise ProjectRealityError("non-current project reality cannot satisfy source_current")
        gates = EvolutionGateState(**{
            name: by_name[name].state == "PASS"
            for name, _ in HARD_GATE_FIELDS
        }).validate()
        unknown_gates = tuple(sorted(
            item.gate_name for item in binding.gate_observations if item.state == "UNKNOWN"
        ))
        if type(pressure_observations) is not tuple:
            raise ProjectRealityError("pressure_observations must be tuple")
        validated_pressures = tuple(sorted(
            (item.validate() for item in pressure_observations),
            key=lambda item: item.dimension,
        ))
        dimensions = tuple(item.dimension for item in validated_pressures)
        if dimensions != tuple(sorted(set(dimensions))):
            raise ProjectRealityError("pressure observations must be unique by dimension")
        pressures = tuple(
            EvolutionPressure(item.dimension, item.value, item.evidence_ref).validate()
            for item in validated_pressures
        )
        evidence_refs = tuple(sorted(set(
            binding.evidence_refs
            + reality.evidence_refs
            + tuple(item.evidence_ref for item in binding.gate_observations)
            + tuple(item.evidence_ref for item in validated_pressures)
        )))
        return EvolutionRealityContext(
            candidate_id=binding.candidate_id,
            project_reality_ref=reality.snapshot_id,
            project_reality_digest=reality.snapshot_digest,
            candidate_reality_binding_digest=binding.binding_digest,
            gates=gates,
            pressures=pressures,
            unknown_gates=unknown_gates,
            evidence_refs=evidence_refs,
        ).sealed()

    def bind_fitness_candidate(
        self,
        *,
        candidate: EvolutionFitnessCandidate,
        context: EvolutionRealityContext,
    ) -> EvolutionFitnessCandidate:
        self.assert_no_effect_surface()
        candidate.validate()
        context.validate()
        if candidate.candidate_id != context.candidate_id:
            raise ProjectRealityError("fitness candidate/reality candidate mismatch")
        evidence = tuple(sorted(set(
            candidate.evidence_refs
            + context.evidence_refs
            + (f"project-reality:{context.project_reality_digest}",)
        )))
        return replace(candidate, gates=context.gates, evidence_refs=evidence).validate()

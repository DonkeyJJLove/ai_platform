"""Read-only canonical PDP context for repository maintenance.

The context composes organizational/evidence state only. It contains no authority,
credential, policy decision, repository mutation, or effect capability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import inspect
import json
from typing import Mapping

from .agent_registry import AgentRegistryStore
from .canonical_lion_status_adapter import adapt_fleet_status
from .canonical_mission_state import CanonicalMissionStore, mission_digest
from .canonical_policy_state import CanonicalPolicyStore
from .enterprise_graph import EnterpriseGraphStore
from .fleet_status_projection import FleetStatusProjector
from .models import AgentSpec, MissionSpec, SwarmSpec
from .planner import SwarmPlanner


class RepositoryMaintenancePDPContextError(RuntimeError):
    pass


def _canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _agent_from(raw: Mapping[str, object]) -> AgentSpec:
    data = dict(raw)
    for key in ("capabilities", "observability_events", "memory_policy_ids"):
        data[key] = tuple(data.get(key, ()))
    try:
        return AgentSpec(**data).validate()
    except Exception as exc:
        raise RepositoryMaintenancePDPContextError("canonical AgentSpec invalid") from exc


def _object_digest(value: object) -> str:
    data = asdict(value)
    for key, item in list(data.items()):
        if isinstance(item, tuple):
            data[key] = list(item)
    return sha256(_canon(data)).hexdigest()


def _agents_digest(agents: Mapping[str, AgentSpec]) -> str:
    payload = []
    for key in sorted(agents):
        spec = agents[key].validate()
        data = asdict(spec)
        for field, item in list(data.items()):
            if isinstance(item, tuple):
                data[field] = list(item)
        payload.append(data)
    return sha256(_canon(payload)).hexdigest()


def _planner_digest() -> str:
    try:
        source = inspect.getsource(SwarmPlanner)
    except (OSError, TypeError) as exc:
        raise RepositoryMaintenancePDPContextError("SwarmPlanner implementation unavailable") from exc
    return sha256(source.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RepositoryMaintenancePDPContext:
    policy_binding: str
    policy_digest: str
    mission_id: str
    mission_revision: int
    mission_digest: str
    agent_registry_id: str
    registry_revision: int
    registry_event_head: str
    registry_projection_digest: str
    planner_implementation_digest: str
    swarm_digest: str
    agents_digest: str
    enterprise_graph_id: str
    graph_revision: int
    graph_event_head: str
    graph_projection_digest: str
    status_digest: str
    fleet_snapshot_digest: str
    observability_state: str
    master: str
    tree: str
    context_digest: str = ""

    def canonical_payload(self) -> dict[str, object]:
        data = asdict(self)
        data.pop("context_digest")
        return data

    def compute_digest(self) -> str:
        return sha256(_canon(self.canonical_payload())).hexdigest()

    def validate(self) -> "RepositoryMaintenancePDPContext":
        text_fields = (
            "policy_binding", "policy_digest", "mission_id", "mission_digest",
            "agent_registry_id", "registry_event_head", "registry_projection_digest",
            "planner_implementation_digest", "swarm_digest", "agents_digest",
            "enterprise_graph_id", "graph_event_head", "graph_projection_digest",
            "status_digest", "fleet_snapshot_digest", "master", "tree",
        )
        if any(not isinstance(getattr(self, field), str) or not getattr(self, field) for field in text_fields):
            raise RepositoryMaintenancePDPContextError("context identity/digest field invalid")
        if self.observability_state not in {"HEALTHY", "DEGRADED", "LOST"}:
            raise RepositoryMaintenancePDPContextError("context observability invalid")
        if not isinstance(self.mission_revision, int) or self.mission_revision < 1:
            raise RepositoryMaintenancePDPContextError("mission revision invalid")
        if not isinstance(self.registry_revision, int) or self.registry_revision < 0:
            raise RepositoryMaintenancePDPContextError("registry revision invalid")
        if not isinstance(self.graph_revision, int) or self.graph_revision < 0:
            raise RepositoryMaintenancePDPContextError("graph revision invalid")
        if self.context_digest and self.context_digest != self.compute_digest():
            raise RepositoryMaintenancePDPContextError("context digest mismatch")
        return self

    def sealed(self) -> "RepositoryMaintenancePDPContext":
        self.validate()
        return RepositoryMaintenancePDPContext(**{**asdict(self), "context_digest": self.compute_digest()}).validate()


@dataclass(frozen=True)
class ResolvedRepositoryMaintenancePDPContext:
    context: RepositoryMaintenancePDPContext
    policy: object
    mission: MissionSpec
    swarm: SwarmSpec
    agents: Mapping[str, AgentSpec]
    graph_projection: object
    lion_status: Mapping[str, object]


class RepositoryMaintenancePDPContextResolver:
    """Capability-reduced resolver over fixed canonical stores/readers."""

    def __init__(
        self,
        *,
        policy_store: CanonicalPolicyStore,
        mission_store: CanonicalMissionStore,
        agent_registry: AgentRegistryStore,
        enterprise_graph: EnterpriseGraphStore,
        fleet_projector: FleetStatusProjector,
        planner: SwarmPlanner,
        policy_id: str,
        mission_id: str,
    ) -> None:
        if not isinstance(policy_store, CanonicalPolicyStore):
            raise RepositoryMaintenancePDPContextError("canonical policy store required")
        if not isinstance(mission_store, CanonicalMissionStore):
            raise RepositoryMaintenancePDPContextError("canonical mission store required")
        if not isinstance(agent_registry, AgentRegistryStore):
            raise RepositoryMaintenancePDPContextError("canonical agent registry required")
        if not isinstance(enterprise_graph, EnterpriseGraphStore):
            raise RepositoryMaintenancePDPContextError("canonical enterprise graph required")
        if not isinstance(fleet_projector, FleetStatusProjector):
            raise RepositoryMaintenancePDPContextError("canonical fleet projector required")
        if not isinstance(planner, SwarmPlanner):
            raise RepositoryMaintenancePDPContextError("canonical swarm planner required")
        if not policy_id or not mission_id:
            raise RepositoryMaintenancePDPContextError("fixed policy/mission identity required")
        self._policy_store = policy_store
        self._mission_store = mission_store
        self._agent_registry = agent_registry
        self._graph = enterprise_graph
        self._fleet = fleet_projector
        self._planner = planner
        self._policy_id = policy_id
        self._mission_id = mission_id

    def resolve(
        self,
        *,
        observed_master: str,
        observed_tree: str,
        exact_master_relation_proven: bool,
    ) -> ResolvedRepositoryMaintenancePDPContext:
        policy = self._policy_store.resolve_current(self._policy_id)
        mission, mission_revision, mission_dg = self._mission_store.resolve_current(self._mission_id)
        if mission.mission_id != self._mission_id or "repository_ref.delete" not in mission.required_capabilities:
            raise RepositoryMaintenancePDPContextError("canonical maintenance mission binding mismatch")
        projection = self._agent_registry.resolve_for_mission(mission).verify_digest()
        swarm = self._planner.plan(mission, projection).validate()
        all_agents = {_agent_from(raw).agent_id: _agent_from(raw) for raw in projection.candidate_specs}
        selected = {agent_id: all_agents[agent_id] for agent_id in swarm.member_agent_ids if agent_id in all_agents}
        if set(selected) != set(swarm.member_agent_ids):
            raise RepositoryMaintenancePDPContextError("canonical swarm member AgentSpec missing")
        graph = self._graph.projection().verify_digest()
        snapshot = self._fleet.snapshot().validate()
        status, observability = adapt_fleet_status(
            snapshot,
            observed_master=observed_master,
            observed_tree=observed_tree,
            exact_master_relation_proven=exact_master_relation_proven,
        )
        context = RepositoryMaintenancePDPContext(
            policy_binding=policy.binding,
            policy_digest=policy.content_digest,
            mission_id=mission.mission_id,
            mission_revision=mission_revision,
            mission_digest=mission_dg,
            agent_registry_id=projection.registry_id,
            registry_revision=projection.revision,
            registry_event_head=projection.event_head,
            registry_projection_digest=projection.resolution_digest,
            planner_implementation_digest=_planner_digest(),
            swarm_digest=_object_digest(swarm),
            agents_digest=_agents_digest(selected),
            enterprise_graph_id=graph.graph_id,
            graph_revision=graph.revision,
            graph_event_head=graph.event_head,
            graph_projection_digest=graph.projection_digest,
            status_digest=str(status["status_digest"]),
            fleet_snapshot_digest=snapshot.snapshot_digest,
            observability_state=observability,
            master=observed_master,
            tree=observed_tree,
        ).sealed()
        return ResolvedRepositoryMaintenancePDPContext(
            context=context,
            policy=policy,
            mission=mission,
            swarm=swarm,
            agents=selected,
            graph_projection=graph,
            lion_status=status,
        )

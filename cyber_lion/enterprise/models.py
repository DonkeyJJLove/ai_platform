"""Formal enterprise contracts for agents, missions, swarms and topology deltas.

These objects define organizational structure and authority ceilings. They do not execute
models or tools and they never grant credentials merely because a specification exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple


class EnterpriseModelError(ValueError):
    """Raised when an enterprise contract violates a deterministic invariant."""


RISK_CLASSES = {"GREEN", "AMBER", "RED"}
AUTHORITY_RANK: Dict[str, int] = {
    "none": 0,
    "read": 1,
    "local_write": 2,
    "external_write": 3,
    "financial": 4,
    "deploy": 4,
    "privileged": 5,
}


def authority_rank(value: str) -> int:
    try:
        return AUTHORITY_RANK[value]
    except KeyError as exc:
        raise EnterpriseModelError(f"unknown authority class: {value}") from exc


@dataclass(frozen=True)
class AgentSpec:
    """Versioned organizational definition of one agent role/template."""

    agent_id: str
    version: str
    role: str
    mission: str
    capabilities: Tuple[str, ...]
    authority_ceiling: str = "read"
    execution_domain: str = "analysis"
    observability_events: Tuple[str, ...] = ()
    memory_read: bool = False
    memory_write: bool = False
    memory_policy_ids: Tuple[str, ...] = ()
    max_runtime_seconds: int = 900
    max_cost_units: float = 1.0
    risk_class: str = "GREEN"
    provider_class: str = "hybrid"
    is_verifier: bool = False
    process_profile: str | None = None

    def validate(self) -> "AgentSpec":
        if not self.agent_id or not self.version or not self.role or not self.mission:
            raise EnterpriseModelError("agent identity/version/role/mission are required")
        if not self.capabilities or any(not item for item in self.capabilities):
            raise EnterpriseModelError("agent must declare at least one capability")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise EnterpriseModelError("agent capabilities must be unique")
        authority_rank(self.authority_ceiling)
        if self.risk_class not in RISK_CLASSES:
            raise EnterpriseModelError(f"invalid risk_class: {self.risk_class}")
        if self.max_runtime_seconds <= 0 or self.max_cost_units < 0:
            raise EnterpriseModelError("runtime must be positive and cost budget non-negative")
        if self.memory_write and not self.memory_policy_ids:
            raise EnterpriseModelError("memory_write requires explicit memory_policy_ids")
        if authority_rank(self.authority_ceiling) > authority_rank("read") and not self.observability_events:
            raise EnterpriseModelError("consequential agent authority requires observability events")
        return self


@dataclass(frozen=True)
class MissionSpec:
    """A mission is the input to dynamic organizational formation."""

    mission_id: str
    purpose: str
    required_capabilities: Tuple[str, ...]
    authority_ceiling: str = "read"
    risk_class: str = "GREEN"
    max_agents: int = 5
    observability_quorum: float = 1.0
    require_independent_verifier: bool = False
    max_total_cost_units: float = 10.0

    def validate(self) -> "MissionSpec":
        if not self.mission_id or not self.purpose:
            raise EnterpriseModelError("mission_id and purpose are required")
        if not self.required_capabilities or any(not item for item in self.required_capabilities):
            raise EnterpriseModelError("mission requires at least one capability")
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise EnterpriseModelError("required capabilities must be unique")
        authority_rank(self.authority_ceiling)
        if self.risk_class not in RISK_CLASSES:
            raise EnterpriseModelError(f"invalid risk_class: {self.risk_class}")
        if self.max_agents <= 0:
            raise EnterpriseModelError("max_agents must be positive")
        if not 0.0 <= self.observability_quorum <= 1.0:
            raise EnterpriseModelError("observability_quorum must be in [0,1]")
        if self.max_total_cost_units < 0:
            raise EnterpriseModelError("max_total_cost_units must be non-negative")
        return self


@dataclass(frozen=True)
class SwarmSpec:
    """A derived, time-bounded organizational mosaic for one mission."""

    swarm_id: str
    mission_id: str
    member_agent_ids: Tuple[str, ...]
    covered_capabilities: Tuple[str, ...]
    topology: str
    authority_ceiling: str
    risk_class: str
    observability_quorum: float
    verifier_agent_ids: Tuple[str, ...] = ()
    estimated_cost_units: float = 0.0

    def validate(self) -> "SwarmSpec":
        if not self.swarm_id or not self.mission_id or not self.member_agent_ids:
            raise EnterpriseModelError("swarm identity/mission/members are required")
        if len(set(self.member_agent_ids)) != len(self.member_agent_ids):
            raise EnterpriseModelError("swarm member IDs must be unique")
        authority_rank(self.authority_ceiling)
        if self.risk_class not in RISK_CLASSES:
            raise EnterpriseModelError(f"invalid risk_class: {self.risk_class}")
        if not 0.0 <= self.observability_quorum <= 1.0:
            raise EnterpriseModelError("observability_quorum must be in [0,1]")
        if self.estimated_cost_units < 0:
            raise EnterpriseModelError("estimated_cost_units must be non-negative")
        if self.risk_class == "RED" and not self.verifier_agent_ids:
            raise EnterpriseModelError("RED swarm requires an independent verifier")
        return self


@dataclass(frozen=True)
class MosaicDelta:
    """Explicit topology/authority change to an existing mosaic/swarm."""

    delta_id: str
    swarm_id: str
    added_agents: Tuple[str, ...] = ()
    removed_agents: Tuple[str, ...] = ()
    added_edges: Tuple[Tuple[str, str], ...] = ()
    removed_edges: Tuple[Tuple[str, str], ...] = ()
    authority_before: str = "read"
    authority_after: str = "read"
    reason: str = ""
    evidence_refs: Tuple[str, ...] = ()
    gate_event_id: str | None = None

    def validate(self) -> "MosaicDelta":
        if not self.delta_id or not self.swarm_id or not self.reason:
            raise EnterpriseModelError("delta_id/swarm_id/reason are required")
        before = authority_rank(self.authority_before)
        after = authority_rank(self.authority_after)
        if after > before and not self.gate_event_id:
            raise EnterpriseModelError("authority-expanding MosaicDelta requires gate_event_id")
        if set(self.added_agents) & set(self.removed_agents):
            raise EnterpriseModelError("same agent cannot be added and removed in one delta")
        if not self.evidence_refs:
            raise EnterpriseModelError("MosaicDelta requires evidence_refs")
        return self

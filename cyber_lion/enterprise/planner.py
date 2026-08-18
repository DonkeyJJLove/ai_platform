"""Deterministic dynamic swarm planner.

The planner solves a small constrained capability-cover problem. It creates organizational
specifications only; runtime admission/credentials remain the responsibility of MAND/INF.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Set

from .models import (
    AgentSpec,
    EnterpriseModelError,
    MissionSpec,
    SwarmSpec,
    authority_rank,
)


class SwarmPlanner:
    """Create the smallest sufficient observable swarm for a mission."""

    @staticmethod
    def _observable(agent: AgentSpec) -> bool:
        # Read-only analytical agents may operate with a minimal event surface; anything
        # above read requires explicit observability by AgentSpec validation.
        return bool(agent.observability_events) or authority_rank(agent.authority_ceiling) <= authority_rank("read")

    @staticmethod
    def _effective_agent_authority(agent: AgentSpec, mission: MissionSpec) -> int:
        return min(authority_rank(agent.authority_ceiling), authority_rank(mission.authority_ceiling))

    def plan(self, mission: MissionSpec, agents: Sequence[AgentSpec]) -> SwarmSpec:
        mission.validate()
        valid = [agent.validate() for agent in agents]
        if not valid:
            raise EnterpriseModelError("no AgentSpecs available")

        required: Set[str] = set(mission.required_capabilities)
        available: Set[str] = set()
        for agent in valid:
            available.update(agent.capabilities)
        missing = sorted(required - available)
        if missing:
            raise EnterpriseModelError(f"uncovered mission capabilities: {missing}")

        selected: List[AgentSpec] = []
        uncovered = set(required)

        # Deterministic greedy set cover: maximize newly covered capabilities, then prefer
        # lower effective authority, lower cost, verifier diversity, stable agent_id.
        while uncovered:
            candidates = []
            for agent in valid:
                if agent in selected:
                    continue
                new_cover = uncovered & set(agent.capabilities)
                if not new_cover:
                    continue
                candidates.append(
                    (
                        -len(new_cover),
                        self._effective_agent_authority(agent, mission),
                        agent.max_cost_units,
                        0 if agent.is_verifier else 1,
                        agent.agent_id,
                        agent,
                    )
                )
            if not candidates:
                raise EnterpriseModelError(f"cannot cover capabilities: {sorted(uncovered)}")
            agent = sorted(candidates, key=lambda item: item[:-1])[0][-1]
            selected.append(agent)
            uncovered -= set(agent.capabilities)
            if len(selected) > mission.max_agents:
                raise EnterpriseModelError("mission capability coverage exceeds max_agents")

        verifier_required = (
            mission.require_independent_verifier
            or mission.risk_class == "RED"
            or authority_rank(mission.authority_ceiling) >= authority_rank("external_write")
        )
        verifier_ids: List[str] = [agent.agent_id for agent in selected if agent.is_verifier]
        if verifier_required and not verifier_ids:
            verifier_candidates = [
                agent
                for agent in valid
                if agent.is_verifier and agent not in selected and self._observable(agent)
            ]
            if not verifier_candidates:
                raise EnterpriseModelError("mission requires an independent verifier AgentSpec")
            verifier = sorted(
                verifier_candidates,
                key=lambda agent: (
                    self._effective_agent_authority(agent, mission),
                    agent.max_cost_units,
                    agent.agent_id,
                ),
            )[0]
            selected.append(verifier)
            verifier_ids.append(verifier.agent_id)

        if len(selected) > mission.max_agents:
            raise EnterpriseModelError("required verifier would exceed max_agents")

        total_cost = sum(agent.max_cost_units for agent in selected)
        if total_cost > mission.max_total_cost_units:
            raise EnterpriseModelError(
                f"swarm cost {total_cost:.3f} exceeds mission budget {mission.max_total_cost_units:.3f}"
            )

        observable_count = sum(1 for agent in selected if self._observable(agent))
        coverage = observable_count / len(selected)
        if coverage < mission.observability_quorum:
            raise EnterpriseModelError(
                f"observability coverage {coverage:.3f} below quorum {mission.observability_quorum:.3f}"
            )

        topology = self._topology(mission, selected, bool(verifier_ids))
        covered = sorted(required & set().union(*(set(agent.capabilities) for agent in selected)))
        return SwarmSpec(
            swarm_id=f"swarm:{mission.mission_id}",
            mission_id=mission.mission_id,
            member_agent_ids=tuple(agent.agent_id for agent in selected),
            covered_capabilities=tuple(covered),
            topology=topology,
            authority_ceiling=mission.authority_ceiling,
            risk_class=mission.risk_class,
            observability_quorum=mission.observability_quorum,
            verifier_agent_ids=tuple(sorted(verifier_ids)),
            estimated_cost_units=total_cost,
        ).validate()

    @staticmethod
    def _topology(mission: MissionSpec, agents: Iterable[AgentSpec], has_verifier: bool) -> str:
        count = sum(1 for _ in agents)
        if mission.risk_class == "RED":
            return "segmented_peer_review"
        if has_verifier or mission.risk_class == "AMBER":
            return "hub_spoke_with_verifier"
        if count <= 2:
            return "direct_cell"
        return "capability_mosaic"

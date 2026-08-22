"""Deterministic dynamic swarm planner over a canonical registry projection."""
from __future__ import annotations
from typing import Iterable,List,Set
from cyber_lion.contracts.agent_registry import AgentRegistryProjection
from .models import AgentSpec,EnterpriseModelError,MissionSpec,SwarmSpec,authority_rank

class SwarmPlanner:
    @staticmethod
    def _observable(agent:AgentSpec)->bool:return bool(agent.observability_events) or authority_rank(agent.authority_ceiling)<=authority_rank("read")
    @staticmethod
    def _effective_agent_authority(agent:AgentSpec,mission:MissionSpec)->int:return min(authority_rank(agent.authority_ceiling),authority_rank(mission.authority_ceiling))
    @staticmethod
    def _agents(projection:AgentRegistryProjection,mission:MissionSpec)->list[AgentSpec]:
        projection.verify_digest()
        if projection.mission_id!=mission.mission_id or projection.required_capabilities!=mission.required_capabilities:raise EnterpriseModelError("registry projection mission binding mismatch")
        out=[]
        for raw in projection.candidate_specs:
            d=dict(raw)
            for k in ("capabilities","observability_events","memory_policy_ids"):d[k]=tuple(d.get(k,()))
            try:out.append(AgentSpec(**d).validate())
            except (TypeError,ValueError) as e:raise EnterpriseModelError("registry projection contains invalid AgentSpec") from e
        return out
    def plan(self,mission:MissionSpec,projection:AgentRegistryProjection)->SwarmSpec:
        mission.validate();valid=self._agents(projection,mission)
        if not valid:raise EnterpriseModelError("no canonical AgentSpecs available")
        required:Set[str]=set(mission.required_capabilities);available=set().union(*(set(a.capabilities) for a in valid));missing=sorted(required-available)
        if missing:raise EnterpriseModelError(f"uncovered mission capabilities: {missing}")
        selected:List[AgentSpec]=[];uncovered=set(required)
        while uncovered:
            candidates=[]
            for a in valid:
                if a in selected:continue
                cover=uncovered&set(a.capabilities)
                if cover:candidates.append((-len(cover),self._effective_agent_authority(a,mission),a.max_cost_units,0 if a.is_verifier else 1,a.agent_id,a))
            if not candidates:raise EnterpriseModelError(f"cannot cover capabilities: {sorted(uncovered)}")
            a=sorted(candidates,key=lambda x:x[:-1])[0][-1];selected.append(a);uncovered-=set(a.capabilities)
            if len(selected)>mission.max_agents:raise EnterpriseModelError("mission capability coverage exceeds max_agents")
        need=mission.require_independent_verifier or mission.risk_class=="RED" or authority_rank(mission.authority_ceiling)>=authority_rank("external_write")
        vids=[a.agent_id for a in selected if a.is_verifier]
        if need and not vids:
            vs=[a for a in valid if a.is_verifier and a not in selected and self._observable(a)]
            if not vs:raise EnterpriseModelError("mission requires an independent verifier AgentSpec")
            v=sorted(vs,key=lambda a:(self._effective_agent_authority(a,mission),a.max_cost_units,a.agent_id))[0];selected.append(v);vids.append(v.agent_id)
        if len(selected)>mission.max_agents:raise EnterpriseModelError("required verifier would exceed max_agents")
        cost=sum(a.max_cost_units for a in selected)
        if cost>mission.max_total_cost_units:raise EnterpriseModelError(f"swarm cost {cost:.3f} exceeds mission budget {mission.max_total_cost_units:.3f}")
        coverage=sum(1 for a in selected if self._observable(a))/len(selected)
        if coverage<mission.observability_quorum:raise EnterpriseModelError(f"observability coverage {coverage:.3f} below quorum {mission.observability_quorum:.3f}")
        topology=self._topology(mission,selected,bool(vids));covered=sorted(required&set().union(*(set(a.capabilities) for a in selected)))
        return SwarmSpec(f"swarm:{mission.mission_id}",mission.mission_id,tuple(a.agent_id for a in selected),tuple(covered),topology,mission.authority_ceiling,mission.risk_class,mission.observability_quorum,tuple(sorted(vids)),cost).validate()
    @staticmethod
    def _topology(mission:MissionSpec,agents:Iterable[AgentSpec],has_verifier:bool)->str:
        count=sum(1 for _ in agents)
        if mission.risk_class=="RED":return "segmented_peer_review"
        if has_verifier or mission.risk_class=="AMBER":return "hub_spoke_with_verifier"
        if count<=2:return "direct_cell"
        return "capability_mosaic"

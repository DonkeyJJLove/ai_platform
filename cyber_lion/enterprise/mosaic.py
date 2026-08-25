"""Heterogeneous Mosaic planning over canonical Bean composition.

Agent Beans are projected into the existing AgentSpec model without changing the
existing SwarmPlanner. Non-agent Beans remain first-class Mosaic members.
"""
from __future__ import annotations
from typing import Mapping,Tuple
from cyber_lion.contracts.bean import BeanContractError,BeanSpec
from cyber_lion.contracts.bean_composition import CompositionContract
from cyber_lion.contracts.mosaic import MosaicCell,form_mosaic
from .models import AgentSpec

_ROLE_BY_TYPE={"agent":"agent","builder":"builder","verifier":"verifier","observer":"observer","reconciler":"reconciler","adapter":"adapter","tool":"tool","workflow":"workflow","provider":"provider","deterministic_service":"service"}

def bean_to_agent_spec(*,spec:BeanSpec,mission_id:str,risk_class:str="GREEN")->AgentSpec:
    spec.validate()
    if spec.bean_type!="agent":raise BeanContractError("only agent BeanSpec projects to AgentSpec")
    max_runtime=900
    try:
        if spec.time_budget.endswith("s"):max_runtime=max(1,int(spec.time_budget[:-1]))
    except Exception:pass
    return AgentSpec(agent_id=spec.bean_id,version=spec.version,role=spec.purpose,mission=mission_id,capabilities=spec.provided_capabilities,authority_ceiling=spec.authority_ceiling,execution_domain=spec.runtime_class,observability_events=spec.observability_requirements,memory_read="read" in spec.memory_policy,memory_write="write" in spec.memory_policy,memory_policy_ids=spec.memory_policy if "write" in spec.memory_policy else (),max_runtime_seconds=max_runtime,max_cost_units=1.0,risk_class=risk_class,provider_class=spec.runtime_class,is_verifier=False,process_profile=spec.sandbox_class).validate()

class HeterogeneousMosaicPlanner:
    def form(self,*,mosaic_id:str,composition:CompositionContract,specs:Mapping[str,BeanSpec],evidence_refs:Tuple[str,...])->MosaicCell:
        composition.validate()
        ids={b.bean_id for b in composition.bean_bindings}
        if set(specs)!=ids:raise BeanContractError("Mosaic specs must exactly match composition bindings")
        member_types=[]
        for binding in composition.bean_bindings:
            spec=specs[binding.bean_id];spec.validate()
            if spec.spec_digest()!=binding.spec_digest:raise BeanContractError("Mosaic BeanSpec substitution detected")
            member_types.append((spec.bean_id,spec.bean_type,_ROLE_BY_TYPE[spec.bean_type]))
        return form_mosaic(mosaic_id=mosaic_id,composition=composition,member_types=tuple(member_types),evidence_refs=evidence_refs)

"""Deterministic hard-gated Bean composition. No execution or authority minting surface."""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from typing import Mapping, Tuple

from cyber_lion.contracts.bean import BeanContractError, BeanSpec
from cyber_lion.contracts.bean_composition import CompositionBeanBinding, CompositionContract, CompositionRequest
from .policy_gate import authority_contains

class CompositionError(RuntimeError): pass

@dataclass(frozen=True)
class BeanDescriptor:
    spec: BeanSpec
    implementation_digest: str
    provider_family: str
    resource_units: int
    cost_units: int
    def validate(self):
        self.spec.validate()
        CompositionBeanBinding(self.spec.bean_id,self.spec.spec_digest(),self.implementation_digest,self.provider_family,self.resource_units,self.cost_units).validate()
        return self

class CompositionEngine:
    """Select minimal admissible compositions by hard constraints then stable digest tie-break."""
    def compose(self, *, request:CompositionRequest, candidates:Tuple[BeanDescriptor,...])->CompositionContract:
        request.validate()
        if type(candidates) is not tuple or not candidates: raise CompositionError("candidate catalog required")
        catalog=[]
        seen=set()
        for d in candidates:
            if type(d) is not BeanDescriptor: raise CompositionError("exact BeanDescriptor required")
            d.validate()
            if d.spec.bean_id in seen: raise CompositionError("ambiguous duplicate bean_id in catalog")
            seen.add(d.spec.bean_id);catalog.append(d)
        admissible=[]
        for size in range(1,len(catalog)+1):
            for subset in combinations(catalog,size):
                try: contract=self._seal(request,subset)
                except CompositionError: continue
                admissible.append(contract)
            if admissible: break
        if not admissible: raise CompositionError("no admissible composition")
        return sorted(admissible,key=lambda c:(c.total_cost_units,c.total_resource_units,c.digest()))[0]

    def _seal(self,request:CompositionRequest,subset:Tuple[BeanDescriptor,...])->CompositionContract:
        specs=[d.spec for d in subset];ids={s.bean_id for s in specs}
        provided=set().union(*(set(s.provided_capabilities) for s in specs))
        allowed=provided|set(request.external_allowed_capabilities)
        if not set(request.required_capabilities)<=allowed: raise CompositionError("capability closure failed")
        # Every selected Bean's own requirements must also close.
        for s in specs:
            if not set(s.required_capabilities)<=allowed: raise CompositionError("dependency capability closure failed")
        # Typed input/output compatibility: mission inputs or another Bean's exact output must satisfy each input.
        outputs=set().union(*(set(s.outputs) for s in specs))|set(request.mission_inputs)
        for s in specs:
            if not set(s.inputs)<=outputs: raise CompositionError("interface compatibility failed")
        # Dependencies are exact bean_ids and must be closed; cycles are denied.
        for s in specs:
            if not set(s.dependencies)<=ids: raise CompositionError("dependency closure failed")
        graph={s.bean_id:set(s.dependencies) for s in specs}
        self._assert_acyclic(graph)
        for encoded in request.conflict_pairs:
            a,b=encoded.split("|",1)
            if a in ids and b in ids: raise CompositionError("composition conflict")
        resources=sum(d.resource_units for d in subset);cost=sum(d.cost_units for d in subset)
        if resources>request.max_resource_units or cost>request.max_cost_units: raise CompositionError("resource budget exceeded")
        observers=[s for s in specs if s.bean_type=="observer"]
        obs_channels=set().union(*(set(s.observability_requirements) for s in observers)) if observers else set()
        if not set(request.required_observability_channels)<=obs_channels: raise CompositionError("observability coverage failed")
        if len(observers)<request.observability_quorum: raise CompositionError("observability quorum failed")
        # No selected Bean may have a ceiling wider than the externally supplied mission ceiling.
        try:
            if any(not authority_contains(request.mission_authority_ceiling,s.authority_ceiling) for s in specs): raise CompositionError("authority attenuation failed")
        except Exception as exc:
            if isinstance(exc,CompositionError): raise
            raise CompositionError("authority vocabulary invalid") from exc
        builders=[s for s in specs if s.bean_type=="builder"]
        verifiers=[s for s in specs if s.bean_type=="verifier"]
        if request.consequential:
            if not verifiers: raise CompositionError("independent verifier required")
            builder_ids={s.bean_id for s in builders};builder_impl={d.implementation_digest for d in subset if d.spec.bean_type=="builder"};builder_families={d.provider_family for d in subset if d.spec.bean_type=="builder"}
            for d in subset:
                if d.spec.bean_type=="verifier":
                    if d.spec.bean_id in builder_ids or d.implementation_digest in builder_impl or d.provider_family in builder_families: raise CompositionError("epistemically independent verifier required")
            if not observers: raise CompositionError("independent observer required")
            effect_families={d.provider_family for d in subset if d.spec.bean_type in {"builder","tool","adapter","workflow","provider"}}
            if all(d.provider_family in effect_families for d in subset if d.spec.bean_type=="observer"): raise CompositionError("epistemically independent observer required")
        bindings=tuple(sorted((CompositionBeanBinding(d.spec.bean_id,d.spec.spec_digest(),d.implementation_digest,d.provider_family,d.resource_units,d.cost_units) for d in subset),key=lambda b:b.bean_id))
        interfaces=[];deps=[]
        for s in specs:
            for i in s.inputs:
                interfaces.append(f"{s.bean_id}<-{i}")
            for dep in s.dependencies: deps.append(f"{s.bean_id}<-{dep}")
        return CompositionContract(
            composition_id=request.composition_id,mission_id=request.mission_id,goal_digest=request.goal_digest,
            bean_bindings=bindings,required_capabilities=request.required_capabilities,resolved_capabilities=tuple(sorted(set(request.required_capabilities)&allowed)),
            interface_bindings=tuple(sorted(set(interfaces))),dependency_edges=tuple(sorted(set(deps))),observability_channels=tuple(sorted(obs_channels)),
            verifier_bean_ids=tuple(sorted(s.bean_id for s in verifiers)),observer_bean_ids=tuple(sorted(s.bean_id for s in observers)),authority_ceiling=request.mission_authority_ceiling,
            total_resource_units=resources,total_cost_units=cost,provenance_refs=request.provenance_refs,
        ).validate()

    @staticmethod
    def _assert_acyclic(graph:Mapping[str,set[str]])->None:
        visiting=set();done=set()
        def visit(n):
            if n in visiting: raise CompositionError("dependency cycle")
            if n in done:return
            visiting.add(n)
            for dep in graph.get(n,()):visit(dep)
            visiting.remove(n);done.add(n)
        for n in graph:visit(n)

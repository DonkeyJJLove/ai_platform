"""Deterministic CapabilityNeed resolution without hard-coded solution selection."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple
from cyber_lion.contracts.bean import BeanContractError,BeanSpec
from cyber_lion.contracts.capability_need import CapabilityNeed
from .policy_gate import authority_contains

class CapabilityResolutionError(RuntimeError):pass

@dataclass(frozen=True)
class CapabilityResolution:
    need_digest:str
    disposition:str
    existing_spec_digest:str=""
    generated_spec:BeanSpec|None=None
    rationale:str=""
    def validate(self):
        if self.disposition not in {"USE_EXISTING","GENERATE_SPEC"}:raise CapabilityResolutionError("invalid disposition")
        if self.disposition=="USE_EXISTING" and (not self.existing_spec_digest or self.generated_spec is not None):raise CapabilityResolutionError("existing resolution malformed")
        if self.disposition=="GENERATE_SPEC" and (self.generated_spec is None or self.existing_spec_digest):raise CapabilityResolutionError("generated resolution malformed")
        return self

class CapabilityNeedResolver:
    def resolve(self,*,need:CapabilityNeed,catalog:Tuple[BeanSpec,...])->CapabilityResolution:
        need.validate()
        exact=[]
        for spec in catalog:
            if type(spec) is not BeanSpec:raise CapabilityResolutionError("exact BeanSpec catalog required")
            spec.validate()
            if need.required_capability not in spec.provided_capabilities:continue
            if not set(need.required_inputs)<=set(spec.inputs):continue
            if not set(need.required_outputs)<=set(spec.outputs):continue
            try:
                if not authority_contains(need.authority_ceiling,spec.authority_ceiling):continue
            except Exception as exc:raise CapabilityResolutionError("authority vocabulary invalid") from exc
            if not set(need.required_observability)<=set(spec.observability_requirements):continue
            exact.append(spec)
        if exact:
            chosen=sorted(exact,key=lambda s:(s.authority_ceiling,s.spec_digest()))[0]
            return CapabilityResolution(need.digest(),"USE_EXISTING",existing_spec_digest=chosen.spec_digest(),rationale="exact declared capability/interface/authority/observability match").validate()
        return CapabilityResolution(need.digest(),"GENERATE_SPEC",generated_spec=self._new_spec(need),rationale="no compatible existing BeanSpec").validate()
    def _new_spec(self,need:CapabilityNeed)->BeanSpec:
        # This is a specification generator only. It contains no builder invocation or build grant.
        return BeanSpec(bean_id=f"generated:{need.required_capability}",bean_type="adapter",version="0.1.0",purpose=f"Provide gap-derived capability {need.required_capability}",goal_digest=need.goal_digest,
          success_conditions=need.acceptance_conditions,stop_conditions=("spec acceptance evaluated",),defer_conditions=("required evidence unavailable",),inputs=need.required_inputs,outputs=need.required_outputs,interfaces=(f"capability:{need.required_capability}:v1",),required_capabilities=(),provided_capabilities=(need.required_capability,),authority_ceiling=need.authority_ceiling,required_grants=(),epistemic_requirements=("OBSERVED",),evidence_requirements=need.provenance_refs,provenance_policy=(f"gap:{need.gap_digest}",f"need:{need.digest()}"),memory_policy=("candidate-only-until-promotion",),context_policy=("typed-input-only",),observability_requirements=need.required_observability,resource_budget=("bounded-by-composition",),cost_budget="bounded-by-composition",time_budget="bounded-by-composition",runtime_class="unbound-candidate",sandbox_class="required-before-build",dependencies=(),compatibility_constraints=(f"capability:{need.required_capability}:v1",),failure_modes=("acceptance-failure",),degradation_policy=("DEFER",),revocation_policy=("discard-candidate",),security_invariants=("spec-cannot-mint-authority","no-build-without-external-builder-permit"),acceptance_tests=need.acceptance_conditions,falsification_conditions=need.falsification_conditions,evolution_hooks=("gap-derived",),replacement_policy=("exact-lineage",),supersession_policy=("preserve-history",)).validate()

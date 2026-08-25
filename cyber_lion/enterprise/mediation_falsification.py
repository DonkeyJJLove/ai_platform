"""Fail-closed E006 R9B mediation binding resolution and bypass reassessment.

This module is descriptive/evidentiary only. It never authorizes or executes effects.
"""
from __future__ import annotations
from typing import Mapping,Tuple

from cyber_lion.contracts.complete_mediation import ConsequentialEffectSurface,EffectSurfaceInventory,MediationBinding
from cyber_lion.contracts.mediation_falsification import BypassFalsificationResult,MediationBindingCandidate,MediationReassessment

class MediationFalsificationError(RuntimeError):pass

class SurfaceBindingResolver:
    """Resolve only exact, externally supplied evidence bindings for one observed surface."""
    def resolve(self,*,inventory:EffectSurfaceInventory,surface:ConsequentialEffectSurface,candidate:MediationBindingCandidate)->MediationBinding:
        inventory.validate();surface.validate();candidate.validate()
        if candidate.inventory_digest!=inventory.digest():raise MediationFalsificationError("stale or substituted inventory")
        if surface.digest()!=candidate.surface_digest:raise MediationFalsificationError("surface substitution")
        if surface not in inventory.surfaces:raise MediationFalsificationError("surface outside inventory")
        if candidate.provider_identity!=surface.effect_provider:raise MediationFalsificationError("provider substitution")
        if candidate.entrypoint_ref not in surface.entrypoints:raise MediationFalsificationError("entrypoint substitution")
        # Candidate evidence is converted to the canonical R9 binding. Replay guard remains
        # part of candidate identity/evidence but is not silently inserted into the R9 shape.
        refs=tuple(candidate.evidence_refs)+(f"replay-guard:{candidate.replay_guard_digest}",f"candidate:{candidate.digest()}")
        return MediationBinding(
            surface_digest=candidate.surface_digest,
            effect_contract_digest=candidate.effect_contract_digest,
            pep_identity_digest=candidate.pep_identity_digest,
            authority_source_digest=candidate.authority_source_digest,
            currentness_source_digest=candidate.currentness_source_digest,
            execution_boundary_digest=candidate.execution_boundary_digest,
            observer_identity_digests=candidate.observer_identity_digests,
            reconciliation_boundary_digest=candidate.reconciliation_boundary_digest,
            evidence_refs=refs,
        ).validate()

class MediationBindingRegistry:
    """Immutable-by-use registry keyed by exact inventory and surface digest."""
    def __init__(self,*,inventory_digest:str,epoch:str):
        self._inventory_digest=inventory_digest;self._epoch=epoch;self._bindings={};self._candidate_digests=set()
    def register(self,candidate:MediationBindingCandidate,binding:MediationBinding):
        candidate.validate();binding.validate()
        if candidate.inventory_digest!=self._inventory_digest:raise MediationFalsificationError("stale inventory binding")
        if candidate.epoch!=self._epoch:raise MediationFalsificationError("cross-epoch binding replay")
        if candidate.surface_digest!=binding.surface_digest:raise MediationFalsificationError("binding surface mismatch")
        cd=candidate.digest()
        if cd in self._candidate_digests:raise MediationFalsificationError("binding replay")
        prior=self._bindings.get(binding.surface_digest)
        if prior is not None:raise MediationFalsificationError("duplicate or conflicting surface binding")
        self._candidate_digests.add(cd);self._bindings[binding.surface_digest]=binding
        return binding
    def snapshot(self)->Tuple[MediationBinding,...]:return tuple(self._bindings[k] for k in sorted(self._bindings))

class CompleteMediationReassessment:
    """Combine exact bindings with independently observed bypass results."""
    def reassess(self,*,inventory:EffectSurfaceInventory,bindings:Tuple[MediationBinding,...],results:Tuple[BypassFalsificationResult,...],required_attacks:Mapping[str,Tuple[str,...]],observation_evidence_refs:Tuple[str,...])->MediationReassessment:
        inventory.validate()
        by_surface={}
        for b in bindings:
            b.validate()
            if b.surface_digest in by_surface:raise MediationFalsificationError("ambiguous binding")
            by_surface[b.surface_digest]=b
        known={s.digest() for s in inventory.surfaces}
        if set(by_surface)-known:raise MediationFalsificationError("binding outside inventory")
        by_result={}
        for r in results:
            r.validate()
            if r.inventory_digest!=inventory.digest():raise MediationFalsificationError("stale falsification evidence")
            if r.surface_digest not in known:raise MediationFalsificationError("falsification surface outside inventory")
            key=(r.surface_digest,r.attack_id)
            if key in by_result:raise MediationFalsificationError("duplicate falsification result")
            by_result[key]=r
        statuses=[]
        evidence=list(observation_evidence_refs)
        for s in inventory.surfaces:
            sd=s.digest();binding=by_surface.get(sd);attacks=required_attacks.get(sd,())
            if binding is None:
                status="UNKNOWN"
            else:
                selected=[by_result.get((sd,a)) for a in attacks]
                if any(r is not None and r.observed_outcome=="REACHED_EFFECT" for r in selected):status="UNMEDIATED"
                elif any(r is None or r.observed_outcome=="UNKNOWN" or r.epistemic_state!="OBSERVED" for r in selected):status="PARTIAL" if selected else "UNKNOWN"
                elif attacks and all(r.observed_outcome=="DENIED" for r in selected):status="MEDIATED"
                else:status="UNKNOWN"
                for r in selected:
                    if r is not None:evidence.extend(r.evidence_refs)
            statuses.append((sd,status))
        global_pass=bool(statuses) and not inventory.unclassified_refs and all(s=="MEDIATED" for _,s in statuses) and bool(observation_evidence_refs)
        return MediationReassessment(inventory.digest(),tuple(statuses),"PASS" if global_pass else "UNKNOWN",tuple(dict.fromkeys(evidence))).validate()

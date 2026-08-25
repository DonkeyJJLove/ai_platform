"""R9C production mediation tracing and fail-closed closure reporting."""
from __future__ import annotations
from hashlib import sha256
from typing import Mapping,Tuple

from cyber_lion.contracts.complete_mediation import EffectSurfaceInventory,MediationBinding
from cyber_lion.contracts.mediation_falsification import BypassFalsificationResult
from cyber_lion.contracts.production_mediation import (
    GlobalMediationClosureReport,MediationChainEvidence,MediationClosureRecord,
    ProductionEffectTrace,UnclassifiedEffectRecord,
)

class ProductionMediationError(RuntimeError):pass

def _h(text:str)->str:return sha256(text.encode()).hexdigest()

class ProductionEffectInventory:
    """Materialize evidence traces only from exact R9 inventory plus caller-supplied runtime evidence."""
    def materialize(self,*,inventory:EffectSurfaceInventory,runtime_evidence:Mapping[str,Tuple[str,...]])->Tuple[ProductionEffectTrace,...]:
        inventory.validate();out=[]
        for s in inventory.surfaces:
            sd=s.digest();refs=runtime_evidence.get(sd,())
            state="OBSERVED" if refs else "UNKNOWN"
            out.append(ProductionEffectTrace(
                trace_id="trace:"+sd[:24],inventory_digest=inventory.digest(),surface_digest=sd,
                source_entrypoint=s.entrypoints[0],call_path=s.entrypoints,
                consequential_primitive=s.mutation_kind,effect_class=s.effect_class,
                provider_identity=s.effect_provider,target_identity=s.target_class,
                source_refs=s.evidence_refs,runtime_evidence_refs=tuple(refs),epistemic_state=state,
            ).validate())
        return tuple(out)

class MediationChainReconstructor:
    """Accept externally observed components; it never invents authority or execution evidence."""
    def reconstruct(self,*,inventory:EffectSurfaceInventory,trace:ProductionEffectTrace,binding:MediationBinding|None,replay_guard_digest:str="",bounded_scope_digest:str="",verifier_identity_digest:str="",epoch:str="E006")->MediationChainEvidence|None:
        inventory.validate();trace.validate()
        if trace.inventory_digest!=inventory.digest():raise ProductionMediationError("stale trace inventory")
        known={s.digest():s for s in inventory.surfaces}
        if trace.surface_digest not in known:raise ProductionMediationError("trace outside inventory")
        s=known[trace.surface_digest]
        if trace.provider_identity!=s.effect_provider or trace.source_entrypoint not in s.entrypoints:raise ProductionMediationError("trace substitution")
        if binding is None:return None
        binding.validate()
        if binding.surface_digest!=trace.surface_digest:raise ProductionMediationError("binding surface substitution")
        if not replay_guard_digest or not bounded_scope_digest or not verifier_identity_digest:return None
        return MediationChainEvidence(
            surface_digest=trace.surface_digest,trace_digest=trace.digest(),effect_contract_digest=binding.effect_contract_digest,
            authority_source_digest=binding.authority_source_digest,currentness_source_digest=binding.currentness_source_digest,
            pep_identity_digest=binding.pep_identity_digest,execution_boundary_digest=binding.execution_boundary_digest,
            replay_guard_digest=replay_guard_digest,bounded_scope_digest=bounded_scope_digest,
            observer_identity_digests=binding.observer_identity_digests,reconciliation_boundary_digest=binding.reconciliation_boundary_digest,
            evidence_refs=binding.evidence_refs+(f"trace:{trace.digest()}",),verifier_identity_digest=verifier_identity_digest,epoch=epoch,
        ).validate()

class ProductionMediationClosure:
    def close(self,*,inventory:EffectSurfaceInventory,traces:Tuple[ProductionEffectTrace,...],bindings:Tuple[MediationBinding,...],chains:Tuple[MediationChainEvidence,...],results:Tuple[BypassFalsificationResult,...],required_attacks:Mapping[str,Tuple[str,...]],independent_verifier_identity:str,observation_evidence_refs:Tuple[str,...])->Tuple[Tuple[MediationClosureRecord,...],GlobalMediationClosureReport]:
        inventory.validate();inv=inventory.digest();known={s.digest() for s in inventory.surfaces}
        tmap={t.surface_digest:t.validate() for t in traces};bmap={b.surface_digest:b.validate() for b in bindings};cmap={c.surface_digest:c.validate() for c in chains}
        if set(tmap)!=known:raise ProductionMediationError("trace set must exactly match inventory surfaces")
        if set(bmap)-known or set(cmap)-known:raise ProductionMediationError("binding/chain outside inventory")
        rmap={}
        for r in results:
            r.validate()
            if r.inventory_digest!=inv or r.surface_digest not in known:raise ProductionMediationError("stale or foreign bypass evidence")
            key=(r.surface_digest,r.attack_id)
            if key in rmap:raise ProductionMediationError("duplicate bypass evidence")
            rmap[key]=r
        records=[];attempts=denied=reached=0;evidence=list(observation_evidence_refs)
        for sd in sorted(known):
            t=tmap[sd];b=bmap.get(sd);c=cmap.get(sd);attacks=required_attacks.get(sd,())
            selected=[rmap.get((sd,a)) for a in attacks];attempts+=len(attacks)
            denied+=sum(1 for r in selected if r and r.observed_outcome=="DENIED" and r.epistemic_state=="OBSERVED")
            reached+=sum(1 for r in selected if r and r.observed_outcome=="REACHED_EFFECT" and r.epistemic_state=="OBSERVED")
            if any(r and r.observed_outcome=="REACHED_EFFECT" and r.epistemic_state=="OBSERVED" for r in selected):status="UNMEDIATED"
            elif t.epistemic_state!="OBSERVED":status="UNKNOWN"
            elif b is None or c is None:status="PARTIAL"
            elif not attacks or any(r is None or r.observed_outcome!="DENIED" or r.epistemic_state!="OBSERVED" for r in selected):status="PARTIAL"
            else:status="MEDIATED"
            rd=tuple(r.digest() for r in selected if r is not None)
            refs=list(t.runtime_evidence_refs)
            if c:refs.extend(c.evidence_refs)
            for r in selected:
                if r:refs.extend(r.evidence_refs)
            rec=MediationClosureRecord(sd,inv,b.digest() if b else "",t.digest(),rd,status,tuple(dict.fromkeys(refs))).validate();records.append(rec);evidence.extend(rec.evidence_refs)
        counts={k:sum(1 for r in records if r.status==k) for k in ("MEDIATED","PARTIAL","UNMEDIATED","UNKNOWN")}
        unclassified=len(inventory.unclassified_refs)
        global_pass=bool(records) and not unclassified and counts["PARTIAL"]==counts["UNMEDIATED"]==counts["UNKNOWN"]==0 and attempts>0 and attempts==denied and reached==0 and bool(observation_evidence_refs)
        report=GlobalMediationClosureReport(inv,len(records),counts["MEDIATED"],counts["PARTIAL"],counts["UNMEDIATED"],counts["UNKNOWN"],unclassified,attempts,denied,reached,tuple(dict.fromkeys(evidence)),independent_verifier_identity,"PASS" if global_pass else "UNKNOWN").validate()
        return tuple(records),report

def classify_unclassified(refs:Tuple[str,...])->Tuple[UnclassifiedEffectRecord,...]:
    out=[]
    for ref in refs:
        reason="dynamic-SQL" if "dynamic-sql" in ref else "unresolved-provider"
        out.append(UnclassifiedEffectRecord(ref,ref,reason).validate())
    return tuple(out)

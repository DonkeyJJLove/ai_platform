from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Tuple

from cyber_lion.contracts.complete_mediation import EffectSurfaceInventory
from cyber_lion.contracts.production_mediation import MediationClosureRecord
from cyber_lion.enterprise.mediation_falsification import CompleteMediationReassessment
from tools.p0_effect_taxonomy_contract import EffectTaxonomyReconciliationReport
from tools.p0_global_mediation_closure import GlobalMediationClosureCarrierBuilder
from tools.p0_global_mediation_contract import GlobalMediationClosureCarrier, mediation_closure_record_digest
from tools.p0_moon_attack_registry import FENCE_SURFACES, PERMISSION_SURFACE
from tools.p0_moon_attested_adjudication import EXPECTED_SCAN_DIGEST, materialize_attested_adjudication
from tools.p0_moon_structural_falsification import STRUCTURAL_ATTACKS, StructuralFalsificationArtifacts, materialize_structural_falsification

READINESS_DOMAIN=b"LION/MOON-SEVEN-POLICY-CLOSURE-READINESS/1"
CLASS_CANONICAL="CANONICAL_DENIED_RESULT_PRESENT"
CLASS_STRUCTURAL_PENDING="STRUCTURAL_EVIDENCE_NOT_YET_CLOSURE_COMPATIBLE"
CLASS_LIVE_MISSING="LIVE_EVIDENCE_MISSING"
CLASS_BLOCKED_LIVE="BLOCKED_LIVE_BY_AUTHORITY_MODEL"
BLOCKED_PERMISSION=frozenset({"UNTRUSTED_PERMISSION","STALE_AUTHORITY_SOURCE"})

class MoonSevenClosureReadinessError(RuntimeError): pass

def _digest(obj)->str:
    return sha256(READINESS_DOMAIN+b"\0"+json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode()).hexdigest()

@dataclass(frozen=True)
class RequiredAttackReadiness:
    surface_digest:str;attack_id:str;classification:str;result_digest:str;evidence_refs:Tuple[str,...]
    def validate(self):
        if self.classification not in {CLASS_CANONICAL,CLASS_STRUCTURAL_PENDING,CLASS_LIVE_MISSING,CLASS_BLOCKED_LIVE}: raise MoonSevenClosureReadinessError("invalid readiness classification")
        if self.classification==CLASS_CANONICAL and not self.result_digest: raise MoonSevenClosureReadinessError("canonical classification requires result")
        if self.classification!=CLASS_CANONICAL and self.result_digest: raise MoonSevenClosureReadinessError("missing classification cannot carry result")
        if not self.evidence_refs: raise MoonSevenClosureReadinessError("readiness evidence required")
        return self

@dataclass(frozen=True)
class SevenClosureReadinessReport:
    inventory_digest:str;taxonomy_digest:str;attack_policy_digest:str;structural_plan_digest:str;closure_record_digests:Tuple[str,...];global_carrier_digest:str
    mediated_count:int;partial_count:int;unknown_outside_seven_count:int;missing_attack_keys:Tuple[str,...];global_status:str;evidence_refs:Tuple[str,...]
    def validate(self):
        if self.mediated_count!=6 or self.partial_count!=1 or self.unknown_outside_seven_count!=229: raise MoonSevenClosureReadinessError("unexpected seven-surface readiness counts")
        if len(self.closure_record_digests)!=7: raise MoonSevenClosureReadinessError("seven closure records required")
        if self.missing_attack_keys!=(f"{PERMISSION_SURFACE}:STALE_AUTHORITY_SOURCE",f"{PERMISSION_SURFACE}:UNTRUSTED_PERMISSION"): raise MoonSevenClosureReadinessError("minimal missing batch drift")
        if self.global_status!="UNKNOWN": raise MoonSevenClosureReadinessError("global status must remain UNKNOWN")
        return self
    def digest(self): self.validate(); return _digest(self)

@dataclass(frozen=True)
class SevenClosureReadinessArtifacts:
    readiness:Tuple[RequiredAttackReadiness,...]
    closure_records:Tuple[MediationClosureRecord,...]
    global_carrier:GlobalMediationClosureCarrier
    structural:StructuralFalsificationArtifacts
    report:SevenClosureReadinessReport

def materialize_seven_closure_readiness(*,inventory:EffectSurfaceInventory,taxonomy_report:EffectTaxonomyReconciliationReport,repo_root:Path)->SevenClosureReadinessArtifacts:
    inventory.validate();taxonomy_report.validate()
    if inventory.scan_digest!=EXPECTED_SCAN_DIGEST: raise MoonSevenClosureReadinessError("production scan digest drift")
    if taxonomy_report.reconciled_inventory_digest!=inventory.digest() or taxonomy_report.unresolved_refs or inventory.unclassified_refs: raise MoonSevenClosureReadinessError("taxonomy must exactly reconcile current inventory")
    att=materialize_attested_adjudication(inventory=inventory,repo_root=repo_root)
    structural=materialize_structural_falsification(inventory=inventory,repo_root=repo_root,adjudication=att)
    all_results=tuple(att.bypass_results)+tuple(structural.bypass_results)
    by_result={}
    for r in all_results:
        key=(r.surface_digest,r.attack_id)
        if key in by_result: raise MoonSevenClosureReadinessError("shared or duplicate result multiplication")
        by_result[key]=r
    required={r.surface_digest:r.attack_ids for r in att.policy.requirements}
    assessment=CompleteMediationReassessment().reassess(inventory=inventory,bindings=tuple(att.bindings[k] for k in sorted(att.bindings)),results=all_results,required_attacks=required,observation_evidence_refs=(f"attack-policy:{att.policy.digest()}",f"revision-rebind:{att.rebind.digest()}",f"structural-plan:{structural.plan.digest()}"))
    status_map=dict(assessment.surface_statuses)
    readiness=[]
    for req in sorted(att.policy.requirements,key=lambda x:x.surface_digest):
        for aid in req.attack_ids:
            result=by_result.get((req.surface_digest,aid))
            if result is not None:
                readiness.append(RequiredAttackReadiness(req.surface_digest,aid,CLASS_CANONICAL,result.digest(),result.evidence_refs).validate())
            elif aid in BLOCKED_PERMISSION:
                readiness.append(RequiredAttackReadiness(req.surface_digest,aid,CLASS_BLOCKED_LIVE,"",(f"attack-policy:{att.policy.digest()}",f"attack:{aid}","authority-model:blocked-live-evidence-required")).validate())
            elif aid in STRUCTURAL_ATTACKS:
                readiness.append(RequiredAttackReadiness(req.surface_digest,aid,CLASS_STRUCTURAL_PENDING,"",(f"attack-policy:{att.policy.digest()}",f"attack:{aid}")).validate())
            else:
                readiness.append(RequiredAttackReadiness(req.surface_digest,aid,CLASS_LIVE_MISSING,"",(f"attack-policy:{att.policy.digest()}",f"attack:{aid}")).validate())
    if any(x.classification==CLASS_STRUCTURAL_PENDING for x in readiness): raise MoonSevenClosureReadinessError("structural adapter failed to close structural evidence")
    closure=[]
    for sd in sorted(set(FENCE_SURFACES)|{PERMISSION_SURFACE}):
        binding=att.bindings[sd];chain=att.chains[sd];req=required[sd]
        selected=tuple(by_result[(sd,a)] for a in req if (sd,a) in by_result)
        status=status_map[sd]
        if sd in FENCE_SURFACES and status!="MEDIATED": raise MoonSevenClosureReadinessError("fence surface must mediate after exact structural adaptation")
        if sd==PERMISSION_SURFACE and status!="PARTIAL": raise MoonSevenClosureReadinessError("permission surface must remain partial")
        refs=[]
        for seq in (binding.evidence_refs,chain.evidence_refs,tuple(x for r in selected for x in r.evidence_refs)):
            for ref in seq:
                if ref not in refs: refs.append(ref)
        refs.extend(x for x in (f"attack-policy:{att.policy.digest()}",f"structural-plan:{structural.plan.digest()}") if x not in refs)
        closure.append(MediationClosureRecord(sd,inventory.digest(),binding.digest(),chain.trace_digest,tuple(sorted(r.digest() for r in selected)),status,tuple(refs)).validate())
    carrier=GlobalMediationClosureCarrierBuilder().materialize(inventory=inventory,taxonomy_report=taxonomy_report,closure_records=tuple(closure),evidence_refs=(f"attack-policy:{att.policy.digest()}",f"structural-plan:{structural.plan.digest()}","seven-surface-readiness:diagnostic"))
    counts={s:sum(1 for x in carrier.surface_statuses if x.status==s) for s in ("MEDIATED","PARTIAL","UNMEDIATED","UNKNOWN")}
    if counts!={"MEDIATED":6,"PARTIAL":1,"UNMEDIATED":0,"UNKNOWN":229} or carrier.global_status!="UNKNOWN": raise MoonSevenClosureReadinessError("global carrier readiness counts drift")
    missing=tuple(sorted(f"{x.surface_digest}:{x.attack_id}" for x in readiness if x.classification!=CLASS_CANONICAL))
    report=SevenClosureReadinessReport(inventory.digest(),taxonomy_report.digest(),att.policy.digest(),structural.plan.digest(),tuple(sorted(mediation_closure_record_digest(r) for r in closure)),carrier.digest(),6,1,229,missing,"UNKNOWN",(f"assessment:{assessment.inventory_digest}","no-live-execution","no-test-as-bypass-result")).validate()
    return SevenClosureReadinessArtifacts(tuple(readiness),tuple(closure),carrier,structural,report)

from __future__ import annotations
from pathlib import Path
import subprocess
from typing import Tuple

from cyber_lion.contracts.complete_mediation import EffectSurfaceInventory
from cyber_lion.contracts.production_mediation import MediationClosureRecord
from cyber_lion.enterprise.mediation_falsification import CompleteMediationReassessment
from tools.p0_effect_taxonomy_contract import EffectTaxonomyReconciliationReport
from tools.p0_global_mediation_closure import GlobalMediationClosureCarrierBuilder
from tools.p0_global_mediation_contract import mediation_closure_record_digest
from tools.p0_moon_attack_registry import FENCE_SURFACES,PERMISSION_SURFACE
from tools.p0_moon_attested_adjudication import materialize_attested_adjudication
from tools.p0_moon_seven_closure_readiness import materialize_seven_closure_readiness
from tools.p0_moon_attack_policy_v2_contract import EffectBoundaryAttackMapping,SurfaceBypassRequirementV2,RehomedSecurityRequirementV2,MediationAttackRequirementPolicyV2,PermissionPolicyTopologyReadinessReportV2

POLICY_VERSION="MOON-MEDIATION-ATTACK-POLICY/2"
OS_REPLACE_SURFACE="8c6d0020a0816d674a783504d2a8ccc25e3e75c0d446057ba3f4450bd768f687"
PERMISSION_ENTRYPOINT="cyber_lion/enterprise/moon_file_write.py:120:connection.request"
PROVIDER_PATH="cyber_lion/enterprise/moon_file_write.py"
MEDIATION_PATH="cyber_lion/enterprise/moon_file_write_mediation.py"
PRE_EFFECT=("REPOSITORY_SUBSTITUTION","ACTOR_SUBSTITUTION","CONTROL_ISSUE_SUBSTITUTION")
REHOMED=("UNTRUSTED_PERMISSION","STALE_AUTHORITY_SOURCE")

class MoonPermissionPolicyReclassificationError(RuntimeError):pass

def _blob(root:Path,path:str)->str:return subprocess.check_output(["git","hash-object",path],cwd=root,text=True).strip()

def _surface(inventory:EffectSurfaceInventory,sd:str):
    try:return next(s for s in inventory.surfaces if s.digest()==sd)
    except StopIteration as exc:raise MoonPermissionPolicyReclassificationError("required surface absent") from exc

def boundary_matrix(*,inventory:EffectSurfaceInventory,repo_root:Path,definitions)->Tuple[EffectBoundaryAttackMapping,...]:
    permission=_surface(inventory,PERMISSION_SURFACE);replace=_surface(inventory,OS_REPLACE_SURFACE)
    if permission.entrypoints!=(PERMISSION_ENTRYPOINT,):raise MoonPermissionPolicyReclassificationError("permission surface entrypoint drift")
    if replace.entrypoints!=("cyber_lion/enterprise/moon_file_write.py:315:os.replace",):raise MoonPermissionPolicyReclassificationError("replace surface entrypoint drift")
    provider=(repo_root/PROVIDER_PATH).read_text();mediation=(repo_root/MEDIATION_PATH).read_text()
    provider_blob=_blob(repo_root,PROVIDER_PATH);mediation_blob=_blob(repo_root,MEDIATION_PATH)
    if not provider_blob or not mediation_blob:raise MoonPermissionPolicyReclassificationError("production source blob missing")
    i_request=provider.index('connection.request("GET", path, headers=headers)')
    i_untrusted=provider.index('raise MoonFileWriteMediationError("actor permission is not trusted")')
    if not i_request<i_untrusted:raise MoonPermissionPolicyReclassificationError("untrusted permission boundary order drift")
    exec_src=mediation[mediation.index('    def execute(self, request: MoonFileWriteRequest)'):]
    i_pre=exec_src.index('pre_fence_admission = self.admissions.resolve(request)');i_pre_check=exec_src.index('_require_current_admission(admission, pre_fence_admission)');i_prepare=exec_src.index('self.fence.prepare(');i_post=exec_src.index('current_admission = self.admissions.resolve(request)');i_post_check=exec_src.index('_require_current_admission(admission, current_admission)');i_unknown=exec_src.index('self.fence.mark_unknown(effect_key)')
    if not i_pre<i_pre_check<i_prepare<i_post<i_post_check<i_unknown:raise MoonPermissionPolicyReclassificationError("stale authority boundary order drift")
    defs={d.attack_id:d for d in definitions};out=[]
    for aid in PRE_EFFECT:
        d=defs[aid]
        out.append(EffectBoundaryAttackMapping(aid,PERMISSION_SURFACE,"PRE_EFFECT_GUARD",d.pep_name,d.expected_denial,PERMISSION_ENTRYPOINT,"BEFORE_SURFACE_EFFECT",PERMISSION_SURFACE,"BYPASS_DENIAL","The guard rejects substituted execution/authority context before the GitHub authority-observation request is emitted.",(f"source:{PROVIDER_PATH}@{provider_blob}",f"permission-surface:{PERMISSION_SURFACE}",f"pep:{d.expected_pep_digest}")).validate())
    d=defs["UNTRUSTED_PERMISSION"]
    out.append(EffectBoundaryAttackMapping("UNTRUSTED_PERMISSION",PERMISSION_SURFACE,"POST_OBSERVATION_DECISION",d.pep_name,d.expected_denial,PERMISSION_ENTRYPOINT,"AFTER_SURFACE_EFFECT",PERMISSION_SURFACE,"ADMISSION_DECISION_NEGATIVE_EVIDENCE","The permission value is learned by connection.request before the trust decision can reject it; this is admission-decision evidence, not a bypass of the authority-observation surface.",(f"source:{PROVIDER_PATH}@{provider_blob}","control-flow:connection.request-before-actor-permission-denial",f"pep:{d.expected_pep_digest}")).validate())
    d=defs["STALE_AUTHORITY_SOURCE"]
    out.append(EffectBoundaryAttackMapping("STALE_AUTHORITY_SOURCE",PERMISSION_SURFACE,"DOWNSTREAM_CURRENTNESS_GUARD",d.pep_name,d.expected_denial,PERMISSION_ENTRYPOINT,"AFTER_SOURCE_EFFECT_BEFORE_STATE_WRITE_AND_DOWNSTREAM_EFFECT",OS_REPLACE_SURFACE,"DOWNSTREAM_CURRENTNESS_NEGATIVE_EVIDENCE","A pre-fence authority revalidation now rejects stale authority after authority observation but before durable fence state and before the certified os.replace target effect; a second post-prepare revalidation remains mandatory TOCTOU defence.",(f"source:{MEDIATION_PATH}@{mediation_blob}","control-flow:pre-fence-revalidation-before-fence.prepare-and-post-prepare-revalidation",f"downstream-surface:{OS_REPLACE_SURFACE}",f"pep:{d.expected_pep_digest}")).validate())
    return tuple(out)

def policy_v2(*,inventory:EffectSurfaceInventory,repo_root:Path):
    att=materialize_attested_adjudication(inventory=inventory,repo_root=repo_root);v1=att.policy;defs=att.definitions
    v1_by={r.surface_digest:r for r in v1.requirements}
    if PERMISSION_SURFACE not in v1_by:raise MoonPermissionPolicyReclassificationError("permission v1 requirement absent")
    old_permission=set(v1_by[PERMISSION_SURFACE].attack_ids)
    if old_permission!=set(PRE_EFFECT)|set(REHOMED):raise MoonPermissionPolicyReclassificationError("permission attack universe drift")
    mappings=boundary_matrix(inventory=inventory,repo_root=repo_root,definitions=defs)
    req=[]
    for sd in sorted(FENCE_SURFACES):req.append(SurfaceBypassRequirementV2(sd,tuple(v1_by[sd].attack_ids),POLICY_VERSION,"Fence-surface bypass requirements are unchanged from Policy V1.").validate())
    req.append(SurfaceBypassRequirementV2(PERMISSION_SURFACE,PRE_EFFECT,POLICY_VERSION,"Only guards that can deny before connection.request are bypass requirements for the authority-observation surface.").validate())
    bymap={m.attack_id:m for m in mappings}
    sec=(
        RehomedSecurityRequirementV2("UNTRUSTED_PERMISSION",PERMISSION_SURFACE,"POST_OBSERVATION_DECISION",PERMISSION_SURFACE,bymap["UNTRUSTED_PERMISSION"].pep_name,bymap["UNTRUSTED_PERMISSION"].expected_denial,bymap["UNTRUSTED_PERMISSION"].effect_boundary_relation,"ADMISSION_DECISION_NEGATIVE_EVIDENCE","CONTROL_FLOW_OBSERVED_EVIDENCE_REQUIRED","Trusting a returned permission remains a mandatory admission-decision security requirement; no negative live permission state is fabricated.",bymap["UNTRUSTED_PERMISSION"].source_refs).validate(),
        RehomedSecurityRequirementV2("STALE_AUTHORITY_SOURCE",PERMISSION_SURFACE,"DOWNSTREAM_CURRENTNESS_GUARD",OS_REPLACE_SURFACE,bymap["STALE_AUTHORITY_SOURCE"].pep_name,bymap["STALE_AUTHORITY_SOURCE"].expected_denial,bymap["STALE_AUTHORITY_SOURCE"].effect_boundary_relation,"DOWNSTREAM_CURRENTNESS_NEGATIVE_EVIDENCE","CONTROL_FLOW_OBSERVED_EVIDENCE_REQUIRED","Authority freshness remains mandatory before the certified os.replace effect; pre-fence currentness now permits effect-free negative evidence while post-prepare revalidation preserves TOCTOU defence.",bymap["STALE_AUTHORITY_SOURCE"].source_refs).validate(),
    )
    if set(PRE_EFFECT)|{x.attack_id for x in sec}!=old_permission:raise MoonPermissionPolicyReclassificationError("security requirement dropped during reclassification")
    policy=MediationAttackRequirementPolicyV2(inventory.digest(),inventory.revision,POLICY_VERSION,v1.digest(),tuple(sorted(req,key=lambda x:x.surface_digest)),tuple(sorted(sec,key=lambda x:x.attack_id)),tuple(sorted(m.digest() for m in mappings)),("policy-v1-lineage:"+v1.digest(),"no-security-requirement-dropped","no-post-effect-denial-as-bypass")).validate()
    return att,mappings,policy

def materialize_policy_v2_readiness(*,inventory:EffectSurfaceInventory,taxonomy_report:EffectTaxonomyReconciliationReport,repo_root:Path):
    base=materialize_seven_closure_readiness(inventory=inventory,taxonomy_report=taxonomy_report,repo_root=repo_root)
    att,mappings,policy=policy_v2(inventory=inventory,repo_root=repo_root)
    all_results=tuple(att.bypass_results)+tuple(base.structural.bypass_results);by={(r.surface_digest,r.attack_id):r for r in all_results}
    if len(by)!=len(all_results):raise MoonPermissionPolicyReclassificationError("duplicate bypass result")
    required=policy.required_attack_map()
    assessment=CompleteMediationReassessment().reassess(inventory=inventory,bindings=tuple(att.bindings[k] for k in sorted(att.bindings)),results=all_results,required_attacks=required,observation_evidence_refs=(f"policy-v2:{policy.digest()}",f"predecessor-policy:{policy.predecessor_policy_digest}",f"structural-plan:{base.structural.plan.digest()}"))
    status=dict(assessment.surface_statuses)
    seven=set(FENCE_SURFACES)|{PERMISSION_SURFACE}
    if any(status[sd]!="MEDIATED" for sd in seven):raise MoonPermissionPolicyReclassificationError("v2 seven-surface bypass closure incomplete")
    closure=[]
    for sd in sorted(seven):
        req=required[sd];selected=tuple(by[(sd,a)] for a in req)
        b=att.bindings[sd];chain=att.chains[sd];refs=[]
        for seq in (b.evidence_refs,chain.evidence_refs,tuple(x for r in selected for x in r.evidence_refs)):
            for x in seq:
                if x not in refs:refs.append(x)
        for x in (f"policy-v2:{policy.digest()}",f"predecessor-policy:{policy.predecessor_policy_digest}"):
            if x not in refs:refs.append(x)
        closure.append(MediationClosureRecord(sd,inventory.digest(),b.digest(),chain.trace_digest,tuple(sorted(r.digest() for r in selected)),"MEDIATED",tuple(refs)).validate())
    carrier=GlobalMediationClosureCarrierBuilder().materialize(inventory=inventory,taxonomy_report=taxonomy_report,closure_records=tuple(closure),evidence_refs=(f"policy-v2:{policy.digest()}","seven-surface-v2-bypass-closure","security-obligations-remain-explicit"))
    counts={s:sum(1 for x in carrier.surface_statuses if x.status==s) for s in ("MEDIATED","PARTIAL","UNMEDIATED","UNKNOWN")}
    if counts!={"MEDIATED":7,"PARTIAL":0,"UNMEDIATED":0,"UNKNOWN":229} or carrier.global_status!="UNKNOWN":raise MoonPermissionPolicyReclassificationError("v2 global counts drift")
    unresolved=tuple(sorted(x.attack_id for x in policy.security_requirements if x.evidence_state!="CANONICAL_DENIAL_PRESENT"))
    next_plan=("UNTRUSTED_PERMISSION:extract-or-introduce-pure-admission-decision-boundary-before-negative-evidence","STALE_AUTHORITY_SOURCE:materialize-canonical-pre-fence-currentness-negative-evidence")
    report=PermissionPolicyTopologyReadinessReportV2(inventory.digest(),taxonomy_report.digest(),policy.predecessor_policy_digest,policy.digest(),tuple(sorted(m.digest() for m in mappings)),tuple(sorted(x.digest() for x in policy.security_requirements)),tuple(sorted(mediation_closure_record_digest(x) for x in closure)),carrier.digest(),7,229,unresolved,next_plan,"UNKNOWN",("control-flow-source-proven","no-live-execution","no-security-requirement-dropped")).validate()
    return mappings,policy,tuple(closure),carrier,report

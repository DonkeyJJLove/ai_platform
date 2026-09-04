from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping,Tuple

from cyber_lion.contracts.complete_mediation import EffectSurfaceInventory
from cyber_lion.contracts.mediation_falsification import MediationBindingCandidate
from cyber_lion.enterprise.mediation_falsification import MediationBindingRegistry,SurfaceBindingResolver
from cyber_lion.enterprise.production_mediation import MediationChainReconstructor,ProductionEffectInventory
from tools.p0_surface_closure_campaign import RECEIPT_IMPLIED_MOON_SURFACES,certified_runtime_evidence
from tools.p0_moon_seven_binding_contract import (
    MoonBindingOutcome,MoonEvidenceComponent,MoonFalsificationCarrierSpec,
    MoonSafeAttackSpec,MoonSevenBindingPlan,MoonSurfaceEvidenceBundle,
)

EXPECTED_SCAN_DIGEST="2e509f22b7684e465dbebba73886aa9eae74f166480cb7e46d5be90a02a566d3"
SEVEN=tuple(sorted(RECEIPT_IMPLIED_MOON_SURFACES))
PERMISSION="dbff98ee0801784d8616fc32d67dfbb2ea19fbfcc1cfbda829cf904953f5631b"
FENCE=set(SEVEN)-{PERMISSION}
DIRECT_OBSERVER_BLOCKED=frozenset({
    "478e559a2f8762b471ec9d69eca2bf03ed2744ab0e4f34593ab5060ae95cad9d",
    "e631906532cb4c60aa69736270432263cb1d5346afde33cbb01fecec6c793de0",
})
RUN_ID="33911284689"
JOB_ID="101148041371"
EFFECT_KEY="3ad38b9be4ea737d77c672f97f430cb32a4ba432327f5d1086e38f18327dc4c8"
RECON="6648aeb323c104946ec91e5e2af4c53282f01561ed4dce2d7867775c0812819e"
REQUEST="3e26319a2f7fa916898fac51a1d6cb2bdaa7627637cf78adbe8ab16b9d5d3b46"
ADMISSION="2bdbfac9c00b143a9dda95881613747baef473261b6118ce1f7eeb4735cecca7"
PRE="cca4b377f63c63e2b87981e5c0fb2b9fe10f1035b6375e6be70815195ac9fc06"
POST="eac930cce6a4019e020db0784259c9438d7686cc7e7358db6a0c6001f34067e9"
TARGET="/home/d2j3/lion-p0-moon-replace-live-cert-r1.canary"
FENCE_PATH="/home/d2j3/.lion-moon-file-write-fence.sqlite3"
RUNNER="lion-moon-r9d8-test"
HOST="LION-AUTH-LAB"
MACHINE="e69aa593257d47b8885d1bd87710b196"
AGENT=24
BLOBS={
    "cyber_lion.enterprise.moon_file_write.py":"ebc407df90b4bf7311e901ffeb6d389ad26efd36",
    "cyber_lion.enterprise.moon_file_write_mediation.py":"2d4e704cf6143893141cdaae1d0810e50d874522",
}
LIVE_REFS=(
    f"github-actions-run:{RUN_ID}",
    f"github-actions-job:{JOB_ID}",
    f"moon-effect-key:{EFFECT_KEY}",
    f"moon-reconciliation-digest:{RECON}",
)

class MoonSevenBindingError(RuntimeError):pass

@dataclass(frozen=True)
class MoonSevenArtifacts:
    plan:MoonSevenBindingPlan
    carrier:MoonFalsificationCarrierSpec
    bundles:Mapping[str,MoonSurfaceEvidenceBundle]
    candidates:Mapping[str,MediationBindingCandidate]
    bindings:Mapping[str,object]
    chains:Mapping[str,object]
    components:Mapping[str,Tuple[MoonEvidenceComponent,...]]

def _payload(**kw):return tuple(sorted((str(k),str(v)) for k,v in kw.items()))
def _refs(*xs):return tuple(dict.fromkeys(str(x) for x in xs if x))
def _component(kind,subject,revision,state="OBSERVED",refs=LIVE_REFS,**payload):
    return MoonEvidenceComponent(kind,subject,revision,_payload(**payload),_refs(*refs),state).validate()

def _method_name(sd):
    return {
        "478e559a2f8762b471ec9d69eca2bf03ed2744ab0e4f34593ab5060ae95cad9d":"DurableMoonFileWriteFence._initialize",
        "e631906532cb4c60aa69736270432263cb1d5346afde33cbb01fecec6c793de0":"DurableMoonFileWriteFence._connect",
        "e5e829051f5e73e2d4f8135c1b6e1bc76e4712b6e4a91162ddd6cd218eac406b":"DurableMoonFileWriteFence.prepare",
        "135df096a721d0932a9ee3b51f93bb19a130f2bd68e96535e646d5e78311fd0c":"DurableMoonFileWriteFence.mark_attempted",
        "39ad42d545df0e5fd80b99266dc419a84dc1528746e398ecbdeb69b63f631484":"DurableMoonFileWriteFence.mark_observed",
        "99cfcdb99882099f89c90f9247e1bf13eaacb48422c7e276bed43e216e419fad":"DurableMoonFileWriteFence.mark_reconciled",
        PERMISSION:"_PermissionAdmissionResolver.resolve/_github_permission",
    }[sd]

def _transition(sd):
    return {
        "478e559a2f8762b471ec9d69eca2bf03ed2744ab0e4f34593ab5060ae95cad9d":"ENSURE_SCHEMA",
        "e631906532cb4c60aa69736270432263cb1d5346afde33cbb01fecec6c793de0":"SET_WAL_AND_FULL",
        "e5e829051f5e73e2d4f8135c1b6e1bc76e4712b6e4a91162ddd6cd218eac406b":"INSERT_PREPARED",
        "135df096a721d0932a9ee3b51f93bb19a130f2bd68e96535e646d5e78311fd0c":"PREPARED_TO_ATTEMPTED",
        "39ad42d545df0e5fd80b99266dc419a84dc1528746e398ecbdeb69b63f631484":"ATTEMPTED_TO_OBSERVED",
        "99cfcdb99882099f89c90f9247e1bf13eaacb48422c7e276bed43e216e419fad":"OBSERVED_TO_RECONCILED",
        PERMISSION:"DOUBLE_PERMISSION_RESOLVE",
    }[sd]

def _build_components(inventory,surface):
    sd=surface.digest();rev=inventory.revision;blob=BLOBS[surface.effect_provider]
    common=(surface.entrypoints[0],f"source-blob:{blob}")+LIVE_REFS
    effect=_component(
        "effect_contract",sd,rev,refs=common,surface_digest=sd,effect_class=surface.effect_class,
        provider=surface.effect_provider,entrypoint=surface.entrypoints[0],mutation_kind=surface.mutation_kind,
        target_class=surface.target_class,authority_class=surface.authority_class,source_blob=blob,
    )
    if sd==PERMISSION:
        authority=_component(
            "authority_source",sd,rev,refs=common,model="github-collaborator-permission-pdp-v2",
            repository="DonkeyJJLove/ai_platform",actor="DonkeyJJLove",control_issue=144,
            request_digest=REQUEST,admission_digest=ADMISSION,
            token_permissions="contents:read,issues:read,metadata:read",
        )
        current=_component(
            "currentness_source",sd,rev,refs=common,model="double-resolve-admission-digest-equality",
            request_digest=REQUEST,admission_digest=ADMISSION,source_event_binding="sealed-in-admission",
        )
        pep=_component(
            "pep_identity",sd,rev,refs=common,model="_PermissionAdmissionResolver.resolve",
            checks="repository+actor+trusted_permission",trusted_permissions="admin,maintain,write",source_blob=blob,
        )
        observers=(
            _component(
                "observer_identity",sd,rev,refs=common,role="permission-response",
                model="_github_permission response validator",checks="status=200,max=65536,json,permission-string",source_blob=blob,
            ),
            _component(
                "observer_identity",sd,rev,refs=common,role="external-receipt",
                model="GitHub Actions immutable job log",run_id=RUN_ID,job_id=JOB_ID,reconciliation_digest=RECON,
            ),
        )
        reconciliation=_component(
            "reconciliation_boundary",sd,rev,refs=common,
            model="second-resolve admission digest equality + terminal receipt",
            admission_digest=ADMISSION,reconciliation_digest=RECON,
        )
        replay=_component(
            "replay_guard",sd,rev,refs=common,
            model="sealed request/source-event + repeated authority resolution",
            request_digest=REQUEST,admission_digest=ADMISSION,control_issue=144,
        )
        scope=_component(
            "bounded_scope",sd,rev,refs=common,host="api.github.com",method="GET",
            repository="DonkeyJJLove/ai_platform",actor="DonkeyJJLove",
            path="/repos/DonkeyJJLove/ai_platform/collaborators/DonkeyJJLove/permission",
            timeout_seconds=20,max_response_bytes=65536,
        )
    else:
        authority=_component(
            "authority_source",sd,rev,refs=common,model="CanonicalMoonFileWriteAdmission.binds",
            request_digest=REQUEST,admission_digest=ADMISSION,actor="DonkeyJJLove",
            repository="DonkeyJJLove/ai_platform",control_issue=144,runner=RUNNER,target=TARGET,
        )
        current=_component(
            "currentness_source",sd,rev,refs=common,model=_transition(sd),effect_key=EFFECT_KEY,
            pre_observation_digest=PRE,post_observation_digest=POST,fence_path=FENCE_PATH,
        )
        pep=_component(
            "pep_identity",sd,rev,refs=common,model=_method_name(sd),
            mediator="CanonicalMoonFileWriteMediator.execute",source_blob=blob,effect_key=EFFECT_KEY,
        )
        if sd in DIRECT_OBSERVER_BLOCKED:
            obs_state="CANDIDATE_UNOBSERVED"
            obs_model="planned read-only PRAGMA/table schema verifier"
            reconciliation_state="CANDIDATE_UNOBSERVED"
            replay_state="CANDIDATE_UNOBSERVED"
        else:
            obs_state="OBSERVED"
            obs_model="DurableMoonFileWriteFence.get + MoonFileWriteFenceRecord.validate"
            reconciliation_state="OBSERVED"
            replay_state="OBSERVED"
        observers=(
            _component(
                "observer_identity",sd,rev,state=obs_state,refs=common,role="effect-readback",
                model=obs_model,effect_key=EFFECT_KEY,fence_path=FENCE_PATH,
            ),
            _component(
                "observer_identity",sd,rev,refs=common,role="external-receipt",
                model="GitHub Actions immutable job log",run_id=RUN_ID,job_id=JOB_ID,reconciliation_digest=RECON,
            ),
        )
        reconciliation=_component(
            "reconciliation_boundary",sd,rev,state=reconciliation_state,refs=common,
            model="MOON fence state machine + terminal MATCH receipt",transition=_transition(sd),
            effect_key=EFFECT_KEY,reconciliation_digest=RECON,
        )
        replay=_component(
            "replay_guard",sd,rev,state=replay_state,refs=common,
            model="effect-key durable uniqueness + request/admission uniqueness",
            effect_key=EFFECT_KEY,request_digest=REQUEST,admission_digest=ADMISSION,fence_path=FENCE_PATH,
        )
        scope=_component(
            "bounded_scope",sd,rev,refs=common,fence_path=FENCE_PATH,effect_key=EFFECT_KEY,
            target=TARGET,transition=_transition(sd),database_scope="single moon_file_write_effect row",
        )
    execution=_component(
        "execution_boundary",sd,rev,refs=common,runner_name=RUNNER,runner_agent_id=AGENT,
        runner_group="Default",runner_version="2.337.0",execution_host=HOST,machine_id=MACHINE,
        workflow=".github/workflows/moon-file-write.yml",live_run=RUN_ID,live_job=JOB_ID,
    )
    verifier=_component(
        "verifier_identity",sd,rev,refs=common,model="GitHub Actions job log receipt observer",
        run_id=RUN_ID,job_id=JOB_ID,runner_name=RUNNER,machine_name=HOST,reconciliation_digest=RECON,
    )
    comps=(effect,authority,current,pep,execution,*observers,reconciliation,replay,scope,verifier)
    blockers=[]
    for c in comps:
        if c.evidence_state!="OBSERVED":
            payload=dict(c.payload)
            blockers.append(c.component_type+":"+payload.get("role",payload.get("model","unobserved")))
    bundle=MoonSurfaceEvidenceBundle(
        sd,effect.digest(),authority.digest(),current.digest(),pep.digest(),execution.digest(),
        tuple(x.digest() for x in observers),reconciliation.digest(),replay.digest(),scope.digest(),verifier.digest(),
        tuple(sorted(blockers)),_refs(*common,*(f"component:{x.digest()}" for x in comps)),
    ).validate()
    return comps,bundle

def _attacks():
    fence=tuple(sorted(FENCE));perm=(PERMISSION,);refs=("moon-seven-carrier:candidate-unattached",)+LIVE_REFS
    rows=[
        ("STALE_EFFECT_KEY",fence,"fence","DurableMoonFileWriteFence.get","effect unknown","STRUCTURAL_ONLY"),
        ("WRONG_EXPECTED_STATE",fence,"fence","CanonicalMoonFileWriteMediator.execute","REPLACE pre-state mismatch","SAFE_LIVE_DENIAL"),
        ("REPLAYED_EFFECT_KEY",fence,"fence","CanonicalMoonFileWriteMediator.execute","durable file-write replay denied","SAFE_LIVE_DENIAL"),
        ("CROSS_EPOCH_BINDING",fence,"binding","MediationBindingRegistry.register","cross-epoch binding replay","STRUCTURAL_ONLY"),
        ("SURFACE_SUBSTITUTION",fence,"binding","SurfaceBindingResolver.resolve","surface substitution","STRUCTURAL_ONLY"),
        ("PROVIDER_SUBSTITUTION",fence,"binding","SurfaceBindingResolver.resolve","provider substitution","STRUCTURAL_ONLY"),
        ("ENTRYPOINT_SUBSTITUTION",fence,"binding","SurfaceBindingResolver.resolve","entrypoint substitution","STRUCTURAL_ONLY"),
        ("REPOSITORY_SUBSTITUTION",perm,"permission","moon_file_write._execute","repository substitution denied","SAFE_LIVE_DENIAL"),
        ("ACTOR_SUBSTITUTION",perm,"permission","_PermissionAdmissionResolver.resolve","authority subject substitution","SAFE_LIVE_DENIAL"),
        ("UNTRUSTED_PERMISSION",perm,"permission","_PermissionAdmissionResolver.resolve","actor permission is not trusted","BLOCKED_LIVE"),
        ("STALE_AUTHORITY_SOURCE",perm,"permission","CanonicalMoonFileWriteMediator.execute","authority drift","BLOCKED_LIVE"),
        ("CONTROL_ISSUE_SUBSTITUTION",perm,"permission","moon_file_write._execute","wrong control issue","SAFE_LIVE_DENIAL"),
    ]
    return tuple(MoonSafeAttackSpec(a,s,f,e,d,c,False,refs).validate() for a,s,f,e,d,c in rows)

def materialize_seven(*,inventory:EffectSurfaceInventory)->MoonSevenArtifacts:
    inventory.validate()
    if inventory.scan_digest!=EXPECTED_SCAN_DIGEST:raise MoonSevenBindingError("scan digest drift")
    known={s.digest():s for s in inventory.surfaces}
    if set(SEVEN)-set(known):raise MoonSevenBindingError("seven surface drift")
    traces={t.surface_digest:t for t in ProductionEffectInventory().materialize(inventory=inventory,runtime_evidence=certified_runtime_evidence())}
    epoch="P0-MOON-SEVEN-R1@"+inventory.revision[:12]
    resolver=SurfaceBindingResolver()
    registry=MediationBindingRegistry(inventory_digest=inventory.digest(),epoch=epoch)
    reconstructor=MediationChainReconstructor()
    bundles={};candidates={};bindings={};chains={};components={};outcomes=[]
    for sd in SEVEN:
        s=known[sd]
        comps,bundle=_build_components(inventory,s)
        components[sd]=comps;bundles[sd]=bundle
        candidate=MediationBindingCandidate(
            inventory.digest(),sd,bundle.effect_contract_digest,bundle.pep_identity_digest,
            bundle.authority_source_digest,bundle.currentness_source_digest,bundle.execution_boundary_digest,
            bundle.replay_guard_digest,bundle.observer_identity_digests,bundle.reconciliation_boundary_digest,
            s.effect_provider,s.entrypoints[0],bundle.evidence_refs,epoch,
        ).validate()
        candidates[sd]=candidate
        if bundle.blockers:
            outcomes.append(MoonBindingOutcome(sd,candidate.digest(),"","","BLOCKED",bundle.blockers,bundle.evidence_refs).validate())
            continue
        binding=resolver.resolve(inventory=inventory,surface=s,candidate=candidate)
        registry.register(candidate,binding)
        bindings[sd]=binding
        trace=traces[sd]
        if trace.epistemic_state!="OBSERVED":raise MoonSevenBindingError("expected observed trace")
        chain=reconstructor.reconstruct(
            inventory=inventory,trace=trace,binding=binding,replay_guard_digest=bundle.replay_guard_digest,
            bounded_scope_digest=bundle.bounded_scope_digest,verifier_identity_digest=bundle.verifier_identity_digest,
            epoch=epoch,
        )
        if chain is None:raise MoonSevenBindingError("chain unexpectedly incomplete")
        chains[sd]=chain
        outcomes.append(MoonBindingOutcome(sd,candidate.digest(),binding.digest(),chain.digest(),"RESOLVED",(),bundle.evidence_refs).validate())
    attacks=_attacks()
    carrier=MoonFalsificationCarrierSpec(
        "DonkeyJJLove/ai_platform",inventory.revision,144,RUNNER,AGENT,HOST,MACHINE,TARGET,FENCE_PATH,
        SEVEN,tuple(a.digest() for a in attacks),True,False,False,False,False,"CANDIDATE_UNATTACHED",
        _refs("parent-pr:262",*LIVE_REFS),
    ).validate()
    plan=MoonSevenBindingPlan(
        inventory.digest(),inventory.scan_digest,7,len(bindings),len(chains),7-len(bindings),0,
        tuple(sorted(outcomes,key=lambda x:x.surface_digest)),attacks,carrier.digest(),False,"UNKNOWN",
        _refs("parent-pr:262",*LIVE_REFS),
    ).validate()
    return MoonSevenArtifacts(plan,carrier,bundles,candidates,bindings,chains,components)

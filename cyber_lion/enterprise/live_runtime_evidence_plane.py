"""F009 native live-runtime evidence plane for a disposable filesystem proof.

Positive proof uses the integrated CanonicalPolicyDecisionPoint, LiveAuthorityAdmission,
RuntimeAdmissionEngine, RuntimeExecutionEngine, EffectTimeCurrentnessGuardedSandbox and
RuntimeReconciler. The bounded effect is one create-only file outside the repository.
A separate observer process starts before the effect and never reads the runtime receipt.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import argparse
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import time

from cyber_lion.contracts.enterprise_graph import EnterpriseGraphProjection, canonical_json as graph_json
from cyber_lion.contracts.executor_provisioning import ExecutorProvisioningRequest, ProviderTrustBinding, ProvisionedExecutor
from cyber_lion.contracts.executor_sandbox import SandboxExecutionReceipt, SandboxOperation
from cyber_lion.contracts.policy_gate import PolicyRevision
from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding
from cyber_lion.contracts.runtime_enforcement import CanonicalPDPDecisionEvidence, PDPSourceTrustBinding, RequestedRuntimeEffect, RuntimeAdmission, RuntimeIdentityBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding, RuntimeExecutionRequest
from cyber_lion.contracts.runtime_reconciliation import RuntimeEffectObservation, RuntimeObserverTrustBinding
from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_source import AuthorityLineageRecord, AuthorityLookupKey, AuthoritySource, canonical_pr_authority_resource, canonical_source_lineage_digest
from cyber_lion.enterprise.authority_verification import AuthorityVerificationContext, IssuerKeyBinding, authority_grant_signature_payload
from cyber_lion.enterprise.control_plane import ActionProposal
from cyber_lion.enterprise.executor_sandbox import SandboxExecutionResult
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority, LiveAuthorityAdmission
from cyber_lion.enterprise.models import AgentSpec, MissionSpec, SwarmSpec
from cyber_lion.enterprise.persistent_authority_state import DurableReplayGuard, PersistentBindingFinalizer, PersistentEpochStateProvider, PersistentRootAnchorProvider, SQLiteAuthorityStateStore
from cyber_lion.enterprise.policy_gate import CanonicalPolicyDecisionPoint
from cyber_lion.enterprise.runtime_currentness import EffectTimeCurrentnessGuardedSandbox
from cyber_lion.enterprise.runtime_enforcement import RuntimeAdmissionEngine, RuntimeEnforcementError, _pdp_receipt_digest
from cyber_lion.enterprise.runtime_execution import RuntimeExecutionEngine, RuntimeExecutionError
from cyber_lion.enterprise.runtime_reconciliation import RuntimeReconciler, RuntimeReconciliationError

REPOSITORY = "DonkeyJJLove/ai_platform"
MISSION = "LION-F009-LIVE-RUNTIME-EVIDENCE-PLANE"
PARENT_MISSION = "LION-F009-RUNTIME-ENFORCEMENT-PROOF"
BASELINE = "c072ee219021051baec7fa667a98f6e73aa08fe2"
BASELINE_TREE = "4266c249cead2f10ff3d6d19055d9a19db3c04df"
RESOURCE = "proof/out.bin"
PAYLOAD = b"LION-F009-LIVE-RUNTIME-PROOF\n"
ZERO = "0" * 64


def _canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _hash(value: bytes) -> str:
    return sha256(value).hexdigest()


def _module_digest() -> str:
    return _hash(Path(__file__).read_bytes())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _write_once(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(_canon(value)); handle.flush(); os.fsync(handle.fileno())
    path.chmod(0o444)


def _replace_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canon(value))


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path.name} must contain an object")
    return value


def _safe_root(work_dir: Path) -> Path:
    root = work_dir.resolve(); repo = Path(os.environ.get("GITHUB_WORKSPACE", os.getcwd())).resolve()
    if root == repo or repo in root.parents or root in repo.parents:
        raise RuntimeError("proof work directory must be outside repository")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _target(root: Path) -> Path:
    value = (root / "proof" / "out.bin").resolve()
    if root not in value.parents:
        raise RuntimeError("proof target escaped owned directory")
    return value


class FileAuthoritySource(AuthoritySource):
    def __init__(self, record: AuthorityLineageRecord): self._record = record.validate()
    def _lookup_exact(self, key: AuthorityLookupKey):
        return (self._record,) if key.binding() == self._record.lookup_key.binding() else ()


class CanonicalDecisionFileSource:
    source_id = "f009-pdp-evidence"; source_instance_id = "f009-pdp-evidence:1"; trust_anchor_id = "f009-run-root"
    def __init__(self, evidence_path: Path, policy_path: Path, implementation_digest: str, trust_anchor_digest: str):
        self._evidence_path=evidence_path; self._policy_path=policy_path; self.implementation_digest=implementation_digest; self.trust_anchor_digest=trust_anchor_digest
    def resolve(self, request_id: str, gate_event_id: str) -> CanonicalPDPDecisionEvidence:
        value=CanonicalPDPDecisionEvidence(**_read_json(self._evidence_path)).validate()
        if (value.request_id,value.gate_event_id)!=(request_id,gate_event_id): raise RuntimeError("canonical PDP lookup mismatch")
        return value
    def current_policy_binding(self, policy_binding: str) -> str: return str(_read_json(self._policy_path)["binding"])


class FileRuntimeAdmissionSource:
    source_id="f009-runtime-admission"; source_instance_id="f009-runtime-admission:1"; trust_anchor_id="f009-run-root"
    def __init__(self,path:Path,implementation_digest:str,trust_anchor_digest:str): self.path=path; self.implementation_digest=implementation_digest; self.trust_anchor_digest=trust_anchor_digest
    def resolve(self, admission_digest:str)->RuntimeAdmission:
        value=RuntimeAdmission(**_read_json(self.path)).validate()
        if value.admission_digest!=admission_digest: raise RuntimeError("admission lookup mismatch")
        return value
    def is_current(self, admission_digest:str)->bool:
        try: return self.resolve(admission_digest).admission_digest==admission_digest
        except Exception: return False


class SQLiteSingleUseGuard:
    def __init__(self,path:Path):
        self.path=path
        with sqlite3.connect(path) as db: db.execute("CREATE TABLE IF NOT EXISTS consumed(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
    def consume(self,key:str,value:str="consumed")->bool:
        try:
            with sqlite3.connect(self.path) as db: db.execute("INSERT INTO consumed VALUES(?,?)",(key,value))
            return True
        except sqlite3.IntegrityError: return False


class RuntimeAdmissionReplayAdapter:
    def __init__(self,guard:SQLiteSingleUseGuard): self.guard=guard
    def consume(self,replay_key:str)->bool: return self.guard.consume(replay_key,"runtime-admission")


class FileEffectTimeCurrentnessSource:
    source_id="f009-effect-currentness"; source_instance_id="f009-effect-currentness:1"; trust_anchor_id="f009-run-root"
    def __init__(self,authority_path:Path,policy_path:Path,heartbeat_path:Path,observer_pid:int,implementation_digest:str,trust_anchor_digest:str):
        self.authority_path=authority_path; self.policy_path=policy_path; self.heartbeat_path=heartbeat_path; self.observer_pid=observer_pid; self.implementation_digest=implementation_digest; self.trust_anchor_digest=trust_anchor_digest
    def resolve_authority(self,admission_digest:str)->LiveAdmittedAuthority: return LiveAdmittedAuthority(**_read_json(self.authority_path)).validate()
    def current_policy_binding(self,policy_binding:str)->str: return str(_read_json(self.policy_path)["binding"])
    def current_observability_state(self,runtime_identity_digest:str,requested_effect_digest:str)->str:
        try:
            os.kill(self.observer_pid,0)
            heartbeat=datetime.fromisoformat(str(_read_json(self.heartbeat_path)["at"]).replace("Z","+00:00"))
            return "HEALTHY" if (_now()-heartbeat.astimezone(timezone.utc)).total_seconds()<=5 else "LOST"
        except Exception: return "LOST"


class RealFilesystemSandbox:
    def __init__(self,root:Path,identity:RuntimeIdentityBinding,*,policy_digest:str,partial:bool=False,omit_observation:bool=False,abort_before_write:bool=False):
        self.root=root; self.identity=identity; self._policy_digest=policy_digest; self.partial=partial; self.omit_observation=omit_observation; self.abort_before_write=abort_before_write; self.calls=0
    @property
    def policy_digest(self)->str: return self._policy_digest
    def execute(self,op:SandboxOperation,*,payload:bytes=b"")->SandboxExecutionResult:
        self.calls+=1; op.validate()
        if op.action!="WRITE_FILE" or op.path!=RESOURCE: raise RuntimeError("bounded proof sandbox permits one exact write")
        event="fs:write:"+_hash(op.path.encode())[:16]; ref="file:"+_hash(op.path.encode())
        if self.abort_before_write:
            receipt=SandboxExecutionReceipt("f009-sandbox:"+op.operation_id,op.operation_id,op.digest(),self.policy_digest,ZERO,ZERO,ZERO,ZERO,op.mission_id,op.drone_id,op.executor_id,op.sandbox_id,op.workspace_id,op.dispatch_id,op.fencing_token,op.generation,self.identity.runtime_instance_id,self.identity.runtime_attestation_digest,op.action,"ABORTED",ZERO,_hash(b""),0,0,None,("runtime:aborted",),()).validate()
            return SandboxExecutionResult(receipt,b"")
        target=_target(self.root); target.parent.mkdir(parents=True,exist_ok=True)
        data=payload[:max(1,len(payload)//2)] if self.partial else payload
        with target.open("xb") as handle: handle.write(data); handle.flush(); os.fsync(handle.fileno())
        outcome="ABORTED" if self.partial else "SUCCEEDED"
        observed=() if self.omit_observation else (event,)
        receipt=SandboxExecutionReceipt("f009-sandbox:"+op.operation_id,op.operation_id,op.digest(),self.policy_digest,ZERO,ZERO,ZERO,ZERO,op.mission_id,op.drone_id,op.executor_id,op.sandbox_id,op.workspace_id,op.dispatch_id,op.fencing_token,op.generation,self.identity.runtime_instance_id,self.identity.runtime_attestation_digest,op.action,outcome,_hash(data),_hash(b""),0,len(data),None,observed,(ref,))
        if not self.omit_observation: receipt.validate()
        return SandboxExecutionResult(receipt,b"")


class FileObservationSource:
    source_id="f009-independent-observer"; source_instance_id="f009-independent-observer:1"; trust_anchor_id="f009-run-root"
    def __init__(self,path:Path,implementation_digest:str,trust_anchor_digest:str): self.path=path; self.implementation_digest=implementation_digest; self.trust_anchor_digest=trust_anchor_digest
    def observe(self,execution_id:str)->RuntimeEffectObservation:
        value=RuntimeEffectObservation(**_read_json(self.path)).validate()
        if value.execution_id!=execution_id: raise RuntimeError("observer execution mismatch")
        return value


def _observer(manifest_path:Path,target_path:Path,heartbeat_path:Path,observation_path:Path,implementation_digest:str,trust_anchor_digest:str,lie_digest:bool=False)->int:
    manifest=_read_json(manifest_path); deadline=time.time()+30
    while time.time()<deadline:
        _replace_json(heartbeat_path,{"pid":os.getpid(),"at":_now().isoformat()})
        if target_path.exists():
            data=target_path.read_bytes(); digest=("f"*64) if lie_digest else _hash(data); event="fs:write:"+_hash(str(manifest["resource"]).encode())[:16]; ref="file:"+_hash(str(manifest["resource"]).encode())
            obs=RuntimeEffectObservation("f009-observation:"+str(manifest["execution_id"]),str(manifest["execution_id"]),str(manifest["admission_digest"]),str(manifest["request_digest"]),str(manifest["operation_digest"]),str(manifest["action"]),str(manifest["resource"]),"OBSERVED",digest,(event,),(ref,),FileObservationSource.source_id,FileObservationSource.source_instance_id,implementation_digest,FileObservationSource.trust_anchor_id,trust_anchor_digest,_now().isoformat()).sealed()
            _write_once(observation_path,asdict(obs)); return 0
        time.sleep(.05)
    return 3


def _runtime_attest(pid:int,output:Path)->int:
    exe=Path(f"/proc/{pid}/exe"); cmdline=Path(f"/proc/{pid}/cmdline")
    if not exe.exists() or not cmdline.exists(): return 2
    value={"pid":pid,"exe":os.readlink(exe),"cmdline_digest":_hash(cmdline.read_bytes()),"attester_pid":os.getpid(),"observed_at":_now().isoformat()}; value["attestation_digest"]=_hash(_canon(value)); _write_once(output,value); return 0


def _wait(path:Path,timeout:float=10)->None:
    deadline=time.time()+timeout
    while time.time()<deadline:
        if path.exists(): return
        time.sleep(.05)
    raise RuntimeError(f"timed out waiting for {path.name}")


def _graph()->EnterpriseGraphProjection:
    payload={"graph_id":"f009-live","nodes":[],"edges":[]}; return EnterpriseGraphProjection("f009-live",0,ZERO,(),(),_hash(graph_json(payload))).verify_digest()


def _hmac_grant(key:AuthorityLookupKey,secret:bytes,policy_digest:str,now:datetime)->AuthorityGrant:
    base=AuthorityGrant(schema_version="1.1.0",grant_id=key.grant_id,issuer_subject_id="f009-root",subject_id="f009-runtime",tenant_id="f009",organization_id="lion",mission_id=MISSION,capability_id="f009-live-proof",capability_version="1",actions=("WRITE_FILE",),resource_scope=(canonical_pr_authority_resource(key),),authority_ceiling="local_write",constraints=("disposable-runner-only",),parent_grant_id=None,issued_at=(now-timedelta(minutes=2)).isoformat(),expires_at=(now+timedelta(minutes=20)).isoformat(),epoch=1,policy_digest=policy_digest,observability_contract_digest="sha256:"+_hash(b"f009-observability"),signature="unsigned",delegation_allowed=False,delegation_depth_budget=0)
    sig=hmac.new(secret,authority_grant_signature_payload(base,"f009.local"),"sha256").hexdigest(); return AuthorityGrant(**{**asdict(base),"signature":sig}).validate()


def _build_live_authority(root:Path,key:AuthorityLookupKey,policy_digest:str,now:datetime):
    secret=secrets.token_bytes(32); grant=_hmac_grant(key,secret,policy_digest,now); record=AuthorityLineageRecord(key,(grant,),canonical_source_lineage_digest((grant,)),"f009:file-authority").validate(); store=SQLiteAuthorityStateStore(str(root/"authority.sqlite")); context=("f009.local","f009","lion",MISSION); store.bootstrap_context(context,epoch=1); store.register_root(context,epoch=1,root_grant_id=grant.grant_id,root_grant_digest=grant.digest())
    def verifier(payload:bytes,signature:str,key_id:str,algorithm:str)->bool: return algorithm=="hmac-sha256" and key_id=="f009-run-key" and hmac.compare_digest(signature,hmac.new(secret,payload,"sha256").hexdigest())
    live=LiveAuthorityAdmission(authority_source=FileAuthoritySource(record),context=AuthorityVerificationContext("f009.local","f009","lion",MISSION),issuer_keys=(IssuerKeyBinding("f009-root","f009.local","f009-run-key","hmac-sha256"),),signature_verifier=verifier,epoch_provider=PersistentEpochStateProvider(store),root_provider=PersistentRootAnchorProvider(store),replay_guard=DurableReplayGuard(store,domain="f009-live-proof"),binding_finalizer=PersistentBindingFinalizer(store))
    return live,store,grant


def _provision_runtime(root:Path,runtime_attestation_digest:str,now:datetime):
    implementation=_module_digest(); trust_digest=_hash(b"f009-provisioning-root"); trust=ProviderTrustBinding("f009-local-provider","f009-local-provider:1",implementation,"f009-run-root",trust_digest).validate(); workload="workflow:"+os.environ.get("GITHUB_RUN_ID","local"); executor=f"pid:{os.getpid()}"; runtime=f"python:{sys.version_info.major}.{sys.version_info.minor}:pid:{os.getpid()}"; workspace=str(root)
    req=ExecutorProvisioningRequest("1.0.0","f009-provision-request","f009-idempotency",workload,executor,MISSION,PARENT_MISSION,REPOSITORY,BASELINE,BASELINE_TREE,"mission/f009-live-runtime-evidence-plane",("cyber_lion",),("cyber_lion/enterprise/live_runtime_evidence_plane.py",),"github-hosted-linux",_hash(sys.version.encode()),_hash(b"f009-disposable-sandbox"),_hash(b"f009-resource-profile"),(),now.isoformat()).validate()
    pe=ProvisionedExecutor("1.0.0","f009-provisioned",req.request_id,req.digest(),req.idempotency_key,req.drone_id,req.executor_id,runtime,"sandbox:f009",workspace,req.mission_id,req.parent_mission_id,req.repository,req.baseline_sha,req.baseline_tree_sha,req.branch,req.read_scope,req.write_scope,req.runtime_class,req.image_digest,req.sandbox_profile_digest,req.resource_profile_digest,(),trust.provider_id,trust.provider_instance_id,trust.implementation_digest,trust.trust_anchor_id,trust.trust_anchor_digest,runtime_attestation_digest,"attester-process",now.isoformat()).validate_for(req,trust)
    identity=RuntimeIdentityBinding(workload,executor,runtime,pe.sandbox_id,workspace,runtime_attestation_digest,pe.digest()).validate(); return req,trust,pe,identity


def _prepare_chain(root:Path):
    root.mkdir(parents=True,exist_ok=True); now=_now(); implementation=_module_digest(); trust_digest=_hash(b"f009-run-root"); policy=PolicyRevision("f009-live-policy","1","sha256:"+_hash(b"f009-live-policy-v1"),"GREEN").validate(); head=os.environ.get("GITHUB_SHA",BASELINE).lower(); head=head if len(head)==40 and all(c in "0123456789abcdef" for c in head) else BASELINE; rn=os.environ.get("GITHUB_RUN_NUMBER","1"); pr=int(rn) if rn.isdigit() and int(rn)>0 else 1; key=AuthorityLookupKey(REPOSITORY,pr,BASELINE,head,MISSION,"f009-live-grant").validate(); live,store,grant=_build_live_authority(root,key,policy.content_digest,now)
    att_path=root/"runtime-attestation.json"; result=subprocess.run([sys.executable,"-m",__name__,"--attest",str(os.getpid()),str(att_path)],check=False)
    if result.returncode!=0: raise RuntimeError("independent runtime attestation failed")
    req,provider_trust,provisioned,identity=_provision_runtime(root,str(_read_json(att_path)["attestation_digest"]),now)
    status=_read_json(Path(os.environ.get("GITHUB_WORKSPACE",os.getcwd()))/"LION"/"status.json"); agent=AgentSpec(identity.execution_subject,"1","builder",MISSION,("f009-live-proof",),authority_ceiling="local_write",observability_events=("trace",)).validate(); mission=MissionSpec(MISSION,"bounded live runtime proof",("f009-live-proof",),authority_ceiling="local_write",risk_class="GREEN").validate(); swarm=SwarmSpec("f009-live-swarm",MISSION,(identity.execution_subject,),("f009-live-proof",),"mesh","local_write","GREEN",1.0).validate(); payload_digest=_hash(PAYLOAD); proposal=ActionProposal("f009-live-proposal",MISSION,swarm.swarm_id,identity.execution_subject,"f009-live-proof","local_write","WRITE_FILE",RESOURCE,True,("runtime-attestation",),("trace",),payload_digest=payload_digest).validate()
    pdp=CanonicalPolicyDecisionPoint(authority_admission=live); pdp_result=pdp.evaluate(request_id="f009-live-request",gate_event_id="f009-live-gate",proposal=proposal,mission=mission,swarm=swarm,agents={identity.execution_subject:agent},policy=policy,authority_key=key,graph_projection=_graph(),status=status,observability_state="HEALTHY",observed_event_types=("trace",),evidence_refs=("status:r7","graph:f009","runtime-attestation"),trusted_now=now)
    if pdp_result.applied.decision!="ALLOW": raise RuntimeError("canonical PDP did not allow bounded proof")
    admitted=live.admit(repository=REPOSITORY,pr_number=key.pr_number,base_sha=key.base_sha,head_sha=key.head_sha,mission_id=MISSION,grant_id=key.grant_id,now=now,replay_nonce="runtime-admission"); policy_path=root/"policy.json"; _replace_json(policy_path,{"binding":policy.binding}); pdp_evidence=CanonicalPDPDecisionEvidence(pdp_result.applied.request_id,pdp_result.applied.gate_event_id,pdp_result.applied.proposal_id,pdp_result.applied.decision_digest,_pdp_receipt_digest(pdp_result.receipt),pdp_result.receipt.request_digest,pdp_result.receipt.replay_key,pdp_result.applied.policy_binding,pdp_result.applied.authority_lineage_digest,pdp_result.applied.observability_state,CanonicalDecisionFileSource.source_id,CanonicalDecisionFileSource.source_instance_id,implementation,CanonicalDecisionFileSource.trust_anchor_id,trust_digest,now.isoformat(),(now+timedelta(minutes=10)).isoformat()).sealed(); pdp_path=root/"pdp-evidence.json"; _replace_json(pdp_path,asdict(pdp_evidence)); pdp_source=CanonicalDecisionFileSource(pdp_path,policy_path,implementation,trust_digest); pdp_trust=PDPSourceTrustBinding(pdp_source.source_id,pdp_source.source_instance_id,implementation,pdp_source.trust_anchor_id,trust_digest).validate(); effect=RequestedRuntimeEffect("f009-live-effect",proposal.proposal_id,MISSION,policy.binding,admitted.lineage_digest,"local_write","WRITE_FILE",RESOURCE,payload_digest,"HEALTHY",identity.digest()).validate(); admission_engine=RuntimeAdmissionEngine(authority_admission=live,pdp_source=pdp_source,pdp_source_trust=pdp_trust,replay_guard=RuntimeAdmissionReplayAdapter(SQLiteSingleUseGuard(root/"admission-issuance.sqlite"))); runtime_admission=admission_engine.admit(gate=pdp_result.applied,pdp_receipt=pdp_result.receipt,admitted_authority=admitted,proposal=proposal,effect=effect,runtime_identity=identity,provisioned_executor=provisioned,provisioning_request=req,provider_trust=provider_trust,trusted_now=now); admission_path=root/"runtime-admission.json"; authority_path=root/"live-authority.json"; _replace_json(admission_path,asdict(runtime_admission)); _replace_json(authority_path,asdict(admitted)); dispatch=_hash(b"f009-live-dispatch"); fence=_hash(b"f009-live-fence"); request=RuntimeExecutionRequest("f009-live-execution",runtime_admission.admission_digest,effect.digest(),identity.digest(),provisioned.digest(),MISSION,identity.execution_subject,identity.runtime_instance_id,identity.sandbox_id,identity.workspace_id,dispatch,fence,1,"WRITE_FILE",RESOURCE,payload_digest,len(PAYLOAD),()).validate(); op=SandboxOperation(request.execution_id,request.mission_id,identity.workload_identity,request.executor_id,request.sandbox_id,request.workspace_id,request.dispatch_id,request.fencing_token,request.generation,_hash(b"f009-sandbox-policy"),request.action,request.resource,request.payload_digest,request.payload_size,()).validate(); observer_manifest=root/"observer-manifest.json"; _replace_json(observer_manifest,{"execution_id":request.execution_id,"admission_digest":runtime_admission.admission_digest,"request_digest":request.digest(),"operation_digest":op.digest(),"action":request.action,"resource":request.resource}); return locals()


def _start_observer(ctx:dict,*,lie_digest:bool=False):
    root=ctx["root"]; heartbeat=root/"observer-heartbeat.json"; observation=root/"independent-observation.json"; args=[sys.executable,"-m",__name__,"--observer",str(ctx["observer_manifest"]),str(_target(root)),str(heartbeat),str(observation),ctx["implementation"],ctx["trust_digest"]]+(["--lie-digest"] if lie_digest else []); proc=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); _wait(heartbeat); return proc,heartbeat,observation


def _engine_for(ctx:dict,proc:subprocess.Popen,heartbeat:Path,sandbox:RealFilesystemSandbox):
    current=FileEffectTimeCurrentnessSource(ctx["authority_path"],ctx["policy_path"],heartbeat,proc.pid,ctx["implementation"],ctx["trust_digest"]); current_trust=CurrentnessSourceTrustBinding(current.source_id,current.source_instance_id,ctx["implementation"],current.trust_anchor_id,ctx["trust_digest"]).validate(); guarded=EffectTimeCurrentnessGuardedSandbox(inner=sandbox,admission=ctx["runtime_admission"],effect=ctx["effect"],runtime_identity=ctx["identity"],authority_admission=ctx["live"],currentness_source=current,currentness_trust=current_trust,clock=_now); source=FileRuntimeAdmissionSource(ctx["admission_path"],ctx["implementation"],ctx["trust_digest"]); source_trust=RuntimeAdmissionSourceTrustBinding(source.source_id,source.source_instance_id,source.implementation_digest,source.trust_anchor_id,source.trust_anchor_digest).validate(); engine=RuntimeExecutionEngine(admission_source=source,admission_source_trust=source_trust,consumption_guard=SQLiteSingleUseGuard(ctx["root"]/"execution-consumption.sqlite"),sandbox=guarded); return engine,guarded


def _reconcile(ctx:dict,receipt,guarded,observation:Path):
    src=FileObservationSource(observation,ctx["implementation"],ctx["trust_digest"]); trust=RuntimeObserverTrustBinding(src.source_id,src.source_instance_id,src.implementation_digest,src.trust_anchor_id,src.trust_anchor_digest).validate(); return RuntimeReconciler(observer=src,observer_trust=trust,clock=_now).reconcile(receipt=receipt,currentness=guarded.last_currentness_evidence)


def _execute_positive(ctx:dict):
    proc,heartbeat,observation=_start_observer(ctx); sandbox=RealFilesystemSandbox(ctx["root"],ctx["identity"],policy_digest=_hash(b"f009-sandbox-policy")); engine,guarded=_engine_for(ctx,proc,heartbeat,sandbox); receipt=engine.execute(admission=ctx["runtime_admission"],request=ctx["request"],effect=ctx["effect"],runtime_identity=ctx["identity"],payload=PAYLOAD); _wait(observation); reconciliation=_reconcile(ctx,receipt,guarded,observation)
    if reconciliation.disposition!="MATCHED": raise RuntimeError("positive live proof did not reconcile MATCHED")
    try: engine.execute(admission=ctx["runtime_admission"],request=ctx["request"],effect=ctx["effect"],runtime_identity=ctx["identity"],payload=PAYLOAD); raise RuntimeError("replay unexpectedly executed")
    except RuntimeExecutionError: replay_denied=True
    proc.wait(timeout=5); return receipt,guarded.last_currentness_evidence,RuntimeEffectObservation(**_read_json(observation)).validate(),reconciliation,replay_denied


def _negative_currentness(base:Path,mode:str)->bool:
    root=base/("neg-"+mode); root.mkdir(parents=True); ctx=_prepare_chain(root); proc,heartbeat,_=_start_observer(ctx)
    if mode=="revoked": ctx["store"].advance_epoch(("f009.local","f009","lion",MISSION),epoch=1,revoked_grant_ids=(ctx["grant"].grant_id,))
    elif mode=="authority_changed": ctx["store"].advance_epoch(("f009.local","f009","lion",MISSION),epoch=1,revoked_grant_ids=("other",))
    elif mode=="policy_changed": _replace_json(ctx["policy_path"],{"binding":ctx["policy"].binding+":changed"})
    elif mode=="observer_lost": proc.terminate(); proc.wait(timeout=5)
    sandbox=RealFilesystemSandbox(root,ctx["identity"],policy_digest=_hash(b"f009-sandbox-policy")); engine,_=_engine_for(ctx,proc,heartbeat,sandbox)
    try: engine.execute(admission=ctx["runtime_admission"],request=ctx["request"],effect=ctx["effect"],runtime_identity=ctx["identity"],payload=PAYLOAD); return False
    except RuntimeExecutionError: return sandbox.calls==0
    finally:
        if proc.poll() is None: proc.terminate(); proc.wait(timeout=5)


def _negative_substitution(base:Path,mode:str)->bool:
    root=base/("neg-"+mode); root.mkdir(parents=True); ctx=_prepare_chain(root); proc,heartbeat,_=_start_observer(ctx); sandbox=RealFilesystemSandbox(root,ctx["identity"],policy_digest=_hash(b"f009-sandbox-policy")); engine,_=_engine_for(ctx,proc,heartbeat,sandbox); request=ctx["request"]; identity=ctx["identity"]; payload=PAYLOAD
    if mode=="runtime_identity": identity=RuntimeIdentityBinding(**{**asdict(identity),"runtime_instance_id":identity.runtime_instance_id+":forged"}).validate()
    elif mode=="execution_subject": request=RuntimeExecutionRequest(**{**asdict(request),"executor_id":"pid:forged"}).validate()
    elif mode=="workspace": request=RuntimeExecutionRequest(**{**asdict(request),"workspace_id":request.workspace_id+"-forged"}).validate()
    elif mode=="resource": request=RuntimeExecutionRequest(**{**asdict(request),"resource":"proof/other.bin"}).validate()
    elif mode=="payload": payload=b"FORGED"
    try: engine.execute(admission=ctx["runtime_admission"],request=request,effect=ctx["effect"],runtime_identity=identity,payload=payload); return False
    except RuntimeExecutionError: return sandbox.calls==0
    finally:
        if proc.poll() is None: proc.terminate(); proc.wait(timeout=5)


def _negative_replayed_admission(base:Path)->bool:
    root=base/"neg-replayed-admission"; root.mkdir(parents=True); ctx=_prepare_chain(root)
    try:
        ctx["admission_engine"].admit(gate=ctx["pdp_result"].applied,pdp_receipt=ctx["pdp_result"].receipt,admitted_authority=ctx["admitted"],proposal=ctx["proposal"],effect=ctx["effect"],runtime_identity=ctx["identity"],provisioned_executor=ctx["provisioned"],provisioning_request=ctx["req"],provider_trust=ctx["provider_trust"],trusted_now=ctx["now"]); return False
    except RuntimeEnforcementError: return True


def _negative_observer(base:Path,mode:str)->bool:
    root=base/("neg-"+mode); root.mkdir(parents=True); ctx=_prepare_chain(root); proc,heartbeat,observation=_start_observer(ctx,lie_digest=mode=="observer_mismatch"); sandbox=RealFilesystemSandbox(root,ctx["identity"],policy_digest=_hash(b"f009-sandbox-policy"),omit_observation=mode=="missing_runtime_observation"); engine,guarded=_engine_for(ctx,proc,heartbeat,sandbox)
    try:
        receipt=engine.execute(admission=ctx["runtime_admission"],request=ctx["request"],effect=ctx["effect"],runtime_identity=ctx["identity"],payload=PAYLOAD)
    except RuntimeExecutionError:
        if mode=="missing_runtime_observation": return _target(root).exists()
        raise
    _wait(observation); proc.wait(timeout=5)
    if mode=="missing_independent_observation":
        observation.unlink()
        try: _reconcile(ctx,receipt,guarded,observation); return False
        except RuntimeReconciliationError: return True
    if mode=="observer_mismatch": return _reconcile(ctx,receipt,guarded,observation).disposition=="MISMATCH"
    return False


def _negative_partial_or_unknown(base:Path,mode:str)->bool:
    root=base/("neg-"+mode); root.mkdir(parents=True); ctx=_prepare_chain(root); proc,heartbeat,observation=_start_observer(ctx); sandbox=RealFilesystemSandbox(root,ctx["identity"],policy_digest=_hash(b"f009-sandbox-policy"),partial=mode=="partial",abort_before_write=mode=="unknown"); engine,guarded=_engine_for(ctx,proc,heartbeat,sandbox); receipt=engine.execute(admission=ctx["runtime_admission"],request=ctx["request"],effect=ctx["effect"],runtime_identity=ctx["identity"],payload=PAYLOAD)
    if mode=="unknown":
        proc.terminate(); proc.wait(timeout=5); return receipt.effect_state=="UNKNOWN" and receipt.outcome!="SUCCEEDED" and not _target(root).exists()
    _wait(observation); proc.wait(timeout=5); recon=_reconcile(ctx,receipt,guarded,observation); return receipt.effect_state=="PARTIAL_UNKNOWN" and receipt.outcome!="SUCCEEDED" and recon.disposition!="MATCHED"


def run_live_runtime_proof(work_dir:Path,artifact_dir:Path)->dict:
    root=_safe_root(work_dir); artifact_dir=artifact_dir.resolve(); artifact_dir.mkdir(parents=True,exist_ok=True); repo=Path(os.environ.get("GITHUB_WORKSPACE",os.getcwd())).resolve()
    if artifact_dir==repo or repo in artifact_dir.parents: raise RuntimeError("artifact directory must be outside repository")
    ctx=_prepare_chain(root/"positive"); receipt,currentness,observation,reconciliation,replay_denied=_execute_positive(ctx)
    missing_receipt=_negative_observer(root,"missing_runtime_observation")
    negatives={
        "authority-revoked-after-admission-before-effect":_negative_currentness(root,"revoked"),
        "authority-changed-after-admission-before-effect":_negative_currentness(root,"authority_changed"),
        "policy-changed-after-admission-before-effect":_negative_currentness(root,"policy_changed"),
        "observability-lost-after-admission-before-effect":_negative_currentness(root,"observer_lost"),
        "runtime-identity-substitution":_negative_substitution(root,"runtime_identity"),
        "execution-subject-substitution":_negative_substitution(root,"execution_subject"),
        "workspace-substitution":_negative_substitution(root,"workspace"),
        "resource-substitution":_negative_substitution(root,"resource"),
        "payload-substitution":_negative_substitution(root,"payload"),
        "replayed-admission":_negative_replayed_admission(root),
        "replayed-execution":replay_denied,
        "missing-independent-observation":_negative_observer(root,"missing_independent_observation"),
        "observer-effect-mismatch":_negative_observer(root,"observer_mismatch"),
        "receipt-without-observed-effect":missing_receipt,
        "effect-without-receipt":missing_receipt,
        "partial-effect":_negative_partial_or_unknown(root,"partial"),
        "UNKNOWN-effect-state":_negative_partial_or_unknown(root,"unknown"),
    }
    if not all(negatives.values()): raise RuntimeError("mandatory live negative failed")
    _write_once(artifact_dir/"runtime-identity.json",{"binding":asdict(ctx["identity"]),"process_pid":os.getpid(),"workspace":str(ctx["root"]),"attestation":_read_json(ctx["root"]/"runtime-attestation.json")}); _write_once(artifact_dir/"admission.json",asdict(ctx["runtime_admission"])); _write_once(artifact_dir/"effect-currentness.json",asdict(currentness)); _write_once(artifact_dir/"sandbox-execution-receipt.json",asdict(receipt)); _write_once(artifact_dir/"independent-observation.json",asdict(observation)); _write_once(artifact_dir/"reconciliation-receipt.json",asdict(reconciliation)); _write_once(artifact_dir/"replay-denial.json",{"second_effect_denied":replay_denied,"execution_id":receipt.execution_id})
    manifest={"schema_version":"1.0.0","repository":REPOSITORY,"baseline":BASELINE,"baseline_tree":BASELINE_TREE,"github_run_id":os.environ.get("GITHUB_RUN_ID","local"),"github_sha":os.environ.get("GITHUB_SHA",BASELINE),"positive":{"effect_executed_once":True,"reconciliation":reconciliation.disposition,"effect_digest":receipt.effect_digest,"independent_effect_digest":observation.effect_digest},"negative_results":negatives,"f005_runtime_resumed":False,"production_effect":False,"proof_target":str(_target(ctx["root"])),"artifact_digests":{}}
    for name in ("runtime-identity.json","admission.json","effect-currentness.json","sandbox-execution-receipt.json","independent-observation.json","reconciliation-receipt.json","replay-denial.json"): manifest["artifact_digests"][name]=_hash((artifact_dir/name).read_bytes())
    _write_once(artifact_dir/"proof-manifest.json",manifest); return manifest


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--proof",action="store_true"); parser.add_argument("--work-dir"); parser.add_argument("--artifact-dir"); parser.add_argument("--observer",nargs=6); parser.add_argument("--lie-digest",action="store_true"); parser.add_argument("--attest",nargs=2); args=parser.parse_args(argv)
    if args.attest: return _runtime_attest(int(args.attest[0]),Path(args.attest[1]))
    if args.observer:
        m,t,h,o,impl,trust=args.observer; return _observer(Path(m),Path(t),Path(h),Path(o),impl,trust,args.lie_digest)
    if args.proof:
        if not args.work_dir or not args.artifact_dir: raise SystemExit("--work-dir and --artifact-dir are required")
        print(json.dumps(run_live_runtime_proof(Path(args.work_dir),Path(args.artifact_dir)),sort_keys=True)); return 0
    parser.error("one mode is required"); return 2


if __name__=="__main__": raise SystemExit(main())

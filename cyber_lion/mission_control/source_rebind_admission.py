"""Mission Control source-rebind deployment admission candidate.

Pure contract/reconciliation layer. It cannot restart systemd, mutate K3s, write
release files, or mint deployment authority. The actual effect remains outside
this module and requires separate current authority.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json,re

from cyber_lion.mission_control.source_rebind import RuntimeSourceIdentity, SourceRebindPlan, SourceRebindError

DOMAIN=b"LION/MC/SOURCE-REBIND-DEPLOYMENT-ADMISSION/1\0"
HEX40=re.compile(r"^[0-9a-f]{40}$");HEX64=re.compile(r"^[0-9a-f]{64}$")

class SourceRebindAdmissionError(ValueError):pass

def _text(v,n):
    if type(v) is not str or not v.strip() or "\0" in v:raise SourceRebindAdmissionError(n)
def _sha40(v,n):
    if type(v) is not str or HEX40.fullmatch(v) is None:raise SourceRebindAdmissionError(n)
def _dig(v,n):
    if type(v) is not str or HEX64.fullmatch(v) is None:raise SourceRebindAdmissionError(n)
def _canon(v):return json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False)

@dataclass(frozen=True)
class RollbackSourceIdentity:
    source_head:str;source_tree:str;release_id:str;configuration_digest:str;adapter_set_digest:str;database_schema_digest:str
    def validate(self):
        _sha40(self.source_head,"rollback head");_sha40(self.source_tree,"rollback tree");_text(self.release_id,"rollback release")
        for v,n in ((self.configuration_digest,"rollback config"),(self.adapter_set_digest,"rollback adapters"),(self.database_schema_digest,"rollback schema")):_dig(v,n)
        return self
    def digest(self):return sha256(DOMAIN+_canon(asdict(self)).encode()).hexdigest()

@dataclass(frozen=True)
class PostApplyReadbackContract:
    require_pid:bool=True;require_release_id:bool=True;require_source_head_tree:bool=True;require_health:bool=True;require_api_summary:bool=True;require_vkt_observation:bool=True;require_recorded_observed_active_reconciliation:bool=True
    def validate(self):
        if not all(asdict(self).values()):raise SourceRebindAdmissionError("post-apply readback cannot be weakened")
        return self
    def digest(self):return sha256(DOMAIN+_canon(asdict(self)).encode()).hexdigest()

@dataclass(frozen=True)
class SourceRebindDeploymentAdmissionCandidate:
    admission_id:str;idempotency_key:str;plan_digest:str;package_digest:str;observed_runtime_head:str;observed_runtime_tree:str;target_head:str;target_tree:str;rollback_identity_digest:str;readback_contract_digest:str;admission_digest:str
    effect_class:str="SERVICE_RESTART_AND_SOURCE_REBIND";authority_requirement:str="SEPARATE_CURRENT_DEPLOYMENT_AUTHORITY_REQUIRED";state:str="AUTHORITY_REQUIRED_NOT_EXECUTED";max_attempts:int=1;retry_max_attempts:int=0;replay_policy:str="RECONCILE_FIRST";service_restart_executed:bool=False;k3s_effect:str="NONE";runtime_effect:str="NOT_EXECUTED"
    def validate(self):
        for v,n in ((self.admission_id,"admission id"),(self.idempotency_key,"idempotency key")):_text(v,n)
        for v,n in ((self.plan_digest,"plan digest"),(self.package_digest,"package digest"),(self.rollback_identity_digest,"rollback digest"),(self.readback_contract_digest,"readback digest"),(self.admission_digest,"admission digest")):_dig(v,n)
        for v,n in ((self.observed_runtime_head,"runtime head"),(self.observed_runtime_tree,"runtime tree"),(self.target_head,"target head"),(self.target_tree,"target tree")):_sha40(v,n)
        if self.effect_class!="SERVICE_RESTART_AND_SOURCE_REBIND":raise SourceRebindAdmissionError("effect class")
        if self.authority_requirement!="SEPARATE_CURRENT_DEPLOYMENT_AUTHORITY_REQUIRED" or self.state!="AUTHORITY_REQUIRED_NOT_EXECUTED":raise SourceRebindAdmissionError("authority/state promotion")
        if (self.max_attempts,self.retry_max_attempts,self.replay_policy)!=(1,0,"RECONCILE_FIRST"):raise SourceRebindAdmissionError("non-idempotent retry policy")
        if self.service_restart_executed is not False or self.k3s_effect!="NONE" or self.runtime_effect!="NOT_EXECUTED":raise SourceRebindAdmissionError("effect executed or widened")
        body={k:v for k,v in asdict(self).items() if k!="admission_digest"};expected=sha256(DOMAIN+_canon(body).encode()).hexdigest()
        if self.admission_digest!=expected:raise SourceRebindAdmissionError("admission digest mismatch")
        return self

def prepare_deployment_admission(*,plan,package_digest,current_runtime,rollback,readback,admission_id):
    if type(plan) is not SourceRebindPlan or type(current_runtime) is not RuntimeSourceIdentity or type(rollback) is not RollbackSourceIdentity or type(readback) is not PostApplyReadbackContract:raise SourceRebindAdmissionError("exact admission inputs required")
    try:plan.validate();current_runtime.validate()
    except SourceRebindError as exc:raise SourceRebindAdmissionError("source rebind input invalid") from exc
    rollback.validate();readback.validate();_dig(package_digest,"package digest");_text(admission_id,"admission id")
    if plan.currentness!="SOURCE_CHANGE_REQUIRED":raise SourceRebindAdmissionError("deployment admission requires source change")
    if (current_runtime.source_head,current_runtime.source_tree)!=(plan.current_head,plan.current_tree):raise SourceRebindAdmissionError("runtime source substitution")
    if (rollback.source_head,rollback.source_tree,rollback.release_id)!=(current_runtime.source_head,current_runtime.source_tree,current_runtime.release_id):raise SourceRebindAdmissionError("rollback identity must bind exact observed runtime")
    idem=sha256(DOMAIN+b"IDEMPOTENCY\0"+(plan.plan_digest+package_digest+rollback.digest()).encode()).hexdigest()
    fields=dict(admission_id=admission_id,idempotency_key=idem,plan_digest=plan.plan_digest,package_digest=package_digest,observed_runtime_head=current_runtime.source_head,observed_runtime_tree=current_runtime.source_tree,target_head=plan.target_head,target_tree=plan.target_tree,rollback_identity_digest=rollback.digest(),readback_contract_digest=readback.digest(),effect_class="SERVICE_RESTART_AND_SOURCE_REBIND",authority_requirement="SEPARATE_CURRENT_DEPLOYMENT_AUTHORITY_REQUIRED",state="AUTHORITY_REQUIRED_NOT_EXECUTED",max_attempts=1,retry_max_attempts=0,replay_policy="RECONCILE_FIRST",service_restart_executed=False,k3s_effect="NONE",runtime_effect="NOT_EXECUTED")
    fields['admission_digest']=sha256(DOMAIN+_canon(fields).encode()).hexdigest();return SourceRebindDeploymentAdmissionCandidate(**fields).validate()

def apply_deployment_admission(*args,**kwargs):
    raise SourceRebindAdmissionError("Mission Control deployment apply requires separate current authority and external effect executor")

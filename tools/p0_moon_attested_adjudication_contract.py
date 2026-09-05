from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json,re
from typing import Tuple

_SHA40=re.compile(r"^[0-9a-f]{40}$"); _SHA64=re.compile(r"^[0-9a-f]{64}$")
ADJUDICATION_DOMAIN=b"LION/MOON-RUNNER-ATTESTED-ADJUDICATION/1"
PEP_DOMAIN=b"LION/MOON-CANONICAL-ATTACK-PEP/1"
ATTACK_DEFINITION_DOMAIN=b"LION/MOON-CANONICAL-ATTACK-DEFINITION/1"
POLICY_ENTRY_DOMAIN=b"LION/MEDIATION-ATTACK-REQUIREMENT/1"
POLICY_DOMAIN=b"LION/MEDIATION-ATTACK-REQUIREMENT-POLICY/1"
RECONCILIATION_DOMAIN=b"LION/MOON-OBSERVATION-RECONCILIATION-RULE/1"
VERIFIER_DOMAIN=b"LION/MOON-ATTESTED-ADJUDICATION-VERIFIER/1"
REBINDS_DOMAIN=b"LION/MOON-ADJUDICATION-REVISION-REBIND/1"
PLAN_DOMAIN=b"LION/MOON-ATTESTED-ADJUDICATION-PLAN/1"
class AttestedAdjudicationContractError(ValueError): pass

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v: raise AttestedAdjudicationContractError(f"{n} invalid")
    return v
def _sha40(v,n): _text(v,n); (_ for _ in ()).throw(AttestedAdjudicationContractError(f"{n} must be git sha")) if _SHA40.fullmatch(v) is None else None; return v
def _sha64(v,n): _text(v,n); (_ for _ in ()).throw(AttestedAdjudicationContractError(f"{n} must be sha256")) if _SHA64.fullmatch(v) is None else None; return v
def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v): raise AttestedAdjudicationContractError(f"{n} must be immutable tuple")
    if len(v)!=len(set(v)): raise AttestedAdjudicationContractError(f"{n} must be unique")
    for x in v:_text(x,n)
    return v
def _digest(domain,obj):
    raw=json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode();return sha256(domain+b"\0"+raw).hexdigest()

@dataclass(frozen=True)
class GitHubRunEvidence:
    run_id_numeric:int;event:str;status:str;conclusion:str;head_sha:str;head_tree:str;workflow_path:str;head_branch:str
    def validate(self):
        if type(self.run_id_numeric) is not int or self.run_id_numeric<=0:raise AttestedAdjudicationContractError("run id invalid")
        if (self.event,self.status,self.conclusion)!=("workflow_dispatch","completed","success"):raise AttestedAdjudicationContractError("run terminal binding invalid")
        _sha40(self.head_sha,"head_sha");_sha40(self.head_tree,"head_tree");_text(self.workflow_path,"workflow_path");_text(self.head_branch,"head_branch");return self
@dataclass(frozen=True)
class GitHubJobEvidence:
    job_id_numeric:int;run_id_numeric:int;job_name:str;status:str;conclusion:str;runner_name:str;runner_agent_id:int
    def validate(self):
        if type(self.job_id_numeric) is not int or self.job_id_numeric<=0 or type(self.run_id_numeric) is not int or self.run_id_numeric<=0:raise AttestedAdjudicationContractError("job/run id invalid")
        if (self.job_name,self.status,self.conclusion)!=("execute-operation","completed","success"):raise AttestedAdjudicationContractError("job terminal binding invalid")
        if (self.runner_name,self.runner_agent_id)!=("lion-moon-r9d8-test",24):raise AttestedAdjudicationContractError("job runner binding invalid")
        return self
@dataclass(frozen=True)
class RunnerAttestedAdjudicationRecord:
    run_id_numeric:int;job_id_numeric:int;job_name:str;outer_attestation_digest:str;outer_receipt_digest:str;inner_result_digest:str
    operation:str;result:str;revision:str;tree:str;runner_name:str;runner_agent_id:int;os_user:str;uid:int;hostname:str;machine_id:str
    workflow_ref:str;source_bridge_blob_sha:str;observed_at:str;evidence_refs:Tuple[str,...];adjudication_digest:str=""
    def payload(self):d=asdict(self);d.pop("adjudication_digest");return d
    def validate(self):
        if type(self.run_id_numeric) is not int or self.run_id_numeric<=0 or type(self.job_id_numeric) is not int or self.job_id_numeric<=0:raise AttestedAdjudicationContractError("numeric run/job invalid")
        for n in ("outer_attestation_digest","outer_receipt_digest","inner_result_digest"):_sha64(getattr(self,n),n)
        _sha40(self.revision,"revision");_sha40(self.tree,"tree");_sha40(self.source_bridge_blob_sha,"source_bridge_blob_sha")
        for n in ("job_name","operation","result","runner_name","os_user","hostname","machine_id","workflow_ref","observed_at"):_text(getattr(self,n),n)
        if (self.job_name,self.runner_name,self.runner_agent_id,self.os_user,self.uid,self.hostname,self.machine_id)!=("execute-operation","lion-moon-r9d8-test",24,"lion-maintenance-runner",993,"LION-AUTH-LAB","e69aa593257d47b8885d1bd87710b196"):raise AttestedAdjudicationContractError("execution identity invalid")
        if self.result not in {"OBSERVED","DENIED"}:raise AttestedAdjudicationContractError("result invalid")
        _tuple(self.evidence_refs,"evidence_refs",True)
        expected=sha256(ADJUDICATION_DOMAIN+b"\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode()).hexdigest()
        if self.adjudication_digest and self.adjudication_digest!=expected:raise AttestedAdjudicationContractError("adjudication digest mismatch")
        return self
    def sealed(self):self.validate();p=self.payload();d=sha256(ADJUDICATION_DOMAIN+b"\0"+json.dumps(p,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode()).hexdigest();return RunnerAttestedAdjudicationRecord(**p,adjudication_digest=d).validate()
@dataclass(frozen=True)
class CanonicalAttackPepIdentity:
    pep_name:str;source_path:str;source_blob_sha:str;revision:str;role:str
    def validate(self):
        for n in ("pep_name","source_path","role"):_text(getattr(self,n),n)
        _sha40(self.source_blob_sha,"source_blob_sha");_sha40(self.revision,"revision");return self
    def digest(self):self.validate();return _digest(PEP_DOMAIN,self)
@dataclass(frozen=True)
class CanonicalAttackDefinition:
    attack_id:str;surface_digests:Tuple[str,...];pep_name:str;expected_denial:str;expected_pep_digest:str;execution_class:str;conversion_rule:str;source_refs:Tuple[str,...]
    def validate(self):
        for n in ("attack_id","pep_name","expected_denial","execution_class","conversion_rule"):_text(getattr(self,n),n)
        _tuple(self.surface_digests,"surface_digests",True);_sha64(self.expected_pep_digest,"expected_pep_digest");_tuple(self.source_refs,"source_refs",True)
        for d in self.surface_digests:_sha64(d,"surface_digest")
        return self
    def digest(self):self.validate();return _digest(ATTACK_DEFINITION_DOMAIN,self)
@dataclass(frozen=True)
class MediationAttackRequirement:
    surface_digest:str;attack_ids:Tuple[str,...];attack_scopes:Tuple[str,...];expected_pep_digests:Tuple[str,...];rationale:str;policy_version:str
    def validate(self):
        _sha64(self.surface_digest,"surface_digest");_tuple(self.attack_ids,"attack_ids",True);
        if type(self.attack_scopes) is not tuple or not self.attack_scopes:raise AttestedAdjudicationContractError("attack_scopes must be immutable nonempty tuple")
        for scope in self.attack_scopes:_text(scope,"attack_scope")
        _text(self.rationale,"rationale");_text(self.policy_version,"policy_version")
        if len(self.attack_ids)!=len(self.attack_scopes) or len(self.attack_ids)!=len(self.expected_pep_digests):raise AttestedAdjudicationContractError("policy vectors misaligned")
        for d in self.expected_pep_digests:_sha64(d,"expected_pep_digest")
        if any(x not in {"SURFACE_EXACT","EXPLICIT_SHARED_GUARD","STRUCTURAL_EXACT"} for x in self.attack_scopes):raise AttestedAdjudicationContractError("attack scope invalid")
        return self
    def digest(self):self.validate();return _digest(POLICY_ENTRY_DOMAIN,self)
@dataclass(frozen=True)
class MediationAttackRequirementPolicy:
    inventory_digest:str;revision:str;policy_version:str;requirements:Tuple[MediationAttackRequirement,...];attack_definition_digests:Tuple[str,...];evidence_refs:Tuple[str,...]
    def validate(self):
        _sha64(self.inventory_digest,"inventory_digest");_sha40(self.revision,"revision");_text(self.policy_version,"policy_version");_tuple(self.evidence_refs,"evidence_refs",True)
        if type(self.requirements) is not tuple or len(self.requirements)!=7:raise AttestedAdjudicationContractError("exact seven policy requirements required")
        for r in self.requirements:r.validate()
        if len({r.surface_digest for r in self.requirements})!=7:raise AttestedAdjudicationContractError("duplicate policy surface")
        if not self.attack_definition_digests:raise AttestedAdjudicationContractError("attack definitions required")
        for d in self.attack_definition_digests:_sha64(d,"attack_definition_digest")
        return self
    def digest(self):self.validate();return _digest(POLICY_DOMAIN,self)
@dataclass(frozen=True)
class ObservationReconciliationRule:
    surface_digest:str;rule_version:str;model:str;source_entrypoint:str;adjudication_digest:str;postcondition_digest:str;historical_causality_claimed:bool;evidence_refs:Tuple[str,...]
    def validate(self):
        _sha64(self.surface_digest,"surface_digest");_sha64(self.adjudication_digest,"adjudication_digest");_sha64(self.postcondition_digest,"postcondition_digest")
        for n in ("rule_version","model","source_entrypoint"):_text(getattr(self,n),n)
        if self.historical_causality_claimed:raise AttestedAdjudicationContractError("historical causality cannot be fabricated")
        _tuple(self.evidence_refs,"evidence_refs",True);return self
    def digest(self):self.validate();return _digest(RECONCILIATION_DOMAIN,self)
@dataclass(frozen=True)
class AttestedVerifierIdentity:
    adjudication_digest:str;run_id_numeric:int;job_id_numeric:int;runner_name:str;runner_agent_id:int;source_bridge_blob_sha:str;role:str
    def validate(self):
        _sha64(self.adjudication_digest,"adjudication_digest");_sha40(self.source_bridge_blob_sha,"source_bridge_blob_sha");_text(self.runner_name,"runner_name");_text(self.role,"role")
        if self.run_id_numeric<=0 or self.job_id_numeric<=0 or (self.runner_name,self.runner_agent_id)!=("lion-moon-r9d8-test",24):raise AttestedAdjudicationContractError("verifier identity invalid")
        return self
    def digest(self):self.validate();return _digest(VERIFIER_DOMAIN,self)
@dataclass(frozen=True)
class RevisionRebindProof:
    source_revision:str;source_tree:str;source_inventory_digest:str;target_revision:str;target_tree:str;target_inventory_digest:str;scan_digest:str;unchanged_source_blobs:Tuple[str,...];evidence_refs:Tuple[str,...]
    def validate(self):
        for n in ("source_revision","source_tree","target_revision","target_tree"):_sha40(getattr(self,n),n)
        for n in ("source_inventory_digest","target_inventory_digest","scan_digest"):_sha64(getattr(self,n),n)
        _tuple(self.unchanged_source_blobs,"unchanged_source_blobs",True);_tuple(self.evidence_refs,"evidence_refs",True)
        for x in self.unchanged_source_blobs:
            p,s=x.rsplit("@",1);_text(p,"source_path");_sha40(s,"source_blob")
        return self
    def digest(self):self.validate();return _digest(REBINDS_DOMAIN,self)
@dataclass(frozen=True)
class AttestedAdjudicationPlan:
    target_inventory_digest:str;record_digests:Tuple[str,...];policy_digest:str;rebind_digest:str;observer_promotion_digests:Tuple[str,...];resolved_binding_count:int;resolved_chain_count:int;converted_bypass_result_digests:Tuple[str,...];evidence_only_operations:Tuple[str,...];global_status:str;evidence_refs:Tuple[str,...]
    def validate(self):
        _sha64(self.target_inventory_digest,"target_inventory_digest");_sha64(self.policy_digest,"policy_digest");_sha64(self.rebind_digest,"rebind_digest")
        if len(self.record_digests)!=7:raise AttestedAdjudicationContractError("seven adjudication records required")
        for d in self.record_digests+self.observer_promotion_digests+self.converted_bypass_result_digests:_sha64(d,"digest")
        if self.resolved_binding_count!=7 or self.resolved_chain_count!=7:raise AttestedAdjudicationContractError("seven bindings/chains required")
        _tuple(self.evidence_only_operations,"evidence_only_operations");_tuple(self.evidence_refs,"evidence_refs",True)
        if self.global_status!="UNKNOWN":raise AttestedAdjudicationContractError("global status must remain UNKNOWN")
        return self
    def digest(self):self.validate();return _digest(PLAN_DOMAIN,self)

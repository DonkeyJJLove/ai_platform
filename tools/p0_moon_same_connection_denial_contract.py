from __future__ import annotations
from dataclasses import asdict,dataclass
from hashlib import sha256
import json,re
from typing import Tuple

_SHA40=re.compile(r"^[0-9a-f]{40}$")
_SHA64=re.compile(r"^[0-9a-f]{64}$")
RUNNER="lion-moon-r9d8-test"
AGENT=24
HOST="LION-AUTH-LAB"
MACHINE="e69aa593257d47b8885d1bd87710b196"
CONTROL_ISSUE=144
CREATE_TABLE_SURFACE="478e559a2f8762b471ec9d69eca2bf03ed2744ab0e4f34593ab5060ae95cad9d"
PRAGMA_SURFACE="e631906532cb4c60aa69736270432263cb1d5346afde33cbb01fecec6c793de0"
ATTACK_IDS=("WRONG_EXPECTED_STATE","REPLAYED_EFFECT_KEY","REPOSITORY_SUBSTITUTION","ACTOR_SUBSTITUTION","CONTROL_ISSUE_SUBSTITUTION")

class MoonSameConnectionContractError(ValueError):pass

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise MoonSameConnectionContractError(f"{n} invalid")
    return v

def _sha40(v,n):
    _text(v,n)
    if not _SHA40.fullmatch(v):raise MoonSameConnectionContractError(f"{n} must be git sha")
    return v

def _sha64(v,n):
    _text(v,n)
    if not _SHA64.fullmatch(v):raise MoonSameConnectionContractError(f"{n} must be sha256")
    return v

def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise MoonSameConnectionContractError(f"{n} must be immutable tuple")
    if len(v)!=len(set(v)):raise MoonSameConnectionContractError(f"{n} must be unique")
    for x in v:_text(x,n)
    return v

def _digest(domain,obj):
    raw=json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode()
    return sha256(domain+b"\0"+raw).hexdigest()

@dataclass(frozen=True)
class MoonCarrierExecutionIdentity:
    revision:str;tree:str;runner_name:str;runner_agent_id:int;execution_host:str;machine_id:str;control_issue:int
    def validate(self):
        _sha40(self.revision,"revision");_sha40(self.tree,"tree")
        if (self.runner_name,self.runner_agent_id,self.execution_host,self.machine_id,self.control_issue)!=(RUNNER,AGENT,HOST,MACHINE,CONTROL_ISSUE):raise MoonSameConnectionContractError("execution identity mismatch")
        return self
    def digest(self):self.validate();return _digest(b"LION/MOON-DENIAL-EXECUTION-IDENTITY/1",self)

@dataclass(frozen=True)
class MoonObservationReceipt:
    receipt_kind:str;revision:str;tree:str;runner_name:str;runner_agent_id:int;execution_host:str;machine_id:str
    database_path:str;database_device:int;database_inode:int;surface_digest:str;entrypoint:str;journal_mode:str;synchronous:int
    schema_digest:str;row_state_digest:str;same_connection:bool;observed_at:str;receipt_digest:str=""
    def payload(self):
        d=asdict(self);d.pop("receipt_digest");return d
    def validate(self):
        if self.receipt_kind not in {"SCHEMA_OBSERVATION","SAME_CONNECTION_PRAGMA"}:raise MoonSameConnectionContractError("receipt kind invalid")
        _sha40(self.revision,"revision");_sha40(self.tree,"tree")
        if (self.runner_name,self.runner_agent_id,self.execution_host,self.machine_id)!=(RUNNER,AGENT,HOST,MACHINE):raise MoonSameConnectionContractError("receipt execution identity mismatch")
        _text(self.database_path,"database_path");_text(self.entrypoint,"entrypoint");_text(self.observed_at,"observed_at")
        if type(self.database_device) is not int or type(self.database_inode) is not int:raise MoonSameConnectionContractError("database identity invalid")
        _sha64(self.surface_digest,"surface_digest");_sha64(self.schema_digest,"schema_digest");_sha64(self.row_state_digest,"row_state_digest")
        if self.journal_mode!="wal" or self.synchronous!=2:raise MoonSameConnectionContractError("pragma readback mismatch")
        if self.receipt_kind=="SCHEMA_OBSERVATION" and (self.surface_digest!=CREATE_TABLE_SURFACE or self.same_connection):raise MoonSameConnectionContractError("schema receipt binding invalid")
        if self.receipt_kind=="SAME_CONNECTION_PRAGMA" and (self.surface_digest!=PRAGMA_SURFACE or not self.same_connection):raise MoonSameConnectionContractError("pragma receipt binding invalid")
        expected=sha256(b"LION/MOON-OBSERVATION-RECEIPT/1\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        if self.receipt_digest and self.receipt_digest!=expected:raise MoonSameConnectionContractError("observation receipt digest mismatch")
        return self
    def sealed(self):
        self.validate();p=self.payload();d=sha256(b"LION/MOON-OBSERVATION-RECEIPT/1\0"+json.dumps(p,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest();return MoonObservationReceipt(**p,receipt_digest=d).validate()

@dataclass(frozen=True)
class MoonDenialReceipt:
    revision:str;tree:str;runner_name:str;runner_agent_id:int;execution_host:str;machine_id:str;attack_id:str;pep:str;denial:str
    canary_pre_sha256:str;canary_post_sha256:str;fence_pre_digest:str;fence_post_digest:str;effect_boundary_reached:bool
    valid_fence_transition:bool;observed_at:str;receipt_digest:str=""
    def payload(self):d=asdict(self);d.pop("receipt_digest");return d
    def validate(self):
        _sha40(self.revision,"revision");_sha40(self.tree,"tree")
        if (self.runner_name,self.runner_agent_id,self.execution_host,self.machine_id)!=(RUNNER,AGENT,HOST,MACHINE):raise MoonSameConnectionContractError("denial execution identity mismatch")
        if self.attack_id not in ATTACK_IDS:raise MoonSameConnectionContractError("attack id invalid")
        for n in ("pep","denial","observed_at"):_text(getattr(self,n),n)
        for n in ("canary_pre_sha256","canary_post_sha256","fence_pre_digest","fence_post_digest"):_sha64(getattr(self,n),n)
        if self.canary_pre_sha256!=self.canary_post_sha256 or self.fence_pre_digest!=self.fence_post_digest:raise MoonSameConnectionContractError("denial changed bounded state")
        if self.effect_boundary_reached or self.valid_fence_transition:raise MoonSameConnectionContractError("denial crossed effect boundary")
        expected=sha256(b"LION/MOON-DENIAL-OBSERVATION-RECEIPT/1\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        if self.receipt_digest and self.receipt_digest!=expected:raise MoonSameConnectionContractError("denial receipt digest mismatch")
        return self
    def sealed(self):
        self.validate();p=self.payload();d=sha256(b"LION/MOON-DENIAL-OBSERVATION-RECEIPT/1\0"+json.dumps(p,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest();return MoonDenialReceipt(**p,receipt_digest=d).validate()

@dataclass(frozen=True)
class MoonDenialAttackPlan:
    attack_id:str;surface_digests:Tuple[str,...];pep:str;expected_denial:str;input_variant:str;denial_before_effect:bool
    canary_hash_capture:bool;fence_state_capture:bool;pre_post_equality_required:bool;valid_transition_allowed:bool;state:str
    def validate(self):
        if self.attack_id not in ATTACK_IDS:raise MoonSameConnectionContractError("attack id invalid")
        if type(self.surface_digests) is not tuple or not self.surface_digests:raise MoonSameConnectionContractError("surface digests required")
        for x in self.surface_digests:_sha64(x,"surface_digest")
        for n in ("pep","expected_denial","input_variant"):_text(getattr(self,n),n)
        if not self.denial_before_effect or not self.canary_hash_capture or not self.fence_state_capture or not self.pre_post_equality_required or self.valid_transition_allowed:raise MoonSameConnectionContractError("attack safety invariant invalid")
        if self.state!="CANDIDATE_UNEXECUTED":raise MoonSameConnectionContractError("attack state invalid")
        return self
    def digest(self):self.validate();return _digest(b"LION/MOON-FIVE-DENIAL-ATTACK-PLAN/1",self)

@dataclass(frozen=True)
class MoonObservationExecutionCarrierSpec:
    parent_revision:str;runner_name:str;runner_agent_id:int;execution_host:str;machine_id:str;control_issue:int;database_path:str
    create_table_surface:str;pragma_surface:str;schema_receipt_required:bool;same_connection_receipt_required:bool;live_execution:bool;state:str
    def validate(self):
        _sha40(self.parent_revision,"parent_revision");_text(self.database_path,"database_path")
        if (self.runner_name,self.runner_agent_id,self.execution_host,self.machine_id,self.control_issue)!=(RUNNER,AGENT,HOST,MACHINE,CONTROL_ISSUE):raise MoonSameConnectionContractError("observation carrier binding invalid")
        if self.create_table_surface!=CREATE_TABLE_SURFACE or self.pragma_surface!=PRAGMA_SURFACE:raise MoonSameConnectionContractError("observation surfaces invalid")
        if not self.schema_receipt_required or not self.same_connection_receipt_required or self.live_execution or self.state!="CANDIDATE_UNATTACHED":raise MoonSameConnectionContractError("observation carrier state invalid")
        return self
    def digest(self):self.validate();return _digest(b"LION/MOON-OBSERVATION-EXECUTION-CARRIER/1",self)

@dataclass(frozen=True)
class MoonDenialExecutionCarrierSpec:
    parent_revision:str;runner_name:str;runner_agent_id:int;execution_host:str;machine_id:str;control_issue:int;target_path:str;fence_path:str
    attack_ids:Tuple[str,...];attack_digests:Tuple[str,...];generic_shell:bool;arbitrary_command:bool;arbitrary_path:bool;direct_database_write:bool
    live_execution:bool;state:str
    def validate(self):
        _sha40(self.parent_revision,"parent_revision");_text(self.target_path,"target_path");_text(self.fence_path,"fence_path")
        if (self.runner_name,self.runner_agent_id,self.execution_host,self.machine_id,self.control_issue)!=(RUNNER,AGENT,HOST,MACHINE,CONTROL_ISSUE):raise MoonSameConnectionContractError("denial carrier binding invalid")
        if self.attack_ids!=ATTACK_IDS or len(self.attack_digests)!=5:raise MoonSameConnectionContractError("exact five attacks required")
        for x in self.attack_digests:_sha64(x,"attack_digest")
        if self.generic_shell or self.arbitrary_command or self.arbitrary_path or self.direct_database_write or self.live_execution or self.state!="CANDIDATE_UNATTACHED":raise MoonSameConnectionContractError("denial carrier state invalid")
        return self
    def digest(self):self.validate();return _digest(b"LION/MOON-DENIAL-EXECUTION-CARRIER/1",self)

@dataclass(frozen=True)
class MoonSameConnectionCandidatePlan:
    inventory_digest:str;scan_digest:str;observation_carrier_digest:str;denial_carrier_digest:str;attack_plan_digests:Tuple[str,...]
    observation_receipt_count:int;denial_receipt_count:int;bypass_result_count:int;live_execution:bool;global_status:str;evidence_refs:Tuple[str,...]
    def validate(self):
        for n in ("inventory_digest","scan_digest","observation_carrier_digest","denial_carrier_digest"):_sha64(getattr(self,n),n)
        if len(self.attack_plan_digests)!=5:raise MoonSameConnectionContractError("five attack plan digests required")
        for x in self.attack_plan_digests:_sha64(x,"attack_plan_digest")
        if (self.observation_receipt_count,self.denial_receipt_count,self.bypass_result_count)!=(0,0,0) or self.live_execution or self.global_status!="UNKNOWN":raise MoonSameConnectionContractError("candidate cannot contain live evidence or promotion")
        _tuple(self.evidence_refs,"evidence_refs",True);return self
    def digest(self):self.validate();return _digest(b"LION/MOON-SAME-CONNECTION-DENIAL-CANDIDATE-PLAN/1",self)

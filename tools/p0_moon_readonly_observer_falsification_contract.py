from __future__ import annotations
from dataclasses import asdict,dataclass
from hashlib import sha256
import json,re
from typing import Tuple

_SHA40=re.compile(r"^[0-9a-f]{40}$")
_SHA64=re.compile(r"^[0-9a-f]{64}$")
ATTACK_IDS=("WRONG_EXPECTED_STATE","REPLAYED_EFFECT_KEY","REPOSITORY_SUBSTITUTION","ACTOR_SUBSTITUTION","CONTROL_ISSUE_SUBSTITUTION")
DOMAINS={
    "readback":b"LION/MOON-FENCE-READONLY-READBACK/1",
    "observer_spec":b"LION/MOON-FENCE-READONLY-OBSERVER-SPEC/1",
    "observer_receipt":b"LION/MOON-FENCE-READONLY-OBSERVER-RECEIPT/1",
    "attack_plan":b"LION/MOON-BOUNDED-FALSIFICATION-ATTACK-PLAN/1",
    "runtime_spec":b"LION/MOON-BOUNDED-FALSIFICATION-RUNTIME-SPEC/1",
    "candidate_plan":b"LION/MOON-READONLY-OBSERVER-FALSIFICATION-CANDIDATE/1",
}
class MoonRuntimeCandidateContractError(ValueError):pass

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise MoonRuntimeCandidateContractError(f"{n} invalid")
    return v

def _sha(v,n):
    _text(v,n)
    if not _SHA64.fullmatch(v):raise MoonRuntimeCandidateContractError(f"{n} must be sha256")
    return v

def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise MoonRuntimeCandidateContractError(f"{n} must be immutable tuple")
    if len(set(v))!=len(v):raise MoonRuntimeCandidateContractError(f"{n} must be unique")
    for x in v:_text(x,n)
    return v

def _digest(domain,obj):
    raw=json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode()
    return sha256(domain+b"\0"+raw).hexdigest()

@dataclass(frozen=True)
class MoonFenceReadback:
    database_path:str
    database_device:int
    database_inode:int
    query_only:bool
    table_name:str
    columns:Tuple[str,...]
    primary_key_columns:Tuple[str,...]
    unique_columns:Tuple[str,...]
    journal_mode:str
    synchronous:int
    schema_digest:str
    pragma_digest:str
    schema_exact:bool
    journal_mode_exact:bool
    synchronous_value_exact:bool
    synchronous_historical_proof:bool
    def validate(self):
        _text(self.database_path,"database_path");_text(self.table_name,"table_name")
        if type(self.database_device) is not int or self.database_device<0 or type(self.database_inode) is not int or self.database_inode<=0:raise MoonRuntimeCandidateContractError("database identity invalid")
        if self.query_only is not True:raise MoonRuntimeCandidateContractError("query_only required")
        for n in ("columns","primary_key_columns","unique_columns"):_tuple(getattr(self,n),n,True)
        _text(self.journal_mode,"journal_mode")
        if type(self.synchronous) is not int:raise MoonRuntimeCandidateContractError("synchronous invalid")
        _sha(self.schema_digest,"schema_digest");_sha(self.pragma_digest,"pragma_digest")
        if self.synchronous_historical_proof:raise MoonRuntimeCandidateContractError("detached observer cannot prove historical synchronous setter")
        return self
    def digest(self):self.validate();return _digest(DOMAINS["readback"],self)

@dataclass(frozen=True)
class MoonReadOnlyObserverSpec:
    parent_revision:str
    database_path:str
    observer_identity:str
    mode_ro:bool
    query_only_required:bool
    schema_readback:bool
    journal_mode_readback:bool
    synchronous_readback:bool
    same_connection_synchronous_probe_required:bool
    arbitrary_path:bool
    write_transaction:bool
    schema_mutation:bool
    persistent_pragma_mutation:bool
    live_execution:bool
    state:str
    def validate(self):
        if not _SHA40.fullmatch(self.parent_revision):raise MoonRuntimeCandidateContractError("parent revision invalid")
        for n in ("database_path","observer_identity"):_text(getattr(self,n),n)
        if not self.mode_ro or not self.query_only_required or not self.schema_readback or not self.journal_mode_readback or not self.synchronous_readback or not self.same_connection_synchronous_probe_required:raise MoonRuntimeCandidateContractError("observer read-only capabilities incomplete")
        if self.arbitrary_path or self.write_transaction or self.schema_mutation or self.persistent_pragma_mutation or self.live_execution:raise MoonRuntimeCandidateContractError("observer boundary unsafe")
        if self.state!="CANDIDATE_UNATTACHED":raise MoonRuntimeCandidateContractError("observer state invalid")
        return self
    def digest(self):self.validate();return _digest(DOMAINS["observer_spec"],self)

@dataclass(frozen=True)
class MoonFenceObservationReceipt:
    revision:str
    tree:str
    database_path:str
    database_identity:str
    query_only:bool
    schema_digest:str
    pragma_digest:str
    observer_identity:str
    observed_at:str
    readback_digest:str
    receipt_digest:str=""
    def payload(self):
        value=asdict(self);value.pop("receipt_digest");return value
    def validate(self):
        if not _SHA40.fullmatch(self.revision) or not _SHA40.fullmatch(self.tree):raise MoonRuntimeCandidateContractError("receipt revision/tree invalid")
        for n in ("database_path","database_identity","observer_identity","observed_at"):_text(getattr(self,n),n)
        if self.query_only is not True:raise MoonRuntimeCandidateContractError("receipt query_only required")
        for n in ("schema_digest","pragma_digest","readback_digest"):_sha(getattr(self,n),n)
        expected=sha256(DOMAINS["observer_receipt"]+b"\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        if self.receipt_digest and self.receipt_digest!=expected:raise MoonRuntimeCandidateContractError("receipt digest mismatch")
        return self
    def sealed(self):
        self.validate();payload=self.payload();d=sha256(DOMAINS["observer_receipt"]+b"\0"+json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest();return MoonFenceObservationReceipt(**payload,receipt_digest=d).validate()

@dataclass(frozen=True)
class MoonFutureAttackPlan:
    attack_id:str
    surface_digests:Tuple[str,...]
    expected_pep:str
    expected_denial:str
    denial_before_effect_boundary:bool
    canary_unchanged_by_construction:bool
    valid_fence_state_transition_reached:bool
    target_path:str
    fence_path:str
    observation_receipt_required:bool
    live_execution:bool
    state:str
    evidence_refs:Tuple[str,...]
    def validate(self):
        if self.attack_id not in ATTACK_IDS:raise MoonRuntimeCandidateContractError("attack id not allowed")
        _tuple(self.surface_digests,"surface_digests",True)
        for x in self.surface_digests:_sha(x,"surface_digest")
        for n in ("expected_pep","expected_denial","target_path","fence_path"):_text(getattr(self,n),n)
        if not self.denial_before_effect_boundary or not self.canary_unchanged_by_construction or self.valid_fence_state_transition_reached or not self.observation_receipt_required or self.live_execution:raise MoonRuntimeCandidateContractError("attack plan is not bounded pre-effect denial")
        if self.state!="CANDIDATE_UNEXECUTED":raise MoonRuntimeCandidateContractError("attack state invalid")
        _tuple(self.evidence_refs,"evidence_refs",True);return self
    def digest(self):self.validate();return _digest(DOMAINS["attack_plan"],self)

@dataclass(frozen=True)
class MoonBoundedFalsificationRuntimeSpec:
    parent_revision:str
    control_issue:int
    runner_agent_id:int
    execution_host:str
    target_path:str
    fence_path:str
    allowed_attack_ids:Tuple[str,...]
    attack_plan_digests:Tuple[str,...]
    generic_shell:bool
    subprocess_enabled:bool
    eval_enabled:bool
    exec_enabled:bool
    arbitrary_import:bool
    arbitrary_path:bool
    arbitrary_command:bool
    direct_database_write:bool
    live_execution:bool
    state:str
    def validate(self):
        if not _SHA40.fullmatch(self.parent_revision):raise MoonRuntimeCandidateContractError("runtime parent invalid")
        for n in ("execution_host","target_path","fence_path"):_text(getattr(self,n),n)
        if self.control_issue!=144 or self.runner_agent_id!=24:raise MoonRuntimeCandidateContractError("runtime authority binding invalid")
        if self.allowed_attack_ids!=ATTACK_IDS:raise MoonRuntimeCandidateContractError("exact five attacks required")
        if type(self.attack_plan_digests) is not tuple or len(self.attack_plan_digests)!=5:raise MoonRuntimeCandidateContractError("five attack plans required")
        for x in self.attack_plan_digests:_sha(x,"attack_plan_digest")
        if any((self.generic_shell,self.subprocess_enabled,self.eval_enabled,self.exec_enabled,self.arbitrary_import,self.arbitrary_path,self.arbitrary_command,self.direct_database_write,self.live_execution)):raise MoonRuntimeCandidateContractError("runtime must remain inert/bounded")
        if self.state!="CANDIDATE_UNATTACHED":raise MoonRuntimeCandidateContractError("runtime state invalid")
        return self
    def digest(self):self.validate();return _digest(DOMAINS["runtime_spec"],self)

@dataclass(frozen=True)
class MoonObserverRuntimeCandidatePlan:
    inventory_digest:str
    scan_digest:str
    observer_spec_digest:str
    runtime_spec_digest:str
    blocked_surface_digests:Tuple[str,...]
    attack_plan_digests:Tuple[str,...]
    observer_receipt_count:int
    bypass_result_count:int
    live_observation_executed:bool
    live_falsification_executed:bool
    global_status:str
    evidence_refs:Tuple[str,...]
    def validate(self):
        for n in ("inventory_digest","scan_digest","observer_spec_digest","runtime_spec_digest"):_sha(getattr(self,n),n)
        if type(self.blocked_surface_digests) is not tuple or len(self.blocked_surface_digests)!=2:raise MoonRuntimeCandidateContractError("exact two blocked surfaces required")
        for x in self.blocked_surface_digests:_sha(x,"blocked_surface_digest")
        if type(self.attack_plan_digests) is not tuple or len(self.attack_plan_digests)!=5:raise MoonRuntimeCandidateContractError("exact five attack plans required")
        for x in self.attack_plan_digests:_sha(x,"attack_plan_digest")
        if self.observer_receipt_count!=0 or self.bypass_result_count!=0 or self.live_observation_executed or self.live_falsification_executed or self.global_status!="UNKNOWN":raise MoonRuntimeCandidateContractError("candidate cannot synthesize live evidence/global promotion")
        _tuple(self.evidence_refs,"evidence_refs",True);return self
    def digest(self):self.validate();return _digest(DOMAINS["candidate_plan"],self)

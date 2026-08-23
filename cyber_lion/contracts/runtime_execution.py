"""Immutable contracts for F009 admission-bound runtime execution.

These records bind one verified RuntimeAdmission to one exact bounded sandbox operation
and one observed execution receipt. They do not mint authority or execute effects.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping

SCHEMA_VERSION="1.0.0"
_SHA256=re.compile(r"^[0-9a-f]{64}$")
_ACTIONS={"READ_FILE","WRITE_FILE","RUN_TEST"}
_OUTCOMES={"SUCCEEDED","FAILED","ABORTED"}
_EFFECT_STATES={"OBSERVED","UNKNOWN","PARTIAL_UNKNOWN"}

class RuntimeExecutionContractError(ValueError):pass

def canonical_json(value:Mapping[str,Any])->bytes:
    return json.dumps(dict(value),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def _text(value:Any,name:str,limit:int=2048)->str:
    if not isinstance(value,str) or not value.strip() or len(value)>limit or "\x00" in value:raise RuntimeExecutionContractError(f"{name} invalid")
    return value

def _digest(value:Any,name:str)->str:
    value=_text(value,name,64)
    if not _SHA256.fullmatch(value):raise RuntimeExecutionContractError(f"{name} must be sha256 hex")
    return value

def _positive(value:Any,name:str,*,allow_zero:bool=False)->int:
    if isinstance(value,bool) or not isinstance(value,int) or value<(0 if allow_zero else 1):raise RuntimeExecutionContractError(f"{name} invalid")
    return value

def _command(value:Any)->tuple[str,...]:
    if type(value) is not tuple or not value:raise RuntimeExecutionContractError("command invalid")
    for token in value:
        _text(token,"command token")
        if "\n" in token or "\r" in token:raise RuntimeExecutionContractError("command token invalid")
    return value

@dataclass(frozen=True)
class RuntimeAdmissionSourceTrustBinding:
    source_id:str
    source_instance_id:str
    source_implementation_digest:str
    trust_anchor_id:str
    trust_anchor_digest:str
    schema_version:str=SCHEMA_VERSION
    def validate(self):
        if self.schema_version!=SCHEMA_VERSION:raise RuntimeExecutionContractError("unsupported admission source trust schema")
        for n in ("source_id","source_instance_id","trust_anchor_id"):_text(getattr(self,n),n)
        _digest(self.source_implementation_digest,"source_implementation_digest");_digest(self.trust_anchor_digest,"trust_anchor_digest")
        return self
    def binding(self):
        self.validate();return (self.source_id,self.source_instance_id,self.source_implementation_digest,self.trust_anchor_id,self.trust_anchor_digest)

@dataclass(frozen=True)
class RuntimeExecutionRequest:
    execution_id:str
    admission_digest:str
    requested_effect_digest:str
    runtime_identity_digest:str
    provisioned_executor_digest:str
    mission_id:str
    executor_id:str
    runtime_instance_id:str
    sandbox_id:str
    workspace_id:str
    dispatch_id:str
    fencing_token:str
    generation:int
    action:str
    resource:str
    payload_digest:str
    payload_size:int
    command:tuple[str,...]=()
    schema_version:str=SCHEMA_VERSION
    def validate(self):
        if self.schema_version!=SCHEMA_VERSION:raise RuntimeExecutionContractError("unsupported execution request schema")
        for n in ("execution_id","mission_id","executor_id","runtime_instance_id","sandbox_id","workspace_id","resource"):_text(getattr(self,n),n)
        for n in ("admission_digest","requested_effect_digest","runtime_identity_digest","provisioned_executor_digest","dispatch_id","fencing_token","payload_digest"):_digest(getattr(self,n),n)
        _positive(self.generation,"generation")
        if self.action not in _ACTIONS:raise RuntimeExecutionContractError("action invalid")
        _positive(self.payload_size,"payload_size",allow_zero=True)
        if self.action=="WRITE_FILE":
            if self.payload_size<1 or self.command:raise RuntimeExecutionContractError("WRITE_FILE payload/command invalid")
        elif self.action=="RUN_TEST":
            if self.payload_size!=0:raise RuntimeExecutionContractError("RUN_TEST payload_size must be zero")
            _command(self.command)
        elif self.payload_size!=0 or self.command:raise RuntimeExecutionContractError("READ_FILE cannot carry payload or command")
        return self
    def canonical_dict(self):
        self.validate();d=asdict(self);d["command"]=list(self.command);return d
    def digest(self):return sha256(b"LION/F009-RUNTIME-EXECUTION-REQUEST/1\0"+canonical_json(self.canonical_dict())).hexdigest()

@dataclass(frozen=True)
class RuntimeExecutionReceipt:
    receipt_id:str
    execution_id:str
    admission_digest:str
    request_digest:str
    sandbox_receipt_digest:str
    operation_digest:str
    mission_id:str
    executor_id:str
    runtime_instance_id:str
    sandbox_id:str
    workspace_id:str
    dispatch_id:str
    fencing_token:str
    generation:int
    action:str
    resource:str
    payload_digest:str
    outcome:str
    effect_state:str
    effect_digest:str
    observed_events:tuple[str,...]
    side_effect_refs:tuple[str,...]
    receipt_digest:str=""
    schema_version:str=SCHEMA_VERSION
    def canonical_dict(self,*,include_digest:bool=True):
        self.validate(check_digest=False);d=asdict(self);d["observed_events"]=list(self.observed_events);d["side_effect_refs"]=list(self.side_effect_refs)
        if not include_digest:d.pop("receipt_digest")
        return d
    def compute_digest(self):return sha256(b"LION/F009-RUNTIME-EXECUTION-RECEIPT/1\0"+canonical_json(self.canonical_dict(include_digest=False))).hexdigest()
    def validate(self,*,check_digest:bool=True):
        if self.schema_version!=SCHEMA_VERSION:raise RuntimeExecutionContractError("unsupported execution receipt schema")
        for n in ("receipt_id","execution_id","mission_id","executor_id","runtime_instance_id","sandbox_id","workspace_id","resource"):_text(getattr(self,n),n)
        for n in ("admission_digest","request_digest","sandbox_receipt_digest","operation_digest","dispatch_id","fencing_token","payload_digest","effect_digest"):_digest(getattr(self,n),n)
        _positive(self.generation,"generation")
        if self.action not in _ACTIONS or self.outcome not in _OUTCOMES or self.effect_state not in _EFFECT_STATES:raise RuntimeExecutionContractError("receipt classification invalid")
        if type(self.observed_events) is not tuple or not self.observed_events or len(set(self.observed_events))!=len(self.observed_events):raise RuntimeExecutionContractError("observed_events invalid")
        if type(self.side_effect_refs) is not tuple or len(set(self.side_effect_refs))!=len(self.side_effect_refs):raise RuntimeExecutionContractError("side_effect_refs invalid")
        if self.outcome=="SUCCEEDED" and self.effect_state!="OBSERVED":raise RuntimeExecutionContractError("success requires observed effect")
        if self.effect_state in {"UNKNOWN","PARTIAL_UNKNOWN"} and self.outcome=="SUCCEEDED":raise RuntimeExecutionContractError("unknown effect cannot succeed")
        if self.effect_state=="PARTIAL_UNKNOWN" and not self.side_effect_refs:raise RuntimeExecutionContractError("partial unknown effect requires side-effect evidence")
        if self.action=="WRITE_FILE" and self.outcome=="SUCCEEDED" and not self.side_effect_refs:raise RuntimeExecutionContractError("successful write requires side-effect reference")
        if check_digest:
            _digest(self.receipt_digest,"receipt_digest")
            if self.receipt_digest!=self.compute_digest():raise RuntimeExecutionContractError("receipt_digest mismatch")
        return self
    def sealed(self):
        self.validate(check_digest=False);return RuntimeExecutionReceipt(**{**asdict(self),"receipt_digest":self.compute_digest()}).validate()

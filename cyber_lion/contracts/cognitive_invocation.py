"""Canonical non-effectful cognitive invocation contracts for LION v1.5."""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json, re
from typing import Any, Tuple
AUTHORITY_EFFECT="NONE"
PROVIDER_CLASSES=frozenset({"LOCAL","SAAS"})
COGNITIVE_CLASSES=frozenset({"COORDINATION","PLANNING","VERIFICATION","EXPLANATION"})
INVOCATION_STATES=frozenset({"PREPARED","READY","SUBMITTED","OUTCOME_UNKNOWN","RESULT_ACCEPTED","DELIVERED","RECONCILED","CANCELLED","SUPERSEDED","EXPIRED"})
CURRENTNESS_STATES=frozenset({"CURRENT","STALE","UNKNOWN","NOT_APPLICABLE"})
_SAFE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$");_HEX=re.compile(r"^[0-9a-f]{64}$")
class CognitiveInvocationError(ValueError): pass
def _j(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _digest(domain,payload): return sha256(domain+_j(payload)).hexdigest()
def _txt(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v: raise CognitiveInvocationError(n)
    return v
def _id(v,n):
    _txt(v,n)
    if not _SAFE.fullmatch(v): raise CognitiveInvocationError(n)
    return v
def _hex(v,n):
    if not isinstance(v,str) or not _HEX.fullmatch(v): raise CognitiveInvocationError(n)
    return v
@dataclass(frozen=True)
class CognitiveProvider:
    provider_id:str;provider_class:str;profile_ref:str;authority_effect:str="NONE"
    def validate(self):
        _id(self.provider_id,"provider_id");_txt(self.profile_ref,"profile_ref")
        if self.provider_class not in PROVIDER_CLASSES or self.authority_effect!="NONE": raise CognitiveInvocationError("provider")
        return self
@dataclass(frozen=True)
class CognitiveEndpoint:
    endpoint_id:str;provider_ref:str;provider_class:str;transport_profile_ref:str;identity_evidence_class:str;model_identity_ref:str|None;authority_effect:str="NONE"
    def validate(self):
        _id(self.endpoint_id,"endpoint_id");_id(self.provider_ref,"provider_ref");_txt(self.transport_profile_ref,"transport_profile_ref");_txt(self.identity_evidence_class,"identity_evidence_class")
        if self.provider_class not in PROVIDER_CLASSES or self.authority_effect!="NONE": raise CognitiveInvocationError("endpoint")
        if self.model_identity_ref is not None:_txt(self.model_identity_ref,"model_identity_ref")
        return self
@dataclass(frozen=True)
class CognitiveSessionBinding:
    binding_id:str;scope_type:str;mission_id:str|None;thread_id:str;endpoint_ref:str;session_ref:str;binding_epoch:int;model_release_ref:str;input_context_digest:str;issued_at:str;expires_at:str;binding_digest:str="";authority_effect:str="NONE"
    def payload(self): d=asdict(self);d.pop("binding_digest",None);return d
    def compute_digest(self): return _digest(b"LION/COGNITIVE-SESSION-BINDING/1\0",self.payload())
    def validate(self,require_digest=True):
        _id(self.binding_id,"binding_id");_id(self.thread_id,"thread_id");_id(self.endpoint_ref,"endpoint_ref");_txt(self.session_ref,"session_ref");_txt(self.model_release_ref,"model_release_ref");_hex(self.input_context_digest,"input_context_digest");_txt(self.issued_at,"issued_at");_txt(self.expires_at,"expires_at")
        if self.scope_type not in {"MISSION","THREAD"} or isinstance(self.binding_epoch,bool) or self.binding_epoch<1 or self.authority_effect!="NONE": raise CognitiveInvocationError("binding")
        if self.scope_type=="MISSION" and not self.mission_id: raise CognitiveInvocationError("mission binding")
        if require_digest:
            _hex(self.binding_digest,"binding_digest")
            if self.binding_digest!=self.compute_digest():raise CognitiveInvocationError("binding digest")
        return self
    def sealed(self): return replace(self,binding_digest=self.compute_digest()).validate()
@dataclass(frozen=True)
class InvocationIntent:
    invocation_id:str;parent_request_ref:str;message_ref:str;payload_digest:str;binding_ref:str;binding_digest:str;provider_leg:str;route_policy_ref:str;cognitive_class:str;deadline_at:str;causal_group_ref:str;authority_effect:str="NONE"
    def validate(self):
        for v,n in [(self.invocation_id,"invocation_id"),(self.parent_request_ref,"parent_request_ref"),(self.message_ref,"message_ref"),(self.binding_ref,"binding_ref"),(self.route_policy_ref,"route_policy_ref"),(self.causal_group_ref,"causal_group_ref")]:_id(v,n)
        _hex(self.payload_digest,"payload_digest");_hex(self.binding_digest,"binding_digest");_txt(self.deadline_at,"deadline_at")
        if self.provider_leg not in PROVIDER_CLASSES or self.cognitive_class not in COGNITIVE_CLASSES or self.authority_effect!="NONE":raise CognitiveInvocationError("intent")
        return self
@dataclass(frozen=True)
class InvocationPlan:
    plan_id:str;invocation_ref:str;endpoint_ref:str;session_binding_ref:str;model_release_ref:str;transport_profile_ref:str;causal_group_ref:str;scheduler_assignment_ref:str|None;plan_digest:str="";authority_effect:str="NONE"
    def payload(self):d=asdict(self);d.pop("plan_digest",None);return d
    def compute_digest(self):return _digest(b"LION/COGNITIVE-INVOCATION-PLAN/1\0",self.payload())
    def validate(self,require_digest=True):
        for v,n in [(self.plan_id,"plan_id"),(self.invocation_ref,"invocation_ref"),(self.endpoint_ref,"endpoint_ref"),(self.session_binding_ref,"session_binding_ref"),(self.model_release_ref,"model_release_ref"),(self.transport_profile_ref,"transport_profile_ref"),(self.causal_group_ref,"causal_group_ref")]:_id(v,n)
        if self.scheduler_assignment_ref is not None:_id(self.scheduler_assignment_ref,"scheduler_assignment_ref")
        if self.authority_effect!="NONE":raise CognitiveInvocationError("plan authority")
        if require_digest:
            _hex(self.plan_digest,"plan_digest")
            if self.plan_digest!=self.compute_digest():raise CognitiveInvocationError("plan digest")
        return self
    def sealed(self):return replace(self,plan_digest=self.compute_digest()).validate()
@dataclass(frozen=True)
class InvocationAttempt:
    attempt_id:str;invocation_ref:str;plan_digest:str;generation:int;started_at:str;attempt_digest:str="";authority_effect:str="NONE"
    def payload(self):d=asdict(self);d.pop("attempt_digest",None);return d
    def compute_digest(self):return _digest(b"LION/COGNITIVE-INVOCATION-ATTEMPT/1\0",self.payload())
    def validate(self,require_digest=True):
        _id(self.attempt_id,"attempt_id");_id(self.invocation_ref,"invocation_ref");_hex(self.plan_digest,"plan_digest");_txt(self.started_at,"started_at")
        if isinstance(self.generation,bool) or self.generation<1 or self.authority_effect!="NONE":raise CognitiveInvocationError("attempt")
        if require_digest and (not _HEX.fullmatch(self.attempt_digest) or self.attempt_digest!=self.compute_digest()):raise CognitiveInvocationError("attempt digest")
        return self
    def sealed(self):return replace(self,attempt_digest=self.compute_digest()).validate()
@dataclass(frozen=True)
class InvocationLease:
    lease_id:str;attempt_ref:str;issued_at:str;expires_at:str;lease_scope:str;authority_effect:str="NONE"
    def validate(self):
        _id(self.lease_id,"lease_id");_id(self.attempt_ref,"attempt_ref");_txt(self.issued_at,"issued_at");_txt(self.expires_at,"expires_at");_txt(self.lease_scope,"lease_scope")
        if self.authority_effect!="NONE":raise CognitiveInvocationError("lease authority")
        return self
@dataclass(frozen=True)
class InvocationReceipt:
    receipt_id:str;attempt_ref:str;transport_profile_ref:str;state:str;result_digest:str|None;observed_at:str;authority_effect:str="NONE"
    def validate(self):
        _id(self.receipt_id,"receipt_id");_id(self.attempt_ref,"attempt_ref");_id(self.transport_profile_ref,"transport_profile_ref");_txt(self.observed_at,"observed_at")
        if self.state not in INVOCATION_STATES or self.authority_effect!="NONE":raise CognitiveInvocationError("receipt")
        if self.result_digest is not None:_hex(self.result_digest,"result_digest")
        return self
@dataclass(frozen=True)
class InvocationCurrentness:
    invocation_ref:str;transport_state:str;session_state:str;model_release_state:str;runtime_state:str;observed_at:str;evidence_refs:Tuple[str,...]
    def validate(self):
        _id(self.invocation_ref,"invocation_ref");_txt(self.observed_at,"observed_at")
        if any(x not in CURRENTNESS_STATES for x in (self.transport_state,self.session_state,self.model_release_state,self.runtime_state)):raise CognitiveInvocationError("currentness")
        if type(self.evidence_refs) is not tuple or not self.evidence_refs:raise CognitiveInvocationError("currentness evidence")
        return self
@dataclass(frozen=True)
class InvocationReconciliation:
    invocation_ref:str;attempt_ref:str;expected_payload_digest:str;reported_result_digest:str|None;observed_delivery_digest:str|None;state:str;evidence_refs:Tuple[str,...];authority_effect:str="NONE"
    def validate(self):
        _id(self.invocation_ref,"invocation_ref");_id(self.attempt_ref,"attempt_ref");_hex(self.expected_payload_digest,"expected_payload_digest")
        if self.reported_result_digest is not None:_hex(self.reported_result_digest,"reported_result_digest")
        if self.observed_delivery_digest is not None:_hex(self.observed_delivery_digest,"observed_delivery_digest")
        if self.state not in {"RECONCILED","PARTIAL","UNKNOWN","FAILED"} or type(self.evidence_refs) is not tuple or self.authority_effect!="NONE":raise CognitiveInvocationError("reconciliation")
        if self.state=="RECONCILED" and (not self.reported_result_digest or not self.observed_delivery_digest or not self.evidence_refs):raise CognitiveInvocationError("false reconciliation")
        return self

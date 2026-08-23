"""Immutable contracts for F009 deterministic runtime admission R2.

These objects bind one canonical PDP ALLOW, one trusted PDP evidence record, one
provisioned executor identity and one exact requested effect. They grant no authority
by themselves and execute no effect.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Any, Mapping

_SCHEMA="1.1.0"
_SHA256=re.compile(r"^[0-9a-f]{64}$")
_OBS={"HEALTHY","DEGRADED","LOST"}

class RuntimeEnforcementContractError(ValueError): pass

def canonical_json(value:Mapping[str,Any])->bytes:
    return json.dumps(dict(value),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def _text(v:Any,n:str,limit:int=2048)->str:
    if not isinstance(v,str) or not v.strip() or len(v)>limit or "\x00" in v: raise RuntimeEnforcementContractError(f"{n} invalid")
    return v

def _digest(v:Any,n:str)->str:
    v=_text(v,n,64)
    if not _SHA256.fullmatch(v): raise RuntimeEnforcementContractError(f"{n} must be sha256 hex")
    return v

def _utc(v:Any,n:str)->datetime:
    v=_text(v,n)
    try:d=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as exc:raise RuntimeEnforcementContractError(f"{n} invalid") from exc
    if d.tzinfo is None:raise RuntimeEnforcementContractError(f"{n} must be timezone-aware")
    return d

@dataclass(frozen=True)
class PDPSourceTrustBinding:
    source_id:str
    source_instance_id:str
    source_implementation_digest:str
    trust_anchor_id:str
    trust_anchor_digest:str
    schema_version:str=_SCHEMA
    def validate(self):
        if self.schema_version!=_SCHEMA:raise RuntimeEnforcementContractError("unsupported PDP source trust schema")
        for n in ("source_id","source_instance_id","trust_anchor_id"):_text(getattr(self,n),n)
        _digest(self.source_implementation_digest,"source_implementation_digest");_digest(self.trust_anchor_digest,"trust_anchor_digest")
        return self
    def binding(self):
        self.validate();return (self.source_id,self.source_instance_id,self.source_implementation_digest,self.trust_anchor_id,self.trust_anchor_digest)

@dataclass(frozen=True)
class CanonicalPDPDecisionEvidence:
    request_id:str
    gate_event_id:str
    proposal_id:str
    gate_decision_digest:str
    pdp_receipt_digest:str
    request_digest:str
    replay_key:str
    policy_binding:str
    authority_lineage_digest:str
    observability_state:str
    source_id:str
    source_instance_id:str
    source_implementation_digest:str
    trust_anchor_id:str
    trust_anchor_digest:str
    issued_at:str
    expires_at:str
    evidence_digest:str=""
    schema_version:str=_SCHEMA
    def canonical_dict(self,*,include_digest:bool=True):
        self.validate(check_digest=False);d=asdict(self)
        if not include_digest:d.pop("evidence_digest")
        return d
    def compute_digest(self):return sha256(b"LION/F009-PDP-EVIDENCE/2\0"+canonical_json(self.canonical_dict(include_digest=False))).hexdigest()
    def validate(self,*,check_digest:bool=True):
        if self.schema_version!=_SCHEMA:raise RuntimeEnforcementContractError("unsupported PDP evidence schema")
        for n in ("request_id","gate_event_id","proposal_id","policy_binding","source_id","source_instance_id","trust_anchor_id"):_text(getattr(self,n),n)
        for n in ("gate_decision_digest","pdp_receipt_digest","request_digest","replay_key","authority_lineage_digest","source_implementation_digest","trust_anchor_digest"):_digest(getattr(self,n),n)
        if self.observability_state not in _OBS:raise RuntimeEnforcementContractError("invalid observability_state")
        issued=_utc(self.issued_at,"issued_at");expires=_utc(self.expires_at,"expires_at")
        if expires<=issued:raise RuntimeEnforcementContractError("PDP evidence expiry must follow issue time")
        if check_digest:
            _digest(self.evidence_digest,"evidence_digest")
            if self.evidence_digest!=self.compute_digest():raise RuntimeEnforcementContractError("PDP evidence digest mismatch")
        return self
    def sealed(self):
        self.validate(check_digest=False);return CanonicalPDPDecisionEvidence(**{**asdict(self),"evidence_digest":self.compute_digest()}).validate()

@dataclass(frozen=True)
class RuntimeIdentityBinding:
    workload_identity:str
    execution_subject:str
    runtime_instance_id:str
    sandbox_id:str
    workspace_id:str
    runtime_attestation_digest:str
    provisioned_executor_digest:str
    schema_version:str=_SCHEMA
    def validate(self):
        if self.schema_version!=_SCHEMA: raise RuntimeEnforcementContractError("unsupported runtime identity schema")
        for n in ("workload_identity","execution_subject","runtime_instance_id","sandbox_id","workspace_id"):_text(getattr(self,n),n)
        _digest(self.runtime_attestation_digest,"runtime_attestation_digest");_digest(self.provisioned_executor_digest,"provisioned_executor_digest")
        return self
    def canonical_dict(self):self.validate();return asdict(self)
    def digest(self):return sha256(b"LION/F009-RUNTIME-IDENTITY/2\0"+canonical_json(self.canonical_dict())).hexdigest()

@dataclass(frozen=True)
class RequestedRuntimeEffect:
    effect_id:str
    proposal_id:str
    mission_id:str
    policy_binding:str
    authority_lineage_digest:str
    requested_authority:str
    action_class:str
    resource:str
    payload_digest:str
    observability_state:str
    runtime_identity_digest:str
    schema_version:str=_SCHEMA
    def validate(self):
        if self.schema_version!=_SCHEMA:raise RuntimeEnforcementContractError("unsupported requested effect schema")
        for n in ("effect_id","proposal_id","mission_id","policy_binding","requested_authority","action_class","resource"):_text(getattr(self,n),n)
        for n in ("authority_lineage_digest","payload_digest","runtime_identity_digest"):_digest(getattr(self,n),n)
        if self.observability_state not in _OBS:raise RuntimeEnforcementContractError("invalid observability_state")
        return self
    def canonical_dict(self):self.validate();return asdict(self)
    def digest(self):return sha256(b"LION/F009-REQUESTED-EFFECT/2\0"+canonical_json(self.canonical_dict())).hexdigest()

@dataclass(frozen=True)
class RuntimeAdmission:
    admission_id:str
    request_id:str
    gate_event_id:str
    proposal_id:str
    gate_decision_digest:str
    pdp_receipt_digest:str
    pdp_evidence_digest:str
    live_authority_digest:str
    authority_lineage_digest:str
    policy_binding:str
    effective_authority:str
    requested_effect_digest:str
    runtime_identity_digest:str
    provisioned_executor_digest:str
    observability_state:str
    replay_key:str
    admission_digest:str=""
    schema_version:str=_SCHEMA
    def canonical_dict(self,*,include_digest:bool=True):
        self.validate(check_digest=False);d=asdict(self)
        if not include_digest:d.pop("admission_digest")
        return d
    def compute_digest(self):return sha256(b"LION/F009-RUNTIME-ADMISSION/2\0"+canonical_json(self.canonical_dict(include_digest=False))).hexdigest()
    def validate(self,*,check_digest:bool=True):
        if self.schema_version!=_SCHEMA:raise RuntimeEnforcementContractError("unsupported runtime admission schema")
        for n in ("admission_id","request_id","gate_event_id","proposal_id","policy_binding","effective_authority"):_text(getattr(self,n),n)
        for n in ("gate_decision_digest","pdp_receipt_digest","pdp_evidence_digest","live_authority_digest","authority_lineage_digest","requested_effect_digest","runtime_identity_digest","provisioned_executor_digest","replay_key"):_digest(getattr(self,n),n)
        if self.observability_state not in _OBS:raise RuntimeEnforcementContractError("invalid observability_state")
        if check_digest:
            _digest(self.admission_digest,"admission_digest")
            if self.admission_digest!=self.compute_digest():raise RuntimeEnforcementContractError("admission_digest mismatch")
        return self
    def sealed(self):
        self.validate(check_digest=False);return RuntimeAdmission(**{**asdict(self),"admission_digest":self.compute_digest()}).validate()

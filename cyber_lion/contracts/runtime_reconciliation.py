"""Independent effect-observation and reconciliation contracts for F009.

Execution receipts and effect observations are separate evidence surfaces. Neither may
substitute for the other and no UNKNOWN/PARTIAL_UNKNOWN state may reconcile as success.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass
from datetime import datetime
from hashlib import sha256
import json,re
from typing import Any,Mapping

SCHEMA_VERSION="1.0.0"
_SHA256=re.compile(r"^[0-9a-f]{64}$")
_EFFECT_STATES={"OBSERVED","UNKNOWN","PARTIAL_UNKNOWN"}
_DISPOSITIONS={"MATCHED","NON_SUCCESS_RECONCILED","MISMATCH","UNKNOWN"}
class RuntimeReconciliationContractError(ValueError):pass

def canonical_json(v:Mapping[str,Any])->bytes:return json.dumps(dict(v),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _text(v:Any,n:str,limit:int=2048)->str:
    if not isinstance(v,str) or not v.strip() or len(v)>limit or "\x00" in v:raise RuntimeReconciliationContractError(f"{n} invalid")
    return v
def _digest(v:Any,n:str)->str:
    v=_text(v,n,64)
    if not _SHA256.fullmatch(v):raise RuntimeReconciliationContractError(f"{n} must be sha256 hex")
    return v
def _utc(v:Any,n:str)->datetime:
    v=_text(v,n)
    try:d=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as exc:raise RuntimeReconciliationContractError(f"{n} invalid") from exc
    if d.tzinfo is None:raise RuntimeReconciliationContractError(f"{n} must be timezone-aware")
    return d

@dataclass(frozen=True)
class RuntimeObserverTrustBinding:
    source_id:str;source_instance_id:str;source_implementation_digest:str;trust_anchor_id:str;trust_anchor_digest:str;schema_version:str=SCHEMA_VERSION
    def validate(self):
        if self.schema_version!=SCHEMA_VERSION:raise RuntimeReconciliationContractError("unsupported observer trust schema")
        for n in ("source_id","source_instance_id","trust_anchor_id"):_text(getattr(self,n),n)
        _digest(self.source_implementation_digest,"source_implementation_digest");_digest(self.trust_anchor_digest,"trust_anchor_digest");return self
    def binding(self):self.validate();return (self.source_id,self.source_instance_id,self.source_implementation_digest,self.trust_anchor_id,self.trust_anchor_digest)

@dataclass(frozen=True)
class RuntimeEffectObservation:
    observation_id:str;execution_id:str;admission_digest:str;request_digest:str;operation_digest:str;action:str;resource:str;effect_state:str;effect_digest:str;observed_events:tuple[str,...];side_effect_refs:tuple[str,...];source_id:str;source_instance_id:str;source_implementation_digest:str;trust_anchor_id:str;trust_anchor_digest:str;observed_at:str;observation_digest:str="";schema_version:str=SCHEMA_VERSION
    def canonical_dict(self,*,include_digest=True):
        self.validate(check_digest=False);d=asdict(self);d["observed_events"]=list(self.observed_events);d["side_effect_refs"]=list(self.side_effect_refs)
        if not include_digest:d.pop("observation_digest")
        return d
    def compute_digest(self):return sha256(b"LION/F009-RUNTIME-OBSERVATION/1\0"+canonical_json(self.canonical_dict(include_digest=False))).hexdigest()
    def validate(self,*,check_digest=True):
        if self.schema_version!=SCHEMA_VERSION:raise RuntimeReconciliationContractError("unsupported observation schema")
        for n in ("observation_id","execution_id","action","resource","source_id","source_instance_id","trust_anchor_id"):_text(getattr(self,n),n)
        for n in ("admission_digest","request_digest","operation_digest","effect_digest","source_implementation_digest","trust_anchor_digest"):_digest(getattr(self,n),n)
        if self.effect_state not in _EFFECT_STATES:raise RuntimeReconciliationContractError("invalid effect_state")
        if type(self.observed_events) is not tuple or not self.observed_events or len(set(self.observed_events))!=len(self.observed_events):raise RuntimeReconciliationContractError("observed_events invalid")
        if type(self.side_effect_refs) is not tuple or len(set(self.side_effect_refs))!=len(self.side_effect_refs):raise RuntimeReconciliationContractError("side_effect_refs invalid")
        if self.effect_state=="PARTIAL_UNKNOWN" and not self.side_effect_refs:raise RuntimeReconciliationContractError("partial unknown requires side-effect evidence")
        _utc(self.observed_at,"observed_at")
        if check_digest:
            _digest(self.observation_digest,"observation_digest")
            if self.observation_digest!=self.compute_digest():raise RuntimeReconciliationContractError("observation_digest mismatch")
        return self
    def sealed(self):self.validate(check_digest=False);return RuntimeEffectObservation(**{**asdict(self),"observation_digest":self.compute_digest()}).validate()

@dataclass(frozen=True)
class RuntimeReconciliationReceipt:
    reconciliation_id:str;runtime_execution_receipt_digest:str;effect_observation_digest:str;currentness_evidence_digest:str;execution_id:str;admission_digest:str;disposition:str;anomaly_codes:tuple[str,...];reconciled_effect_digest:str;reconciled_at:str;reconciliation_digest:str="";schema_version:str=SCHEMA_VERSION
    def canonical_dict(self,*,include_digest=True):
        self.validate(check_digest=False);d=asdict(self);d["anomaly_codes"]=list(self.anomaly_codes)
        if not include_digest:d.pop("reconciliation_digest")
        return d
    def compute_digest(self):return sha256(b"LION/F009-RUNTIME-RECONCILIATION/1\0"+canonical_json(self.canonical_dict(include_digest=False))).hexdigest()
    def validate(self,*,check_digest=True):
        if self.schema_version!=SCHEMA_VERSION:raise RuntimeReconciliationContractError("unsupported reconciliation schema")
        for n in ("reconciliation_id","execution_id"):_text(getattr(self,n),n)
        for n in ("runtime_execution_receipt_digest","effect_observation_digest","currentness_evidence_digest","admission_digest","reconciled_effect_digest"):_digest(getattr(self,n),n)
        if self.disposition not in _DISPOSITIONS:raise RuntimeReconciliationContractError("invalid disposition")
        if type(self.anomaly_codes) is not tuple or len(set(self.anomaly_codes))!=len(self.anomaly_codes):raise RuntimeReconciliationContractError("anomaly_codes invalid")
        if self.disposition=="MATCHED" and self.anomaly_codes:raise RuntimeReconciliationContractError("MATCHED cannot contain anomalies")
        if self.disposition in {"MISMATCH","UNKNOWN"} and not self.anomaly_codes:raise RuntimeReconciliationContractError("non-matched disposition requires anomaly evidence")
        _utc(self.reconciled_at,"reconciled_at")
        if check_digest:
            _digest(self.reconciliation_digest,"reconciliation_digest")
            if self.reconciliation_digest!=self.compute_digest():raise RuntimeReconciliationContractError("reconciliation_digest mismatch")
        return self
    def sealed(self):self.validate(check_digest=False);return RuntimeReconciliationReceipt(**{**asdict(self),"reconciliation_digest":self.compute_digest()}).validate()

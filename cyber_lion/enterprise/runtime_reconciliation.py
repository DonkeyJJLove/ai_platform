"""Independent F009 runtime receipt/effect reconciliation.

The reconciler consumes one RuntimeExecutionReceipt, one independently sourced effect
observation, and one effect-time currentness evidence record. It never executes effects
or mints authority. UNKNOWN/PARTIAL_UNKNOWN can never become MATCHED success.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from typing import Protocol
from cyber_lion.contracts.runtime_currentness import EffectTimeCurrentnessEvidence
from cyber_lion.contracts.runtime_execution import RuntimeExecutionReceipt
from cyber_lion.contracts.runtime_reconciliation import RuntimeEffectObservation,RuntimeObserverTrustBinding,RuntimeReconciliationReceipt

class RuntimeReconciliationError(RuntimeError):pass
class RuntimeObservationSource(Protocol):
    source_id:str;source_instance_id:str;implementation_digest:str;trust_anchor_id:str;trust_anchor_digest:str
    def observe(self,execution_id:str)->RuntimeEffectObservation:...

class RuntimeReconciler:
    def __init__(self,*,observer:RuntimeObservationSource,observer_trust:RuntimeObserverTrustBinding,clock):
        observer_trust.validate();actual=(getattr(observer,"source_id",None),getattr(observer,"source_instance_id",None),getattr(observer,"implementation_digest",None),getattr(observer,"trust_anchor_id",None),getattr(observer,"trust_anchor_digest",None))
        if actual!=observer_trust.binding():raise RuntimeReconciliationError("runtime observer substitution denied")
        if not callable(getattr(observer,"observe",None)):raise RuntimeReconciliationError("runtime observer unavailable")
        self._observer=observer;self._trust=observer_trust;self._clock=clock
    def _now(self):
        now=self._clock()
        if not isinstance(now,datetime) or now.tzinfo is None:raise RuntimeReconciliationError("trusted reconciliation clock unavailable")
        return now.astimezone(timezone.utc)
    def reconcile(self,*,receipt:RuntimeExecutionReceipt,currentness:EffectTimeCurrentnessEvidence)->RuntimeReconciliationReceipt:
        if type(receipt) is not RuntimeExecutionReceipt or type(currentness) is not EffectTimeCurrentnessEvidence:raise RuntimeReconciliationError("exact receipt/currentness evidence required")
        try:receipt.validate();currentness.validate()
        except Exception as exc:raise RuntimeReconciliationError("runtime reconciliation input invalid") from exc
        if currentness.admission_digest!=receipt.admission_digest:raise RuntimeReconciliationError("currentness/admission binding mismatch")
        try:obs=self._observer.observe(receipt.execution_id)
        except Exception as exc:raise RuntimeReconciliationError("independent runtime observation unavailable") from exc
        if type(obs) is not RuntimeEffectObservation:raise RuntimeReconciliationError("observer returned invalid type")
        try:obs.validate()
        except Exception as exc:raise RuntimeReconciliationError("independent runtime observation invalid") from exc
        source=(obs.source_id,obs.source_instance_id,obs.source_implementation_digest,obs.trust_anchor_id,obs.trust_anchor_digest)
        if source!=self._trust.binding():raise RuntimeReconciliationError("observation source binding mismatch")
        anomalies=[]
        expected=(receipt.execution_id,receipt.admission_digest,receipt.request_digest,receipt.operation_digest,receipt.action,receipt.resource)
        actual=(obs.execution_id,obs.admission_digest,obs.request_digest,obs.operation_digest,obs.action,obs.resource)
        if actual!=expected:anomalies.append("IDENTITY_OR_OPERATION_MISMATCH")
        if obs.effect_digest!=receipt.effect_digest:anomalies.append("EFFECT_DIGEST_MISMATCH")
        if tuple(obs.observed_events)!=tuple(receipt.observed_events):anomalies.append("OBSERVED_EVENTS_MISMATCH")
        if set(obs.side_effect_refs)!=set(receipt.side_effect_refs):anomalies.append("SIDE_EFFECT_REFERENCE_MISMATCH")
        disposition="MATCHED"
        if receipt.outcome=="SUCCEEDED":
            if receipt.effect_state!="OBSERVED" or obs.effect_state!="OBSERVED":anomalies.append("SUCCESS_WITHOUT_OBSERVED_EFFECT")
            disposition="MISMATCH" if anomalies else "MATCHED"
        else:
            if receipt.effect_state in {"UNKNOWN","PARTIAL_UNKNOWN"} or obs.effect_state in {"UNKNOWN","PARTIAL_UNKNOWN"}:
                disposition="UNKNOWN" if obs.effect_state=="UNKNOWN" or receipt.effect_state=="UNKNOWN" else "NON_SUCCESS_RECONCILED"
                if disposition=="UNKNOWN" and "UNKNOWN_EFFECT" not in anomalies:anomalies.append("UNKNOWN_EFFECT")
            elif anomalies:disposition="MISMATCH"
            else:disposition="NON_SUCCESS_RECONCILED"
        if receipt.outcome=="SUCCEEDED" and disposition!="MATCHED":pass
        if receipt.outcome!="SUCCEEDED" and disposition=="MATCHED":raise RuntimeReconciliationError("non-success cannot reconcile as MATCHED")
        now=self._now().isoformat();rid=sha256((receipt.receipt_digest+"\0"+obs.observation_digest+"\0"+currentness.evidence_digest).encode()).hexdigest()
        return RuntimeReconciliationReceipt(rid,receipt.receipt_digest,obs.observation_digest,currentness.evidence_digest,receipt.execution_id,receipt.admission_digest,disposition,tuple(sorted(set(anomalies))),obs.effect_digest,now).sealed()

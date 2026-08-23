"""F009 admission-bound runtime execution by composition over the existing sandbox PEP.

The engine consumes one canonical current RuntimeAdmission before invoking the bounded
sandbox. It never mints authority and treats unknown or partial effects as non-success.
"""
from __future__ import annotations

from hashlib import sha256
from threading import Lock
from typing import Protocol

from cyber_lion.contracts.executor_sandbox import SandboxExecutionReceipt,SandboxOperation
from cyber_lion.contracts.runtime_enforcement import RequestedRuntimeEffect,RuntimeAdmission,RuntimeIdentityBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding,RuntimeExecutionReceipt,RuntimeExecutionRequest
from .executor_sandbox import SandboxExecutionResult

class RuntimeExecutionError(RuntimeError):pass

class RuntimeAdmissionSource(Protocol):
    source_id:str;source_instance_id:str;implementation_digest:str;trust_anchor_id:str;trust_anchor_digest:str
    def resolve(self,admission_digest:str)->RuntimeAdmission:...
    def is_current(self,admission_digest:str)->bool:...

class AdmissionConsumptionGuard(Protocol):
    def consume(self,admission_digest:str,execution_id:str)->bool:...

class InMemoryAdmissionConsumptionGuard:
    def __init__(self):self._lock=Lock();self._seen:set[str]=set()
    def consume(self,admission_digest:str,execution_id:str)->bool:
        with self._lock:
            if admission_digest in self._seen:return False
            self._seen.add(admission_digest);return True

class SandboxExecutor(Protocol):
    @property
    def policy_digest(self)->str:...
    def execute(self,op:SandboxOperation,*,payload:bytes=b"")->SandboxExecutionResult:...

class RuntimeExecutionEngine:
    def __init__(self,*,admission_source:RuntimeAdmissionSource,admission_source_trust:RuntimeAdmissionSourceTrustBinding,consumption_guard:AdmissionConsumptionGuard,sandbox:SandboxExecutor):
        if type(admission_source_trust) is not RuntimeAdmissionSourceTrustBinding:raise RuntimeExecutionError("exact admission source trust binding required")
        admission_source_trust.validate()
        actual=(getattr(admission_source,"source_id",None),getattr(admission_source,"source_instance_id",None),getattr(admission_source,"implementation_digest",None),getattr(admission_source,"trust_anchor_id",None),getattr(admission_source,"trust_anchor_digest",None))
        if actual!=admission_source_trust.binding():raise RuntimeExecutionError("runtime admission source substitution denied")
        if not callable(getattr(admission_source,"resolve",None)) or not callable(getattr(admission_source,"is_current",None)):raise RuntimeExecutionError("runtime admission source unavailable")
        if not callable(getattr(consumption_guard,"consume",None)):raise RuntimeExecutionError("admission consumption guard unavailable")
        if not callable(getattr(sandbox,"execute",None)) or not isinstance(getattr(sandbox,"policy_digest",None),str):raise RuntimeExecutionError("bounded sandbox unavailable")
        self._source=admission_source;self._trust=admission_source_trust;self._consume=consumption_guard;self._sandbox=sandbox

    def _canonical_admission(self,admission:RuntimeAdmission)->RuntimeAdmission:
        try:admission.validate();canonical=self._source.resolve(admission.admission_digest)
        except Exception as exc:raise RuntimeExecutionError("canonical runtime admission unavailable") from exc
        if type(canonical) is not RuntimeAdmission:raise RuntimeExecutionError("canonical admission source returned invalid type")
        try:canonical.validate()
        except Exception as exc:raise RuntimeExecutionError("canonical runtime admission invalid") from exc
        if canonical.admission_digest!=admission.admission_digest or canonical!=admission:raise RuntimeExecutionError("forged or substituted RuntimeAdmission denied")
        try:current=self._source.is_current(admission.admission_digest)
        except Exception as exc:raise RuntimeExecutionError("runtime admission currentness unavailable") from exc
        if current is not True:raise RuntimeExecutionError("stale RuntimeAdmission denied")
        return canonical

    @staticmethod
    def _validate_bindings(admission:RuntimeAdmission,request:RuntimeExecutionRequest,effect:RequestedRuntimeEffect,identity:RuntimeIdentityBinding,payload:bytes)->None:
        try:request.validate();effect.validate();identity.validate()
        except Exception as exc:raise RuntimeExecutionError("runtime execution input invalid") from exc
        if request.admission_digest!=admission.admission_digest:raise RuntimeExecutionError("execution request admission substitution denied")
        if request.requested_effect_digest!=admission.requested_effect_digest or effect.digest()!=admission.requested_effect_digest:raise RuntimeExecutionError("admission effect substitution denied")
        if request.runtime_identity_digest!=admission.runtime_identity_digest or identity.digest()!=admission.runtime_identity_digest:raise RuntimeExecutionError("runtime identity substitution denied")
        if request.provisioned_executor_digest!=admission.provisioned_executor_digest or identity.provisioned_executor_digest!=admission.provisioned_executor_digest:raise RuntimeExecutionError("provisioned executor substitution denied")
        if request.mission_id!=effect.mission_id:raise RuntimeExecutionError("mission binding mismatch")
        if (request.runtime_instance_id,request.sandbox_id,request.workspace_id)!=(identity.runtime_instance_id,identity.sandbox_id,identity.workspace_id):raise RuntimeExecutionError("runtime/sandbox/workspace binding mismatch")
        if request.executor_id!=identity.execution_subject:raise RuntimeExecutionError("execution subject binding mismatch")
        if (request.action,request.resource)!=(effect.action_class,effect.resource):raise RuntimeExecutionError("action or resource substitution denied")
        if request.payload_digest!=effect.payload_digest:raise RuntimeExecutionError("payload digest substitution denied")
        if not isinstance(payload,bytes):raise RuntimeExecutionError("payload type invalid")
        if request.action=="WRITE_FILE":
            if len(payload)!=request.payload_size or sha256(payload).hexdigest()!=request.payload_digest:raise RuntimeExecutionError("write payload binding mismatch")
        elif payload or request.payload_size:raise RuntimeExecutionError("unexpected payload for non-write operation")

    def execute(self,*,admission:RuntimeAdmission,request:RuntimeExecutionRequest,effect:RequestedRuntimeEffect,runtime_identity:RuntimeIdentityBinding,payload:bytes=b"")->RuntimeExecutionReceipt:
        canonical=self._canonical_admission(admission)
        self._validate_bindings(canonical,request,effect,runtime_identity,payload)
        op=SandboxOperation(operation_id=request.execution_id,mission_id=request.mission_id,drone_id=runtime_identity.workload_identity,executor_id=request.executor_id,sandbox_id=request.sandbox_id,workspace_id=request.workspace_id,dispatch_id=request.dispatch_id,fencing_token=request.fencing_token,generation=request.generation,policy_digest=self._sandbox.policy_digest,action=request.action,path=request.resource,payload_digest=request.payload_digest if request.action=="WRITE_FILE" else None,payload_size=request.payload_size,command=()).validate()
        try:consumed=self._consume.consume(canonical.admission_digest,request.execution_id)
        except Exception as exc:raise RuntimeExecutionError("admission consumption state unavailable") from exc
        if consumed is not True:raise RuntimeExecutionError("RuntimeAdmission replay denied")
        try:result=self._sandbox.execute(op,payload=payload)
        except Exception as exc:raise RuntimeExecutionError("bounded sandbox execution failed before trustworthy receipt") from exc
        if type(result) is not SandboxExecutionResult or type(result.receipt) is not SandboxExecutionReceipt:raise RuntimeExecutionError("sandbox returned invalid execution result")
        receipt=result.receipt
        try:receipt.validate()
        except Exception as exc:raise RuntimeExecutionError("sandbox execution receipt invalid") from exc
        expected=(op.operation_id,op.digest(),self._sandbox.policy_digest,request.mission_id,request.executor_id,request.sandbox_id,request.workspace_id,request.dispatch_id,request.fencing_token,request.generation,request.runtime_instance_id,request.action)
        actual=(receipt.operation_id,receipt.operation_digest,receipt.policy_digest,receipt.mission_id,receipt.executor_id,receipt.sandbox_id,receipt.workspace_id,receipt.dispatch_id,receipt.fencing_token,receipt.generation,receipt.runtime_instance_id,receipt.action)
        if actual!=expected:raise RuntimeExecutionError("sandbox receipt binding mismatch")
        if not receipt.observed_events:raise RuntimeExecutionError("effect observation missing")
        if request.action=="WRITE_FILE" and receipt.outcome=="SUCCEEDED" and (receipt.effect_digest!=request.payload_digest or not receipt.side_effect_refs):raise RuntimeExecutionError("successful write lacks exact observed effect binding")
        effect_state="OBSERVED"
        if receipt.outcome=="ABORTED":effect_state="PARTIAL_UNKNOWN" if receipt.side_effect_refs else "UNKNOWN"
        if receipt.outcome=="SUCCEEDED" and effect_state!="OBSERVED":raise RuntimeExecutionError("unknown effect cannot succeed")
        sr_digest=receipt.digest()
        return RuntimeExecutionReceipt(receipt_id="runtime-execution:"+sha256((canonical.admission_digest+request.digest()+sr_digest).encode("ascii")).hexdigest(),execution_id=request.execution_id,admission_digest=canonical.admission_digest,request_digest=request.digest(),sandbox_receipt_digest=sr_digest,operation_digest=op.digest(),mission_id=request.mission_id,executor_id=request.executor_id,runtime_instance_id=request.runtime_instance_id,sandbox_id=request.sandbox_id,workspace_id=request.workspace_id,dispatch_id=request.dispatch_id,fencing_token=request.fencing_token,generation=request.generation,action=request.action,resource=request.resource,payload_digest=request.payload_digest,outcome=receipt.outcome,effect_state=effect_state,effect_digest=receipt.effect_digest,observed_events=receipt.observed_events,side_effect_refs=receipt.side_effect_refs).sealed()

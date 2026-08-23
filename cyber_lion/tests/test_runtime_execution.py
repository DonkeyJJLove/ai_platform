import unittest
from hashlib import sha256
from cyber_lion.contracts.executor_sandbox import SandboxExecutionReceipt
from cyber_lion.contracts.runtime_enforcement import RequestedRuntimeEffect,RuntimeAdmission,RuntimeIdentityBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding,RuntimeExecutionRequest
from cyber_lion.enterprise.executor_sandbox import SandboxExecutionResult
from cyber_lion.enterprise.runtime_execution import InMemoryAdmissionConsumptionGuard,RuntimeExecutionEngine,RuntimeExecutionError
Z="0"*64
F="f"*64
PAYLOAD=b"x"
PD=sha256(PAYLOAD).hexdigest()

class AdmissionSource:
    source_id="runtime-admission";source_instance_id="runtime-admission:1";implementation_digest=Z;trust_anchor_id="anchor";trust_anchor_digest=Z
    def __init__(self,admission,current=True):self.admission=admission;self.current=current
    def resolve(self,digest):return self.admission
    def is_current(self,digest):return self.current

def trust():return RuntimeAdmissionSourceTrustBinding("runtime-admission","runtime-admission:1",Z,"anchor",Z).validate()

def identity(**changes):
    values=dict(workload_identity="drone:1",execution_subject="executor:1",runtime_instance_id="runtime:1",sandbox_id="sandbox:1",workspace_id="workspace:1",runtime_attestation_digest=Z,provisioned_executor_digest=Z)
    values.update(changes);return RuntimeIdentityBinding(**values).validate()

def effect(i=None,**changes):
    i=i or identity();values=dict(effect_id="effect:1",proposal_id="proposal:1",mission_id="mission:1",policy_binding="policy@1:sha256:"+Z,authority_lineage_digest=Z,requested_authority="local_write",action_class="WRITE_FILE",resource="workspace/out.txt",payload_digest=PD,observability_state="HEALTHY",runtime_identity_digest=i.digest())
    values.update(changes);return RequestedRuntimeEffect(**values).validate()

def admission(e=None,i=None,**changes):
    i=i or identity();e=e or effect(i);values=dict(admission_id="admission:1",request_id="request:1",gate_event_id="gate:1",proposal_id=e.proposal_id,gate_decision_digest=Z,pdp_receipt_digest=Z,pdp_evidence_digest=Z,live_authority_digest=Z,authority_lineage_digest=e.authority_lineage_digest,policy_binding=e.policy_binding,effective_authority=e.requested_authority,requested_effect_digest=e.digest(),runtime_identity_digest=i.digest(),provisioned_executor_digest=i.provisioned_executor_digest,observability_state=e.observability_state,replay_key=Z)
    values.update(changes);return RuntimeAdmission(**values).sealed()

def request(a=None,e=None,i=None,**changes):
    i=i or identity();e=e or effect(i);a=a or admission(e,i);values=dict(execution_id="exec:1",admission_digest=a.admission_digest,requested_effect_digest=e.digest(),runtime_identity_digest=i.digest(),provisioned_executor_digest=i.provisioned_executor_digest,mission_id=e.mission_id,executor_id=i.execution_subject,runtime_instance_id=i.runtime_instance_id,sandbox_id=i.sandbox_id,workspace_id=i.workspace_id,dispatch_id=Z,fencing_token=F,generation=1,action=e.action_class,resource=e.resource,payload_digest=e.payload_digest,payload_size=len(PAYLOAD),command=())
    values.update(changes);return RuntimeExecutionRequest(**values).validate()

class FakeSandbox:
    policy_digest=Z
    def __init__(self,*,outcome="SUCCEEDED",observed=True,partial=False,expected_dispatch=Z,expected_fence=F,expected_generation=1):
        self.outcome=outcome;self.observed=observed;self.partial=partial;self.expected_dispatch=expected_dispatch;self.expected_fence=expected_fence;self.expected_generation=expected_generation;self.calls=0
    def execute(self,op,*,payload=b""):
        self.calls+=1
        if (op.dispatch_id,op.fencing_token,op.generation)!=(self.expected_dispatch,self.expected_fence,self.expected_generation):raise RuntimeError("stale dispatch/fence/generation")
        events=("event:1",) if self.observed else ()
        refs=("side:1",) if (op.action=="WRITE_FILE" and self.outcome=="SUCCEEDED") or self.partial else ()
        effect_digest=op.payload_digest if op.action=="WRITE_FILE" and self.outcome=="SUCCEEDED" else F
        receipt=SandboxExecutionReceipt("sandbox-receipt:"+op.operation_id,op.operation_id,op.digest(),self.policy_digest,Z,Z,Z,Z,op.mission_id,op.drone_id,op.executor_id,op.sandbox_id,op.workspace_id,op.dispatch_id,op.fencing_token,op.generation,op.runtime_instance_id if hasattr(op,"runtime_instance_id") else "runtime:1",Z,op.action,self.outcome,effect_digest,Z,0,len(payload) if op.action=="WRITE_FILE" else 0,None,events,refs)
        return SandboxExecutionResult(receipt,b"")

class DenyGuard:
    def consume(self,*_):return False

class RuntimeExecutionTests(unittest.TestCase):
    def fixture(self,*,current=True,sandbox=None,guard=None):
        i=identity();e=effect(i);a=admission(e,i);r=request(a,e,i);s=sandbox or FakeSandbox();eng=RuntimeExecutionEngine(admission_source=AdmissionSource(a,current),admission_source_trust=trust(),consumption_guard=guard or InMemoryAdmissionConsumptionGuard(),sandbox=s);return eng,a,r,e,i,s
    def execute(self,parts,payload=PAYLOAD):
        eng,a,r,e,i,_=parts;return eng.execute(admission=a,request=r,effect=e,runtime_identity=i,payload=payload)
    def test_exact_admission_executes_once_and_returns_observed_receipt(self):
        p=self.fixture();out=self.execute(p);out.validate();self.assertEqual(out.outcome,"SUCCEEDED");self.assertEqual(out.effect_state,"OBSERVED");self.assertEqual(p[5].calls,1)
    def test_replayed_runtime_admission_is_denied_before_second_effect(self):
        p=self.fixture();self.execute(p);self.assertRaises(RuntimeExecutionError,self.execute,p);self.assertEqual(p[5].calls,1)
    def test_forged_runtime_admission_is_denied(self):
        p=self.fixture();eng,a,r,e,i,s=p;forged=RuntimeAdmission(**{**a.__dict__,"admission_id":"forged","admission_digest":""}).sealed();self.assertRaises(RuntimeExecutionError,eng.execute,admission=forged,request=r,effect=e,runtime_identity=i,payload=PAYLOAD);self.assertEqual(s.calls,0)
    def test_stale_runtime_admission_is_denied(self):
        p=self.fixture(current=False);self.assertRaises(RuntimeExecutionError,self.execute,p);self.assertEqual(p[5].calls,0)
    def test_admission_effect_substitution_is_denied(self):
        p=self.fixture();eng,a,r,e,i,s=p;bad=RequestedRuntimeEffect(**{**e.__dict__,"resource":"workspace/other.txt"}).validate();self.assertRaises(RuntimeExecutionError,eng.execute,admission=a,request=r,effect=bad,runtime_identity=i,payload=PAYLOAD);self.assertEqual(s.calls,0)
    def test_wrong_dispatch_is_denied_by_bounded_sandbox(self):
        p=self.fixture();eng,a,r,e,i,s=p;bad=RuntimeExecutionRequest(**{**r.__dict__,"dispatch_id":F}).validate();self.assertRaises(RuntimeExecutionError,eng.execute,admission=a,request=bad,effect=e,runtime_identity=i,payload=PAYLOAD)
    def test_stale_fencing_token_is_denied_by_bounded_sandbox(self):
        p=self.fixture();eng,a,r,e,i,s=p;bad=RuntimeExecutionRequest(**{**r.__dict__,"fencing_token":Z}).validate();self.assertRaises(RuntimeExecutionError,eng.execute,admission=a,request=bad,effect=e,runtime_identity=i,payload=PAYLOAD)
    def test_wrong_generation_is_denied_by_bounded_sandbox(self):
        p=self.fixture();eng,a,r,e,i,s=p;bad=RuntimeExecutionRequest(**{**r.__dict__,"generation":2}).validate();self.assertRaises(RuntimeExecutionError,eng.execute,admission=a,request=bad,effect=e,runtime_identity=i,payload=PAYLOAD)
    def test_wrong_executor_is_denied_before_effect(self):
        p=self.fixture();eng,a,r,e,i,s=p;bad=RuntimeExecutionRequest(**{**r.__dict__,"executor_id":"executor:other"}).validate();self.assertRaises(RuntimeExecutionError,eng.execute,admission=a,request=bad,effect=e,runtime_identity=i,payload=PAYLOAD);self.assertEqual(s.calls,0)
    def test_wrong_runtime_instance_sandbox_workspace_are_denied(self):
        for field,value in (("runtime_instance_id","runtime:other"),("sandbox_id","sandbox:other"),("workspace_id","workspace:other")):
            p=self.fixture();eng,a,r,e,i,s=p;bad=RuntimeExecutionRequest(**{**r.__dict__,field:value}).validate();self.assertRaises(RuntimeExecutionError,eng.execute,admission=a,request=bad,effect=e,runtime_identity=i,payload=PAYLOAD);self.assertEqual(s.calls,0)
    def test_wrong_resource_action_and_payload_are_denied(self):
        for change in ({"resource":"workspace/other.txt"},{"action":"READ_FILE","payload_size":0},{"payload_digest":Z}):
            p=self.fixture();eng,a,r,e,i,s=p;bad=RuntimeExecutionRequest(**{**r.__dict__,**change})
            try:bad=bad.validate()
            except Exception:continue
            self.assertRaises(RuntimeExecutionError,eng.execute,admission=a,request=bad,effect=e,runtime_identity=i,payload=PAYLOAD);self.assertEqual(s.calls,0)
    def test_effect_cannot_run_when_admission_consumption_denied(self):
        p=self.fixture(guard=DenyGuard());self.assertRaises(RuntimeExecutionError,self.execute,p);self.assertEqual(p[5].calls,0)
    def test_missing_effect_observation_is_fail_closed(self):
        p=self.fixture(sandbox=FakeSandbox(observed=False));self.assertRaises(RuntimeExecutionError,self.execute,p)
    def test_unknown_effect_is_explicit_non_success(self):
        p=self.fixture(sandbox=FakeSandbox(outcome="ABORTED"));out=self.execute(p);self.assertEqual(out.outcome,"ABORTED");self.assertEqual(out.effect_state,"UNKNOWN")
    def test_partial_unknown_effect_is_explicit_non_success(self):
        p=self.fixture(sandbox=FakeSandbox(outcome="ABORTED",partial=True));out=self.execute(p);self.assertEqual(out.outcome,"ABORTED");self.assertEqual(out.effect_state,"PARTIAL_UNKNOWN")

if __name__=="__main__":unittest.main()

import unittest
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding,RuntimeExecutionContractError,RuntimeExecutionReceipt,RuntimeExecutionRequest
Z="0"*64

class RuntimeExecutionContractTests(unittest.TestCase):
    def request(self,**changes):
        values=dict(execution_id="exec:1",admission_digest=Z,requested_effect_digest=Z,runtime_identity_digest=Z,provisioned_executor_digest=Z,mission_id="mission:1",executor_id="executor:1",runtime_instance_id="runtime:1",sandbox_id="sandbox:1",workspace_id="workspace:1",dispatch_id=Z,fencing_token=Z,generation=1,action="WRITE_FILE",resource="workspace/out.txt",payload_digest=Z,payload_size=1,command=())
        values.update(changes);return RuntimeExecutionRequest(**values)
    def receipt(self,**changes):
        values=dict(receipt_id="receipt:1",execution_id="exec:1",admission_digest=Z,request_digest=Z,sandbox_receipt_digest=Z,operation_digest=Z,mission_id="mission:1",executor_id="executor:1",runtime_instance_id="runtime:1",sandbox_id="sandbox:1",workspace_id="workspace:1",dispatch_id=Z,fencing_token=Z,generation=1,action="WRITE_FILE",resource="workspace/out.txt",payload_digest=Z,outcome="SUCCEEDED",effect_state="OBSERVED",effect_digest=Z,observed_events=("event:1",),side_effect_refs=("effect:1",))
        values.update(changes);return RuntimeExecutionReceipt(**values)
    def test_request_digest_is_deterministic(self):
        r=self.request().validate();self.assertEqual(r.digest(),r.digest())
    def test_run_test_requires_exact_command(self):
        self.assertRaises(RuntimeExecutionContractError,self.request(action="RUN_TEST",payload_size=0).validate)
        self.request(action="RUN_TEST",payload_size=0,command=("python","-m","unittest")).validate()
    def test_success_requires_observed_effect(self):
        self.assertRaises(RuntimeExecutionContractError,self.receipt(effect_state="UNKNOWN",side_effect_refs=()).sealed)
    def test_partial_unknown_cannot_be_success(self):
        self.assertRaises(RuntimeExecutionContractError,self.receipt(effect_state="PARTIAL_UNKNOWN").sealed)
        self.receipt(outcome="ABORTED",effect_state="PARTIAL_UNKNOWN").sealed().validate()
    def test_receipt_is_tamper_evident(self):
        r=self.receipt().sealed();bad=RuntimeExecutionReceipt(**{**r.__dict__,"resource":"workspace/other.txt"})
        self.assertRaises(RuntimeExecutionContractError,bad.validate)
    def test_source_trust_binding_is_pinned(self):
        b=RuntimeAdmissionSourceTrustBinding("src","src:1",Z,"anchor",Z).validate();self.assertEqual(b.binding()[0],"src")

if __name__=="__main__":unittest.main()

import unittest
from tools.lion_local_intelligence_runtime import local_assignment_worker_once

class LocalAssignmentWorkerTests(unittest.TestCase):
    def test_worker_claims_executes_dual_and_receipts_without_browser(self):
        calls=[]
        row={"assignment_id":"assignment-1","material_drone_id":"MD025","input_json":"{\"kind\":\"LOCAL_MODEL_INFERENCE\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}],\"max_tokens\":64,\"dual_request_id\":\"dual-11111111111111111111111111111111\"}"}
        def control(op,args):
            calls.append((op,args))
            if op=="local_assignments":return {"assignments":[row]}
            if op=="local_assignment_claim":return dict(row,state="CLAIMED")
            if op=="dual_response":return {"state":"WAITING_SAAS"}
            if op=="local_assignment_receipt":return {"receipt_id":"receipt-1","duplicate":False}
            raise AssertionError(op)
        out=local_assignment_worker_once(control,lambda messages,max_tokens:"LOCAL OK",material_drone_id="MD025")
        self.assertEqual(out["receipt_id"],"receipt-1")
        self.assertEqual([x[0] for x in calls],["local_assignments","local_assignment_claim","dual_response","local_assignment_receipt"])
        receipt=calls[-1][1]
        self.assertEqual(receipt["status"],"PASS")
        self.assertEqual(receipt["result"]["response_text"],"LOCAL OK")
        self.assertEqual(receipt["result"]["authority_effect"],"NONE")

    def test_worker_ignores_assignment_for_other_material_identity(self):
        def control(op,args):
            if op=="local_assignments":return {"assignments":[{"assignment_id":"a","material_drone_id":"MD026","input_json":"{}"}]}
            raise AssertionError(op)
        self.assertIsNone(local_assignment_worker_once(control,lambda *a:"no",material_drone_id="MD025"))

if __name__=="__main__":unittest.main()

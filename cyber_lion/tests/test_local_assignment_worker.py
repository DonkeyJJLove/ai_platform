import unittest

from cyber_lion.mission_control import operator_control
from tools.lion_local_intelligence_runtime import local_assignment_worker_once

class LocalAssignmentWorkerTests(unittest.TestCase):
    def test_worker_claims_executes_dual_and_receipts_without_browser(self):
        calls=[]
        row={"assignment_id":"assignment-1","material_drone_id":"MD025","lease_generation":7,"lease_expires_at":"2099-01-01T00:00:00Z","input_json":"{\"kind\":\"LOCAL_MODEL_INFERENCE\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}],\"max_tokens\":64,\"dual_request_id\":\"dual-11111111111111111111111111111111\"}"}
        def control(op,args):
            calls.append((op,args))
            if op=="local_assignments":return {"assignments":[row]}
            if op=="local_assignment_claim":return dict(row,state="CLAIMED",mission_id="M1",phase_id="P1",logical_drone_id="LD1")
            if op=="model_call_intent":return {"status":"INTENT_DURABLE","model_call_id":args["model_call_id"]}
            if op=="model_call_transition":return {"status":args["state"],"model_call_id":args["model_call_id"]}
            if op=="dual_response":return {"state":"WAITING_SAAS"}
            if op=="local_assignment_receipt":return {"receipt_id":"receipt-1","duplicate":False}
            raise AssertionError(op)
        out=local_assignment_worker_once(control,lambda messages,max_tokens:"LOCAL OK",material_drone_id="MD025")
        self.assertEqual(out["receipt_id"],"receipt-1")
        self.assertEqual([x[0] for x in calls],[
            "local_assignments","local_assignment_claim",
            "model_call_intent","model_call_transition","model_call_transition",
            "dual_response","local_assignment_receipt","model_call_transition",
        ])
        self.assertEqual([x[1].get("state") for x in calls if x[0]=="model_call_transition"],["SEND_ATTEMPT","SEND_CONFIRMED","RESPONSE_RECONCILED"])
        receipt=next(args for op,args in calls if op=="local_assignment_receipt")
        self.assertEqual(receipt["status"],"PASS")
        self.assertEqual(receipt["material_drone_id"],"MD025")
        self.assertEqual(receipt["lease_generation"],7)
        self.assertEqual(receipt["result"]["response_text"],"LOCAL OK")
        self.assertEqual(receipt["result"]["authority_effect"],"NONE")

    def test_expired_local_assignment_lease_blocks_provider_effect(self):
        calls=[];provider=[]
        row={"assignment_id":"expired-1","material_drone_id":"MD025","lease_generation":3,"lease_expires_at":"2000-01-01T00:00:00Z","input_json":"{\"kind\":\"LOCAL_MODEL_INFERENCE\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}]}"}
        def control(op,args):
            calls.append((op,args))
            if op=='local_assignments':return {'assignments':[row]}
            if op=='local_assignment_claim':return dict(row,state='CLAIMED')
            if op=='local_assignment_receipt':return {'receipt_id':'expired-receipt'}
            raise AssertionError(op)
        def model(*a):provider.append(a);return 'MUST NOT RUN'
        out=local_assignment_worker_once(control,model,material_drone_id='MD025')
        self.assertEqual(out['receipt_id'],'expired-receipt')
        self.assertEqual(provider,[])
        self.assertEqual(calls[-1][1]['status'],'FAIL')
        self.assertIn('lease expired',calls[-1][1]['result']['error'])

    def test_worker_ignores_assignment_for_other_material_identity(self):
        def control(op,args):
            if op=="local_assignments":return {"assignments":[{"assignment_id":"a","material_drone_id":"MD026","input_json":"{}"}]}
            raise AssertionError(op)
        self.assertIsNone(local_assignment_worker_once(control,lambda *a:"no",material_drone_id="MD025"))

    def test_assignment_claim_filters_operator_messages_to_explicit_ids(self):
        rows=[
            {'message_id':'old','content':'stale pending'},
            {'message_id':'current','content':'current request'},
        ]
        filtered=operator_control.assignment_messages_for_input(rows,'{"operator_message_ids":["current"]}')
        self.assertEqual([x['message_id'] for x in filtered],['current'])
        self.assertEqual(operator_control.assignment_messages_for_input(rows,'{}'),rows)

    def test_prefetched_assignments_do_not_poll_control_plane_again(self):
        calls=[]
        row={"assignment_id":"assignment-prefetch","material_drone_id":"MD025","lease_generation":2,"lease_expires_at":"2099-01-01T00:00:00Z","input_json":"{\"kind\":\"LOCAL_MODEL_INFERENCE\",\"messages\":[{\"role\":\"user\",\"content\":\"x\"}]}"}
        def control(op,args):
            calls.append(op)
            if op=="local_assignments":raise AssertionError("unexpected duplicate poll")
            if op=="local_assignment_claim":return dict(row,state="CLAIMED",mission_id="M1",phase_id="P1",logical_drone_id="LD1")
            if op=="model_call_intent":return {"status":"INTENT_DURABLE","model_call_id":args["model_call_id"]}
            if op=="model_call_transition":return {"status":args["state"],"model_call_id":args["model_call_id"]}
            if op=="local_assignment_receipt":return {"receipt_id":"receipt-prefetch","duplicate":False}
            raise AssertionError(op)
        out=local_assignment_worker_once(control,lambda messages,max_tokens:"OK",material_drone_id="MD025",pending=[row])
        self.assertEqual(out["receipt_id"],"receipt-prefetch")
        self.assertNotIn("local_assignments",calls)

if __name__=="__main__":unittest.main()

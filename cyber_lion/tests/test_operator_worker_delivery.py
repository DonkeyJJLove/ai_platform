import json
import unittest

from tools.lion_local_intelligence_runtime import local_assignment_worker_once


class OperatorWorkerDeliveryTests(unittest.TestCase):
    def test_operator_context_and_message_enter_next_inference_and_receipt(self):
        calls=[];model_messages=[]
        def control(op,args):
            calls.append((op,args))
            if op=='local_assignments':return {'assignments':[{'assignment_id':'A1','material_drone_id':'MD025'}]}
            if op=='local_assignment_claim':return {
                'assignment_id':'A1','mission_id':'M1','phase_id':'P1','logical_drone_id':'LD1','material_drone_id':'MD025','lease_generation':3,'lease_expires_at':'2099-01-01T00:00:00Z',
                'input_json':json.dumps({'kind':'LOCAL_MODEL_INFERENCE','messages':[{'role':'user','content':'base'}],'max_tokens':64}),
                'operator_context':{'revision':2,'content':{'rule':'prefer evidence A'}},
                'operator_plan':None,
                'operator_messages':[{'message_id':'opmsg-1','target':'drone:MD025','content':'check branch X'}],
            }
            if op=='model_call_intent':return {'status':'INTENT_DURABLE','model_call_id':args['model_call_id']}
            if op=='model_call_transition':return {'status':args['state'],'model_call_id':args['model_call_id']}
            if op=='local_assignment_receipt':return {'status':'PASS','captured':args}
            raise AssertionError(op)
        def model(messages,max_tokens):
            model_messages.extend(messages);return 'ack'
        out=local_assignment_worker_once(control,model,material_drone_id='MD025')
        self.assertEqual(out['status'],'PASS')
        self.assertEqual(model_messages[0]['role'],'system')
        self.assertIn('OPERATOR_PRIMARY',model_messages[0]['content'])
        self.assertIn('prefer evidence A',model_messages[0]['content'])
        self.assertIn('check branch X',model_messages[0]['content'])
        result=out['captured']['result']
        self.assertEqual(result['operator_context_revision'],2)
        self.assertEqual(result['operator_message_ids'],['opmsg-1'])
        self.assertEqual(result['authority_effect'],'NONE')


if __name__=='__main__':unittest.main()

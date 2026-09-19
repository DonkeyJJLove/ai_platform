from __future__ import annotations

import json
import sqlite3
import unittest
from unittest.mock import patch

from cyber_lion.mission_control import model_calls
from tools import lion_local_intelligence_runtime as runtime


class ModelCallLedgerTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.row_factory=sqlite3.Row
        self.counter=0
        model_calls.migrate(self.conn,self.now)

    def tearDown(self):
        self.conn.close()

    def now(self):
        self.counter+=1
        return f'2026-09-19T00:00:{self.counter:02d}Z'

    def intent(self, **overrides):
        value={
            'model_call_id':'modelcall-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            'mission_id':'MISSION-A',
            'phase_id':'PHASE-A',
            'task_id':'TASK-A',
            'assignment_id':'assignment-a',
            'logical_drone_id':'LD01',
            'material_worker_id':'MD025',
            'requested_capability':'LOCAL_MODEL_INFERENCE',
            'provider':'LION_LOCAL_MODEL',
            'model_requested':'gpt-oss-20b-MXFP4',
            'model_declared':None,
            'model_attested':None,
            'transport':'LOCAL',
            'selection_reason':'TEST_SELECTION',
            'candidate_set_digest':'b'*64,
            'context_revision':2,
            'input_digest':'c'*64,
            'downstream_consumer':'GLOBAL_SCHEDULER',
            'authority_effect':'NONE',
        }
        value.update(overrides)
        return value

    def trans(self,state,**overrides):
        value={'state':state,'result_digest':None,'model_declared':None,'model_attested':None,'downstream_consumer':'GLOBAL_SCHEDULER','authority_effect':'NONE'}
        value.update(overrides);return value

    def test_intent_is_idempotent_and_conflicting_reuse_is_denied(self):
        first=model_calls.create_intent(self.conn,self.intent(),self.now)
        second=model_calls.create_intent(self.conn,self.intent(),self.now)
        self.assertEqual(first['intent_digest'],second['intent_digest'])
        self.assertEqual(self.conn.execute('select count(*) from mission_model_calls').fetchone()[0],1)
        with self.assertRaisesRegex(ValueError,'idempotency conflict'):
            model_calls.create_intent(self.conn,self.intent(selection_reason='DIFFERENT'),self.now)

    def test_unknown_send_cannot_transition_back_to_attempt(self):
        model_calls.create_intent(self.conn,self.intent(),self.now)
        model_calls.transition(self.conn,self.intent()['model_call_id'],self.trans('SEND_ATTEMPT'),self.now)
        model_calls.transition(self.conn,self.intent()['model_call_id'],self.trans('SEND_UNKNOWN'),self.now)
        with self.assertRaisesRegex(ValueError,'model call transition'):
            model_calls.transition(self.conn,self.intent()['model_call_id'],self.trans('SEND_ATTEMPT'),self.now)

    def test_success_requires_confirmed_then_reconciled(self):
        mid=self.intent()['model_call_id'];model_calls.create_intent(self.conn,self.intent(),self.now)
        model_calls.transition(self.conn,mid,self.trans('SEND_ATTEMPT'),self.now)
        digest='d'*64
        model_calls.transition(self.conn,mid,self.trans('SEND_CONFIRMED',result_digest=digest,model_declared='gpt-oss-20b-MXFP4'),self.now)
        out=model_calls.transition(self.conn,mid,self.trans('RESPONSE_RECONCILED',result_digest=digest,model_declared='gpt-oss-20b-MXFP4'),self.now)
        self.assertEqual(out['state'],'RESPONSE_RECONCILED')
        self.assertEqual(out['result_digest'],digest)


class LocalWorkerModelCallTests(unittest.TestCase):
    def claimed(self):
        return {
          'assignment_id':'assignment-a','mission_id':'MISSION-A','phase_id':'PHASE-A',
          'logical_drone_id':'LD01','material_drone_id':'MD025','lease_generation':3,
          'lease_expires_at':'2999-01-01T00:00:00Z',
          'input_json':json.dumps({'kind':'LOCAL_MODEL_INFERENCE','messages':[{'role':'user','content':'hello'}],'max_tokens':16,'task_id':'TASK-A'}),
          'operator_context':{'revision':2,'content':{'note':'ctx'}},
          'operator_plan':None,'operator_messages':[]
        }

    def fake_control(self,log):
        claimed=self.claimed()
        def control(op,args):
            log.append((op,dict(args)))
            if op=='local_assignments':return {'assignments':[{'assignment_id':'assignment-a','material_drone_id':'MD025'}]}
            if op=='local_assignment_claim':return dict(claimed)
            if op=='model_call_intent':return {'state':'INTENT_DURABLE',**args}
            if op=='model_call_transition':return {'state':args['state'],**args}
            if op=='local_assignment_receipt':return {'receipt_id':'r1','status':args['status']}
            raise AssertionError(op)
        return control

    def test_worker_persists_intent_before_provider_and_reconciles_after_receipt(self):
        log=[];control=self.fake_control(log)
        def model(messages,max_tokens):
            log.append(('PROVIDER_EFFECT',{'messages':messages,'max_tokens':max_tokens}))
            return 'answer'
        out=runtime.local_assignment_worker_once(control,model)
        ops=[x[0] for x in log]
        self.assertEqual(out['status'],'PASS')
        self.assertLess(ops.index('model_call_intent'),ops.index('PROVIDER_EFFECT'))
        attempts=[x[1]['state'] for x in log if x[0]=='model_call_transition']
        self.assertEqual(attempts,['SEND_ATTEMPT','SEND_CONFIRMED','RESPONSE_RECONCILED'])
        self.assertLess(ops.index('local_assignment_receipt'),len(ops)-1)
        intent=next(x[1] for x in log if x[0]=='model_call_intent')
        self.assertEqual((intent['mission_id'],intent['phase_id'],intent['logical_drone_id'],intent['material_worker_id']),('MISSION-A','PHASE-A','LD01','MD025'))
        self.assertEqual(intent['transport'],'LOCAL')
        self.assertEqual(intent['authority_effect'],'NONE')

    def test_provider_exception_becomes_send_unknown_without_blind_retry(self):
        log=[];control=self.fake_control(log);calls=[]
        def model(messages,max_tokens):
            calls.append(1)
            log.append(('PROVIDER_EFFECT',{}))
            raise TimeoutError('ambiguous provider timeout')
        out=runtime.local_assignment_worker_once(control,model)
        self.assertEqual(len(calls),1)
        states=[x[1]['state'] for x in log if x[0]=='model_call_transition']
        self.assertEqual(states,['SEND_ATTEMPT','SEND_UNKNOWN'])
        self.assertEqual(out['status'],'FAIL')
        receipt=next(x[1] for x in log if x[0]=='local_assignment_receipt')
        self.assertEqual(receipt['result']['model_call_state'],'SEND_UNKNOWN')


if __name__=='__main__':
    unittest.main()

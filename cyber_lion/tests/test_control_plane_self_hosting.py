from __future__ import annotations
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import lion_local_intelligence_runtime as rt


class _OneShotStop:
    def __init__(self): self.done=False
    def is_set(self): return self.done
    def wait(self, _seconds): self.done=True


class SelfHostingControlPlaneTests(unittest.TestCase):
    def test_windows_local_canary_posts_receipt_instead_of_phase_update(self):
        calls=[]
        def control(op,args):
            calls.append((op,args))
            if op=='recent': return {'focus_mission_id':'M1'}
            if op=='process': return {'process':{'current_phase':'LIVE_AUTONOMY_CANARY'},'protocol_messages':[]}
            if op=='post_message': return {'ok':True}
            raise AssertionError(op)
        def modelprov(messages,max_tokens):
            self.assertEqual(max_tokens,64)
            return 'proposal-only local inference response'
        rt.local_canary_loop(control,modelprov,_OneShotStop(),8780,'http://127.0.0.1:8772')
        posted=[a for op,a in calls if op=='post_message']
        self.assertEqual(len(posted),1)
        payload=posted[0]['payload']
        self.assertEqual(payload['event'],'LOCAL_MODEL_CANARY_PASS')
        self.assertEqual(payload['model'],'gpt-oss-20b-MXFP4')
        self.assertEqual(payload['authority_effect'],'NONE')
        self.assertEqual(posted[0]['phase'],'LIVE_AUTONOMY_CANARY')

    def test_windows_terminal_readback_posts_panel_and_model_evidence(self):
        calls=[]
        def control(op,args):
            calls.append((op,args))
            if op=='recent': return {'focus_mission_id':'M1'}
            if op=='process': return {'process':{'current_phase':'READY_FOR_SYSTEM_ACCEPTANCE_TESTS'},'protocol_messages':[]}
            if op=='post_message': return {'ok':True}
            raise AssertionError(op)
        def fake_json(url,**kwargs):
            if url.endswith(':8780/health'): return {'status':'ok','authority_effect':'NONE'}
            if url.endswith(':8772/v1/models'): return {'data':[{'id':'gpt-oss-20b-MXFP4'}]}
            raise AssertionError(url)
        with patch.object(rt,'_json_request',side_effect=fake_json):
            rt.local_canary_loop(control,lambda *_:'unused',_OneShotStop(),8780,'http://127.0.0.1:8772')
        posted=[a for op,a in calls if op=='post_message']
        self.assertEqual(len(posted),1)
        payload=posted[0]['payload']
        self.assertEqual(payload['event'],'WINDOWS_CONTROL_SURFACE_READBACK')
        self.assertEqual(payload['panel_http'],200)
        self.assertEqual(payload['model_http'],200)
        self.assertEqual(payload['model_count'],1)
        self.assertEqual(payload['authority_effect'],'NONE')

    def test_exact_head_gate_requires_real_workflow_names_only(self):
        import importlib,sys
        tools=Path(__file__).resolve().parents[2]/'tools'
        if str(tools) not in sys.path: sys.path.insert(0,str(tools))
        sys.modules['mission_control_compat']=importlib.import_module('lion_mission_control_compat')
        mc=importlib.import_module('lion_mission_control_v3')
        head='a'*40
        runs=[
            {'name':'Bandit Security Scan','status':'completed','conclusion':'success','head_sha':head},
            {'name':'LION R22C Full Symbol Census','status':'completed','conclusion':'success','head_sha':head},
            {'name':'Cyber-Lion Core','status':'completed','conclusion':'success','head_sha':head},
        ]
        green,names=mc._all_required_ci_green({'head':head,'runs':runs})
        self.assertTrue(green)
        self.assertEqual(set(names),{'Bandit Security Scan','LION R22C Full Symbol Census','Cyber-Lion Core'})



if __name__=='__main__': unittest.main()

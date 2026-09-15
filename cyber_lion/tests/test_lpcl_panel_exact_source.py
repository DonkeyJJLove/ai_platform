from __future__ import annotations
import importlib
import unittest

runtime = importlib.import_module('tools.lion_local_intelligence_runtime')


class LpclPanelExactSourceTests(unittest.TestCase):
    def bridge(self):
        bridge = runtime.LpclControlBridge.__new__(runtime.LpclControlBridge)
        bridge.base = 'http://127.0.0.1:8766'
        bridge.broker = None
        return bridge

    def test_register_returns_exact_backend_confirmation(self):
        bridge=self.bridge();source='PROJECT=LION_EVOLUSION\n';digest='a'*64;mid='EXACT-SOURCE-R1'
        bridge.validate=lambda value: {'lpcl_digest':digest,'spec':{'mission_id':mid,'lpcl_digest':digest,'lpcl_text':value}}
        calls=[]
        bridge._post=lambda path,body,timeout=10: (calls.append((path,body)) or {'idempotent':False,'mission':{'mission_id':mid,'spec_digest':digest,'process':{'lpcl_digest':digest}}})
        out=bridge('register_lpcl',{'lpcl_text':source})
        self.assertEqual(calls,[('/api/v3/missions/register-lpcl',{'mission_id':mid,'lpcl_digest':digest,'lpcl_text':source})])
        self.assertEqual(out['registration_confirmation'],{'mission_id':mid,'lpcl_digest':digest,'source_length':len(source),'authority_effect':'NONE'})

    def test_register_fails_closed_on_backend_digest_drift(self):
        bridge=self.bridge();source='PROJECT=LION_EVOLUSION\n';digest='a'*64;mid='EXACT-SOURCE-R1'
        bridge.validate=lambda value: {'lpcl_digest':digest,'spec':{'mission_id':mid,'lpcl_digest':digest,'lpcl_text':value}}
        bridge._post=lambda path,body,timeout=10: {'mission':{'mission_id':mid,'spec_digest':'b'*64,'process':{'lpcl_digest':'b'*64}}}
        with self.assertRaisesRegex(ValueError,'REGISTERED_SOURCE_DRIFT'):
            bridge('register_lpcl',{'lpcl_text':source})

    def test_activation_returns_exact_digest_confirmation_without_source(self):
        bridge=self.bridge();digest='c'*64;mid='EXACT-SOURCE-R1';calls=[]
        bridge._post=lambda path,body,timeout=10: (calls.append((path,body)) or {'mission_id':mid,'state':'RUNNING','runtime_state':'DRIVER_RUNNING'})
        out=bridge('activate_lpcl',{'mission_id':mid,'lpcl_digest':digest})
        self.assertEqual(calls,[('/api/v3/missions/'+mid+'/activate',{'lpcl_digest':digest,'activation_event':'EXPLICIT_UI_ACTIVATION'})])
        self.assertEqual(out['activation_confirmation'],{'mission_id':mid,'lpcl_digest':digest,'authority_effect':'EXPLICIT_USER_ACTIVATION'})
        self.assertNotIn('lpcl_text',calls[0][1])

    def test_activation_rejects_nonhex_digest(self):
        bridge=self.bridge()
        with self.assertRaisesRegex(ValueError,'activation'):
            bridge('activate_lpcl',{'mission_id':'EXACT-SOURCE-R1','lpcl_digest':'x'*64})


    def test_legacy_lpcl_1_1_aliases_remain_accepted_by_authoritative_bridge(self):
        class Broker:
            def call(self, role, op, args):
                self.last=(role,op,args)
                return {'result':{'head':'a'*40,'tree':'b'*40}}
        bridge=self.bridge();bridge.broker=Broker()
        source=(
            'PROJECT=LION_EVOLUSION\n'
            'MODE=AUTONOMOUS_EXECUTE\n'
            'CONTROL_LANGUAGE=LPCL/1.1\n'
            'MISSION_ID=LEGACY-COMPAT-R1\n'
            'MISSION_TITLE=Legacy compatibility\n'
            'MISSION_OBJECTIVE=Preserve legacy intake\n'
            'LOGICAL_DRONES=12\n'
            'MATERIAL_FLEET_TARGET=64\n'
            'PROTOCOLS=LPCL,AUTHORITY,CURRENTNESS,EVIDENCE,VALIDATION,RECEIPT,CONTROL\n'
            'PHASE_01=LEGACY_VERIFY|Legacy verify\n'
        )
        out=bridge.validate(source)
        self.assertTrue(out['valid'])
        self.assertEqual(out['spec']['description'],'Preserve legacy intake')
        self.assertEqual(out['spec']['logical_count'],12)
        self.assertEqual(out['spec']['material_target'],64)
        self.assertEqual(out['parsed']['control_language'],'LPCL/1.1')

    def test_ui_exact_source_state_machine_contract_is_present(self):
        from cyber_lion.app_coordination.local_intelligence_gateway import UI
        self.assertIn("const LPCL_REQUIRED_KEYS=['PROJECT','MODE','CONTROL_LANGUAGE','MISSION_ID','MISSION_TITLE','MISSION_OBJECTIVE','MISSION_DESCRIPTION','LOGICAL_DRONE_COUNT','MATERIAL_DRONE_COUNT','PROTOCOLS']",UI)
        self.assertIn("const LPCL_ENVELOPE_KEYS=['PROJECT','MODE','CONTROL_LANGUAGE','MISSION_ID']",UI)
        self.assertIn("MISSION_DESCRIPTION:['MISSION_DESCRIPTION','MISSION_OBJECTIVE']",UI)
        self.assertIn("LOGICAL_DRONE_COUNT:['LOGICAL_DRONE_COUNT','LOGICAL_DRONES']",UI)
        self.assertIn("MATERIAL_DRONE_COUNT:['MATERIAL_DRONE_COUNT','MATERIAL_FLEET_TARGET']",UI)
        self.assertIn("'LPCL FRAGMENT · MISSING ENVELOPE'",UI)
        self.assertIn("body:JSON.stringify({lpcl_text:snapshot.validated_source})",UI)
        self.assertIn("$('lpclText').addEventListener('input',invalidateLpclSource)",UI)
        self.assertIn("'LPCL INPUT NOT DETECTED'",UI)
        self.assertIn("REGISTERED_SOURCE_DRIFT",UI)
        self.assertIn("ACTIVATION_DIGEST_DRIFT",UI)
        self.assertIn('id="lpclRegisterButton"',UI)
        self.assertIn('id="lpclActivateButton"',UI)
        self.assertNotIn("body:JSON.stringify({lpcl_text:$('lpclText').value})",UI)


if __name__=='__main__':unittest.main()

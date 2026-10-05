"""Adapter-selection regression, using original parser and temporary MC DBs.

Explicit activation and Docker currentness in these tests are fixtures only.
"""
from __future__ import annotations
from hashlib import sha256
import unittest
from unittest.mock import patch
from cyber_lion.mission_control.lpcl_runtime_selection import runtime_selection, require_runtime_selection
from tools.lion_local_intelligence_runtime import LpclControlBridge
from cyber_lion.tests import test_lpcl_rebind_live_currentness as baseline

LPCL = '''RUN=COOPERATIVE-TOPOLOGY-FIXTURE
PROJECT=LION_EVOLUSION
MODE=AUTONOMOUS_EXECUTE
CONTROL_LANGUAGE=LPCL/1.2
MISSION_ID=COOPERATIVE-TOPOLOGY-FIXTURE
MISSION_TITLE=Two logical builders on existing capacity
MISSION_OBJECTIVE=Test an explicit runtime selector without creating containers
MISSION_DESCRIPTION=Source fixture, never live authorization
LOGICAL_DRONE_COUNT=2
MATERIAL_DRONE_COUNT=32
PROTOCOLS=LPCL,ASSIGNMENT,EVIDENCE
PILOT_TARGET_COMPOSE=/not-an-authority/compose.yaml
PHASE_01=BUILD|Build product
PHASE_01_EXECUTION_CLASS=VERIFY
PHASE_01_CAPABILITY_CLASS=COOPERATIVE_ARTIFACT_PRODUCTION
PHASE_01_EFFECT_CEILING=NONE
PHASE_01_BINDING_MODE=DYNAMIC
PHASE_01_ON_MISSING_CAPABILITY=WAIT_AND_DISCOVER
PHASE_01_AUTO_RESUME=TRUE
PHASE_01_VERIFY_BEFORE_MUTATE=TRUE
PHASE_01_CURRENTNESS=LIVE_DOCKER_FLEET
PHASE_01_EVIDENCE=ARTIFACT_READBACK
PHASE_01_COMPLETION_01=ARTIFACT_VERIFIED=PASS
'''

class Broker:
    def call(self,*args):return {'result':{'head':'a'*40,'tree':'b'*40}}

class RuntimeSelectionTests(unittest.TestCase):
    def bridge(self):
        bridge=LpclControlBridge(Broker())
        bridge._get=lambda *args,**kw:{'capabilities':{},'registry_digest':'c'*64}
        return bridge

    def test_missing_runtime_is_distinct_from_syntax_validity(self):
        result=self.bridge().validate(LPCL)
        self.assertTrue(result['valid'])
        self.assertEqual(result['runtime_preflight']['diagnostic'],'LPCL_MATERIAL_RUNTIME_REQUIRED')
        self.assertFalse(result['runtime_preflight']['declaration_supported'])

    def test_two_logical_and_thirty_two_material_are_supported(self):
        selected=runtime_selection({'MATERIAL_RUNTIME':'DOCKER_LOCAL_MODEL'},2,32)
        self.assertTrue(selected['declaration_supported'])
        self.assertFalse(selected['fleet_observed'])
        self.assertEqual(selected['authority_effect'],'NONE')

    def test_adding_explicit_runtime_preserves_exact_source_digest(self):
        source=LPCL+'MATERIAL_RUNTIME=DOCKER_LOCAL_MODEL\n'
        result=self.bridge().validate(source)
        self.assertEqual(result['lpcl_digest'],sha256(source.encode()).hexdigest())
        self.assertEqual(result['spec']['lpcl_text'],source)
        self.assertTrue(result['runtime_preflight']['declaration_supported'])
        self.assertEqual(result['execution_preflight']['mission_readiness'],'WAITING_FOR_CAPABILITIES')

    def test_pilot_hint_does_not_implicitly_select_docker(self):
        value=runtime_selection({'PILOT_TARGET_COMPOSE':'/r24/compose.yaml'},2,32)
        self.assertEqual(value['diagnostic'],'LPCL_MATERIAL_RUNTIME_REQUIRED')

    def test_legacy_cardinalities_preserved(self):
        for count in (12,128):
            self.assertEqual(require_runtime_selection({},count,64),'EPOCH3_COMPATIBILITY')

    def test_unsupported_runtime_is_not_silently_legacy(self):
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED'):
            require_runtime_selection({'MATERIAL_RUNTIME':'TYPO'},12,64)

    def test_docker_wrong_capacity_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'MUST_BE_32'):
            require_runtime_selection({'MATERIAL_RUNTIME':'DOCKER_LOCAL_MODEL'},2,64)

    def test_docker_parent_and_continuation_are_rejected(self):
        for extra in ({'PARENT_MISSION_ID':'old'},{'CONTINUE_EXISTING_EPOCH3_MISSION':'TRUE'},{'CONTINUE_EXISTING_EPOCH3_LINEAGE':'TRUE'}):
            with self.assertRaisesRegex(ValueError,'FRESH_MISSION'):
                require_runtime_selection({'MATERIAL_RUNTIME':'DOCKER_LOCAL_MODEL',**extra},2,32)

    def test_count_types_and_bounds(self):
        for logical,material in ((True,32),(0,32),(513,32),(2,True),(2,-1),(2,4097)):
            with self.assertRaises(ValueError):runtime_selection({},logical,material)

    def test_unknown_future_capacity_remains_unresolved(self):
        value=runtime_selection({},8,16)
        self.assertFalse(value['declaration_supported'])
        self.assertIsNone(value['selected_adapter'])

    def test_runtime_diagnostic_exists_before_any_registration(self):
        bridge=self.bridge()
        bridge._post=lambda *a,**k: (_ for _ in ()).throw(AssertionError('registration must not occur'))
        value=bridge.validate(LPCL)
        self.assertEqual(value['runtime_preflight']['diagnostic'],'LPCL_MATERIAL_RUNTIME_REQUIRED')


class RuntimeBindingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.f=baseline.LpclRebindLiveCurrentnessTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.mc=self.f.mc
        self.bridge=LpclControlBridge(Broker());self.bridge._get=lambda *a,**k:{'capabilities':{},'registry_digest':'c'*64}

    def register(self,text):
        spec=self.bridge.validate(text)['spec']
        self.mc.register_lpcl_mission(spec)
        return spec

    def test_actual_mc_reports_missing_runtime_without_touching_fleet(self):
        spec=self.register(LPCL)
        with patch.object(self.mc,'epoch3_broker',side_effect=AssertionError('wrong fleet must not be read')):
            out=self.mc.activate_lpcl_mission(spec['mission_id'],{'lpcl_digest':spec['lpcl_digest'],'activation_event':'EXPLICIT_UI_ACTIVATION'})
        self.assertIn('LPCL_MATERIAL_RUNTIME_REQUIRED',out['last_error'])
        self.assertEqual(out['runtime_state'],'NOT_STARTED')
        self.assertEqual(out['execution_assignments'],[])

    def test_original_docker_binder_accepts_2_32_without_capacity_rewrite(self):
        spec=self.register(LPCL+'MATERIAL_RUNTIME=DOCKER_LOCAL_MODEL\n')
        workers=[{'material_worker_id':f'MD{i:03d}','pod_name':f'lion-r24-md{i:03d}',
                  'pod_uid':sha256(str(i).encode()).hexdigest(),'ready':1,'model':'gpt-oss-20b-MXFP4'} for i in range(1,33)]
        observed={'digest':'d'*64,'observed_at':self.mc.now(),'workers':workers,'physical_failure_domains':1}
        with patch.object(self.mc,'_docker_local_model_currentness',return_value=observed),patch.object(self.mc,'epoch3_broker',side_effect=AssertionError('legacy fleet not selected')):
            out=self.mc.activate_lpcl_mission(spec['mission_id'],{'lpcl_digest':spec['lpcl_digest'],'activation_event':'EXPLICIT_UI_ACTIVATION'})
        self.assertIsNone(out['last_error'])
        self.assertEqual((out['logical_count'],out['materialized'],out['ready']),(2,32,32))
        with self.mc.connect() as c:
            bound=[tuple(r) for r in c.execute("SELECT logical_drone_id,material_drone_id FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__' ORDER BY logical_drone_id",(spec['mission_id'],))]
        self.assertEqual(bound,[('LD001','MD001'),('LD002','MD002')])
        self.assertEqual(out['runtime_state'],'DOCKER_LOCAL_MODEL_FLEET_BOUND')

if __name__=='__main__':unittest.main()

from pathlib import Path
import unittest

from cyber_lion.app_coordination import saas_handoff_extension as saas_ext

ROOT=Path(__file__).resolve().parents[2]


class Epoch4CommunicationModelControlArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gateway=(ROOT/'cyber_lion/app_coordination/local_intelligence_gateway.py').read_text(encoding='utf-8')
        cls.runtime=(ROOT/'tools/lion_local_intelligence_runtime.py').read_text(encoding='utf-8')
        cls.operator=(ROOT/'cyber_lion/mission_control/operator_control.py').read_text(encoding='utf-8')
        cls.supervisor=(ROOT/'tools/lion_control_plane_supervisor_windows.ps1').read_text(encoding='utf-8')
        cls.mc=(ROOT/'tools/lion_mission_control_v3.py').read_text(encoding='utf-8')
        cls.model_calls=(ROOT/'cyber_lion/mission_control/model_calls.py').read_text(encoding='utf-8')

    def test_one_canonical_operator_message_store(self):
        self.assertIn('CREATE TABLE IF NOT EXISTS operator_messages',self.operator)
        self.assertIn('CREATE TABLE IF NOT EXISTS operator_message_deliveries',self.operator)
        self.assertFalse((ROOT/'cyber_lion/app_coordination/operator_chat_store.py').exists())
        self.assertFalse((ROOT/'cyber_lion/app_coordination/operator_chat_extension.py').exists())

    def test_thread_binding_is_bus_context_not_provider_context(self):
        self.assertIn('CREATE TABLE IF NOT EXISTS thread_bindings',self.runtime)
        self.assertIn("'LION_BUS'",self.runtime)
        self.assertIn("'correlation_id':tid",self.gateway)
        self.assertIn("'SUPERSEDED_BY_LION_BUS'",self.gateway)
        self.assertIn('Wiadomość do LION BUS',self.gateway)

    def test_auto_text_cannot_select_saas_or_dual_provider(self):
        self.assertEqual(saas_ext.ROUTE_CONTEXT.get(),'AUTO')
        self.assertFalse(saas_ext._explicit_saas('wyślij do saas: test'))
        self.assertFalse(saas_ext._dual_saas_local('porównaj local i saas'))
        token=saas_ext.ROUTE_CONTEXT.set('SAAS')
        try:self.assertTrue(saas_ext._explicit_saas('anything'))
        finally:saas_ext.ROUTE_CONTEXT.reset(token)
        token=saas_ext.ROUTE_CONTEXT.set('DUAL')
        try:self.assertTrue(saas_ext._dual_saas_local('anything'))
        finally:saas_ext.ROUTE_CONTEXT.reset(token)

    def test_operator_controls_are_disabled_until_pairing_is_confirmed(self):
        t=self.gateway
        self.assertIn('data-operator-control disabled',t)
        self.assertIn('let operatorSessionPaired=false',t)
        self.assertIn('function setOperatorControlAvailability(enabled)',t)
        self.assertIn('setOperatorControlAvailability(!!session.paired)',t)
        self.assertIn('setOperatorControlAvailability(!!x.paired)',t)
        self.assertIn('setOperatorControlAvailability(false)',t)
        self.assertIn("if(!operatorSessionPaired)throw new Error('Operator session not paired')",t)

    def test_model_calls_are_read_only_diagnostics_in_panel(self):
        for literal in ('MODEL PLANE DIAGNOSTICS','Model Calls','Requested capability','Selection reason','Material worker','Authority'):
            self.assertIn(literal,self.gateway)
        self.assertIn("'model_calls':model_calls",self.gateway)
        self.assertIn("self.control_provider('model_call_list'",self.gateway)

    def test_normal_ready_path_does_not_depend_on_firefox_manager(self):
        self.assertIn('PORT_8790_MUST_BE_ABSENT_IN_NORMAL_READY_PATH',self.supervisor)
        self.assertIn("panel_channel='LION_BUS'",self.supervisor)
        self.assertIn("message_transport='LION_OPERATOR_MESSAGES'",self.supervisor)

    def test_control_plane_has_no_browser_or_model_dependency(self):
        low=self.operator.lower()
        self.assertNotIn('firefox',low)
        self.assertNotIn('chatgpt.com',low)
        self.assertNotIn('/v1/chat/completions',low)
        self.assertIn('control_epoch',low)

    def test_model_call_boundary_is_separate_from_operator_messages(self):
        self.assertIn('mission_model_calls',self.model_calls)
        self.assertIn('model_call_ledger',self.mc)
        self.assertNotIn('mission_model_calls',self.operator)


if __name__=='__main__':
    unittest.main()

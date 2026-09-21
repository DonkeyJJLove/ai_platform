import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

class LpclPanelOperatorBusR1SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui=(ROOT/'cyber_lion/app_coordination/local_intelligence_gateway.py').read_text(encoding='utf-8')
        cls.runtime=(ROOT/'tools/lion_local_intelligence_runtime.py').read_text(encoding='utf-8')
        cls.supervisor=(ROOT/'tools/lion_control_plane_supervisor_windows.ps1').read_text(encoding='utf-8')
        cls.client=(ROOT/'tools/lion_operator_client.py').read_text(encoding='utf-8')

    def test_main_composer_is_shared_bus_not_provider_route(self):
        t=self.ui
        self.assertIn('SHARED OPERATOR MESSAGE PLANE',t)
        self.assertIn('LION BUS · SENTINELX',t)
        self.assertIn("'/api/threads/'+encodeURIComponent(activeThreadId)+'/bus'",t)
        self.assertIn("'SUPERSEDED_BY_LION_BUS'",t)
        self.assertNotIn('<select id="composerRoute"',t)
        self.assertNotIn('Otwórz Firefox Mediator',t)
        self.assertNotIn('id="saasBridgePanel"',t)
        self.assertNotIn('refreshFirefoxMediator',t)
        self.assertNotIn('pollSaas',t)
        self.assertNotIn('127.0.0.1:8790',t)
        self.assertNotIn('LION Local + SaaS Supervisor',t)
        self.assertNotIn('saasBridgeDetail',t)

    def test_thread_binding_and_stable_order_are_persistent(self):
        t=self.runtime
        self.assertIn('CREATE TABLE IF NOT EXISTS thread_bindings',t)
        self.assertIn("'LION_BUS'",t)
        self.assertIn('ORDER BY t.created_at DESC',t)
        self.assertNotIn('ORDER BY updated_at DESC LIMIT 500',t)

    def test_bus_scroll_follows_new_message_start_not_tail(self):
        t=self.ui
        self.assertIn("scrollIntoView({behavior:'smooth',block:'start'})",t)
        self.assertNotIn("scrollIntoView({behavior:'smooth',block:'end'})",t)
        self.assertIn("'data-message-id'",t)
        self.assertIn("startsWith('operator')",t)

    def test_sentinelx_client_can_join_exact_panel_thread(self):
        t=self.client
        self.assertIn("sub.add_parser('thread')",t)
        self.assertIn("x.add_argument('--correlation-id')",t)
        self.assertIn("command['correlation_id']=a.correlation_id",t)

    def test_normal_supervisor_has_node_panel_and_no_browser_dependency(self):
        t=self.supervisor
        for forbidden in ('OPENAI','8768','DirectSupervisor','Ensure-FirefoxMediator','CHATGPT_FIREFOX_PROJECT_MEDIATED','Observe-OptionalFirefoxTransport','lion_local_intelligence_runtime.py'):
            self.assertNotIn(forbidden,t)
        self.assertIn("node_panel\\src\\server.js",t)
        self.assertIn("panel_runtime='NODE_EXPRESS_R18'",t)
        self.assertIn("browser_automation='DISABLED_BY_POLICY'",t)
        self.assertIn("browser_relay_active=$false",t)
        self.assertIn("message_transport='LION_OPERATOR_MESSAGES'",t)
        self.assertIn("control_transport='SENTINELX_OPERATOR_CONTROL'",t)
        self.assertIn("panel_channel='LION_BUS'",t)
        self.assertNotIn('PORT_8790_MUST_BE_ABSENT_IN_NORMAL_READY_PATH',t)
        self.assertIn("$OperatorControlUrl = 'http://127.0.0.1:8767'",t)

    def test_browser_transport_is_not_reachable_from_current_supervisor(self):
        t=self.supervisor
        self.assertNotIn('Process-For-Port 8790',t)
        self.assertNotIn("firefox-mediator-app",t)
        self.assertNotIn(r"mediator\.js",t)
        self.assertNotIn("Stop-Process -Name firefox",t)
        self.assertNotIn("Retire-LionBrowserPath",t)
        self.assertIn("browser_automation='DISABLED_BY_POLICY'",t)

if __name__=='__main__':unittest.main()

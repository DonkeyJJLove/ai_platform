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

    def test_normal_supervisor_has_no_provider_or_browser_dependency(self):
        t=self.supervisor
        for forbidden in ('OPENAI','8768','DirectSupervisor','Ensure-FirefoxMediator','CHATGPT_FIREFOX_PROJECT_MEDIATED'):
            self.assertNotIn(forbidden,t)
        self.assertIn("message_transport='LION_OPERATOR_MESSAGES'",t)
        self.assertIn("control_transport='SENTINELX_OPERATOR_CONTROL'",t)
        self.assertIn("panel_channel='LION_BUS'",t)
        self.assertIn("if (Listener 8790) { throw 'PORT_8790_MUST_BE_ABSENT_IN_NORMAL_READY_PATH' }",t)
        self.assertIn("--operator-panel-proxy-key-file",t)
        self.assertIn("--operator-pairing-key-file",t)
        self.assertIn("OPERATOR_PAIRING_KEY_MISSING",t)
        self.assertIn("$OperatorControlUrl = 'http://127.0.0.1:8767'",t)

    def test_browser_retirement_is_scoped_to_lion_legacy_processes(self):
        t=self.supervisor
        self.assertIn("open_session_mediator\\.ps1",t)
        self.assertIn("firefox-mediator-app",t)
        self.assertIn("mediator\\.js",t)
        self.assertNotIn("Stop-Process -Name firefox",t)

if __name__=='__main__':unittest.main()

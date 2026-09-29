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

    def test_main_composer_is_model_chat_and_protocol_bus_is_separate(self):
        t=self.ui
        self.assertIn('PROTOCOL COMMUNICATION PLANE',t)
        self.assertIn('LION BUS · PROTOKÓŁ ROJU',t)
        self.assertIn("cmcPost('/api/conversations/'+encodeURIComponent(id)+'/chat'",t)
        self.assertIn("fetch('/api/missions/'+encodeURIComponent(mid)+'/process'",t)
        self.assertIn('PROTOCOL ≠ MODEL CHAT',t)
        self.assertNotIn("'/api/threads/'+encodeURIComponent(activeThreadId)+'/bus'",t)
        self.assertIn('id="modelRoute"',t)
        self.assertIn('MODEL CHAT',t)
        self.assertNotIn("'SUPERSEDED_BY_LION_BUS'",t)
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
        self.assertNotIn('PORT_8790_MUST_BE_ABSENT_IN_NORMAL_READY_PATH',t)
        self.assertIn('Observe-OptionalFirefoxTransport',t)
        self.assertIn('optional_model_transport_8790=$FirefoxTransportActive',t)
        self.assertIn("--operator-panel-proxy-key-file",t)
        self.assertNotIn("--operator-pairing-key-file",t)
        self.assertNotIn("OPERATOR_PAIRING_KEY_MISSING",t)
        self.assertIn("$OperatorControlUrl = 'http://127.0.0.1:8767'",t)

    def test_operator_pairing_uses_ephemeral_gateway_challenge_without_browser_secret(self):
        self.assertIn("/v1/session/pair/challenge",self.runtime)
        self.assertIn("'challenge_id':challenge_id,'pairing_code':code",self.runtime)
        self.assertIn("body:'{}'",self.ui)
        self.assertIn("PAIRING · lokalna obecność operatora",self.ui)
        self.assertNotIn('id="operatorPairing"',self.ui)
        self.assertIn("Aktywuj sterowanie operatorem",self.ui)
        self.assertIn("operator-panel-proxy.dpapi",self.supervisor)
        self.assertNotIn("--operator-pairing-key-file",self.supervisor)
        self.assertNotIn("OPERATOR_PAIRING_KEY_MISSING",self.supervisor)

    def test_optional_browser_transport_is_observed_not_managed(self):
        t=self.supervisor
        self.assertIn('Process-For-Port 8790',t)
        self.assertIn("firefox-mediator-app",t)
        self.assertIn(r"mediator\.js",t)
        self.assertNotIn("Stop-Process -Name firefox",t)
        self.assertNotIn("Stop-Process -Id $old.ProcessId",t)
        self.assertNotIn("Retire-LionBrowserPath",t)

if __name__=='__main__':unittest.main()

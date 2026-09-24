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

    def test_panel_uses_contextual_mission_binding_not_raw_target_entry(self):
        t=self.ui
        self.assertNotIn('id="busTarget"',t)
        self.assertIn('id="bindingHint"',t)
        self.assertIn('Powiąż z wybraną misją',t)
        self.assertIn("const target='mission:'+mid",t)
        self.assertIn('Przepiąć ten wątek z misji',t)

    def test_operator_pairing_is_local_otp_handshake_without_renderer_secret_entry(self):
        t=self.ui
        self.assertNotIn('id="operatorPairing"',t)
        self.assertIn('Aktywuj sterowanie operatorem',t)
        self.assertIn("body:'{}'",t)
        self.assertIn("PAIRING · lokalny OTP",t)

    def test_thread_rename_is_inline_and_has_http_readback(self):
        t=self.ui
        self.assertNotIn("prompt('Nowa nazwa wątku:",t)
        self.assertIn('data-rename-input',t)
        self.assertIn('data-rename-save',t)
        self.assertIn('saveRenameThread',t)
        self.assertIn("if(!r.ok)throw new Error",t)

    def test_thread_history_uses_correlation_projection_across_mission_rebinds(self):
        t=self.ui
        self.assertIn("self._operator('thread'",t)
        self.assertIn("'correlation_id':tid",t)
        self.assertIn("'thread_mission_ids'",t)
        self.assertIn("'suppressed_response_ids'",t)
        self.assertNotIn("messages=[m for m in (state.get('messages') or []) if m.get('correlation_id')==tid",t)

    def test_conversation_state_overrides_raw_fanout_state_in_ui(self):
        t=self.ui
        self.assertIn('m.conversation_state||m.state',t)

    def test_delivery_observability_is_aggregated_not_inlined_per_recipient(self):
        t=self.ui
        self.assertIn('deliverySummary',t)
        self.assertIn("mDeliveries.length+' odbiorca'",t)
        self.assertIn('<summary>Delivery</summary>',t)
        self.assertNotIn("map(d=>d.recipient+':'+d.delivery_state).join(' · ')",t)

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
        self.assertIn("--operator-pairing-key-file",t)
        self.assertIn("OPERATOR_PAIRING_KEY_MISSING",t)
        self.assertIn("$OperatorControlUrl = 'http://127.0.0.1:8767'",t)

    def test_optional_browser_transport_is_observed_not_managed(self):
        t=self.supervisor
        self.assertIn('Process-For-Port 8790',t)
        self.assertIn("firefox-mediator-app",t)
        self.assertIn(r"mediator\.js",t)
        self.assertNotIn("Stop-Process -Name firefox",t)
        self.assertNotIn("Stop-Process -Id $old.ProcessId",t)
        self.assertNotIn("Retire-LionBrowserPath",t)

if __name__=='__main__':unittest.main()

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tools' / 'lion_control_plane_supervisor_windows.ps1'


class WindowsControlPlaneSupervisorSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text(encoding='utf-8')

    def test_supervisor_owns_manager_not_always_on_browser(self):
        t = self.text
        self.assertIn("$FirefoxMediatorUrl = 'http://127.0.0.1:8790/status'", t)
        self.assertIn('function Ensure-FirefoxMediatorManager', t)
        self.assertIn("$FirefoxMediatorNode = 'C:\\Program Files\\nodejs\\node.exe'", t)
        self.assertIn("'mediator\\.js'", t)
        self.assertNotIn('$FirefoxMediatorScript =', t)
        self.assertNotIn('FIREFOX_MEDIATOR_NOT_READY', t)

    def test_disabled_relay_is_a_valid_supervised_state(self):
        t = self.text
        self.assertIn('firefox_mediator_manager=$true', t)
        self.assertIn('firefox_mediator_state=$mediatorState', t)
        self.assertIn('browser_relay_active=$browserRelayActive', t)
        self.assertIn("$browserRelayActive=$mediatorState -in @('STARTING','READY','DEGRADED','LOGIN_REQUIRED','PROJECT_BINDING_REQUIRED')", t)
        self.assertNotIn("$mediatorState -eq 'READY'", t)

    def test_legacy_open_session_auto_opener_is_retired(self):
        t = self.text
        self.assertIn('function Stop-LegacyFirefoxMediators', t)
        self.assertIn("-match 'open_session_mediator\\.ps1'", t)
        self.assertIn('Stop-Process -Id $old.ProcessId -Force', t)
        self.assertIn('FIREFOX_LEGACY_AUTO_OPENER_STOP', t)
        ensure = t.index('function Ensure-FirefoxMediatorManager')
        call = t.index('Stop-LegacyFirefoxMediators', ensure)
        port = t.index('$p=Process-For-Port 8790', ensure)
        self.assertLess(call, port)

    def test_8780_is_bound_to_authenticated_operator_proxy_without_pairing_secret_in_process_args(self):
        t = self.text
        self.assertIn("$OperatorControlUrl = 'http://127.0.0.1:8767'", t)
        self.assertIn("[string]$OperatorPanelProxyKey = 'C:\\Users\\d2j3\\AppData\\Local\\LION\\secrets\\operator-panel-proxy.key'", t)
        self.assertIn("'--operator-control-url',$OperatorControlUrl", t)
        self.assertIn("'--operator-panel-proxy-key-file',$OperatorPanelProxyKey", t)
        self.assertIn("throw 'OPERATOR_PANEL_PROXY_KEY_MISSING'", t)
        self.assertIn("throw 'PORT_8780_OPERATOR_BINDING_MISSING'", t)
        self.assertNotIn('--operator-pairing-key-file', t)
        self.assertNotIn('operator-pairing.key', t)

    def test_operator_gateway_health_is_observed_not_assumed(self):
        t = self.text
        self.assertIn('function Test-OperatorControl', t)
        self.assertIn("$OperatorControlUrl + '/v1/participants'", t)
        self.assertIn("return [int]$_.Exception.Response.StatusCode -eq 403", t)
        self.assertIn("throw 'OPERATOR_CONTROL_8767_UNAVAILABLE'", t)
        self.assertIn('$operatorControl=[bool](Test-OperatorControl)', t)
        self.assertIn('operator_control_8767=$operatorControl', t)
        self.assertNotIn('operator_control_8767=$true', t)

    def test_panel_health_precedes_optional_browser_manager_in_one_pass(self):
        t = self.text
        start = t.index('function One-Pass')
        block = t[start:t.index("if ($Once)", start)]
        self.assertLess(block.index('$panelPid=Ensure-Panel'), block.index('$firefoxMediatorPid=Ensure-FirefoxMediatorManager'))


if __name__ == '__main__':
    unittest.main()

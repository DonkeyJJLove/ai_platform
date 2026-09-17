from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'tools'/'lion_control_plane_supervisor_windows.ps1'
class WindowsControlPlaneSupervisorSourceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.text=SOURCE.read_text(encoding='utf-8')
 def test_normal_ready_path_requires_direct_provider_not_browser_manager(self):
  t=self.text
  self.assertIn("$DirectSupervisorUrl = 'http://127.0.0.1:8768/status'",t)
  self.assertIn('function Test-DirectSupervisorReady',t)
  self.assertIn("$state.state -eq 'READY'",t);self.assertIn("$state.credential_state -eq 'PRESENT'",t)
  self.assertIn("$state.inference_transport -eq 'OPENAI_RESPONSES_API_MEDIATED'",t)
  self.assertIn("throw 'DIRECT_SUPERVISOR_8768_NOT_READY'",t)
  self.assertNotIn('function Ensure-FirefoxMediatorManager',t)
  self.assertNotIn('$FirefoxMediatorUrl',t)
  self.assertNotIn('FIREFOX_MEDIATOR_MANAGER_START',t)
 def test_lion_owned_legacy_browser_path_is_retired_and_8790_must_be_absent(self):
  t=self.text
  self.assertIn('function Retire-LionBrowserPath',t)
  self.assertIn("-match 'open_session_mediator\\.ps1'",t)
  self.assertIn("-match 'firefox-mediator-app'",t);self.assertIn("-match 'mediator\\.js'",t)
  self.assertIn('Stop-Process -Id $old.ProcessId -Force',t)
  self.assertIn("throw 'PORT_8790_MUST_BE_ABSENT_IN_NORMAL_READY_PATH'",t)
  self.assertIn('legacy_browser_8790=$false',t);self.assertIn('browser_relay_active=$false',t)
 def test_8780_is_bound_to_authenticated_operator_proxy(self):
  t=self.text
  self.assertIn("$OperatorControlUrl = 'http://127.0.0.1:8767'",t)
  self.assertIn("'--operator-control-url',$OperatorControlUrl",t)
  self.assertIn("'--operator-panel-proxy-key-file',$OperatorPanelProxyKey",t)
  self.assertIn("throw 'OPERATOR_PANEL_PROXY_KEY_MISSING'",t)
  self.assertIn("throw 'PORT_8780_OPERATOR_BINDING_MISSING'",t)
  self.assertNotIn('--operator-pairing-key-file',t)
 def test_operator_gateway_health_is_observed_not_assumed(self):
  t=self.text
  self.assertIn('function Test-OperatorControl',t);self.assertIn("$OperatorControlUrl + '/v1/participants'",t)
  self.assertIn("return [int]$_.Exception.Response.StatusCode -eq 403",t)
  self.assertIn("throw 'OPERATOR_CONTROL_8767_UNAVAILABLE'",t)
  self.assertIn('operator_control_8767=$operatorControl',t)
 def test_one_pass_retires_browser_then_requires_8767_and_8768_before_panel(self):
  t=self.text;start=t.index('function One-Pass');block=t[start:t.index('if ($Once)',start)]
  self.assertLess(block.index('Retire-LionBrowserPath'),block.index('$panelPid=Ensure-Panel'))
  self.assertLess(block.index('Test-OperatorControl'),block.index('$panelPid=Ensure-Panel'))
  self.assertLess(block.index('Test-DirectSupervisorReady'),block.index('$panelPid=Ensure-Panel'))
  self.assertNotIn('Ensure-FirefoxMediatorManager',block)
  self.assertIn('browser8790=ABSENT',block)

class LegacyBrowserFallbackControllerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.text=(ROOT/'tools'/'lion_legacy_browser_fallback_windows.ps1').read_text(encoding='utf-8')
 def test_manager_is_manual_and_starts_disabled(self):
  t=self.text;self.assertIn("[ValidateSet('ON','OFF','STATUS')]",t);self.assertIn("$Action -eq 'ON'",t);self.assertIn("$s.state -eq 'DISABLED'",t);self.assertNotIn('/control/relay/on',t);self.assertNotIn('firefox.exe',t)
 def test_off_targets_only_exact_8790_node_manager(self):
  t=self.text;self.assertIn("$p.Name -ne 'node.exe'",t);self.assertIn("-notmatch 'firefox-mediator-app'",t);self.assertIn("-notmatch 'mediator\\.js'",t);self.assertIn("throw 'PORT_8790_FOREIGN_PROCESS'",t);self.assertIn("/control/relay/off",t)

if __name__=='__main__':unittest.main()

import unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_legacy_wrapper_preserves_cli_and_uses_generic_core(self):
  r=Path(__file__).resolve().parents[2];x=(r/'tools/vkt_r3_mission_control.py').read_text();self.assertIn('cyber_lion.mission_control',x);self.assertIn("default='127.0.0.1'",x)
 def test_service_user_and_history_import(self):
  r=Path(__file__).resolve().parents[2];u=(r/'deploy/mission-control/lion-mission-control.service').read_text();t=(r/'tools/lion_mission_control.py').read_text();self.assertIn('User=sentinelx',u);self.assertIn('NoNewPrivileges=yes',u);self.assertIn('import_known',t)
if __name__=='__main__':unittest.main()

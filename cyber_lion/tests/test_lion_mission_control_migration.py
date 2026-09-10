import unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_legacy_wrapper(self):
  r=Path(__file__).resolve().parents[2];x=(r/'tools/vkt_r3_mission_control.py').read_text();self.assertIn('lion_mission_control',x)
 def test_service_user(self):
  r=Path(__file__).resolve().parents[2];u=(r/'deploy/mission-control/lion-mission-control.service').read_text();self.assertIn('User=sentinelx',u);self.assertIn('NoNewPrivileges=yes',u)
if __name__=='__main__':unittest.main()

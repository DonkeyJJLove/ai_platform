import unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_generic_endpoints(self):
  s=(Path(__file__).resolve().parents[2]/'cyber_lion/mission_control/server.py').read_text()
  for x in ('/api/summary','/api/adapters','/api/runs','/api/export','/api/export/','/health','/ws'):self.assertIn(x,s)
 def test_event_socket_is_materialized(self):
  s=(Path(__file__).resolve().parents[2]/'tools/lion_mission_control.py').read_text();self.assertIn('EventSocket',s);self.assertIn('/run/lion-mission-control/events.sock',s)
if __name__=='__main__':unittest.main()

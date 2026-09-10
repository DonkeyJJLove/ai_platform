import unittest
from pathlib import Path
class T(unittest.TestCase):
 def test_generic_endpoints(self):
  s=(Path(__file__).resolve().parents[2]/'cyber_lion/mission_control/server.py').read_text()
  for x in ('/api/summary','/api/adapters','/api/runs','/api/export','/health','/ws'):self.assertIn(x,s)
if __name__=='__main__':unittest.main()

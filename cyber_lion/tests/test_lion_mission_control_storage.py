import tempfile,unittest
from pathlib import Path
from cyber_lion.mission_control.storage import Store
class T(unittest.TestCase):
 def test_roundtrip(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(str(Path(d)/'x.db'));s.upsert_run({'run_id':'r','status':'PASS'});self.assertEqual(s.run('r')['status'],'PASS')
if __name__=='__main__':unittest.main()

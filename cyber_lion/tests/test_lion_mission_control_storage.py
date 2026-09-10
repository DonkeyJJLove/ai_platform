import tempfile,unittest
from pathlib import Path
from cyber_lion.mission_control.storage import Store
class T(unittest.TestCase):
 def test_roundtrip_and_indexes(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(str(Path(d)/'x.db'));s.index_run({'run_id':'r','status':'PASS','metrics':{'n':1},'participants':[{'id':'p'}],'artifacts':[{'path':'/x','sha256':'a'}],'receipts':[{'path':'/q','sha256':'b'}]});self.assertEqual(s.run('r')['status'],'PASS');self.assertEqual(s.metrics('r')['n'],1);self.assertEqual(len(s.artifacts('r')),1);self.assertEqual(len(s.export_run('r')['receipts']),1)
if __name__=='__main__':unittest.main()

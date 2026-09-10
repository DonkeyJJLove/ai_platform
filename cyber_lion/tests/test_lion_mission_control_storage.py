import tempfile, time, unittest
from pathlib import Path

from cyber_lion.mission_control.storage import Store


class StorageTests(unittest.TestCase):
    def test_run_event_metric_artifact_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'mc.db')
            s.upsert_run({'run_id':'r1','status':'RUNNING','verification_status':'OBSERVED','adapter_type':'X'})
            ev={'event_id':'e1','run_id':'r1','timestamp':time.time(),'event_type':'RUN_STARTED'}
            self.assertTrue(s.append_event(ev)); self.assertFalse(s.append_event(ev))
            s.add_metric('r1','tests_passed',297)
            s.add_participant('r1','worker',{'count':1})
            s.add_artifact('r1',{'artifact_id':'a1','path':'/x','sha256':'a'*64,'size':1,'evidence_class':'ARTIFACT_HASH'})
            s.add_receipt('r1',{'receipt_id':'rc1','path':'/x','sha256':'b'*64,'operation':'READ','status':'PASS','timestamp':1})
            out=s.export_run('r1')
            self.assertEqual(out['metrics']['tests_passed'],297)
            self.assertEqual(len(out['events']),1); self.assertEqual(len(out['artifacts']),1); self.assertEqual(len(out['receipts']),1)

if __name__=='__main__': unittest.main()

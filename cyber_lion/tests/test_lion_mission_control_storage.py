import tempfile, time, unittest
from pathlib import Path

from cyber_lion.mission_control.events import EventSocketServer
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

    def test_lifecycle_event_preserves_adapter_runtime_proof(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'mc.db')
            s.upsert_run({
                'run_id':'oss-test','status':'PASS','verification_status':'VERIFIED','adapter_type':'OSS_REPOSITORY_TEST',
                'source':{'repository':'DonkeyJJLove/ai_platform','head':'h','tree':'t'},
                'target':{'repository':'pallets/itsdangerous','commit':'c','cloned_head':'c'},
                'authority':{'class':'BOUNDED_PRIVILEGED_ADMISSION','mission_control':'READ_ONLY'},
            })
            server=object.__new__(EventSocketServer); server.store=s
            server._project_run({
                'event_id':'cleanup','run_id':'oss-test','timestamp':time.time(),'event_type':'CLEANUP_COMPLETED',
                'process_language':'LPCL-1_0','process_class':'AUTONOMOUS_LOCAL_K3S_OSS_REPOSITORY_TEST',
                'adapter_type':'OSS_REPOSITORY_TEST','host':'LION-AUTH-LAB','runtime':'K3S','phase':'CLEANUP_COMPLETE','status':'CLEANED',
                'source':{'repository':'DonkeyJJLove/ai_platform'},
                'target':{'repository':'pallets/itsdangerous','commit':'c'},
                'authority':{'mission_control':'READ_ONLY'},
                'payload':{'status':'CLEANED','verification_status':'VERIFIED','runtime_status':'ABSENT'},
            })
            run=s.get_run('oss-test')
            self.assertEqual(run['target']['cloned_head'],'c')
            self.assertEqual(run['source']['head'],'h')
            self.assertEqual(run['authority']['class'],'BOUNDED_PRIVILEGED_ADMISSION')
            self.assertEqual(run['status'],'CLEANED')
            self.assertEqual(run['verification_status'],'VERIFIED')

if __name__=='__main__': unittest.main()

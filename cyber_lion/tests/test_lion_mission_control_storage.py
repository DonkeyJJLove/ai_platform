import tempfile, time, unittest
from pathlib import Path

from cyber_lion.mission_control.events import EventSocketServer
from cyber_lion.mission_control.reconciliation import Reconciler
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

    def test_partial_snapshot_does_not_erase_non_null_nested_runtime_proof(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'mc.db')
            s.upsert_run({
                'run_id':'oss-test','status':'PASS','verification_status':'VERIFIED','adapter_type':'OSS_REPOSITORY_TEST',
                'target':{'commit':'c','cloned_head':'c'},
                'workload':{'kind':'KubernetesJob','pod_uid':'pod-1','image_ids':{'pytest':'img'}},
                'metrics':{'pytest_exit_code':0,'pytest_summary':'297 passed','clone_exit_code':0},
                'evidence':{'image_ids':{'pytest':'img'},'job_status':{'succeeded':1}},
            })
            s.upsert_run({
                'run_id':'oss-test','status':'RUNNING','verification_status':'OBSERVED','adapter_type':'OSS_REPOSITORY_TEST',
                'target':{'commit':'c','cloned_head':None},
                'workload':{'kind':'KubernetesJob','pod_uid':None,'image_ids':{}},
                'metrics':{'pytest_exit_code':None,'pytest_summary':None,'clone_exit_code':None},
                'evidence':{'image_ids':{},'job_status':{}},
            })
            run=s.get_run('oss-test')
            self.assertEqual(run['target']['cloned_head'],'c')
            self.assertEqual(run['workload']['pod_uid'],'pod-1')
            self.assertEqual(run['metrics']['pytest_exit_code'],0)
            self.assertEqual(run['metrics']['pytest_summary'],'297 passed')
            self.assertEqual(run['evidence']['image_ids']['pytest'],'img')

    def test_adapter_channel_message_is_validated_persisted_and_deduplicated(self):
        class Adapter:
            adapter_id="VKT_R3"
            def poll(self):
                event={
                    "schema_version":"lion.observation-event/v1","event_id":"channel-1","run_id":"fleet","timestamp":1.0,
                    "event_type":"CHANNEL_MESSAGE","process_language":"LPCL-1_0","process_class":"VKT_R3_384_DRONE_TEST",
                    "adapter_type":"VKT_R3","host":"LION-AUTH-LAB","runtime":"K3S","phase":"P1","status":"RUNNING",
                    "payload":{"message_id":"m1","from_fleet":"TIGER","to_fleet":"SPECTRA","from_drone_id":"1","type":"RELATION"},
                }
                return [{"run_id":"fleet","status":"RUNNING","verification_status":"OBSERVED","adapter_type":"VKT_R3","_observation_events":[event]}]
        class Registry:
            def all(self): return [Adapter()]
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/"mc.db")
            r=Reconciler(s,Registry())
            r.poll_once(); r.poll_once()
            events=s.events("fleet")
            self.assertEqual(len(events),1)
            self.assertEqual(events[0]["event_type"],"CHANNEL_MESSAGE")
            self.assertEqual(events[0]["payload"]["from_fleet"],"TIGER")

    def test_late_adapter_snapshot_cannot_regress_cleaned_verified_run(self):
        class Adapter:
            adapter_id='OSS_REPOSITORY_TEST'
            def poll(self):
                return [{
                    'run_id':'oss-test','status':'RUNNING','verification_status':'OBSERVED','adapter_type':self.adapter_id,
                    'target':{'commit':'c','cloned_head':None},
                    'workload':{'pod_uid':None,'image_ids':{}},
                    'metrics':{'pytest_exit_code':None,'pytest_summary':None},
                    'evidence':{'image_ids':{},'job_status':{}},
                }]
        class Registry:
            def __init__(self, adapter): self.adapter=adapter
            def all(self): return [self.adapter]
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'mc.db')
            s.upsert_run({
                'run_id':'oss-test','status':'CLEANED','verification_status':'VERIFIED','adapter_type':'OSS_REPOSITORY_TEST','phase':'CLEANUP_COMPLETE',
                'target':{'commit':'c','cloned_head':'c'},'workload':{'pod_uid':'pod-1'},
                'metrics':{'pytest_exit_code':0,'pytest_summary':'297 passed'},'cleanup':{'status':'CLEANED'},
            })
            Reconciler(s,Registry(Adapter())).poll_once()
            run=s.get_run('oss-test')
            self.assertEqual(run['status'],'CLEANED')
            self.assertEqual(run['verification_status'],'VERIFIED')
            self.assertEqual(run['phase'],'CLEANUP_COMPLETE')
            self.assertEqual(run['target']['cloned_head'],'c')
            self.assertEqual(run['workload']['pod_uid'],'pod-1')
            self.assertEqual(run['metrics']['pytest_exit_code'],0)
            self.assertEqual(run['metrics']['pytest_summary'],'297 passed')

if __name__=='__main__': unittest.main()

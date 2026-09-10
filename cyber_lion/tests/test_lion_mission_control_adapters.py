import unittest

from cyber_lion.mission_control.adapters.oss_repository_test import OssRepositoryTestAdapter
from cyber_lion.mission_control.adapters.vkt_r3 import VktR3Adapter
from cyber_lion.mission_control.adapters.lpcl_event_stream import LpclEventStreamAdapter


class AdapterTests(unittest.TestCase):
    def test_oss_pass_projects_to_verified_generic_run(self):
        a=OssRepositoryTestAdapter('a'*40,'b'*40)
        a._read=lambda:{'status':'PASS','namespace':'oss-test-itsdangerous','job':'itsdangerous-pytest','vendor_requests':0,'pytest_summary':'297 passed in 0.48s','clone_log':'CLONED_HEAD='+a.COMMIT,'pods':[{'uid':'u1','states':[{'name':'git-clone','exit_code':0,'restart_count':0,'image_id':'docker.io/alpine/git@sha256:'+'a'*64},{'name':'pytest','exit_code':0,'restart_count':0,'image_id':'docker.io/library/python@sha256:'+'b'*64}]}],'job_status':{'succeeded':1,'failed':0}}
        run=a.poll()[0]
        self.assertEqual(run['status'],'PASS'); self.assertEqual(run['verification_status'],'VERIFIED')
        self.assertEqual(run['metrics']['pytest_exit_code'],0); self.assertEqual(run['target']['cloned_head'],a.COMMIT)

    def test_vkt_is_adapter_specific(self):
        a=VktR3Adapter('a'*40,'b'*40)
        a._read=lambda:{'materialized':384,'ready':384,'unique_uid_count':384,'restart_count_total':0,'vendor_requests':0,'pod_uid_set_sha256':'c'*64,'router_state':{'mission':{'completed':True,'phase':'COMPLETE'},'fresh_count':384,'cases_seen':36,'cases_proven':36,'messages_total':768,'ack_rate':1.0}}
        run=a.poll()[0]
        self.assertEqual(run['adapter_type'],'VKT_R3'); self.assertEqual(run['metrics']['pods'],384)

    def test_registry_has_generic_event_adapter(self):
        self.assertEqual(LpclEventStreamAdapter().adapter_id,'LPCL_EVENT_STREAM')

if __name__=='__main__': unittest.main()

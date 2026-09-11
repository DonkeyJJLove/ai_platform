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
        a._read=lambda:{'materialized':384,'ready':384,'unique_uid_count':384,'restart_count_total':0,'vendor_requests':0,'pod_uid_set_sha256':'c'*64,'by_fleet':{'TIGER':128,'SPECTRA':128,'LION':128},'router_state':{'mission':{'completed':True,'phase':'COMPLETE'},'fresh_count':384,'fresh_by_fleet':{'TIGER':128,'SPECTRA':128,'LION':128},'cases_seen':36,'cases_proven':36,'messages_total':768,'ack_rate':1.0,'messages':[{'message_id':'m1','timestamp':1.0,'from_fleet':'TIGER','from_drone_id':'1','from_pod_uid':'u1','to_fleet':'SPECTRA','case_id':'c1','phase':'TIGER_RELATION_ANALYSIS','type':'RELATION','payload_digest':'d'*64,'correlation_id':'e'*64,'parent_message_id':None,'evidence_class':'LOCAL_SYNTHETIC','vendor_requests':0}]}}
        run=a.poll()[0]
        self.assertEqual(run['adapter_type'],'VKT_R3'); self.assertEqual(run['metrics']['pods'],384)
        self.assertEqual(run['metrics']['fleet_organizations']['TIGER'],128); self.assertEqual(run['metrics']['active_by_organization']['LION'],128)
        self.assertEqual(run['_observation_events'][0]['event_type'],'CHANNEL_MESSAGE'); self.assertEqual(run['_observation_events'][0]['payload']['to_fleet'],'SPECTRA')

    def test_registry_has_generic_event_adapter(self):
        self.assertEqual(LpclEventStreamAdapter().adapter_id,'LPCL_EVENT_STREAM')

    def test_real_provider_structured_counts_and_pod_identities(self):
        a = VktR3Adapter('a'*40, 'b'*40)
        a._read = lambda: {
            'materialized': 1, 'by_fleet': {'TIGER': {'materialized': 1, 'ready': 1, 'restarts': 0}},
            'pods': [{'uid': 'uid-1', 'name': 'drone-1', 'fleet': 'TIGER', 'ready': True,
                      'phase': 'Running', 'restarts': 0, 'pod_ip': 'not-for-ui'}, {'name': 'no-uid'}],
            'router_state': {'participants': {'RELATION': 128}},
        }
        run = a.poll()[0]
        self.assertEqual(run['metrics']['fleet_organizations'], {'TIGER': 1})
        self.assertEqual(run['participants'], {'RELATION': 128})
        pods = run['metrics']['drone_pods']
        self.assertEqual(len(pods), 1)
        self.assertEqual(pods[0]['uid'], 'uid-1')
        self.assertIs(pods[0]['ready'], True)
        self.assertNotIn('pod_ip', pods[0])

if __name__=='__main__': unittest.main()

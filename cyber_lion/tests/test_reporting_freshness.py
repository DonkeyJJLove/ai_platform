import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from cyber_lion.mission_control.server import MissionControl
from cyber_lion.mission_control.storage import Store
from cyber_lion.mission_control.reconciliation import Reconciler
from cyber_lion.mission_control.registry import AdapterRegistry
from cyber_lion.mission_control.adapters.vkt_r3 import VktR3Adapter

class Adapter:
    adapter_id='TEST'
    supported_process_classes=('TEST',)
    fail=False
    def __init__(self):
        self.runs=[{'run_id':'r','adapter_type':'TEST','status':'RUNNING','metrics':
            {'pods':1,'fresh_drones':0,'fleet_organizations':{'LION':1},
             'active_by_organization':{'LION':0},'drone_pods':[{'uid':'p','ready':True}]}}]
    def poll(self):
        if self.fail: raise RuntimeError('secret should not appear in API')
        return self.runs

class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.temp.name)/'test.db')
        self.adapter=Adapter(); registry=AdapterRegistry(); registry.register(self.adapter)
        self.mc=MissionControl(self.store,registry,Reconciler(self.store,registry))
    def tearDown(self):
        self.store.close(); self.temp.cleanup()
    def test_per_run_fleet_isolation(self):
        import copy
        second=copy.deepcopy(self.adapter.runs[0]); second['run_id']='second'
        second['metrics']['fleet_organizations']={'TIGER':1}
        second['metrics']['active_by_organization']={'TIGER':0}
        self.adapter.runs.append(second)
        self.mc.poll_once(); result=self.mc.summary()
        self.assertEqual(set(result['run_fleets']), {'r','second'})
        self.assertNotIn('TIGER',result['run_fleets']['r']['organizations'])
        self.assertNotIn('LION',result['run_fleets']['second']['organizations'])
        self.adapter.runs=[]; self.adapter.empty_reason='K3S_NOT_RUNNING'
        self.mc.poll_once(); result=self.mc.summary()
        self.assertEqual(result['run_fleets'],{})
        self.assertEqual(result['run_observations']['r']['source_reason'],'K3S_NOT_RUNNING')
    def test_never_polled(self):
        s=self.mc.summary(); self.assertEqual(s['observation']['reason'],'NEVER_POLLED')
        self.assertIsNone(s['observation']['age_seconds']); self.assertIsNone(s['summary']['observed_active_runs'])
    def test_ready_is_not_heartbeat(self):
        self.mc.poll_once(); s=self.mc.summary()
        self.assertEqual(s['observation']['reason'],'OBSERVED')
        self.assertEqual(s['run_observations']['r']['heartbeat_status'],'NONE_FRESH')
        self.assertEqual(s['summary']['recorded_active_runs'],1)
        self.assertEqual(s['observation']['adapters']['TEST']['result_count'],1)
    def test_stale_poll(self):
        self.mc.poll_once()
        with patch('cyber_lion.mission_control.server.time.monotonic',return_value=self.mc.last_poll_at+6):
            s=self.mc.summary(); self.assertEqual(s['observation']['reason'],'POLL_STALE')
            self.assertEqual(s['run_observations']['r']['heartbeat_status'],'UNKNOWN')
            self.assertEqual(s['fleet']['pod_observations'],[])
    def test_empty_keeps_history(self):
        self.mc.poll_once(); self.adapter.runs=[]; self.mc.poll_once(); s=self.mc.summary()
        self.assertEqual(s['observation']['reason'],'EMPTY_OBSERVATION')
        self.assertEqual(s['run_observations']['r']['recorded_status'],'RUNNING')
        self.assertEqual(s['observation']['adapters']['TEST']['result_count'],0)
    def test_error_after_success(self):
        self.mc.poll_once(); success=self.mc.summary()['observation']['success_at']
        self.adapter.fail=True; self.mc.poll_once(); s=self.mc.summary()
        self.assertEqual(s['observation']['reason'],'POLL_ERROR')
        self.assertEqual(s['observation']['success_at'],success)
        self.assertNotIn('secret',str(s)); self.assertIsNone(s['observation']['adapters']['TEST']['result_count'])
    def test_invalid_observation(self):
        self.adapter.runs[0]['metrics']['fresh_drones']=2
        self.mc.poll_once(); self.assertEqual(self.mc.summary()['observation']['reason'],'INVALID_OBSERVATION')
    def test_terminal_preserved(self):
        for terminal in ('PASS','FAIL','CLEANED'):
            self.store.upsert_run({'run_id':'r','status':terminal})
            self.mc.poll_once(); self.assertEqual(self.store.get_run('r')['status'],terminal)
    def test_missing_heartbeat_does_not_reuse_stored_value(self):
        self.mc.poll_once()
        self.adapter.runs[0]['metrics']['fresh_drones']=None
        self.adapter.runs[0]['metrics']['active_by_organization']={}
        self.mc.poll_once(); s=self.mc.summary()
        self.assertEqual(s['run_observations']['r']['heartbeat_status'],'UNKNOWN')
        self.assertEqual(self.store.get_run('r')['metrics']['fresh_drones'],0)
    def test_fatal_poll_exception_is_visible(self):
        self.mc.poll_once()
        with patch.object(self.mc.reconciler,'poll_once',side_effect=RuntimeError('private')):
            with self.assertRaises(RuntimeError): self.mc.poll_once()
        s=self.mc.summary(); self.assertEqual(s['observation']['reason'],'POLL_ERROR')
        self.assertFalse(s['observation']['in_progress']); self.assertNotIn('private',str(s))
    def test_inflight_does_not_publish_partial_snapshot(self):
        self.mc.poll_once(); entered=threading.Event(); release=threading.Event()
        def poll():
            entered.set(); release.wait(2); return []
        self.adapter.poll=poll
        thread=threading.Thread(target=self.mc.poll_once); thread.start()
        try:
            self.assertTrue(entered.wait(1)); s=self.mc.summary()
            self.assertTrue(s['observation']['in_progress'])
            self.assertEqual(s['observation']['adapters']['TEST']['result_count'],1)
        finally: release.set(); thread.join(3)
        self.assertFalse(thread.is_alive()); self.assertEqual(self.mc.summary()['observation']['reason'],'EMPTY_OBSERVATION')
    def test_adapter_missing_is_not_zero(self):
        a=VktR3Adapter('a'*40,'b'*40)
        a._read=lambda:{'materialized':1,'pods':[{'uid':'p','ready':True}]}
        m=a.poll()[0]['metrics']; self.assertIsNone(m['fresh_drones']); self.assertIsNone(m['messages'])
        a._read=lambda:{'materialized':1,'router_state':{'fresh_count':0,'messages_total':0}}
        m=a.poll()[0]['metrics']; self.assertEqual(m['fresh_drones'],0); self.assertEqual(m['messages'],0)
    def test_nonfleet_run_has_current_observation(self):
        self.adapter.runs[0]['metrics']={'tests_passed':3}
        self.mc.poll_once(); s=self.mc.summary()
        self.assertEqual(s['observation']['reason'],'NO_FLEET_OBSERVATION')
        self.assertEqual(s['run_observations']['r']['observation_status'],'OBSERVED')
        self.assertEqual(s['summary']['observed_active_runs'],1)
        self.assertEqual(s['run_observations']['r']['heartbeat_status'],'UNKNOWN')
    def test_invalid_counter_is_unknown_not_zero(self):
        self.adapter.runs[0]['metrics']['fresh_drones']=2
        self.mc.poll_once(); self.assertIsNone(self.mc.summary()['summary']['observed_active_runs'])
    def test_terminal_excluded_heartbeat_with_other_current_run(self):
        import copy
        other=copy.deepcopy(self.adapter.runs[0]); other['run_id']='other'
        self.adapter.runs.append(other); self.store.upsert_run({'run_id':'r','status':'CLEANED'})
        self.mc.poll_once(); s=self.mc.summary()
        self.assertEqual(s['run_observations']['r']['observation_status'],'TERMINAL_HISTORY')
        self.assertEqual(s['run_observations']['r']['heartbeat_status'],'UNKNOWN')
    def test_numeric_boundary_does_not_throw(self):
        from cyber_lion.mission_control.adapters.vkt_r3 import optional_number
        for x in (True,float('nan'),float('inf'),-1,'3'):
            self.assertIsNone(optional_number(x))
        self.assertEqual(optional_number(10**400),10**400)
        self.assertIsNone(optional_number(10**400,fractional=True))

if __name__=='__main__': unittest.main()

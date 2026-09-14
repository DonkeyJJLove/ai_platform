import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from tools import lion_mission_control_compat as compat

class SummaryObservationsTest(unittest.TestCase):
    def snapshot(self,stamp=100):
        return {'state':'RUNNING','materialized':1,'ready':1,'material_target':1,'workers':[{'logical_id':'LD01','pod_name':'one','pod_uid':'one-uid','phase':'Running','ready':1,'observed_at':datetime.fromtimestamp(stamp,timezone.utc).isoformat()}]}

    def summary(self,s,focus='maintenance',poll=105,event_count=3):
        runs=[compat.current_run(s),{'run_id':'maintenance','status':'AUTHORIZED','metrics':{},'workload':{}}]
        sources={'sources':[{'name':'mission_control_v3','tables':{'mission_events':event_count,'protocol_messages':2}},{'name':'history','tables':{'events':2552}}]}
        with patch.object(compat,'all_runs',return_value=runs),patch.object(compat,'_v3_focus_id',return_value=focus),patch.object(compat,'source_inventory',return_value=sources),patch.object(compat,'table_count',return_value=25),patch.object(compat.time,'time',return_value=poll):
            return compat.summary(s)

    def test_focus_does_not_hide_observed_global_fleet(self):
        s=self.snapshot()
        for focus in ['maintenance',compat.CURRENT_ID]:
            result=self.summary(s,focus)
            self.assertEqual(result['summary']['observed_active_runs'],1)
            self.assertEqual(result['fleet']['run_ids'],[compat.CURRENT_ID])
        self.assertEqual(self.summary(s)['readiness']['status'],'UNKNOWN')

    def test_polling_does_not_refresh_old_worker_evidence(self):
        fresh=self.summary(self.snapshot(),poll=105)
        stale=self.summary(self.snapshot(),poll=120)
        self.assertEqual(fresh['observation']['age_seconds'],5)
        self.assertEqual(stale['observation']['age_seconds'],20)
        self.assertEqual(stale['observation']['success_at'],100)
        self.assertEqual(stale['summary']['observed_active_runs'],0)
        self.assertIsNone(stale['fleet']['working_drones'])

    def test_unknown_and_future_timestamps_are_not_fresh(self):
        for stamp in [None,'invalid','2999-01-01T00:00:00Z']:
            s=self.snapshot();s['workers'][0]['observed_at']=stamp
            self.assertEqual(self.summary(s)['summary']['observed_active_runs'],0)

    def test_live_events_change_independently_of_history(self):
        a=self.summary(self.snapshot(),event_count=3)['summary']
        b=self.summary(self.snapshot(),event_count=4)['summary']
        self.assertEqual((a['events'],b['events']),(5,6))
        self.assertEqual(a['historical_events'],b['historical_events'])
        self.assertEqual(a['recorded_active_runs'],1)
        self.assertEqual(a['authorized_runs'],1)

if __name__=='__main__':unittest.main()

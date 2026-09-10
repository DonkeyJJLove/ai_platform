import unittest

from cyber_lion.mission_control.models import normalize_run, summary_from_runs


class ModelsTests(unittest.TestCase):
    def test_generic_run_requires_no_vkt_fields(self):
        run = normalize_run({'run_id':'r1','process_class':'BUILD_AND_TEST','adapter_type':'X','status':'RUNNING','verification_status':'OBSERVED'})
        self.assertEqual(run['run_id'],'r1')
        self.assertNotIn('fresh_drones', run)
        self.assertNotIn('cases_proven', run)
        self.assertNotIn('ack_rate', run)

    def test_summary_is_generic(self):
        runs=[normalize_run({'run_id':'a','status':'RUNNING','verification_status':'OBSERVED','adapter_type':'X','host':'h','workload':{'kind':'Job'}}),normalize_run({'run_id':'b','status':'PASS','verification_status':'VERIFIED','adapter_type':'Y','host':'h'})]
        s=summary_from_runs(runs)
        self.assertEqual(s['active_runs'],1); self.assertEqual(s['completed_runs'],1); self.assertEqual(s['hosts'],1)

    def test_invalid_status_denied(self):
        with self.assertRaises(ValueError): normalize_run({'run_id':'r','status':'BOGUS'})

if __name__=='__main__': unittest.main()

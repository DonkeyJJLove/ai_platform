import unittest

from cyber_lion.mission_control.models import fleet_summary_from_runs, normalize_run, summary_from_runs


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

    def test_fleet_summary_is_dynamic_and_organization_bound(self):
        runs=[
            normalize_run({
                "run_id":"fleet-a","status":"RUNNING","verification_status":"OBSERVED","adapter_type":"VKT_R3",
                "metrics":{"pods":384,"fresh_drones":300,"fleet_organizations":{"TIGER":128,"SPECTRA":128,"LION":128},"active_by_organization":{"TIGER":100,"SPECTRA":96,"LION":104}},
            }),
            normalize_run({"run_id":"historical","status":"CLEANED","verification_status":"VERIFIED","adapter_type":"OSS","metrics":{"pytest_exit_code":0}}),
        ]
        fleet=fleet_summary_from_runs(runs)
        self.assertEqual(fleet["fleet_total"],384)
        self.assertEqual(fleet["working_drones"],300)
        self.assertEqual(fleet["organization_count"],3)
        self.assertEqual(fleet["organizations"]["TIGER"],{"total":128,"active":100,"idle":28})
        self.assertEqual(fleet["run_ids"],["fleet-a"])

    def test_invalid_status_denied(self):
        with self.assertRaises(ValueError): normalize_run({'run_id':'r','status':'BOGUS'})

if __name__=='__main__': unittest.main()

"""Deterministic policy tests. Resource pressure is not evidence of compromise."""
from dataclasses import replace
import unittest
from cyber_lion.enterprise.edge_yoke.policy import YokePolicy,VetoMachine
from cyber_lion.mission_control.edge_support import EdgeRejected

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy=YokePolicy(cool_samples=2)
        self.machine=VetoMachine(self.policy)
    def sample(self,**kw):
        return dict(dict(observed_at=100,cpu_percent=10,memory_percent=20,free_bytes=2**40,integrity='MATCH'),**kw)
    def clear(self):
        self.machine.update(self.sample(),100)
        return self.machine.update(self.sample(),100)
    def test_initial_warmup(self):self.assertEqual(self.machine.update(self.sample(),100)['state'],'HOLD')
    def test_cool_samples_release_veto_not_authority(self):
        r=self.clear();self.assertEqual(r['state'],'NO_VETO');self.assertEqual(r['authority_effect'],'NONE')
    def test_sustained_cpu(self):
        self.clear()
        for _ in range(3):r=self.machine.update(self.sample(cpu_percent=99),100)
        self.assertEqual(r['state'],'HOLD')
    def test_spike_requests_review(self):
        self.clear();r=self.machine.update(self.sample(cpu_percent=99),100)
        self.assertEqual(r['state'],'NO_VETO');self.assertIn('CPU_PATTERN_CHANGE_REVIEW',r['notices'])
    def test_memory_pressure(self):
        self.clear()
        for _ in range(3):r=self.machine.update(self.sample(memory_percent=99),100)
        self.assertEqual(r['state'],'HOLD')
    def test_disk_hard_stop(self):self.assertEqual(self.machine.update(self.sample(free_bytes=0),100)['state'],'HOLD')
    def test_stale(self):self.assertEqual(self.machine.update(self.sample(),111)['state'],'UNKNOWN')
    def test_future(self):self.assertEqual(self.machine.update(self.sample(),99)['state'],'UNKNOWN')
    def test_boolean_not_metric(self):self.assertEqual(self.machine.update(self.sample(cpu_percent=True),100)['state'],'UNKNOWN')
    def test_nan_not_metric(self):self.assertEqual(self.machine.update(self.sample(cpu_percent=float('nan')),100)['state'],'UNKNOWN')
    def test_missing_metrics(self):self.assertEqual(self.machine.update({},100)['state'],'UNKNOWN')
    def test_integrity_mismatch_latches_without_metrics(self):
        self.assertEqual(self.machine.update({'integrity':'MISMATCH'},100)['state'],'QUARANTINE')
        self.assertEqual(self.machine.update({},100)['state'],'QUARANTINE')
    def test_integrity_unknown(self):self.assertEqual(self.machine.update(self.sample(integrity='UNKNOWN'),100)['state'],'UNKNOWN')
    def test_stalled_progress(self):self.assertEqual(self.machine.update(self.sample(task_active=True,seconds_without_progress=130),100)['state'],'HOLD')
    def test_active_missing_progress(self):self.assertEqual(self.machine.update(self.sample(task_active=True),100)['state'],'HOLD')
    def test_recovery_hysteresis(self):
        self.clear();self.machine.update(self.sample(free_bytes=0),100)
        self.assertEqual(self.machine.update(self.sample(),100)['state'],'HOLD')
        self.assertEqual(self.machine.update(self.sample(),100)['state'],'NO_VETO')
    def test_policy_negative_controls(self):
        for kw in [dict(cpu_limit=101),dict(ema_alpha=0),dict(cool_samples=True),dict(snapshot_ttl=100),dict(free_bytes_min=-1),dict(cpu_step=float('nan'))]:
            with self.subTest(kw=kw),self.assertRaises(EdgeRejected):replace(self.policy,**kw).validate()
    def test_policy_digest_changes(self):self.assertNotEqual(self.policy.digest(),replace(self.policy,cpu_limit=90).digest())
if __name__=='__main__':unittest.main()

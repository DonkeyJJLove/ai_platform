from dataclasses import replace
import unittest
from cyber_lion.mission_control.source_rebind import RuntimeSourceIdentity,TargetSourceCandidate,propose_source_rebind
from cyber_lion.mission_control.source_rebind_admission import *
D=lambda c:c*64;H=lambda c:c*40
class AdmissionTests(unittest.TestCase):
 def current(self):return RuntimeSourceIdentity('DonkeyJJLove/ai_platform','master',H('1'),H('2'),'e02-passive','TEST_ONLY')
 def target(self):return TargetSourceCandidate('DonkeyJJLove/ai_platform','master',H('3'),H('4'),D('5'),D('6'),D('7'),D('8'))
 def plan(self):return propose_source_rebind(self.current(),self.target(),observed_master_head=H('3'),observed_master_tree=H('4'))
 def rollback(self):return RollbackSourceIdentity(H('1'),H('2'),'e02-passive',D('9'),D('a'),D('b'))
 def admission(self):return prepare_deployment_admission(plan=self.plan(),package_digest=D('c'),current_runtime=self.current(),rollback=self.rollback(),readback=PostApplyReadbackContract(),admission_id='mc-r6-admission-1')
 def test_candidate_is_nonexecuted_one_shot(self):
  a=self.admission();self.assertEqual((a.max_attempts,a.retry_max_attempts,a.replay_policy),(1,0,'RECONCILE_FIRST'));self.assertEqual(a.state,'AUTHORITY_REQUIRED_NOT_EXECUTED');self.assertFalse(a.service_restart_executed);self.assertEqual(a.k3s_effect,'NONE')
 def test_deterministic_idempotency_and_digest(self):self.assertEqual(self.admission(),self.admission())
 def test_runtime_substitution_denied(self):
  with self.assertRaisesRegex(SourceRebindAdmissionError,'runtime source substitution'):prepare_deployment_admission(plan=self.plan(),package_digest=D('c'),current_runtime=replace(self.current(),source_head=H('f')),rollback=self.rollback(),readback=PostApplyReadbackContract(),admission_id='x')
 def test_rollback_substitution_denied(self):
  with self.assertRaisesRegex(SourceRebindAdmissionError,'rollback identity'):prepare_deployment_admission(plan=self.plan(),package_digest=D('c'),current_runtime=self.current(),rollback=replace(self.rollback(),release_id='other'),readback=PostApplyReadbackContract(),admission_id='x')
 def test_readback_cannot_be_weakened(self):
  with self.assertRaisesRegex(SourceRebindAdmissionError,'readback cannot be weakened'):prepare_deployment_admission(plan=self.plan(),package_digest=D('c'),current_runtime=self.current(),rollback=self.rollback(),readback=replace(PostApplyReadbackContract(),require_vkt_observation=False),admission_id='x')
 def test_retry_and_state_promotion_denied(self):
  a=self.admission()
  for bad in (replace(a,retry_max_attempts=1),replace(a,state='AUTHORIZED'),replace(a,service_restart_executed=True),replace(a,k3s_effect='START')):
   with self.assertRaises(SourceRebindAdmissionError):bad.validate()
 def test_plan_and_package_substitution_denied_by_digest(self):
  a=self.admission()
  with self.assertRaisesRegex(SourceRebindAdmissionError,'admission digest mismatch'):replace(a,package_digest=D('d')).validate()
 def test_apply_is_unavailable(self):
  with self.assertRaisesRegex(SourceRebindAdmissionError,'separate current authority'):apply_deployment_admission(self.admission())
if __name__=='__main__':unittest.main()

from dataclasses import replace
import unittest
from cyber_lion.mission_control.source_rebind import RuntimeSourceIdentity,TargetSourceCandidate,SourceRebindError,propose_source_rebind,apply_source_rebind
D=lambda c:c*64
H=lambda c:c*40
class SourceRebindTests(unittest.TestCase):
 def current(self): return RuntimeSourceIdentity("DonkeyJJLove/ai_platform","master",H("1"),H("2"),"e02-passive","TEST_ONLY")
 def target(self): return TargetSourceCandidate("DonkeyJJLove/ai_platform","master",H("3"),H("4"),D("5"),D("6"),D("7"),D("8"))
 def plan(self,c=None,t=None):
  t=t or self.target(); return propose_source_rebind(c or self.current(),t,observed_master_head=t.source_head,observed_master_tree=t.source_tree)
 def test_stale_source_yields_effect_free_change_plan(self):
  p=self.plan(); self.assertEqual(p.currentness,"SOURCE_CHANGE_REQUIRED"); self.assertEqual(p.authority_effect,"NONE"); self.assertFalse(p.service_restart); self.assertEqual(p.k3s_effect,"NONE")
 def test_already_current_is_explicit_noop_candidate(self):
  t=self.target(); c=RuntimeSourceIdentity(t.repository,t.branch,t.source_head,t.source_tree,"same","CANDIDATE"); self.assertEqual(self.plan(c,t).currentness,"ALREADY_CURRENT")
 def test_target_must_equal_observed_master(self):
  with self.assertRaisesRegex(SourceRebindError,"exact observed master"): propose_source_rebind(self.current(),self.target(),observed_master_head=H("9"),observed_master_tree=H("4"))
 def test_repository_branch_and_hash_substitution_denied(self):
  for bad in (replace(self.target(),repository="other/repo"),replace(self.target(),branch="dev"),replace(self.target(),source_head="bad")):
   with self.assertRaises(SourceRebindError): self.plan(t=bad)
 def test_digest_substitution_denied(self):
  for field in ("release_digest","configuration_digest","adapter_set_digest","database_schema_digest"):
   with self.assertRaises(SourceRebindError): self.plan(t=replace(self.target(),**{field:"bad"}))
 def test_plan_digest_is_deterministic(self): self.assertEqual(self.plan(),self.plan())
 def test_plan_tamper_denied(self):
  p=self.plan()
  with self.assertRaisesRegex(SourceRebindError,"plan digest mismatch"): replace(p,target_tree=H("a")).validate()
 def test_apply_is_never_implemented(self):
  with self.assertRaisesRegex(SourceRebindError,"separate deployment authority"): apply_source_rebind(self.plan())
 def test_runtime_identity_trust_class_is_explicit(self):
  with self.assertRaises(SourceRebindError): replace(self.current(),trust_class="TRUST_ME").validate()
 def test_exact_types_required(self):
  with self.assertRaises(SourceRebindError): propose_source_rebind(object(),self.target(),observed_master_head=H("3"),observed_master_tree=H("4"))
if __name__=='__main__': unittest.main()

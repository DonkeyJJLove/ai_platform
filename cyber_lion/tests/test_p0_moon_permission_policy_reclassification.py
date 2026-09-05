from pathlib import Path
import subprocess,unittest
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler
from tools.p0_moon_attack_registry import PERMISSION_SURFACE
from tools.p0_moon_permission_policy_reclassification import OS_REPLACE_SURFACE,PRE_EFFECT,REHOMED,boundary_matrix,materialize_policy_v2_readiness,policy_v2
REPO="DonkeyJJLove/ai_platform"
def current():
    root=Path(__file__).resolve().parents[2];src={}
    for p in subprocess.check_output(["git","ls-files"],cwd=root,text=True).splitlines():
        if (p.startswith("cyber_lion/") and p.endswith(".py") and "/tests/" not in f"/{p}") or (p.startswith(".github/workflows/") and p.endswith((".yml",".yaml"))):src[p]=(root/p).read_text()
    rev=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip();tree=subprocess.check_output(["git","rev-parse","HEAD^{tree}"],cwd=root,text=True).strip();raw=EffectSurfaceScanner().scan(repository=REPO,revision=rev,tree_digest=tree,sources=src);inv,report,_=EffectTaxonomyReconciler().reconcile(raw_inventory=raw,sources=src);return root,inv,report
class PermissionPolicyReclassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.root,cls.inv,cls.tax=current();cls.mappings,cls.policy,cls.closure,cls.carrier,cls.report=materialize_policy_v2_readiness(inventory=cls.inv,taxonomy_report=cls.tax,repo_root=cls.root)
    def test_current_inventory_and_taxonomy_remain_exact(self):
        self.assertEqual(self.inv.scan_digest,"8ee66a2523a0b03784ecd283a7c502d928abd0a342b087b236f1c9c6de01c71c");self.assertFalse(self.tax.unresolved_refs);self.assertEqual(len(self.inv.surfaces),236)
    def test_permission_boundary_matrix_is_exact(self):
        by={x.attack_id:x for x in self.mappings};self.assertEqual(set(by),set(PRE_EFFECT)|set(REHOMED))
        for a in PRE_EFFECT:self.assertEqual(by[a].classification,"PRE_EFFECT_GUARD");self.assertEqual(by[a].effect_boundary_relation,"BEFORE_SURFACE_EFFECT")
        self.assertEqual(by["UNTRUSTED_PERMISSION"].classification,"POST_OBSERVATION_DECISION");self.assertEqual(by["UNTRUSTED_PERMISSION"].effect_boundary_relation,"AFTER_SURFACE_EFFECT")
        self.assertEqual(by["STALE_AUTHORITY_SOURCE"].classification,"DOWNSTREAM_CURRENTNESS_GUARD");self.assertEqual(by["STALE_AUTHORITY_SOURCE"].target_surface_digest,OS_REPLACE_SURFACE)
    def test_policy_v2_drops_no_security_requirement(self):
        _,_,p=policy_v2(inventory=self.inv,repo_root=self.root);req=p.required_attack_map();self.assertEqual(req[PERMISSION_SURFACE],PRE_EFFECT);self.assertEqual({x.attack_id for x in p.security_requirements},set(REHOMED));self.assertEqual(set(req[PERMISSION_SURFACE])|{x.attack_id for x in p.security_requirements},set(PRE_EFFECT)|set(REHOMED))
    def test_seven_surface_bypass_closure_is_mediated_but_security_obligations_remain_open(self):
        self.assertEqual(len(self.closure),7);self.assertTrue(all(x.status=="MEDIATED" for x in self.closure));self.assertEqual(self.report.seven_mediated_count,7);self.assertEqual(self.report.unresolved_security_requirement_keys,("STALE_AUTHORITY_SOURCE","UNTRUSTED_PERMISSION"));self.assertEqual(self.report.global_status,"UNKNOWN")
    def test_global_carrier_remains_fail_closed(self):
        counts={s:sum(x.status==s for x in self.carrier.surface_statuses) for s in ("MEDIATED","PARTIAL","UNMEDIATED","UNKNOWN")};self.assertEqual(counts,{"MEDIATED":7,"PARTIAL":0,"UNMEDIATED":0,"UNKNOWN":229});self.assertEqual(self.carrier.global_status,"UNKNOWN")
    def test_no_new_bypass_evidence_is_invented_for_rehomed_requirements(self):
        for x in self.policy.security_requirements:self.assertEqual(x.evidence_state,"CONTROL_FLOW_OBSERVED_EVIDENCE_REQUIRED")
    def test_next_minimal_plan_requires_boundary_refactor_not_live_probe(self):
        self.assertTrue(any("pure-admission-decision-boundary" in x for x in self.report.next_evidence_plan));self.assertTrue(any("canonical-pre-fence-currentness-negative-evidence" in x for x in self.report.next_evidence_plan))
if __name__=="__main__":unittest.main()

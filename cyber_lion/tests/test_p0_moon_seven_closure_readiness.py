from __future__ import annotations
from pathlib import Path
import subprocess, unittest

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler
from tools.p0_moon_attack_registry import FENCE_SURFACES, PERMISSION_SURFACE, PREPARED_SURFACE
from tools.p0_moon_attested_adjudication import EXPECTED_SCAN_DIGEST
from tools.p0_moon_seven_closure_readiness import BLOCKED_PERMISSION, CLASS_BLOCKED_LIVE, CLASS_CANONICAL, materialize_seven_closure_readiness
from tools.p0_moon_structural_falsification import STRUCTURAL_ATTACKS

REPO="DonkeyJJLove/ai_platform"
def current_inventory():
    root=Path(__file__).resolve().parents[2];sources={}
    for raw in subprocess.run(["git","ls-files"],cwd=root,check=True,stdout=subprocess.PIPE,text=True).stdout.splitlines():
        if (raw.startswith("cyber_lion/") and raw.endswith(".py") and "/tests/" not in f"/{raw}") or (raw.startswith(".github/workflows/") and raw.endswith((".yml",".yaml"))): sources[raw]=(root/raw).read_text(encoding="utf-8")
    revision=subprocess.run(["git","rev-parse","HEAD"],cwd=root,check=True,stdout=subprocess.PIPE,text=True).stdout.strip();tree=subprocess.run(["git","write-tree"],cwd=root,check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
    raw=EffectSurfaceScanner().scan(repository=REPO,revision=revision,tree_digest=tree,sources=sources)
    inv,report,_=EffectTaxonomyReconciler().reconcile(raw_inventory=raw,sources=sources);return root,inv,report

class MoonSevenClosureReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root,cls.inventory,cls.taxonomy=current_inventory();cls.art=materialize_seven_closure_readiness(inventory=cls.inventory,taxonomy_report=cls.taxonomy,repo_root=cls.root)

    def test_current_inventory_is_exact_and_globally_fail_closed(self):
        self.assertEqual(self.inventory.scan_digest,EXPECTED_SCAN_DIGEST);self.assertFalse(self.inventory.unclassified_refs);self.assertFalse(self.taxonomy.unresolved_refs)
        self.assertEqual(self.art.global_carrier.global_status,"UNKNOWN")
        counts={s:sum(1 for x in self.art.global_carrier.surface_statuses if x.status==s) for s in ("MEDIATED","PARTIAL","UNMEDIATED","UNKNOWN")}
        self.assertEqual(counts,{"MEDIATED":6,"PARTIAL":1,"UNMEDIATED":0,"UNKNOWN":229})

    def test_structural_adapter_materializes_exact_surface_local_matrix(self):
        self.assertEqual(len(self.art.structural.bypass_results),24);self.assertEqual(len(self.art.structural.observations),24)
        keys={(r.surface_digest,r.attack_id) for r in self.art.structural.bypass_results};self.assertEqual(len(keys),24)
        for sd in FENCE_SURFACES:
            self.assertEqual({a for s,a in keys if s==sd},set(STRUCTURAL_ATTACKS))
        self.assertTrue(all(r.observed_outcome=="DENIED" and r.epistemic_state=="OBSERVED" for r in self.art.structural.bypass_results))
        self.assertTrue(all(not any(ref.startswith("test:") for ref in r.evidence_refs) for r in self.art.structural.bypass_results))

    def test_required_attack_matrix_has_only_two_remaining_permission_blockers(self):
        missing=[x for x in self.art.readiness if x.classification!=CLASS_CANONICAL]
        self.assertEqual({x.surface_digest for x in missing},{PERMISSION_SURFACE});self.assertEqual({x.attack_id for x in missing},set(BLOCKED_PERMISSION));self.assertTrue(all(x.classification==CLASS_BLOCKED_LIVE for x in missing))
        self.assertEqual(self.art.report.missing_attack_keys,(f"{PERMISSION_SURFACE}:STALE_AUTHORITY_SOURCE",f"{PERMISSION_SURFACE}:UNTRUSTED_PERMISSION"))

    def test_closure_records_are_six_mediated_one_partial_and_policy_complete(self):
        records={r.surface_digest:r for r in self.art.closure_records};self.assertEqual(set(records),set(FENCE_SURFACES)|{PERMISSION_SURFACE})
        for sd in FENCE_SURFACES:
            self.assertEqual(records[sd].status,"MEDIATED");self.assertTrue(records[sd].binding_digest);self.assertTrue(records[sd].bypass_result_digests)
        self.assertEqual(records[PERMISSION_SURFACE].status,"PARTIAL");self.assertEqual(len(records[PERMISSION_SURFACE].bypass_result_digests),3)
        self.assertEqual(len(records[PREPARED_SURFACE].bypass_result_digests),5)
        for sd in set(FENCE_SURFACES)-{PREPARED_SURFACE}: self.assertEqual(len(records[sd].bypass_result_digests),4)

    def test_no_shared_result_multiplies_across_surfaces(self):
        seen={}
        for r in self.art.structural.bypass_results:
            self.assertNotIn(r.digest(),seen);seen[r.digest()]=(r.surface_digest,r.attack_id)
        self.assertEqual(len(seen),24)

if __name__=="__main__": unittest.main()

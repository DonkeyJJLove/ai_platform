from __future__ import annotations
from collections import Counter
from pathlib import Path
import subprocess,unittest
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler
from tools.p0_surface_closure_campaign import (
    CERTIFIED_PARTIAL_SURFACE,EXPECTED_SCAN_DIGEST,RECEIPT_IMPLIED_MOON_SURFACES,
    SurfaceClosureCampaignBuilder,SurfaceClosureCampaignError,certified_runtime_evidence,
)

REPO="DonkeyJJLove/ai_platform"
EXPECTED_CLASSES={
    "persistent_state.write":185,"filesystem.write":12,"filesystem.delete":11,"runtime.tool_execution":8,"filesystem.replace":5,
    "external.network.post":4,"filesystem.bootstrap.write":3,"filesystem.bootstrap.mkdir":2,"external.network.authority_observation":1,
    "external.network.delete":1,"external.network.patch":1,"repository_ref.delete":1,"runtime.process_launch":1,
}
EXPECTED_FIRST=frozenset(RECEIPT_IMPLIED_MOON_SURFACES)
WORKFLOW_STEP_ONLY=frozenset({
    "f30fb49749edd3ae3fde43962e5b1a65e7cc1696cd33fea44dc8304f58a32333",
    "b6a46b7837f7e156dbcaada7fa3c48f7e3cb30cb3272a14af32eebcea6eff9f6",
    "e4fdf5e6f7cf94773ee1934f868a50a30e0fc9abe810cdf50d9699227f84b2d4",
    "0c8b4950f2190e63564a928d1a0957f3dbd5b3a43d249cc46176fa0c646d3a54",
    "7463678780ded21dfe1c67ac58e8704a65cec92aec6ef952dce81aaf6efe3389",
})
MARK_UNKNOWN="b7c1aed2b404ff1963867306f5e57c3abc64dc12916366296cb9ae089e3c6dc5"

def current_inventory():
    root=Path(__file__).resolve().parents[2]
    sources={}
    for raw in subprocess.run(["git","ls-files"],check=True,stdout=subprocess.PIPE,text=True).stdout.splitlines():
        if (raw.startswith("cyber_lion/") and raw.endswith(".py") and "/tests/" not in f"/{raw}") or (raw.startswith(".github/workflows/") and raw.endswith((".yml",".yaml"))):sources[raw]=(root/raw).read_text(encoding="utf-8")
    revision=subprocess.run(["git","rev-parse","HEAD"],check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
    tree=subprocess.run(["git","write-tree"],check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
    raw=EffectSurfaceScanner().scan(repository=REPO,revision=revision,tree_digest=tree,sources=sources)
    inv,report,_=EffectTaxonomyReconciler().reconcile(raw_inventory=raw,sources=sources)
    return inv,report

def campaign():
    inv,_=current_inventory()
    return inv,SurfaceClosureCampaignBuilder().materialize(
        inventory=inv,runtime_evidence=certified_runtime_evidence(),live_falsification_carrier_state="ABSENT",
        evidence_refs=("github-actions-run:33911284689","github-actions-job:101148041371","p0-moon-replace-live-cert-r2"),
    )

class P0SurfaceClosureCampaignTests(unittest.TestCase):
    def test_exact_235_matrix_and_scan_digest(self):
        inv,c=campaign();self.assertEqual(inv.scan_digest,EXPECTED_SCAN_DIGEST);self.assertEqual(len(inv.surfaces),236);self.assertEqual(c.remaining_surface_count,235)
        self.assertEqual(c.excluded_surface_digests,(CERTIFIED_PARTIAL_SURFACE,));self.assertEqual(c.global_status,"UNKNOWN")
        self.assertEqual(Counter(x.effect_class for x in c.work_items),Counter(EXPECTED_CLASSES))

    def test_first_safe_batch_is_exact_seven_receipt_implied_surfaces(self):
        _,c=campaign();self.assertEqual(set(c.first_safe_batch_digests),EXPECTED_FIRST);self.assertEqual(len(c.first_safe_batch_digests),7)
        by={x.surface_digest:x for x in c.work_items}
        self.assertTrue(all(by[d].runtime_state=="OBSERVED" and by[d].closure_status=="PARTIAL" for d in EXPECTED_FIRST))
        self.assertTrue(all(by[d].binding_state==by[d].chain_state==by[d].bypass_state=="ABSENT" for d in EXPECTED_FIRST))

    def test_step_success_only_and_unknown_transition_are_not_promoted_to_runtime_trace(self):
        _,c=campaign();by={x.surface_digest:x for x in c.work_items}
        self.assertTrue(all(by[d].runtime_state=="UNKNOWN" for d in WORKFLOW_STEP_ONLY));self.assertEqual(by[MARK_UNKNOWN].runtime_state,"UNKNOWN")

    def test_no_surface_is_synthetically_mediated(self):
        _,c=campaign();self.assertEqual(sum(x.closure_status=="PARTIAL" for x in c.work_items),7);self.assertEqual(sum(x.closure_status=="UNKNOWN" for x in c.work_items),228)
        self.assertTrue(all(x.binding_state==x.chain_state==x.bypass_state=="ABSENT" for x in c.work_items));self.assertEqual(c.live_falsification_carrier_state,"ABSENT")

    def test_provider_family_partition_and_concentration(self):
        _,c=campaign();multi=[f for f in c.provider_families if len(f.surface_digests)>1];single=[f for f in c.provider_families if len(f.surface_digests)==1]
        self.assertEqual(len(multi),32);self.assertEqual(sum(len(f.surface_digests) for f in multi),222);self.assertEqual(len(single),13)
        self.assertEqual(sum(len(f.surface_digests) for f in c.provider_families),235)

    def test_foreign_runtime_evidence_and_scan_drift_fail_closed(self):
        inv,_=current_inventory()
        with self.assertRaises(SurfaceClosureCampaignError):SurfaceClosureCampaignBuilder().materialize(inventory=inv,runtime_evidence={"f"*64:("x",)},evidence_refs=("e",))
        object.__setattr__(inv,"scan_digest","0"*64)
        with self.assertRaises(SurfaceClosureCampaignError):SurfaceClosureCampaignBuilder().materialize(inventory=inv,runtime_evidence={},evidence_refs=("e",))

    def test_campaign_digest_is_stable(self):
        _,c=campaign();self.assertEqual(c.digest(),c.digest());self.assertEqual(len(c.digest()),64)

if __name__=="__main__":unittest.main()

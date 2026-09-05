from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import subprocess,unittest

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler
from tools.p0_moon_attack_registry import ATTACKS,FENCE_SURFACES,PERMISSION_SURFACE,PREPARED_SURFACE,live_attacks
from tools.p0_moon_runner_attested_bridge_contract import RunnerAttestedOperationReceipt
from tools.p0_moon_attested_adjudication_contract import ADJUDICATION_DOMAIN,POLICY_DOMAIN,AttestedAdjudicationContractError,GitHubJobEvidence
from tools.p0_moon_attested_adjudication import (
    EXPECTED_SCAN_DIGEST,SOURCE_BRIDGE_BLOB,SOURCE_REVISION,SOURCE_TREE,
    RunnerAttestedReceiptAdjudicator,_job,_outer,_run,adjudicate_live_receipts,materialize_attested_adjudication,
)
from tools.p0_moon_same_connection_denial_carrier import _attack_plans
from tools.p0_moon_readonly_observer_falsification import MoonBoundedFalsificationRuntimeCandidate
from tools.p0_moon_seven_binding import _attacks

REPO="DonkeyJJLove/ai_platform"
def current_inventory():
    root=Path(__file__).resolve().parents[2];sources={}
    for raw in subprocess.run(["git","ls-files"],cwd=root,check=True,stdout=subprocess.PIPE,text=True).stdout.splitlines():
        if (raw.startswith("cyber_lion/") and raw.endswith(".py") and "/tests/" not in f"/{raw}") or (raw.startswith(".github/workflows/") and raw.endswith((".yml",".yaml"))):sources[raw]=(root/raw).read_text(encoding="utf-8")
    revision=subprocess.run(["git","rev-parse","HEAD"],cwd=root,check=True,stdout=subprocess.PIPE,text=True).stdout.strip();tree=subprocess.run(["git","write-tree"],cwd=root,check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
    raw=EffectSurfaceScanner().scan(repository=REPO,revision=revision,tree_digest=tree,sources=sources)
    inv,report,_=EffectTaxonomyReconciler().reconcile(raw_inventory=raw,sources=sources);return root,inv,report

class MoonAttestedAdjudicationTests(unittest.TestCase):
    def test_contract_domains_are_explicit_and_versioned(self):
        self.assertEqual(ADJUDICATION_DOMAIN,b"LION/MOON-RUNNER-ATTESTED-ADJUDICATION/1")
        self.assertEqual(POLICY_DOMAIN,b"LION/MEDIATION-ATTACK-REQUIREMENT-POLICY/1")

    def test_all_seven_outer_receipts_are_representable_without_inner_payload(self):
        records=adjudicate_live_receipts();self.assertEqual(len(records),7)
        self.assertEqual(sum(r.result=="OBSERVED" for r in records.values()),2);self.assertEqual(sum(r.result=="DENIED" for r in records.values()),5)
        for op,r in records.items():
            self.assertEqual(len(r.inner_result_digest),64);self.assertFalse(hasattr(r,"inner_observed_at"));self.assertFalse(hasattr(r,"canary_pre_sha256"));self.assertFalse(hasattr(r,"fence_pre_digest"));self.assertEqual(r.source_bridge_blob_sha,SOURCE_BRIDGE_BLOB)

    def test_forged_outer_receipt_is_denied(self):
        outer=_outer("DENY_ACTOR_SUBSTITUTION")
        bad=replace(outer,result_digest="0"*64)
        with self.assertRaises(Exception):RunnerAttestedReceiptAdjudicator().adjudicate(outer=bad,run=_run("DENY_ACTOR_SUBSTITUTION"),job=_job("DENY_ACTOR_SUBSTITUTION"))

    def test_wrong_numeric_job_run_runner_revision_and_tree_are_denied(self):
        a=RunnerAttestedReceiptAdjudicator();op="DENY_ACTOR_SUBSTITUTION";outer=_outer(op);run=_run(op);job=_job(op)
        with self.assertRaises(Exception):a.adjudicate(outer=outer,run=run,job=replace(job,job_id_numeric=job.job_id_numeric+1,run_id_numeric=run.run_id_numeric+1))
        with self.assertRaises(Exception):a.adjudicate(outer=outer,run=replace(run,head_sha="0"*40),job=job)
        with self.assertRaises(Exception):a.adjudicate(outer=outer,run=replace(run,head_tree="0"*40),job=job)
        with self.assertRaises(Exception):a.adjudicate(outer=outer,run=run,job=replace(job,runner_agent_id=25))

    def test_attack_semantics_have_one_registry_source_and_actor_drift_is_fixed(self):
        self.assertEqual(len(ATTACKS),len(set(ATTACKS)))
        actual={p.attack_id:(p.pep,p.expected_denial) for p in _attack_plans()}
        runtime=MoonBoundedFalsificationRuntimeCandidate(SOURCE_REVISION);legacy=runtime._rows()
        for a in live_attacks():
            self.assertEqual(actual[a.attack_id],(a.pep,a.expected_denial));self.assertEqual(legacy[a.attack_id][1:],(a.pep,a.expected_denial))
        self.assertEqual(actual["ACTOR_SUBSTITUTION"],("_PermissionAdmissionResolver.resolve","authority subject substitution"))
        self.assertEqual({x.attack_id for x in _attacks()},set(ATTACKS))

    def test_materialization_promotes_two_observers_resolves_seven_and_converts_only_four_results(self):
        root,inv,report=current_inventory();self.assertEqual(inv.scan_digest,EXPECTED_SCAN_DIGEST);self.assertFalse(report.unresolved_refs)
        art=materialize_attested_adjudication(inventory=inv,repo_root=root)
        self.assertEqual(len(art.records),7);self.assertEqual(len(art.bindings),7);self.assertEqual(len(art.chains),7)
        self.assertEqual(len(art.bypass_results),4);self.assertEqual(art.plan.resolved_binding_count,7);self.assertEqual(art.plan.resolved_chain_count,7);self.assertEqual(art.plan.global_status,"UNKNOWN")
        self.assertEqual(art.conversion_decisions["DENY_WRONG_EXPECTED_STATE"],"EVIDENCE_ONLY:FAMILY_SCOPE_WITHOUT_EXPLICIT_SHARED_CLOSURE_COVERAGE")
        replay=[r for r in art.bypass_results if r.attack_id=="REPLAYED_EFFECT_KEY"];self.assertEqual(len(replay),1);self.assertEqual(replay[0].surface_digest,PREPARED_SURFACE)
        actor=[r for r in art.bypass_results if r.attack_id=="ACTOR_SUBSTITUTION"];self.assertEqual(len(actor),1);self.assertEqual(actor[0].surface_digest,PERMISSION_SURFACE)
        self.assertFalse(any(r.attack_id=="WRONG_EXPECTED_STATE" for r in art.bypass_results))

    def test_shared_fence_denial_cannot_auto_create_six_results(self):
        root,inv,_=current_inventory();art=materialize_attested_adjudication(inventory=inv,repo_root=root)
        wrong=[r for r in art.bypass_results if r.attack_id=="WRONG_EXPECTED_STATE"]
        self.assertEqual(wrong,[]);self.assertEqual(len(FENCE_SURFACES),6)

    def test_required_attack_policy_is_nonempty_and_missing_results_block_mediated(self):
        root,inv,_=current_inventory();art=materialize_attested_adjudication(inventory=inv,repo_root=root)
        self.assertEqual(len(art.policy.requirements),7)
        results={(r.surface_digest,r.attack_id) for r in art.bypass_results}
        partial=0;mediated=0
        for req in art.policy.requirements:
            self.assertTrue(req.attack_ids)
            complete=all((req.surface_digest,a) in results for a in req.attack_ids)
            mediated+=int(complete);partial+=int(not complete)
        self.assertEqual(mediated,0);self.assertEqual(partial,7)
        permission=next(r for r in art.policy.requirements if r.surface_digest==PERMISSION_SURFACE)
        self.assertIn("UNTRUSTED_PERMISSION",permission.attack_ids);self.assertIn("STALE_AUTHORITY_SOURCE",permission.attack_ids)

    def test_revision_rebind_is_explicit_and_source_blobs_are_unchanged(self):
        root,inv,_=current_inventory();art=materialize_attested_adjudication(inventory=inv,repo_root=root)
        self.assertEqual(art.rebind.source_revision,SOURCE_REVISION);self.assertEqual(art.rebind.source_tree,SOURCE_TREE);self.assertEqual(art.rebind.target_revision,inv.revision);self.assertEqual(art.rebind.target_inventory_digest,inv.digest());self.assertEqual(art.rebind.scan_digest,EXPECTED_SCAN_DIGEST)

if __name__=="__main__":unittest.main()

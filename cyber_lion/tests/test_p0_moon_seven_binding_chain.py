from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import subprocess,unittest

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.mediation_falsification import MediationBindingRegistry,MediationFalsificationError,SurfaceBindingResolver
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler
from tools.p0_moon_seven_binding import (
    DIRECT_OBSERVER_BLOCKED,PERMISSION,SEVEN,materialize_seven,
)
from tools.p0_moon_seven_binding_contract import COMPONENT_DOMAINS

REPO="DonkeyJJLove/ai_platform"
EXPECTED_SCAN="d345e96fb1c7c8c4c1ee9bea5672b64d51f290ce7129c860dbf97a5a7907cae2"
EXPECTED_ATTACKS={
    "STALE_EFFECT_KEY","WRONG_EXPECTED_STATE","REPLAYED_EFFECT_KEY","CROSS_EPOCH_BINDING",
    "SURFACE_SUBSTITUTION","PROVIDER_SUBSTITUTION","ENTRYPOINT_SUBSTITUTION",
    "REPOSITORY_SUBSTITUTION","ACTOR_SUBSTITUTION","UNTRUSTED_PERMISSION",
    "STALE_AUTHORITY_SOURCE","CONTROL_ISSUE_SUBSTITUTION",
}

def current_inventory():
    root=Path(__file__).resolve().parents[2]
    sources={}
    for base in (root/"cyber_lion",root/".github/workflows"):
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in {".py",".yml",".yaml"}:
                sources[p.relative_to(root).as_posix()]=p.read_text(encoding="utf-8")
    revision=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    tree=subprocess.check_output(["git","rev-parse","HEAD^{tree}"],cwd=root,text=True).strip()
    raw=EffectSurfaceScanner().scan(repository=REPO,revision=revision,tree_digest=tree,sources=sources)
    inventory,report,_=EffectTaxonomyReconciler().reconcile(raw_inventory=raw,sources=sources)
    return inventory,report

class MoonSevenBindingChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory,cls.taxonomy=current_inventory()
        cls.artifacts=materialize_seven(inventory=cls.inventory)
        cls.known={s.digest():s for s in cls.inventory.surfaces}

    def test_revision_bound_exact_seven_and_scan_digest(self):
        self.assertEqual(self.inventory.scan_digest,EXPECTED_SCAN)
        self.assertEqual(set(SEVEN),set(self.artifacts.candidates))
        self.assertEqual(len(self.artifacts.candidates),7)
        self.assertTrue(set(SEVEN).issubset(self.known))

    def test_all_component_domains_are_explicit_versioned_and_unique(self):
        self.assertEqual(len(COMPONENT_DOMAINS),10)
        self.assertEqual(len(set(COMPONENT_DOMAINS.values())),10)
        for domain in COMPONENT_DOMAINS.values():
            self.assertTrue(domain.startswith(b"LION/MOON-SEVEN-"))
            self.assertTrue(domain.endswith(b"/1"))

    def test_exact_resolution_matrix_is_five_resolved_two_blocked(self):
        plan=self.artifacts.plan
        self.assertEqual(plan.candidate_count,7)
        self.assertEqual(plan.resolved_binding_count,5)
        self.assertEqual(plan.reconstructed_chain_count,5)
        self.assertEqual(plan.blocked_count,2)
        self.assertEqual(plan.bypass_result_count,0)
        self.assertEqual(plan.global_status,"UNKNOWN")
        self.assertFalse(plan.live_falsification_executed)
        blocked={o.surface_digest for o in plan.outcomes if o.status=="BLOCKED"}
        self.assertEqual(blocked,set(DIRECT_OBSERVER_BLOCKED))
        for o in plan.outcomes:
            if o.surface_digest in DIRECT_OBSERVER_BLOCKED:
                self.assertTrue(any(x.startswith("observer_identity:") for x in o.blockers))
                self.assertTrue(any(x.startswith("reconciliation_boundary:") for x in o.blockers))
                self.assertTrue(any(x.startswith("replay_guard:") for x in o.blockers))
            else:
                self.assertEqual(o.status,"RESOLVED")
                self.assertTrue(o.binding_digest)
                self.assertTrue(o.chain_digest)

    def test_resolved_chains_are_bound_to_observed_traces_and_exact_surfaces(self):
        self.assertEqual(set(self.artifacts.bindings),set(SEVEN)-set(DIRECT_OBSERVER_BLOCKED))
        self.assertEqual(set(self.artifacts.chains),set(SEVEN)-set(DIRECT_OBSERVER_BLOCKED))
        for sd,chain in self.artifacts.chains.items():
            chain.validate()
            self.assertEqual(chain.surface_digest,sd)
            self.assertEqual(chain.epoch,"P0-MOON-SEVEN-R1@"+self.inventory.revision[:12])
            self.assertTrue(any(ref.startswith("trace:") for ref in chain.evidence_refs))

    def test_binding_resolver_falsifies_substitution_stale_epoch_and_duplicate(self):
        sd=next(x for x in SEVEN if x not in DIRECT_OBSERVER_BLOCKED and x!=PERMISSION)
        other=next(x for x in SEVEN if x!=sd)
        candidate=self.artifacts.candidates[sd]
        binding=self.artifacts.bindings[sd]
        surface=self.known[sd]
        resolver=SurfaceBindingResolver()
        with self.assertRaises(MediationFalsificationError):
            resolver.resolve(inventory=self.inventory,surface=surface,candidate=replace(candidate,surface_digest=other))
        with self.assertRaises(MediationFalsificationError):
            resolver.resolve(inventory=self.inventory,surface=surface,candidate=replace(candidate,provider_identity="substituted.provider"))
        with self.assertRaises(MediationFalsificationError):
            resolver.resolve(inventory=self.inventory,surface=surface,candidate=replace(candidate,entrypoint_ref="substituted:1:entrypoint"))
        with self.assertRaises(MediationFalsificationError):
            resolver.resolve(inventory=self.inventory,surface=surface,candidate=replace(candidate,inventory_digest="0"*64))
        with self.assertRaises(MediationFalsificationError):
            MediationBindingRegistry(inventory_digest=self.inventory.digest(),epoch="OTHER").register(candidate,binding)
        registry=MediationBindingRegistry(inventory_digest=self.inventory.digest(),epoch=candidate.epoch)
        registry.register(candidate,binding)
        with self.assertRaises(MediationFalsificationError):
            registry.register(candidate,binding)

    def test_attack_matrix_is_exact_bounded_and_not_executed(self):
        attacks=self.artifacts.plan.attacks
        self.assertEqual({a.attack_id for a in attacks},EXPECTED_ATTACKS)
        self.assertEqual(len(attacks),12)
        self.assertEqual(sum(a.execution_class=="SAFE_LIVE_DENIAL" for a in attacks),5)
        self.assertEqual(sum(a.execution_class=="STRUCTURAL_ONLY" for a in attacks),5)
        self.assertEqual(sum(a.execution_class=="BLOCKED_LIVE" for a in attacks),2)
        self.assertTrue(all(not a.target_mutation_allowed for a in attacks))
        self.assertEqual(self.artifacts.plan.bypass_result_count,0)

    def test_falsification_carrier_is_dedicated_unattached_and_non_generic(self):
        carrier=self.artifacts.carrier.validate()
        self.assertEqual(carrier.repository,REPO)
        self.assertEqual(carrier.control_issue,144)
        self.assertEqual(carrier.runner_name,"lion-moon-r9d8-test")
        self.assertEqual(carrier.runner_agent_id,24)
        self.assertEqual(carrier.execution_host,"LION-AUTH-LAB")
        self.assertEqual(carrier.machine_id,"e69aa593257d47b8885d1bd87710b196")
        self.assertEqual(set(carrier.surface_digests),set(SEVEN))
        self.assertEqual(carrier.state,"CANDIDATE_UNATTACHED")
        self.assertTrue(carrier.observation_receipt_required)
        self.assertFalse(carrier.generic_shell)
        self.assertFalse(carrier.arbitrary_command)
        self.assertFalse(carrier.arbitrary_path)
        self.assertFalse(carrier.live_execution)

if __name__=="__main__":unittest.main()

from dataclasses import replace
import unittest

from cyber_lion.contracts.complete_mediation import ConsequentialEffectSurface,EffectSurfaceInventory
from cyber_lion.contracts.mediation_falsification import BypassFalsificationResult,MediationBindingCandidate
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.mediation_falsification import CompleteMediationReassessment,MediationBindingRegistry,MediationFalsificationError,SurfaceBindingResolver

H="a"*64

def inventory():
    return EffectSurfaceScanner().scan(repository="DonkeyJJLove/ai_platform",revision="4"*40,tree_digest="t"*40,sources={"cyber_lion/enterprise/x.py":"from pathlib import Path\ndef f():\n Path('x').write_text('y')\n"})

def candidate(inv,s,**kw):
    d=dict(inventory_digest=inv.digest(),surface_digest=s.digest(),effect_contract_digest=H,pep_identity_digest="b"*64,authority_source_digest="c"*64,currentness_source_digest="d"*64,execution_boundary_digest="e"*64,replay_guard_digest="f"*64,observer_identity_digests=("1"*64,),reconciliation_boundary_digest="2"*64,provider_identity=s.effect_provider,entrypoint_ref=s.entrypoints[0],evidence_refs=("observed:binding",),epoch="E006")
    d.update(kw);return MediationBindingCandidate(**d)

def result(inv,s,attack,outcome="DENIED",**kw):
    d=dict(attack_id=attack,inventory_digest=inv.digest(),surface_digest=s.digest(),attempted_entrypoint=s.entrypoints[0],expected_pep_digest="b"*64,observed_outcome=outcome,evidence_refs=(f"observed:{attack}",),verifier_identity_digest="3"*64,epistemic_state="OBSERVED" if outcome!="UNKNOWN" else "UNKNOWN",epoch="E006")
    d.update(kw);return BypassFalsificationResult(**d)

class MediationFalsificationTests(unittest.TestCase):
    def test_exact_binding_resolution_and_registry(self):
        inv=inventory();s=inv.surfaces[0];c=candidate(inv,s)
        b=SurfaceBindingResolver().resolve(inventory=inv,surface=s,candidate=c)
        reg=MediationBindingRegistry(inventory_digest=inv.digest(),epoch="E006")
        self.assertEqual(reg.register(c,b),b);self.assertEqual(reg.snapshot(),(b,))
        with self.assertRaises(MediationFalsificationError):reg.register(c,b)

    def test_stale_inventory_surface_provider_and_entrypoint_substitution_denied(self):
        inv=inventory();s=inv.surfaces[0];r=SurfaceBindingResolver()
        for c in (candidate(inv,s,inventory_digest="9"*64),candidate(inv,s,surface_digest="8"*64),candidate(inv,s,provider_identity="evil"),candidate(inv,s,entrypoint_ref="evil:1")):
            with self.assertRaises(MediationFalsificationError):r.resolve(inventory=inv,surface=s,candidate=c)

    def test_cross_epoch_binding_replay_denied(self):
        inv=inventory();s=inv.surfaces[0];c=candidate(inv,s,epoch="E005");b=SurfaceBindingResolver().resolve(inventory=inv,surface=s,candidate=c)
        with self.assertRaises(MediationFalsificationError):MediationBindingRegistry(inventory_digest=inv.digest(),epoch="E006").register(c,b)

    def test_missing_binding_keeps_unknown(self):
        inv=inventory();s=inv.surfaces[0]
        out=CompleteMediationReassessment().reassess(inventory=inv,bindings=(),results=(),required_attacks={s.digest():("direct-provider-call",)},observation_evidence_refs=("observed:inventory",))
        self.assertEqual(out.global_status,"UNKNOWN");self.assertEqual(out.surface_statuses[0][1],"UNKNOWN")

    def test_bypass_reaching_effect_marks_unmediated(self):
        inv=inventory();s=inv.surfaces[0];c=candidate(inv,s);b=SurfaceBindingResolver().resolve(inventory=inv,surface=s,candidate=c)
        out=CompleteMediationReassessment().reassess(inventory=inv,bindings=(b,),results=(result(inv,s,"direct-provider-call","REACHED_EFFECT"),),required_attacks={s.digest():("direct-provider-call",)},observation_evidence_refs=("observed:inventory",))
        self.assertEqual(out.surface_statuses[0][1],"UNMEDIATED");self.assertEqual(out.global_status,"UNKNOWN")

    def test_unknown_or_missing_attack_keeps_partial(self):
        inv=inventory();s=inv.surfaces[0];c=candidate(inv,s);b=SurfaceBindingResolver().resolve(inventory=inv,surface=s,candidate=c)
        out=CompleteMediationReassessment().reassess(inventory=inv,bindings=(b,),results=(result(inv,s,"direct-provider-call","UNKNOWN"),),required_attacks={s.digest():("direct-provider-call","replay")},observation_evidence_refs=("observed:inventory",))
        self.assertEqual(out.surface_statuses[0][1],"PARTIAL");self.assertEqual(out.global_status,"UNKNOWN")

    def test_all_required_bypasses_denied_can_mark_surface_mediated(self):
        inv=inventory();s=inv.surfaces[0];c=candidate(inv,s);b=SurfaceBindingResolver().resolve(inventory=inv,surface=s,candidate=c)
        attacks=("direct-provider-call","replay","authority-amplification")
        out=CompleteMediationReassessment().reassess(inventory=inv,bindings=(b,),results=tuple(result(inv,s,a) for a in attacks),required_attacks={s.digest():attacks},observation_evidence_refs=("observed:inventory",))
        self.assertEqual(out.surface_statuses[0][1],"MEDIATED")
        # Scanner evidence is sufficient for this unit fixture only; production R9B must regenerate full checkout inventory.
        self.assertEqual(out.global_status,"PASS")

    def test_unclassified_entrypoint_prevents_global_pass(self):
        inv=EffectSurfaceScanner().scan(repository="r",revision="4"*40,tree_digest="t"*40,sources={"cyber_lion/enterprise/x.py":"def f(c,q):\n c.execute(q)\n"})
        self.assertTrue(inv.unclassified_refs)
        out=CompleteMediationReassessment().reassess(inventory=inv,bindings=(),results=(),required_attacks={},observation_evidence_refs=("observed:inventory",))
        self.assertEqual(out.global_status,"UNKNOWN")

    def test_contracts_have_no_effect_authority_or_selection_methods(self):
        forbidden={"authorize","execute","mutate","select_pep","select_observer","select_currentness"}
        for cls in (MediationBindingCandidate,BypassFalsificationResult,SurfaceBindingResolver,CompleteMediationReassessment):
            self.assertFalse(forbidden & set(dir(cls)))

if __name__=="__main__":unittest.main()

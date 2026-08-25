from __future__ import annotations
import unittest

from cyber_lion.contracts.complete_mediation import MediationBinding
from cyber_lion.contracts.mediation_falsification import BypassFalsificationResult
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.production_mediation import (
    MediationChainReconstructor,ProductionEffectInventory,ProductionMediationClosure,
    ProductionMediationError,classify_unclassified,
)

H=lambda c:c*64

class ProductionMediationTests(unittest.TestCase):
    def inventory(self,source='from pathlib import Path\ndef f():\n    Path("x").write_text("y")\n'):
        return EffectSurfaceScanner().scan(repository="r",revision=H("1"),tree_digest=H("2"),sources={"cyber_lion/enterprise/x.py":source})

    def binding(self,sd):
        return MediationBinding(sd,H("a"),H("b"),H("c"),H("d"),H("e"),(H("f"),),H("9"),("observed:binding",)).validate()

    def result(self,inv,sd,outcome="DENIED",attack="direct-provider-call"):
        return BypassFalsificationResult(attack,inv.digest(),sd,"entry",H("d"),outcome,("ci:observed-bypass",),H("8"),"OBSERVED","E006").validate()

    def test_production_trace_unknown_without_runtime_observation(self):
        inv=self.inventory();traces=ProductionEffectInventory().materialize(inventory=inv,runtime_evidence={})
        self.assertEqual(len(traces),1);self.assertEqual(traces[0].epistemic_state,"UNKNOWN")

    def test_exact_observed_chain_can_close_one_surface(self):
        inv=self.inventory();s=inv.surfaces[0];sd=s.digest()
        traces=ProductionEffectInventory().materialize(inventory=inv,runtime_evidence={sd:("ci:runtime-effect",)})
        b=self.binding(sd)
        chain=MediationChainReconstructor().reconstruct(inventory=inv,trace=traces[0],binding=b,replay_guard_digest=H("6"),bounded_scope_digest=H("7"),verifier_identity_digest=H("8"))
        records,report=ProductionMediationClosure().close(inventory=inv,traces=traces,bindings=(b,),chains=(chain,),results=(self.result(inv,sd),),required_attacks={sd:("direct-provider-call",)},independent_verifier_identity="S16",observation_evidence_refs=("ci:post-effect-observation",))
        self.assertEqual(records[0].status,"MEDIATED");self.assertEqual(report.global_status,"PASS")

    def test_reached_effect_is_unmediated(self):
        inv=self.inventory();s=inv.surfaces[0];sd=s.digest();traces=ProductionEffectInventory().materialize(inventory=inv,runtime_evidence={sd:("ci:runtime-effect",)})
        b=self.binding(sd);chain=MediationChainReconstructor().reconstruct(inventory=inv,trace=traces[0],binding=b,replay_guard_digest=H("6"),bounded_scope_digest=H("7"),verifier_identity_digest=H("8"))
        records,report=ProductionMediationClosure().close(inventory=inv,traces=traces,bindings=(b,),chains=(chain,),results=(self.result(inv,sd,"REACHED_EFFECT"),),required_attacks={sd:("direct-provider-call",)},independent_verifier_identity="S16",observation_evidence_refs=("ci:observation",))
        self.assertEqual(records[0].status,"UNMEDIATED");self.assertEqual(report.global_status,"UNKNOWN")

    def test_missing_chain_is_partial_not_mediated(self):
        inv=self.inventory();sd=inv.surfaces[0].digest();traces=ProductionEffectInventory().materialize(inventory=inv,runtime_evidence={sd:("ci:runtime-effect",)})
        records,report=ProductionMediationClosure().close(inventory=inv,traces=traces,bindings=(self.binding(sd),),chains=(),results=(self.result(inv,sd),),required_attacks={sd:("direct-provider-call",)},independent_verifier_identity="S16",observation_evidence_refs=("ci:observation",))
        self.assertEqual(records[0].status,"PARTIAL");self.assertEqual(report.global_status,"UNKNOWN")

    def test_dynamic_sql_remains_unclassified_and_blocks_global_pass(self):
        inv=self.inventory('def f(cur,q):\n    cur.execute(q)\n')
        self.assertTrue(inv.unclassified_refs)
        classified=classify_unclassified(inv.unclassified_refs)
        self.assertEqual(classified[0].reason,"dynamic-SQL");self.assertEqual(classified[0].epistemic_state,"UNKNOWN")

    def test_trace_set_must_exactly_cover_inventory(self):
        inv=self.inventory()
        with self.assertRaises(ProductionMediationError):
            ProductionMediationClosure().close(inventory=inv,traces=(),bindings=(),chains=(),results=(),required_attacks={},independent_verifier_identity="S16",observation_evidence_refs=())

    def test_tests_and_docs_not_production_surfaces(self):
        inv=EffectSurfaceScanner().scan(repository="r",revision=H("1"),tree_digest=H("2"),sources={"cyber_lion/tests/test_x.py":'open("x","w")',"docs/x.md":"git push"})
        self.assertEqual(inv.surfaces,());self.assertEqual(inv.unclassified_refs,())

if __name__=="__main__":unittest.main()

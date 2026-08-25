import unittest
from dataclasses import replace
from cyber_lion.contracts.bean import BeanContractError,BeanSpec
from cyber_lion.contracts.capability_need import derive_capability_needs
from cyber_lion.contracts.evolutionary_state import GoalContract,WorldSnapshot,SystemSnapshot,derive_gap
from cyber_lion.enterprise.capability_need import CapabilityNeedResolver

class CapabilityNeedTests(unittest.TestCase):
    def goal(self):return GoalContract("g",1,"close gap",(),("capability observed",),("blocked",),(),"none","source").validate()
    def gap(self):
        g=self.goal();w=WorldSnapshot("w","t","t","UNKNOWN",(("problem","unseen-format"),),("world",),("e",),unknowns if False else "",(),()).validate() if False else WorldSnapshot("w","t","t","UNKNOWN",(("problem","unseen-format"),),("world",),("e",),"",(),()).validate()
        s=SystemSnapshot("s","t","t","UNKNOWN","repo","sha","tree",(("capability","missing"),),(),("repo",),"",("parse.unseen",),()).validate()
        return derive_gap(gap_id="gap",goal=g,world=w,system=s,missing_capabilities=("parse.unseen",),unsatisfied_conditions=("cannot parse unseen format",),evidence_refs=("e",),falsification_conditions=("parser fails fixture",))
    def need(self):
        gap=self.gap();return derive_capability_needs(gap=gap,goal_digest=gap.goal_digest,capability_requirements=(("parse.unseen",("raw",),("normalized",),"none"),),provenance_refs=("gap-evidence",))[0]
    def spec(self,cap="parse.unseen"):
        n=self.need();return BeanSpec(bean_id="existing",bean_type="adapter",version="1",purpose="existing",goal_digest=n.goal_digest,success_conditions=("ok",),stop_conditions=("done",),defer_conditions=("unknown",),inputs=("raw",),outputs=("normalized",),interfaces=("v1",),required_capabilities=(),provided_capabilities=(cap,),authority_ceiling="none",required_grants=(),epistemic_requirements=("OBSERVED",),evidence_requirements=("e",),provenance_policy=("p",),memory_policy=("m",),context_policy=("c",),observability_requirements=(),resource_budget=("r",),cost_budget="c",time_budget="t",runtime_class="r",sandbox_class="s",dependencies=(),compatibility_constraints=("v1",),failure_modes=("f",),degradation_policy=("d",),revocation_policy=("r",),security_invariants=("i",),acceptance_tests=("a",),falsification_conditions=("x",),evolution_hooks=("e",),replacement_policy=("r",),supersession_policy=("s",)).validate()
    def test_need_is_exactly_gap_derived_and_non_effectful(self):
        n=self.need();self.assertEqual(n.required_capability,"parse.unseen");self.assertEqual(n.authority_effect,"NONE")
    def test_silent_capability_substitution_denied(self):
        gap=self.gap()
        with self.assertRaises(BeanContractError):derive_capability_needs(gap=gap,goal_digest=gap.goal_digest,capability_requirements=(("different",(),(),"none"),),provenance_refs=("e",))
    def test_silent_omission_denied(self):
        gap=self.gap()
        with self.assertRaises(BeanContractError):derive_capability_needs(gap=gap,goal_digest=gap.goal_digest,capability_requirements=(),provenance_refs=("e",))
    def test_goal_substitution_denied(self):
        gap=self.gap()
        with self.assertRaises(BeanContractError):derive_capability_needs(gap=gap,goal_digest="9"*64,capability_requirements=(("parse.unseen",(),(),"none"),),provenance_refs=("e",))
    def test_existing_bean_is_reused_when_exactly_compatible(self):
        r=CapabilityNeedResolver().resolve(need=self.need(),catalog=(self.spec(),));self.assertEqual(r.disposition,"USE_EXISTING");self.assertIsNone(r.generated_spec)
    def test_missing_capability_generates_spec_not_build(self):
        r=CapabilityNeedResolver().resolve(need=self.need(),catalog=());self.assertEqual(r.disposition,"GENERATE_SPEC");self.assertIn("no-build-without-external-builder-permit",r.generated_spec.security_invariants);self.assertFalse(hasattr(r.generated_spec,"build"));self.assertFalse(hasattr(r.generated_spec,"grant"))
    def test_incompatible_existing_bean_is_not_silent_substitute(self):
        bad=replace(self.spec(),outputs=("wrong",));r=CapabilityNeedResolver().resolve(need=self.need(),catalog=(bad,));self.assertEqual(r.disposition,"GENERATE_SPEC")
    def test_resolution_is_deterministic_under_catalog_order(self):
        a=self.spec();b=replace(a,bean_id="existing-b")
        x=CapabilityNeedResolver().resolve(need=self.need(),catalog=(a,b));y=CapabilityNeedResolver().resolve(need=self.need(),catalog=(b,a));self.assertEqual(x.existing_spec_digest,y.existing_spec_digest)

if __name__=="__main__":unittest.main()

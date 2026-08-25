import unittest
from dataclasses import replace

from cyber_lion.contracts.bean import BeanSpec
from cyber_lion.contracts.bean_composition import CompositionRequest
from cyber_lion.enterprise.bean_composition import BeanDescriptor,CompositionEngine,CompositionError

class BeanCompositionTests(unittest.TestCase):
    def spec(self,bean_id,bean_type,provided,*,required=(),inputs=(),outputs=(),deps=(),authority="none",obs=()):
        return BeanSpec(bean_id=bean_id,bean_type=bean_type,version="1",purpose=bean_id,goal_digest="1"*64,
          success_conditions=("ok",),stop_conditions=("done",),defer_conditions=("unknown",),inputs=inputs,outputs=outputs,interfaces=("v1",),
          required_capabilities=required,provided_capabilities=provided,authority_ceiling=authority,required_grants=(),epistemic_requirements=("OBSERVED",),evidence_requirements=("e",),provenance_policy=("p",),memory_policy=("m",),context_policy=("c",),observability_requirements=obs,resource_budget=("bounded",),cost_budget="bounded",time_budget="bounded",runtime_class="test",sandbox_class="test",dependencies=deps,compatibility_constraints=("v1",),failure_modes=("f",),degradation_policy=("deny",),revocation_policy=("revoke",),security_invariants=("no-mint",),acceptance_tests=("a",),falsification_conditions=("x",),evolution_hooks=("g",),replacement_policy=("r",),supersession_policy=("s",)).validate()
    def d(self,s,family,resource=1,cost=1,impl=None): return BeanDescriptor(s,impl or (s.bean_id[0].encode().hex()*64)[:64],family,resource,cost)
    def request(self,**kw):
        v=dict(composition_id="C",mission_id="M",goal_digest="1"*64,required_capabilities=("result",),external_allowed_capabilities=("source",),mission_inputs=("raw",),max_resource_units=10,max_cost_units=10,required_observability_channels=("effect",),observability_quorum=1,consequential=True,mission_authority_ceiling="local_write",conflict_pairs=(),provenance_refs=("gap:e006",))
        v.update(kw);return CompositionRequest(**v)
    def catalog(self):
        builder=self.spec("builder","builder",("result",),required=("source",),inputs=("raw",),outputs=("candidate",),authority="local_write",obs=("build",))
        verifier=self.spec("verifier","verifier",("verify",),inputs=("candidate",),outputs=("verified",),obs=("verify",))
        observer=self.spec("observer","observer",("observe",),inputs=(),outputs=("observation",),obs=("effect",))
        return (self.d(builder,"builder-family",impl="2"*64),self.d(verifier,"verifier-family",impl="3"*64),self.d(observer,"observer-family",impl="4"*64))
    def test_valid_consequential_composition_is_deterministic(self):
        e=CompositionEngine();a=e.compose(request=self.request(),candidates=self.catalog());b=e.compose(request=self.request(),candidates=tuple(reversed(self.catalog())))
        self.assertEqual(a.digest(),b.digest());self.assertEqual({x.bean_id for x in a.bean_bindings},{"builder","verifier","observer"})
    def test_missing_capability_denied(self):
        with self.assertRaises(CompositionError):CompositionEngine().compose(request=self.request(required_capabilities=("missing",)),candidates=self.catalog())
    def test_interface_mismatch_denied(self):
        cat=list(self.catalog());cat[0]=self.d(replace(cat[0].spec,inputs=("unavailable",)),"builder-family",impl="2"*64)
        with self.assertRaises(CompositionError):CompositionEngine().compose(request=self.request(),candidates=tuple(cat))
    def test_dependency_cycle_denied(self):
        a=self.spec("a","adapter",("result",),deps=("b",));b=self.spec("b","adapter",("x",),deps=("a",));obs=self.spec("o","observer",("observe",),obs=("effect",));ver=self.spec("v","verifier",("verify",))
        cat=(self.d(a,"fa",impl="a"*64),self.d(b,"fb",impl="b"*64),self.d(obs,"fo",impl="c"*64),self.d(ver,"fv",impl="d"*64))
        with self.assertRaises(CompositionError):CompositionEngine().compose(request=self.request(),candidates=cat)
    def test_conflict_denied(self):
        with self.assertRaises(CompositionError):CompositionEngine().compose(request=self.request(conflict_pairs=("builder|verifier",)),candidates=self.catalog())
    def test_resource_budget_denied(self):
        with self.assertRaises(CompositionError):CompositionEngine().compose(request=self.request(max_resource_units=2),candidates=self.catalog())
    def test_observability_quorum_denied(self):
        with self.assertRaises(CompositionError):CompositionEngine().compose(request=self.request(observability_quorum=2,required_observability_channels=("effect","second")),candidates=self.catalog())
    def test_builder_verifier_provider_collusion_denied(self):
        cat=list(self.catalog());v=cat[1];cat[1]=BeanDescriptor(v.spec,v.implementation_digest,"builder-family",1,1)
        with self.assertRaises(CompositionError):CompositionEngine().compose(request=self.request(),candidates=tuple(cat))
    def test_builder_verifier_implementation_collusion_denied(self):
        cat=list(self.catalog());v=cat[1];cat[1]=BeanDescriptor(v.spec,"2"*64,"verifier-family",1,1)
        with self.assertRaises(CompositionError):CompositionEngine().compose(request=self.request(),candidates=tuple(cat))
    def test_authority_amplification_denied(self):
        cat=list(self.catalog());cat[0]=self.d(replace(cat[0].spec,authority_ceiling="deploy"),"builder-family",impl="2"*64)
        with self.assertRaises(CompositionError):CompositionEngine().compose(request=self.request(mission_authority_ceiling="financial"),candidates=tuple(cat))
    def test_financial_and_deploy_remain_incomparable(self):
        cat=list(self.catalog());cat[0]=self.d(replace(cat[0].spec,authority_ceiling="deploy"),"builder-family",impl="2"*64)
        with self.assertRaises(CompositionError):CompositionEngine().compose(request=self.request(mission_authority_ceiling="financial"),candidates=tuple(cat))
    def test_composition_has_no_grant_or_effect_surface(self):
        c=CompositionEngine().compose(request=self.request(),candidates=self.catalog())
        for field in ("grant","credential","authority_effect","execution_effect","external_effect"):self.assertFalse(hasattr(c,field))

if __name__=="__main__":unittest.main()

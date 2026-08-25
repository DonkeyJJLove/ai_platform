import unittest
from dataclasses import replace
from cyber_lion.contracts.bean import BeanContractError,BeanSpec
from cyber_lion.contracts.bean_composition import CompositionBeanBinding,CompositionContract
from cyber_lion.contracts.mosaic import advance_mosaic
from cyber_lion.enterprise.mosaic import HeterogeneousMosaicPlanner,bean_to_agent_spec

class DynamicMosaicTests(unittest.TestCase):
    def spec(self,bid,btype,cap,authority="none",obs=()):return BeanSpec(bean_id=bid,bean_type=btype,version="1",purpose=bid,goal_digest="1"*64,success_conditions=("ok",),stop_conditions=("done",),defer_conditions=("unknown",),inputs=(),outputs=(cap,),interfaces=("v1",),required_capabilities=(),provided_capabilities=(cap,),authority_ceiling=authority,required_grants=(),epistemic_requirements=("OBSERVED",),evidence_requirements=("e",),provenance_policy=("p",),memory_policy=("read",),context_policy=("c",),observability_requirements=obs,resource_budget=("r",),cost_budget="1",time_budget="30s",runtime_class="analysis",sandbox_class="isolated",dependencies=(),compatibility_constraints=("v1",),failure_modes=("f",),degradation_policy=("d",),revocation_policy=("r",),security_invariants=("i",),acceptance_tests=("a",),falsification_conditions=("x",),evolution_hooks=("e",),replacement_policy=("r",),supersession_policy=("s",)).validate()
    def setup(self):
        specs={"agent-a":self.spec("agent-a","agent","reason"),"builder-b":self.spec("builder-b","builder","build"),"verifier-v":self.spec("verifier-v","verifier","verify"),"observer-o":self.spec("observer-o","observer","observe",obs=("effect",)),"reconciler-r":self.spec("reconciler-r","reconciler","reconcile")}
        bindings=tuple(CompositionBeanBinding(k,s.spec_digest(),str(i+2)*64 if i<8 else "f"*64,f"family-{k}",1,1).validate() for i,(k,s) in enumerate(sorted(specs.items())))
        c=CompositionContract("comp","mission","1"*64,bindings,("reason","build","verify","observe","reconcile"),("build","observe","reason","reconcile","verify"),(),(),("effect",),("verifier-v",),("observer-o",),"read",5,5,("gap",)).validate()
        return specs,c
    def test_heterogeneous_formation_preserves_all_members(self):
        specs,c=self.setup();m=HeterogeneousMosaicPlanner().form(mosaic_id="m",composition=c,specs=specs,evidence_refs=("formation",));self.assertEqual({x.bean_type for x in m.members},{"agent","builder","verifier","observer","reconciler"});self.assertEqual(m.lifecycle_state,"FORM");self.assertEqual(m.authority_effect,"NONE")
    def test_full_mosaic_lifecycle(self):
        specs,c=self.setup();m=HeterogeneousMosaicPlanner().form(mosaic_id="m",composition=c,specs=specs,evidence_refs=("formation",));m=advance_mosaic(m,"ATTEST",evidence_refs=("attestation",));m=advance_mosaic(m,"OPERATE",evidence_refs=("operation",));m=advance_mosaic(m,"OBSERVE",evidence_refs=("observation",));m=advance_mosaic(m,"RECONCILE",evidence_refs=("reconciliation",));m=advance_mosaic(m,"DISSOLVE",evidence_refs=("dissolve",),reason="mission closed");self.assertEqual(m.lifecycle_state,"DISSOLVE")
    def test_lifecycle_skip_denied(self):
        specs,c=self.setup();m=HeterogeneousMosaicPlanner().form(mosaic_id="m",composition=c,specs=specs,evidence_refs=("formation",));
        with self.assertRaises(BeanContractError):advance_mosaic(m,"OPERATE",evidence_refs=("operation",))
    def test_missing_member_substitution_denied(self):
        specs,c=self.setup();specs.pop("observer-o")
        with self.assertRaises(BeanContractError):HeterogeneousMosaicPlanner().form(mosaic_id="m",composition=c,specs=specs,evidence_refs=("formation",))
    def test_spec_digest_substitution_denied(self):
        specs,c=self.setup();specs["agent-a"]=replace(specs["agent-a"],purpose="changed")
        with self.assertRaises(BeanContractError):HeterogeneousMosaicPlanner().form(mosaic_id="m",composition=c,specs=specs,evidence_refs=("formation",))
    def test_agent_bean_projects_to_existing_agent_spec(self):
        s=self.spec("agent-a","agent","reason");a=bean_to_agent_spec(spec=s,mission_id="mission");self.assertEqual(a.agent_id,"agent-a");self.assertEqual(a.capabilities,("reason",))
    def test_nonagent_cannot_masquerade_as_agent(self):
        with self.assertRaises(BeanContractError):bean_to_agent_spec(spec=self.spec("builder","builder","build"),mission_id="mission")

if __name__=="__main__":unittest.main()

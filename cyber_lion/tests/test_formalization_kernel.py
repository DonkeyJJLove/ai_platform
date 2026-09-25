import dataclasses, unittest
from cyber_lion.tests.formalization_test_support import *
class FormalizationKernelTests(unittest.TestCase):
    def test_registry_is_sealed_and_unique(self):
        r=registry(); self.assertEqual(r.authority_effect,"NONE"); self.assertEqual(len(r.entries),len({x.artifact_id for x in r.entries}))
    def test_duplicate_registry_path_fails(self):
        r=registry(); dup=dataclasses.replace(r.entries[1],artifact_id="other-id",path=r.entries[0].path)
        with self.assertRaises(Exception): dataclasses.replace(r,entries=r.entries+(dup,),registry_digest="").sealed()
    def test_closure_authority_effect_must_remain_none(self):
        r,m,c=self._closure(); bad=dataclasses.replace(c,authority_effect="MERGE")
        with self.assertRaises(Exception): bad.sealed(m,r)
    def test_required_set_is_deterministic(self):
        r=registry(); m=manifest(r); a=derive_required_formalization_set(m,r); b=derive_required_formalization_set(m,r); self.assertEqual(a.set_digest,b.set_digest); self.assertEqual(a.items,b.items)
    def test_duplicate_semantic_owner_fails(self):
        r=registry(); m=manifest(r); bad=dataclasses.replace(m,semantic_owner_delta=m.semantic_owner_delta+m.semantic_owner_delta,manifest_digest="")
        with self.assertRaises(Exception): bad.sealed(r)
    def test_unknown_formalization_artifact_fails(self):
        r=registry(); u=global_updates()+(FormalizationUpdate("missing-artifact","UPDATE","must fail"),)
        with self.assertRaises(Exception): manifest(r,formalization_updates=u)
    def test_architecture_concept_without_contract_catalog_fails(self):
        r=registry(); u=tuple(x for x in global_updates() if x.artifact_id!="contract-catalog")
        with self.assertRaises(Exception): manifest(r,formalization_updates=u)
    def test_architecture_concept_without_projection_fails(self):
        r=registry(); u=tuple(x for x in global_updates() if x.artifact_id!="architecture-projection")
        with self.assertRaises(Exception): manifest(r,formalization_updates=u)
    def test_architecture_concept_without_evolution_eval_fails(self):
        r=registry(); u=tuple(x for x in global_updates() if x.artifact_id!="evolution-evals")
        with self.assertRaises(Exception): manifest(r,formalization_updates=u)
    def test_new_top_level_plane_fails(self):
        r=registry(); m=manifest(r); lb=(LayerBinding("test_concept",("EVOLUTIONARY_EPOCH",),True),)
        with self.assertRaises(Exception): dataclasses.replace(m,layer_bindings=lb,manifest_digest="").sealed(r)
    def test_stale_updated_surface_without_invalidation_fails(self):
        r=registry(); u=global_updates(); inv=tuple(x.artifact_id for x in u if x.operation in {"UPDATE","REGENERATE","ADD","SUPERSEDE"} and x.artifact_id!="contract-catalog")
        with self.assertRaises(Exception): manifest(r,currentness_invalidations=inv)
    def test_manifest_digest_substitution_fails(self):
        r=registry(); m=manifest(r); with_bad=dataclasses.replace(m,manifest_digest="f"*64)
        with self.assertRaises(Exception): with_bad.validate(r)
    def test_authority_effect_must_remain_none(self):
        r=registry(); m=manifest(r); bad=dataclasses.replace(m,authority_effect="WRITE",manifest_digest="")
        with self.assertRaises(Exception): bad.sealed(r)
    def test_binding_is_non_effectful(self):
        b=FormalizationProposalBinding("bind:test","4"*64,"5"*64).sealed(); self.assertEqual(b.authority_effect,"NONE"); self.assertEqual(b.execution_effect,"NONE")
    def _closure(self,decision="PASS",unknowns=(),currentness="CURRENT_CANDIDATE",eval_result="PASS",rag="PASS",disc="PASS"):
        r=registry(); m=manifest(r); req=derive_required_formalization_set(m,r); ars=[]
        for x in req.items:
            state="NOT_APPLICABLE" if x.classification=="NOT_APPLICABLE" else "PASS"; ars.append(ArtifactResult(x.artifact_id,x.classification,state,("evidence:"+x.artifact_id,)))
        return r,m,FormalizationClosureRecord("fcr:test",CandidateBinding("6"*64,"7"*40,"8"*40,"9"*64),m.manifest_digest,tuple(ars),"PASS","PASS",disc,rag,(GateResult("t1","PASS",("test",)),),(GateResult("e1",eval_result,("eval",)),),currentness,tuple(unknowns),decision)
    def test_closure_pass(self):
        r,m,c=self._closure(); self.assertEqual(c.sealed(m,r).decision,"PASS")
    def test_closure_with_unknown_fails(self):
        r,m,c=self._closure(unknowns=("u",))
        with self.assertRaises(Exception): c.sealed(m,r)
    def test_closure_with_failed_eval_fails(self):
        r,m,c=self._closure(eval_result="FAIL")
        with self.assertRaises(Exception): c.sealed(m,r)
    def test_closure_without_rag_probe_pass_fails(self):
        r,m,c=self._closure(rag="UNKNOWN")
        with self.assertRaises(Exception): c.sealed(m,r)
    def test_closure_without_discoverability_fails(self):
        r,m,c=self._closure(disc="UNKNOWN")
        with self.assertRaises(Exception): c.sealed(m,r)
    def test_candidate_substitution_fails_through_digest_tamper(self):
        r,m,c=self._closure(); sealed=c.sealed(m,r); bad=dataclasses.replace(sealed,candidate=CandidateBinding("a"*64,sealed.candidate.head,sealed.candidate.tree,sealed.candidate.verification_digest))
        with self.assertRaises(Exception): bad.validate(m,r)
if __name__=="__main__": unittest.main()

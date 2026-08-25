import unittest
from dataclasses import replace
from cyber_lion.contracts.bean import BeanContractError,BeanSpec
from cyber_lion.contracts.bean_builder_bridge import bind_bean_to_builder_permit,detached_repository_candidate_to_bean_candidate
from cyber_lion.contracts.builder_invocation_permit import BuilderInvocationPermit,SCHEMA_VERSION,BUILDER_CAPABILITY_CLASS,compute_builder_invocation_replay_digest
from cyber_lion.contracts.repository_mutation import DetachedRepositoryCandidate

class BeanBuilderBridgeTests(unittest.TestCase):
    def spec(self):return BeanSpec(bean_id="generated:parse.unseen",bean_type="adapter",version="1",purpose="parse unseen",goal_digest="1"*64,success_conditions=("ok",),stop_conditions=("done",),defer_conditions=("unknown",),inputs=("raw",),outputs=("normalized",),interfaces=("v1",),required_capabilities=(),provided_capabilities=("parse.unseen",),authority_ceiling="none",required_grants=(),epistemic_requirements=("OBSERVED",),evidence_requirements=("e",),provenance_policy=("p",),memory_policy=("m",),context_policy=("c",),observability_requirements=(),resource_budget=("r",),cost_budget="c",time_budget="t",runtime_class="candidate",sandbox_class="detached",dependencies=(),compatibility_constraints=("v1",),failure_modes=("f",),degradation_policy=("d",),revocation_policy=("r",),security_invariants=("no-authority",),acceptance_tests=("a",),falsification_conditions=("x",),evolution_hooks=("e",),replacement_policy=("r",),supersession_policy=("s",)).validate()
    def permit(self):
        kwargs=dict(source_builder_entry_permit_id="bep:1",source_builder_entry_permit_digest="1"*64,source_builder_entry_replay_digest="2"*64,repository="DonkeyJJLove/ai_platform",baseline_master_sha="a"*40,baseline_master_tree_sha="b"*40,current_baseline_digest="3"*64,action="BUILD_CANDIDATE",candidate_scope=("cyber_lion/generated_adapter.py",),resource_scope=("repo-path:DonkeyJJLove/ai_platform:cyber_lion/generated_adapter.py",),authority_epoch=6,authority_state_version=1,root_grant_id="grant:1",root_grant_digest="4"*64,current_authority_digest="5"*64,builder_subject_id="builder:1",builder_instance_id="builder-instance:1",builder_capability_class=BUILDER_CAPABILITY_CLASS,builder_identity_digest="6"*64,builder_implementation_digest="7"*64,builder_attestation_digest="8"*64,current_builder_subject_digest="9"*64)
        replay=compute_builder_invocation_replay_digest(**kwargs)
        return BuilderInvocationPermit(schema_version=SCHEMA_VERSION,builder_invocation_permit_id=f"bip:{replay}",checked_at="2026-08-25T22:00:00Z",builder_invocation_replay_digest=replay,**kwargs).sealed()
    def candidate(self):return DetachedRepositoryCandidate(repository="DonkeyJJLove/ai_platform",branch="mission/e006-test",expected_head_sha="a"*40,expected_parent_sha="a"*40,candidate_commit_sha="c"*40,candidate_tree_sha="d"*40,changed_paths=("cyber_lion/generated_adapter.py",),builder_id="builder:1",prepared_at="2026-08-25T22:01:00Z").validate()
    def test_existing_builder_permit_binds_spec_without_minting_authority(self):
        b=bind_bean_to_builder_permit(spec=self.spec(),permit=self.permit(),evidence_refs=("need:1",));self.assertEqual(b.authority_effect,"NONE");self.assertEqual(b.candidate_scope,("cyber_lion/generated_adapter.py",))
    def test_detached_candidate_becomes_built_bean_candidate(self):
        spec=self.spec();p=self.permit();b=bind_bean_to_builder_permit(spec=spec,permit=p,evidence_refs=("need:1",));c=detached_repository_candidate_to_bean_candidate(binding=b,spec=spec,permit=p,candidate=self.candidate(),builder_identity_digest="6"*64);self.assertEqual(c.state,"BUILT");self.assertEqual(c.authority_effect,"NONE")
    def test_scope_substitution_denied(self):
        spec=self.spec();p=self.permit();b=bind_bean_to_builder_permit(spec=spec,permit=p,evidence_refs=("need:1",));c=replace(self.candidate(),changed_paths=("cyber_lion/other.py",))
        with self.assertRaises(BeanContractError):detached_repository_candidate_to_bean_candidate(binding=b,spec=spec,permit=p,candidate=c,builder_identity_digest="6"*64)
    def test_spec_substitution_denied(self):
        spec=self.spec();p=self.permit();b=bind_bean_to_builder_permit(spec=spec,permit=p,evidence_refs=("need:1",));changed=replace(spec,purpose="different")
        with self.assertRaises(BeanContractError):detached_repository_candidate_to_bean_candidate(binding=b,spec=changed,permit=p,candidate=self.candidate(),builder_identity_digest="6"*64)
    def test_permit_substitution_denied(self):
        spec=self.spec();p=self.permit();b=bind_bean_to_builder_permit(spec=spec,permit=p,evidence_refs=("need:1",));p2=replace(p,builder_invocation_permit_digest="f"*64)
        with self.assertRaises(Exception):detached_repository_candidate_to_bean_candidate(binding=b,spec=spec,permit=p2,candidate=self.candidate(),builder_identity_digest="6"*64)
    def test_bridge_does_not_expose_builder_launch_or_effect(self):
        b=bind_bean_to_builder_permit(spec=self.spec(),permit=self.permit(),evidence_refs=("need:1",));self.assertFalse(hasattr(b,"launch"));self.assertFalse(hasattr(b,"execute"));self.assertFalse(hasattr(b,"grant"))

if __name__=="__main__":unittest.main()

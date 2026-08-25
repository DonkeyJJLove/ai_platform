from dataclasses import replace
import unittest

from cyber_lion.contracts.builder_entry_permit import (
    BUILDER_CAPABILITY_CLASS, BuilderEntryPermit, BuilderEntryPermitContractError,
    SCHEMA_VERSION, TrustedBuilderSubject, compute_builder_entry_replay_digest,
)

D=lambda c:c*64
S=lambda c:c*40
REPO="DonkeyJJLove/ai_platform"
SCOPE=("cyber_lion/example.py",)
RES=(f"repo-path:{REPO}:cyber_lion/example.py",)


def subject():
    return TrustedBuilderSubject(
        builder_subject_id="builder-R17",builder_instance_id="instance-01",
        capability_class=BUILDER_CAPABILITY_CLASS,repository=REPO,
        candidate_scope=SCOPE,resource_scope=RES,identity_digest=D("1"),
        implementation_digest=D("2"),attestation_digest=D("3"),
        valid_from="2026-08-25T00:00:00+00:00",expires_at="2026-08-26T00:00:00+00:00",
    ).sealed()


def permit():
    kw=dict(
        source_consumption_permit_id="cbcp:"+D("4"),source_consumption_permit_digest=D("5"),source_consumption_replay_digest=D("4"),
        repository=REPO,baseline_master_sha=S("a"),baseline_master_tree_sha=S("b"),current_baseline_digest=D("6"),
        action="BUILD_CANDIDATE",candidate_scope=SCOPE,resource_scope=RES,authority_epoch=4,authority_state_version=9,
        root_grant_id="root-R17",root_grant_digest=D("7"),current_authority_digest=D("8"),
        builder_subject_id="builder-R17",builder_instance_id="instance-01",builder_capability_class=BUILDER_CAPABILITY_CLASS,
        builder_identity_digest=D("1"),builder_implementation_digest=D("2"),builder_attestation_digest=D("3"),
    )
    replay=compute_builder_entry_replay_digest(**kw)
    return BuilderEntryPermit(schema_version=SCHEMA_VERSION,builder_entry_permit_id="bep:"+replay,checked_at="2026-08-25T01:00:00+00:00",builder_entry_replay_digest=replay,**kw).sealed()


class BuilderEntryPermitContractTests(unittest.TestCase):
    def test_trusted_subject_is_immutable_sealed_and_scope_bound(self):
        s=subject(); self.assertEqual(s.subject_digest,s.compute_digest())
        with self.assertRaises(Exception): s.builder_instance_id="other"
        with self.assertRaises(BuilderEntryPermitContractError): replace(s,capability_class="WRITE_REF",subject_digest="").sealed()
        with self.assertRaises(BuilderEntryPermitContractError): replace(s,resource_scope=(f"repo-path:{REPO}:other.py",),subject_digest="").sealed()

    def test_permit_is_sealed_non_effectful_and_source_bound(self):
        p=permit(); self.assertEqual(p.builder_entry_permit_digest,p.compute_digest()); self.assertEqual(p.builder_entry_permit_id,"bep:"+p.builder_entry_replay_digest)
        self.assertEqual((p.authority_effect,p.execution_effect,p.repository_ref_effect,p.external_effect),("NONE","NONE","NONE","NONE"))
        with self.assertRaises(Exception): p.action="MERGE"

    def test_replay_digest_and_id_substitution_fail(self):
        p=permit()
        with self.assertRaises(BuilderEntryPermitContractError): replace(p,builder_entry_replay_digest=D("9"),builder_entry_permit_digest="").sealed()
        with self.assertRaises(BuilderEntryPermitContractError): replace(p,builder_entry_permit_id="bep:"+D("9"),builder_entry_permit_digest="").sealed()

    def test_coherent_builder_field_reseal_fails(self):
        p=permit()
        forged=replace(p,builder_subject_id="builder-other",builder_instance_id="instance-other",builder_entry_permit_digest="")
        with self.assertRaises(BuilderEntryPermitContractError): forged.sealed()

    def test_coherent_scope_widening_reseal_fails(self):
        p=permit(); scope=("cyber_lion/example.py","cyber_lion/extra.py"); res=tuple(f"repo-path:{REPO}:{x}" for x in scope)
        with self.assertRaises(BuilderEntryPermitContractError): replace(p,candidate_scope=scope,resource_scope=res,builder_entry_permit_digest="").sealed()

    def test_repository_and_baseline_substitution_reseal_fail(self):
        p=permit()
        scope=p.candidate_scope; other="DonkeyJJLove/glitchlab"; res=tuple(f"repo-path:{other}:{x}" for x in scope)
        for forged in (
            replace(p,repository=other,resource_scope=res,builder_entry_permit_digest=""),
            replace(p,baseline_master_sha=S("c"),builder_entry_permit_digest=""),
            replace(p,current_baseline_digest=D("a"),builder_entry_permit_digest=""),
            replace(p,current_authority_digest=D("b"),builder_entry_permit_digest=""),
            replace(p,builder_implementation_digest=D("c"),builder_entry_permit_digest=""),
            replace(p,builder_attestation_digest=D("d"),builder_entry_permit_digest=""),
        ):
            with self.assertRaises(BuilderEntryPermitContractError): forged.sealed()

    def test_cross_action_and_effect_widening_fail(self):
        p=permit()
        for action in ("RUN_TEST","REQUEST_PR","fast_forward_ref","MERGE","DEPLOY","RELEASE"):
            with self.assertRaises(BuilderEntryPermitContractError): replace(p,action=action,builder_entry_permit_digest="").sealed()
        with self.assertRaises(BuilderEntryPermitContractError): replace(p,repository_ref_effect="fast_forward_ref",builder_entry_permit_digest="").sealed()

if __name__=="__main__": unittest.main()

from dataclasses import replace
import unittest

from cyber_lion.contracts.builder_invocation_permit import (
    BUILDER_CAPABILITY_CLASS,
    SCHEMA_VERSION,
    BuilderInvocationPermit,
    BuilderInvocationPermitContractError,
    compute_builder_invocation_replay_digest,
)

D = lambda c: c * 64
S = lambda c: c * 40
REPO = "DonkeyJJLove/ai_platform"
SCOPE = ("cyber_lion/example.py",)
RES = (f"repo-path:{REPO}:cyber_lion/example.py",)


def permit():
    kwargs = dict(
        source_builder_entry_permit_id="bep:" + D("1"),
        source_builder_entry_permit_digest=D("2"),
        source_builder_entry_replay_digest=D("3"),
        repository=REPO,
        baseline_master_sha=S("a"),
        baseline_master_tree_sha=S("b"),
        current_baseline_digest=D("4"),
        action="BUILD_CANDIDATE",
        candidate_scope=SCOPE,
        resource_scope=RES,
        authority_epoch=4,
        authority_state_version=9,
        root_grant_id="root-R19",
        root_grant_digest=D("5"),
        current_authority_digest=D("6"),
        builder_subject_id="builder-R19",
        builder_instance_id="instance-R19",
        builder_capability_class=BUILDER_CAPABILITY_CLASS,
        builder_identity_digest=D("7"),
        builder_implementation_digest=D("8"),
        builder_attestation_digest=D("9"),
        current_builder_subject_digest=D("a"),
    )
    replay = compute_builder_invocation_replay_digest(**kwargs)
    return BuilderInvocationPermit(
        schema_version=SCHEMA_VERSION,
        builder_invocation_permit_id="bip:" + replay,
        checked_at="2026-08-25T08:20:00+00:00",
        builder_invocation_replay_digest=replay,
        **kwargs,
    ).sealed()


class BuilderInvocationPermitContractTests(unittest.TestCase):
    def test_sealed_permit_is_deterministic_and_non_effectful(self):
        value = permit()
        value.validate()
        self.assertEqual(value.builder_invocation_permit_id, "bip:" + value.builder_invocation_replay_digest)
        self.assertEqual(value.builder_invocation_replay_digest, value.compute_builder_invocation_replay_digest())
        self.assertEqual(value.builder_invocation_permit_digest, value.compute_digest())
        self.assertEqual((value.authority_effect, value.execution_effect, value.repository_ref_effect, value.external_effect), ("NONE", "NONE", "NONE", "NONE"))

    def test_id_substitution_denied(self):
        with self.assertRaises(BuilderInvocationPermitContractError):
            replace(permit(), builder_invocation_permit_id="bip:" + D("f")).validate()

    def test_replay_digest_substitution_denied(self):
        with self.assertRaises(BuilderInvocationPermitContractError):
            replace(permit(), builder_invocation_replay_digest=D("f"), builder_invocation_permit_digest="").validate()

    def test_source_permit_substitution_denied_even_with_outer_digest_cleared(self):
        value = replace(permit(), source_builder_entry_permit_digest=D("f"), builder_invocation_permit_digest="")
        with self.assertRaises(BuilderInvocationPermitContractError):
            value.validate()
        with self.assertRaises(BuilderInvocationPermitContractError):
            value.sealed()

    def test_scope_widening_denied_even_with_reseal_attempt(self):
        value = permit()
        widened = replace(value, candidate_scope=SCOPE + ("cyber_lion/extra.py",), builder_invocation_permit_digest="")
        with self.assertRaises(BuilderInvocationPermitContractError):
            widened.sealed()

    def test_action_and_capability_transfer_denied(self):
        for field, value in (("action", "RUN_TEST"), ("builder_capability_class", "ANY")):
            with self.assertRaises(BuilderInvocationPermitContractError):
                replace(permit(), **{field: value, "builder_invocation_permit_digest": ""}).validate()

    def test_builder_subject_digest_substitution_denied(self):
        with self.assertRaises(BuilderInvocationPermitContractError):
            replace(permit(), current_builder_subject_digest=D("f"), builder_invocation_permit_digest="").validate()

    def test_state_and_effect_widening_denied(self):
        with self.assertRaises(BuilderInvocationPermitContractError):
            replace(permit(), state="CONSUMED", builder_invocation_permit_digest="").validate()
        with self.assertRaises(BuilderInvocationPermitContractError):
            replace(permit(), execution_effect="BUILDER_START", builder_invocation_permit_digest="").validate()


if __name__ == "__main__":
    unittest.main()

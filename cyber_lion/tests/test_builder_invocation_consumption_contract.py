from __future__ import annotations

from dataclasses import replace
import unittest

from cyber_lion.contracts.builder_invocation_consumption import (
    BuilderInvocationConsumptionContractError,
    BuilderInvocationConsumptionPermit,
    SCHEMA_VERSION,
    compute_invocation_consumption_replay_digest,
)

D = lambda c: c * 64
S = lambda c: c * 40
REPO = "DonkeyJJLove/ai_platform"
SCOPE = ("cyber_lion/example.py",)
RES = (f"repo-path:{REPO}:cyber_lion/example.py",)


def permit() -> BuilderInvocationConsumptionPermit:
    kwargs = dict(
        source_builder_invocation_permit_id="bip:" + D("1"),
        source_builder_invocation_permit_digest=D("2"),
        source_builder_invocation_replay_digest=D("1"),
        source_builder_entry_permit_id="bep:" + D("3"),
        source_builder_entry_permit_digest=D("4"),
        repository=REPO,
        baseline_master_sha=S("a"),
        baseline_master_tree_sha=S("b"),
        current_baseline_digest=D("5"),
        action="BUILD_CANDIDATE",
        candidate_scope=SCOPE,
        resource_scope=RES,
        authority_epoch=4,
        authority_state_version=9,
        root_grant_id="root-R20",
        root_grant_digest=D("6"),
        current_authority_digest=D("7"),
        builder_subject_id="builder-R20",
        builder_instance_id="instance-01",
        builder_capability_class="DETACHED_CANDIDATE_BUILD_ONLY",
        builder_identity_digest=D("8"),
        builder_implementation_digest=D("9"),
        builder_attestation_digest=D("a"),
        current_builder_subject_digest=D("b"),
    )
    replay = compute_invocation_consumption_replay_digest(**kwargs)
    return BuilderInvocationConsumptionPermit(
        schema_version=SCHEMA_VERSION,
        invocation_consumption_permit_id="bicp:" + replay,
        checked_at="2026-08-25T11:00:00+00:00",
        invocation_consumption_replay_digest=replay,
        **kwargs,
    ).sealed()


class BuilderInvocationConsumptionContractTests(unittest.TestCase):
    def test_sealed_permit_is_non_effectful_and_source_bound(self):
        value = permit()
        self.assertEqual((value.authority_effect, value.execution_effect, value.repository_ref_effect, value.external_effect), ("NONE", "NONE", "NONE", "NONE"))
        self.assertEqual(value.invocation_consumption_permit_id, "bicp:" + value.invocation_consumption_replay_digest)
        self.assertEqual(value.invocation_consumption_permit_digest, value.compute_digest())
        value.validate()

    def test_source_digest_replay_id_and_scope_substitution_denied(self):
        value = permit()
        mutations = (
            ("source_builder_invocation_permit_digest", D("c")),
            ("source_builder_invocation_replay_digest", D("d")),
            ("source_builder_invocation_permit_id", "bip:" + D("e")),
            ("candidate_scope", ("cyber_lion/other.py",)),
            ("builder_instance_id", "instance-02"),
        )
        for field, replacement in mutations:
            with self.assertRaises(BuilderInvocationConsumptionContractError):
                replace(value, **{field: replacement}).validate()

    def test_coherent_reseal_changes_identity_and_cannot_preserve_original(self):
        value = permit()
        changed = replace(value, checked_at="2026-08-25T11:01:00+00:00", invocation_consumption_permit_digest="").sealed()
        self.assertNotEqual(changed.invocation_consumption_permit_digest, value.invocation_consumption_permit_digest)
        self.assertEqual(changed.invocation_consumption_replay_digest, value.invocation_consumption_replay_digest)

    def test_effect_substitution_denied(self):
        value = permit()
        for field in ("authority_effect", "execution_effect", "repository_ref_effect", "external_effect"):
            with self.assertRaises(BuilderInvocationConsumptionContractError):
                replace(value, **{field: "ALLOW"}).validate()


if __name__ == "__main__":
    unittest.main()

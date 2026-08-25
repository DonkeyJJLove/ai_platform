from __future__ import annotations

from dataclasses import replace
import unittest

from cyber_lion.contracts.builder_start_admission import (
    BuilderStartAdmission,
    BuilderStartAdmissionContractError,
    SCHEMA_VERSION,
    compute_builder_start_admission_replay_digest,
    compute_launch_policy_digest,
    compute_process_profile_digest,
)

D = lambda c: c * 64
S = lambda c: c * 40
REPO = "DonkeyJJLove/ai_platform"
SCOPE = ("cyber_lion/example.py",)
RES = (f"repo-path:{REPO}:cyber_lion/example.py",)


def admission() -> BuilderStartAdmission:
    profile_kwargs = dict(
        repository=REPO,
        action="BUILD_CANDIDATE",
        candidate_scope=SCOPE,
        resource_scope=RES,
        builder_subject_id="builder-R21",
        builder_instance_id="instance-21",
        builder_capability_class="DETACHED_CANDIDATE_BUILD_ONLY",
        builder_identity_digest=D("8"),
        builder_implementation_digest=D("9"),
        builder_attestation_digest=D("a"),
        current_builder_subject_digest=D("b"),
    )
    profile = compute_process_profile_digest(**profile_kwargs)
    kwargs = dict(
        source_invocation_consumption_permit_id="bicp:" + D("1"),
        source_invocation_consumption_permit_digest=D("2"),
        source_invocation_consumption_replay_digest=D("1"),
        source_builder_invocation_permit_id="bip:" + D("3"),
        source_builder_invocation_permit_digest=D("4"),
        source_builder_entry_permit_id="bep:" + D("5"),
        source_builder_entry_permit_digest=D("6"),
        repository=REPO,
        baseline_master_sha=S("a"),
        baseline_master_tree_sha=S("b"),
        current_baseline_digest=D("7"),
        action="BUILD_CANDIDATE",
        candidate_scope=SCOPE,
        resource_scope=RES,
        authority_epoch=5,
        authority_state_version=10,
        root_grant_id="root-R21",
        root_grant_digest=D("c"),
        current_authority_digest=D("d"),
        builder_subject_id="builder-R21",
        builder_instance_id="instance-21",
        builder_capability_class="DETACHED_CANDIDATE_BUILD_ONLY",
        builder_identity_digest=D("8"),
        builder_implementation_digest=D("9"),
        builder_attestation_digest=D("a"),
        current_builder_subject_digest=D("b"),
        process_profile_id="bpp:" + profile,
        process_profile_digest=profile,
        launch_policy_digest=compute_launch_policy_digest(),
    )
    replay = compute_builder_start_admission_replay_digest(**kwargs)
    return BuilderStartAdmission(
        schema_version=SCHEMA_VERSION,
        builder_start_admission_id="bsa:" + replay,
        builder_start_admission_replay_digest=replay,
        checked_at="2026-08-25T12:20:00+00:00",
        **kwargs,
    ).sealed()


class BuilderStartAdmissionContractTests(unittest.TestCase):
    def test_sealed_admission_is_non_effectful_and_deterministic(self):
        value = admission()
        self.assertEqual(value.builder_start_admission_id, "bsa:" + value.builder_start_admission_replay_digest)
        self.assertEqual(value.builder_start_admission_digest, value.compute_digest())
        self.assertEqual((value.authority_effect, value.execution_effect, value.repository_ref_effect, value.external_effect), ("NONE", "NONE", "NONE", "NONE"))
        value.validate()

    def test_profile_is_not_caller_replaceable(self):
        value = admission()
        with self.assertRaises(BuilderStartAdmissionContractError):
            replace(value, process_profile_digest=D("e"), builder_start_admission_digest="").sealed()
        with self.assertRaises(BuilderStartAdmissionContractError):
            replace(value, launch_policy_digest=D("f"), builder_start_admission_digest="").sealed()

    def test_source_and_scope_substitution_denied(self):
        value = admission()
        for field, replacement in (
            ("source_invocation_consumption_permit_digest", D("e")),
            ("source_builder_invocation_permit_digest", D("f")),
            ("source_builder_entry_permit_digest", D("0")),
            ("candidate_scope", ("cyber_lion/other.py",)),
            ("builder_instance_id", "other-instance"),
        ):
            with self.assertRaises(BuilderStartAdmissionContractError):
                replace(value, **{field: replacement}).validate()

    def test_checked_at_coherent_reseal_changes_artifact_identity_not_replay(self):
        value = admission()
        changed = replace(value, checked_at="2026-08-25T12:21:00+00:00", builder_start_admission_digest="").sealed()
        self.assertEqual(changed.builder_start_admission_replay_digest, value.builder_start_admission_replay_digest)
        self.assertNotEqual(changed.builder_start_admission_digest, value.builder_start_admission_digest)

    def test_effect_substitution_denied(self):
        value = admission()
        for field in ("authority_effect", "execution_effect", "repository_ref_effect", "external_effect"):
            with self.assertRaises(BuilderStartAdmissionContractError):
                replace(value, **{field: "ALLOW"}).validate()


if __name__ == "__main__":
    unittest.main()

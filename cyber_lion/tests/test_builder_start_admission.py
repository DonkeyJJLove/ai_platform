from __future__ import annotations

import inspect
import unittest

from cyber_lion.contracts.builder_start_admission import (
    compute_launch_policy_digest,
    compute_process_profile_digest,
)
from cyber_lion.enterprise.builder_start_admission import (
    BuilderStartAdmissionEngine,
    PersistentBuilderInvocationConsumptionIssuanceRecord,
    PersistentBuilderStartAdmissionIssuanceRecord,
    _R21Persistence,
)

D = lambda c: c * 64
S = lambda c: c * 40
REPO = "DonkeyJJLove/ai_platform"
SCOPE = ("cyber_lion/example.py",)
RES = (f"repo-path:{REPO}:cyber_lion/example.py",)


class BuilderStartAdmissionTests(unittest.TestCase):
    def test_constructor_has_no_caller_selected_store_or_profile_surface(self):
        params = set(inspect.signature(BuilderStartAdmissionEngine).parameters)
        for forbidden in ("store", "origin", "replay_guard", "issuance_source", "process_profile", "launch_policy"):
            self.assertNotIn(forbidden, params)

    def test_no_effect_surface(self):
        BuilderStartAdmissionEngine.assert_no_effect_surface()
        for name in ("start_builder", "spawn", "popen", "fork", "exec", "build_candidate", "allocate_workspace"):
            self.assertFalse(hasattr(BuilderStartAdmissionEngine, name))

    def test_process_profile_and_launch_policy_are_deterministic(self):
        kwargs = dict(
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
        self.assertEqual(compute_process_profile_digest(**kwargs), compute_process_profile_digest(**kwargs))
        self.assertEqual(compute_launch_policy_digest(), compute_launch_policy_digest())

    def test_r20_durable_record_binds_exact_artifact_identity(self):
        value = PersistentBuilderInvocationConsumptionIssuanceRecord(
            invocation_consumption_permit_id="bicp:" + D("1"),
            invocation_consumption_permit_digest=D("2"),
            invocation_consumption_replay_digest=D("1"),
            source_builder_invocation_permit_id="bip:" + D("3"),
            source_builder_invocation_permit_digest=D("4"),
            source_builder_invocation_replay_digest=D("3"),
            source_builder_entry_permit_id="bep:" + D("5"),
            source_builder_entry_permit_digest=D("6"),
            repository=REPO,
            baseline_master_sha=S("a"),
            baseline_master_tree_sha=S("b"),
            current_baseline_digest=D("7"),
            action="BUILD_CANDIDATE",
            candidate_scope=SCOPE,
            resource_scope=RES,
            authority_epoch=1,
            authority_state_version=1,
            root_grant_id="root",
            root_grant_digest=D("c"),
            current_authority_digest=D("d"),
            builder_subject_id="builder",
            builder_instance_id="instance",
            builder_capability_class="DETACHED_CANDIDATE_BUILD_ONLY",
            builder_identity_digest=D("8"),
            builder_implementation_digest=D("9"),
            builder_attestation_digest=D("a"),
            current_builder_subject_digest=D("b"),
            authority_store_origin_id="aso:" + D("e"),
            authority_store_origin_digest=D("e"),
            issued_at="2026-08-25T12:00:00+00:00",
        )
        self.assertIs(value.validate(), value)

    def test_r21_durable_record_binds_process_profile_and_policy(self):
        value = PersistentBuilderStartAdmissionIssuanceRecord(
            builder_start_admission_id="bsa:" + D("1"),
            builder_start_admission_digest=D("2"),
            builder_start_admission_replay_digest=D("1"),
            source_invocation_consumption_permit_id="bicp:" + D("3"),
            source_invocation_consumption_permit_digest=D("4"),
            source_invocation_consumption_replay_digest=D("3"),
            source_builder_invocation_permit_id="bip:" + D("5"),
            source_builder_invocation_permit_digest=D("6"),
            source_builder_entry_permit_id="bep:" + D("7"),
            source_builder_entry_permit_digest=D("8"),
            repository=REPO,
            baseline_master_sha=S("a"),
            baseline_master_tree_sha=S("b"),
            current_baseline_digest=D("9"),
            action="BUILD_CANDIDATE",
            candidate_scope=SCOPE,
            resource_scope=RES,
            authority_epoch=1,
            authority_state_version=1,
            root_grant_id="root",
            root_grant_digest=D("a"),
            current_authority_digest=D("b"),
            builder_subject_id="builder",
            builder_instance_id="instance",
            builder_capability_class="DETACHED_CANDIDATE_BUILD_ONLY",
            builder_identity_digest=D("c"),
            builder_implementation_digest=D("d"),
            builder_attestation_digest=D("e"),
            current_builder_subject_digest=D("f"),
            process_profile_id="bpp:" + D("0"),
            process_profile_digest=D("0"),
            launch_policy_digest=D("1"),
            authority_store_origin_id="aso:" + D("2"),
            authority_store_origin_digest=D("2"),
            issued_at="2026-08-25T12:10:00+00:00",
        )
        self.assertIs(value.validate(), value)
        self.assertEqual(_R21Persistence.R20_TABLE, "builder_invocation_consumption_issuance")
        self.assertEqual(_R21Persistence.R21_TABLE, "builder_start_admission_issuance")


if __name__ == "__main__":
    unittest.main()

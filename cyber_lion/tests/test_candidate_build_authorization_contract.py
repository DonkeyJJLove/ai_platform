from dataclasses import FrozenInstanceError, replace
import unittest

from cyber_lion.contracts.candidate_build_authorization import (
    BoundedCandidateBuildAuthorization,
    CandidateBuildAuthorizationContractError,
    ResourceAuthorityLookupKey,
    TrustedRepositoryBaseline,
    canonical_repo_path_resource,
)

REPO = "DonkeyJJLove/ai_platform"
P1 = "cyber_lion/contracts/example.py"
P2 = "cyber_lion/tests/test_example.py"
H40 = "a" * 40
H64 = "b" * 64


def make_authorization(**overrides):
    scope = (P1, P2)
    values = dict(
        schema_version="1.0.0",
        authorization_id="cba:" + "1" * 64,
        admission_request_id="gca:req-1",
        admission_request_digest="2" * 64,
        gate_request_id="gate:req-1",
        gate_request_digest="3" * 64,
        gate_event_id="gate:event-1",
        gate_decision_digest="4" * 64,
        pdp_receipt_id="pdp:receipt-1",
        pdp_request_id="gate:req-1",
        pdp_request_digest="3" * 64,
        pdp_decision_digest="4" * 64,
        pdp_replay_key="5" * 64,
        policy_binding="candidate-build@1:sha256:" + "6" * 64,
        grant_id="grant-build-1",
        leaf_grant_digest="7" * 64,
        authority_lineage_digest="8" * 64,
        authority_provenance_id="control-plane:build:1",
        authority_epoch=4,
        authority_state_version=7,
        root_grant_id="grant-root-1",
        root_grant_digest="9" * 64,
        live_admission_digest="a" * 64,
        authority_admitted_at="2026-08-25T00:00:00+00:00",
        repository=REPO,
        baseline_master_sha=H40,
        baseline_master_tree_sha="c" * 40,
        baseline_observation_digest="d" * 64,
        candidate_scope=scope,
        resource_scope=tuple(canonical_repo_path_resource(REPO, p) for p in scope),
        action="BUILD_CANDIDATE",
        requested_authority="local_write",
        effective_authority_ceiling="local_write",
        valid_from="2026-08-25T00:00:00+00:00",
        expires_at="2026-08-25T01:00:00+00:00",
        issuance_replay_digest="e" * 64,
    )
    values.update(overrides)
    return BoundedCandidateBuildAuthorization(**values)


class CandidateBuildAuthorizationContractTests(unittest.TestCase):
    def test_sealed_authorization_is_immutable_and_deterministic(self):
        first = make_authorization().sealed()
        second = make_authorization().sealed()
        self.assertEqual(first.authorization_digest, second.authorization_digest)
        self.assertEqual(len(first.authorization_digest), 64)
        with self.assertRaises(FrozenInstanceError):
            first.action = "RUN_TEST"

    def test_changed_payload_invalidates_seal(self):
        sealed = make_authorization().sealed()
        changed = replace(sealed, baseline_master_sha="f" * 40)
        with self.assertRaisesRegex(CandidateBuildAuthorizationContractError, "authorization_digest mismatch"):
            changed.validate()

    def test_action_and_authority_are_closed(self):
        with self.assertRaisesRegex(CandidateBuildAuthorizationContractError, "BUILD_CANDIDATE"):
            make_authorization(action="RUN_TEST").validate()
        with self.assertRaisesRegex(CandidateBuildAuthorizationContractError, "local_write"):
            make_authorization(effective_authority_ceiling="external_write").validate()

    def test_effect_assertions_are_forbidden(self):
        with self.assertRaisesRegex(CandidateBuildAuthorizationContractError, "cannot carry effects"):
            make_authorization(external_effect="WRITE").validate()

    def test_scope_is_exact_and_wildcards_or_traversal_are_denied(self):
        bad_scope = ("../escape.py",)
        with self.assertRaises(CandidateBuildAuthorizationContractError):
            make_authorization(
                candidate_scope=bad_scope,
                resource_scope=(f"repo-path:{REPO}:../escape.py",),
            ).validate()
        with self.assertRaises(CandidateBuildAuthorizationContractError):
            make_authorization(
                candidate_scope=("cyber_lion/*.py",),
                resource_scope=(f"repo-path:{REPO}:cyber_lion/*.py",),
            ).validate()
        with self.assertRaisesRegex(CandidateBuildAuthorizationContractError, "exactly project"):
            make_authorization(resource_scope=(canonical_repo_path_resource(REPO, P1),)).validate()

    def test_pre_pr_resource_key_has_no_pr_or_branch_identity(self):
        key = ResourceAuthorityLookupKey(
            repository=REPO,
            mission_id="E004-R11",
            grant_id="grant-build-1",
            action="BUILD_CANDIDATE",
            resource_scope=(canonical_repo_path_resource(REPO, P1),),
        ).validate()
        self.assertNotIn("pr_number", key.__dataclass_fields__)
        self.assertNotIn("branch", key.__dataclass_fields__)
        self.assertNotIn("head_sha", key.__dataclass_fields__)
        self.assertEqual(len(key.digest()), 64)

    def test_resource_key_rejects_cross_action_and_wildcard(self):
        with self.assertRaisesRegex(CandidateBuildAuthorizationContractError, "BUILD_CANDIDATE"):
            ResourceAuthorityLookupKey(
                REPO, "E004-R11", "grant-build-1", "RUN_TEST",
                (canonical_repo_path_resource(REPO, P1),),
            ).validate()
        with self.assertRaises(CandidateBuildAuthorizationContractError):
            ResourceAuthorityLookupKey(
                REPO, "E004-R11", "grant-build-1", "BUILD_CANDIDATE",
                (f"repo-path:{REPO}:cyber_lion/*",),
            ).validate()

    def test_trusted_baseline_binds_commit_and_tree(self):
        baseline = TrustedRepositoryBaseline(
            REPO, H40, "c" * 40, "2026-08-25T00:00:00+00:00"
        ).validate()
        self.assertEqual(len(baseline.digest()), 64)
        with self.assertRaises(CandidateBuildAuthorizationContractError):
            TrustedRepositoryBaseline(REPO, "short", "c" * 40, "now").validate()


if __name__ == "__main__":
    unittest.main()

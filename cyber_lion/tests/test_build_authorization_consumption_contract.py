from dataclasses import replace
import unittest

from cyber_lion.contracts.build_authorization_consumption import (
    BuildAuthorizationConsumptionContractError,
    BuildAuthorizationConsumptionPermit,
)

D = "a" * 64
SHA = "b" * 40
PATH = "cyber_lion/example.py"
RESOURCE = "repo-path:DonkeyJJLove/ai_platform:cyber_lion/example.py"


def make_permit(**changes):
    values = dict(
        schema_version="1.0.0",
        consumption_permit_id=f"cbcp:{D}",
        authorization_id=f"cba:{'c'*64}",
        authorization_digest="d" * 64,
        issuance_replay_digest="c" * 64,
        repository="DonkeyJJLove/ai_platform",
        baseline_master_sha=SHA,
        baseline_master_tree_sha="c" * 40,
        baseline_observation_digest="e" * 64,
        action="BUILD_CANDIDATE",
        candidate_scope=(PATH,),
        resource_scope=(RESOURCE,),
        grant_id="grant-1",
        leaf_grant_digest="f" * 64,
        authority_lineage_digest="1" * 64,
        authority_provenance_id="trusted-control-plane:1",
        authority_epoch=4,
        authority_state_version=8,
        root_grant_id="root-1",
        root_grant_digest="2" * 64,
        live_admission_digest="3" * 64,
        authorization_valid_from="2026-08-25T00:00:00+00:00",
        authorization_expires_at="2026-08-26T00:00:00+00:00",
        checked_at="2026-08-25T01:00:00+00:00",
        current_baseline_digest="4" * 64,
        current_authority_digest="5" * 64,
        consumption_replay_digest=D,
    )
    values.update(changes)
    return BuildAuthorizationConsumptionPermit(**values)


class BuildAuthorizationConsumptionPermitContractTests(unittest.TestCase):
    def test_valid_permit_is_sealed_and_deterministic(self):
        permit = make_permit().sealed()
        self.assertEqual(permit.consumption_permit_digest, permit.compute_digest())
        self.assertEqual(permit, make_permit().sealed())
        self.assertEqual(permit.authority_effect, "NONE")
        self.assertEqual(permit.execution_effect, "NONE")

    def test_permit_id_must_derive_from_replay_digest(self):
        with self.assertRaisesRegex(BuildAuthorizationConsumptionContractError, "permit id"):
            make_permit(consumption_permit_id=f"cbcp:{'9'*64}").validate()

    def test_reseal_does_not_repair_substituted_id(self):
        permit = make_permit().sealed()
        forged = replace(permit, consumption_permit_id=f"cbcp:{'9'*64}", consumption_permit_digest="")
        with self.assertRaises(BuildAuthorizationConsumptionContractError):
            forged.sealed()

    def test_digest_substitution_fails(self):
        permit = make_permit().sealed()
        forged = replace(permit, authorization_digest="9" * 64)
        with self.assertRaisesRegex(BuildAuthorizationConsumptionContractError, "permit digest mismatch"):
            forged.validate()

    def test_action_substitution_fails(self):
        with self.assertRaisesRegex(BuildAuthorizationConsumptionContractError, "BUILD_CANDIDATE"):
            make_permit(action="RUN_TEST").validate()

    def test_scope_widening_and_traversal_fail(self):
        with self.assertRaises(BuildAuthorizationConsumptionContractError):
            make_permit(candidate_scope=(PATH, "other.py"), resource_scope=(RESOURCE,)).validate()
        with self.assertRaises(BuildAuthorizationConsumptionContractError):
            make_permit(candidate_scope=("../escape",), resource_scope=(RESOURCE,)).validate()

    def test_resource_wildcard_fails_exact_projection(self):
        with self.assertRaises(BuildAuthorizationConsumptionContractError):
            make_permit(resource_scope=("repo-path:DonkeyJJLove/ai_platform:*",)).validate()

    def test_effectful_artifact_fails(self):
        with self.assertRaisesRegex(BuildAuthorizationConsumptionContractError, "cannot carry effects"):
            make_permit(execution_effect="WRITE_FILE").validate()

    def test_frozen_contract(self):
        permit = make_permit().sealed()
        with self.assertRaises(Exception):
            permit.action = "RUN_TEST"


if __name__ == "__main__":
    unittest.main()

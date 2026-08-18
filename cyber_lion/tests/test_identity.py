import unittest

from cyber_lion.contracts.identity import (
    EntityIdentity,
    IdentityValidationError,
    aid_from_entity,
    entity_from_aid,
)


class EntityIdentityTests(unittest.TestCase):
    def test_aid_round_trip_is_lossless(self):
        aid = {
            "app_id": "sbom",
            "owner_team": "K82M",
            "env": "lab",
            "vcs_ref": "abc123",
            "app_version": "1.2.3",
            "repo": "DonkeyJJLove/sbom",
            "custom_extension": "preserve-me",
        }
        entity = entity_from_aid(aid)
        self.assertEqual(entity.entity_id, "aid:application:sbom")
        self.assertEqual(entity.owner, "K82M")
        self.assertEqual(aid_from_entity(entity), aid)

    def test_missing_aid_field_fails_closed(self):
        with self.assertRaises(IdentityValidationError):
            entity_from_aid({"app_id": "sbom"})

    def test_network_address_is_not_valid_repository_identity(self):
        entity = EntityIdentity(
            schema_version="1.0.0",
            entity_id="service:aggregator",
            entity_type="service",
            owner="swarm",
            environment="lab",
            repo="10.0.0.12:6000",
        )
        with self.assertRaises(IdentityValidationError):
            entity.validate()

    def test_unknown_environment_is_explicit_not_guessed(self):
        aid = {
            "app_id": "legacy-app",
            "owner_team": "legacy-team",
            "env": "mystery-zone",
            "vcs_ref": "local",
            "app_version": "0.0.0",
        }
        entity = entity_from_aid(aid)
        self.assertEqual(entity.environment, "unknown")
        self.assertEqual(aid_from_entity(entity)["env"], "mystery-zone")


if __name__ == "__main__":
    unittest.main()

import unittest
from cyber_lion.contracts.identity import EntityIdentity, IdentityValidationError, aid_from_entity, entity_from_aid

class IdentityTests(unittest.TestCase):
    def test_aid_round_trip(self):
        aid={"app_id":"sbom","owner_team":"K82M","env":"lab","vcs_ref":"abc123","app_version":"1.2.3","repo":"DonkeyJJLove/sbom","extra":"keep"}
        entity=entity_from_aid(aid)
        self.assertEqual(entity.entity_id,"aid:application:sbom")
        self.assertEqual(aid_from_entity(entity),aid)

    def test_missing_aid_fails_closed(self):
        with self.assertRaises(IdentityValidationError): entity_from_aid({"app_id":"sbom"})

    def test_network_address_is_not_repo_identity(self):
        with self.assertRaises(IdentityValidationError):
            EntityIdentity("1.0.0","service:aggregator","service","swarm","lab",repo="10.0.0.12:6000").validate()

    def test_unknown_env_is_explicit_and_original_preserved(self):
        aid={"app_id":"legacy","owner_team":"team","env":"mystery","vcs_ref":"local","app_version":"0.0.0"}
        entity=entity_from_aid(aid)
        self.assertEqual(entity.environment,"unknown")
        self.assertEqual(aid_from_entity(entity)["env"],"mystery")

if __name__ == "__main__": unittest.main()

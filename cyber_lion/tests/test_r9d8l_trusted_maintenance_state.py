import tempfile
import unittest

from cyber_lion.contracts.policy_gate import PolicyRevision
from cyber_lion.enterprise.models import MissionSpec
from cyber_lion.enterprise.trusted_control_plane_providers import (
    PinnedMaintenanceStateSource,
    SQLiteTrustedControlPlaneStore,
    TrustedControlPlaneProviderError,
    TrustedSignatureVerifierAdapter,
)
from cyber_lion.enterprise.trusted_control_plane_service import TrustedControlPlaneService


REPOSITORY = "DonkeyJJLove/ai_platform"
MISSION_ID = "repository-maintenance-e006"
POLICY_ID = "repository-maintenance-policy"


def policy_record(*, revision="1", active=True, provenance_ref="external:policy:1"):
    policy = PolicyRevision(
        policy_id=POLICY_ID,
        revision=revision,
        content_digest="sha256:" + ("a" * 64),
        lane="RED",
        active=active,
    ).validate()
    return {
        "record_kind": "maintenance-policy",
        "lookup_key": {
            "repository": REPOSITORY,
            "mission_id": MISSION_ID,
            "policy_id": POLICY_ID,
        },
        "revision": policy.revision,
        "content_digest": policy.content_digest,
        "lane": policy.lane,
        "active": policy.active,
        "provenance_ref": provenance_ref,
        "policy_payload": {
            "policy_id": policy.policy_id,
            "revision": policy.revision,
            "content_digest": policy.content_digest,
            "lane": policy.lane,
            "active": policy.active,
            "schema_version": policy.schema_version,
        },
    }


def mission_record(*, provenance_ref="external:mission:1"):
    mission = MissionSpec(
        mission_id=MISSION_ID,
        purpose="Govern exact repository maintenance state without granting authority.",
        required_capabilities=("repository_ref.delete",),
        authority_ceiling="external_write",
        risk_class="RED",
        max_agents=3,
        observability_quorum=1.0,
        require_independent_verifier=True,
        max_total_cost_units=1.0,
    ).validate()
    return {
        "record_kind": "maintenance-mission",
        "lookup_key": {"repository": REPOSITORY, "mission_id": MISSION_ID},
        "provenance_ref": provenance_ref,
        "mission_payload": {
            "mission_id": mission.mission_id,
            "purpose": mission.purpose,
            "required_capabilities": list(mission.required_capabilities),
            "authority_ceiling": mission.authority_ceiling,
            "risk_class": mission.risk_class,
            "max_agents": mission.max_agents,
            "observability_quorum": mission.observability_quorum,
            "require_independent_verifier": mission.require_independent_verifier,
            "max_total_cost_units": mission.max_total_cost_units,
        },
    }


class R9D8LTrustedMaintenanceStateTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.store = SQLiteTrustedControlPlaneStore(self.tempdir.name + "/trusted.sqlite3")
        self.verifier = TrustedSignatureVerifierAdapter(lambda *_: True)
        self.service = TrustedControlPlaneService(store=self.store, verifier=self.verifier, credential="secret")
        self.headers = {"Authorization": "Bearer secret"}

    def get(self, path):
        return self.service.dispatch(method="GET", target=path, headers=self.headers)

    def test_zero_records_are_explicit_absence(self):
        policy = self.get(
            "/v1/maintenance-policy?repository=DonkeyJJLove%2Fai_platform"
            f"&mission_id={MISSION_ID}&policy_id={POLICY_ID}"
        )
        mission = self.get(
            "/v1/maintenance-mission?repository=DonkeyJJLove%2Fai_platform"
            f"&mission_id={MISSION_ID}"
        )
        self.assertEqual(policy.status, 200)
        self.assertEqual(mission.status, 200)
        self.assertEqual(policy.payload["records"], [])
        self.assertEqual(mission.payload["records"], [])

    def test_exact_records_round_trip_without_authority_semantics(self):
        policy = policy_record()
        mission = mission_record()
        self.store.put_maintenance_policy_record(policy)
        self.store.put_maintenance_mission_record(mission)

        policy_response = self.get(
            "/v1/maintenance-policy?repository=DonkeyJJLove%2Fai_platform"
            f"&mission_id={MISSION_ID}&policy_id={POLICY_ID}"
        )
        mission_response = self.get(
            "/v1/maintenance-mission?repository=DonkeyJJLove%2Fai_platform"
            f"&mission_id={MISSION_ID}"
        )
        self.assertEqual(policy_response.payload["records"], [policy])
        self.assertEqual(mission_response.payload["records"], [mission])
        self.assertNotIn("authority_grant", str(policy_response.payload).lower())
        self.assertNotIn("allow", str(policy_response.payload).lower())

    def test_query_widening_and_non_get_are_denied(self):
        valid = (
            "/v1/maintenance-policy?repository=DonkeyJJLove%2Fai_platform"
            f"&mission_id={MISSION_ID}&policy_id={POLICY_ID}"
        )
        widened = valid + "&provider=http%3A%2F%2Fevil"
        self.assertEqual(self.get(widened).status, 400)
        self.assertEqual(
            self.service.dispatch(method="POST", target=valid, headers=self.headers).status,
            400,
        )

    def test_strict_policy_payload_rejects_unknown_field_and_binding_substitution(self):
        unknown = policy_record()
        unknown["policy_payload"]["extra"] = "x"
        with self.assertRaises(TrustedControlPlaneProviderError):
            self.store.put_maintenance_policy_record(unknown)

        substituted = policy_record()
        substituted["policy_payload"]["policy_id"] = "other"
        with self.assertRaises(TrustedControlPlaneProviderError):
            self.store.put_maintenance_policy_record(substituted)

    def test_strict_mission_payload_rejects_unknown_field_and_binding_substitution(self):
        unknown = mission_record()
        unknown["mission_payload"]["extra"] = "x"
        with self.assertRaises(TrustedControlPlaneProviderError):
            self.store.put_maintenance_mission_record(unknown)

        substituted = mission_record()
        substituted["mission_payload"]["mission_id"] = "other"
        with self.assertRaises(TrustedControlPlaneProviderError):
            self.store.put_maintenance_mission_record(substituted)

    def test_inactive_policy_is_not_current(self):
        self.store.put_maintenance_policy_record(policy_record(active=False))
        response = self.get(
            "/v1/maintenance-policy?repository=DonkeyJJLove%2Fai_platform"
            f"&mission_id={MISSION_ID}&policy_id={POLICY_ID}"
        )
        self.assertEqual(response.payload["records"], [])

    def test_multiple_active_policy_records_preserve_ambiguity(self):
        self.store.put_maintenance_policy_record(policy_record(revision="1", provenance_ref="external:policy:1"))
        self.store.put_maintenance_policy_record(policy_record(revision="2", provenance_ref="external:policy:2"))
        response = self.get(
            "/v1/maintenance-policy?repository=DonkeyJJLove%2Fai_platform"
            f"&mission_id={MISSION_ID}&policy_id={POLICY_ID}"
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(len(response.payload["records"]), 2)
        source = PinnedMaintenanceStateSource(self.store)
        with self.assertRaises(TrustedControlPlaneProviderError):
            source.resolve_maintenance_policy_exact(
                repository=REPOSITORY,
                mission_id=MISSION_ID,
                policy_id=POLICY_ID,
            )

    def test_capability_reduced_reader_requires_exactly_one_record(self):
        source = PinnedMaintenanceStateSource(self.store)
        with self.assertRaises(TrustedControlPlaneProviderError):
            source.resolve_maintenance_policy_exact(
                repository=REPOSITORY,
                mission_id=MISSION_ID,
                policy_id=POLICY_ID,
            )
        with self.assertRaises(TrustedControlPlaneProviderError):
            source.resolve_maintenance_mission_exact(repository=REPOSITORY, mission_id=MISSION_ID)

        self.store.put_maintenance_policy_record(policy_record())
        self.store.put_maintenance_mission_record(mission_record())
        policy, policy_provenance, policy_origin = source.resolve_maintenance_policy_exact(
            repository=REPOSITORY,
            mission_id=MISSION_ID,
            policy_id=POLICY_ID,
        )
        mission, mission_provenance, mission_origin = source.resolve_maintenance_mission_exact(
            repository=REPOSITORY,
            mission_id=MISSION_ID,
        )
        self.assertEqual(policy.policy_id, POLICY_ID)
        self.assertEqual(mission.mission_id, MISSION_ID)
        self.assertTrue(policy_provenance.startswith("external:"))
        self.assertTrue(mission_provenance.startswith("external:"))
        self.assertEqual(policy_origin, mission_origin)
        self.assertEqual(policy_origin, source.source_origin_id)


if __name__ == "__main__":
    unittest.main()

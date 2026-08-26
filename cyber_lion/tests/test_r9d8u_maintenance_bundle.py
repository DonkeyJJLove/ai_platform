from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.policy_gate import PolicyRevision
from cyber_lion.enterprise.maintenance_bundle import (
    CAPABILITY_REPOSITORY_REF_DELETE,
    MaintenanceBinding,
    MaintenanceBundleError,
    SQLiteMaintenanceBundleRepository,
    decode_maintenance_bundle,
)
from cyber_lion.enterprise.models import MissionSpec
from cyber_lion.enterprise.trusted_control_plane_providers import SQLiteTrustedControlPlaneStore
from cyber_lion.enterprise.trusted_maintenance_bundle_service import TrustedMaintenanceBundleService

Z = "0" * 64
REPO = "DonkeyJJLove/ai_platform"
MISSION = "LION-E006-R9D8-CANARY"
POLICY = "LION-E006-R9D8-POLICY"


def records():
    policy = PolicyRevision(POLICY, "1", "sha256:" + Z, "RED", True).validate()
    mission = MissionSpec(
        MISSION,
        "governed repository maintenance branch-ref deletion",
        (CAPABILITY_REPOSITORY_REF_DELETE,),
        authority_ceiling="external_write",
        risk_class="RED",
        max_agents=2,
        observability_quorum=1.0,
        require_independent_verifier=True,
        max_total_cost_units=2.0,
    ).validate()
    policy_record = {
        "record_kind": "maintenance-policy",
        "lookup_key": {"repository": REPO, "mission_id": MISSION, "policy_id": POLICY},
        "revision": policy.revision,
        "content_digest": policy.content_digest,
        "lane": policy.lane,
        "active": policy.active,
        "provenance_ref": "external-admin:r9d8u:policy",
        "policy_payload": asdict(policy),
    }
    mission_payload = asdict(mission)
    mission_payload["required_capabilities"] = list(mission.required_capabilities)
    mission_record = {
        "record_kind": "maintenance-mission",
        "lookup_key": {"repository": REPO, "mission_id": MISSION},
        "provenance_ref": "external-admin:r9d8u:mission",
        "mission_payload": mission_payload,
    }
    return policy_record, mission_record


class R9D8UMaintenanceBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "control-plane.sqlite")
        self.store = SQLiteTrustedControlPlaneStore(self.db)
        self.repo = SQLiteMaintenanceBundleRepository(self.store, initialize_schema=True)
        self.binding = MaintenanceBinding(REPO, CAPABILITY_REPOSITORY_REF_DELETE, MISSION, POLICY).validate()

    def tearDown(self):
        self.tmp.cleanup()

    def provision(self):
        policy_record, mission_record = records()
        return self.repo.provision(
            binding=self.binding,
            maintenance_policy_record=policy_record,
            maintenance_mission_record=mission_record,
            administrator_id="external-admin:r9d8u",
            operation_id="provision:r9d8u:1",
            source_system_id="lion-control-plane-prod",
            provisioned_at="2026-08-26T09:00:00+00:00",
        )

    def test_atomic_producer_output_is_direct_consumer_input(self):
        bundle = self.provision()
        decoded = decode_maintenance_bundle(bundle.to_wire())
        self.assertEqual(decoded.bundle_digest, bundle.bundle_digest)
        self.assertEqual(decoded.binding, self.binding)
        self.assertEqual(decoded.policy().policy_id, POLICY)
        self.assertIn(CAPABILITY_REPOSITORY_REF_DELETE, decoded.mission().required_capabilities)
        self.assertEqual(decoded.administrative_receipt.source_origin_digest, bundle.source_origin_digest)

    def test_read_only_service_exposes_exact_attested_bundle_and_rejects_post(self):
        bundle = self.provision()
        service = TrustedMaintenanceBundleService(repository=self.repo, credential="credential")
        target = f"/v1/maintenance-bundle?repository={REPO}&capability=repository_ref.delete"
        status, payload = service.dispatch(method="GET", target=target, headers={"Authorization": "Bearer credential"})
        self.assertEqual(status, 200)
        self.assertEqual(decode_maintenance_bundle(payload).bundle_digest, bundle.bundle_digest)
        status, _ = service.dispatch(method="POST", target=target, headers={"Authorization": "Bearer credential"})
        self.assertEqual(status, 405)

    def test_second_current_binding_is_conflicted_not_overwritten(self):
        self.provision()
        with self.assertRaises(MaintenanceBundleError):
            self.provision()
        current = self.repo.resolve_exact(repository=REPO, capability=CAPABILITY_REPOSITORY_REF_DELETE)
        self.assertEqual(current.binding, self.binding)

    def test_source_attestation_substitution_is_denied(self):
        bundle = self.provision()
        wire = bundle.to_wire()
        wire["database_identity"] = "f" * 64
        with self.assertRaises(MaintenanceBundleError):
            decode_maintenance_bundle(wire)

    def test_unknown_bundle_field_is_denied(self):
        wire = self.provision().to_wire()
        wire["authority_grant"] = "forbidden"
        with self.assertRaises(MaintenanceBundleError):
            decode_maintenance_bundle(wire)

    def test_missing_or_ambiguous_binding_fails_closed(self):
        empty = SQLiteMaintenanceBundleRepository(self.store, initialize_schema=True)
        with self.assertRaises(MaintenanceBundleError):
            empty.resolve_exact(repository="other/repo", capability=CAPABILITY_REPOSITORY_REF_DELETE)
        self.provision()
        with self.repo._connect() as connection:
            connection.execute(
                "INSERT INTO maintenance_binding(repository,capability,mission_id,policy_id,transaction_digest,binding_digest,active,record_json) VALUES(?,?,?,?,?,?,1,?)",
                (REPO, CAPABILITY_REPOSITORY_REF_DELETE, MISSION, POLICY, "f" * 64, self.binding.digest(), '{"active":true,"binding_digest":"%s","capability":"repository_ref.delete","mission_id":"%s","policy_id":"%s","repository":"%s","transaction_digest":"%s"}' % (self.binding.digest(), MISSION, POLICY, REPO, "f" * 64)),
            )
        with self.assertRaises(MaintenanceBundleError):
            self.repo.resolve_exact(repository=REPO, capability=CAPABILITY_REPOSITORY_REF_DELETE)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import datetime, timezone
import json
import tempfile
from pathlib import Path
import unittest

from cyber_lion.contracts.fleet_status import FleetStatusIdentity, TrustedVerificationEvidence, VerificationTrustPins
from cyber_lion.enterprise.fleet_status_projection import FleetStatusProjector
from cyber_lion.enterprise.fleet_status_service import FleetStatusService
from cyber_lion.enterprise.fleet_status_state import FleetStatusStore


class Source:
    def resolve(self, verification_id):
        return TrustedVerificationEvidence(
            verification_id, "mission-1", "drone-1", "executor-1", "verifier-1",
            "1"*64, "2"*64, "anchor-1", "3"*64, "PASS", "4"*64,
            "verification-provenance", "ANCHORED", "2026-08-21T08:00:00+00:00",
        )


class BrokenReader:
    def snapshot(self):
        raise RuntimeError("down")


class FleetStatusServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db = Path(self.tmp.name) / "fleet.sqlite3"
        clock = lambda: datetime(2026, 8, 21, 8, 0, tzinfo=timezone.utc)
        pins = VerificationTrustPins("verifier-1", "1"*64, "2"*64, "anchor-1", "3"*64)
        self.store = FleetStatusStore(db, registry_instance_id="registry-1", clock=clock,
                                      verification_source=Source(), verification_pins=pins)
        self.store.register_identity(FleetStatusIdentity(
            "drone-1", "executor-1", "mission-1", "parent-1", "DonkeyJJLove/ai_platform",
            "a"*40, "b"*40, "mission/fcsr", ("**",), ("cyber_lion/**",), "sandbox-1",
        ))
        self.service = FleetStatusService(FleetStatusProjector(self.store))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def payload(self, response):
        return json.loads(response[2].decode())

    def test_non_get_methods_are_denied(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertEqual(self.service.handle(method, "/v1/fleet/snapshot")[0], 405)

    def test_get_body_is_denied(self):
        self.assertEqual(self.service.handle("GET", "/v1/fleet/snapshot", b"{}")[0], 400)

    def test_caller_provider_or_clock_selection_is_not_a_query_surface(self):
        for target in (
            "/v1/fleet/snapshot?provider=x",
            "/v1/fleet/snapshot?clock=x",
            "/v1/fleet/snapshot?db=/tmp/x",
        ):
            self.assertEqual(self.service.handle("GET", target)[0], 400)

    def test_snapshot_is_read_only_wire_contract(self):
        status, _, body = self.service.handle("GET", "/v1/fleet/snapshot")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["aggregate"]["total_known_drones"], 1)
        self.assertEqual(payload["drone_records"][0]["drone_id"], "drone-1")

    def test_exact_drone_and_mission_lookup(self):
        self.assertEqual(self.service.handle("GET", "/v1/fleet/drone?drone_id=drone-1")[0], 200)
        self.assertEqual(self.service.handle("GET", "/v1/fleet/mission?mission_id=mission-1")[0], 200)
        self.assertEqual(self.service.handle("GET", "/v1/fleet/drone?drone_id=missing")[0], 404)

    def test_health_exposes_snapshot_binding(self):
        response = self.service.handle("GET", "/healthz")
        self.assertEqual(response[0], 200)
        payload = self.payload(response)
        self.assertEqual(len(payload["snapshot_digest"]), 64)
        self.assertIn("snapshot_revision", payload)

    def test_backend_failure_is_status_unavailable_not_healthy_fallback(self):
        service = FleetStatusService(BrokenReader())
        status, _, body = service.handle("GET", "/healthz")
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)["error"], "STATUS_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()

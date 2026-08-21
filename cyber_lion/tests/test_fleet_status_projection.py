from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
import tempfile
from pathlib import Path
import unittest

from cyber_lion.contracts.fleet_status import FleetStatusIdentity, TrustedVerificationEvidence, VerificationTrustPins
from cyber_lion.enterprise.fleet_status_projection import FleetStatusProjector
from cyber_lion.enterprise.fleet_status_state import FleetStatusStateError, FleetStatusStore


class Clock:
    def __init__(self):
        self.value = datetime(2026, 8, 21, 8, 0, tzinfo=timezone.utc)
    def __call__(self):
        return self.value
    def tick(self, seconds):
        self.value += timedelta(seconds=seconds)


class Source:
    def resolve(self, verification_id):
        return TrustedVerificationEvidence(
            verification_id, "mission-1", "drone-1", "executor-1", "verifier-1",
            "1"*64, "2"*64, "anchor-1", "3"*64, "PASS", "4"*64,
            "verification-provenance", "ANCHORED", "2026-08-21T08:00:00+00:00",
        )


PINS = VerificationTrustPins("verifier-1", "1"*64, "2"*64, "anchor-1", "3"*64)


class FleetStatusProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "fleet.sqlite3"
        self.clock = Clock()
        self.store = FleetStatusStore(self.db, registry_instance_id="registry-1", clock=self.clock,
                                      verification_source=Source(), verification_pins=PINS)
        self.store.register_identity(FleetStatusIdentity(
            "drone-1", "executor-1", "mission-1", "parent-1", "DonkeyJJLove/ai_platform",
            "a"*40, "b"*40, "mission/fcsr", ("**",), ("cyber_lion/**",), "sandbox-1",
        ))
        self.projector = FleetStatusProjector(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_known_identity_survives_missing_mission_state(self):
        self.store.bind_runtime("mission-1", "runtime-1", "runtime-evidence")
        self.store.heartbeat("mission-1", "runtime-1", sequence=1, deadline_seconds=60, source_ref="hb")
        snap = self.projector.snapshot()
        self.assertEqual(snap.aggregate.total_known_drones, 1)
        self.assertEqual(snap.drone_records[0].mission_status, "UNKNOWN")
        self.assertTrue(any(a.anomaly_type == "MISSING_MISSION_STATE" for a in snap.anomalies))

    def test_missing_runtime_is_unreachable_not_idle(self):
        self.store.set_mission_state("mission-1", phase="IDLE", status="WAITING")
        record = self.projector.snapshot().drone_records[0]
        self.assertEqual(record.mission_status, "UNREACHABLE")
        self.assertEqual(record.heartbeat_state, "MISSING")
        self.assertNotEqual(record.mission_status, "IDLE")

    def test_missing_critical_projections_are_unknown(self):
        self.store.bind_runtime("mission-1", "runtime-1", "runtime-evidence")
        self.store.heartbeat("mission-1", "runtime-1", sequence=1, deadline_seconds=60, source_ref="hb")
        self.store.set_mission_state("mission-1", phase="IMPLEMENT", status="RUNNING")
        r = self.projector.snapshot().drone_records[0]
        self.assertEqual(r.authority_state, "UNKNOWN")
        self.assertEqual(r.sandbox_state, "UNKNOWN")
        self.assertEqual(r.verification_state, "UNKNOWN")
        self.assertEqual(r.effect_state, "UNKNOWN")
        self.assertEqual(r.reconciliation_state, "UNKNOWN")
        self.assertEqual(r.lease_state, "UNKNOWN")

    def test_stale_heartbeat_forces_unreachable_and_degrades_active_authority(self):
        self.store.bind_runtime("mission-1", "runtime-1", "runtime-evidence")
        self.store.set_mission_state("mission-1", phase="IMPLEMENT", status="RUNNING")
        self.store.heartbeat("mission-1", "runtime-1", sequence=1, deadline_seconds=10, source_ref="hb")
        self.store.project_observed_state("mission-1", kind="authority", state="ACTIVE", source_ref="authority")
        self.clock.tick(11)
        r = self.projector.snapshot().drone_records[0]
        self.assertEqual(r.heartbeat_state, "STALE")
        self.assertEqual(r.mission_status, "UNREACHABLE")
        self.assertEqual(r.authority_state, "UNUSABLE_STALE_OBSERVABILITY")

    def test_complete_evidence_preserves_anchored_floor(self):
        self.store.bind_runtime("mission-1", "runtime-1", "runtime-evidence")
        self.store.set_mission_state("mission-1", phase="VERIFY", status="RUNNING")
        self.store.heartbeat("mission-1", "runtime-1", sequence=1, deadline_seconds=60, source_ref="hb")
        self.store.project_verification("verify-1")
        for kind, state in (
            ("authority", "NONE"), ("sandbox", "CLEANED"), ("effect", "NONE"), ("reconciliation", "NOT_REQUIRED")
        ):
            self.store.project_observed_state("mission-1", kind=kind, state=state, source_ref=f"{kind}-source")
        self.store.append_receipt("mission-1", receipt_id="receipt-1", source_ref="receipt-source")
        r = self.projector.snapshot().drone_records[0]
        self.assertEqual(r.evidence_state, "COMPLETE")
        self.assertEqual(r.epistemic_class, "ANCHORED")

    def test_snapshot_digest_is_self_consistent(self):
        snap = self.projector.snapshot()
        self.assertEqual(snap.snapshot_digest, snap.recompute_digest())
        self.assertEqual(snap.to_wire()["snapshot_digest"], snap.snapshot_digest)

    def test_event_chain_head_corruption_fails_snapshot(self):
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE fleet_meta SET event_head=? WHERE singleton=1", ("f"*64,))
        conn.commit()
        conn.close()
        with self.assertRaises(FleetStatusStateError):
            self.projector.snapshot()

    def test_receipt_chain_head_corruption_fails_snapshot(self):
        self.store.append_receipt("mission-1", receipt_id="receipt-1", source_ref="receipt-source")
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE fleet_meta SET receipt_head=? WHERE singleton=1", ("f"*64,))
        conn.commit()
        conn.close()
        with self.assertRaises(FleetStatusStateError):
            self.projector.snapshot()

    def test_snapshot_revision_is_monotonic(self):
        first = self.projector.snapshot().snapshot_revision
        self.store.set_mission_state("mission-1", phase="PLAN", status="WAITING")
        second = self.projector.snapshot().snapshot_revision
        self.assertGreater(second, first)


if __name__ == "__main__":
    unittest.main()

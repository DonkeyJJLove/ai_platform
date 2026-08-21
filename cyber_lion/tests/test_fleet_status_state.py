from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect
import sqlite3
import tempfile
from pathlib import Path
import unittest

from cyber_lion.contracts.fleet_status import FleetStatusIdentity, TrustedVerificationEvidence, VerificationTrustPins
from cyber_lion.enterprise.fleet_status_state import FleetStatusStateError, FleetStatusStore


class Clock:
    def __init__(self):
        self.value = datetime(2026, 8, 21, 8, 0, tzinfo=timezone.utc)
    def __call__(self):
        return self.value
    def tick(self, seconds=1):
        self.value += timedelta(seconds=seconds)


class Source:
    def __init__(self, evidence):
        self.evidence = evidence
    def resolve(self, verification_id):
        if verification_id != self.evidence.verification_id:
            raise KeyError(verification_id)
        return self.evidence


def evidence(**overrides):
    values = dict(
        verification_id="verify-1", mission_id="mission-1", drone_id="drone-1", executor_id="executor-1",
        verifier_id="verifier-1", verifier_identity_digest="1"*64, verifier_implementation_digest="2"*64,
        trust_anchor_id="anchor-1", trust_anchor_digest="3"*64, verification_state="PASS",
        evidence_digest="4"*64, source_provenance_ref="provenance-1", epistemic_class="ANCHORED",
        observed_at="2026-08-21T08:00:00+00:00",
    )
    values.update(overrides)
    return TrustedVerificationEvidence(**values)


PINS = VerificationTrustPins("verifier-1", "1"*64, "2"*64, "anchor-1", "3"*64)


class FleetStatusStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "fleet.sqlite3"
        self.clock = Clock()
        self.source = Source(evidence())
        self.store = FleetStatusStore(self.db, registry_instance_id="registry-1", clock=self.clock,
                                      verification_source=self.source, verification_pins=PINS)
        self.identity = FleetStatusIdentity(
            "drone-1", "executor-1", "mission-1", "parent-1", "DonkeyJJLove/ai_platform",
            "a"*40, "b"*40, "mission/fcsr", ("**",), ("cyber_lion/**",), "sandbox-1",
        )
        self.store.register_identity(self.identity)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_duplicate_drone_and_executor_fail_closed(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.register_identity(self.identity)
        other = FleetStatusIdentity(
            "drone-2", "executor-1", "mission-2", "parent-1", "DonkeyJJLove/ai_platform",
            "a"*40, "b"*40, "other", ("**",), ("other/**",), "sandbox-2",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.register_identity(other)

    def test_runtime_binding_is_one_shot(self):
        self.store.bind_runtime("mission-1", "runtime-1", "runtime-evidence")
        with self.assertRaises(FleetStatusStateError):
            self.store.bind_runtime("mission-1", "runtime-2", "other")

    def test_heartbeat_sequence_and_time_rollback_denied(self):
        self.store.bind_runtime("mission-1", "runtime-1", "runtime-evidence")
        self.store.heartbeat("mission-1", "runtime-1", sequence=1, deadline_seconds=30, source_ref="hb-1")
        with self.assertRaises(FleetStatusStateError):
            self.store.heartbeat("mission-1", "runtime-1", sequence=1, deadline_seconds=30, source_ref="hb-2")
        self.clock.tick()
        self.store.heartbeat("mission-1", "runtime-1", sequence=2, deadline_seconds=30, source_ref="hb-2")
        self.clock.value -= timedelta(seconds=2)
        with self.assertRaises(FleetStatusStateError):
            self.store.heartbeat("mission-1", "runtime-1", sequence=3, deadline_seconds=30, source_ref="hb-3")

    def test_verification_is_resolved_from_fixed_source_not_raw_caller_evidence(self):
        sig = inspect.signature(self.store.project_verification)
        self.assertEqual(list(sig.parameters), ["verification_id"])
        out = self.store.project_verification("verify-1")
        self.assertEqual(out.verification_state, "PASS")

    def test_verifier_implementation_substitution_denied(self):
        self.source.evidence = evidence(verifier_implementation_digest="f"*64)
        with self.assertRaises(FleetStatusStateError):
            self.store.project_verification("verify-1")

    def test_executor_as_verifier_denied(self):
        self.source.evidence = evidence(verifier_id="executor-1")
        with self.assertRaises(FleetStatusStateError):
            self.store.project_verification("verify-1")

    def test_self_reported_done_is_denied(self):
        with self.assertRaises(FleetStatusStateError):
            self.store.set_mission_state("mission-1", phase="IMPLEMENT", status="DONE")

    def test_done_requires_trusted_pass(self):
        self.store.set_mission_state("mission-1", phase="IMPLEMENT", status="RUNNING")
        with self.assertRaises(FleetStatusStateError):
            self.store.mark_verified_done("mission-1")
        self.store.project_verification("verify-1")
        self.store.mark_verified_done("mission-1")
        reader = self.store.open_query_reader()
        try:
            row = reader.execute("SELECT status,closure_state FROM fleet_mission WHERE mission_id='mission-1'").fetchone()
            self.assertEqual((row["status"], row["closure_state"]), ("DONE", "READY_TO_CLOSE"))
        finally:
            reader.close()

    def test_append_only_event_and_receipt_are_database_enforced(self):
        self.store.append_receipt("mission-1", receipt_id="receipt-1", source_ref="receipt-source")
        conn = sqlite3.connect(self.db)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE fleet_event SET event_type='tamper' WHERE seq=1")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM fleet_event WHERE seq=1")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE fleet_receipt SET source_ref='tamper' WHERE seq=1")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM fleet_receipt WHERE seq=1")
        finally:
            conn.close()

    def test_query_reader_is_query_only(self):
        reader = self.store.open_query_reader()
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                reader.execute("INSERT INTO fleet_event(event_id,event_type,payload_json,previous_digest,event_digest,observed_at) VALUES('x','x','{}','x','x','x')")
        finally:
            reader.close()

    def test_overlapping_path_lease_denied(self):
        self.store.record_lease("mission-1", lease_id="l1", lease_type="PATH", resource="cyber_lion", state="ACTIVE", source_ref="lease")
        identity2 = FleetStatusIdentity(
            "drone-2", "executor-2", "mission-2", "parent-1", "DonkeyJJLove/ai_platform",
            "a"*40, "b"*40, "mission/2", ("**",), ("cyber_lion/tests/**",), "sandbox-2",
        )
        self.store.register_identity(identity2)
        with self.assertRaises(FleetStatusStateError):
            self.store.record_lease("mission-2", lease_id="l2", lease_type="PATH", resource="cyber_lion/tests", state="ACTIVE", source_ref="lease2")

    def test_close_requires_explicit_complete_critical_evidence(self):
        self.store.set_mission_state("mission-1", phase="IMPLEMENT", status="RUNNING")
        self.store.project_verification("verify-1")
        self.store.mark_verified_done("mission-1")
        with self.assertRaises(FleetStatusStateError):
            self.store.close_mission("mission-1")
        self.store.project_observed_state("mission-1", kind="authority", state="NONE", source_ref="authority-observer")
        self.store.project_observed_state("mission-1", kind="sandbox", state="CLEANED", source_ref="sandbox-observer")
        self.store.project_observed_state("mission-1", kind="effect", state="NONE", source_ref="effect-observer")
        self.store.project_observed_state("mission-1", kind="reconciliation", state="NOT_REQUIRED", source_ref="reconciler")
        self.store.append_receipt("mission-1", receipt_id="receipt-1", source_ref="receipt-source")
        self.store.close_mission("mission-1")
        reader = self.store.open_query_reader()
        try:
            row = reader.execute("SELECT closure_state FROM fleet_mission WHERE mission_id='mission-1'").fetchone()
            self.assertEqual(row["closure_state"], "CLOSED")
        finally:
            reader.close()

    def test_restart_safe_and_registry_substitution_denied(self):
        self.store.close()
        self.store = FleetStatusStore(self.db, registry_instance_id="registry-1", clock=self.clock,
                                      verification_source=self.source, verification_pins=PINS)
        reader = self.store.open_query_reader()
        try:
            self.assertEqual(reader.execute("SELECT count(*) FROM fleet_identity").fetchone()[0], 1)
        finally:
            reader.close()
        self.store.close()
        with self.assertRaises(FleetStatusStateError):
            FleetStatusStore(self.db, registry_instance_id="registry-2", clock=self.clock,
                             verification_source=self.source, verification_pins=PINS)
        self.store = FleetStatusStore(self.db, registry_instance_id="registry-1", clock=self.clock,
                                      verification_source=self.source, verification_pins=PINS)


if __name__ == "__main__":
    unittest.main()

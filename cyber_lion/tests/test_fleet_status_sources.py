from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import sqlite3
import tempfile
from pathlib import Path
import unittest

from cyber_lion.contracts.fleet_status import FleetStatusIdentity, TrustedVerificationEvidence, VerificationTrustPins
from cyber_lion.contracts.fleet_status_sources import (
    MissingStatusSource,
    ReconciledStatusFact,
    SourceConflict,
    StatusSourceIdentity,
    StatusSourceObservation,
    StatusSourceRead,
)
from cyber_lion.enterprise.fleet_status_state import FleetStatusStateError, FleetStatusStore


class Clock:
    def __init__(self):
        self.value = datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc)
    def __call__(self):
        return self.value
    def tick(self, seconds=1):
        self.value += timedelta(seconds=seconds)


class VerificationSource:
    def resolve(self, verification_id):
        return TrustedVerificationEvidence(
            verification_id, "mission-1", "drone-1", "executor-1", "verifier-1",
            "1"*64, "2"*64, "anchor-1", "3"*64, "PASS", "4"*64,
            "verification-prov", "ANCHORED", "2026-08-21T10:00:00+00:00",
        )


PINS = VerificationTrustPins("verifier-1", "1"*64, "2"*64, "anchor-1", "3"*64)


def source_identity(**overrides):
    values = dict(
        source_id="source-1", source_kind="FLEET_CONTROL", source_instance_id="instance-1",
        source_implementation_digest="5"*64, trust_anchor_id="source-anchor",
    )
    values.update(overrides)
    return StatusSourceIdentity(**values).validate()


def observation(state="RUNNING", *, observation_id="obs-1", evidence="6"*64):
    return StatusSourceObservation(
        observation_id, "mission-1", "drone-1", None, None,
        "DonkeyJJLove/ai_platform", "a"*40, "MISSION", state,
        (("phase", "IMPLEMENT"),), "source-prov", evidence, "OBSERVED",
    ).validate()


def read(clock, identity=None, observations=None):
    return StatusSourceRead(
        identity or source_identity(), clock().isoformat(), tuple(observations if observations is not None else (observation(),)),
    ).validate()


class FleetStatusSourceStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "fleet.sqlite3"
        self.clock = Clock()
        self.store = FleetStatusStore(
            self.db, registry_instance_id="registry-1", clock=self.clock,
            verification_source=VerificationSource(), verification_pins=PINS,
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()


    def test_caller_cannot_supply_source_sequence(self):
        import inspect
        sig = inspect.signature(self.store.ingest_source_read)
        self.assertEqual(list(sig.parameters), ["read"])
        self.assertNotIn("source_sequence", StatusSourceRead.__dataclass_fields__)

    def test_status_store_has_no_operational_authority_surface(self):
        import inspect
        forbidden = {"grant_authority", "revoke_authority", "dispatch_mission", "execute_effect", "acquire_live_lease", "release_live_lease"}
        public = {name for name, _ in inspect.getmembers(FleetStatusStore) if not name.startswith("_")}
        self.assertTrue(forbidden.isdisjoint(public), public & forbidden)

    def test_source_sequence_is_registry_owned_and_monotonic(self):
        first = self.store.ingest_source_read(read(self.clock))
        self.assertEqual(first.source_sequence, 1)
        self.clock.tick()
        second = self.store.ingest_source_read(read(self.clock, observations=(observation(observation_id="obs-2", evidence="7"*64),)))
        self.assertEqual(second.source_sequence, 2)
        self.assertNotEqual(first.source_chain_digest, second.source_chain_digest)

    def test_same_time_same_content_is_idempotent_but_different_content_denied(self):
        first_read = read(self.clock)
        first = self.store.ingest_source_read(first_read)
        again = self.store.ingest_source_read(first_read)
        self.assertEqual(first, again)
        with self.assertRaises(FleetStatusStateError):
            self.store.ingest_source_read(read(self.clock, observations=(observation(state="FAILED", observation_id="obs-x", evidence="8"*64),)))

    def test_source_time_regression_and_future_time_are_denied(self):
        self.store.ingest_source_read(read(self.clock))
        self.clock.tick(10)
        old = StatusSourceRead(source_identity(), "2026-08-21T09:59:59+00:00", (observation(),)).validate()
        with self.assertRaises(FleetStatusStateError):
            self.store.ingest_source_read(old)
        future = StatusSourceRead(source_identity(), "2026-08-21T11:00:00+00:00", (observation(),)).validate()
        with self.assertRaises(FleetStatusStateError):
            self.store.ingest_source_read(future)

    def test_source_instance_and_implementation_substitution_are_denied(self):
        self.store.ingest_source_read(read(self.clock))
        self.clock.tick()
        with self.assertRaises(FleetStatusStateError):
            self.store.ingest_source_read(read(self.clock, identity=source_identity(source_instance_id="evil")))
        with self.assertRaises(FleetStatusStateError):
            self.store.ingest_source_read(read(self.clock, identity=source_identity(source_implementation_digest="f"*64)))

    def test_empty_latest_read_supersedes_previous_current_observations(self):
        self.store.ingest_source_read(read(self.clock))
        self.assertEqual(len(self.store.source_observation_rows(current_only=True)), 1)
        self.clock.tick()
        self.store.ingest_source_read(read(self.clock, observations=()))
        self.assertEqual(self.store.source_observation_rows(current_only=True), [])
        self.assertEqual(len(self.store.source_observation_rows(current_only=False)), 1)

    def test_source_journal_and_decisions_are_database_append_only(self):
        self.store.ingest_source_read(read(self.clock))
        fact = ReconciledStatusFact(
            "mission-1", "MISSION", "RUNNING", (("phase", "IMPLEMENT"),),
            ("source-1",), ("source-prov",), "OBSERVED",
        ).validate()
        self.store.record_source_decisions((fact,), ())
        conn = sqlite3.connect(self.db)
        try:
            for sql in (
                "UPDATE fleet_source_batch SET source_kind='X' WHERE seq=1",
                "DELETE FROM fleet_source_batch WHERE seq=1",
                "UPDATE fleet_source_observation SET state='X' WHERE seq=1",
                "DELETE FROM fleet_source_observation WHERE seq=1",
                "UPDATE fleet_source_decision SET decision_type='X' WHERE seq=1",
                "DELETE FROM fleet_source_decision WHERE seq=1",
            ):
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute(sql)
        finally:
            conn.close()

    def test_checkpoint_corruption_fails_source_chain_validation(self):
        self.store.ingest_source_read(read(self.clock))
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE fleet_source_checkpoint SET source_chain_digest=? WHERE source_id='source-1'", ("f"*64,))
        conn.commit(); conn.close()
        with self.assertRaises(FleetStatusStateError):
            self.store.verify_source_chains()

    def test_decision_corruption_fails_snapshot_validation(self):
        fact = ReconciledStatusFact(
            "mission-1", "MISSION", "RUNNING", (("phase", "IMPLEMENT"),),
            ("source-1",), ("source-prov",), "OBSERVED",
        ).validate()
        self.store.record_source_decisions((fact,), ())
        conn = sqlite3.connect(self.db)
        conn.execute("DROP TRIGGER fleet_source_decision_no_update")
        conn.execute("UPDATE fleet_source_decision SET decision_json='{}' WHERE seq=1")
        conn.commit(); conn.close()
        with self.assertRaises(FleetStatusStateError):
            self.store.verify_source_decisions()

    def test_restart_preserves_source_checkpoint_and_chain(self):
        checkpoint = self.store.ingest_source_read(read(self.clock))
        self.store.close()
        self.store = FleetStatusStore(
            self.db, registry_instance_id="registry-1", clock=self.clock,
            verification_source=VerificationSource(), verification_pins=PINS,
        )
        self.assertEqual(self.store.source_checkpoints()[0]["source_chain_digest"], checkpoint.source_chain_digest)
        self.assertEqual(self.store.verify_source_chains()["source-1"], checkpoint.source_chain_digest)

    def test_identical_fact_can_resolve_a_previous_conflict_in_later_cycle(self):
        fact = ReconciledStatusFact(
            "mission-1", "AUTHORITY", "ACTIVE", (("grant_id", "g1"),),
            ("source-1",), ("prov-1",), "ANCHORED",
        ).validate()
        conflict = SourceConflict(
            "c1", "SOURCE_PROVENANCE_CONFLICT", "mission-1", "drone-1", "AUTHORITY",
            ("source-1",), (), ("prov-1",), self.clock().isoformat(),
        ).validate()
        self.store.record_source_decisions((fact,), (conflict,))
        latest = self.store.latest_source_decisions()
        self.assertEqual(latest[0]["decision_type"], "CONFLICT")
        self.clock.tick()
        self.store.record_source_decisions((fact,), ())
        latest = self.store.latest_source_decisions()
        self.assertEqual(latest[0]["decision_type"], "FACT")

    def test_missing_source_decision_supersedes_old_fact(self):
        fact = ReconciledStatusFact(
            "mission-1", "HEARTBEAT", "OBSERVED", (("runtime_id", "r1"),),
            ("hb-source",), ("hb-prov",), "ANCHORED",
        ).validate()
        self.store.record_source_decisions((fact,), ())
        self.clock.tick()
        missing = MissingStatusSource(
            "mission-1", "drone-1", "HEARTBEAT", ("HEARTBEAT",), self.clock().isoformat(),
        ).validate()
        self.store.record_source_decisions((), (), (missing,))
        self.assertEqual(self.store.latest_source_decisions()[0]["decision_type"], "MISSING")

    def test_close_denies_conflict_in_any_latest_dimension(self):
        identity = FleetStatusIdentity(
            "drone-1", "executor-1", "mission-1", "parent-1", "DonkeyJJLove/ai_platform",
            "a"*40, "b"*40, "mission/fcsr", ("**",), ("cyber_lion/**",), "sandbox-1",
        )
        self.store.register_identity(identity)
        self.store.bind_runtime("mission-1", "runtime-1", "runtime-prov")
        self.store.heartbeat("mission-1", "runtime-1", sequence=1, deadline_seconds=60, source_ref="hb")
        self.store.set_mission_state("mission-1", phase="VERIFY", status="RUNNING")
        self.store.project_verification("verify-1")
        self.store.mark_verified_done("mission-1")
        self.store.project_observed_state("mission-1", kind="authority", state="NONE", source_ref="auth")
        self.store.project_observed_state("mission-1", kind="sandbox", state="CLEANED", source_ref="sandbox")
        self.store.project_observed_state("mission-1", kind="effect", state="NONE", source_ref="effect")
        self.store.project_observed_state("mission-1", kind="reconciliation", state="NOT_REQUIRED", source_ref="rec")
        self.store.append_receipt("mission-1", receipt_id="receipt-1", source_ref="receipt")
        conflict = SourceConflict(
            "c-auth", "SOURCE_PROVENANCE_CONFLICT", "mission-1", "drone-1", "AUTHORITY",
            ("auth-source",), (), ("auth-prov",), self.clock().isoformat(),
        ).validate()
        fact = ReconciledStatusFact(
            "mission-1", "CI", "SUCCESS", (("run_id", "1"),),
            ("ci-source",), ("ci-prov",), "ANCHORED",
        ).validate()
        self.store.record_source_decisions((fact,), (conflict,))
        with self.assertRaises(FleetStatusStateError):
            self.store.close_mission("mission-1")


if __name__ == "__main__":
    unittest.main()

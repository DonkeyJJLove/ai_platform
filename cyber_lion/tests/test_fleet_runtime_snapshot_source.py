from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cyber_lion.contracts.fleet_reconciliation import ConvergenceReceipt, RECEIPT_PURPOSE
from cyber_lion.contracts.fleet_runtime_snapshot_source import (
    RuntimeSnapshotSourceConfig,
    RuntimeSnapshotSourceContractError,
    canonical_json,
)
from cyber_lion.enterprise.fleet_runtime_snapshot_source import (
    RuntimeSnapshotSourceError,
    _observe_runtime_state_with_details,
    _ro_connect,
    materialize_snapshot,
    observe_runtime_state,
)

REPO = "DonkeyJJLove/ai_platform"
MASTER = "9" * 40
TREE = "a" * 40
NOW = datetime(2026, 8, 21, 16, 0, tzinfo=timezone.utc)
ZERO = "0" * 64
MISSION = "F005-X"
EXECUTOR = "executor-F005-X"
RUNTIME = "runtime-F005-X"
BRANCH = "mission/f005-x"
BASELINE = "7" * 40
BASELINE_TREE = "8" * 40


def status_receipt_digest(previous: str, receipt_id: str, mission_id: str, source_ref: str, observed_at: str) -> str:
    return sha256(canonical_json({
        "previous_digest": previous,
        "receipt_id": receipt_id,
        "mission_id": mission_id,
        "source_ref": source_ref,
        "observed_at": observed_at,
    })).hexdigest()


def repository_decision_json(*, branch: str = BRANCH) -> str:
    values = [
        ["baseline_sha", BASELINE], ["baseline_tree_sha", BASELINE_TREE], ["branch", branch],
        ["branch_head_sha", "b" * 40], ["branch_tree_sha", "c" * 40], ["repository", REPO],
        ["source_record_observed_at", (NOW - timedelta(seconds=10)).isoformat()],
    ]
    return json.dumps({"fact": {"state": "OBSERVED", "value_items": values}}, sort_keys=True, separators=(",", ":"))


def create_status_db(path: Path, *, active: bool = False, include_repository_decision: bool = True) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
        CREATE TABLE fleet_meta(singleton INTEGER PRIMARY KEY, registry_instance_id TEXT, revision INTEGER,event_head TEXT, receipt_head TEXT);
        CREATE TABLE fleet_identity(mission_id TEXT PRIMARY KEY, executor_id TEXT, repository TEXT,baseline_sha TEXT, baseline_tree_sha TEXT, branch TEXT);
        CREATE TABLE fleet_mission(mission_id TEXT PRIMARY KEY, status TEXT);
        CREATE TABLE fleet_runtime(mission_id TEXT PRIMARY KEY, runtime_id TEXT);
        CREATE TABLE fleet_heartbeat(mission_id TEXT PRIMARY KEY, deadline_seconds INTEGER, observed_at TEXT);
        CREATE TABLE fleet_projection(mission_id TEXT, kind TEXT, state TEXT, observed_at TEXT,PRIMARY KEY(mission_id,kind));
        CREATE TABLE fleet_verification(mission_id TEXT PRIMARY KEY, verification_state TEXT);
        CREATE TABLE fleet_lease(lease_id TEXT PRIMARY KEY, mission_id TEXT, state TEXT);
        CREATE TABLE fleet_event(seq INTEGER PRIMARY KEY, event_type TEXT, mission_id TEXT, payload_json TEXT,previous_digest TEXT, event_digest TEXT, observed_at TEXT);
        CREATE TABLE fleet_receipt(seq INTEGER PRIMARY KEY, receipt_id TEXT, mission_id TEXT, source_ref TEXT,previous_digest TEXT, receipt_digest TEXT, observed_at TEXT);
        CREATE TABLE fleet_source_decision(seq INTEGER PRIMARY KEY, mission_id TEXT, dimension TEXT,decision_type TEXT, decision_json TEXT);
        """)
        state = "RUNNING" if active else "DONE"
        observed = (NOW - timedelta(seconds=10)).isoformat()
        rid = "receipt-F005-X"
        rd = status_receipt_digest(ZERO, rid, MISSION, "result:done", observed)
        conn.execute("INSERT INTO fleet_meta VALUES(1,?,?,?,?)", ("status-01", 1, ZERO, ZERO if active else rd))
        conn.execute("INSERT INTO fleet_identity VALUES(?,?,?,?,?,?)", (MISSION, EXECUTOR, REPO, BASELINE, BASELINE_TREE, BRANCH))
        conn.execute("INSERT INTO fleet_mission VALUES(?,?)", (MISSION, state))
        conn.execute("INSERT INTO fleet_runtime VALUES(?,?)", (MISSION, RUNTIME))
        conn.execute("INSERT INTO fleet_verification VALUES(?,?)", (MISSION, "PASS"))
        if active:
            conn.execute("INSERT INTO fleet_heartbeat VALUES(?,?,?)", (MISSION, 5, (NOW - timedelta(seconds=60)).isoformat()))
        for kind, value in (("authority", "ACTIVE" if active else "NONE"),("effect", "PREPARED" if active else "APPLIED"),("reconciliation", "PENDING" if active else "RESOLVED"),("sandbox", "RUNNING" if active else "CLEANED")):
            conn.execute("INSERT INTO fleet_projection VALUES(?,?,?,?)", (MISSION, kind, value, observed))
        if active:
            conn.execute("INSERT INTO fleet_lease VALUES(?,?,?)", ("write-lease-1", MISSION, "ACTIVE"))
        else:
            conn.execute("INSERT INTO fleet_receipt VALUES(1,?,?,?,?,?,?)", (rid, MISSION, "result:done", ZERO, rd, observed))
        if include_repository_decision:
            conn.execute("INSERT INTO fleet_source_decision VALUES(1,?,?,?,?)", (MISSION, "REPOSITORY", "FACT", repository_decision_json()))
        conn.commit()
    finally:
        conn.close()


def create_coordination_db(path: Path, *, active: bool = False) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
        CREATE TABLE fleet_coordination_meta(singleton INTEGER PRIMARY KEY, coordinator_id TEXT,revision INTEGER, event_head TEXT);
        CREATE TABLE fleet_coordination_mission(mission_id TEXT PRIMARY KEY, state TEXT, generation INTEGER, dispatch_id TEXT,fencing_token TEXT, branch TEXT, updated_at TEXT);
        CREATE TABLE fleet_coordination_active_lease(repository TEXT, lease_kind TEXT, resource TEXT, mission_id TEXT,dispatch_id TEXT, generation INTEGER);
        CREATE TABLE fleet_coordination_event(seq INTEGER PRIMARY KEY, event_id TEXT, event_type TEXT, mission_id TEXT,payload_json TEXT, previous_digest TEXT, event_digest TEXT, observed_at TEXT);
        """)
        conn.execute("INSERT INTO fleet_coordination_meta VALUES(1,?,?,?)", ("coord-01", 1, ZERO))
        if active:
            dispatch = "d" * 64
            fence = "f" * 64
            conn.execute("INSERT INTO fleet_coordination_mission VALUES(?,?,?,?,?,?,?)", (MISSION, "RUNNING", 1, dispatch, fence, BRANCH, NOW.isoformat()))
            conn.execute("INSERT INTO fleet_coordination_active_lease VALUES(?,?,?,?,?,?)", (REPO, "BRANCH", BRANCH, MISSION, dispatch, 1))
            conn.execute("INSERT INTO fleet_coordination_active_lease VALUES(?,?,?,?,?,?)", (REPO, "PATH", "cyber_lion/x.py", MISSION, dispatch, 1))
        else:
            conn.execute("INSERT INTO fleet_coordination_mission VALUES(?,?,?,?,?,?,?)", (MISSION, "DONE", 1, "d" * 64, "f" * 64, BRANCH, NOW.isoformat()))
        conn.commit()
    finally:
        conn.close()


def create_reconciliation_db(path: Path, *, master: str = MASTER, converged: bool = True, consumed: int = 0, purpose: str = RECEIPT_PURPOSE, receipt_preconditions: str | None = None) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
        CREATE TABLE reconciliation_inventory_head(repository TEXT PRIMARY KEY, inventory_id TEXT, inventory_revision INTEGER,inventory_digest TEXT, default_head_sha TEXT, observed_at TEXT);
        CREATE TABLE reconciliation_report(report_digest TEXT PRIMARY KEY, report_id TEXT, repository TEXT, inventory_id TEXT,inventory_revision INTEGER, inventory_digest TEXT, closure_preconditions_digest TEXT,default_head_sha TEXT, disposition TEXT, observed_at TEXT);
        CREATE TABLE convergence_receipt(receipt_digest TEXT PRIMARY KEY, receipt_id TEXT, report_digest TEXT, repository TEXT,inventory_id TEXT, inventory_revision INTEGER, inventory_digest TEXT,closure_preconditions_digest TEXT, default_head_sha TEXT, issued_at TEXT,purpose TEXT, consumed INTEGER);
        """)
        inv = "1" * 64; report_digest = "2" * 64; pre = "3" * 64; receipt_pre = receipt_preconditions or pre
        report_id = "report-1"; inventory_id = "inventory-1"; issued_at = NOW.isoformat()
        conn.execute("INSERT INTO reconciliation_inventory_head VALUES(?,?,?,?,?,?)", (REPO, inventory_id, 1, inv, master, NOW.isoformat()))
        conn.execute("INSERT INTO reconciliation_report VALUES(?,?,?,?,?,?,?,?,?,?)", (report_digest, report_id, REPO, inventory_id, 1, inv, pre, master, "CONVERGED" if converged else "RECONCILIATION_REQUIRED", NOW.isoformat()))
        canonical = ConvergenceReceipt.build(schema_version="1.0.0", receipt_id="receipt-1", repository=REPO, inventory_id=inventory_id, inventory_revision=1, inventory_digest=inv, report_id=report_id, report_digest=report_digest, closure_preconditions_digest=receipt_pre, default_head_sha=master, issued_at=issued_at)
        conn.execute("INSERT INTO convergence_receipt VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (canonical.receipt_digest, canonical.receipt_id, report_digest, REPO, inventory_id, 1, inv, receipt_pre, master, issued_at, purpose, consumed))
        conn.commit()
    finally:
        conn.close()


def append_orphan_receipt(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        previous = str(conn.execute("SELECT receipt_head FROM fleet_meta WHERE singleton=1").fetchone()[0])
        observed = (NOW - timedelta(seconds=5)).isoformat()
        digest = status_receipt_digest(previous, "orphan-result", "ORPHAN", "result:orphan", observed)
        conn.execute("INSERT INTO fleet_receipt VALUES(2,?,?,?,?,?,?)", ("orphan-result", "ORPHAN", "result:orphan", previous, digest, observed))
        conn.execute("UPDATE fleet_meta SET receipt_head=? WHERE singleton=1", (digest,)); conn.commit()
    finally:
        conn.close()


class RuntimeSnapshotSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(); root = Path(self.tmp.name)
        self.status = root / "status.sqlite"; self.coordination = root / "coordination.sqlite"; self.reconciliation = root / "reconciliation.sqlite"; self.output = root / "out" / "fleet-convergence-snapshot.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def config(self) -> RuntimeSnapshotSourceConfig:
        return RuntimeSnapshotSourceConfig(repository=REPO, current_master=MASTER, current_master_tree=TREE, source_instance="lion-runtime-01", status_db_path=str(self.status), coordination_db_path=str(self.coordination), reconciliation_db_path=str(self.reconciliation), output_path=str(self.output)).validate()

    def create_valid_sources(self) -> None:
        create_status_db(self.status); create_coordination_db(self.coordination); create_reconciliation_db(self.reconciliation)

    def test_terminal_consistent_sources_materialize_closable_snapshot(self):
        self.create_valid_sources(); value = materialize_snapshot(self.config(), clock=lambda: NOW)
        self.assertTrue(self.output.is_file()); self.assertEqual(value, json.loads(self.output.read_text(encoding="utf-8")))
        for name in ("active_missions", "unknown_missions", "unresolved_write_leases", "unknown_results", "late_unreconciled_results", "missing_heartbeats", "stale_heartbeats", "unknown_branch_ownership", "unowned_active_branches", "unreconciled_effects", "reconciliation_disagreements", "active_authority", "residual_authority"):
            self.assertEqual(value[name], 0, name)
        self.assertTrue(value["durable_state_consistency"]); self.assertTrue(value["event_chain_consistency"]); self.assertTrue(value["generation_fencing_consistency"]); self.assertTrue(value["inventory_complete"]); self.assertEqual(value["source_kind"], "AUTHORITATIVE_RUNTIME_STORE")

    def test_query_only_connection_rejects_write(self):
        self.create_valid_sources(); conn = _ro_connect(str(self.status))
        try:
            self.assertEqual(conn.execute("PRAGMA query_only").fetchone()[0], 1)
            with self.assertRaises(sqlite3.OperationalError): conn.execute("DELETE FROM fleet_mission")
        finally: conn.close()

    def test_active_runtime_is_observed_not_defaulted_to_zero(self):
        create_status_db(self.status, active=True); create_coordination_db(self.coordination, active=True); create_reconciliation_db(self.reconciliation)
        observed = observe_runtime_state(self.config(), clock=lambda: NOW)
        self.assertEqual(observed.active_missions, 1); self.assertGreater(observed.unresolved_write_leases, 0); self.assertEqual(observed.active_authority, 1); self.assertEqual(observed.residual_authority, 1); self.assertEqual(observed.stale_heartbeats, 1); self.assertGreater(observed.unreconciled_effects, 0)

    def test_missing_authoritative_source_denied(self):
        create_status_db(self.status); create_coordination_db(self.coordination)
        with self.assertRaises(RuntimeSnapshotSourceError): observe_runtime_state(self.config(), clock=lambda: NOW)

    def test_missing_runtime_registry_table_denied(self):
        self.create_valid_sources(); conn = sqlite3.connect(self.status); conn.execute("DROP TABLE fleet_runtime"); conn.commit(); conn.close()
        with self.assertRaises(RuntimeSnapshotSourceError): observe_runtime_state(self.config(), clock=lambda: NOW)

    def test_missing_verification_registry_table_denied(self):
        self.create_valid_sources(); conn = sqlite3.connect(self.status); conn.execute("DROP TABLE fleet_verification"); conn.commit(); conn.close()
        with self.assertRaises(RuntimeSnapshotSourceError): observe_runtime_state(self.config(), clock=lambda: NOW)

    def test_runtime_inventory_mismatch_fails_closed(self):
        self.create_valid_sources(); conn = sqlite3.connect(self.status); conn.execute("DELETE FROM fleet_runtime WHERE mission_id=?", (MISSION,)); conn.commit(); conn.close()
        observed = observe_runtime_state(self.config(), clock=lambda: NOW); self.assertFalse(observed.inventory_complete); self.assertGreater(observed.unknown_missions, 0)

    def test_verification_inventory_mismatch_fails_closed(self):
        self.create_valid_sources(); conn = sqlite3.connect(self.status); conn.execute("DELETE FROM fleet_verification WHERE mission_id=?", (MISSION,)); conn.commit(); conn.close()
        observed = observe_runtime_state(self.config(), clock=lambda: NOW); self.assertFalse(observed.inventory_complete); self.assertGreater(observed.unknown_missions, 0)

    def test_orphan_result_is_counted_and_blocks_inventory(self):
        self.create_valid_sources(); append_orphan_receipt(self.status); observed = observe_runtime_state(self.config(), clock=lambda: NOW); self.assertEqual(observed.unknown_results, 1); self.assertFalse(observed.inventory_complete)

    def test_repository_ownership_evidence_is_required(self):
        create_status_db(self.status, include_repository_decision=False); create_coordination_db(self.coordination); create_reconciliation_db(self.reconciliation)
        observed = observe_runtime_state(self.config(), clock=lambda: NOW); self.assertGreater(observed.unknown_branch_ownership, 0); self.assertFalse(observed.inventory_complete)

    def test_repository_ownership_mismatch_fails_closed(self):
        self.create_valid_sources(); conn = sqlite3.connect(self.status); conn.execute("UPDATE fleet_source_decision SET decision_json=? WHERE dimension='REPOSITORY'", (repository_decision_json(branch="mission/wrong"),)); conn.commit(); conn.close()
        observed = observe_runtime_state(self.config(), clock=lambda: NOW); self.assertGreater(observed.unknown_branch_ownership, 0); self.assertFalse(observed.inventory_complete)

    def test_malformed_critical_decision_denied(self):
        self.create_valid_sources(); conn = sqlite3.connect(self.status); conn.execute("INSERT INTO fleet_source_decision VALUES(2,?,?,?,?)", (MISSION, "AUTHORITY", "BROKEN", "{}")); conn.commit(); conn.close()
        with self.assertRaises(RuntimeSnapshotSourceError): observe_runtime_state(self.config(), clock=lambda: NOW)

    def test_consumed_reconciliation_receipt_is_replay_denied(self):
        create_status_db(self.status); create_coordination_db(self.coordination); create_reconciliation_db(self.reconciliation, consumed=1)
        observed = observe_runtime_state(self.config(), clock=lambda: NOW); self.assertFalse(observed.inventory_complete); self.assertGreater(observed.reconciliation_disagreements, 0)

    def test_wrong_reconciliation_receipt_purpose_is_denied(self):
        create_status_db(self.status); create_coordination_db(self.coordination); create_reconciliation_db(self.reconciliation, purpose="FLEET_CLOSURE")
        observed = observe_runtime_state(self.config(), clock=lambda: NOW); self.assertFalse(observed.inventory_complete); self.assertGreater(observed.reconciliation_disagreements, 0)

    def test_closure_preconditions_digest_mismatch_is_denied(self):
        create_status_db(self.status); create_coordination_db(self.coordination); create_reconciliation_db(self.reconciliation, receipt_preconditions="5" * 64)
        observed = observe_runtime_state(self.config(), clock=lambda: NOW); self.assertFalse(observed.inventory_complete); self.assertGreater(observed.reconciliation_disagreements, 0)

    def test_reconciliation_head_substitution_fails_inventory_complete(self):
        create_status_db(self.status); create_coordination_db(self.coordination); create_reconciliation_db(self.reconciliation, master="8" * 40)
        observed = observe_runtime_state(self.config(), clock=lambda: NOW); self.assertFalse(observed.inventory_complete)

    def test_nonconverged_reconciliation_is_blocking(self):
        create_status_db(self.status); create_coordination_db(self.coordination); create_reconciliation_db(self.reconciliation, converged=False)
        observed = observe_runtime_state(self.config(), clock=lambda: NOW); self.assertFalse(observed.inventory_complete); self.assertGreater(observed.reconciliation_disagreements, 0)

    def test_relative_runtime_source_path_denied(self):
        self.create_valid_sources()
        with self.assertRaises(RuntimeSnapshotSourceContractError):
            RuntimeSnapshotSourceConfig(repository=REPO, current_master=MASTER, current_master_tree=TREE, source_instance="lion-runtime-01", status_db_path="relative.sqlite", coordination_db_path=str(self.coordination), reconciliation_db_path=str(self.reconciliation), output_path=str(self.output)).validate()

    def test_detailed_observation_preserves_public_observed_state_and_source_digest(self):
        self.create_valid_sources()
        details = _observe_runtime_state_with_details(self.config(), clock=lambda: NOW)
        public = observe_runtime_state(self.config(), clock=lambda: NOW)
        self.assertEqual(details.observed, public)
        self.assertEqual(details.observed.source_digest, public.source_digest)
        self.assertEqual(details.active_ids, frozenset())
        self.assertEqual(details.unknown_ids, frozenset())
        self.assertEqual(details.status_registry_instance_id, "status-01")
        self.assertEqual(details.status_revision, 1)
        self.assertEqual(details.coordinator_id, "coord-01")
        self.assertEqual(details.coordination_revision, 1)

    def test_invalid_status_source_identity_and_revision_fail_closed(self):
        self.create_valid_sources(); conn = sqlite3.connect(self.status); conn.execute("UPDATE fleet_meta SET registry_instance_id='' WHERE singleton=1"); conn.commit(); conn.close()
        with self.assertRaises(RuntimeSnapshotSourceError): observe_runtime_state(self.config(), clock=lambda: NOW)
        self.status.unlink(); create_status_db(self.status); conn = sqlite3.connect(self.status); conn.execute("UPDATE fleet_meta SET revision=-1 WHERE singleton=1"); conn.commit(); conn.close()
        with self.assertRaises(RuntimeSnapshotSourceError): observe_runtime_state(self.config(), clock=lambda: NOW)

    def test_invalid_coordination_source_identity_and_revision_fail_closed(self):
        self.create_valid_sources(); conn = sqlite3.connect(self.coordination); conn.execute("UPDATE fleet_coordination_meta SET coordinator_id='' WHERE singleton=1"); conn.commit(); conn.close()
        with self.assertRaises(RuntimeSnapshotSourceError): observe_runtime_state(self.config(), clock=lambda: NOW)
        self.coordination.unlink(); create_coordination_db(self.coordination); conn = sqlite3.connect(self.coordination); conn.execute("UPDATE fleet_coordination_meta SET revision=-1 WHERE singleton=1"); conn.commit(); conn.close()
        with self.assertRaises(RuntimeSnapshotSourceError): observe_runtime_state(self.config(), clock=lambda: NOW)


if __name__ == "__main__":
    unittest.main()
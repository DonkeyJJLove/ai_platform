from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cyber_lion.contracts.fleet_runtime_snapshot_source import (
    RuntimeSnapshotSourceConfig,
    RuntimeSnapshotSourceContractError,
    canonical_json,
)
from cyber_lion.enterprise.fleet_runtime_snapshot_source import (
    RuntimeSnapshotSourceError,
    materialize_snapshot,
    observe_runtime_state,
)

REPO = "DonkeyJJLove/ai_platform"
MASTER = "9" * 40
TREE = "a" * 40
NOW = datetime(2026, 8, 21, 16, 0, tzinfo=timezone.utc)
ZERO = "0" * 64


def receipt_digest(receipt_id: str, mission_id: str, source_ref: str, observed_at: str) -> str:
    return sha256(canonical_json({
        "previous_digest": ZERO,
        "receipt_id": receipt_id,
        "mission_id": mission_id,
        "source_ref": source_ref,
        "observed_at": observed_at,
    })).hexdigest()


def create_status_db(path: Path, *, active: bool = False) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
        CREATE TABLE fleet_meta(singleton INTEGER PRIMARY KEY, registry_instance_id TEXT, revision INTEGER, event_head TEXT, receipt_head TEXT);
        CREATE TABLE fleet_identity(mission_id TEXT PRIMARY KEY);
        CREATE TABLE fleet_mission(mission_id TEXT PRIMARY KEY, status TEXT);
        CREATE TABLE fleet_heartbeat(mission_id TEXT PRIMARY KEY, deadline_seconds INTEGER, observed_at TEXT);
        CREATE TABLE fleet_projection(mission_id TEXT, kind TEXT, state TEXT, observed_at TEXT, PRIMARY KEY(mission_id,kind));
        CREATE TABLE fleet_lease(lease_id TEXT PRIMARY KEY, mission_id TEXT, state TEXT);
        CREATE TABLE fleet_event(seq INTEGER PRIMARY KEY, event_type TEXT, mission_id TEXT, payload_json TEXT, previous_digest TEXT, event_digest TEXT, observed_at TEXT);
        CREATE TABLE fleet_receipt(seq INTEGER PRIMARY KEY, receipt_id TEXT, mission_id TEXT, source_ref TEXT, previous_digest TEXT, receipt_digest TEXT, observed_at TEXT);
        CREATE TABLE fleet_source_decision(seq INTEGER PRIMARY KEY, mission_id TEXT, dimension TEXT, decision_type TEXT, decision_json TEXT);
        """)
        mission_id = "F005-X"
        state = "RUNNING" if active else "DONE"
        observed = (NOW - timedelta(seconds=10)).isoformat()
        rid = "receipt-F005-X"
        rd = receipt_digest(rid, mission_id, "result:done", observed)
        conn.execute("INSERT INTO fleet_meta VALUES(1,?,?,?,?)", ("status-01", 1, ZERO, ZERO if active else rd))
        conn.execute("INSERT INTO fleet_identity VALUES(?)", (mission_id,))
        conn.execute("INSERT INTO fleet_mission VALUES(?,?)", (mission_id, state))
        if active:
            conn.execute("INSERT INTO fleet_heartbeat VALUES(?,?,?)", (mission_id, 5, (NOW - timedelta(seconds=60)).isoformat()))
        for kind, value in (
            ("authority", "ACTIVE" if active else "NONE"),
            ("effect", "PREPARED" if active else "APPLIED"),
            ("reconciliation", "PENDING" if active else "RESOLVED"),
            ("sandbox", "RUNNING" if active else "CLEANED"),
        ):
            conn.execute("INSERT INTO fleet_projection VALUES(?,?,?,?)", (mission_id, kind, value, observed))
        if active:
            conn.execute("INSERT INTO fleet_lease VALUES(?,?,?)", ("write-lease-1", mission_id, "ACTIVE"))
        else:
            conn.execute("INSERT INTO fleet_receipt VALUES(1,?,?,?,?,?,?)", (rid, mission_id, "result:done", ZERO, rd, observed))
        conn.commit()
    finally:
        conn.close()


def create_coordination_db(path: Path, *, active: bool = False) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
        CREATE TABLE fleet_coordination_meta(singleton INTEGER PRIMARY KEY, coordinator_id TEXT, revision INTEGER, event_head TEXT);
        CREATE TABLE fleet_coordination_mission(
            mission_id TEXT PRIMARY KEY, state TEXT, generation INTEGER, dispatch_id TEXT,
            fencing_token TEXT, branch TEXT, updated_at TEXT
        );
        CREATE TABLE fleet_coordination_active_lease(
            repository TEXT, lease_kind TEXT, resource TEXT, mission_id TEXT,
            dispatch_id TEXT, generation INTEGER
        );
        CREATE TABLE fleet_coordination_event(
            seq INTEGER PRIMARY KEY, event_id TEXT, event_type TEXT, mission_id TEXT,
            payload_json TEXT, previous_digest TEXT, event_digest TEXT, observed_at TEXT
        );
        """)
        conn.execute("INSERT INTO fleet_coordination_meta VALUES(1,?,?,?)", ("coord-01", 1, ZERO))
        if active:
            dispatch = "d" * 64
            fence = "f" * 64
            conn.execute(
                "INSERT INTO fleet_coordination_mission VALUES(?,?,?,?,?,?,?)",
                ("F005-X", "RUNNING", 1, dispatch, fence, "mission/f005-x", NOW.isoformat()),
            )
            conn.execute(
                "INSERT INTO fleet_coordination_active_lease VALUES(?,?,?,?,?,?)",
                (REPO, "BRANCH", "mission/f005-x", "F005-X", dispatch, 1),
            )
            conn.execute(
                "INSERT INTO fleet_coordination_active_lease VALUES(?,?,?,?,?,?)",
                (REPO, "PATH", "cyber_lion/x.py", "F005-X", dispatch, 1),
            )
        else:
            conn.execute(
                "INSERT INTO fleet_coordination_mission VALUES(?,?,?,?,?,?,?)",
                ("F005-X", "DONE", 1, "d" * 64, "f" * 64, "mission/f005-x", NOW.isoformat()),
            )
        conn.commit()
    finally:
        conn.close()


def create_reconciliation_db(path: Path, *, master: str = MASTER, converged: bool = True) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
        CREATE TABLE reconciliation_inventory_head(
            repository TEXT PRIMARY KEY, inventory_id TEXT, inventory_revision INTEGER,
            inventory_digest TEXT, default_head_sha TEXT, observed_at TEXT
        );
        CREATE TABLE reconciliation_report(
            report_digest TEXT PRIMARY KEY, report_id TEXT, repository TEXT, inventory_id TEXT,
            inventory_revision INTEGER, inventory_digest TEXT, closure_preconditions_digest TEXT,
            default_head_sha TEXT, disposition TEXT, observed_at TEXT
        );
        CREATE TABLE convergence_receipt(
            receipt_digest TEXT PRIMARY KEY, receipt_id TEXT, report_digest TEXT, repository TEXT,
            inventory_id TEXT, inventory_revision INTEGER, inventory_digest TEXT,
            closure_preconditions_digest TEXT, default_head_sha TEXT, issued_at TEXT,
            purpose TEXT, consumed INTEGER
        );
        """)
        inv = "1" * 64
        report = "2" * 64
        pre = "3" * 64
        conn.execute(
            "INSERT INTO reconciliation_inventory_head VALUES(?,?,?,?,?,?)",
            (REPO, "inventory-1", 1, inv, master, NOW.isoformat()),
        )
        conn.execute(
            "INSERT INTO reconciliation_report VALUES(?,?,?,?,?,?,?,?,?,?)",
            (report, "report-1", REPO, "inventory-1", 1, inv, pre, master,
             "CONVERGED" if converged else "RECONCILIATION_REQUIRED", NOW.isoformat()),
        )
        conn.execute(
            "INSERT INTO convergence_receipt VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            ("4" * 64, "receipt-1", report, REPO, "inventory-1", 1, inv, pre, master,
             NOW.isoformat(), "FLEET_CLOSURE", 0),
        )
        conn.commit()
    finally:
        conn.close()


class RuntimeSnapshotSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.status = root / "status.sqlite"
        self.coordination = root / "coordination.sqlite"
        self.reconciliation = root / "reconciliation.sqlite"
        self.output = root / "out" / "fleet-convergence-snapshot.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def config(self) -> RuntimeSnapshotSourceConfig:
        return RuntimeSnapshotSourceConfig(
            repository=REPO,
            current_master=MASTER,
            current_master_tree=TREE,
            source_instance="lion-runtime-01",
            status_db_path=str(self.status),
            coordination_db_path=str(self.coordination),
            reconciliation_db_path=str(self.reconciliation),
            output_path=str(self.output),
        ).validate()

    def test_terminal_consistent_sources_materialize_closable_snapshot(self):
        create_status_db(self.status)
        create_coordination_db(self.coordination)
        create_reconciliation_db(self.reconciliation)
        value = materialize_snapshot(self.config(), clock=lambda: NOW)
        self.assertTrue(self.output.is_file())
        self.assertEqual(value, json.loads(self.output.read_text(encoding="utf-8")))
        for name in (
            "active_missions", "unknown_missions", "unresolved_write_leases", "unknown_results",
            "late_unreconciled_results", "missing_heartbeats", "stale_heartbeats",
            "unknown_branch_ownership", "unowned_active_branches", "unreconciled_effects",
            "reconciliation_disagreements", "active_authority", "residual_authority",
        ):
            self.assertEqual(value[name], 0, name)
        self.assertTrue(value["durable_state_consistency"])
        self.assertTrue(value["event_chain_consistency"])
        self.assertTrue(value["generation_fencing_consistency"])
        self.assertTrue(value["inventory_complete"])
        self.assertEqual(value["source_kind"], "AUTHORITATIVE_RUNTIME_STORE")

    def test_active_runtime_is_observed_not_defaulted_to_zero(self):
        create_status_db(self.status, active=True)
        create_coordination_db(self.coordination, active=True)
        create_reconciliation_db(self.reconciliation)
        observed = observe_runtime_state(self.config(), clock=lambda: NOW)
        self.assertEqual(observed.active_missions, 1)
        self.assertGreater(observed.unresolved_write_leases, 0)
        self.assertEqual(observed.active_authority, 1)
        self.assertEqual(observed.residual_authority, 1)
        self.assertEqual(observed.stale_heartbeats, 1)
        self.assertGreater(observed.unreconciled_effects, 0)

    def test_missing_authoritative_source_denied(self):
        create_status_db(self.status)
        create_coordination_db(self.coordination)
        with self.assertRaises(RuntimeSnapshotSourceError):
            observe_runtime_state(self.config(), clock=lambda: NOW)

    def test_reconciliation_head_substitution_fails_inventory_complete(self):
        create_status_db(self.status)
        create_coordination_db(self.coordination)
        create_reconciliation_db(self.reconciliation, master="8" * 40)
        observed = observe_runtime_state(self.config(), clock=lambda: NOW)
        self.assertFalse(observed.inventory_complete)

    def test_nonconverged_reconciliation_is_blocking(self):
        create_status_db(self.status)
        create_coordination_db(self.coordination)
        create_reconciliation_db(self.reconciliation, converged=False)
        observed = observe_runtime_state(self.config(), clock=lambda: NOW)
        self.assertFalse(observed.inventory_complete)
        self.assertGreater(observed.reconciliation_disagreements, 0)

    def test_relative_runtime_source_path_denied(self):
        create_status_db(self.status)
        create_coordination_db(self.coordination)
        create_reconciliation_db(self.reconciliation)
        with self.assertRaises(RuntimeSnapshotSourceContractError):
            RuntimeSnapshotSourceConfig(
                repository=REPO,
                current_master=MASTER,
                current_master_tree=TREE,
                source_instance="lion-runtime-01",
                status_db_path="relative.sqlite",
                coordination_db_path=str(self.coordination),
                reconciliation_db_path=str(self.reconciliation),
                output_path=str(self.output),
            ).validate()


if __name__ == "__main__":
    unittest.main()

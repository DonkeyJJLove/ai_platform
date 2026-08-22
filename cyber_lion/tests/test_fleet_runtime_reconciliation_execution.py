from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from cyber_lion.contracts.fleet_reconciliation import ReconciliationTrustPins
from cyber_lion.contracts.fleet_runtime_reconciliation_execution import (
    REPOSITORY,
    RUNTIME_SOURCE_INSTANCE_ID,
    RuntimeReconciliationExecutionConfig,
    RuntimeReconciliationExecutionReceipt,
)
from cyber_lion.enterprise.fleet_reconciliation import ReconciliationStore
from cyber_lion.enterprise.fleet_runtime_reconciliation_execution import (
    RuntimeReconciliationExecutionError,
    execute_runtime_reconciliation,
)
from cyber_lion.enterprise.fleet_runtime_reconciliation_ingestion import (
    _build_inventory,
    _load_observation,
)
from cyber_lion.tests.test_fleet_runtime_snapshot_source import create_coordination_db, create_status_db

MASTER = "a" * 40
TREE = "b" * 40
ROOT = r"C:\Users\d2j3\Documents\LION\runtime\f005"
PINS = ReconciliationTrustPins(
    source_id="lion-runtime-reconciliation-source",
    source_instance_id=RUNTIME_SOURCE_INSTANCE_ID,
    source_implementation_digest="1" * 64,
    trust_anchor_id="lion-runtime-reconciliation-root-01",
).validate()


class RuntimeReconciliationExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = mock.patch.dict(os.environ, {"LION_FLEET_RUNTIME_ROOT": ROOT}, clear=False)
        self.env.start()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        self.external = root / "runtime"
        self.external.mkdir()
        self.status = self.external / "status.sqlite"
        self.coordination = self.external / "coordination.sqlite"
        self.reconciliation = self.external / "reconciliation.sqlite"
        self.trust = self.external / "reconciliation-trust.json"
        self.inventory_file = self.external / "repository-inventory.json"
        self.receipt_file = self.external / "reconciliation-execution-receipt.json"
        create_status_db(self.status)
        create_coordination_db(self.coordination)
        self.trust.write_text(json.dumps({
            "source_id": PINS.source_id,
            "source_instance_id": PINS.source_instance_id,
            "source_implementation_digest": PINS.source_implementation_digest,
            "trust_anchor_id": PINS.trust_anchor_id,
        }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        self.observed_at = "2026-08-21T20:45:00+00:00"
        self.observation = {
            "schema_version": "1.0.0",
            "repository": REPOSITORY,
            "inventory_revision": 1,
            "default_branch": "master",
            "default_head_sha": MASTER,
            "observed_at": self.observed_at,
            "branches": [{
                "branch": "mission/example",
                "branch_head_sha": "c" * 40,
                "mission_id": "MISSION-EXAMPLE",
                "baseline_sha": "d" * 40,
                "ownership_state": "TERMINAL",
                "ancestry_state": "HEAD_ANCESTOR_OF_DEFAULT",
                "ahead_by": 0,
                "behind_by": 1,
                "superseded_by_branch": None,
                "supersession_provenance_ref": None,
                "source_provenance_ref": "runtime-observation:test",
                "epistemic_class": "OBSERVED",
                "observed_at": self.observed_at,
            }],
        }
        self.inventory_file.write_text(json.dumps(self.observation, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        observation = _load_observation(self.inventory_file.read_bytes(), repository=REPOSITORY, current_master=MASTER)
        self.inventory = _build_inventory(observation, PINS)
        store = ReconciliationStore(self.reconciliation, trust_pins=PINS, clock=lambda: datetime.now(timezone.utc))
        store.record_inventory(self.inventory)
        store.close()

    def tearDown(self) -> None:
        self.tmp.cleanup()
        self.env.stop()

    def config(self, *, master: str = MASTER, tree: str = TREE) -> RuntimeReconciliationExecutionConfig:
        return RuntimeReconciliationExecutionConfig(REPOSITORY, master, tree).validate()

    def paths(self):
        return {
            "status": self.status,
            "coordination": self.coordination,
            "reconciliation": self.reconciliation,
            "trust": self.trust,
            "inventory": self.inventory_file,
            "receipt": self.receipt_file,
        }

    def execute(self, config=None):
        return execute_runtime_reconciliation(
            config or self.config(),
            repository_root=str(self.repo),
            physical_paths=self.paths(),
        )

    def test_converged_execution_generates_report_receipt_and_immutable_execution_receipt(self) -> None:
        receipt = self.execute()
        self.assertEqual(receipt.disposition, "CONVERGED")
        self.assertIsNotNone(receipt.convergence_receipt_digest)
        self.assertFalse(receipt.receipt_consumed)
        self.assertFalse(receipt.mission_closed)
        self.assertFalse(receipt.fleet_closed)
        self.assertTrue(self.receipt_file.is_file())
        stored = RuntimeReconciliationExecutionReceipt(**json.loads(self.receipt_file.read_text(encoding="utf-8"))).validate()
        self.assertEqual(stored.execution_receipt_digest, receipt.execution_receipt_digest)
        conn = sqlite3.connect(self.reconciliation)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM reconciliation_inventory_head").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM reconciliation_report").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM convergence_receipt").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM convergence_receipt WHERE consumed<>0").fetchone()[0], 0)
        finally:
            conn.close()

    def test_inventory_is_never_re_recorded(self) -> None:
        before = sqlite3.connect(self.reconciliation)
        try:
            head_before = before.execute("SELECT * FROM reconciliation_inventory_head").fetchone()
        finally:
            before.close()
        self.execute()
        after = sqlite3.connect(self.reconciliation)
        try:
            head_after = after.execute("SELECT * FROM reconciliation_inventory_head").fetchone()
        finally:
            after.close()
        self.assertEqual(head_before, head_after)

    def test_missing_recorded_inventory_fails_closed(self) -> None:
        conn = sqlite3.connect(self.reconciliation)
        try:
            conn.execute("DELETE FROM reconciliation_inventory_head")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(RuntimeReconciliationExecutionError):
            self.execute()

    def test_stale_inventory_binding_fails_closed(self) -> None:
        conn = sqlite3.connect(self.reconciliation)
        try:
            conn.execute("UPDATE reconciliation_inventory_head SET inventory_digest=?", ("f" * 64,))
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(RuntimeReconciliationExecutionError):
            self.execute()

    def test_master_drift_fails_closed(self) -> None:
        with self.assertRaises(RuntimeReconciliationExecutionError):
            self.execute(self.config(master="e" * 40))

    def test_trust_substitution_fails_closed(self) -> None:
        value = json.loads(self.trust.read_text(encoding="utf-8"))
        value["source_instance_id"] = "attacker"
        self.trust.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        with self.assertRaises(RuntimeReconciliationExecutionError):
            self.execute()

    def test_runtime_source_missing_fails_closed(self) -> None:
        self.status.unlink()
        with self.assertRaises(Exception):
            self.execute()

    def test_execution_receipt_is_one_shot(self) -> None:
        self.execute()
        with self.assertRaises(RuntimeReconciliationExecutionError):
            self.execute()

    def test_contract_rejects_prohibited_effect_assertion(self) -> None:
        with self.assertRaises(ValueError):
            RuntimeReconciliationExecutionReceipt.build(
                schema_version="1.0.0",
                repository=REPOSITORY,
                current_master=MASTER,
                current_master_tree=TREE,
                inventory_id="inventory-1",
                inventory_revision=1,
                inventory_digest="1" * 64,
                closure_preconditions_digest="2" * 64,
                report_id="report-1",
                report_digest="3" * 64,
                disposition="CONVERGED",
                convergence_receipt_digest="4" * 64,
                execution_config_digest="5" * 64,
                receipt_consumed=True,
                mission_closed=False,
                fleet_closed=False,
                release_performed=False,
                deploy_performed=False,
            )


if __name__ == "__main__":
    unittest.main()

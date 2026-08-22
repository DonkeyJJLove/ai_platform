from __future__ import annotations

from dataclasses import asdict
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
    execution_epoch_key,
    execution_epoch_receipt_filename,
)
from cyber_lion.enterprise.fleet_reconciliation import ReconciliationStore
from cyber_lion.enterprise.fleet_runtime_reconciliation_execution import (
    RuntimeReconciliationExecutionError,
    execute_runtime_reconciliation,
)
from cyber_lion.enterprise.fleet_runtime_reconciliation_ingestion import _build_inventory, _load_observation
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
        self.legacy_receipt = self.external / "reconciliation-execution-receipt.json"
        create_status_db(self.status)
        create_coordination_db(self.coordination)
        self.trust.write_text(json.dumps({
            "source_id": PINS.source_id,
            "source_instance_id": PINS.source_instance_id,
            "source_implementation_digest": PINS.source_implementation_digest,
            "trust_anchor_id": PINS.trust_anchor_id,
        }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        self.observed_at = "2026-08-21T20:45:00+00:00"
        self._write_observation(revision=1, observed_at=self.observed_at)
        self.inventory = self._inventory()
        store = ReconciliationStore(self.reconciliation, trust_pins=PINS, clock=lambda: datetime.now(timezone.utc))
        store.record_inventory(self.inventory)
        store.close()

    def tearDown(self) -> None:
        self.tmp.cleanup()
        self.env.stop()

    def _write_observation(self, *, revision: int, observed_at: str) -> None:
        observation = {
            "schema_version": "1.0.0",
            "repository": REPOSITORY,
            "inventory_revision": revision,
            "default_branch": "master",
            "default_head_sha": MASTER,
            "observed_at": observed_at,
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
                "observed_at": observed_at,
            }],
        }
        self.inventory_file.write_text(json.dumps(observation, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    def _inventory(self):
        observation = _load_observation(self.inventory_file.read_bytes(), repository=REPOSITORY, current_master=MASTER)
        return _build_inventory(observation, PINS)

    def config(self, *, master: str = MASTER, tree: str = TREE) -> RuntimeReconciliationExecutionConfig:
        return RuntimeReconciliationExecutionConfig(REPOSITORY, master, tree).validate()

    def paths(self):
        return {
            "status": self.status,
            "coordination": self.coordination,
            "reconciliation": self.reconciliation,
            "trust": self.trust,
            "inventory": self.inventory_file,
            "receipt": self.legacy_receipt,
        }

    def execute(self, config=None):
        return execute_runtime_reconciliation(
            config or self.config(), repository_root=str(self.repo), physical_paths=self.paths()
        )

    def epoch_path(self, inventory=None) -> Path:
        inventory = inventory or self._inventory()
        return self.external / execution_epoch_receipt_filename(
            repository=inventory.repository,
            inventory_id=inventory.inventory_id,
            inventory_revision=inventory.inventory_revision,
            inventory_digest=inventory.inventory_digest,
        )

    def write_legacy(self, receipt: RuntimeReconciliationExecutionReceipt) -> bytes:
        raw = json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
        self.legacy_receipt.write_bytes(raw)
        return raw

    def valid_receipt_for(self, *, inventory_id: str, inventory_revision: int, inventory_digest: str):
        return RuntimeReconciliationExecutionReceipt.build(
            schema_version="1.0.0",
            repository=REPOSITORY,
            current_master=MASTER,
            current_master_tree=TREE,
            inventory_id=inventory_id,
            inventory_revision=inventory_revision,
            inventory_digest=inventory_digest,
            closure_preconditions_digest="2" * 64,
            report_id="report-test",
            report_digest="3" * 64,
            disposition="RECONCILIATION_REQUIRED",
            convergence_receipt_digest=None,
            execution_config_digest="4" * 64,
            receipt_consumed=False,
            mission_closed=False,
            fleet_closed=False,
            release_performed=False,
            deploy_performed=False,
        )

    def test_epoch_key_is_deterministic_and_binds_inventory_tuple(self) -> None:
        first = execution_epoch_key(
            repository=REPOSITORY,
            inventory_id="inventory-1",
            inventory_revision=1,
            inventory_digest="1" * 64,
        )
        second = execution_epoch_key(
            repository=REPOSITORY,
            inventory_id="inventory-1",
            inventory_revision=1,
            inventory_digest="1" * 64,
        )
        changed = execution_epoch_key(
            repository=REPOSITORY,
            inventory_id="inventory-1",
            inventory_revision=2,
            inventory_digest="1" * 64,
        )
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        self.assertNotEqual(first, changed)

    def test_converged_execution_creates_only_epoch_receipt(self) -> None:
        receipt = self.execute()
        path = self.epoch_path()
        self.assertTrue(path.is_file())
        self.assertFalse(self.legacy_receipt.exists())
        stored = RuntimeReconciliationExecutionReceipt(**json.loads(path.read_text(encoding="utf-8"))).validate()
        self.assertEqual(stored.execution_receipt_digest, receipt.execution_receipt_digest)

    def test_same_epoch_second_execution_denied(self) -> None:
        self.execute()
        with self.assertRaises(RuntimeReconciliationExecutionError):
            self.execute()

    def test_valid_foreign_legacy_epoch_does_not_block_current(self) -> None:
        foreign = self.valid_receipt_for(
            inventory_id="foreign-inventory",
            inventory_revision=99,
            inventory_digest="9" * 64,
        )
        before = self.write_legacy(foreign)
        self.execute()
        self.assertEqual(self.legacy_receipt.read_bytes(), before)
        self.assertTrue(self.epoch_path().is_file())

    def test_valid_legacy_current_epoch_denies(self) -> None:
        current = self._inventory()
        self.write_legacy(self.valid_receipt_for(
            inventory_id=current.inventory_id,
            inventory_revision=current.inventory_revision,
            inventory_digest=current.inventory_digest,
        ))
        with self.assertRaises(RuntimeReconciliationExecutionError):
            self.execute()

    def test_malformed_legacy_receipt_denies(self) -> None:
        self.legacy_receipt.write_text("{}", encoding="utf-8")
        with self.assertRaises(RuntimeReconciliationExecutionError):
            self.execute()

    def test_epoch_receipt_filename_mismatch_denies(self) -> None:
        foreign = self.valid_receipt_for(
            inventory_id="foreign-inventory",
            inventory_revision=99,
            inventory_digest="9" * 64,
        )
        wrong = self.external / ("reconciliation-execution-receipt." + "0" * 64 + ".json")
        wrong.write_text(json.dumps(asdict(foreign), sort_keys=True, separators=(",", ":")), encoding="utf-8")
        with self.assertRaises(RuntimeReconciliationExecutionError):
            self.execute()

    def test_different_authoritative_inventory_epoch_executes_once(self) -> None:
        first_receipt = self.execute()
        first_path = self.epoch_path(self.inventory)
        self.assertTrue(first_path.exists())

        self._write_observation(revision=2, observed_at="2026-08-21T21:45:00+00:00")
        second_inventory = self._inventory()
        store = ReconciliationStore(self.reconciliation, trust_pins=PINS, clock=lambda: datetime.now(timezone.utc))
        store.record_inventory(second_inventory)
        store.close()

        second_receipt = self.execute()
        second_path = self.epoch_path(second_inventory)
        self.assertTrue(second_path.exists())
        self.assertNotEqual(first_receipt.inventory_digest, second_receipt.inventory_digest)
        with self.assertRaises(RuntimeReconciliationExecutionError):
            self.execute()

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

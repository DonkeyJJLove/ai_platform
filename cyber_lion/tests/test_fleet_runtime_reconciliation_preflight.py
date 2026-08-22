from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from cyber_lion.contracts.fleet_reconciliation import ReconciliationTrustPins
from cyber_lion.contracts.fleet_runtime_reconciliation_execution import (
    REPOSITORY,
    RUNTIME_SOURCE_INSTANCE_ID,
    RuntimeReconciliationExecutionReceipt,
    execution_epoch_receipt_filename,
)
from cyber_lion.contracts.fleet_runtime_reconciliation_preflight import RuntimeReconciliationPreflightConfig
from cyber_lion.enterprise.fleet_reconciliation import ReconciliationStore
from cyber_lion.enterprise import fleet_runtime_reconciliation_preflight as preflight
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


class RuntimeReconciliationPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = mock.patch.dict(os.environ, {"LION_FLEET_RUNTIME_ROOT": ROOT}, clear=False)
        self.env.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.status = self.root / "status.sqlite"
        self.coordination = self.root / "coordination.sqlite"
        self.reconciliation = self.root / "reconciliation.sqlite"
        self.trust = self.root / "reconciliation-trust.json"
        self.inventory_file = self.root / "repository-inventory.json"
        self.legacy_receipt = self.root / "reconciliation-execution-receipt.json"
        create_status_db(self.status)
        create_coordination_db(self.coordination)
        self.trust.write_text(json.dumps({
            "source_id": PINS.source_id,
            "source_instance_id": PINS.source_instance_id,
            "source_implementation_digest": PINS.source_implementation_digest,
            "trust_anchor_id": PINS.trust_anchor_id,
        }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        self.observed_at = "2026-08-22T02:20:00+00:00"
        self.write_inventory(revision=7, master=MASTER, observed_at=self.observed_at)
        self.inventory = self.expected_inventory()
        store = ReconciliationStore(self.reconciliation, trust_pins=PINS, clock=lambda: datetime.now(timezone.utc))
        store.record_inventory(self.inventory)
        store.close()

    def tearDown(self) -> None:
        self.tmp.cleanup()
        self.env.stop()

    def write_inventory(self, *, revision: int, master: str, observed_at: str) -> None:
        value = {
            "schema_version": "1.0.0",
            "repository": REPOSITORY,
            "inventory_revision": revision,
            "default_branch": "master",
            "default_head_sha": master,
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
        self.inventory_file.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    def config(self) -> RuntimeReconciliationPreflightConfig:
        return RuntimeReconciliationPreflightConfig(REPOSITORY, MASTER, TREE).validate()

    def paths(self):
        return {
            "status": self.status,
            "coordination": self.coordination,
            "reconciliation": self.reconciliation,
            "trust": self.trust,
            "inventory": self.inventory_file,
            "execution_receipt": self.legacy_receipt,
        }

    def expected_inventory(self):
        raw = self.inventory_file.read_bytes()
        observation = _load_observation(raw, repository=REPOSITORY, current_master=MASTER)
        return _build_inventory(observation, PINS)

    def observe(self):
        return preflight.observe_runtime_reconciliation_preflight(self.config(), physical_paths=self.paths())

    def receipt_for(self, *, inventory_id: str, inventory_revision: int, inventory_digest: str):
        return RuntimeReconciliationExecutionReceipt.build(
            schema_version="1.0.0",
            repository=REPOSITORY,
            current_master=MASTER,
            current_master_tree=TREE,
            inventory_id=inventory_id,
            inventory_revision=inventory_revision,
            inventory_digest=inventory_digest,
            closure_preconditions_digest="2" * 64,
            report_id="report-preflight",
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

    def write_receipt(self, path: Path, receipt: RuntimeReconciliationExecutionReceipt) -> bytes:
        raw = json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
        path.write_bytes(raw)
        return raw

    def current_epoch_path(self) -> Path:
        inv = self.expected_inventory()
        return self.root / execution_epoch_receipt_filename(
            repository=inv.repository,
            inventory_id=inv.inventory_id,
            inventory_revision=inv.inventory_revision,
            inventory_digest=inv.inventory_digest,
        )

    def test_coherent_current_clean_state_remains_admissible(self) -> None:
        result = self.observe()
        self.assertEqual(result.inventory_state, "CURRENT")
        self.assertEqual(result.reconciliation_state, "CLEAN_PRE_EXECUTION")
        self.assertFalse(result.execution_receipt_present)
        self.assertTrue(result.f005_q_admissible)
        self.assertEqual(result.next_step, "RUN_F005_Q")

    def test_foreign_legacy_epoch_receipt_does_not_block_current(self) -> None:
        foreign = self.receipt_for(
            inventory_id="foreign-inventory",
            inventory_revision=6,
            inventory_digest="9" * 64,
        )
        before = self.write_receipt(self.legacy_receipt, foreign)
        result = self.observe()
        self.assertEqual(self.legacy_receipt.read_bytes(), before)
        self.assertEqual(result.inventory_state, "CURRENT")
        self.assertEqual(result.reconciliation_state, "CLEAN_PRE_EXECUTION")
        self.assertFalse(result.execution_receipt_present)
        self.assertTrue(result.f005_q_admissible)
        self.assertEqual(result.next_step, "RUN_F005_Q")

    def test_legacy_current_epoch_receipt_denies(self) -> None:
        inv = self.expected_inventory()
        self.write_receipt(self.legacy_receipt, self.receipt_for(
            inventory_id=inv.inventory_id,
            inventory_revision=inv.inventory_revision,
            inventory_digest=inv.inventory_digest,
        ))
        result = self.observe()
        self.assertEqual(result.reconciliation_state, "EXECUTION_ALREADY_RECORDED")
        self.assertTrue(result.execution_receipt_present)
        self.assertFalse(result.f005_q_admissible)
        self.assertEqual(result.next_step, "DENY")

    def test_malformed_legacy_receipt_conflicts(self) -> None:
        self.legacy_receipt.write_text("{}", encoding="utf-8")
        result = self.observe()
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.reconciliation_state, "CONFLICTING")
        self.assertFalse(result.f005_q_admissible)

    def test_current_epoch_receipt_denies(self) -> None:
        inv = self.expected_inventory()
        self.write_receipt(self.current_epoch_path(), self.receipt_for(
            inventory_id=inv.inventory_id,
            inventory_revision=inv.inventory_revision,
            inventory_digest=inv.inventory_digest,
        ))
        result = self.observe()
        self.assertEqual(result.reconciliation_state, "EXECUTION_ALREADY_RECORDED")
        self.assertTrue(result.execution_receipt_present)
        self.assertFalse(result.f005_q_admissible)

    def test_foreign_epoch_receipt_does_not_block_current(self) -> None:
        foreign = self.receipt_for(
            inventory_id="foreign-inventory",
            inventory_revision=6,
            inventory_digest="9" * 64,
        )
        path = self.root / execution_epoch_receipt_filename(
            repository=foreign.repository,
            inventory_id=foreign.inventory_id,
            inventory_revision=foreign.inventory_revision,
            inventory_digest=foreign.inventory_digest,
        )
        self.write_receipt(path, foreign)
        result = self.observe()
        self.assertEqual(result.reconciliation_state, "CLEAN_PRE_EXECUTION")
        self.assertFalse(result.execution_receipt_present)
        self.assertTrue(result.f005_q_admissible)

    def test_epoch_receipt_key_mismatch_conflicts(self) -> None:
        foreign = self.receipt_for(
            inventory_id="foreign-inventory",
            inventory_revision=6,
            inventory_digest="9" * 64,
        )
        wrong = self.root / ("reconciliation-execution-receipt." + "0" * 64 + ".json")
        self.write_receipt(wrong, foreign)
        result = self.observe()
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.reconciliation_state, "CONFLICTING")

    def test_duplicate_current_epoch_receipts_conflict(self) -> None:
        inv = self.expected_inventory()
        receipt = self.receipt_for(
            inventory_id=inv.inventory_id,
            inventory_revision=inv.inventory_revision,
            inventory_digest=inv.inventory_digest,
        )
        self.write_receipt(self.legacy_receipt, receipt)
        self.write_receipt(self.current_epoch_path(), receipt)
        result = self.observe()
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.reconciliation_state, "CONFLICTING")
        self.assertFalse(result.f005_q_admissible)

    def test_receipt_appearance_race_conflicts(self) -> None:
        original = preflight._execution_receipt_snapshot
        first = original(self.root, self.legacy_receipt)
        inv = self.expected_inventory()
        receipt = self.receipt_for(
            inventory_id=inv.inventory_id,
            inventory_revision=inv.inventory_revision,
            inventory_digest=inv.inventory_digest,
        )
        raw = json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        second = first + ((self.current_epoch_path().name, raw),)
        with mock.patch.object(preflight, "_execution_receipt_snapshot", side_effect=[first, second]):
            result = self.observe()
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.reconciliation_state, "CONFLICTING")

    def test_receipt_disappearance_race_conflicts(self) -> None:
        inv = self.expected_inventory()
        receipt = self.receipt_for(
            inventory_id=inv.inventory_id,
            inventory_revision=inv.inventory_revision,
            inventory_digest=inv.inventory_digest,
        )
        raw = json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        first = ((self.current_epoch_path().name, raw),)
        with mock.patch.object(preflight, "_execution_receipt_snapshot", side_effect=[first, ()]):
            result = self.observe()
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.reconciliation_state, "CONFLICTING")

    def test_receipt_replacement_race_conflicts(self) -> None:
        inv = self.expected_inventory()
        receipt = self.receipt_for(
            inventory_id=inv.inventory_id,
            inventory_revision=inv.inventory_revision,
            inventory_digest=inv.inventory_digest,
        )
        raw = json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        first = ((self.current_epoch_path().name, raw),)
        second = ((self.current_epoch_path().name, raw + b" "),)
        with mock.patch.object(preflight, "_execution_receipt_snapshot", side_effect=[first, second]):
            result = self.observe()
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.reconciliation_state, "CONFLICTING")

    def test_stale_inventory_selects_refresh_when_no_receipt_conflict(self) -> None:
        self.write_inventory(revision=8, master="e" * 40, observed_at="2026-08-22T03:20:00+00:00")
        stale = _build_inventory(
            _load_observation(self.inventory_file.read_bytes(), repository=REPOSITORY, current_master="e" * 40), PINS
        )
        store = ReconciliationStore(self.reconciliation, trust_pins=PINS, clock=lambda: datetime.now(timezone.utc))
        store.record_inventory(stale)
        store.close()
        result = self.observe()
        self.assertEqual(result.inventory_state, "STALE")
        self.assertEqual(result.next_step, "REFRESH_F005_J")
        self.assertFalse(result.f005_q_admissible)


if __name__ == "__main__":
    unittest.main()

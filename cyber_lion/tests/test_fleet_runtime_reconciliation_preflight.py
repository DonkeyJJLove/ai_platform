from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from cyber_lion.contracts.fleet_reconciliation import ReconciliationTrustPins
from cyber_lion.contracts.fleet_runtime_reconciliation_preflight import (
    REPOSITORY,
    RUNTIME_SOURCE_INSTANCE_ID,
    RuntimeReconciliationPreflightConfig,
)
from cyber_lion.enterprise import fleet_runtime_reconciliation_preflight as preflight
from cyber_lion.enterprise.fleet_runtime_reconciliation_ingestion import _build_inventory, _load_observation

MASTER = "a" * 40
TREE = "b" * 40
PINS = ReconciliationTrustPins(
    source_id="lion-runtime-reconciliation-source",
    source_instance_id=RUNTIME_SOURCE_INSTANCE_ID,
    source_implementation_digest="1" * 64,
    trust_anchor_id="lion-runtime-reconciliation-root-01",
).validate()


class RuntimeReconciliationPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.status = root / "status.sqlite"
        self.coordination = root / "coordination.sqlite"
        self.reconciliation = root / "reconciliation.sqlite"
        self.trust = root / "reconciliation-trust.json"
        self.inventory_file = root / "repository-inventory.json"
        self.execution_receipt = root / "reconciliation-execution-receipt.json"
        for path in (self.status, self.coordination, self.reconciliation):
            path.touch()
        self.trust.write_text(json.dumps({
            "source_id": PINS.source_id,
            "source_instance_id": PINS.source_instance_id,
            "source_implementation_digest": PINS.source_implementation_digest,
            "trust_anchor_id": PINS.trust_anchor_id,
        }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        self.observed_at = "2026-08-22T02:20:00+00:00"
        self.write_inventory(MASTER)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_inventory(self, master: str) -> None:
        value = {
            "schema_version": "1.0.0",
            "repository": REPOSITORY,
            "inventory_revision": 7,
            "default_branch": "master",
            "default_head_sha": master,
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
        self.inventory_file.write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    def config(self) -> RuntimeReconciliationPreflightConfig:
        return RuntimeReconciliationPreflightConfig(REPOSITORY, MASTER, TREE).validate()

    def paths(self):
        return {
            "status": self.status,
            "coordination": self.coordination,
            "reconciliation": self.reconciliation,
            "trust": self.trust,
            "inventory": self.inventory_file,
            "execution_receipt": self.execution_receipt,
        }

    def expected_inventory(self, master: str = MASTER):
        raw = self.inventory_file.read_bytes()
        observation = _load_observation(raw, repository=REPOSITORY, current_master=master)
        return _build_inventory(observation, PINS)

    def healthy_patches(self, *, counts=(0, 0, 0), head=None):
        inv = self.expected_inventory()
        if head is None:
            head = {
                "repository": inv.repository,
                "inventory_id": inv.inventory_id,
                "inventory_revision": inv.inventory_revision,
                "inventory_digest": inv.inventory_digest,
                "default_head_sha": inv.default_head_sha,
                "observed_at": inv.observed_at,
            }
        return (
            mock.patch.object(preflight, "_read_status", return_value={
                "stable": True, "event_chain": True, "receipt_chain": True,
            }),
            mock.patch.object(preflight, "_read_coordination", return_value={
                "stable": True, "event_chain": True,
            }),
            mock.patch.object(preflight, "_read_state", return_value={
                "head": head, "reports": counts[0], "receipts": counts[1], "consumed": counts[2],
            }),
            mock.patch.object(preflight, "_current_counts", return_value=counts),
            mock.patch.object(preflight, "_read_reconciliation", return_value={"stable": True}),
        )

    def observe_healthy(self, *, counts=(0, 0, 0), head=None):
        patches = self.healthy_patches(counts=counts, head=head)
        for item in patches:
            item.start()
        try:
            return preflight.observe_runtime_reconciliation_preflight(
                self.config(), physical_paths=self.paths()
            )
        finally:
            for item in reversed(patches):
                item.stop()

    def test_current_clean_state_is_admissible(self) -> None:
        result = self.observe_healthy()
        self.assertEqual(result.inventory_state, "CURRENT")
        self.assertEqual(result.reconciliation_state, "CLEAN_PRE_EXECUTION")
        self.assertTrue(result.runtime_source_healthy)
        self.assertTrue(result.f005_q_admissible)
        self.assertEqual(result.next_step, "RUN_F005_Q")

    def test_stale_inventory_selects_f005_j_refresh(self) -> None:
        self.write_inventory("e" * 40)
        stale_inv = self.expected_inventory(master="e" * 40)
        stale_head = {
            "repository": stale_inv.repository,
            "inventory_id": stale_inv.inventory_id,
            "inventory_revision": stale_inv.inventory_revision,
            "inventory_digest": stale_inv.inventory_digest,
            "default_head_sha": stale_inv.default_head_sha,
            "observed_at": stale_inv.observed_at,
        }
        patches = (
            mock.patch.object(preflight, "_read_status", return_value={"stable": True, "event_chain": True, "receipt_chain": True}),
            mock.patch.object(preflight, "_read_coordination", return_value={"stable": True, "event_chain": True}),
            mock.patch.object(preflight, "_read_state", return_value={"head": stale_head, "reports": 0, "receipts": 0, "consumed": 0}),
            mock.patch.object(preflight, "_current_counts", return_value=(0, 0, 0)),
            mock.patch.object(preflight, "_read_reconciliation", return_value={"stable": True}),
        )
        for item in patches:
            item.start()
        try:
            result = preflight.observe_runtime_reconciliation_preflight(self.config(), physical_paths=self.paths())
        finally:
            for item in reversed(patches):
                item.stop()
        self.assertEqual(result.inventory_state, "STALE")
        self.assertFalse(result.f005_q_admissible)
        self.assertEqual(result.next_step, "REFRESH_F005_J")

    def test_missing_inventory_selects_f005_j_refresh(self) -> None:
        self.inventory_file.unlink()
        with mock.patch.object(preflight, "_read_status", return_value={"stable": True, "event_chain": True, "receipt_chain": True}), \
             mock.patch.object(preflight, "_read_coordination", return_value={"stable": True, "event_chain": True}), \
             mock.patch.object(preflight, "_read_state", return_value={"head": None, "reports": 0, "receipts": 0, "consumed": 0}):
            result = preflight.observe_runtime_reconciliation_preflight(self.config(), physical_paths=self.paths())
        self.assertEqual(result.inventory_state, "MISSING")
        self.assertEqual(result.next_step, "REFRESH_F005_J")
        self.assertFalse(result.f005_q_admissible)

    def test_inventory_head_conflict_denies(self) -> None:
        inv = self.expected_inventory()
        bad_head = {
            "repository": inv.repository,
            "inventory_id": inv.inventory_id,
            "inventory_revision": inv.inventory_revision,
            "inventory_digest": "f" * 64,
            "default_head_sha": inv.default_head_sha,
            "observed_at": inv.observed_at,
        }
        result = self.observe_healthy(head=bad_head)
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_existing_report_denies_execution(self) -> None:
        result = self.observe_healthy(counts=(1, 0, 0))
        self.assertEqual(result.reconciliation_state, "REPORT_ALREADY_PRESENT")
        self.assertFalse(result.f005_q_admissible)
        self.assertEqual(result.next_step, "DENY")

    def test_existing_receipt_denies_execution(self) -> None:
        result = self.observe_healthy(counts=(1, 1, 0))
        self.assertEqual(result.reconciliation_state, "RECEIPT_ALREADY_PRESENT")
        self.assertFalse(result.f005_q_admissible)

    def test_execution_receipt_denies_execution(self) -> None:
        self.execution_receipt.write_text("{}", encoding="utf-8")
        result = self.observe_healthy()
        self.assertEqual(result.reconciliation_state, "EXECUTION_ALREADY_RECORDED")
        self.assertFalse(result.f005_q_admissible)

    def test_unhealthy_status_turns_current_inventory_into_conflict(self) -> None:
        inv = self.expected_inventory()
        head = {
            "repository": inv.repository,
            "inventory_id": inv.inventory_id,
            "inventory_revision": inv.inventory_revision,
            "inventory_digest": inv.inventory_digest,
            "default_head_sha": inv.default_head_sha,
            "observed_at": inv.observed_at,
        }
        with mock.patch.object(preflight, "_read_status", return_value={"stable": False, "event_chain": True, "receipt_chain": True}), \
             mock.patch.object(preflight, "_read_coordination", return_value={"stable": True, "event_chain": True}), \
             mock.patch.object(preflight, "_read_state", return_value={"head": head, "reports": 0, "receipts": 0, "consumed": 0}), \
             mock.patch.object(preflight, "_current_counts", return_value=(0, 0, 0)), \
             mock.patch.object(preflight, "_read_reconciliation", return_value={"stable": True}):
            result = preflight.observe_runtime_reconciliation_preflight(self.config(), physical_paths=self.paths())
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertFalse(result.runtime_source_healthy)
        self.assertEqual(result.next_step, "DENY")

    def test_query_count_helper_does_not_mutate_database(self) -> None:
        db = Path(self.tmp.name) / "counts.sqlite"
        conn = sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE reconciliation_report(repository TEXT, inventory_digest TEXT)")
            conn.execute("CREATE TABLE convergence_receipt(repository TEXT, inventory_digest TEXT, consumed INTEGER)")
            conn.execute("INSERT INTO reconciliation_report VALUES(?,?)", (REPOSITORY, "1" * 64))
            conn.execute("INSERT INTO convergence_receipt VALUES(?,?,0)", (REPOSITORY, "1" * 64))
            conn.commit()
        finally:
            conn.close()
        before = sha256(db.read_bytes()).hexdigest()
        counts = preflight._current_counts(db, REPOSITORY, "1" * 64)
        after = sha256(db.read_bytes()).hexdigest()
        self.assertEqual(counts, (1, 1, 0))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

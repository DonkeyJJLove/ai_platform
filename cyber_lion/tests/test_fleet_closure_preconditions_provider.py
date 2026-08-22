from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cyber_lion.enterprise.fleet_closure_preconditions_provider import (
    FleetClosurePreconditionsProviderError,
    RuntimeClosurePreconditionsProvider,
)
from cyber_lion.tests.test_fleet_reconciliation import evidence, inventory
from cyber_lion.tests.test_fleet_runtime_snapshot_source import (
    NOW,
    create_coordination_db,
    create_reconciliation_db,
    create_status_db,
)


class RuntimeClosurePreconditionsProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.status = root / "status.sqlite"
        self.coordination = root / "coordination.sqlite"
        self.reconciliation = root / "reconciliation.sqlite"
        item = evidence(
            "a",
            ownership="TERMINAL",
            ancestry="HEAD_ANCESTOR_OF_DEFAULT",
            ahead=0,
            behind=1,
        )
        self.inventory = inventory((item,), default_head="a" * 40)
        create_status_db(self.status)
        create_coordination_db(self.coordination)
        create_reconciliation_db(self.reconciliation, master=self.inventory.default_head_sha)
        self._bind_head_to_inventory()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _bind_head_to_inventory(self) -> None:
        conn = sqlite3.connect(self.reconciliation)
        try:
            conn.execute(
                "UPDATE reconciliation_inventory_head SET inventory_id=?,inventory_revision=?,"
                "inventory_digest=?,default_head_sha=?,observed_at=?",
                (
                    self.inventory.inventory_id,
                    self.inventory.inventory_revision,
                    self.inventory.inventory_digest,
                    self.inventory.default_head_sha,
                    self.inventory.observed_at,
                ),
            )
            # Any fixture report/receipt was built for the old synthetic inventory.
            conn.execute("DELETE FROM convergence_receipt")
            conn.execute("DELETE FROM reconciliation_report")
            conn.commit()
        finally:
            conn.close()

    def provider(self, *, clock=None) -> RuntimeClosurePreconditionsProvider:
        return RuntimeClosurePreconditionsProvider(
            current_master=self.inventory.default_head_sha,
            current_master_tree="b" * 40,
            source_instance="lion-runtime-01",
            status_db_path=str(self.status),
            coordination_db_path=str(self.coordination),
            reconciliation_db_path=str(self.reconciliation),
            clock=clock,
        )

    def test_missing_report_and_receipt_are_not_pre_report_disagreement(self) -> None:
        pre = self.provider().snapshot(self.inventory.repository, self.inventory)
        self.assertEqual(pre.reconciliation_disagreement_count, 0)
        self.assertEqual(pre.unknown_result_count, 0)
        self.assertEqual(pre.unresolved_write_lease_count, 0)
        self.assertEqual(pre.unreconciled_effect_count, 0)
        self.assertEqual(pre.active_unknown_mission_count, 0)
        self.assertTrue(pre.satisfied())
        self.assertEqual(pre.observed_at, self.inventory.observed_at)
        self.assertEqual(pre.inventory_digest, self.inventory.inventory_digest)
        self.assertEqual(pre.epistemic_class, "ANCHORED")

    def test_active_runtime_maps_write_lease_and_effect_blockers(self) -> None:
        self.status.unlink()
        self.coordination.unlink()
        create_status_db(self.status, active=True)
        create_coordination_db(self.coordination, active=True)
        pre = self.provider().snapshot(self.inventory.repository, self.inventory)
        self.assertGreater(pre.unresolved_write_lease_count, 0)
        self.assertGreater(pre.unreconciled_effect_count, 0)
        self.assertFalse(pre.satisfied())

    def test_exact_inventory_head_binding_is_required(self) -> None:
        conn = sqlite3.connect(self.reconciliation)
        try:
            conn.execute(
                "UPDATE reconciliation_inventory_head SET inventory_digest=?",
                ("f" * 64,),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(FleetClosurePreconditionsProviderError):
            self.provider().snapshot(self.inventory.repository, self.inventory)

    def test_repository_substitution_is_denied(self) -> None:
        with self.assertRaises(FleetClosurePreconditionsProviderError):
            self.provider().snapshot("Other/repo", self.inventory)

    def test_observation_clock_must_bind_inventory_epoch(self) -> None:
        with self.assertRaises(FleetClosurePreconditionsProviderError):
            self.provider(clock=lambda: NOW).snapshot(
                self.inventory.repository,
                self.inventory,
            )

    def test_preconditions_digest_is_deterministic_for_identical_sources(self) -> None:
        first = self.provider().snapshot(self.inventory.repository, self.inventory)
        second = self.provider().snapshot(self.inventory.repository, self.inventory)
        self.assertEqual(first.preconditions_digest, second.preconditions_digest)
        self.assertEqual(first.source_provenance_refs, second.source_provenance_refs)

    def test_provider_does_not_write_reconciliation_store(self) -> None:
        conn = sqlite3.connect(self.reconciliation)
        try:
            before = (
                conn.execute("SELECT COUNT(*) FROM reconciliation_inventory_head").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM reconciliation_report").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM convergence_receipt").fetchone()[0],
            )
        finally:
            conn.close()
        self.provider().snapshot(self.inventory.repository, self.inventory)
        conn = sqlite3.connect(self.reconciliation)
        try:
            after = (
                conn.execute("SELECT COUNT(*) FROM reconciliation_inventory_head").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM reconciliation_report").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM convergence_receipt").fetchone()[0],
            )
        finally:
            conn.close()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

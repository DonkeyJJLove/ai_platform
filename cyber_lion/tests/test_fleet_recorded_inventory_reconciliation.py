from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.fleet_reconciliation import ClosurePreconditions
from cyber_lion.enterprise.fleet_recorded_inventory_reconciliation import (
    RecordedInventoryReconciliationRunner,
)
from cyber_lion.enterprise.fleet_reconciliation import (
    BranchReconciliationClassifier,
    FleetReconciliationError,
    ReconciliationStore,
)
from cyber_lion.tests.test_fleet_reconciliation import PINS, REPO, evidence, inventory


class ClosureProvider:
    def __init__(self, *, blockers: int = 0) -> None:
        self.blockers = blockers

    def snapshot(self, repository, inv):
        return ClosurePreconditions.build(
            repository=repository,
            inventory_digest=inv.inventory_digest,
            active_unknown_mission_count=0,
            unknown_result_count=0,
            unresolved_write_lease_count=self.blockers,
            unreconciled_effect_count=0,
            reconciliation_disagreement_count=0,
            source_provenance_refs=("runtime:test", "inventory:test"),
            epistemic_class="ANCHORED",
            observed_at=inv.observed_at,
        )


class WrongEpochClosureProvider(ClosureProvider):
    def snapshot(self, repository, inv):
        return ClosurePreconditions.build(
            repository=repository,
            inventory_digest=inv.inventory_digest,
            active_unknown_mission_count=0,
            unknown_result_count=0,
            unresolved_write_lease_count=0,
            unreconciled_effect_count=0,
            reconciliation_disagreement_count=0,
            source_provenance_refs=("runtime:test",),
            epistemic_class="ANCHORED",
            observed_at="2026-08-21T13:00:00+00:00",
        )


class RecordedInventoryReconciliationRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "reconciliation.sqlite"
        self.store = ReconciliationStore(
            self.db,
            trust_pins=PINS,
            clock=lambda: datetime(2026, 8, 21, 12, 30, tzinfo=timezone.utc),
        )
        item = evidence(
            "a",
            ownership="TERMINAL",
            ancestry="HEAD_ANCESTOR_OF_DEFAULT",
            ahead=0,
            behind=1,
        )
        self.inventory = inventory((item,))
        self.store.record_inventory(self.inventory)

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def runner(self, provider=None):
        return RecordedInventoryReconciliationRunner(
            closure_provider=provider or ClosureProvider(),
            classifier=BranchReconciliationClassifier(),
            store=self.store,
        )

    def test_recorded_inventory_can_generate_report_and_receipt(self) -> None:
        run = self.runner().reconcile(REPO, self.inventory)
        self.assertEqual(run.report.disposition, "CONVERGED")
        self.assertIsNotNone(run.convergence_receipt)
        assert run.convergence_receipt is not None
        self.assertFalse(self.store.receipt_consumed(run.convergence_receipt.receipt_digest))
        self.assertEqual(run.inventory_digest, self.inventory.inventory_digest)
        self.assertEqual(
            run.closure_preconditions_digest,
            run.report.closure_preconditions_digest,
        )

    def test_runner_never_re_records_inventory(self) -> None:
        # A second record_inventory() of this exact revision would fail as replay.
        # Successful reconciliation therefore proves the runner begins post-ingest.
        run = self.runner(ClosureProvider(blockers=1)).reconcile(REPO, self.inventory)
        self.assertEqual(run.report.disposition, "RECONCILIATION_REQUIRED")
        self.assertIsNone(run.convergence_receipt)

    def test_nonconverged_report_does_not_issue_receipt(self) -> None:
        run = self.runner(ClosureProvider(blockers=2)).reconcile(REPO, self.inventory)
        self.assertIn("UNRESOLVED_WRITE_LEASE", run.report.anomaly_codes)
        self.assertIsNone(run.convergence_receipt)

    def test_repository_substitution_is_denied(self) -> None:
        with self.assertRaises(FleetReconciliationError):
            self.runner().reconcile("Other/repo", self.inventory)

    def test_unrecorded_inventory_fails_closed_at_report_persistence(self) -> None:
        newer = inventory((self.inventory.branches[0],), revision=2)
        with self.assertRaises(FleetReconciliationError):
            self.runner(ClosureProvider(blockers=1)).reconcile(REPO, newer)

    def test_closure_epoch_must_equal_inventory_epoch(self) -> None:
        with self.assertRaises(FleetReconciliationError):
            self.runner(WrongEpochClosureProvider()).reconcile(REPO, self.inventory)

    def test_receipt_replay_is_denied(self) -> None:
        self.runner().reconcile(REPO, self.inventory)
        with self.assertRaises(FleetReconciliationError):
            self.runner().reconcile(REPO, self.inventory)


if __name__ == "__main__":
    unittest.main()

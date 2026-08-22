from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from cyber_lion.contracts.fleet_reconciliation import ConvergenceReceipt
from cyber_lion.contracts.fleet_runtime_snapshot_source import ObservedRuntimeState
from cyber_lion.enterprise import fleet_closure_preconditions_provider as provider_module
from cyber_lion.enterprise import fleet_runtime_snapshot_source as runtime_source
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
        item = evidence("a", ownership="TERMINAL", ancestry="HEAD_ANCESTOR_OF_DEFAULT", ahead=0, behind=1)
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
                "UPDATE reconciliation_inventory_head SET inventory_id=?,inventory_revision=?,inventory_digest=?,default_head_sha=?,observed_at=?",
                (self.inventory.inventory_id, self.inventory.inventory_revision, self.inventory.inventory_digest, self.inventory.default_head_sha, self.inventory.observed_at),
            )
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

    def _insert_report(self) -> tuple[str, str, str]:
        report_digest = "2" * 64; report_id = "report-r3"; preconditions_digest = "3" * 64
        conn = sqlite3.connect(self.reconciliation)
        try:
            conn.execute("INSERT INTO reconciliation_report VALUES(?,?,?,?,?,?,?,?,?,?)", (report_digest, report_id, self.inventory.repository, self.inventory.inventory_id, self.inventory.inventory_revision, self.inventory.inventory_digest, preconditions_digest, self.inventory.default_head_sha, "CONVERGED", self.inventory.observed_at))
            conn.commit()
        finally:
            conn.close()
        return report_digest, report_id, preconditions_digest

    def _insert_receipt(self, report_digest: str, report_id: str, preconditions_digest: str) -> str:
        receipt = ConvergenceReceipt.build(schema_version="1.0.0", receipt_id="receipt-r3", repository=self.inventory.repository, inventory_id=self.inventory.inventory_id, inventory_revision=self.inventory.inventory_revision, inventory_digest=self.inventory.inventory_digest, report_id=report_id, report_digest=report_digest, closure_preconditions_digest=preconditions_digest, default_head_sha=self.inventory.default_head_sha, issued_at=self.inventory.observed_at)
        conn = sqlite3.connect(self.reconciliation)
        try:
            conn.execute("INSERT INTO convergence_receipt VALUES(?,?,?,?,?,?,?,?,?,?,?,0)", (receipt.receipt_digest, receipt.receipt_id, receipt.report_digest, receipt.repository, receipt.inventory_id, receipt.inventory_revision, receipt.inventory_digest, receipt.closure_preconditions_digest, receipt.default_head_sha, receipt.issued_at, receipt.purpose))
            conn.commit()
        finally:
            conn.close()
        return receipt.receipt_digest

    def _real_reconciliation(self) -> dict[str, object]:
        return runtime_source._read_reconciliation(str(self.reconciliation), self.inventory.repository, self.inventory.default_head_sha)

    def _complete_view(self, *, report_digest: str = "a" * 64, report_id: str = "report-a", disposition: str = "CONVERGED", receipt_digest: str = "b" * 64, receipt_id: str = "receipt-a", consumed: int = 0) -> dict[str, object]:
        value = deepcopy(self._real_reconciliation())
        value["report"] = {"report_digest": report_digest, "report_id": report_id, "disposition": disposition}
        value["receipt"] = {"receipt_digest": receipt_digest, "receipt_id": receipt_id, "consumed": consumed}
        value["report_bound"] = True; value["receipt_bound"] = True; value["converged"] = disposition == "CONVERGED"; value["stable"] = True
        return value

    def _assert_race_fails(self, before: dict[str, object], after: dict[str, object]) -> None:
        with mock.patch.object(provider_module, "_read_reconciliation", side_effect=[before, after]):
            with self.assertRaises(FleetClosurePreconditionsProviderError):
                self.provider().snapshot(self.inventory.repository, self.inventory)

    def _details(self, *, active_ids=(), unknown_ids=(), status_id="status-01", status_revision=1, coordinator_id="coord-01", coordination_revision=1):
        observed = ObservedRuntimeState(
            observed_at=self.inventory.observed_at,
            source_digest="0" * 64,
            active_missions=len(set(active_ids)),
            unknown_missions=len(set(unknown_ids)),
            unresolved_write_leases=0,
            unknown_results=0,
            late_unreconciled_results=0,
            missing_heartbeats=0,
            stale_heartbeats=0,
            unknown_branch_ownership=0,
            unowned_active_branches=0,
            unreconciled_effects=0,
            reconciliation_disagreements=1,
            active_authority=0,
            residual_authority=0,
            durable_state_consistency=True,
            event_chain_consistency=True,
            generation_fencing_consistency=True,
            inventory_complete=False,
        ).validate()
        return runtime_source._ObservedRuntimeDetails(
            observed=observed,
            active_ids=frozenset(active_ids),
            unknown_ids=frozenset(unknown_ids),
            status_registry_instance_id=status_id,
            status_revision=status_revision,
            coordinator_id=coordinator_id,
            coordination_revision=coordination_revision,
        )

    def _snapshot_with_details(self, details):
        with mock.patch.object(provider_module, "_observe_runtime_state_with_details", return_value=details):
            return self.provider().snapshot(self.inventory.repository, self.inventory)

    def test_missing_report_and_receipt_are_not_pre_report_disagreement(self) -> None:
        pre = self.provider().snapshot(self.inventory.repository, self.inventory)
        self.assertEqual(pre.reconciliation_disagreement_count, 0); self.assertEqual(pre.unknown_result_count, 0); self.assertEqual(pre.unresolved_write_lease_count, 0); self.assertEqual(pre.unreconciled_effect_count, 0); self.assertEqual(pre.active_unknown_mission_count, 0); self.assertTrue(pre.satisfied())

    def test_preconditions_are_invariant_across_report_receipt_and_consumption(self) -> None:
        before = self.provider().snapshot(self.inventory.repository, self.inventory)
        report_digest, report_id, pre_digest = self._insert_report(); after_report = self.provider().snapshot(self.inventory.repository, self.inventory)
        receipt_digest = self._insert_receipt(report_digest, report_id, pre_digest); after_receipt = self.provider().snapshot(self.inventory.repository, self.inventory)
        conn = sqlite3.connect(self.reconciliation)
        try:
            conn.execute("UPDATE convergence_receipt SET consumed=1 WHERE receipt_digest=?", (receipt_digest,)); conn.commit()
        finally: conn.close()
        after_consumption = self.provider().snapshot(self.inventory.repository, self.inventory)
        expected = before.preconditions_digest
        for candidate in (after_report, after_receipt, after_consumption):
            self.assertEqual(candidate.preconditions_digest, expected); self.assertEqual(candidate.source_provenance_refs, before.source_provenance_refs); self.assertEqual(candidate.reconciliation_disagreement_count, 0)

    def test_report_identity_change_during_observation_fails(self) -> None:
        self._assert_race_fails(self._complete_view(report_digest="a" * 64, report_id="report-a"), self._complete_view(report_digest="c" * 64, report_id="report-b"))

    def test_receipt_identity_change_during_observation_fails(self) -> None:
        self._assert_race_fails(self._complete_view(receipt_digest="b" * 64, receipt_id="receipt-a"), self._complete_view(receipt_digest="d" * 64, receipt_id="receipt-b"))

    def test_receipt_consumption_change_during_observation_fails(self) -> None:
        self._assert_race_fails(self._complete_view(consumed=0), self._complete_view(consumed=1))

    def test_report_disposition_change_during_observation_fails(self) -> None:
        self._assert_race_fails(self._complete_view(disposition="CONVERGED"), self._complete_view(disposition="RECONCILIATION_REQUIRED"))

    def test_same_post_report_state_before_after_passes(self) -> None:
        view = self._complete_view()
        with mock.patch.object(provider_module, "_read_reconciliation", side_effect=[view, deepcopy(view)]):
            pre = self.provider().snapshot(self.inventory.repository, self.inventory)
        self.assertEqual(pre.inventory_digest, self.inventory.inventory_digest)

    def test_active_runtime_maps_write_lease_and_effect_blockers(self) -> None:
        self.status.unlink(); self.coordination.unlink(); create_status_db(self.status, active=True); create_coordination_db(self.coordination, active=True)
        pre = self.provider().snapshot(self.inventory.repository, self.inventory)
        self.assertGreater(pre.unresolved_write_lease_count, 0); self.assertGreater(pre.unreconciled_effect_count, 0); self.assertFalse(pre.satisfied())

    def test_exact_inventory_head_binding_is_required(self) -> None:
        conn = sqlite3.connect(self.reconciliation)
        try:
            conn.execute("UPDATE reconciliation_inventory_head SET inventory_digest=?", ("f" * 64,)); conn.commit()
        finally: conn.close()
        with self.assertRaises(FleetClosurePreconditionsProviderError): self.provider().snapshot(self.inventory.repository, self.inventory)

    def test_repository_substitution_is_denied(self) -> None:
        with self.assertRaises(FleetClosurePreconditionsProviderError): self.provider().snapshot("Other/repo", self.inventory)

    def test_observation_clock_must_bind_inventory_epoch(self) -> None:
        with self.assertRaises(FleetClosurePreconditionsProviderError): self.provider(clock=lambda: NOW).snapshot(self.inventory.repository, self.inventory)

    def test_preconditions_digest_is_deterministic_for_identical_sources(self) -> None:
        first = self.provider().snapshot(self.inventory.repository, self.inventory); second = self.provider().snapshot(self.inventory.repository, self.inventory)
        self.assertEqual(first.preconditions_digest, second.preconditions_digest); self.assertEqual(first.source_provenance_refs, second.source_provenance_refs)

    def test_provider_does_not_write_reconciliation_store(self) -> None:
        conn = sqlite3.connect(self.reconciliation)
        try:
            before = (conn.execute("SELECT COUNT(*) FROM reconciliation_inventory_head").fetchone()[0], conn.execute("SELECT COUNT(*) FROM reconciliation_report").fetchone()[0], conn.execute("SELECT COUNT(*) FROM convergence_receipt").fetchone()[0])
        finally: conn.close()
        self.provider().snapshot(self.inventory.repository, self.inventory)
        conn = sqlite3.connect(self.reconciliation)
        try:
            after = (conn.execute("SELECT COUNT(*) FROM reconciliation_inventory_head").fetchone()[0], conn.execute("SELECT COUNT(*) FROM reconciliation_report").fetchone()[0], conn.execute("SELECT COUNT(*) FROM convergence_receipt").fetchone()[0])
        finally: conn.close()
        self.assertEqual(before, after)

    def test_active_known_plus_terminal_unknown_does_not_count_active_unknown(self) -> None:
        pre = self._snapshot_with_details(self._details(active_ids={"ACTIVE"}, unknown_ids={"TERMINAL"}))
        self.assertEqual(pre.active_unknown_mission_count, 0)

    def test_active_unknown_is_counted_exactly_once(self) -> None:
        pre = self._snapshot_with_details(self._details(active_ids={"A", "B"}, unknown_ids={"A", "T"}))
        self.assertEqual(pre.active_unknown_mission_count, 1)

    def test_multiple_terminal_unknowns_do_not_count_active_unknown(self) -> None:
        pre = self._snapshot_with_details(self._details(active_ids={"ACTIVE"}, unknown_ids={"T1", "T2"}))
        self.assertEqual(pre.active_unknown_mission_count, 0)

    def test_exact_source_revision_provenance_is_bound(self) -> None:
        pre = self._snapshot_with_details(self._details(status_id="status-X", status_revision=7, coordinator_id="coord-X", coordination_revision=9))
        self.assertEqual(pre.source_provenance_refs[0], "fleet-status:status-X:7")
        self.assertEqual(pre.source_provenance_refs[1], "fleet-coordination:coord-X:9")
        self.assertEqual(pre.source_provenance_refs[2], f"repository-inventory:{self.inventory.inventory_id}:{self.inventory.inventory_revision}")
        self.assertTrue(pre.source_provenance_refs[3].startswith("runtime-pre-report:"))

    def test_status_and_coordination_revision_or_identity_change_changes_digest(self) -> None:
        base = self._snapshot_with_details(self._details())
        variants = (
            self._details(status_revision=2),
            self._details(coordination_revision=2),
            self._details(status_id="status-02"),
            self._details(coordinator_id="coord-02"),
        )
        for details in variants:
            candidate = self._snapshot_with_details(details)
            self.assertNotEqual(candidate.preconditions_digest, base.preconditions_digest)


if __name__ == "__main__":
    unittest.main()
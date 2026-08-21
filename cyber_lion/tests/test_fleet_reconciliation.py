from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.fleet_reconciliation import (
    BranchEvidence,
    ClosurePreconditions,
    ReconciliationTrustPins,
    RepositoryInventory,
)
from cyber_lion.enterprise.fleet_reconciliation import (
    BranchReconciliationClassifier,
    FleetReconciler,
    FleetReconciliationError,
    ReconciliationStore,
    RepositoryConvergenceGate,
)


REPO = "DonkeyJJLove/ai_platform"
BASE = "a" * 40
NEW_DEFAULT = "c" * 40
IMPL = "1" * 64
PINS = ReconciliationTrustPins(
    "github-inventory", "installation-1", IMPL, "github-app:1"
)


def evidence(
    suffix: str,
    *,
    ownership: str = "TERMINAL",
    ancestry: str = "DEFAULT_ANCESTOR_OF_HEAD",
    ahead: int | None = 1,
    behind: int | None = 0,
    baseline: str | None = BASE,
    epistemic: str = "OBSERVED",
    superseded_by: str | None = None,
) -> BranchEvidence:
    mission_id = None if ownership == "UNOWNED" else f"mission-{suffix}"
    supersession_ref = f"supersession:{suffix}" if superseded_by else None
    return BranchEvidence.build(
        repository=REPO,
        branch=f"mission/{suffix}",
        branch_head_sha=(suffix[0] if suffix[0] in "0123456789abcdef" else "b") * 40,
        mission_id=mission_id,
        baseline_sha=baseline,
        ownership_state=ownership,
        ancestry_state=ancestry,
        ahead_by=ahead,
        behind_by=behind,
        superseded_by_branch=superseded_by,
        supersession_provenance_ref=supersession_ref,
        source_provenance_ref=f"github:compare:{suffix}",
        epistemic_class=epistemic,
        observed_at="2026-08-21T12:00:00+00:00",
    )


def inventory(
    branches: tuple[BranchEvidence, ...],
    *,
    revision: int = 1,
    default_head: str = BASE,
    source_instance: str = "installation-1",
) -> RepositoryInventory:
    return RepositoryInventory.build(
        schema_version="1.0.0",
        inventory_id=f"inventory-{revision}",
        inventory_revision=revision,
        repository=REPO,
        default_branch="master",
        default_head_sha=default_head,
        source_id="github-inventory",
        source_instance_id=source_instance,
        source_implementation_digest=IMPL,
        trust_anchor_id="github-app:1",
        observed_at=f"2026-08-21T12:{revision:02d}:00+00:00",
        branches=branches,
    )


def closure(inv: RepositoryInventory, **overrides) -> ClosurePreconditions:
    values = dict(
        repository=REPO,
        inventory_digest=inv.inventory_digest,
        active_unknown_mission_count=0,
        unknown_result_count=0,
        unresolved_write_lease_count=0,
        unreconciled_effect_count=0,
        reconciliation_disagreement_count=0,
        source_provenance_refs=("fleet-status:snapshot", "repository-reconciliation:snapshot"),
        epistemic_class="ANCHORED",
        observed_at=inv.observed_at,
    )
    values.update(overrides)
    return ClosurePreconditions.build(**values)


class Provider:
    def __init__(self, snapshots: list[RepositoryInventory]) -> None:
        self.snapshots = snapshots

    def snapshot(self, repository: str) -> RepositoryInventory:
        if repository != REPO or not self.snapshots:
            raise FleetReconciliationError("no inventory")
        return self.snapshots.pop(0)


class ClosureProvider:
    def __init__(self, factory=closure) -> None:
        self.factory = factory

    def snapshot(self, repository: str, inv: RepositoryInventory) -> ClosurePreconditions:
        if repository != REPO:
            raise FleetReconciliationError("wrong repository")
        return self.factory(inv)


class ClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.classifier = BranchReconciliationClassifier()

    def classification(self, item: BranchEvidence) -> tuple[str, str]:
        inv = inventory((item,))
        report = self.classifier.classify(inv, closure(inv))
        return report.branches[0].classification, report.disposition

    def test_active_mission_dominates_ancestry(self) -> None:
        item = evidence("a", ownership="ACTIVE", ancestry="DEFAULT_ANCESTOR_OF_HEAD", ahead=2, behind=0)
        self.assertEqual(self.classification(item)[0], "ACTIVE_MISSION")

    def test_unowned_integrated_branch_cannot_converge(self) -> None:
        item = evidence(
            "a", ownership="UNOWNED", ancestry="HEAD_ANCESTOR_OF_DEFAULT",
            ahead=0, behind=2, baseline=None,
        )
        inv = inventory((item,))
        report = self.classifier.classify(inv, closure(inv))
        self.assertEqual(report.branches[0].classification, "UNCLASSIFIED")
        self.assertEqual(report.branches[0].rationale_code, "UNOWNED_BRANCH")
        self.assertIn("UNOWNED_BRANCH", report.anomaly_codes)
        self.assertEqual(report.disposition, "RECONCILIATION_REQUIRED")

    def test_unknown_ownership_cannot_converge(self) -> None:
        item = evidence(
            "a", ownership="UNKNOWN", ancestry="HEAD_ANCESTOR_OF_DEFAULT",
            ahead=0, behind=2, baseline=None,
        )
        inv = inventory((item,))
        report = self.classifier.classify(inv, closure(inv))
        self.assertEqual(report.branches[0].classification, "UNCLASSIFIED")
        self.assertIn("UNKNOWN_BRANCH_OWNERSHIP", report.anomaly_codes)
        self.assertEqual(report.disposition, "RECONCILIATION_REQUIRED")

    def test_branch_ahead_is_candidate_not_merge_permission(self) -> None:
        item = evidence("b", ancestry="DEFAULT_ANCESTOR_OF_HEAD", ahead=3, behind=0)
        classification, disposition = self.classification(item)
        self.assertEqual(classification, "MERGE_CANDIDATE")
        self.assertEqual(disposition, "RECONCILIATION_REQUIRED")

    def test_diverged_requires_port_not_merge(self) -> None:
        item = evidence("c", ancestry="DIVERGED", ahead=2, behind=4)
        self.assertEqual(self.classification(item)[0], "PORT_REQUIRED")

    def test_no_common_ancestor_is_foreign_history(self) -> None:
        item = evidence("d", ancestry="NO_COMMON_ANCESTOR", ahead=None, behind=None)
        self.assertEqual(self.classification(item)[0], "FOREIGN_HISTORY")

    def test_inferred_evidence_is_unclassified(self) -> None:
        item = evidence("e", epistemic="INFERRED")
        self.assertEqual(self.classification(item)[0], "UNCLASSIFIED")

    def test_integrated_and_superseded_are_converged_when_closure_ready(self) -> None:
        integrated = evidence("a", ancestry="HEAD_ANCESTOR_OF_DEFAULT", ahead=0, behind=2)
        superseded = evidence(
            "b", ancestry="DEFAULT_ANCESTOR_OF_HEAD", ahead=1, behind=0,
            superseded_by="mission/successor",
        )
        inv = inventory((integrated, superseded))
        report = self.classifier.classify(inv, closure(inv))
        self.assertEqual(
            tuple(item.classification for item in report.branches),
            ("ALREADY_INTEGRATED", "SUPERSEDED"),
        )
        self.assertEqual(report.disposition, "CONVERGED")

    def test_baseline_drift_for_live_candidate_forces_stop_replan(self) -> None:
        item = evidence("a", baseline=BASE)
        inv = inventory((item,), default_head=NEW_DEFAULT)
        report = self.classifier.classify(inv, closure(inv))
        self.assertEqual(report.disposition, "STOP_REPLAN_REQUIRED")
        self.assertIn("BASELINE_DRIFT", report.anomaly_codes)

    def test_empty_inventory_does_not_claim_convergence(self) -> None:
        inv = inventory(())
        report = self.classifier.classify(inv, closure(inv))
        self.assertEqual(report.disposition, "RECONCILIATION_REQUIRED")
        self.assertIn("EMPTY_INVENTORY", report.anomaly_codes)

    def test_each_closure_blocker_denies_convergence(self) -> None:
        integrated = evidence("a", ancestry="HEAD_ANCESTOR_OF_DEFAULT", ahead=0, behind=2)
        cases = (
            ("active_unknown_mission_count", "UNKNOWN_MISSION"),
            ("unknown_result_count", "UNKNOWN_RESULT"),
            ("unresolved_write_lease_count", "UNRESOLVED_WRITE_LEASE"),
            ("unreconciled_effect_count", "UNRECONCILED_EFFECT"),
            ("reconciliation_disagreement_count", "RECONCILIATION_DISAGREEMENT"),
        )
        for field, code in cases:
            with self.subTest(field=field):
                inv = inventory((integrated,))
                report = self.classifier.classify(inv, closure(inv, **{field: 1}))
                self.assertEqual(report.disposition, "RECONCILIATION_REQUIRED")
                self.assertIn(code, report.anomaly_codes)

    def test_untrusted_closure_evidence_denies_convergence(self) -> None:
        integrated = evidence("a", ancestry="HEAD_ANCESTOR_OF_DEFAULT", ahead=0, behind=2)
        inv = inventory((integrated,))
        report = self.classifier.classify(inv, closure(inv, epistemic_class="INFERRED"))
        self.assertEqual(report.disposition, "RECONCILIATION_REQUIRED")
        self.assertIn("CLOSURE_EVIDENCE_UNTRUSTED", report.anomaly_codes)

    def test_closure_inventory_binding_and_atomic_time_are_exact(self) -> None:
        integrated = evidence("a", ancestry="HEAD_ANCESTOR_OF_DEFAULT", ahead=0, behind=2)
        inv = inventory((integrated,))
        wrong_digest = ClosurePreconditions.build(
            repository=REPO,
            inventory_digest="f" * 64,
            active_unknown_mission_count=0,
            unknown_result_count=0,
            unresolved_write_lease_count=0,
            unreconciled_effect_count=0,
            reconciliation_disagreement_count=0,
            source_provenance_refs=("x",),
            epistemic_class="ANCHORED",
            observed_at=inv.observed_at,
        )
        with self.assertRaises(FleetReconciliationError):
            self.classifier.classify(inv, wrong_digest)
        stale = closure(inv, observed_at="2026-08-21T11:59:00+00:00")
        with self.assertRaises(FleetReconciliationError):
            self.classifier.classify(inv, stale)


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.clock_values = [
            datetime(2026, 8, 21, 12, 10, tzinfo=timezone.utc),
            datetime(2026, 8, 21, 12, 11, tzinfo=timezone.utc),
        ]
        self.store = ReconciliationStore(
            Path(self.tmp.name) / "reconciliation.db",
            trust_pins=PINS,
            clock=lambda: self.clock_values.pop(0),
        )
        self.classifier = BranchReconciliationClassifier()

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def converged_inventory(self, *, revision: int = 1, default_head: str = BASE) -> RepositoryInventory:
        item = evidence(
            "a", ancestry="HEAD_ANCESTOR_OF_DEFAULT", ahead=0, behind=1, baseline=BASE
        )
        return inventory((item,), revision=revision, default_head=default_head)

    def test_inventory_source_substitution_denied(self) -> None:
        with self.assertRaises(FleetReconciliationError):
            self.store.record_inventory(inventory((evidence("a"),), source_instance="evil"))

    def test_stale_inventory_revision_denied(self) -> None:
        first = self.converged_inventory(revision=1)
        self.store.record_inventory(first)
        with self.assertRaises(FleetReconciliationError):
            self.store.record_inventory(first)

    def test_report_persists_only_against_current_inventory(self) -> None:
        first = self.converged_inventory(revision=1)
        self.store.record_inventory(first)
        report = self.classifier.classify(first, closure(first))
        self.store.record_report(report)
        self.assertTrue(self.store.has_report(report.report_digest))

        newer_item = evidence("a", ancestry="HEAD_ANCESTOR_OF_DEFAULT", ahead=0, behind=2, baseline=BASE)
        newer = inventory((newer_item,), revision=2, default_head=NEW_DEFAULT)
        self.store.record_inventory(newer)
        with self.assertRaises(FleetReconciliationError):
            self.store.record_report(report)

    def test_receipt_requires_converged_report(self) -> None:
        inv = inventory((evidence("a"),))
        self.store.record_inventory(inv)
        report = self.classifier.classify(inv, closure(inv))
        self.store.record_report(report)
        with self.assertRaises(FleetReconciliationError):
            self.store.issue_convergence_receipt(report)

    def test_blocked_closure_never_gets_receipt(self) -> None:
        inv = self.converged_inventory()
        self.store.record_inventory(inv)
        report = self.classifier.classify(inv, closure(inv, unknown_result_count=1))
        self.store.record_report(report)
        with self.assertRaises(FleetReconciliationError):
            self.store.issue_convergence_receipt(report)

    def test_receipt_is_one_per_report_and_one_use(self) -> None:
        inv = self.converged_inventory()
        self.store.record_inventory(inv)
        report = self.classifier.classify(inv, closure(inv))
        self.store.record_report(report)
        receipt = self.store.issue_convergence_receipt(report)
        self.assertEqual(receipt.closure_preconditions_digest, report.closure_preconditions_digest)
        with self.assertRaises(FleetReconciliationError):
            self.store.issue_convergence_receipt(report)
        gate = RepositoryConvergenceGate(self.store)
        self.assertEqual(gate.observe_close_evidence_once(receipt), receipt.receipt_digest)
        self.assertTrue(self.store.receipt_consumed(receipt.receipt_digest))
        with self.assertRaises(FleetReconciliationError):
            gate.observe_close_evidence_once(receipt)

    def test_receipt_becomes_stale_after_new_inventory(self) -> None:
        inv = self.converged_inventory(revision=1)
        self.store.record_inventory(inv)
        report = self.classifier.classify(inv, closure(inv))
        self.store.record_report(report)
        receipt = self.store.issue_convergence_receipt(report)

        newer_item = evidence("a", ancestry="HEAD_ANCESTOR_OF_DEFAULT", ahead=0, behind=2, baseline=BASE)
        newer = inventory((newer_item,), revision=2, default_head=NEW_DEFAULT)
        self.store.record_inventory(newer)
        with self.assertRaises(FleetReconciliationError):
            self.store.claim_close_evidence_once(receipt)


class OrchestrationTests(unittest.TestCase):
    def test_reconciler_emits_receipt_only_for_converged_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv = inventory((evidence("a", ancestry="HEAD_ANCESTOR_OF_DEFAULT", ahead=0, behind=1),))
            store = ReconciliationStore(
                Path(tmp) / "r.db",
                trust_pins=PINS,
                clock=lambda: datetime(2026, 8, 21, 12, 10, tzinfo=timezone.utc),
            )
            try:
                run = FleetReconciler(
                    provider=Provider([inv]),
                    closure_provider=ClosureProvider(),
                    classifier=BranchReconciliationClassifier(),
                    store=store,
                ).reconcile(REPO)
                self.assertEqual(run.report.disposition, "CONVERGED")
                self.assertIsNotNone(run.convergence_receipt)
                self.assertEqual(run.closure_preconditions_digest, run.report.closure_preconditions_digest)
            finally:
                store.close()

    def test_reconciler_does_not_emit_receipt_when_closure_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv = inventory((evidence("a", ancestry="HEAD_ANCESTOR_OF_DEFAULT", ahead=0, behind=1),))
            store = ReconciliationStore(
                Path(tmp) / "r.db",
                trust_pins=PINS,
                clock=lambda: datetime(2026, 8, 21, 12, 10, tzinfo=timezone.utc),
            )
            try:
                run = FleetReconciler(
                    provider=Provider([inv]),
                    closure_provider=ClosureProvider(
                        lambda x: closure(x, reconciliation_disagreement_count=1)
                    ),
                    classifier=BranchReconciliationClassifier(),
                    store=store,
                ).reconcile(REPO)
                self.assertEqual(run.report.disposition, "RECONCILIATION_REQUIRED")
                self.assertIsNone(run.convergence_receipt)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()

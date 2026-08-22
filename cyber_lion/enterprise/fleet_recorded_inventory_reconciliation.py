"""F005-P reconciliation runner for an inventory already recorded by F005-J.

This bridge exists because the canonical FleetReconciler owns the ingest-first path and
therefore calls ReconciliationStore.record_inventory().  Runtime F005-J has already
performed that monotonic write.  Replaying the same inventory revision is correctly
rejected by the store, so the post-ingest path must start at closure observation,
classification, report persistence, and optional receipt issuance.

The runner performs no inventory write, receipt consumption, mission close, merge,
release, deploy, or authority mutation.
"""
from __future__ import annotations

from cyber_lion.contracts.fleet_reconciliation import (
    ClosurePreconditions,
    RepositoryInventory,
)
from cyber_lion.enterprise.fleet_reconciliation import (
    BranchReconciliationClassifier,
    ClosurePreconditionsProvider,
    FleetReconciliationError,
    ReconciliationRun,
    ReconciliationStore,
)


class RecordedInventoryReconciliationRunner:
    """Compute and persist reconciliation evidence for the exact recorded inventory."""

    def __init__(
        self,
        *,
        closure_provider: ClosurePreconditionsProvider,
        classifier: BranchReconciliationClassifier,
        store: ReconciliationStore,
    ) -> None:
        self._closure_provider = closure_provider
        self._classifier = classifier
        self._store = store

    def reconcile(
        self,
        repository: str,
        inventory: RepositoryInventory,
    ) -> ReconciliationRun:
        if not isinstance(repository, str) or not repository.strip() or "\x00" in repository:
            raise FleetReconciliationError("repository is invalid")
        if type(inventory) is not RepositoryInventory:
            raise FleetReconciliationError("inventory must use exact RepositoryInventory contract")
        inventory.validate()
        if inventory.repository != repository:
            raise FleetReconciliationError("inventory repository substitution denied")

        closure = self._closure_provider.snapshot(repository, inventory)
        if type(closure) is not ClosurePreconditions:
            raise FleetReconciliationError("closure provider returned invalid contract type")
        closure.validate()
        if closure.repository != repository or closure.inventory_digest != inventory.inventory_digest:
            raise FleetReconciliationError("closure provider binding mismatch")
        if closure.observed_at != inventory.observed_at:
            raise FleetReconciliationError("closure provider observation epoch mismatch")

        report = self._classifier.classify(inventory, closure)

        # record_report() is the first durable write in this post-ingest path and
        # independently re-checks the exact current inventory binding fail-closed.
        self._store.record_report(report)

        receipt = None
        if report.disposition == "CONVERGED":
            receipt = self._store.issue_convergence_receipt(report)

        return ReconciliationRun(
            inventory_digest=inventory.inventory_digest,
            closure_preconditions_digest=closure.preconditions_digest,
            report=report,
            convergence_receipt=receipt,
        )

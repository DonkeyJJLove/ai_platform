"""Production fail-closed ClosurePreconditionsProvider for F005-O.

The provider reuses the authoritative F005-G runtime observation semantics. It does
not write reconciliation state, generate reports, issue receipts, or assert closure.
The one post-report reconciliation completeness bit used by F005-G is removed from
the pre-report closure disagreement count to avoid a circular dependency.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from cyber_lion.contracts.fleet_reconciliation import ClosurePreconditions, RepositoryInventory
from cyber_lion.contracts.fleet_runtime_snapshot_source import RuntimeSnapshotSourceConfig
from cyber_lion.enterprise.fleet_runtime_snapshot_source import (
    RuntimeSnapshotSourceError,
    _parse_time,
    _read_reconciliation,
    observe_runtime_state,
)


class FleetClosurePreconditionsProviderError(RuntimeError):
    """Raised when exact trusted closure evidence cannot be established."""


class RuntimeClosurePreconditionsProvider:
    """Map canonical runtime observations onto exact reconciliation preconditions."""

    def __init__(
        self,
        *,
        current_master: str,
        current_master_tree: str,
        source_instance: str,
        status_db_path: str,
        coordination_db_path: str,
        reconciliation_db_path: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._current_master = current_master
        self._current_master_tree = current_master_tree
        self._source_instance = source_instance
        self._status_db_path = status_db_path
        self._coordination_db_path = coordination_db_path
        self._reconciliation_db_path = reconciliation_db_path
        self._clock = clock

    def snapshot(self, repository: str, inventory: RepositoryInventory) -> ClosurePreconditions:
        if type(inventory) is not RepositoryInventory:
            raise FleetClosurePreconditionsProviderError("inventory must use exact RepositoryInventory contract")
        inventory.validate()
        if repository != inventory.repository:
            raise FleetClosurePreconditionsProviderError("repository substitution denied")
        if inventory.default_head_sha != self._current_master:
            raise FleetClosurePreconditionsProviderError("inventory default head does not bind current master")

        inventory_time = _parse_time(inventory.observed_at)
        if self._clock is not None:
            supplied = self._clock()
            if supplied.tzinfo is None or supplied.astimezone(inventory_time.tzinfo) != inventory_time:
                raise FleetClosurePreconditionsProviderError("trusted observation clock does not bind inventory epoch")

        output_sentinel = str(Path(self._reconciliation_db_path).with_name("__f005_o_no_materialize__.json"))
        config = RuntimeSnapshotSourceConfig(
            repository=repository,
            current_master=self._current_master,
            current_master_tree=self._current_master_tree,
            source_instance=self._source_instance,
            status_db_path=self._status_db_path,
            coordination_db_path=self._coordination_db_path,
            reconciliation_db_path=self._reconciliation_db_path,
            output_path=output_sentinel,
        ).validate()

        try:
            observed = observe_runtime_state(config, clock=lambda: inventory_time)
            reconciliation = _read_reconciliation(
                self._reconciliation_db_path,
                repository,
                self._current_master,
            )
        except RuntimeSnapshotSourceError as exc:
            raise FleetClosurePreconditionsProviderError("authoritative closure evidence unavailable") from exc

        head = reconciliation.get("head")
        if not isinstance(head, dict):
            raise FleetClosurePreconditionsProviderError("reconciliation inventory head missing")
        expected_head = (
            inventory.inventory_id,
            inventory.inventory_revision,
            inventory.inventory_digest,
            inventory.default_head_sha,
            inventory.observed_at,
        )
        actual_head = (
            head.get("inventory_id"),
            int(head.get("inventory_revision", -1)),
            head.get("inventory_digest"),
            head.get("default_head_sha"),
            head.get("observed_at"),
        )
        if actual_head != expected_head:
            raise FleetClosurePreconditionsProviderError("reconciliation head does not bind exact inventory")

        if not observed.durable_state_consistency:
            raise FleetClosurePreconditionsProviderError("durable runtime state is inconsistent")
        if not observed.event_chain_consistency:
            raise FleetClosurePreconditionsProviderError("runtime event chain is inconsistent")
        if not observed.generation_fencing_consistency:
            raise FleetClosurePreconditionsProviderError("runtime generation fencing is inconsistent")

        post_report_disagreement = int(
            not reconciliation.get("converged")
            or not reconciliation.get("report_bound")
            or not reconciliation.get("receipt_bound")
        )
        pre_report_disagreements = observed.reconciliation_disagreements - post_report_disagreement
        if pre_report_disagreements < 0:
            raise FleetClosurePreconditionsProviderError("reconciliation disagreement accounting invalid")

        # The public observation exposes total unknown and active mission counts, not the
        # internal set intersection. Using total unknowns whenever any mission is active
        # is conservative: it can only block closure, never manufacture readiness.
        active_unknown_missions = observed.unknown_missions if observed.active_missions else 0

        return ClosurePreconditions.build(
            repository=repository,
            inventory_digest=inventory.inventory_digest,
            active_unknown_mission_count=active_unknown_missions,
            unknown_result_count=observed.unknown_results,
            unresolved_write_lease_count=observed.unresolved_write_leases,
            unreconciled_effect_count=observed.unreconciled_effects,
            reconciliation_disagreement_count=pre_report_disagreements,
            source_provenance_refs=(
                f"repository-inventory:{inventory.inventory_id}:{inventory.inventory_revision}",
                f"runtime-observation:{observed.source_digest}",
            ),
            epistemic_class="ANCHORED",
            observed_at=inventory.observed_at,
        )

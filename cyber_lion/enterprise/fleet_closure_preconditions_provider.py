"""Production fail-closed ClosurePreconditionsProvider for F005-O R2.

This provider reuses the canonical F005-G runtime observation algorithm while deriving
closure preconditions from a pre-report view. Report/receipt existence and receipt
consumption are deliberately excluded from provenance and from reconciliation blocker
accounting. No reconciliation, runtime, inventory, report, receipt, or closure state is
written by this module.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

from cyber_lion.contracts.fleet_reconciliation import ClosurePreconditions, RepositoryInventory
from cyber_lion.contracts.fleet_runtime_snapshot_source import RuntimeSnapshotSourceConfig, canonical_json
from cyber_lion.enterprise.fleet_runtime_snapshot_source import (
    RuntimeSnapshotSourceError,
    _parse_time,
    _read_reconciliation,
    observe_runtime_state,
)


class FleetClosurePreconditionsProviderError(RuntimeError):
    """Raised when exact trusted closure evidence cannot be established."""


def _head_binding(reconciliation: dict[str, Any]) -> tuple[object, ...]:
    head = reconciliation.get("head")
    if not isinstance(head, dict):
        raise FleetClosurePreconditionsProviderError("reconciliation inventory head missing")
    return (
        head.get("inventory_id"),
        int(head.get("inventory_revision", -1)),
        head.get("inventory_digest"),
        head.get("default_head_sha"),
        head.get("observed_at"),
    )


def _post_report_disagreement(reconciliation: dict[str, Any]) -> int:
    return int(
        not reconciliation.get("converged")
        or not reconciliation.get("report_bound")
        or not reconciliation.get("receipt_bound")
    )


def _pre_report_source_digest(
    *,
    repository: str,
    inventory: RepositoryInventory,
    observed: object,
    reconciliation_disagreements: int,
) -> str:
    # Deliberately exclude observed.source_digest and observed.inventory_complete:
    # F005-G binds both to post-report completeness. Everything below is derived from
    # the same canonical observation but contains only pre-report state.
    fields = {
        "repository": repository,
        "inventory_id": inventory.inventory_id,
        "inventory_revision": inventory.inventory_revision,
        "inventory_digest": inventory.inventory_digest,
        "default_head_sha": inventory.default_head_sha,
        "inventory_observed_at": inventory.observed_at,
        "observation_observed_at": observed.observed_at,
        "active_missions": observed.active_missions,
        "unknown_missions": observed.unknown_missions,
        "unresolved_write_leases": observed.unresolved_write_leases,
        "unknown_results": observed.unknown_results,
        "late_unreconciled_results": observed.late_unreconciled_results,
        "missing_heartbeats": observed.missing_heartbeats,
        "stale_heartbeats": observed.stale_heartbeats,
        "unknown_branch_ownership": observed.unknown_branch_ownership,
        "unowned_active_branches": observed.unowned_active_branches,
        "unreconciled_effects": observed.unreconciled_effects,
        "reconciliation_disagreements": reconciliation_disagreements,
        "active_authority": observed.active_authority,
        "residual_authority": observed.residual_authority,
        "durable_state_consistency": observed.durable_state_consistency,
        "event_chain_consistency": observed.event_chain_consistency,
        "generation_fencing_consistency": observed.generation_fencing_consistency,
    }
    return sha256(b"LION/F005-O-PRE-REPORT/2\0" + canonical_json(fields)).hexdigest()


class RuntimeClosurePreconditionsProvider:
    """Map one bounded canonical runtime observation onto exact pre-report blockers."""

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
            before = _read_reconciliation(self._reconciliation_db_path, repository, self._current_master)
            observed = observe_runtime_state(config, clock=lambda: inventory_time)
            after = _read_reconciliation(self._reconciliation_db_path, repository, self._current_master)
        except RuntimeSnapshotSourceError as exc:
            raise FleetClosurePreconditionsProviderError("authoritative closure evidence unavailable") from exc

        expected_head = (
            inventory.inventory_id,
            inventory.inventory_revision,
            inventory.inventory_digest,
            inventory.default_head_sha,
            inventory.observed_at,
        )
        before_head = _head_binding(before)
        after_head = _head_binding(after)
        if before_head != expected_head or after_head != expected_head:
            raise FleetClosurePreconditionsProviderError("reconciliation head does not bind exact inventory")
        if before_head != after_head:
            raise FleetClosurePreconditionsProviderError("reconciliation inventory changed during observation")
        if not before.get("stable") or not after.get("stable"):
            raise FleetClosurePreconditionsProviderError("reconciliation source unstable")

        # Post-report state may legitimately differ across separate calls, but changing
        # during one observation is treated as a race and fails closed. This allows a
        # single bounded epoch without making report/receipt state part of provenance.
        before_post = _post_report_disagreement(before)
        after_post = _post_report_disagreement(after)
        if before_post != after_post:
            raise FleetClosurePreconditionsProviderError("post-report state changed during observation")

        if not observed.durable_state_consistency:
            raise FleetClosurePreconditionsProviderError("durable runtime state is inconsistent")
        if not observed.event_chain_consistency:
            raise FleetClosurePreconditionsProviderError("runtime event chain is inconsistent")
        if not observed.generation_fencing_consistency:
            raise FleetClosurePreconditionsProviderError("runtime generation fencing is inconsistent")

        pre_report_disagreements = observed.reconciliation_disagreements - before_post
        if pre_report_disagreements < 0:
            raise FleetClosurePreconditionsProviderError("reconciliation disagreement accounting invalid")

        active_unknown_missions = observed.unknown_missions if observed.active_missions else 0
        pre_report_digest = _pre_report_source_digest(
            repository=repository,
            inventory=inventory,
            observed=observed,
            reconciliation_disagreements=pre_report_disagreements,
        )

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
                f"runtime-pre-report:{pre_report_digest}",
            ),
            epistemic_class="ANCHORED",
            observed_at=inventory.observed_at,
        )

"""Production fail-closed ClosurePreconditionsProvider for F005-O R4.

The provider reuses canonical F005-G runtime observation semantics while deriving
closure preconditions from a post-report-independent pre-report view. Post-report
state is observed only as a bounded-race fingerprint and never enters provenance,
precondition counters, or the preconditions digest.
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
    _observe_runtime_state_with_details,
    _parse_time,
    _read_reconciliation,
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


def _post_report_fingerprint(reconciliation: dict[str, Any]) -> tuple[object, ...]:
    """Exact bounded-observation race fingerprint; never used as closure provenance."""
    report = reconciliation.get("report")
    receipt = reconciliation.get("receipt")
    if report is not None and not isinstance(report, dict):
        raise FleetClosurePreconditionsProviderError("reconciliation report evidence invalid")
    if receipt is not None and not isinstance(receipt, dict):
        raise FleetClosurePreconditionsProviderError("reconciliation receipt evidence invalid")
    return (
        None if report is None else report.get("report_digest"),
        None if report is None else report.get("report_id"),
        None if report is None else report.get("disposition"),
        bool(reconciliation.get("report_bound")),
        bool(reconciliation.get("converged")),
        None if receipt is None else receipt.get("receipt_digest"),
        None if receipt is None else receipt.get("receipt_id"),
        bool(reconciliation.get("receipt_bound")),
        None if receipt is None else receipt.get("consumed"),
    )


def _pre_report_source_digest(
    *,
    repository: str,
    inventory: RepositoryInventory,
    observed: object,
    active_unknown_missions: int,
    status_registry_instance_id: str,
    status_revision: int,
    coordinator_id: str,
    coordination_revision: int,
    reconciliation_disagreements: int,
) -> str:
    # Deliberately exclude observed.source_digest and observed.inventory_complete:
    # F005-G binds those to post-report completeness. All fields below are pre-report.
    fields = {
        "repository": repository,
        "inventory_id": inventory.inventory_id,
        "inventory_revision": inventory.inventory_revision,
        "inventory_digest": inventory.inventory_digest,
        "default_head_sha": inventory.default_head_sha,
        "inventory_observed_at": inventory.observed_at,
        "observation_observed_at": observed.observed_at,
        "status_registry_instance_id": status_registry_instance_id,
        "status_revision": status_revision,
        "coordinator_id": coordinator_id,
        "coordination_revision": coordination_revision,
        "active_unknown_missions": active_unknown_missions,
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
    return sha256(b"LION/F005-O-PRE-REPORT/4\0" + canonical_json(fields)).hexdigest()


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
            details = _observe_runtime_state_with_details(config, clock=lambda: inventory_time)
            observed = details.observed
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

        if _post_report_fingerprint(before) != _post_report_fingerprint(after):
            raise FleetClosurePreconditionsProviderError("post-report state changed during observation")

        if not observed.durable_state_consistency:
            raise FleetClosurePreconditionsProviderError("durable runtime state is inconsistent")
        if not observed.event_chain_consistency:
            raise FleetClosurePreconditionsProviderError("runtime event chain is inconsistent")
        if not observed.generation_fencing_consistency:
            raise FleetClosurePreconditionsProviderError("runtime generation fencing is inconsistent")

        post_report_disagreement = _post_report_disagreement(before)
        pre_report_disagreements = observed.reconciliation_disagreements - post_report_disagreement
        if pre_report_disagreements < 0:
            raise FleetClosurePreconditionsProviderError("reconciliation disagreement accounting invalid")

        active_unknown_missions = len(details.active_ids.intersection(details.unknown_ids))
        pre_report_digest = _pre_report_source_digest(
            repository=repository,
            inventory=inventory,
            observed=observed,
            active_unknown_missions=active_unknown_missions,
            status_registry_instance_id=details.status_registry_instance_id,
            status_revision=details.status_revision,
            coordinator_id=details.coordinator_id,
            coordination_revision=details.coordination_revision,
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
                f"fleet-status:{details.status_registry_instance_id}:{details.status_revision}",
                f"fleet-coordination:{details.coordinator_id}:{details.coordination_revision}",
                f"repository-inventory:{inventory.inventory_id}:{inventory.inventory_revision}",
                f"runtime-pre-report:{pre_report_digest}",
            ),
            epistemic_class="ANCHORED",
            observed_at=inventory.observed_at,
        )
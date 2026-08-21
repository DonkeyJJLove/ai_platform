"""Strict source contract for F005-G authoritative runtime convergence snapshots.

The producer is evidence-only. It grants no authority and may only materialize a
derived snapshot file from explicitly supplied read-only runtime stores.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from cyber_lion.contracts.fleet_runtime_convergence import RuntimeFleetConvergenceSnapshot

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_REPO = re.compile(r"^[^/\s]+/[^/\s]+$")


class RuntimeSnapshotSourceContractError(ValueError):
    pass


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise RuntimeSnapshotSourceContractError(f"{name} invalid")
    return value


def _sha40(value: object, name: str) -> str:
    value = _text(value, name)
    if not _SHA40.fullmatch(value):
        raise RuntimeSnapshotSourceContractError(f"{name} must be lowercase git sha")
    return value


def _absolute_path(value: object, name: str) -> str:
    value = _text(value, name)
    if not Path(value).is_absolute():
        raise RuntimeSnapshotSourceContractError(f"{name} must be absolute")
    return value


@dataclass(frozen=True)
class RuntimeSnapshotSourceConfig:
    repository: str
    current_master: str
    current_master_tree: str
    source_instance: str
    status_db_path: str
    coordination_db_path: str
    reconciliation_db_path: str
    output_path: str

    def validate(self) -> "RuntimeSnapshotSourceConfig":
        if not _REPO.fullmatch(_text(self.repository, "repository")):
            raise RuntimeSnapshotSourceContractError("repository must use owner/name form")
        _sha40(self.current_master, "current_master")
        _sha40(self.current_master_tree, "current_master_tree")
        _text(self.source_instance, "source_instance")
        paths = (
            _absolute_path(self.status_db_path, "status_db_path"),
            _absolute_path(self.coordination_db_path, "coordination_db_path"),
            _absolute_path(self.reconciliation_db_path, "reconciliation_db_path"),
        )
        if len(set(paths)) != len(paths):
            raise RuntimeSnapshotSourceContractError("runtime source databases must be distinct")
        _absolute_path(self.output_path, "output_path")
        return self


@dataclass(frozen=True)
class ObservedRuntimeState:
    observed_at: str
    source_digest: str
    active_missions: int
    unknown_missions: int
    unresolved_write_leases: int
    unknown_results: int
    late_unreconciled_results: int
    missing_heartbeats: int
    stale_heartbeats: int
    unknown_branch_ownership: int
    unowned_active_branches: int
    unreconciled_effects: int
    reconciliation_disagreements: int
    active_authority: int
    residual_authority: int
    durable_state_consistency: bool
    event_chain_consistency: bool
    generation_fencing_consistency: bool
    inventory_complete: bool

    def validate(self) -> "ObservedRuntimeState":
        _text(self.observed_at, "observed_at")
        if not re.fullmatch(r"[0-9a-f]{64}", _text(self.source_digest, "source_digest")):
            raise RuntimeSnapshotSourceContractError("source_digest must be sha256")
        counters = (
            "active_missions", "unknown_missions", "unresolved_write_leases",
            "unknown_results", "late_unreconciled_results", "missing_heartbeats",
            "stale_heartbeats", "unknown_branch_ownership", "unowned_active_branches",
            "unreconciled_effects", "reconciliation_disagreements", "active_authority",
            "residual_authority",
        )
        for name in counters:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise RuntimeSnapshotSourceContractError(f"{name} invalid")
        for name in (
            "durable_state_consistency", "event_chain_consistency",
            "generation_fencing_consistency", "inventory_complete",
        ):
            if type(getattr(self, name)) is not bool:
                raise RuntimeSnapshotSourceContractError(f"{name} invalid")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def build_convergence_snapshot(
    config: RuntimeSnapshotSourceConfig,
    observed: ObservedRuntimeState,
) -> RuntimeFleetConvergenceSnapshot:
    config.validate()
    observed.validate()
    snapshot_id = sha256(
        b"LION/F005-G-SNAPSHOT/1\0"
        + canonical_json(
            {
                "repository": config.repository,
                "current_master": config.current_master,
                "current_master_tree": config.current_master_tree,
                "source_instance": config.source_instance,
                "observed_at": observed.observed_at,
                "source_digest": observed.source_digest,
            }
        )
    ).hexdigest()
    return RuntimeFleetConvergenceSnapshot(
        schema_version="1.0.0",
        snapshot_id=snapshot_id,
        repository=config.repository,
        current_master=config.current_master,
        current_master_tree=config.current_master_tree,
        observed_at=observed.observed_at,
        source_kind="AUTHORITATIVE_RUNTIME_STORE",
        source_instance=config.source_instance,
        source_digest=observed.source_digest,
        active_missions=observed.active_missions,
        unknown_missions=observed.unknown_missions,
        unresolved_write_leases=observed.unresolved_write_leases,
        unknown_results=observed.unknown_results,
        late_unreconciled_results=observed.late_unreconciled_results,
        missing_heartbeats=observed.missing_heartbeats,
        stale_heartbeats=observed.stale_heartbeats,
        unknown_branch_ownership=observed.unknown_branch_ownership,
        unowned_active_branches=observed.unowned_active_branches,
        unreconciled_effects=observed.unreconciled_effects,
        reconciliation_disagreements=observed.reconciliation_disagreements,
        active_authority=observed.active_authority,
        residual_authority=observed.residual_authority,
        durable_state_consistency=observed.durable_state_consistency,
        event_chain_consistency=observed.event_chain_consistency,
        generation_fencing_consistency=observed.generation_fencing_consistency,
        inventory_complete=observed.inventory_complete,
    ).validate()

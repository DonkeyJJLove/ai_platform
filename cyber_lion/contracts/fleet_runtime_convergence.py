"""Strict evidence contract for F005 runtime fleet convergence.

This contract is evidence-only. It grants no authority and performs no mutation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_ZERO_COUNTERS = (
    "active_missions",
    "unknown_missions",
    "unresolved_write_leases",
    "unknown_results",
    "late_unreconciled_results",
    "missing_heartbeats",
    "stale_heartbeats",
    "unknown_branch_ownership",
    "unowned_active_branches",
    "unreconciled_effects",
    "reconciliation_disagreements",
    "active_authority",
    "residual_authority",
)


class RuntimeFleetConvergenceContractError(ValueError):
    pass


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise RuntimeFleetConvergenceContractError(f"{name} invalid")
    return value


def _sha40(value: object, name: str) -> str:
    value = _text(value, name)
    if not _SHA40.fullmatch(value):
        raise RuntimeFleetConvergenceContractError(f"{name} must be lowercase git sha")
    return value


def _sha256(value: object, name: str) -> str:
    value = _text(value, name)
    if not _SHA256.fullmatch(value):
        raise RuntimeFleetConvergenceContractError(f"{name} must be sha256")
    return value


@dataclass(frozen=True)
class RuntimeFleetConvergenceSnapshot:
    schema_version: str
    snapshot_id: str
    repository: str
    current_master: str
    current_master_tree: str
    observed_at: str
    source_kind: str
    source_instance: str
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

    def validate(self) -> "RuntimeFleetConvergenceSnapshot":
        if self.schema_version != "1.0.0":
            raise RuntimeFleetConvergenceContractError("unsupported schema_version")
        _sha256(self.snapshot_id, "snapshot_id")
        repository = _text(self.repository, "repository")
        if repository.count("/") != 1:
            raise RuntimeFleetConvergenceContractError("repository invalid")
        _sha40(self.current_master, "current_master")
        _sha40(self.current_master_tree, "current_master_tree")
        _text(self.observed_at, "observed_at")
        if self.source_kind != "AUTHORITATIVE_RUNTIME_STORE":
            raise RuntimeFleetConvergenceContractError("non-authoritative source denied")
        _text(self.source_instance, "source_instance")
        _sha256(self.source_digest, "source_digest")
        for name in _REQUIRED_ZERO_COUNTERS:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise RuntimeFleetConvergenceContractError(f"{name} invalid")
        for name in (
            "durable_state_consistency",
            "event_chain_consistency",
            "generation_fencing_consistency",
            "inventory_complete",
        ):
            if type(getattr(self, name)) is not bool:
                raise RuntimeFleetConvergenceContractError(f"{name} invalid")
        return self

    def blocker_codes(self) -> tuple[str, ...]:
        self.validate()
        blockers = [name.upper() for name in _REQUIRED_ZERO_COUNTERS if getattr(self, name) != 0]
        if not self.durable_state_consistency:
            blockers.append("DURABLE_STATE_INCONSISTENT")
        if not self.event_chain_consistency:
            blockers.append("EVENT_CHAIN_INCONSISTENT")
        if not self.generation_fencing_consistency:
            blockers.append("GENERATION_FENCING_INCONSISTENT")
        if not self.inventory_complete:
            blockers.append("PARTIAL_RUNTIME_INVENTORY")
        return tuple(blockers)

    def closable(self) -> bool:
        return not self.blocker_codes()

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    def digest(self) -> str:
        return sha256(b"LION/F005-RUNTIME-CONVERGENCE/1\0" + canonical_json(self.canonical_dict())).hexdigest()

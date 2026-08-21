"""F005-J contracts for runtime reconciliation inventory ingestion.

This slice accepts an immutable external repository observation, binds it to the
provisioned reconciliation trust pins and exact live master, and permits exactly one
RepositoryInventory head update through ReconciliationStore.record_inventory(). It
never emits reconciliation reports, convergence receipts, closure facts, or authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import PureWindowsPath
import re
from typing import Any, Mapping, Tuple

from cyber_lion.contracts.fleet_reconciliation import ReconciliationTrustPins
from cyber_lion.contracts.fleet_runtime_paths import resolve_fleet_runtime_paths

REPOSITORY = "DonkeyJJLove/ai_platform"
RUNTIME_SOURCE_INSTANCE_ID = "lion-runtime-reconciliation-source-01"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class RuntimeReconciliationIngestionContractError(ValueError):
    pass


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: object, name: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise RuntimeReconciliationIngestionContractError(f"{name} invalid")
    return value


def _sha40(value: object, name: str) -> str:
    value = _text(value, name, limit=40)
    if not _SHA40.fullmatch(value):
        raise RuntimeReconciliationIngestionContractError(f"{name} must be full lowercase git SHA")
    return value


def _sha256(value: object, name: str) -> str:
    value = _text(value, name, limit=64)
    if not _SHA256.fullmatch(value):
        raise RuntimeReconciliationIngestionContractError(f"{name} must be sha256 hex")
    return value


def _exact_path(value: object, expected: str, name: str) -> str:
    value = _text(value, name)
    actual = PureWindowsPath(value)
    target = PureWindowsPath(expected)
    if not actual.is_absolute() or actual != target:
        raise RuntimeReconciliationIngestionContractError(f"{name} must equal {expected}")
    return str(actual)


@dataclass(frozen=True)
class RuntimeReconciliationIngestionConfig:
    repository: str
    current_master: str
    current_master_tree: str
    source_instance_id: str
    observation_sha256: str
    trust_sha256: str
    reconciliation_db_path: str = field(default_factory=lambda: resolve_fleet_runtime_paths().reconciliation_db_path)
    observation_path: str = field(default_factory=lambda: resolve_fleet_runtime_paths().repository_inventory_path)
    reconciliation_trust_path: str = field(default_factory=lambda: resolve_fleet_runtime_paths().reconciliation_trust_path)

    def validate(self) -> "RuntimeReconciliationIngestionConfig":
        if self.repository != REPOSITORY:
            raise RuntimeReconciliationIngestionContractError("repository binding mismatch")
        _sha40(self.current_master, "current_master")
        _sha40(self.current_master_tree, "current_master_tree")
        if self.source_instance_id != RUNTIME_SOURCE_INSTANCE_ID:
            raise RuntimeReconciliationIngestionContractError("source instance substitution denied")
        _sha256(self.observation_sha256, "observation_sha256")
        _sha256(self.trust_sha256, "trust_sha256")
        paths = resolve_fleet_runtime_paths()
        _exact_path(self.reconciliation_db_path, paths.reconciliation_db_path, "reconciliation_db_path")
        _exact_path(self.observation_path, paths.repository_inventory_path, "observation_path")
        _exact_path(self.reconciliation_trust_path, paths.reconciliation_trust_path, "reconciliation_trust_path")
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(
            b"LION/F005-J-RUNTIME-RECONCILIATION-INGESTION-CONFIG/1\0"
            + canonical_json(asdict(self))
        ).hexdigest()


@dataclass(frozen=True)
class ObservedBranch:
    branch: str
    branch_head_sha: str
    mission_id: str | None
    baseline_sha: str | None
    ownership_state: str
    ancestry_state: str
    ahead_by: int | None
    behind_by: int | None
    superseded_by_branch: str | None
    supersession_provenance_ref: str | None
    source_provenance_ref: str
    epistemic_class: str
    observed_at: str


@dataclass(frozen=True)
class RuntimeRepositoryObservation:
    schema_version: str
    repository: str
    inventory_revision: int
    default_branch: str
    default_head_sha: str
    observed_at: str
    branches: Tuple[ObservedBranch, ...]

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "repository": self.repository,
            "inventory_revision": self.inventory_revision,
            "default_branch": self.default_branch,
            "default_head_sha": self.default_head_sha,
            "observed_at": self.observed_at,
            "branches": [asdict(item) for item in self.branches],
        }

    def deterministic_inventory_id(self, pins: ReconciliationTrustPins) -> str:
        pins.validate()
        return sha256(
            b"LION/F005-J-REPOSITORY-INVENTORY-ID/1\0"
            + canonical_json({
                "observation": self.canonical_dict(),
                "source_pins": {
                    "source_id": pins.source_id,
                    "source_instance_id": pins.source_instance_id,
                    "source_implementation_digest": pins.source_implementation_digest,
                    "trust_anchor_id": pins.trust_anchor_id,
                },
            })
        ).hexdigest()


@dataclass(frozen=True)
class RuntimeReconciliationIngestionReceipt:
    schema_version: str
    repository: str
    current_master: str
    current_master_tree: str
    source_instance_id: str
    config_digest: str
    observation_sha256: str
    trust_sha256: str
    inventory_id: str
    inventory_revision: int
    inventory_digest: str
    branch_count: int
    report_generated: bool
    convergence_receipt_generated: bool
    convergence_receipt_consumed: bool
    fleet_close_asserted: bool

    def validate(self) -> "RuntimeReconciliationIngestionReceipt":
        if self.schema_version != "1.0.0":
            raise RuntimeReconciliationIngestionContractError("unsupported receipt schema_version")
        if self.repository != REPOSITORY:
            raise RuntimeReconciliationIngestionContractError("receipt repository binding mismatch")
        _sha40(self.current_master, "current_master")
        _sha40(self.current_master_tree, "current_master_tree")
        if self.source_instance_id != RUNTIME_SOURCE_INSTANCE_ID:
            raise RuntimeReconciliationIngestionContractError("receipt source instance mismatch")
        for name in ("config_digest", "observation_sha256", "trust_sha256", "inventory_id", "inventory_digest"):
            _sha256(getattr(self, name), name)
        if isinstance(self.inventory_revision, bool) or not isinstance(self.inventory_revision, int) or self.inventory_revision < 1:
            raise RuntimeReconciliationIngestionContractError("inventory_revision invalid")
        if isinstance(self.branch_count, bool) or not isinstance(self.branch_count, int) or self.branch_count < 1:
            raise RuntimeReconciliationIngestionContractError("branch_count must be positive")
        for name in (
            "report_generated",
            "convergence_receipt_generated",
            "convergence_receipt_consumed",
            "fleet_close_asserted",
        ):
            value = getattr(self, name)
            if type(value) is not bool or value:
                raise RuntimeReconciliationIngestionContractError(f"{name} must remain false")
        return self

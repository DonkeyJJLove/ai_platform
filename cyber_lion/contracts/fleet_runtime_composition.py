"""Contracts for the F005-H Windows runtime composition root.

The composition root binds existing durable fleet stores to deterministic runtime
paths. It does not create mission facts, results, heartbeats, reconciliation facts,
authority, leases, effects, or closure evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import PureWindowsPath
import re
from typing import Any, Mapping

from cyber_lion.contracts.fleet_reconciliation import ReconciliationTrustPins
from cyber_lion.contracts.fleet_status import VerificationTrustPins
from cyber_lion.contracts.fleet_runtime_paths import resolve_fleet_runtime_paths

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPO = re.compile(r"^[^/\s]+/[^/\s]+$")


class FleetRuntimeCompositionContractError(ValueError):
    pass


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: object, name: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise FleetRuntimeCompositionContractError(f"{name} invalid")
    return value


def _sha40(value: object, name: str) -> str:
    value = _text(value, name, limit=40)
    if not _SHA40.fullmatch(value):
        raise FleetRuntimeCompositionContractError(f"{name} must be a full lowercase git SHA")
    return value


def _sha256(value: object, name: str) -> str:
    value = _text(value, name, limit=64)
    if not _SHA256.fullmatch(value):
        raise FleetRuntimeCompositionContractError(f"{name} must be sha256 hex")
    return value


def _exact_windows_path(value: object, expected: str, name: str) -> str:
    value = _text(value, name)
    path = PureWindowsPath(value)
    expected_path = PureWindowsPath(expected)
    if not path.is_absolute() or path != expected_path:
        raise FleetRuntimeCompositionContractError(f"{name} must equal {expected}")
    return str(path)


@dataclass(frozen=True)
class RuntimeCompositionConfig:
    repository: str
    current_master: str
    current_master_tree: str
    composition_instance_id: str
    registry_instance_id: str
    coordinator_instance_id: str
    verification_pins: VerificationTrustPins
    reconciliation_pins: ReconciliationTrustPins
    runtime_root: str = field(default_factory=lambda: resolve_fleet_runtime_paths().runtime_root)
    status_db_path: str = field(default_factory=lambda: resolve_fleet_runtime_paths().status_db_path)
    coordination_db_path: str = field(default_factory=lambda: resolve_fleet_runtime_paths().coordination_db_path)
    reconciliation_db_path: str = field(default_factory=lambda: resolve_fleet_runtime_paths().reconciliation_db_path)

    def validate(self) -> "RuntimeCompositionConfig":
        if not _REPO.fullmatch(_text(self.repository, "repository")):
            raise FleetRuntimeCompositionContractError("repository must use owner/name form")
        _sha40(self.current_master, "current_master")
        _sha40(self.current_master_tree, "current_master_tree")
        _text(self.composition_instance_id, "composition_instance_id")
        _text(self.registry_instance_id, "registry_instance_id")
        _text(self.coordinator_instance_id, "coordinator_instance_id")
        if type(self.verification_pins) is not VerificationTrustPins:
            raise FleetRuntimeCompositionContractError("verification_pins must use exact contract type")
        if type(self.reconciliation_pins) is not ReconciliationTrustPins:
            raise FleetRuntimeCompositionContractError("reconciliation_pins must use exact contract type")
        self.verification_pins.validate()
        self.reconciliation_pins.validate()
        paths = resolve_fleet_runtime_paths()
        _exact_windows_path(self.runtime_root, paths.runtime_root, "runtime_root")
        _exact_windows_path(self.status_db_path, paths.status_db_path, "status_db_path")
        _exact_windows_path(self.coordination_db_path, paths.coordination_db_path, "coordination_db_path")
        _exact_windows_path(self.reconciliation_db_path, paths.reconciliation_db_path, "reconciliation_db_path")
        paths = {
            PureWindowsPath(self.status_db_path),
            PureWindowsPath(self.coordination_db_path),
            PureWindowsPath(self.reconciliation_db_path),
        }
        if len(paths) != 3:
            raise FleetRuntimeCompositionContractError("runtime store paths must be distinct")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "repository": self.repository,
            "current_master": self.current_master,
            "current_master_tree": self.current_master_tree,
            "composition_instance_id": self.composition_instance_id,
            "registry_instance_id": self.registry_instance_id,
            "coordinator_instance_id": self.coordinator_instance_id,
            "verification_pins": asdict(self.verification_pins),
            "reconciliation_pins": asdict(self.reconciliation_pins),
            "runtime_root": str(PureWindowsPath(self.runtime_root)),
            "status_db_path": str(PureWindowsPath(self.status_db_path)),
            "coordination_db_path": str(PureWindowsPath(self.coordination_db_path)),
            "reconciliation_db_path": str(PureWindowsPath(self.reconciliation_db_path)),
        }

    def digest(self) -> str:
        return sha256(b"LION/F005-H-COMPOSITION/1\0" + canonical_json(self.canonical_dict())).hexdigest()


@dataclass(frozen=True)
class RuntimeCompositionReceipt:
    schema_version: str
    composition_id: str
    repository: str
    current_master: str
    current_master_tree: str
    composition_instance_id: str
    runtime_root: str
    status_db_path: str
    coordination_db_path: str
    reconciliation_db_path: str
    status_mission_count: int
    coordination_mission_count: int
    reconciliation_inventory_count: int
    state_classification: str
    closable: bool
    composition_digest: str

    def validate(self) -> "RuntimeCompositionReceipt":
        if self.schema_version != "1.0.0":
            raise FleetRuntimeCompositionContractError("unsupported receipt schema_version")
        _sha256(self.composition_id, "composition_id")
        if not _REPO.fullmatch(_text(self.repository, "repository")):
            raise FleetRuntimeCompositionContractError("repository invalid")
        _sha40(self.current_master, "current_master")
        _sha40(self.current_master_tree, "current_master_tree")
        _text(self.composition_instance_id, "composition_instance_id")
        paths = resolve_fleet_runtime_paths()
        _exact_windows_path(self.runtime_root, paths.runtime_root, "runtime_root")
        _exact_windows_path(self.status_db_path, paths.status_db_path, "status_db_path")
        _exact_windows_path(self.coordination_db_path, paths.coordination_db_path, "coordination_db_path")
        _exact_windows_path(self.reconciliation_db_path, paths.reconciliation_db_path, "reconciliation_db_path")
        for name in ("status_mission_count", "coordination_mission_count", "reconciliation_inventory_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise FleetRuntimeCompositionContractError(f"{name} invalid")
        if self.state_classification not in {"EMPTY_NOT_CLOSABLE", "STATE_PRESENT_REQUIRES_RUNTIME_CONVERGENCE"}:
            raise FleetRuntimeCompositionContractError("state_classification invalid")
        if type(self.closable) is not bool or self.closable:
            raise FleetRuntimeCompositionContractError("composition bootstrap can never assert closable")
        _sha256(self.composition_digest, "composition_digest")
        return self

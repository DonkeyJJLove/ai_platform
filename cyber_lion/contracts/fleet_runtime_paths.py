"""Canonical F005 logical runtime-path resolver.

F005 runtime state is deployment state, not repository state. The root therefore
must be supplied explicitly through ``LION_FLEET_RUNTIME_ROOT``. There is no
fallback path: a missing or invalid binding fails closed before any runtime effect.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import PureWindowsPath
from typing import Mapping

RUNTIME_ROOT_ENV = "LION_FLEET_RUNTIME_ROOT"


class FleetRuntimePathContractError(ValueError):
    pass


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise FleetRuntimePathContractError(f"{name} invalid")
    return value.strip()


def _canonical_root(raw: object) -> PureWindowsPath:
    value = _text(raw, RUNTIME_ROOT_ENV)
    path = PureWindowsPath(value)
    if not path.is_absolute():
        raise FleetRuntimePathContractError("fleet runtime root must be an absolute Windows path")
    if any(part in {".", ".."} for part in path.parts):
        raise FleetRuntimePathContractError("fleet runtime root traversal denied")
    if path.drive.casefold() == "c:" and len(path.parts) > 1 and path.parts[1].casefold() == "lion":
        raise FleetRuntimePathContractError("legacy C:\\LION runtime root is falsified")
    return path


def _child(root: PureWindowsPath, *parts: str) -> str:
    value = root.joinpath(*parts)
    if not value.is_absolute():
        raise FleetRuntimePathContractError("derived runtime path must remain absolute")
    return str(value)


@dataclass(frozen=True)
class FleetRuntimePaths:
    runtime_root: str
    status_db_path: str
    coordination_db_path: str
    reconciliation_db_path: str
    trust_root: str
    verification_trust_path: str
    reconciliation_trust_path: str
    f005_h_pins_path: str
    trust_provisioning_receipt_path: str
    reconciliation_source_root: str
    branch_ownership_manifest_path: str
    branch_ownership_registry_path: str
    repository_inventory_path: str
    fleet_convergence_snapshot_path: str


def resolve_fleet_runtime_paths(
    environ: Mapping[str, str] | None = None,
) -> FleetRuntimePaths:
    source = os.environ if environ is None else environ
    raw = source.get(RUNTIME_ROOT_ENV)
    if raw is None:
        raise FleetRuntimePathContractError(f"{RUNTIME_ROOT_ENV} missing")
    root = _canonical_root(raw)
    trust = root / "trust"
    reconciliation_source = root / "reconciliation-source"
    return FleetRuntimePaths(
        runtime_root=str(root),
        status_db_path=_child(root, "status.sqlite"),
        coordination_db_path=_child(root, "coordination.sqlite"),
        reconciliation_db_path=_child(root, "reconciliation.sqlite"),
        trust_root=str(trust),
        verification_trust_path=_child(trust, "verification-trust.json"),
        reconciliation_trust_path=_child(trust, "reconciliation-trust.json"),
        f005_h_pins_path=_child(trust, "f005-h-pins.json"),
        trust_provisioning_receipt_path=_child(trust, "trust-provisioning-receipt.json"),
        reconciliation_source_root=str(reconciliation_source),
        branch_ownership_manifest_path=_child(reconciliation_source, "branch-ownership-manifest.json"),
        branch_ownership_registry_path=_child(reconciliation_source, "branch-ownership-registry.json"),
        repository_inventory_path=_child(reconciliation_source, "repository-inventory.json"),
        fleet_convergence_snapshot_path=_child(root, "fleet-convergence-snapshot.json"),
    )

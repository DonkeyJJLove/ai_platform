"""Contracts for F005-I runtime trust-root provisioning.

This slice derives trust pins from explicit external runtime material. It does not
assert verification success, reconciliation convergence, fleet closure, or mint
operational authority.
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

REPOSITORY = "DonkeyJJLove/ai_platform"
RUNTIME_INSTANCE_ID = "lion-runtime-01"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class FleetRuntimeTrustContractError(ValueError):
    pass


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _text(value: object, name: str, *, limit: int = 4096) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise FleetRuntimeTrustContractError(f"{name} invalid")
    return value


def _sha40(value: object, name: str) -> str:
    value = _text(value, name, limit=40)
    if not _SHA40.fullmatch(value):
        raise FleetRuntimeTrustContractError(
            f"{name} must be a full lowercase git SHA"
        )
    return value


def _sha256(value: object, name: str) -> str:
    value = _text(value, name, limit=64)
    if not _SHA256.fullmatch(value):
        raise FleetRuntimeTrustContractError(f"{name} must be sha256 hex")
    return value


def _exact_windows_path(value: object, expected: str, name: str) -> str:
    value = _text(value, name)
    actual = PureWindowsPath(value)
    target = PureWindowsPath(expected)
    if not actual.is_absolute() or actual != target:
        raise FleetRuntimeTrustContractError(f"{name} must equal {expected}")
    return str(actual)


@dataclass(frozen=True)
class RuntimeTrustProvisioningConfig:
    repository: str
    current_master: str
    current_master_tree: str
    runtime_instance_id: str
    expected_verifier_id: str
    expected_verification_trust_anchor_id: str
    expected_reconciliation_source_id: str
    expected_reconciliation_source_instance_id: str
    expected_reconciliation_trust_anchor_id: str
    trust_root: str = field(default_factory=lambda: resolve_fleet_runtime_paths().trust_root)
    verification_trust_path: str = field(default_factory=lambda: resolve_fleet_runtime_paths().verification_trust_path)
    reconciliation_trust_path: str = field(default_factory=lambda: resolve_fleet_runtime_paths().reconciliation_trust_path)
    f005_h_pins_path: str = field(default_factory=lambda: resolve_fleet_runtime_paths().f005_h_pins_path)
    provisioning_receipt_path: str = field(default_factory=lambda: resolve_fleet_runtime_paths().trust_provisioning_receipt_path)

    def validate(self) -> "RuntimeTrustProvisioningConfig":
        if self.repository != REPOSITORY:
            raise FleetRuntimeTrustContractError("repository binding mismatch")
        _sha40(self.current_master, "current_master")
        _sha40(self.current_master_tree, "current_master_tree")
        if self.runtime_instance_id != RUNTIME_INSTANCE_ID:
            raise FleetRuntimeTrustContractError("runtime instance substitution denied")
        for name in (
            "expected_verifier_id",
            "expected_verification_trust_anchor_id",
            "expected_reconciliation_source_id",
            "expected_reconciliation_source_instance_id",
            "expected_reconciliation_trust_anchor_id",
        ):
            _text(getattr(self, name), name, limit=256)
        paths = resolve_fleet_runtime_paths()
        _exact_windows_path(self.trust_root, paths.trust_root, "trust_root")
        _exact_windows_path(
            self.verification_trust_path,
            paths.verification_trust_path,
            "verification_trust_path",
        )
        _exact_windows_path(
            self.reconciliation_trust_path,
            paths.reconciliation_trust_path,
            "reconciliation_trust_path",
        )
        _exact_windows_path(self.f005_h_pins_path, paths.f005_h_pins_path, "f005_h_pins_path")
        _exact_windows_path(
            self.provisioning_receipt_path,
            paths.trust_provisioning_receipt_path,
            "provisioning_receipt_path",
        )
        outputs = {
            PureWindowsPath(self.verification_trust_path),
            PureWindowsPath(self.reconciliation_trust_path),
            PureWindowsPath(self.f005_h_pins_path),
            PureWindowsPath(self.provisioning_receipt_path),
        }
        if len(outputs) != 4:
            raise FleetRuntimeTrustContractError("runtime trust outputs must be distinct")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "repository": self.repository,
            "current_master": self.current_master,
            "current_master_tree": self.current_master_tree,
            "runtime_instance_id": self.runtime_instance_id,
            "expected_verifier_id": self.expected_verifier_id,
            "expected_verification_trust_anchor_id": self.expected_verification_trust_anchor_id,
            "expected_reconciliation_source_id": self.expected_reconciliation_source_id,
            "expected_reconciliation_source_instance_id": self.expected_reconciliation_source_instance_id,
            "expected_reconciliation_trust_anchor_id": self.expected_reconciliation_trust_anchor_id,
            "trust_root": str(PureWindowsPath(self.trust_root)),
            "verification_trust_path": str(PureWindowsPath(self.verification_trust_path)),
            "reconciliation_trust_path": str(PureWindowsPath(self.reconciliation_trust_path)),
            "f005_h_pins_path": str(PureWindowsPath(self.f005_h_pins_path)),
            "provisioning_receipt_path": str(PureWindowsPath(self.provisioning_receipt_path)),
        }

    def digest(self) -> str:
        return sha256(
            b"LION/F005-I-RUNTIME-TRUST-CONFIG/1\0"
            + canonical_json(self.canonical_dict())
        ).hexdigest()


@dataclass(frozen=True)
class RuntimeTrustProvisioningReceipt:
    schema_version: str
    receipt_id: str
    repository: str
    current_master: str
    current_master_tree: str
    runtime_instance_id: str
    config_digest: str
    verification_manifest_digest: str
    verifier_identity_digest: str
    verifier_implementation_digest: str
    verification_anchor_manifest_digest: str
    reconciliation_manifest_digest: str
    reconciliation_source_implementation_digest: str
    reconciliation_anchor_manifest_digest: str
    f005_h_pins_digest: str
    outputs_digest: str
    asserts_verification_pass: bool
    asserts_fleet_closure: bool

    def validate(self) -> "RuntimeTrustProvisioningReceipt":
        if self.schema_version != "1.0.0":
            raise FleetRuntimeTrustContractError("unsupported receipt schema_version")
        _sha256(self.receipt_id, "receipt_id")
        if self.repository != REPOSITORY:
            raise FleetRuntimeTrustContractError("receipt repository binding mismatch")
        _sha40(self.current_master, "current_master")
        _sha40(self.current_master_tree, "current_master_tree")
        if self.runtime_instance_id != RUNTIME_INSTANCE_ID:
            raise FleetRuntimeTrustContractError("receipt runtime instance mismatch")
        for name in (
            "config_digest",
            "verification_manifest_digest",
            "verifier_identity_digest",
            "verifier_implementation_digest",
            "verification_anchor_manifest_digest",
            "reconciliation_manifest_digest",
            "reconciliation_source_implementation_digest",
            "reconciliation_anchor_manifest_digest",
            "f005_h_pins_digest",
            "outputs_digest",
        ):
            _sha256(getattr(self, name), name)
        if type(self.asserts_verification_pass) is not bool or self.asserts_verification_pass:
            raise FleetRuntimeTrustContractError(
                "runtime trust receipt cannot assert verification PASS"
            )
        if type(self.asserts_fleet_closure) is not bool or self.asserts_fleet_closure:
            raise FleetRuntimeTrustContractError(
                "runtime trust receipt cannot assert fleet closure"
            )
        return self


def f005_h_pins_payload(
    verification: VerificationTrustPins,
    reconciliation: ReconciliationTrustPins,
) -> dict[str, Any]:
    if type(verification) is not VerificationTrustPins:
        raise FleetRuntimeTrustContractError("exact VerificationTrustPins required")
    if type(reconciliation) is not ReconciliationTrustPins:
        raise FleetRuntimeTrustContractError("exact ReconciliationTrustPins required")
    verification.validate()
    reconciliation.validate()
    payload = {
        "verification": asdict(verification),
        "reconciliation": asdict(reconciliation),
    }
    forbidden = {
        "verification_state",
        "verification_pass",
        "closable",
        "closure_state",
        "fleet_closure",
        "authority",
    }
    if forbidden.intersection(payload) or forbidden.intersection(payload["verification"]) or forbidden.intersection(payload["reconciliation"]):
        raise FleetRuntimeTrustContractError("pins payload contains forbidden claims")
    return payload

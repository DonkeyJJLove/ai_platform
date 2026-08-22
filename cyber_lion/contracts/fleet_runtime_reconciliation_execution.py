"""Contracts for one bounded F005-Q runtime reconciliation execution."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any

REPOSITORY = "DonkeyJJLove/ai_platform"
RUNTIME_SOURCE_INSTANCE_ID = "lion-runtime-reconciliation-source-01"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{name} invalid")
    return value.strip()


def _sha40(value: object, name: str) -> str:
    value = _text(value, name)
    if _SHA40.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase sha40")
    return value


def _sha256(value: object, name: str) -> str:
    value = _text(value, name)
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase sha256")
    return value


@dataclass(frozen=True)
class RuntimeReconciliationExecutionConfig:
    repository: str
    current_master: str
    current_master_tree: str
    source_instance: str = RUNTIME_SOURCE_INSTANCE_ID

    def validate(self) -> "RuntimeReconciliationExecutionConfig":
        if self.repository != REPOSITORY:
            raise ValueError("repository substitution denied")
        _sha40(self.current_master, "current_master")
        _sha40(self.current_master_tree, "current_master_tree")
        if _text(self.source_instance, "source_instance") != RUNTIME_SOURCE_INSTANCE_ID:
            raise ValueError("runtime reconciliation source substitution denied")
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(b"LION/F005-Q-CONFIG/1\0" + canonical_json(asdict(self))).hexdigest()


@dataclass(frozen=True)
class RuntimeReconciliationExecutionReceipt:
    schema_version: str
    repository: str
    current_master: str
    current_master_tree: str
    inventory_id: str
    inventory_revision: int
    inventory_digest: str
    closure_preconditions_digest: str
    report_id: str
    report_digest: str
    disposition: str
    convergence_receipt_digest: str | None
    execution_config_digest: str
    receipt_consumed: bool
    mission_closed: bool
    fleet_closed: bool
    release_performed: bool
    deploy_performed: bool
    execution_receipt_digest: str

    def payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("execution_receipt_digest")
        return value

    def validate(self) -> "RuntimeReconciliationExecutionReceipt":
        if self.schema_version != "1.0.0":
            raise ValueError("execution receipt schema mismatch")
        if self.repository != REPOSITORY:
            raise ValueError("execution receipt repository substitution denied")
        _sha40(self.current_master, "current_master")
        _sha40(self.current_master_tree, "current_master_tree")
        _text(self.inventory_id, "inventory_id")
        if isinstance(self.inventory_revision, bool) or not isinstance(self.inventory_revision, int) or self.inventory_revision < 1:
            raise ValueError("inventory_revision invalid")
        for name in ("inventory_digest", "closure_preconditions_digest", "report_digest", "execution_config_digest"):
            _sha256(getattr(self, name), name)
        _text(self.report_id, "report_id")
        if self.disposition not in {"CONVERGED", "RECONCILIATION_REQUIRED"}:
            raise ValueError("disposition invalid")
        if self.convergence_receipt_digest is not None:
            _sha256(self.convergence_receipt_digest, "convergence_receipt_digest")
        if self.disposition == "CONVERGED" and self.convergence_receipt_digest is None:
            raise ValueError("CONVERGED execution requires receipt digest")
        if self.disposition != "CONVERGED" and self.convergence_receipt_digest is not None:
            raise ValueError("non-converged execution cannot bind receipt digest")
        if any((self.receipt_consumed, self.mission_closed, self.fleet_closed, self.release_performed, self.deploy_performed)):
            raise ValueError("execution receipt asserts prohibited effect")
        expected = sha256(b"LION/F005-Q-EXECUTION-RECEIPT/1\0" + canonical_json(self.payload())).hexdigest()
        if self.execution_receipt_digest != expected:
            raise ValueError("execution receipt digest mismatch")
        return self

    @classmethod
    def build(cls, **values: object) -> "RuntimeReconciliationExecutionReceipt":
        payload = dict(values)
        digest = sha256(b"LION/F005-Q-EXECUTION-RECEIPT/1\0" + canonical_json(payload)).hexdigest()
        return cls(**payload, execution_receipt_digest=digest).validate()

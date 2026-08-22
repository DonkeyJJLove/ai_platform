"""Contracts for F005-Q strictly read-only runtime reconciliation preflight."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any

REPOSITORY = "DonkeyJJLove/ai_platform"
RUNTIME_SOURCE_INSTANCE_ID = "lion-runtime-reconciliation-source-01"
INVENTORY_STATES = frozenset({"CURRENT", "STALE", "MISSING", "CONFLICTING"})
RECONCILIATION_STATES = frozenset({
    "CLEAN_PRE_EXECUTION",
    "REPORT_ALREADY_PRESENT",
    "RECEIPT_ALREADY_PRESENT",
    "EXECUTION_ALREADY_RECORDED",
    "CONFLICTING",
})
NEXT_STEPS = frozenset({"RUN_F005_Q", "REFRESH_F005_J", "DENY"})
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha40(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase sha40")
    return value


def _sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase sha256")
    return value


@dataclass(frozen=True)
class RuntimeReconciliationPreflightConfig:
    repository: str
    current_master: str
    current_master_tree: str
    source_instance: str = RUNTIME_SOURCE_INSTANCE_ID

    def validate(self) -> "RuntimeReconciliationPreflightConfig":
        if self.repository != REPOSITORY:
            raise ValueError("repository substitution denied")
        _sha40(self.current_master, "current_master")
        _sha40(self.current_master_tree, "current_master_tree")
        if self.source_instance != RUNTIME_SOURCE_INSTANCE_ID:
            raise ValueError("runtime reconciliation source substitution denied")
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(b"LION/F005-Q-PREFLIGHT-CONFIG/1\0" + canonical_json(asdict(self))).hexdigest()


@dataclass(frozen=True)
class RuntimeReconciliationPreflightResult:
    schema_version: str
    repository: str
    current_master: str
    current_master_tree: str
    runtime_root: str
    required_sources_present: bool
    runtime_source_healthy: bool
    inventory_state: str
    reconciliation_state: str
    f005_q_admissible: bool
    next_step: str
    inventory_id: str | None
    inventory_revision: int | None
    inventory_digest: str | None
    inventory_default_head: str | None
    inventory_observed_at: str | None
    recorded_head_digest: str | None
    report_count: int | None
    receipt_count: int | None
    receipt_consumed_count: int | None
    execution_receipt_present: bool | None
    reconciliation_source_instance: str | None
    reconciliation_source_id: str | None
    reconciliation_source_implementation_digest: str | None
    reconciliation_trust_anchor_id: str | None
    status_stable: bool | None
    status_event_chain_valid: bool | None
    status_receipt_chain_valid: bool | None
    coordination_stable: bool | None
    coordination_event_chain_valid: bool | None
    reconciliation_stable: bool | None
    result_digest: str

    def payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("result_digest")
        return value

    def validate(self) -> "RuntimeReconciliationPreflightResult":
        if self.schema_version != "1.0.0":
            raise ValueError("preflight schema mismatch")
        if self.repository != REPOSITORY:
            raise ValueError("preflight repository substitution denied")
        _sha40(self.current_master, "current_master")
        _sha40(self.current_master_tree, "current_master_tree")
        if self.inventory_state not in INVENTORY_STATES:
            raise ValueError("inventory_state invalid")
        if self.reconciliation_state not in RECONCILIATION_STATES:
            raise ValueError("reconciliation_state invalid")
        if self.next_step not in NEXT_STEPS:
            raise ValueError("next_step invalid")
        if self.inventory_revision is not None and (
            isinstance(self.inventory_revision, bool)
            or not isinstance(self.inventory_revision, int)
            or self.inventory_revision < 1
        ):
            raise ValueError("inventory_revision invalid")
        for name in (
            "inventory_digest",
            "recorded_head_digest",
            "reconciliation_source_implementation_digest",
        ):
            value = getattr(self, name)
            if value is not None:
                _sha256(value, name)
        if self.inventory_default_head is not None:
            _sha40(self.inventory_default_head, "inventory_default_head")
        for name in ("report_count", "receipt_count", "receipt_consumed_count"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} invalid")
        derived_admissible = (
            self.required_sources_present
            and self.runtime_source_healthy
            and self.inventory_state == "CURRENT"
            and self.reconciliation_state == "CLEAN_PRE_EXECUTION"
            and self.execution_receipt_present is False
        )
        if self.f005_q_admissible != derived_admissible:
            raise ValueError("admissibility derivation mismatch")
        expected_next = (
            "RUN_F005_Q" if derived_admissible
            else "REFRESH_F005_J" if self.inventory_state in {"STALE", "MISSING"}
            else "DENY"
        )
        if self.next_step != expected_next:
            raise ValueError("next_step derivation mismatch")
        expected = sha256(b"LION/F005-Q-PREFLIGHT-RESULT/1\0" + canonical_json(self.payload())).hexdigest()
        if self.result_digest != expected:
            raise ValueError("preflight result digest mismatch")
        return self

    @classmethod
    def build(cls, **values: object) -> "RuntimeReconciliationPreflightResult":
        payload = dict(values)
        digest = sha256(b"LION/F005-Q-PREFLIGHT-RESULT/1\0" + canonical_json(payload)).hexdigest()
        return cls(**payload, result_digest=digest).validate()

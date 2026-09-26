"""Canonical fail-closed contract for one single-use bounded mutation admission."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

SCHEMA_ID = "lion.bounded-mutation-admission/v1"
RECEIPT_SCHEMA_ID = "lion.bounded-mutation-receipt/v1"

EFFECT_CLASS_CEILINGS = {
    "REPOSITORY_CONTENT_WRITE_BOUNDED": "BOUNDED_REPOSITORY",
    "REPOSITORY_REF_WRITE_BOUNDED": "BOUNDED_REPOSITORY",
    "PR_STATE_WRITE_BOUNDED": "BOUNDED_REPOSITORY",
    "MISSION_STATE_WRITE_BOUNDED": "CONTROL_STATE",
    "MISSION_DB_WRITE_BOUNDED": "CONTROL_STATE",
    "RUNTIME_DEPLOY_BOUNDED": "BOUNDED_MATERIAL",
    "RUNTIME_RESTART_BOUNDED": "BOUNDED_MATERIAL",
    "STATE_MIGRATION_BOUNDED": "BOUNDED_LOCAL",
    "ARCHIVE_WRITE_BOUNDED": "BOUNDED_LOCAL",
}
EFFECT_ORDER = {
    "NONE": 0,
    "CONTROL_STATE": 1,
    "BOUNDED_LOCAL": 2,
    "BOUNDED_REPOSITORY": 3,
    "BOUNDED_MATERIAL": 4,
}
REQUIRED_FIELDS = frozenset({
    "MUTATION_ADMISSION_ID", "PARENT_MISSION_ID", "PHASE_ID", "CHANGE_ID",
    "ACTOR_ROLE", "TARGET_OBJECT", "EXPECTED_PRE_STATE", "EXPECTED_POST_STATE",
    "ALLOWED_EFFECT_CLASS", "EFFECT_CEILING", "SOURCE_IDENTITY",
    "DEPENDENCY_SNAPSHOT", "ROLLBACK_PROCEDURE", "TEST_PROCEDURE",
    "READBACK_PROCEDURE", "EXPIRATION", "SINGLE_USE_NONCE",
})
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_NONCE = re.compile(r"^[A-Za-z0-9._:-]{24,160}$")


class MutationContractError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def parse_expiration(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MutationContractError("EXPIRATION must be UTC Z time")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MutationContractError("EXPIRATION invalid") from exc
    if parsed.tzinfo is None:
        raise MutationContractError("EXPIRATION timezone missing")
    return parsed.astimezone(timezone.utc)


def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise MutationContractError(f"{name} invalid")
    return value


def _hex(value: Any, pattern: re.Pattern[str], name: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise MutationContractError(f"{name} invalid")
    return value


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise MutationContractError(f"{name} must be non-empty object")
    return dict(value)


def _procedure(value: Any, name: str) -> dict[str, Any]:
    out = _mapping(value, name)
    if not isinstance(out.get("id"), str) or not out["id"].strip():
        raise MutationContractError(f"{name}.id required")
    return out


@dataclass(frozen=True)
class MutationAdmission:
    mutation_admission_id: str
    parent_mission_id: str
    phase_id: str
    change_id: str
    actor_role: str
    target_object: dict[str, Any]
    expected_pre_state: str
    expected_post_state: str
    allowed_effect_class: str
    effect_ceiling: str
    source_identity: dict[str, Any]
    dependency_snapshot: dict[str, Any]
    rollback_procedure: dict[str, Any]
    test_procedure: dict[str, Any]
    readback_procedure: dict[str, Any]
    expiration: str
    single_use_nonce: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MutationAdmission":
        if not isinstance(value, Mapping) or set(value) != REQUIRED_FIELDS:
            missing = sorted(REQUIRED_FIELDS - set(value or {}))
            extra = sorted(set(value or {}) - REQUIRED_FIELDS)
            raise MutationContractError(f"admission fields mismatch missing={missing} extra={extra}")
        effect = str(value["ALLOWED_EFFECT_CLASS"])
        if effect not in EFFECT_CLASS_CEILINGS:
            raise MutationContractError("ALLOWED_EFFECT_CLASS unknown")
        ceiling = str(value["EFFECT_CEILING"])
        if ceiling not in EFFECT_ORDER:
            raise MutationContractError("EFFECT_CEILING invalid")
        required_ceiling = EFFECT_CLASS_CEILINGS[effect]
        if EFFECT_ORDER[required_ceiling] > EFFECT_ORDER[ceiling]:
            raise MutationContractError("effect class exceeds EFFECT_CEILING")
        source = _mapping(value["SOURCE_IDENTITY"], "SOURCE_IDENTITY")
        if set(source) != {"source_head", "source_tree"}:
            raise MutationContractError("SOURCE_IDENTITY exact keys required")
        _hex(source["source_head"], _HEX40, "SOURCE_IDENTITY.source_head")
        _hex(source["source_tree"], _HEX40, "SOURCE_IDENTITY.source_tree")
        parse_expiration(str(value["EXPIRATION"]))
        nonce = str(value["SINGLE_USE_NONCE"])
        if _NONCE.fullmatch(nonce) is None:
            raise MutationContractError("SINGLE_USE_NONCE invalid")
        return cls(
            _id(value["MUTATION_ADMISSION_ID"], "MUTATION_ADMISSION_ID"),
            _id(value["PARENT_MISSION_ID"], "PARENT_MISSION_ID"),
            _id(value["PHASE_ID"], "PHASE_ID"),
            _id(value["CHANGE_ID"], "CHANGE_ID"),
            _id(value["ACTOR_ROLE"], "ACTOR_ROLE"),
            _mapping(value["TARGET_OBJECT"], "TARGET_OBJECT"),
            _hex(value["EXPECTED_PRE_STATE"], _HEX64, "EXPECTED_PRE_STATE"),
            _hex(value["EXPECTED_POST_STATE"], _HEX64, "EXPECTED_POST_STATE"),
            effect, ceiling, source,
            _mapping(value["DEPENDENCY_SNAPSHOT"], "DEPENDENCY_SNAPSHOT"),
            _procedure(value["ROLLBACK_PROCEDURE"], "ROLLBACK_PROCEDURE"),
            _procedure(value["TEST_PROCEDURE"], "TEST_PROCEDURE"),
            _procedure(value["READBACK_PROCEDURE"], "READBACK_PROCEDURE"),
            str(value["EXPIRATION"]), nonce,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "MUTATION_ADMISSION_ID": self.mutation_admission_id,
            "PARENT_MISSION_ID": self.parent_mission_id,
            "PHASE_ID": self.phase_id,
            "CHANGE_ID": self.change_id,
            "ACTOR_ROLE": self.actor_role,
            "TARGET_OBJECT": self.target_object,
            "EXPECTED_PRE_STATE": self.expected_pre_state,
            "EXPECTED_POST_STATE": self.expected_post_state,
            "ALLOWED_EFFECT_CLASS": self.allowed_effect_class,
            "EFFECT_CEILING": self.effect_ceiling,
            "SOURCE_IDENTITY": self.source_identity,
            "DEPENDENCY_SNAPSHOT": self.dependency_snapshot,
            "ROLLBACK_PROCEDURE": self.rollback_procedure,
            "TEST_PROCEDURE": self.test_procedure,
            "READBACK_PROCEDURE": self.readback_procedure,
            "EXPIRATION": self.expiration,
            "SINGLE_USE_NONCE": self.single_use_nonce,
        }

    @property
    def admission_digest(self) -> str:
        return digest({"schema": SCHEMA_ID, **self.as_dict()})


@dataclass(frozen=True)
class MutationReceipt:
    receipt_id: str
    mutation_admission_id: str
    admission_digest: str
    allowed_effect_class: str
    executor_id: str
    target_object_digest: str
    observed_pre_state: str
    observed_post_state: str
    effect_result_digest: str
    test_result_digest: str
    rollback_result_digest: str | None
    status: str
    observed_at: str

    def as_dict(self) -> dict[str, Any]:
        value = {
            "schema": RECEIPT_SCHEMA_ID,
            "receipt_id": self.receipt_id,
            "mutation_admission_id": self.mutation_admission_id,
            "admission_digest": self.admission_digest,
            "allowed_effect_class": self.allowed_effect_class,
            "executor_id": self.executor_id,
            "target_object_digest": self.target_object_digest,
            "observed_pre_state": self.observed_pre_state,
            "observed_post_state": self.observed_post_state,
            "effect_result_digest": self.effect_result_digest,
            "test_result_digest": self.test_result_digest,
            "rollback_result_digest": self.rollback_result_digest,
            "status": self.status,
            "observed_at": self.observed_at,
            "receipt_is_evidence_not_authority": True,
        }
        value["receipt_digest"] = digest(value)
        return value

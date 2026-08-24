"""Bounded repository-maintenance sandbox contracts for exact branch-ref cleanup."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping

REPOSITORY = "DonkeyJJLove/ai_platform"
SCHEMA_VERSION = "1.0.0"
ALLOWED_ACTIONS = frozenset({
    "READ_BRANCH_REF",
    "COMPARE_BRANCH_TO_MASTER",
    "CHECK_BRANCH_PR_STATE",
    "CHECK_BRANCH_OWNERSHIP",
    "DELETE_BRANCH_REF",
})
DELETE_CLASSIFICATIONS = frozenset({"A", "B"})
OUTCOMES = frozenset({"SUCCEEDED", "DENIED", "ABORTED", "ALREADY_ABSENT"})
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OP_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_BRANCH = re.compile(r"^(?:docs|mission)/[A-Za-z0-9._/-]{1,220}$")


class RepositoryMaintenanceContractError(ValueError):
    pass


def canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RepositoryMaintenanceContractError("value is not strict JSON") from exc


def digest(value: object, domain: bytes) -> str:
    return sha256(domain + canonical_json(value)).hexdigest()


def _sha40(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise RepositoryMaintenanceContractError(f"{name} must be lowercase sha40")
    return value


def _sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise RepositoryMaintenanceContractError(f"{name} must be sha256")
    return value


def validate_branch_name(branch: str) -> str:
    if not isinstance(branch, str) or _BRANCH.fullmatch(branch) is None:
        raise RepositoryMaintenanceContractError("branch outside cleanup allowlist")
    if branch in {"master", "main"} or branch.startswith("refs/"):
        raise RepositoryMaintenanceContractError("protected or non-canonical branch denied")
    if ".." in branch or "//" in branch or branch.endswith("/") or branch.startswith("-"):
        raise RepositoryMaintenanceContractError("unsafe branch name denied")
    return branch


@dataclass(frozen=True)
class RepositoryMaintenanceOperation:
    schema_version: str
    repository: str
    mission_id: str
    drone_id: str
    operation_id: str
    dispatch_id: str
    fencing_token: int
    generation: int
    protected_master_sha: str
    branch_name: str
    expected_branch_head: str
    ancestry_evidence_digest: str
    pr_state_evidence_digest: str
    ownership_evidence_digest: str
    classification_digest: str
    classification: str
    requested_effect: str
    policy_digest: str

    def validate(self) -> "RepositoryMaintenanceOperation":
        if self.schema_version != SCHEMA_VERSION or self.repository != REPOSITORY:
            raise RepositoryMaintenanceContractError("operation identity invalid")
        for name, value in (
            ("mission_id", self.mission_id),
            ("drone_id", self.drone_id),
            ("operation_id", self.operation_id),
            ("dispatch_id", self.dispatch_id),
        ):
            if not isinstance(value, str) or _OP_ID.fullmatch(value) is None:
                raise RepositoryMaintenanceContractError(f"{name} invalid")
        if isinstance(self.fencing_token, bool) or not isinstance(self.fencing_token, int) or self.fencing_token < 1:
            raise RepositoryMaintenanceContractError("fencing_token invalid")
        if isinstance(self.generation, bool) or not isinstance(self.generation, int) or self.generation < 1:
            raise RepositoryMaintenanceContractError("generation invalid")
        _sha40(self.protected_master_sha, "protected_master_sha")
        validate_branch_name(self.branch_name)
        _sha40(self.expected_branch_head, "expected_branch_head")
        for name, value in (
            ("ancestry_evidence_digest", self.ancestry_evidence_digest),
            ("pr_state_evidence_digest", self.pr_state_evidence_digest),
            ("ownership_evidence_digest", self.ownership_evidence_digest),
            ("classification_digest", self.classification_digest),
            ("policy_digest", self.policy_digest),
        ):
            _sha256(value, name)
        if self.classification not in DELETE_CLASSIFICATIONS:
            raise RepositoryMaintenanceContractError("classification not deletion eligible")
        if self.requested_effect != "DELETE_EXACT_REF":
            raise RepositoryMaintenanceContractError("requested effect invalid")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    def operation_digest(self) -> str:
        return digest(self.canonical_dict(), b"LION/REPOSITORY-MAINTENANCE-OP/1\0")


@dataclass(frozen=True)
class RepositoryMaintenancePolicy:
    schema_version: str
    repository: str
    mission_id: str
    protected_ref: str
    allowed_prefixes: tuple[str, ...]
    max_deletions: int
    authority_effect: bool = False
    master_effect: bool = False

    def validate(self) -> "RepositoryMaintenancePolicy":
        if self.schema_version != SCHEMA_VERSION or self.repository != REPOSITORY:
            raise RepositoryMaintenanceContractError("policy identity invalid")
        if not isinstance(self.mission_id, str) or _OP_ID.fullmatch(self.mission_id) is None:
            raise RepositoryMaintenanceContractError("mission_id invalid")
        if self.protected_ref != "master":
            raise RepositoryMaintenanceContractError("protected ref must be master")
        if self.allowed_prefixes != ("docs/", "mission/"):
            raise RepositoryMaintenanceContractError("branch allowlist substitution denied")
        if isinstance(self.max_deletions, bool) or not isinstance(self.max_deletions, int) or not (1 <= self.max_deletions <= 100):
            raise RepositoryMaintenanceContractError("max_deletions invalid")
        if self.authority_effect is not False or self.master_effect is not False:
            raise RepositoryMaintenanceContractError("policy cannot mint authority or master effect")
        return self

    def digest(self) -> str:
        self.validate()
        return digest(asdict(self), b"LION/REPOSITORY-MAINTENANCE-POLICY/1\0")


@dataclass(frozen=True)
class RepositoryMaintenanceExecutionReceipt:
    schema_version: str
    receipt_id: str
    operation_id: str
    operation_digest: str
    policy_digest: str
    mission_id: str
    drone_id: str
    dispatch_id: str
    fencing_token: int
    generation: int
    repository: str
    master_sha_before: str
    master_sha_after: str
    branch_name: str
    branch_head_before: str
    branch_exists_after: bool
    effect: str
    outcome: str
    observed_event_refs: tuple[str, ...]
    authority_effect: bool
    master_effect: bool
    receipt_digest: str

    def payload_without_digest(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("receipt_digest")
        return value

    def validate(self) -> "RepositoryMaintenanceExecutionReceipt":
        if self.schema_version != SCHEMA_VERSION or self.repository != REPOSITORY:
            raise RepositoryMaintenanceContractError("receipt identity invalid")
        for name, value in (
            ("receipt_id", self.receipt_id),
            ("operation_id", self.operation_id),
            ("mission_id", self.mission_id),
            ("drone_id", self.drone_id),
            ("dispatch_id", self.dispatch_id),
        ):
            if not isinstance(value, str) or _OP_ID.fullmatch(value) is None:
                raise RepositoryMaintenanceContractError(f"{name} invalid")
        for name, value in (
            ("operation_digest", self.operation_digest),
            ("policy_digest", self.policy_digest),
            ("receipt_digest", self.receipt_digest),
        ):
            _sha256(value, name)
        _sha40(self.master_sha_before, "master_sha_before")
        _sha40(self.master_sha_after, "master_sha_after")
        validate_branch_name(self.branch_name)
        _sha40(self.branch_head_before, "branch_head_before")
        if not isinstance(self.branch_exists_after, bool):
            raise RepositoryMaintenanceContractError("branch_exists_after invalid")
        if self.effect != "DELETE_BRANCH_REF" or self.outcome not in OUTCOMES:
            raise RepositoryMaintenanceContractError("receipt effect/outcome invalid")
        if type(self.observed_event_refs) is not tuple or not self.observed_event_refs:
            raise RepositoryMaintenanceContractError("observed evidence required")
        if self.authority_effect is not False or self.master_effect is not False:
            raise RepositoryMaintenanceContractError("receipt cannot report authority/master effect")
        expected = digest(self.payload_without_digest(), b"LION/REPOSITORY-MAINTENANCE-RECEIPT/1\0")
        if self.receipt_digest != expected:
            raise RepositoryMaintenanceContractError("receipt digest mismatch")
        return self

    @classmethod
    def build(cls, **values: Any) -> "RepositoryMaintenanceExecutionReceipt":
        raw = dict(values)
        raw["receipt_digest"] = "0" * 64
        provisional = cls(**raw)
        final = cls(**{**raw, "receipt_digest": digest(provisional.payload_without_digest(), b"LION/REPOSITORY-MAINTENANCE-RECEIPT/1\0")})
        return final.validate()


def evidence_digest(value: Mapping[str, Any], label: str) -> str:
    if not isinstance(label, str) or not label:
        raise RepositoryMaintenanceContractError("evidence label invalid")
    return digest(dict(value), ("LION/REPOSITORY-MAINTENANCE-EVIDENCE/" + label + "/1\0").encode())

"""Immutable contracts for F005-E fleet observability reconciliation.

These objects describe repository observations, deterministic branch classification,
explicit closure preconditions, and one-shot convergence evidence. They grant no
repository authority, merge permission, deployment permission, lease, or execution
capability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Tuple

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPO = re.compile(r"^[^/\s]+/[^/\s]+$")

BRANCH_CLASSES = frozenset({
    "ACTIVE_MISSION",
    "ALREADY_INTEGRATED",
    "SUPERSEDED",
    "MERGE_CANDIDATE",
    "PORT_REQUIRED",
    "FOREIGN_HISTORY",
    "UNCLASSIFIED",
})
CONVERGED_BRANCH_CLASSES = frozenset({"ALREADY_INTEGRATED", "SUPERSEDED"})
OWNERSHIP_STATES = frozenset({"ACTIVE", "TERMINAL", "UNOWNED", "UNKNOWN"})
ANCESTRY_STATES = frozenset({
    "IDENTICAL",
    "HEAD_ANCESTOR_OF_DEFAULT",
    "DEFAULT_ANCESTOR_OF_HEAD",
    "DIVERGED",
    "NO_COMMON_ANCESTOR",
    "UNKNOWN",
})
EPISTEMIC_CLASSES = frozenset({"OBSERVED", "ANCHORED", "INFERRED", "UNKNOWN"})
RECONCILIATION_DISPOSITIONS = frozenset({
    "CONVERGED", "RECONCILIATION_REQUIRED", "STOP_REPLAN_REQUIRED",
})
RATIONALE_CODES = frozenset({
    "ACTIVE_MISSION_OWNS_BRANCH",
    "UNOWNED_BRANCH",
    "UNKNOWN_BRANCH_OWNERSHIP",
    "HEAD_ALREADY_IN_DEFAULT_HISTORY",
    "EXPLICIT_SUCCESSOR_SUPERSEDES_BRANCH",
    "BRANCH_AHEAD_OF_CURRENT_DEFAULT",
    "BRANCH_DIVERGED_FROM_CURRENT_DEFAULT",
    "NO_COMMON_ANCESTOR",
    "INSUFFICIENT_TRUSTED_EVIDENCE",
})
ANOMALY_CODES = frozenset({
    "ACTIVE_MISSION",
    "UNOWNED_BRANCH",
    "UNKNOWN_BRANCH_OWNERSHIP",
    "BASELINE_DRIFT",
    "EMPTY_INVENTORY",
    "FOREIGN_HISTORY",
    "MERGE_CANDIDATE",
    "PORT_REQUIRED",
    "UNCLASSIFIED_BRANCH",
    "UNKNOWN_MISSION",
    "UNKNOWN_RESULT",
    "UNRESOLVED_WRITE_LEASE",
    "UNRECONCILED_EFFECT",
    "RECONCILIATION_DISAGREEMENT",
    "CLOSURE_EVIDENCE_UNTRUSTED",
})
RECEIPT_PURPOSE = "MISSION_CLOSE_EVIDENCE_ONLY"


class FleetReconciliationContractError(ValueError):
    """Raised when reconciliation evidence is malformed, ambiguous, or overclaims."""


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: Any, name: str, *, optional: bool = False, limit: int = 4096) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise FleetReconciliationContractError(f"{name} is invalid")
    return value


def _sha40(value: Any, name: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    value = _text(value, name, limit=40)
    assert isinstance(value, str)
    if not _SHA40.fullmatch(value):
        raise FleetReconciliationContractError(f"{name} must be a full lowercase git SHA")
    return value


def _sha256(value: Any, name: str) -> str:
    value = _text(value, name, limit=64)
    assert isinstance(value, str)
    if not _SHA256.fullmatch(value):
        raise FleetReconciliationContractError(f"{name} must be sha256 hex")
    return value


def _enum(value: Any, name: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise FleetReconciliationContractError(f"{name} is invalid")
    return value


def _utc(value: Any, name: str) -> datetime:
    value = _text(value, name)
    assert isinstance(value, str)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FleetReconciliationContractError(f"{name} is invalid") from exc
    if parsed.tzinfo is None:
        raise FleetReconciliationContractError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _count(value: Any, name: str, *, optional: bool = False) -> int | None:
    if optional and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FleetReconciliationContractError(f"{name} is invalid")
    return value


def _string_tuple(value: Any, name: str, *, nonempty: bool = False) -> Tuple[str, ...]:
    if type(value) is not tuple:
        raise FleetReconciliationContractError(f"{name} must be a tuple")
    if nonempty and not value:
        raise FleetReconciliationContractError(f"{name} must be non-empty")
    for item in value:
        _text(item, name)
    if len(value) != len(set(value)):
        raise FleetReconciliationContractError(f"{name} must contain unique values")
    return value


@dataclass(frozen=True)
class ReconciliationTrustPins:
    source_id: str
    source_instance_id: str
    source_implementation_digest: str
    trust_anchor_id: str

    def validate(self) -> "ReconciliationTrustPins":
        _text(self.source_id, "source_id")
        _text(self.source_instance_id, "source_instance_id")
        _sha256(self.source_implementation_digest, "source_implementation_digest")
        _text(self.trust_anchor_id, "trust_anchor_id")
        return self

    def binding(self) -> tuple[str, str, str, str]:
        self.validate()
        return (
            self.source_id,
            self.source_instance_id,
            self.source_implementation_digest,
            self.trust_anchor_id,
        )


@dataclass(frozen=True)
class BranchEvidence:
    repository: str
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
    evidence_digest: str

    def validate(self) -> "BranchEvidence":
        if not isinstance(self.repository, str) or not _REPO.fullmatch(self.repository):
            raise FleetReconciliationContractError("repository must use owner/name form")
        _text(self.branch, "branch")
        if self.branch.startswith("refs/"):
            raise FleetReconciliationContractError("branch must be a repository branch name")
        _sha40(self.branch_head_sha, "branch_head_sha")
        _text(self.mission_id, "mission_id", optional=True)
        _sha40(self.baseline_sha, "baseline_sha", optional=True)
        _enum(self.ownership_state, "ownership_state", OWNERSHIP_STATES)
        _enum(self.ancestry_state, "ancestry_state", ANCESTRY_STATES)
        _enum(self.epistemic_class, "epistemic_class", EPISTEMIC_CLASSES)
        _text(self.source_provenance_ref, "source_provenance_ref")
        _utc(self.observed_at, "observed_at")
        _sha256(self.evidence_digest, "evidence_digest")

        if self.ownership_state in {"ACTIVE", "TERMINAL"} and (
            self.mission_id is None or self.baseline_sha is None
        ):
            raise FleetReconciliationContractError("mission-owned branch requires mission_id and baseline_sha")
        if self.ownership_state == "UNOWNED" and self.mission_id is not None:
            raise FleetReconciliationContractError("unowned branch cannot claim mission ownership")

        supersession = (self.superseded_by_branch, self.supersession_provenance_ref)
        if (supersession[0] is None) != (supersession[1] is None):
            raise FleetReconciliationContractError("supersession evidence must be complete")
        if self.superseded_by_branch is not None:
            _text(self.superseded_by_branch, "superseded_by_branch")
            _text(self.supersession_provenance_ref, "supersession_provenance_ref")
            if self.superseded_by_branch == self.branch:
                raise FleetReconciliationContractError("branch cannot supersede itself")

        ahead = _count(self.ahead_by, "ahead_by", optional=True)
        behind = _count(self.behind_by, "behind_by", optional=True)
        if self.ancestry_state == "IDENTICAL":
            if ahead != 0 or behind != 0:
                raise FleetReconciliationContractError("IDENTICAL ancestry requires zero ahead/behind")
        elif self.ancestry_state == "HEAD_ANCESTOR_OF_DEFAULT":
            if ahead != 0 or behind is None or behind <= 0:
                raise FleetReconciliationContractError("HEAD_ANCESTOR_OF_DEFAULT counts are inconsistent")
        elif self.ancestry_state == "DEFAULT_ANCESTOR_OF_HEAD":
            if ahead is None or ahead <= 0 or behind != 0:
                raise FleetReconciliationContractError("DEFAULT_ANCESTOR_OF_HEAD counts are inconsistent")
        elif self.ancestry_state == "DIVERGED":
            if ahead is None or behind is None or ahead <= 0 or behind <= 0:
                raise FleetReconciliationContractError("DIVERGED ancestry requires positive ahead/behind")
        elif self.ancestry_state in {"NO_COMMON_ANCESTOR", "UNKNOWN"}:
            if ahead is not None or behind is not None:
                raise FleetReconciliationContractError("unknown/foreign ancestry cannot carry ahead/behind counts")

        if self.evidence_digest != self.recompute_digest():
            raise FleetReconciliationContractError("branch evidence digest mismatch")
        return self

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value = asdict(self)
        if not include_digest:
            value.pop("evidence_digest")
        return value

    def recompute_digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict(include_digest=False))).hexdigest()

    @classmethod
    def build(cls, **values: Any) -> "BranchEvidence":
        raw = dict(values)
        raw["evidence_digest"] = "0" * 64
        provisional = cls(**raw)
        return cls(**{**values, "evidence_digest": provisional.recompute_digest()}).validate()


@dataclass(frozen=True)
class RepositoryInventory:
    schema_version: str
    inventory_id: str
    inventory_revision: int
    repository: str
    default_branch: str
    default_head_sha: str
    source_id: str
    source_instance_id: str
    source_implementation_digest: str
    trust_anchor_id: str
    observed_at: str
    branches: Tuple[BranchEvidence, ...]
    inventory_digest: str

    def validate(self) -> "RepositoryInventory":
        if self.schema_version != "1.0.0":
            raise FleetReconciliationContractError("unsupported inventory schema_version")
        _text(self.inventory_id, "inventory_id")
        if isinstance(self.inventory_revision, bool) or not isinstance(self.inventory_revision, int) or self.inventory_revision < 1:
            raise FleetReconciliationContractError("inventory_revision must be positive")
        if not isinstance(self.repository, str) or not _REPO.fullmatch(self.repository):
            raise FleetReconciliationContractError("repository must use owner/name form")
        _text(self.default_branch, "default_branch")
        _sha40(self.default_head_sha, "default_head_sha")
        self.source_pins().validate()
        observed = _utc(self.observed_at, "observed_at")
        if type(self.branches) is not tuple:
            raise FleetReconciliationContractError("branches must be a tuple")
        names: list[str] = []
        for item in self.branches:
            if type(item) is not BranchEvidence:
                raise FleetReconciliationContractError("inventory branch evidence type is invalid")
            item.validate()
            if item.repository != self.repository:
                raise FleetReconciliationContractError("branch repository does not bind inventory repository")
            if item.branch == self.default_branch:
                raise FleetReconciliationContractError("default branch must not be classified as mission branch")
            if _utc(item.observed_at, "branch observed_at") > observed:
                raise FleetReconciliationContractError("branch evidence cannot be newer than inventory")
            names.append(item.branch)
        if len(names) != len(set(names)):
            raise FleetReconciliationContractError("inventory contains duplicate branches")
        if tuple(names) != tuple(sorted(names)):
            raise FleetReconciliationContractError("branches must be sorted for deterministic inventory")
        _sha256(self.inventory_digest, "inventory_digest")
        if self.inventory_digest != self.recompute_digest():
            raise FleetReconciliationContractError("inventory digest mismatch")
        return self

    def source_pins(self) -> ReconciliationTrustPins:
        return ReconciliationTrustPins(
            self.source_id,
            self.source_instance_id,
            self.source_implementation_digest,
            self.trust_anchor_id,
        )

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value = asdict(self)
        value["branches"] = [item.canonical_dict() for item in self.branches]
        if not include_digest:
            value.pop("inventory_digest")
        return value

    def recompute_digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict(include_digest=False))).hexdigest()

    @classmethod
    def build(cls, **values: Any) -> "RepositoryInventory":
        raw = dict(values)
        raw["branches"] = tuple(sorted(tuple(raw.get("branches", ())), key=lambda item: item.branch))
        raw["inventory_digest"] = "0" * 64
        provisional = cls(**raw)
        digest = provisional.recompute_digest()
        return cls(**{**raw, "inventory_digest": digest}).validate()


@dataclass(frozen=True)
class ClosurePreconditions:
    """Externally observed blockers required by the fleet closure policy."""

    repository: str
    inventory_digest: str
    active_unknown_mission_count: int
    unknown_result_count: int
    unresolved_write_lease_count: int
    unreconciled_effect_count: int
    reconciliation_disagreement_count: int
    source_provenance_refs: Tuple[str, ...]
    epistemic_class: str
    observed_at: str
    preconditions_digest: str

    def validate(self) -> "ClosurePreconditions":
        if not isinstance(self.repository, str) or not _REPO.fullmatch(self.repository):
            raise FleetReconciliationContractError("repository must use owner/name form")
        _sha256(self.inventory_digest, "inventory_digest")
        for name in (
            "active_unknown_mission_count",
            "unknown_result_count",
            "unresolved_write_lease_count",
            "unreconciled_effect_count",
            "reconciliation_disagreement_count",
        ):
            _count(getattr(self, name), name)
        _string_tuple(self.source_provenance_refs, "source_provenance_refs", nonempty=True)
        _enum(self.epistemic_class, "epistemic_class", EPISTEMIC_CLASSES)
        _utc(self.observed_at, "observed_at")
        _sha256(self.preconditions_digest, "preconditions_digest")
        if self.preconditions_digest != self.recompute_digest():
            raise FleetReconciliationContractError("closure preconditions digest mismatch")
        return self

    def blocker_codes(self) -> Tuple[str, ...]:
        self.validate()
        blockers: list[str] = []
        if self.epistemic_class not in {"OBSERVED", "ANCHORED"}:
            blockers.append("CLOSURE_EVIDENCE_UNTRUSTED")
        if self.active_unknown_mission_count:
            blockers.append("UNKNOWN_MISSION")
        if self.unknown_result_count:
            blockers.append("UNKNOWN_RESULT")
        if self.unresolved_write_lease_count:
            blockers.append("UNRESOLVED_WRITE_LEASE")
        if self.unreconciled_effect_count:
            blockers.append("UNRECONCILED_EFFECT")
        if self.reconciliation_disagreement_count:
            blockers.append("RECONCILIATION_DISAGREEMENT")
        return tuple(blockers)

    def satisfied(self) -> bool:
        return not self.blocker_codes()

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value = asdict(self)
        value["source_provenance_refs"] = list(self.source_provenance_refs)
        if not include_digest:
            value.pop("preconditions_digest")
        return value

    def recompute_digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict(include_digest=False))).hexdigest()

    @classmethod
    def build(cls, **values: Any) -> "ClosurePreconditions":
        raw = dict(values)
        raw["source_provenance_refs"] = tuple(raw.get("source_provenance_refs", ()))
        raw["preconditions_digest"] = "0" * 64
        provisional = cls(**raw)
        return cls(**{**raw, "preconditions_digest": provisional.recompute_digest()}).validate()


@dataclass(frozen=True)
class BranchReconciliation:
    repository: str
    inventory_digest: str
    branch: str
    branch_head_sha: str
    mission_id: str | None
    baseline_sha: str | None
    classification: str
    rationale_code: str
    evidence_digest: str
    observed_at: str

    def validate(self) -> "BranchReconciliation":
        if not isinstance(self.repository, str) or not _REPO.fullmatch(self.repository):
            raise FleetReconciliationContractError("repository must use owner/name form")
        _sha256(self.inventory_digest, "inventory_digest")
        _text(self.branch, "branch")
        _sha40(self.branch_head_sha, "branch_head_sha")
        _text(self.mission_id, "mission_id", optional=True)
        _sha40(self.baseline_sha, "baseline_sha", optional=True)
        _enum(self.classification, "classification", BRANCH_CLASSES)
        _enum(self.rationale_code, "rationale_code", RATIONALE_CODES)
        _sha256(self.evidence_digest, "evidence_digest")
        _utc(self.observed_at, "observed_at")
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(canonical_json(asdict(self))).hexdigest()


@dataclass(frozen=True)
class ReconciliationReport:
    schema_version: str
    report_id: str
    repository: str
    inventory_id: str
    inventory_revision: int
    inventory_digest: str
    default_head_sha: str
    closure_preconditions: ClosurePreconditions
    closure_preconditions_digest: str
    observed_at: str
    disposition: str
    anomaly_codes: Tuple[str, ...]
    branches: Tuple[BranchReconciliation, ...]
    report_digest: str

    def validate(self) -> "ReconciliationReport":
        if self.schema_version != "1.0.0":
            raise FleetReconciliationContractError("unsupported report schema_version")
        _text(self.report_id, "report_id")
        if not isinstance(self.repository, str) or not _REPO.fullmatch(self.repository):
            raise FleetReconciliationContractError("repository must use owner/name form")
        _text(self.inventory_id, "inventory_id")
        if isinstance(self.inventory_revision, bool) or not isinstance(self.inventory_revision, int) or self.inventory_revision < 1:
            raise FleetReconciliationContractError("inventory_revision must be positive")
        _sha256(self.inventory_digest, "inventory_digest")
        _sha40(self.default_head_sha, "default_head_sha")
        if type(self.closure_preconditions) is not ClosurePreconditions:
            raise FleetReconciliationContractError("closure_preconditions must use exact contract type")
        self.closure_preconditions.validate()
        if (
            self.closure_preconditions.repository != self.repository
            or self.closure_preconditions.inventory_digest != self.inventory_digest
        ):
            raise FleetReconciliationContractError("closure preconditions do not bind report inventory")
        _sha256(self.closure_preconditions_digest, "closure_preconditions_digest")
        if self.closure_preconditions_digest != self.closure_preconditions.preconditions_digest:
            raise FleetReconciliationContractError("closure preconditions digest binding mismatch")
        _utc(self.observed_at, "observed_at")
        _enum(self.disposition, "disposition", RECONCILIATION_DISPOSITIONS)
        _string_tuple(self.anomaly_codes, "anomaly_codes")
        if tuple(self.anomaly_codes) != tuple(sorted(self.anomaly_codes)):
            raise FleetReconciliationContractError("anomaly_codes must be sorted")
        for code in self.anomaly_codes:
            _enum(code, "anomaly_code", ANOMALY_CODES)

        required_blockers = set(self.closure_preconditions.blocker_codes())
        if not required_blockers.issubset(set(self.anomaly_codes)):
            raise FleetReconciliationContractError("closure blocker anomalies are incomplete")

        if type(self.branches) is not tuple:
            raise FleetReconciliationContractError("branches must be a tuple")
        names: list[str] = []
        for item in self.branches:
            if type(item) is not BranchReconciliation:
                raise FleetReconciliationContractError("report branch type is invalid")
            item.validate()
            if item.repository != self.repository or item.inventory_digest != self.inventory_digest:
                raise FleetReconciliationContractError("branch reconciliation does not bind report")
            names.append(item.branch)
        if len(names) != len(set(names)):
            raise FleetReconciliationContractError("report contains duplicate branches")
        if tuple(names) != tuple(sorted(names)):
            raise FleetReconciliationContractError("report branches must be sorted")

        all_converged = bool(self.branches) and all(
            item.classification in CONVERGED_BRANCH_CLASSES for item in self.branches
        )
        closure_ready = self.closure_preconditions.satisfied()
        if self.disposition == "CONVERGED" and not (all_converged and closure_ready):
            raise FleetReconciliationContractError(
                "CONVERGED report requires converged branches and satisfied closure preconditions"
            )
        if self.disposition == "STOP_REPLAN_REQUIRED" and "BASELINE_DRIFT" not in self.anomaly_codes:
            raise FleetReconciliationContractError("STOP_REPLAN_REQUIRED requires BASELINE_DRIFT")
        if self.disposition == "RECONCILIATION_REQUIRED" and all_converged and closure_ready:
            raise FleetReconciliationContractError(
                "fully converged report with satisfied closure preconditions cannot require reconciliation"
            )

        _sha256(self.report_digest, "report_digest")
        if self.report_digest != self.recompute_digest():
            raise FleetReconciliationContractError("report digest mismatch")
        return self

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value = asdict(self)
        value["closure_preconditions"] = self.closure_preconditions.canonical_dict()
        value["anomaly_codes"] = list(self.anomaly_codes)
        value["branches"] = [asdict(item) for item in self.branches]
        if not include_digest:
            value.pop("report_digest")
        return value

    def recompute_digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict(include_digest=False))).hexdigest()

    @classmethod
    def build(cls, **values: Any) -> "ReconciliationReport":
        raw = dict(values)
        raw["anomaly_codes"] = tuple(sorted(tuple(raw.get("anomaly_codes", ()))))
        raw["branches"] = tuple(sorted(tuple(raw.get("branches", ())), key=lambda item: item.branch))
        raw["report_digest"] = "0" * 64
        provisional = cls(**raw)
        digest = provisional.recompute_digest()
        return cls(**{**raw, "report_digest": digest}).validate()


@dataclass(frozen=True)
class ConvergenceReceipt:
    schema_version: str
    receipt_id: str
    repository: str
    inventory_id: str
    inventory_revision: int
    inventory_digest: str
    report_id: str
    report_digest: str
    closure_preconditions_digest: str
    default_head_sha: str
    issued_at: str
    purpose: str
    receipt_digest: str

    def validate(self) -> "ConvergenceReceipt":
        if self.schema_version != "1.0.0":
            raise FleetReconciliationContractError("unsupported receipt schema_version")
        _text(self.receipt_id, "receipt_id")
        if not isinstance(self.repository, str) or not _REPO.fullmatch(self.repository):
            raise FleetReconciliationContractError("repository must use owner/name form")
        _text(self.inventory_id, "inventory_id")
        if isinstance(self.inventory_revision, bool) or not isinstance(self.inventory_revision, int) or self.inventory_revision < 1:
            raise FleetReconciliationContractError("inventory_revision must be positive")
        _sha256(self.inventory_digest, "inventory_digest")
        _text(self.report_id, "report_id")
        _sha256(self.report_digest, "report_digest")
        _sha256(self.closure_preconditions_digest, "closure_preconditions_digest")
        _sha40(self.default_head_sha, "default_head_sha")
        _utc(self.issued_at, "issued_at")
        if self.purpose != RECEIPT_PURPOSE:
            raise FleetReconciliationContractError("convergence receipt purpose cannot grant execution authority")
        _sha256(self.receipt_digest, "receipt_digest")
        if self.receipt_digest != self.recompute_digest():
            raise FleetReconciliationContractError("convergence receipt digest mismatch")
        return self

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value = asdict(self)
        if not include_digest:
            value.pop("receipt_digest")
        return value

    def recompute_digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict(include_digest=False))).hexdigest()

    @classmethod
    def build(cls, **values: Any) -> "ConvergenceReceipt":
        raw = dict(values)
        raw["purpose"] = RECEIPT_PURPOSE
        raw["receipt_digest"] = "0" * 64
        provisional = cls(**raw)
        return cls(**{**raw, "receipt_digest": provisional.recompute_digest()}).validate()

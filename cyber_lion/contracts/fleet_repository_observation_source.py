"""Contracts for F005-K read-only live repository observation production."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import PureWindowsPath
import re
from typing import Any, Mapping, Tuple

REPOSITORY = "DonkeyJJLove/ai_platform"
DEFAULT_BRANCH = "master"
OUTPUT_PATH = r"C:\LION\runtime\f005\reconciliation-source\repository-inventory.json"
_SCHEMA_VERSION = "1.0.0"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_OWNERSHIP = frozenset({"ACTIVE", "TERMINAL", "UNOWNED", "UNKNOWN"})
_ANCESTRY = frozenset({"IDENTICAL", "HEAD_ANCESTOR_OF_DEFAULT", "DEFAULT_ANCESTOR_OF_HEAD", "DIVERGED", "NO_COMMON_ANCESTOR", "UNKNOWN"})
_EPISTEMIC = frozenset({"OBSERVED", "ANCHORED"})


class RepositoryObservationContractError(ValueError):
    pass


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: object, name: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise RepositoryObservationContractError(f"{name} invalid")
    return value


def _sha40(value: object, name: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    value = _text(value, name)
    assert isinstance(value, str)
    if not _SHA40.fullmatch(value):
        raise RepositoryObservationContractError(f"{name} must be full lowercase git SHA")
    return value


@dataclass(frozen=True)
class ObservationConfig:
    repository: str
    expected_master: str
    expected_master_tree: str
    inventory_revision: int
    default_branch: str = DEFAULT_BRANCH
    output_path: str = OUTPUT_PATH

    def validate(self) -> "ObservationConfig":
        if self.repository != REPOSITORY:
            raise RepositoryObservationContractError("repository substitution denied")
        if self.default_branch != DEFAULT_BRANCH:
            raise RepositoryObservationContractError("default branch substitution denied")
        _sha40(self.expected_master, "expected_master")
        _sha40(self.expected_master_tree, "expected_master_tree")
        if isinstance(self.inventory_revision, bool) or not isinstance(self.inventory_revision, int) or self.inventory_revision < 1:
            raise RepositoryObservationContractError("inventory_revision invalid")
        path = PureWindowsPath(self.output_path)
        if not path.is_absolute() or path != PureWindowsPath(OUTPUT_PATH):
            raise RepositoryObservationContractError("output path substitution denied")
        return self


@dataclass(frozen=True)
class LiveBranch:
    branch: str
    head_sha: str

    def validate(self) -> "LiveBranch":
        _text(self.branch, "branch")
        if self.branch.startswith("refs/"):
            raise RepositoryObservationContractError("branch must be repository branch name")
        _sha40(self.head_sha, "head_sha")
        return self


@dataclass(frozen=True)
class OwnershipEvidence:
    branch: str
    ownership_state: str
    mission_id: str | None
    baseline_sha: str | None
    superseded_by_branch: str | None
    supersession_provenance_ref: str | None
    source_provenance_ref: str
    epistemic_class: str

    def validate(self) -> "OwnershipEvidence":
        _text(self.branch, "branch")
        if self.ownership_state not in _OWNERSHIP or self.ownership_state == "UNKNOWN":
            raise RepositoryObservationContractError("unknown ownership denied")
        if self.epistemic_class not in _EPISTEMIC:
            raise RepositoryObservationContractError("ownership evidence must be observed or anchored")
        _text(self.source_provenance_ref, "source_provenance_ref")
        if self.ownership_state in {"ACTIVE", "TERMINAL"}:
            _text(self.mission_id, "mission_id")
            _sha40(self.baseline_sha, "baseline_sha")
        elif self.ownership_state == "UNOWNED":
            if self.mission_id is not None or self.baseline_sha is not None:
                raise RepositoryObservationContractError("unowned branch cannot claim mission binding")
        pair = (self.superseded_by_branch, self.supersession_provenance_ref)
        if (pair[0] is None) != (pair[1] is None):
            raise RepositoryObservationContractError("supersession requires explicit provenance")
        if pair[0] is not None:
            _text(pair[0], "superseded_by_branch")
            _text(pair[1], "supersession_provenance_ref")
            if pair[0] == self.branch:
                raise RepositoryObservationContractError("branch cannot supersede itself")
        return self


@dataclass(frozen=True)
class AncestryEvidence:
    branch: str
    ancestry_state: str
    ahead_by: int | None
    behind_by: int | None

    def validate(self) -> "AncestryEvidence":
        _text(self.branch, "branch")
        if self.ancestry_state not in _ANCESTRY or self.ancestry_state == "UNKNOWN":
            raise RepositoryObservationContractError("unknown ancestry denied")
        for name in ("ahead_by", "behind_by"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise RepositoryObservationContractError(f"{name} invalid")
        a, b = self.ahead_by, self.behind_by
        if self.ancestry_state == "IDENTICAL" and (a, b) != (0, 0):
            raise RepositoryObservationContractError("IDENTICAL ancestry count mismatch")
        if self.ancestry_state == "HEAD_ANCESTOR_OF_DEFAULT" and not (a == 0 and isinstance(b, int) and b > 0):
            raise RepositoryObservationContractError("HEAD_ANCESTOR_OF_DEFAULT count mismatch")
        if self.ancestry_state == "DEFAULT_ANCESTOR_OF_HEAD" and not (isinstance(a, int) and a > 0 and b == 0):
            raise RepositoryObservationContractError("DEFAULT_ANCESTOR_OF_HEAD count mismatch")
        if self.ancestry_state == "DIVERGED" and not (isinstance(a, int) and a > 0 and isinstance(b, int) and b > 0):
            raise RepositoryObservationContractError("DIVERGED count mismatch")
        if self.ancestry_state == "NO_COMMON_ANCESTOR" and (a is not None or b is not None):
            raise RepositoryObservationContractError("foreign ancestry cannot carry counts")
        return self


@dataclass(frozen=True)
class ObservationReceipt:
    repository: str
    observed_master: str
    observed_master_tree: str
    inventory_revision: int
    branch_count: int
    output_sha256: str
    materialized: bool
    asserts_fleet_close: bool

    def validate(self) -> "ObservationReceipt":
        if self.repository != REPOSITORY:
            raise RepositoryObservationContractError("receipt repository mismatch")
        _sha40(self.observed_master, "observed_master")
        _sha40(self.observed_master_tree, "observed_master_tree")
        if self.branch_count < 1:
            raise RepositoryObservationContractError("branch_count must be positive")
        if not re.fullmatch(r"[0-9a-f]{64}", self.output_sha256):
            raise RepositoryObservationContractError("output_sha256 invalid")
        if type(self.materialized) is not bool:
            raise RepositoryObservationContractError("materialized invalid")
        if type(self.asserts_fleet_close) is not bool or self.asserts_fleet_close:
            raise RepositoryObservationContractError("observation cannot assert fleet close")
        return self


def observation_digest(payload: Mapping[str, Any]) -> str:
    return sha256(canonical_json(payload)).hexdigest()

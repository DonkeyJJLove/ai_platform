"""F005-L durable authoritative branch-ownership registry contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import PureWindowsPath
import re
from typing import Any, Mapping, Tuple

from cyber_lion.contracts.fleet_runtime_paths import resolve_fleet_runtime_paths

REPOSITORY = "DonkeyJJLove/ai_platform"
RUNTIME_SOURCE_INSTANCE_ID = "lion-runtime-reconciliation-source-01"
SCHEMA_VERSION = "1.0.0"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OWNERSHIP = frozenset({"ACTIVE", "TERMINAL", "UNOWNED", "UNKNOWN"})
_EPISTEMIC = frozenset({"OBSERVED", "ANCHORED"})


class BranchOwnershipRegistryContractError(ValueError):
    pass


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: object, name: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise BranchOwnershipRegistryContractError(f"{name} invalid")
    return value


def _sha40(value: object, name: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    value = _text(value, name)
    assert isinstance(value, str)
    if not _SHA40.fullmatch(value):
        raise BranchOwnershipRegistryContractError(f"{name} must be full lowercase git SHA")
    return value


def _sha256(value: object, name: str) -> str:
    value = _text(value, name)
    assert isinstance(value, str)
    if not _SHA256.fullmatch(value):
        raise BranchOwnershipRegistryContractError(f"{name} must be sha256 hex")
    return value


@dataclass(frozen=True)
class BranchOwnershipRecord:
    repository: str
    branch: str
    branch_head_sha: str
    ownership_state: str
    mission_id: str | None
    baseline_sha: str | None
    superseded_by_branch: str | None
    supersession_provenance_ref: str | None
    source_provenance_ref: str
    epistemic_class: str
    record_revision: int

    def validate(self) -> "BranchOwnershipRecord":
        if self.repository != REPOSITORY:
            raise BranchOwnershipRegistryContractError("repository substitution denied")
        _text(self.branch, "branch")
        if self.branch.startswith("refs/"):
            raise BranchOwnershipRegistryContractError("branch must be repository branch name")
        _sha40(self.branch_head_sha, "branch_head_sha")
        if self.ownership_state not in _OWNERSHIP or self.ownership_state == "UNKNOWN":
            raise BranchOwnershipRegistryContractError("unknown ownership denied")
        if self.epistemic_class not in _EPISTEMIC:
            raise BranchOwnershipRegistryContractError("epistemic_class must be OBSERVED or ANCHORED")
        _text(self.source_provenance_ref, "source_provenance_ref")
        if isinstance(self.record_revision, bool) or not isinstance(self.record_revision, int) or self.record_revision < 1:
            raise BranchOwnershipRegistryContractError("record_revision invalid")
        if self.ownership_state in {"ACTIVE", "TERMINAL"}:
            _text(self.mission_id, "mission_id")
            _sha40(self.baseline_sha, "baseline_sha")
        elif self.ownership_state == "UNOWNED":
            if self.mission_id is not None or self.baseline_sha is not None:
                raise BranchOwnershipRegistryContractError("unowned branch cannot claim mission binding")
        pair = (self.superseded_by_branch, self.supersession_provenance_ref)
        if (pair[0] is None) != (pair[1] is None):
            raise BranchOwnershipRegistryContractError("supersession requires explicit provenance")
        if pair[0] is not None:
            _text(pair[0], "superseded_by_branch")
            _text(pair[1], "supersession_provenance_ref")
            if pair[0] == self.branch:
                raise BranchOwnershipRegistryContractError("branch cannot supersede itself")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class BranchOwnershipRegistrySnapshot:
    schema_version: str
    repository: str
    source_instance_id: str
    registry_revision: int
    observed_at: str
    records: Tuple[BranchOwnershipRecord, ...]
    registry_digest: str

    def validate(self) -> "BranchOwnershipRegistrySnapshot":
        if self.schema_version != SCHEMA_VERSION:
            raise BranchOwnershipRegistryContractError("unsupported registry schema")
        if self.repository != REPOSITORY:
            raise BranchOwnershipRegistryContractError("registry repository substitution denied")
        if self.source_instance_id != RUNTIME_SOURCE_INSTANCE_ID:
            raise BranchOwnershipRegistryContractError("registry source instance substitution denied")
        if isinstance(self.registry_revision, bool) or not isinstance(self.registry_revision, int) or self.registry_revision < 1:
            raise BranchOwnershipRegistryContractError("registry_revision invalid")
        _text(self.observed_at, "observed_at")
        if type(self.records) is not tuple or not self.records:
            raise BranchOwnershipRegistryContractError("registry records must be non-empty tuple")
        keys: list[tuple[str, str]] = []
        for record in self.records:
            if type(record) is not BranchOwnershipRecord:
                raise BranchOwnershipRegistryContractError("registry record type invalid")
            record.validate()
            if record.repository != self.repository:
                raise BranchOwnershipRegistryContractError("record repository mismatch")
            keys.append((record.branch, record.branch_head_sha))
        if len(keys) != len(set(keys)):
            raise BranchOwnershipRegistryContractError("duplicate branch/head record denied")
        names = [record.branch for record in self.records]
        if len(names) != len(set(names)):
            raise BranchOwnershipRegistryContractError("conflicting branch records denied")
        if tuple(names) != tuple(sorted(names)):
            raise BranchOwnershipRegistryContractError("registry records must be deterministically sorted")
        _sha256(self.registry_digest, "registry_digest")
        if self.registry_digest != self.recompute_digest():
            raise BranchOwnershipRegistryContractError("registry digest mismatch")
        return self

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value = {
            "schema_version": self.schema_version,
            "repository": self.repository,
            "source_instance_id": self.source_instance_id,
            "registry_revision": self.registry_revision,
            "observed_at": self.observed_at,
            "records": [record.canonical_dict() for record in self.records],
        }
        if include_digest:
            value["registry_digest"] = self.registry_digest
        return value

    def recompute_digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict(include_digest=False))).hexdigest()

    @classmethod
    def build(cls, **values: Any) -> "BranchOwnershipRegistrySnapshot":
        raw = dict(values)
        raw["records"] = tuple(sorted(tuple(raw["records"]), key=lambda item: item.branch))
        raw["registry_digest"] = "0" * 64
        provisional = cls(**raw)
        return cls(**{**raw, "registry_digest": provisional.recompute_digest()}).validate()


@dataclass(frozen=True)
class BranchOwnershipProviderConfig:
    repository: str
    source_instance_id: str
    registry_path: str = field(default_factory=lambda: resolve_fleet_runtime_paths().branch_ownership_registry_path)
    minimum_registry_revision: int = 1

    def validate(self) -> "BranchOwnershipProviderConfig":
        if self.repository != REPOSITORY:
            raise BranchOwnershipRegistryContractError("provider repository substitution denied")
        if self.source_instance_id != RUNTIME_SOURCE_INSTANCE_ID:
            raise BranchOwnershipRegistryContractError("provider source instance substitution denied")
        path = PureWindowsPath(self.registry_path)
        expected = PureWindowsPath(resolve_fleet_runtime_paths().branch_ownership_registry_path)
        if not path.is_absolute() or path != expected:
            raise BranchOwnershipRegistryContractError("registry path substitution denied")
        if isinstance(self.minimum_registry_revision, bool) or not isinstance(self.minimum_registry_revision, int) or self.minimum_registry_revision < 1:
            raise BranchOwnershipRegistryContractError("minimum_registry_revision invalid")
        return self

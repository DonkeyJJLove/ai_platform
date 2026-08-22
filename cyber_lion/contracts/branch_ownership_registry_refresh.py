"""Contracts for canonical F005-L branch ownership registry refresh."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Tuple

from cyber_lion.contracts.branch_ownership_registry import (
    BranchOwnershipRecord,
    REPOSITORY,
    RUNTIME_SOURCE_INSTANCE_ID,
)

SCHEMA_VERSION = "1.0.0"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class BranchOwnershipRegistryRefreshContractError(ValueError):
    pass


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise BranchOwnershipRegistryRefreshContractError(f"{name} invalid")
    return value


def _sha(value: object, name: str, pattern: re.Pattern[str]) -> str:
    value = _text(value, name)
    if not pattern.fullmatch(value):
        raise BranchOwnershipRegistryRefreshContractError(f"{name} invalid")
    return value


@dataclass(frozen=True)
class BranchOwnershipRefreshManifest:
    schema_version: str
    repository: str
    source_instance_id: str
    previous_registry_revision: int
    previous_registry_digest: str
    target_registry_revision: int
    expected_master: str
    expected_master_tree: str
    observed_at: str
    records: Tuple[BranchOwnershipRecord, ...]
    manifest_digest: str

    def validate(self) -> "BranchOwnershipRefreshManifest":
        if self.schema_version != SCHEMA_VERSION:
            raise BranchOwnershipRegistryRefreshContractError("unsupported manifest schema")
        if self.repository != REPOSITORY:
            raise BranchOwnershipRegistryRefreshContractError("repository substitution denied")
        if self.source_instance_id != RUNTIME_SOURCE_INSTANCE_ID:
            raise BranchOwnershipRegistryRefreshContractError("source instance substitution denied")
        for value, name in (
            (self.previous_registry_revision, "previous_registry_revision"),
            (self.target_registry_revision, "target_registry_revision"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise BranchOwnershipRegistryRefreshContractError(f"{name} invalid")
        if self.target_registry_revision != self.previous_registry_revision + 1:
            raise BranchOwnershipRegistryRefreshContractError("target registry revision must advance exactly once")
        _sha(self.previous_registry_digest, "previous_registry_digest", _SHA256)
        _sha(self.expected_master, "expected_master", _SHA40)
        _sha(self.expected_master_tree, "expected_master_tree", _SHA40)
        _text(self.observed_at, "observed_at")
        if type(self.records) is not tuple or not self.records:
            raise BranchOwnershipRegistryRefreshContractError("manifest records must be non-empty tuple")
        names: list[str] = []
        for record in self.records:
            if type(record) is not BranchOwnershipRecord:
                raise BranchOwnershipRegistryRefreshContractError("manifest record type invalid")
            record.validate()
            if record.repository != self.repository:
                raise BranchOwnershipRegistryRefreshContractError("record repository mismatch")
            names.append(record.branch)
        if len(names) != len(set(names)):
            raise BranchOwnershipRegistryRefreshContractError("duplicate manifest branch denied")
        if tuple(names) != tuple(sorted(names)):
            raise BranchOwnershipRegistryRefreshContractError("manifest records must be deterministically sorted")
        _sha(self.manifest_digest, "manifest_digest", _SHA256)
        if self.manifest_digest != self.recompute_digest():
            raise BranchOwnershipRegistryRefreshContractError("manifest digest mismatch")
        return self

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value = {
            "schema_version": self.schema_version,
            "repository": self.repository,
            "source_instance_id": self.source_instance_id,
            "previous_registry_revision": self.previous_registry_revision,
            "previous_registry_digest": self.previous_registry_digest,
            "target_registry_revision": self.target_registry_revision,
            "expected_master": self.expected_master,
            "expected_master_tree": self.expected_master_tree,
            "observed_at": self.observed_at,
            "records": [record.canonical_dict() for record in self.records],
        }
        if include_digest:
            value["manifest_digest"] = self.manifest_digest
        return value

    def recompute_digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict(include_digest=False))).hexdigest()

    @classmethod
    def build(cls, **values: Any) -> "BranchOwnershipRefreshManifest":
        raw = dict(values)
        raw["records"] = tuple(sorted(tuple(raw["records"]), key=lambda item: item.branch))
        raw["manifest_digest"] = "0" * 64
        provisional = cls(**raw)
        return cls(**{**raw, "manifest_digest": provisional.recompute_digest()}).validate()

"""Immutable non-effectful authorization contract for bounded pre-PR candidate builds.

The presence of this artifact is not an execution effect.  It binds an already-admitted
BUILD_CANDIDATE request, exact PDP evidence, current trusted authority, and one exact
repository baseline/resource envelope for later consumption by a separate builder.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from pathlib import PurePosixPath
from typing import Any, Tuple

SCHEMA_VERSION = "1.0.0"
_DOMAIN = b"LION/E004-BOUNDED-CANDIDATE-BUILD-AUTHORIZATION/1\0"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,511}$")
_REPOSITORY = re.compile(r"^[^/\s]+/[^/\s]+$")


class CandidateBuildAuthorizationContractError(ValueError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: Any, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise CandidateBuildAuthorizationContractError(f"{name} invalid")
    return value


def _id(value: Any, name: str) -> str:
    value = _text(value, name, 512)
    if not _SAFE_ID.fullmatch(value):
        raise CandidateBuildAuthorizationContractError(f"{name} invalid")
    return value


def _digest(value: Any, name: str) -> str:
    value = _text(value, name, 64)
    if not _SHA64.fullmatch(value):
        raise CandidateBuildAuthorizationContractError(f"{name} must be sha256 hex")
    return value


def _sha(value: Any, name: str) -> str:
    value = _text(value, name, 40)
    if not _SHA40.fullmatch(value):
        raise CandidateBuildAuthorizationContractError(f"{name} must be full lowercase git SHA")
    return value


def _repository(value: Any) -> str:
    value = _text(value, "repository", 512)
    if not _REPOSITORY.fullmatch(value):
        raise CandidateBuildAuthorizationContractError("repository invalid")
    return value


def _paths(values: Any, name: str) -> Tuple[str, ...]:
    if type(values) is not tuple or not values:
        raise CandidateBuildAuthorizationContractError(f"{name} must be non-empty tuple")
    if len(set(values)) != len(values):
        raise CandidateBuildAuthorizationContractError(f"{name} must be unique")
    for raw in values:
        _text(raw, name, 2048)
        if "\\" in raw or any(c in raw for c in "*?[]"):
            raise CandidateBuildAuthorizationContractError(f"{name} contains unsafe path")
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts or str(path) in {"", "."} or str(path) != raw:
            raise CandidateBuildAuthorizationContractError(f"{name} contains unsafe path")
    return values


def canonical_repo_path_resource(repository: str, path: str) -> str:
    repository = _repository(repository)
    _paths((path,), "path")
    return f"repo-path:{repository}:{path}"


def _resources(values: Any, repository: str, candidate_scope: Tuple[str, ...]) -> Tuple[str, ...]:
    if type(values) is not tuple or not values or len(set(values)) != len(values):
        raise CandidateBuildAuthorizationContractError("resource_scope must be unique non-empty tuple")
    expected = tuple(canonical_repo_path_resource(repository, path) for path in candidate_scope)
    for value in values:
        _text(value, "resource_scope", 4096)
        if "*" in value or ".." in value.split("/"):
            raise CandidateBuildAuthorizationContractError("resource_scope unsafe")
    if values != expected:
        raise CandidateBuildAuthorizationContractError("resource_scope must exactly project candidate_scope")
    return values


@dataclass(frozen=True)
class ResourceAuthorityLookupKey:
    """Pre-PR authority identity; no PR number, branch, or synthetic head is permitted."""

    repository: str
    mission_id: str
    grant_id: str
    action: str
    resource_scope: Tuple[str, ...]

    def validate(self) -> "ResourceAuthorityLookupKey":
        _repository(self.repository)
        _id(self.mission_id, "mission_id")
        _id(self.grant_id, "grant_id")
        if self.action != "BUILD_CANDIDATE":
            raise CandidateBuildAuthorizationContractError("resource authority action must be BUILD_CANDIDATE")
        if type(self.resource_scope) is not tuple or not self.resource_scope or len(set(self.resource_scope)) != len(self.resource_scope):
            raise CandidateBuildAuthorizationContractError("resource authority scope invalid")
        prefix = f"repo-path:{self.repository}:"
        for resource in self.resource_scope:
            _text(resource, "resource_scope", 4096)
            if not resource.startswith(prefix) or "*" in resource or ".." in resource.split("/"):
                raise CandidateBuildAuthorizationContractError("resource authority scope invalid")
        return self

    def binding(self) -> tuple[str, str, str, str, Tuple[str, ...]]:
        self.validate()
        return (self.repository, self.mission_id, self.grant_id, self.action, self.resource_scope)

    def digest(self) -> str:
        self.validate()
        payload = {
            "repository": self.repository,
            "mission_id": self.mission_id,
            "grant_id": self.grant_id,
            "action": self.action,
            "resource_scope": list(self.resource_scope),
        }
        return sha256(b"LION/E004-RESOURCE-AUTHORITY-LOOKUP/1\0" + canonical_json(payload)).hexdigest()


@dataclass(frozen=True)
class TrustedRepositoryBaseline:
    repository: str
    master_sha: str
    master_tree_sha: str
    observed_at: str

    def validate(self) -> "TrustedRepositoryBaseline":
        _repository(self.repository)
        _sha(self.master_sha, "master_sha")
        _sha(self.master_tree_sha, "master_tree_sha")
        _text(self.observed_at, "observed_at", 128)
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(b"LION/E004-TRUSTED-REPOSITORY-BASELINE/1\0" + canonical_json(asdict(self))).hexdigest()


@dataclass(frozen=True)
class BoundedCandidateBuildAuthorization:
    schema_version: str
    authorization_id: str
    admission_request_id: str
    admission_request_digest: str
    gate_request_id: str
    gate_request_digest: str
    gate_event_id: str
    gate_decision_digest: str
    pdp_receipt_id: str
    pdp_request_id: str
    pdp_request_digest: str
    pdp_decision_digest: str
    pdp_replay_key: str
    policy_binding: str
    grant_id: str
    leaf_grant_digest: str
    authority_lineage_digest: str
    authority_provenance_id: str
    authority_epoch: int
    authority_state_version: int
    root_grant_id: str
    root_grant_digest: str
    live_admission_digest: str
    authority_admitted_at: str
    repository: str
    baseline_master_sha: str
    baseline_master_tree_sha: str
    baseline_observation_digest: str
    candidate_scope: Tuple[str, ...]
    resource_scope: Tuple[str, ...]
    action: str
    requested_authority: str
    effective_authority_ceiling: str
    valid_from: str
    expires_at: str
    issuance_replay_digest: str
    state: str = "AUTHORIZATION_ISSUED"
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    repository_ref_effect: str = "NONE"
    external_effect: str = "NONE"
    authorization_digest: str = ""

    def canonical_payload(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("authorization_digest")
        value["candidate_scope"] = list(self.candidate_scope)
        value["resource_scope"] = list(self.resource_scope)
        return value

    def compute_digest(self) -> str:
        return sha256(_DOMAIN + canonical_json(self.canonical_payload())).hexdigest()

    def validate(self) -> "BoundedCandidateBuildAuthorization":
        if self.schema_version != SCHEMA_VERSION:
            raise CandidateBuildAuthorizationContractError("unsupported authorization schema")
        for name in (
            "authorization_id", "admission_request_id", "gate_request_id", "gate_event_id",
            "pdp_receipt_id", "pdp_request_id", "grant_id", "root_grant_id",
        ):
            _id(getattr(self, name), name)
        for name in (
            "admission_request_digest", "gate_request_digest", "gate_decision_digest",
            "pdp_request_digest", "pdp_decision_digest", "pdp_replay_key",
            "leaf_grant_digest", "authority_lineage_digest", "root_grant_digest",
            "live_admission_digest", "baseline_observation_digest", "issuance_replay_digest",
        ):
            _digest(getattr(self, name), name)
        _text(self.policy_binding, "policy_binding", 2048)
        _text(self.authority_provenance_id, "authority_provenance_id", 1024)
        if isinstance(self.authority_epoch, bool) or not isinstance(self.authority_epoch, int) or self.authority_epoch < 0:
            raise CandidateBuildAuthorizationContractError("authority_epoch invalid")
        if isinstance(self.authority_state_version, bool) or not isinstance(self.authority_state_version, int) or self.authority_state_version < 1:
            raise CandidateBuildAuthorizationContractError("authority_state_version invalid")
        _text(self.authority_admitted_at, "authority_admitted_at", 128)
        _repository(self.repository)
        _sha(self.baseline_master_sha, "baseline_master_sha")
        _sha(self.baseline_master_tree_sha, "baseline_master_tree_sha")
        _paths(self.candidate_scope, "candidate_scope")
        _resources(self.resource_scope, self.repository, self.candidate_scope)
        if self.action != "BUILD_CANDIDATE":
            raise CandidateBuildAuthorizationContractError("authorization action must be BUILD_CANDIDATE")
        if self.requested_authority != "local_write" or self.effective_authority_ceiling != "local_write":
            raise CandidateBuildAuthorizationContractError("candidate build authorization must be local_write only")
        _text(self.valid_from, "valid_from", 128)
        _text(self.expires_at, "expires_at", 128)
        if self.state != "AUTHORIZATION_ISSUED":
            raise CandidateBuildAuthorizationContractError("authorization state invalid")
        if (
            self.authority_effect,
            self.execution_effect,
            self.repository_ref_effect,
            self.external_effect,
        ) != ("NONE", "NONE", "NONE", "NONE"):
            raise CandidateBuildAuthorizationContractError("authorization artifact cannot carry effects")
        if self.authorization_digest:
            _digest(self.authorization_digest, "authorization_digest")
            if self.authorization_digest != self.compute_digest():
                raise CandidateBuildAuthorizationContractError("authorization_digest mismatch")
        return self

    def sealed(self) -> "BoundedCandidateBuildAuthorization":
        self.validate()
        return BoundedCandidateBuildAuthorization(
            **{**asdict(self), "authorization_digest": self.compute_digest()}
        ).validate()

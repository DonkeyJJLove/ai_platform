"""Immutable non-effectful permit for single-use candidate-build authorization consumption."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from pathlib import PurePosixPath
from typing import Any, Tuple

SCHEMA_VERSION = "1.0.0"
_DOMAIN = b"LION/E004-BUILD-AUTHORIZATION-CONSUMPTION-PERMIT/1\0"
_REPLAY_DOMAIN = b"LION/E004-CANDIDATE-BUILD-AUTHORIZATION-CONSUMPTION/1\0"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,511}$")
_REPOSITORY = re.compile(r"^[^/\s]+/[^/\s]+$")


class BuildAuthorizationConsumptionContractError(ValueError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: Any, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise BuildAuthorizationConsumptionContractError(f"{name} invalid")
    return value


def _id(value: Any, name: str) -> str:
    value = _text(value, name, 512)
    if not _SAFE_ID.fullmatch(value):
        raise BuildAuthorizationConsumptionContractError(f"{name} invalid")
    return value


def _digest(value: Any, name: str) -> str:
    value = _text(value, name, 64)
    if not _SHA64.fullmatch(value):
        raise BuildAuthorizationConsumptionContractError(f"{name} must be sha256 hex")
    return value


def _sha(value: Any, name: str) -> str:
    value = _text(value, name, 40)
    if not _SHA40.fullmatch(value):
        raise BuildAuthorizationConsumptionContractError(f"{name} must be git sha")
    return value


def _repository(value: Any) -> str:
    value = _text(value, "repository", 512)
    if not _REPOSITORY.fullmatch(value):
        raise BuildAuthorizationConsumptionContractError("repository invalid")
    return value


def _paths(values: Any, name: str) -> Tuple[str, ...]:
    if type(values) is not tuple or not values or len(set(values)) != len(values):
        raise BuildAuthorizationConsumptionContractError(f"{name} must be unique non-empty tuple")
    for raw in values:
        _text(raw, name, 2048)
        if "\\" in raw or any(c in raw for c in "*?[]"):
            raise BuildAuthorizationConsumptionContractError(f"{name} unsafe")
        p = PurePosixPath(raw)
        if p.is_absolute() or ".." in p.parts or str(p) in {"", "."} or str(p) != raw:
            raise BuildAuthorizationConsumptionContractError(f"{name} unsafe")
    return values


def canonical_repo_path_resource(repository: str, path: str) -> str:
    _repository(repository)
    _paths((path,), "path")
    return f"repo-path:{repository}:{path}"


def consumption_replay_payload(
    *,
    authorization_id: str,
    authorization_digest: str,
    issuance_replay_digest: str,
    repository: str,
    baseline_master_sha: str,
    baseline_master_tree_sha: str,
    baseline_observation_digest: str,
    current_baseline_digest: str,
    candidate_scope: Tuple[str, ...],
    resource_scope: Tuple[str, ...],
    action: str,
    grant_id: str,
    leaf_grant_digest: str,
    authority_lineage_digest: str,
    authority_provenance_id: str,
    authority_epoch: int,
    authority_state_version: int,
    root_grant_id: str,
    root_grant_digest: str,
    live_admission_digest: str,
    current_authority_digest: str,
    authorization_valid_from: str,
    authorization_expires_at: str,
) -> dict[str, Any]:
    _id(authorization_id, "authorization_id")
    for name, value in (
        ("authorization_digest", authorization_digest),
        ("issuance_replay_digest", issuance_replay_digest),
        ("baseline_observation_digest", baseline_observation_digest),
        ("current_baseline_digest", current_baseline_digest),
        ("leaf_grant_digest", leaf_grant_digest),
        ("authority_lineage_digest", authority_lineage_digest),
        ("root_grant_digest", root_grant_digest),
        ("live_admission_digest", live_admission_digest),
        ("current_authority_digest", current_authority_digest),
    ):
        _digest(value, name)
    _repository(repository)
    _sha(baseline_master_sha, "baseline_master_sha")
    _sha(baseline_master_tree_sha, "baseline_master_tree_sha")
    candidate_scope = _paths(candidate_scope, "candidate_scope")
    resource_scope = _paths(resource_scope, "resource_scope")
    expected_resources = tuple(canonical_repo_path_resource(repository, p) for p in candidate_scope)
    if resource_scope != expected_resources:
        raise BuildAuthorizationConsumptionContractError("resource_scope must exactly project candidate_scope")
    if action != "BUILD_CANDIDATE":
        raise BuildAuthorizationConsumptionContractError("action must be BUILD_CANDIDATE")
    _id(grant_id, "grant_id")
    _text(authority_provenance_id, "authority_provenance_id", 1024)
    if isinstance(authority_epoch, bool) or not isinstance(authority_epoch, int) or authority_epoch < 0:
        raise BuildAuthorizationConsumptionContractError("authority_epoch invalid")
    if isinstance(authority_state_version, bool) or not isinstance(authority_state_version, int) or authority_state_version < 1:
        raise BuildAuthorizationConsumptionContractError("authority_state_version invalid")
    _id(root_grant_id, "root_grant_id")
    _text(authorization_valid_from, "authorization_valid_from", 1024)
    _text(authorization_expires_at, "authorization_expires_at", 1024)
    return {
        "authorization_id": authorization_id,
        "authorization_digest": authorization_digest,
        "issuance_replay_digest": issuance_replay_digest,
        "repository": repository,
        "baseline_master_sha": baseline_master_sha,
        "baseline_master_tree_sha": baseline_master_tree_sha,
        "baseline_observation_digest": baseline_observation_digest,
        "current_baseline_digest": current_baseline_digest,
        "candidate_scope": list(candidate_scope),
        "resource_scope": list(resource_scope),
        "action": action,
        "grant_id": grant_id,
        "leaf_grant_digest": leaf_grant_digest,
        "authority_lineage_digest": authority_lineage_digest,
        "authority_provenance_id": authority_provenance_id,
        "authority_epoch": authority_epoch,
        "authority_state_version": authority_state_version,
        "root_grant_id": root_grant_id,
        "root_grant_digest": root_grant_digest,
        "live_admission_digest": live_admission_digest,
        "current_authority_digest": current_authority_digest,
        "authorization_valid_from": authorization_valid_from,
        "authorization_expires_at": authorization_expires_at,
    }


def compute_consumption_replay_digest(**kwargs: Any) -> str:
    return sha256(_REPLAY_DOMAIN + canonical_json(consumption_replay_payload(**kwargs))).hexdigest()


@dataclass(frozen=True)
class BuildAuthorizationConsumptionPermit:
    schema_version: str
    consumption_permit_id: str
    authorization_id: str
    authorization_digest: str
    issuance_replay_digest: str
    repository: str
    baseline_master_sha: str
    baseline_master_tree_sha: str
    baseline_observation_digest: str
    action: str
    candidate_scope: Tuple[str, ...]
    resource_scope: Tuple[str, ...]
    grant_id: str
    leaf_grant_digest: str
    authority_lineage_digest: str
    authority_provenance_id: str
    authority_epoch: int
    authority_state_version: int
    root_grant_id: str
    root_grant_digest: str
    live_admission_digest: str
    authorization_valid_from: str
    authorization_expires_at: str
    checked_at: str
    current_baseline_digest: str
    current_authority_digest: str
    consumption_replay_digest: str
    state: str = "CONSUMPTION_PERMIT_ISSUED"
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    repository_ref_effect: str = "NONE"
    external_effect: str = "NONE"
    consumption_permit_digest: str = ""

    def canonical_payload(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("consumption_permit_digest")
        value["candidate_scope"] = list(self.candidate_scope)
        value["resource_scope"] = list(self.resource_scope)
        return value

    def compute_consumption_replay_digest(self) -> str:
        return compute_consumption_replay_digest(
            authorization_id=self.authorization_id,
            authorization_digest=self.authorization_digest,
            issuance_replay_digest=self.issuance_replay_digest,
            repository=self.repository,
            baseline_master_sha=self.baseline_master_sha,
            baseline_master_tree_sha=self.baseline_master_tree_sha,
            baseline_observation_digest=self.baseline_observation_digest,
            current_baseline_digest=self.current_baseline_digest,
            candidate_scope=self.candidate_scope,
            resource_scope=self.resource_scope,
            action=self.action,
            grant_id=self.grant_id,
            leaf_grant_digest=self.leaf_grant_digest,
            authority_lineage_digest=self.authority_lineage_digest,
            authority_provenance_id=self.authority_provenance_id,
            authority_epoch=self.authority_epoch,
            authority_state_version=self.authority_state_version,
            root_grant_id=self.root_grant_id,
            root_grant_digest=self.root_grant_digest,
            live_admission_digest=self.live_admission_digest,
            current_authority_digest=self.current_authority_digest,
            authorization_valid_from=self.authorization_valid_from,
            authorization_expires_at=self.authorization_expires_at,
        )

    def compute_digest(self) -> str:
        return sha256(_DOMAIN + canonical_json(self.canonical_payload())).hexdigest()

    def validate(self) -> "BuildAuthorizationConsumptionPermit":
        if self.schema_version != SCHEMA_VERSION:
            raise BuildAuthorizationConsumptionContractError("unsupported schema")
        for name in ("consumption_permit_id", "authorization_id", "grant_id", "root_grant_id"):
            _id(getattr(self, name), name)
        for name in (
            "authorization_digest", "issuance_replay_digest", "baseline_observation_digest",
            "leaf_grant_digest", "authority_lineage_digest", "root_grant_digest",
            "live_admission_digest", "current_baseline_digest", "current_authority_digest",
            "consumption_replay_digest",
        ):
            _digest(getattr(self, name), name)
        _repository(self.repository)
        _sha(self.baseline_master_sha, "baseline_master_sha")
        _sha(self.baseline_master_tree_sha, "baseline_master_tree_sha")
        _paths(self.candidate_scope, "candidate_scope")
        expected_resources = tuple(canonical_repo_path_resource(self.repository, p) for p in self.candidate_scope)
        if self.resource_scope != expected_resources:
            raise BuildAuthorizationConsumptionContractError("resource_scope must exactly project candidate_scope")
        if self.action != "BUILD_CANDIDATE":
            raise BuildAuthorizationConsumptionContractError("action must be BUILD_CANDIDATE")
        if isinstance(self.authority_epoch, bool) or not isinstance(self.authority_epoch, int) or self.authority_epoch < 0:
            raise BuildAuthorizationConsumptionContractError("authority_epoch invalid")
        if isinstance(self.authority_state_version, bool) or not isinstance(self.authority_state_version, int) or self.authority_state_version < 1:
            raise BuildAuthorizationConsumptionContractError("authority_state_version invalid")
        for name in ("authority_provenance_id", "authorization_valid_from", "authorization_expires_at", "checked_at"):
            _text(getattr(self, name), name, 1024)
        expected_replay = self.compute_consumption_replay_digest()
        if self.consumption_replay_digest != expected_replay:
            raise BuildAuthorizationConsumptionContractError("consumption replay digest source binding mismatch")
        if self.consumption_permit_id != f"cbcp:{self.consumption_replay_digest}":
            raise BuildAuthorizationConsumptionContractError("permit id must derive from consumption replay digest")
        if self.state != "CONSUMPTION_PERMIT_ISSUED":
            raise BuildAuthorizationConsumptionContractError("state invalid")
        if (self.authority_effect, self.execution_effect, self.repository_ref_effect, self.external_effect) != ("NONE", "NONE", "NONE", "NONE"):
            raise BuildAuthorizationConsumptionContractError("permit cannot carry effects")
        if self.consumption_permit_digest:
            _digest(self.consumption_permit_digest, "consumption_permit_digest")
            if self.consumption_permit_digest != self.compute_digest():
                raise BuildAuthorizationConsumptionContractError("permit digest mismatch")
        return self

    def sealed(self) -> "BuildAuthorizationConsumptionPermit":
        self.validate()
        return BuildAuthorizationConsumptionPermit(
            **{**asdict(self), "consumption_permit_digest": self.compute_digest()}
        ).validate()

"""Immutable non-effectful admission immediately before builder process launch."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from pathlib import PurePosixPath

SCHEMA_VERSION = "1.0.0"
BUILDER_CAPABILITY_CLASS = "DETACHED_CANDIDATE_BUILD_ONLY"
ADMISSION_STATE = "BUILDER_START_ADMITTED"
PERMIT_DOMAIN = b"LION/E004-BUILDER-START-ADMISSION/1\0"
REPLAY_DOMAIN = b"LION/E004-BUILDER-START-ADMISSION-REPLAY/1\0"
PROCESS_PROFILE_DOMAIN = b"LION/E004-BUILDER-PROCESS-PROFILE/1\0"
LAUNCH_POLICY_DOMAIN = b"LION/E004-BUILDER-LAUNCH-POLICY/1\0"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,511}$")
_REPO = re.compile(r"^[^/\s]+/[^/\s]+$")


class BuilderStartAdmissionContractError(ValueError):
    pass


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: object, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise BuilderStartAdmissionContractError(f"{name} invalid")
    return value


def _id(value: object, name: str) -> str:
    value = _text(value, name, 512)
    if not _ID.fullmatch(value):
        raise BuilderStartAdmissionContractError(f"{name} invalid")
    return value


def _digest(value: object, name: str) -> str:
    value = _text(value, name, 64)
    if not _SHA64.fullmatch(value):
        raise BuilderStartAdmissionContractError(f"{name} invalid")
    return value


def _sha(value: object, name: str) -> str:
    value = _text(value, name, 40)
    if not _SHA40.fullmatch(value):
        raise BuilderStartAdmissionContractError(f"{name} invalid")
    return value


def _paths(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not tuple or not value or len(set(value)) != len(value):
        raise BuilderStartAdmissionContractError(f"{name} invalid")
    for raw in value:
        _text(raw, name, 2048)
        if "\\" in raw or any(c in raw for c in "*?[]"):
            raise BuilderStartAdmissionContractError(f"{name} unsafe")
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts or str(path) in {"", "."} or str(path) != raw:
            raise BuilderStartAdmissionContractError(f"{name} unsafe")
    return value


def canonical_launch_policy() -> dict[str, object]:
    return {
        "authority_minting": "DENY",
        "detached_candidate_admission_required": True,
        "direct_master_write": "DENY",
        "executor_sandbox_entry": "DENY_AT_R21",
        "external_effect": "DENY",
        "launch_class": "DETACHED_CANDIDATE_BUILDER_PROCESS",
        "process_allocation": "R22_ONLY",
        "repository_ref_mutation": "DENY",
        "workspace_allocation": "R22_OR_LATER_ONLY",
    }


def compute_launch_policy_digest() -> str:
    return sha256(LAUNCH_POLICY_DOMAIN + _json(canonical_launch_policy())).hexdigest()


def process_profile_payload(**kwargs: object) -> dict[str, object]:
    repository = _text(kwargs["repository"], "repository", 512)
    if not _REPO.fullmatch(repository):
        raise BuilderStartAdmissionContractError("repository invalid")
    if kwargs["action"] != "BUILD_CANDIDATE":
        raise BuilderStartAdmissionContractError("action invalid")
    candidate_scope = _paths(kwargs["candidate_scope"], "candidate_scope")
    resource_scope = _paths(kwargs["resource_scope"], "resource_scope")
    expected = tuple(f"repo-path:{repository}:{path}" for path in candidate_scope)
    if resource_scope != expected:
        raise BuilderStartAdmissionContractError("resource scope projection mismatch")
    for name in ("builder_subject_id", "builder_instance_id"):
        _id(kwargs[name], name)
    if kwargs["builder_capability_class"] != BUILDER_CAPABILITY_CLASS:
        raise BuilderStartAdmissionContractError("builder capability invalid")
    for name in (
        "builder_identity_digest",
        "builder_implementation_digest",
        "builder_attestation_digest",
        "current_builder_subject_digest",
    ):
        _digest(kwargs[name], name)
    return {
        "action": kwargs["action"],
        "builder_attestation_digest": kwargs["builder_attestation_digest"],
        "builder_capability_class": kwargs["builder_capability_class"],
        "builder_identity_digest": kwargs["builder_identity_digest"],
        "builder_implementation_digest": kwargs["builder_implementation_digest"],
        "builder_instance_id": kwargs["builder_instance_id"],
        "builder_subject_id": kwargs["builder_subject_id"],
        "candidate_scope": list(candidate_scope),
        "current_builder_subject_digest": kwargs["current_builder_subject_digest"],
        "repository": repository,
        "resource_scope": list(resource_scope),
    }


def compute_process_profile_digest(**kwargs: object) -> str:
    return sha256(PROCESS_PROFILE_DOMAIN + _json(process_profile_payload(**kwargs))).hexdigest()


def builder_start_replay_payload(**kwargs: object) -> dict[str, object]:
    for name in (
        "source_invocation_consumption_permit_id",
        "source_builder_invocation_permit_id",
        "source_builder_entry_permit_id",
        "root_grant_id",
        "builder_subject_id",
        "builder_instance_id",
        "process_profile_id",
    ):
        _id(kwargs[name], name)
    for name in (
        "source_invocation_consumption_permit_digest",
        "source_invocation_consumption_replay_digest",
        "source_builder_invocation_permit_digest",
        "source_builder_entry_permit_digest",
        "current_baseline_digest",
        "root_grant_digest",
        "current_authority_digest",
        "builder_identity_digest",
        "builder_implementation_digest",
        "builder_attestation_digest",
        "current_builder_subject_digest",
        "process_profile_digest",
        "launch_policy_digest",
    ):
        _digest(kwargs[name], name)
    repository = _text(kwargs["repository"], "repository", 512)
    if not _REPO.fullmatch(repository):
        raise BuilderStartAdmissionContractError("repository invalid")
    _sha(kwargs["baseline_master_sha"], "baseline_master_sha")
    _sha(kwargs["baseline_master_tree_sha"], "baseline_master_tree_sha")
    candidate_scope = _paths(kwargs["candidate_scope"], "candidate_scope")
    resource_scope = _paths(kwargs["resource_scope"], "resource_scope")
    if resource_scope != tuple(f"repo-path:{repository}:{path}" for path in candidate_scope):
        raise BuilderStartAdmissionContractError("resource scope projection mismatch")
    if kwargs["action"] != "BUILD_CANDIDATE":
        raise BuilderStartAdmissionContractError("action invalid")
    if kwargs["builder_capability_class"] != BUILDER_CAPABILITY_CLASS:
        raise BuilderStartAdmissionContractError("builder capability invalid")
    for name in ("authority_epoch", "authority_state_version"):
        value = kwargs[name]
        minimum = 0 if name == "authority_epoch" else 1
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise BuilderStartAdmissionContractError(f"{name} invalid")
    profile_kwargs = {name: kwargs[name] for name in (
        "repository", "action", "candidate_scope", "resource_scope",
        "builder_subject_id", "builder_instance_id", "builder_capability_class",
        "builder_identity_digest", "builder_implementation_digest",
        "builder_attestation_digest", "current_builder_subject_digest",
    )}
    expected_profile = compute_process_profile_digest(**profile_kwargs)
    if kwargs["process_profile_digest"] != expected_profile or kwargs["process_profile_id"] != f"bpp:{expected_profile}":
        raise BuilderStartAdmissionContractError("process profile binding mismatch")
    if kwargs["launch_policy_digest"] != compute_launch_policy_digest():
        raise BuilderStartAdmissionContractError("launch policy binding mismatch")
    payload = dict(kwargs)
    payload["candidate_scope"] = list(candidate_scope)
    payload["resource_scope"] = list(resource_scope)
    return payload


def compute_builder_start_admission_replay_digest(**kwargs: object) -> str:
    return sha256(REPLAY_DOMAIN + _json(builder_start_replay_payload(**kwargs))).hexdigest()


@dataclass(frozen=True)
class BuilderStartAdmission:
    schema_version: str
    builder_start_admission_id: str
    source_invocation_consumption_permit_id: str
    source_invocation_consumption_permit_digest: str
    source_invocation_consumption_replay_digest: str
    source_builder_invocation_permit_id: str
    source_builder_invocation_permit_digest: str
    source_builder_entry_permit_id: str
    source_builder_entry_permit_digest: str
    repository: str
    baseline_master_sha: str
    baseline_master_tree_sha: str
    current_baseline_digest: str
    action: str
    candidate_scope: tuple[str, ...]
    resource_scope: tuple[str, ...]
    authority_epoch: int
    authority_state_version: int
    root_grant_id: str
    root_grant_digest: str
    current_authority_digest: str
    builder_subject_id: str
    builder_instance_id: str
    builder_capability_class: str
    builder_identity_digest: str
    builder_implementation_digest: str
    builder_attestation_digest: str
    current_builder_subject_digest: str
    process_profile_id: str
    process_profile_digest: str
    launch_policy_digest: str
    checked_at: str
    builder_start_admission_replay_digest: str
    state: str = ADMISSION_STATE
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    repository_ref_effect: str = "NONE"
    external_effect: str = "NONE"
    builder_start_admission_digest: str = ""

    def replay_kwargs(self) -> dict[str, object]:
        excluded = {
            "schema_version", "builder_start_admission_id", "checked_at", "state",
            "authority_effect", "execution_effect", "repository_ref_effect", "external_effect",
            "builder_start_admission_replay_digest", "builder_start_admission_digest",
        }
        return {k: v for k, v in asdict(self).items() if k not in excluded}

    def canonical_payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("builder_start_admission_digest")
        value["candidate_scope"] = list(self.candidate_scope)
        value["resource_scope"] = list(self.resource_scope)
        return value

    def compute_builder_start_admission_replay_digest(self) -> str:
        return compute_builder_start_admission_replay_digest(**self.replay_kwargs())

    def compute_digest(self) -> str:
        return sha256(PERMIT_DOMAIN + _json(self.canonical_payload())).hexdigest()

    def validate(self) -> "BuilderStartAdmission":
        if self.schema_version != SCHEMA_VERSION:
            raise BuilderStartAdmissionContractError("unsupported schema")
        builder_start_replay_payload(**self.replay_kwargs())
        _text(self.checked_at, "checked_at", 1024)
        replay = self.compute_builder_start_admission_replay_digest()
        if self.builder_start_admission_replay_digest != replay:
            raise BuilderStartAdmissionContractError("start admission replay mismatch")
        if self.builder_start_admission_id != f"bsa:{replay}":
            raise BuilderStartAdmissionContractError("start admission id mismatch")
        if self.state != ADMISSION_STATE:
            raise BuilderStartAdmissionContractError("state invalid")
        if (self.authority_effect, self.execution_effect, self.repository_ref_effect, self.external_effect) != ("NONE", "NONE", "NONE", "NONE"):
            raise BuilderStartAdmissionContractError("admission cannot carry effects")
        if self.builder_start_admission_digest:
            _digest(self.builder_start_admission_digest, "builder_start_admission_digest")
            if self.builder_start_admission_digest != self.compute_digest():
                raise BuilderStartAdmissionContractError("start admission digest mismatch")
        return self

    def sealed(self) -> "BuilderStartAdmission":
        self.validate()
        return BuilderStartAdmission(**{**asdict(self), "builder_start_admission_digest": self.compute_digest()}).validate()

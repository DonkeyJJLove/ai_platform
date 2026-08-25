"""Immutable contracts for the first real builder process start effect boundary."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping

SCHEMA_VERSION = "1.0.0"
PROVIDER_CAPABILITY_CLASS = "BUILDER_PROCESS_START_ONLY"
EFFECT_CLASS = "BUILDER_PROCESS_START"
HELD_STATE = "HELD_NOT_EXECUTING_BUILDER"
STARTED_STATE = "STARTED_OBSERVED"
REQUEST_DOMAIN = b"LION/E004-BUILDER-PROCESS-LAUNCH-REQUEST/1\0"
REPLAY_DOMAIN = b"LION/E004-BUILDER-PROCESS-LAUNCH-REPLAY/1\0"
RECEIPT_DOMAIN = b"LION/E004-BUILDER-PROCESS-LAUNCH-RECEIPT/1\0"
PROVIDER_DOMAIN = b"LION/E004-BUILDER-PROCESS-RUNTIME-PROVIDER/1\0"
IDENTITY_DOMAIN = b"LION/E004-BUILDER-PROCESS-IDENTITY/1\0"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,511}$")
_REPO = re.compile(r"^[^/\s]+/[^/\s]+$")


class BuilderProcessLaunchContractError(ValueError):
    pass


def _json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: object, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise BuilderProcessLaunchContractError(f"{name} invalid")
    return value


def _id(value: object, name: str) -> str:
    value = _text(value, name, 512)
    if not _ID.fullmatch(value):
        raise BuilderProcessLaunchContractError(f"{name} invalid")
    return value


def _digest(value: object, name: str) -> str:
    value = _text(value, name, 64)
    if not _SHA64.fullmatch(value):
        raise BuilderProcessLaunchContractError(f"{name} invalid")
    return value


def _sha(value: object, name: str) -> str:
    value = _text(value, name, 40)
    if not _SHA40.fullmatch(value):
        raise BuilderProcessLaunchContractError(f"{name} invalid")
    return value


def _repo(value: object) -> str:
    value = _text(value, "repository", 512)
    if not _REPO.fullmatch(value):
        raise BuilderProcessLaunchContractError("repository invalid")
    return value


@dataclass(frozen=True)
class BuilderProcessRuntimeProviderDescriptor:
    provider_id: str
    provider_identity_digest: str
    provider_implementation_digest: str
    provider_attestation_digest: str
    capability_class: str
    supported_process_profile_digest: str
    supported_launch_policy_digest: str
    isolation_class: str
    process_identity_scheme: str
    observation_scheme: str
    recovery_scheme: str
    repository_ref_capability: str = "NONE"
    authority_minting_capability: str = "NONE"
    external_effect_capability: str = "NONE"
    descriptor_digest: str = ""
    schema_version: str = SCHEMA_VERSION

    def canonical_payload(self) -> dict[str, object]:
        value = asdict(self); value.pop("descriptor_digest")
        return value

    def compute_digest(self) -> str:
        return sha256(PROVIDER_DOMAIN + _json(self.canonical_payload())).hexdigest()

    def validate(self) -> "BuilderProcessRuntimeProviderDescriptor":
        if self.schema_version != SCHEMA_VERSION:
            raise BuilderProcessLaunchContractError("provider schema invalid")
        _id(self.provider_id, "provider_id")
        for name in ("provider_identity_digest", "provider_implementation_digest", "provider_attestation_digest",
                     "supported_process_profile_digest", "supported_launch_policy_digest"):
            _digest(getattr(self, name), name)
        for name in ("isolation_class", "process_identity_scheme", "observation_scheme", "recovery_scheme"):
            _text(getattr(self, name), name, 512)
        if self.capability_class != PROVIDER_CAPABILITY_CLASS:
            raise BuilderProcessLaunchContractError("provider capability invalid")
        if (self.repository_ref_capability, self.authority_minting_capability, self.external_effect_capability) != ("NONE", "NONE", "NONE"):
            raise BuilderProcessLaunchContractError("provider carries prohibited capability")
        if self.descriptor_digest:
            _digest(self.descriptor_digest, "descriptor_digest")
            if self.descriptor_digest != self.compute_digest():
                raise BuilderProcessLaunchContractError("provider descriptor digest mismatch")
        return self

    def sealed(self) -> "BuilderProcessRuntimeProviderDescriptor":
        self.validate()
        return BuilderProcessRuntimeProviderDescriptor(**{**asdict(self), "descriptor_digest": self.compute_digest()}).validate()


@dataclass(frozen=True)
class BuilderProcessIdentity:
    launch_id: str
    builder_subject_id: str
    builder_instance_id: str
    process_profile_id: str
    process_profile_digest: str
    launch_policy_digest: str
    runtime_provider_id: str
    runtime_provider_identity_digest: str
    execution_environment_id: str
    process_handle_reference: str
    process_identity_token: str
    started_at: str
    state: str
    identity_digest: str = ""
    schema_version: str = SCHEMA_VERSION

    def canonical_payload(self) -> dict[str, object]:
        value = asdict(self); value.pop("identity_digest")
        return value

    def compute_digest(self) -> str:
        return sha256(IDENTITY_DOMAIN + _json(self.canonical_payload())).hexdigest()

    def validate(self) -> "BuilderProcessIdentity":
        if self.schema_version != SCHEMA_VERSION:
            raise BuilderProcessLaunchContractError("identity schema invalid")
        for name in ("launch_id", "builder_subject_id", "builder_instance_id", "process_profile_id", "runtime_provider_id",
                     "execution_environment_id", "process_handle_reference", "process_identity_token", "started_at"):
            _id(getattr(self, name), name) if name != "started_at" else _text(getattr(self, name), name, 1024)
        for name in ("process_profile_digest", "launch_policy_digest", "runtime_provider_identity_digest"):
            _digest(getattr(self, name), name)
        if self.process_handle_reference.isdigit():
            raise BuilderProcessLaunchContractError("PID-alone process handle denied")
        if self.state not in {HELD_STATE, STARTED_STATE, "UNKNOWN_LAUNCH", "TERMINATED"}:
            raise BuilderProcessLaunchContractError("process identity state invalid")
        if self.identity_digest:
            _digest(self.identity_digest, "identity_digest")
            if self.identity_digest != self.compute_digest():
                raise BuilderProcessLaunchContractError("process identity digest mismatch")
        return self

    def sealed(self) -> "BuilderProcessIdentity":
        self.validate()
        return BuilderProcessIdentity(**{**asdict(self), "identity_digest": self.compute_digest()}).validate()


def launch_replay_payload(**kwargs: object) -> dict[str, object]:
    id_fields = (
        "source_builder_start_admission_id", "source_builder_start_issuance_record_id", "repository",
        "root_grant_id", "builder_subject_id", "builder_instance_id", "process_profile_id", "runtime_provider_id",
    )
    for name in id_fields:
        _repo(kwargs[name]) if name == "repository" else _id(kwargs[name], name)
    for name in (
        "source_builder_start_admission_digest", "source_builder_start_admission_replay_digest",
        "source_builder_start_issuance_record_digest", "root_grant_digest", "expected_current_authority_digest",
        "builder_identity_digest", "builder_implementation_digest", "builder_attestation_digest",
        "expected_builder_subject_digest", "process_profile_digest", "launch_policy_digest",
        "runtime_provider_identity_digest", "runtime_provider_implementation_digest", "runtime_provider_attestation_digest",
    ):
        _digest(kwargs[name], name)
    _sha(kwargs["baseline_master_sha"], "baseline_master_sha")
    _sha(kwargs["baseline_master_tree_sha"], "baseline_master_tree_sha")
    for name in ("authority_epoch", "authority_state_version"):
        value = kwargs[name]
        minimum = 0 if name == "authority_epoch" else 1
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise BuilderProcessLaunchContractError(f"{name} invalid")
    return dict(kwargs)


def compute_launch_replay_digest(**kwargs: object) -> str:
    return sha256(REPLAY_DOMAIN + _json(launch_replay_payload(**kwargs))).hexdigest()


@dataclass(frozen=True)
class BuilderProcessLaunchRequest:
    launch_request_id: str
    source_builder_start_admission_id: str
    source_builder_start_admission_digest: str
    source_builder_start_admission_replay_digest: str
    source_builder_start_issuance_record_id: str
    source_builder_start_issuance_record_digest: str
    repository: str
    baseline_master_sha: str
    baseline_master_tree_sha: str
    authority_epoch: int
    authority_state_version: int
    root_grant_id: str
    root_grant_digest: str
    expected_current_authority_digest: str
    builder_subject_id: str
    builder_instance_id: str
    builder_identity_digest: str
    builder_implementation_digest: str
    builder_attestation_digest: str
    expected_builder_subject_digest: str
    process_profile_id: str
    process_profile_digest: str
    launch_policy_digest: str
    runtime_provider_id: str
    runtime_provider_identity_digest: str
    runtime_provider_implementation_digest: str
    runtime_provider_attestation_digest: str
    launch_replay_digest: str
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    repository_ref_effect: str = "NONE"
    external_effect: str = "NONE"
    launch_request_digest: str = ""
    schema_version: str = SCHEMA_VERSION

    def replay_kwargs(self) -> dict[str, object]:
        excluded = {"launch_request_id", "launch_replay_digest", "launch_request_digest", "schema_version",
                    "authority_effect", "execution_effect", "repository_ref_effect", "external_effect"}
        return {k: v for k, v in asdict(self).items() if k not in excluded}

    def canonical_payload(self) -> dict[str, object]:
        value = asdict(self); value.pop("launch_request_digest")
        return value

    def compute_digest(self) -> str:
        return sha256(REQUEST_DOMAIN + _json(self.canonical_payload())).hexdigest()

    def validate(self) -> "BuilderProcessLaunchRequest":
        if self.schema_version != SCHEMA_VERSION:
            raise BuilderProcessLaunchContractError("request schema invalid")
        launch_replay_payload(**self.replay_kwargs())
        replay = compute_launch_replay_digest(**self.replay_kwargs())
        if self.launch_replay_digest != replay or self.launch_request_id != f"bplr:{replay}":
            raise BuilderProcessLaunchContractError("launch request replay binding mismatch")
        if (self.authority_effect, self.execution_effect, self.repository_ref_effect, self.external_effect) != ("NONE", "NONE", "NONE", "NONE"):
            raise BuilderProcessLaunchContractError("launch request cannot carry effects")
        if self.launch_request_digest:
            _digest(self.launch_request_digest, "launch_request_digest")
            if self.launch_request_digest != self.compute_digest():
                raise BuilderProcessLaunchContractError("launch request digest mismatch")
        return self

    def sealed(self) -> "BuilderProcessLaunchRequest":
        self.validate()
        return BuilderProcessLaunchRequest(**{**asdict(self), "launch_request_digest": self.compute_digest()}).validate()


@dataclass(frozen=True)
class BuilderProcessLaunchReceipt:
    launch_receipt_id: str
    launch_request_id: str
    launch_request_digest: str
    launch_replay_digest: str
    source_builder_start_admission_id: str
    source_builder_start_admission_digest: str
    repository: str
    baseline_master_sha: str
    baseline_master_tree_sha: str
    authority_digest_at_launch: str
    builder_subject_digest_at_launch: str
    process_profile_id: str
    process_profile_digest: str
    launch_policy_digest: str
    runtime_provider_id: str
    runtime_provider_identity_digest: str
    runtime_provider_implementation_digest: str
    runtime_provider_attestation_digest: str
    launch_id: str
    execution_environment_id: str
    process_handle_reference: str
    process_identity_token: str
    process_identity_digest: str
    launch_started_at: str
    launch_observed_at: str
    effect_class: str = EFFECT_CLASS
    effect_state: str = STARTED_STATE
    authority_effect: str = "NONE"
    execution_effect: str = EFFECT_CLASS
    repository_ref_effect: str = "NONE"
    external_effect: str = "NONE"
    launch_receipt_digest: str = ""
    schema_version: str = SCHEMA_VERSION

    def canonical_payload(self) -> dict[str, object]:
        value = asdict(self); value.pop("launch_receipt_digest")
        return value

    def compute_digest(self) -> str:
        return sha256(RECEIPT_DOMAIN + _json(self.canonical_payload())).hexdigest()

    def validate(self) -> "BuilderProcessLaunchReceipt":
        if self.schema_version != SCHEMA_VERSION:
            raise BuilderProcessLaunchContractError("receipt schema invalid")
        for name in ("launch_receipt_id", "launch_request_id", "source_builder_start_admission_id", "process_profile_id",
                     "runtime_provider_id", "launch_id", "execution_environment_id", "process_handle_reference", "process_identity_token"):
            _id(getattr(self, name), name)
        _repo(self.repository); _sha(self.baseline_master_sha, "baseline_master_sha"); _sha(self.baseline_master_tree_sha, "baseline_master_tree_sha")
        for name in ("launch_request_digest", "launch_replay_digest", "source_builder_start_admission_digest", "authority_digest_at_launch",
                     "builder_subject_digest_at_launch", "process_profile_digest", "launch_policy_digest", "runtime_provider_identity_digest",
                     "runtime_provider_implementation_digest", "runtime_provider_attestation_digest", "process_identity_digest"):
            _digest(getattr(self, name), name)
        _text(self.launch_started_at, "launch_started_at", 1024); _text(self.launch_observed_at, "launch_observed_at", 1024)
        if self.process_handle_reference.isdigit():
            raise BuilderProcessLaunchContractError("PID-alone process handle denied")
        if (self.effect_class, self.effect_state, self.authority_effect, self.execution_effect, self.repository_ref_effect, self.external_effect) != (
            EFFECT_CLASS, STARTED_STATE, "NONE", EFFECT_CLASS, "NONE", "NONE"):
            raise BuilderProcessLaunchContractError("receipt effect semantics invalid")
        expected_id = f"bplx:{self.launch_replay_digest}"
        if self.launch_receipt_id != expected_id:
            raise BuilderProcessLaunchContractError("receipt id mismatch")
        if self.launch_receipt_digest:
            _digest(self.launch_receipt_digest, "launch_receipt_digest")
            if self.launch_receipt_digest != self.compute_digest():
                raise BuilderProcessLaunchContractError("receipt digest mismatch")
        return self

    def sealed(self) -> "BuilderProcessLaunchReceipt":
        self.validate()
        return BuilderProcessLaunchReceipt(**{**asdict(self), "launch_receipt_digest": self.compute_digest()}).validate()

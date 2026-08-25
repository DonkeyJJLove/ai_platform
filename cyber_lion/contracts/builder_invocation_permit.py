"""Non-effectful E004 builder-invocation permit contract."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from pathlib import PurePosixPath

SCHEMA_VERSION = "1.0.0"
BUILDER_CAPABILITY_CLASS = "DETACHED_CANDIDATE_BUILD_ONLY"
_PERMIT_DOMAIN = b"LION/E004-BUILDER-INVOCATION-PERMIT/1\0"
_REPLAY_DOMAIN = b"LION/E004-BUILDER-INVOCATION/1\0"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,511}$")
_REPO = re.compile(r"^[^/\s]+/[^/\s]+$")


class BuilderInvocationPermitContractError(ValueError):
    pass


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: object, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise BuilderInvocationPermitContractError(f"{name} invalid")
    return value


def _id(value: object, name: str) -> str:
    value = _text(value, name, 512)
    if not _ID.fullmatch(value):
        raise BuilderInvocationPermitContractError(f"{name} invalid")
    return value


def _digest(value: object, name: str) -> str:
    value = _text(value, name, 64)
    if not _SHA64.fullmatch(value):
        raise BuilderInvocationPermitContractError(f"{name} invalid")
    return value


def _sha(value: object, name: str) -> str:
    value = _text(value, name, 40)
    if not _SHA40.fullmatch(value):
        raise BuilderInvocationPermitContractError(f"{name} invalid")
    return value


def _repository(value: object) -> str:
    value = _text(value, "repository", 512)
    if not _REPO.fullmatch(value):
        raise BuilderInvocationPermitContractError("repository invalid")
    return value


def _paths(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not tuple or not value or len(set(value)) != len(value):
        raise BuilderInvocationPermitContractError(f"{name} invalid")
    for raw in value:
        _text(raw, name, 2048)
        if "\\" in raw or any(c in raw for c in "*?[]"):
            raise BuilderInvocationPermitContractError(f"{name} unsafe")
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts or str(path) in {"", "."} or str(path) != raw:
            raise BuilderInvocationPermitContractError(f"{name} unsafe")
    return value


def _resources(repository: str, scope: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"repo-path:{repository}:{path}" for path in scope)


def builder_invocation_replay_payload(**kwargs: object) -> dict[str, object]:
    for name in (
        "source_builder_entry_permit_id",
        "root_grant_id",
        "builder_subject_id",
        "builder_instance_id",
    ):
        _id(kwargs[name], name)
    for name in (
        "source_builder_entry_permit_digest",
        "source_builder_entry_replay_digest",
        "current_baseline_digest",
        "root_grant_digest",
        "current_authority_digest",
        "builder_identity_digest",
        "builder_implementation_digest",
        "builder_attestation_digest",
        "current_builder_subject_digest",
    ):
        _digest(kwargs[name], name)
    _repository(kwargs["repository"])
    _sha(kwargs["baseline_master_sha"], "baseline_master_sha")
    _sha(kwargs["baseline_master_tree_sha"], "baseline_master_tree_sha")
    candidate_scope = _paths(kwargs["candidate_scope"], "candidate_scope")
    resource_scope = _paths(kwargs["resource_scope"], "resource_scope")
    if resource_scope != _resources(kwargs["repository"], candidate_scope):
        raise BuilderInvocationPermitContractError("resource scope projection mismatch")
    if kwargs["action"] != "BUILD_CANDIDATE":
        raise BuilderInvocationPermitContractError("action invalid")
    if kwargs["builder_capability_class"] != BUILDER_CAPABILITY_CLASS:
        raise BuilderInvocationPermitContractError("builder capability invalid")
    for name in ("authority_epoch", "authority_state_version"):
        value = kwargs[name]
        minimum = 0 if name == "authority_epoch" else 1
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise BuilderInvocationPermitContractError(f"{name} invalid")
    payload = dict(kwargs)
    payload["candidate_scope"] = list(candidate_scope)
    payload["resource_scope"] = list(resource_scope)
    return payload


def compute_builder_invocation_replay_digest(**kwargs: object) -> str:
    return sha256(_REPLAY_DOMAIN + _json(builder_invocation_replay_payload(**kwargs))).hexdigest()


@dataclass(frozen=True)
class BuilderInvocationPermit:
    schema_version: str
    builder_invocation_permit_id: str
    source_builder_entry_permit_id: str
    source_builder_entry_permit_digest: str
    source_builder_entry_replay_digest: str
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
    checked_at: str
    builder_invocation_replay_digest: str
    state: str = "BUILDER_INVOCATION_PERMIT_ISSUED"
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    repository_ref_effect: str = "NONE"
    external_effect: str = "NONE"
    builder_invocation_permit_digest: str = ""

    def replay_kwargs(self) -> dict[str, object]:
        names = (
            "source_builder_entry_permit_id",
            "source_builder_entry_permit_digest",
            "source_builder_entry_replay_digest",
            "repository",
            "baseline_master_sha",
            "baseline_master_tree_sha",
            "current_baseline_digest",
            "action",
            "candidate_scope",
            "resource_scope",
            "authority_epoch",
            "authority_state_version",
            "root_grant_id",
            "root_grant_digest",
            "current_authority_digest",
            "builder_subject_id",
            "builder_instance_id",
            "builder_capability_class",
            "builder_identity_digest",
            "builder_implementation_digest",
            "builder_attestation_digest",
            "current_builder_subject_digest",
        )
        return {name: getattr(self, name) for name in names}

    def canonical_payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("builder_invocation_permit_digest")
        value["candidate_scope"] = list(self.candidate_scope)
        value["resource_scope"] = list(self.resource_scope)
        return value

    def compute_builder_invocation_replay_digest(self) -> str:
        return compute_builder_invocation_replay_digest(**self.replay_kwargs())

    def compute_digest(self) -> str:
        return sha256(_PERMIT_DOMAIN + _json(self.canonical_payload())).hexdigest()

    def validate(self) -> "BuilderInvocationPermit":
        if self.schema_version != SCHEMA_VERSION:
            raise BuilderInvocationPermitContractError("unsupported schema")
        builder_invocation_replay_payload(**self.replay_kwargs())
        _text(self.checked_at, "checked_at", 1024)
        expected_replay = self.compute_builder_invocation_replay_digest()
        if self.builder_invocation_replay_digest != expected_replay:
            raise BuilderInvocationPermitContractError("builder invocation replay source binding mismatch")
        if self.builder_invocation_permit_id != f"bip:{expected_replay}":
            raise BuilderInvocationPermitContractError("builder invocation permit id mismatch")
        if self.state != "BUILDER_INVOCATION_PERMIT_ISSUED":
            raise BuilderInvocationPermitContractError("state invalid")
        if (
            self.authority_effect,
            self.execution_effect,
            self.repository_ref_effect,
            self.external_effect,
        ) != ("NONE", "NONE", "NONE", "NONE"):
            raise BuilderInvocationPermitContractError("permit cannot carry effects")
        if self.builder_invocation_permit_digest:
            _digest(self.builder_invocation_permit_digest, "builder_invocation_permit_digest")
            if self.builder_invocation_permit_digest != self.compute_digest():
                raise BuilderInvocationPermitContractError("builder invocation permit digest mismatch")
        return self

    def sealed(self) -> "BuilderInvocationPermit":
        self.validate()
        return BuilderInvocationPermit(
            **{**asdict(self), "builder_invocation_permit_digest": self.compute_digest()}
        ).validate()

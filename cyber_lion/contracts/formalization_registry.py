"""Non-effectful contracts for architecture formalization discovery.

Formalization records describe how architecture is represented and refreshed. They do
not grant repository, runtime, merge, deployment, credential, training, or model
promotion authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Tuple

SCHEMA_ID = "lion.formalization-registry/v1"
DIGEST_DOMAIN = b"LION/FORMALIZATION-REGISTRY/1\0"
AUTHORITY_EFFECT = "NONE"

REFRESH_TRIGGERS = frozenset({
    "SOURCE_CHANGE", "CONTRACT_CHANGE", "CAPABILITY_CHANGE",
    "SEMANTIC_OWNER_CHANGE", "FLOW_CHANGE", "RUNTIME_OBSERVATION",
    "CURRENTNESS_CHANGE", "RAG_RELEASE", "MANUAL_REVIEW",
})
CURRENTNESS_MODES = frozenset({
    "EXACT_HEAD", "SUBJECT_DIGEST", "SOURCE_DERIVED", "RUNTIME_OBSERVED",
    "VERSIONED_STATIC", "MIXED",
})
ARTIFACT_CLASSES = frozenset({
    "SOURCE", "CONTRACT", "DERIVED_PROJECTION", "CURRENTNESS_CARRIER",
    "RAG_ROUTE", "RAG_RELEASE", "EVAL", "DOCUMENTATION", "RESEARCH_ARTIFACT",
})
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class FormalizationRegistryError(ValueError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def domain_digest(domain: bytes, payload: Mapping[str, Any]) -> str:
    return sha256(domain + canonical_json(dict(payload))).hexdigest()


def _text(value: Any, name: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise FormalizationRegistryError(f"{name} invalid")
    return value


def _id(value: Any, name: str) -> str:
    value = _text(value, name, limit=256)
    if not _SAFE_ID.fullmatch(value):
        raise FormalizationRegistryError(f"{name} invalid")
    return value


def _tuple_text(value: Any, name: str) -> Tuple[str, ...]:
    if type(value) is not tuple:
        raise FormalizationRegistryError(f"{name} must be tuple")
    for item in value:
        _text(item, name)
    if len(set(value)) != len(value):
        raise FormalizationRegistryError(f"{name} must be unique")
    return value


def validate_sha40(value: Any, name: str) -> str:
    value = _text(value, name, limit=40)
    if not _SHA40.fullmatch(value):
        raise FormalizationRegistryError(f"{name} must be sha1 hex")
    return value


def validate_sha256(value: Any, name: str) -> str:
    value = _text(value, name, limit=64)
    if not _SHA256.fullmatch(value):
        raise FormalizationRegistryError(f"{name} must be sha256 hex")
    return value


def validate_repository(value: Any, name: str = "repository") -> str:
    value = _text(value, name, limit=256)
    if not _REPOSITORY.fullmatch(value):
        raise FormalizationRegistryError(f"{name} invalid")
    return value


@dataclass(frozen=True)
class FormalizationArtifact:
    artifact_id: str
    path: str
    schema_or_type: str
    semantic_role: str
    semantic_owner_concept: str
    generator: str | None
    source_dependencies: Tuple[str, ...]
    refresh_triggers: Tuple[str, ...]
    validation_refs: Tuple[str, ...]
    consumers: Tuple[str, ...]
    currentness_mode: str
    artifact_class: str

    def validate(self) -> "FormalizationArtifact":
        _id(self.artifact_id, "artifact_id")
        _text(self.path, "path")
        if self.path.startswith("/") or "\x00" in self.path:
            raise FormalizationRegistryError("artifact path invalid")
        _text(self.schema_or_type, "schema_or_type")
        _text(self.semantic_role, "semantic_role")
        _id(self.semantic_owner_concept, "semantic_owner_concept")
        if self.generator is not None:
            _text(self.generator, "generator")
        _tuple_text(self.source_dependencies, "source_dependencies")
        _tuple_text(self.refresh_triggers, "refresh_triggers")
        _tuple_text(self.validation_refs, "validation_refs")
        _tuple_text(self.consumers, "consumers")
        if not set(self.refresh_triggers).issubset(REFRESH_TRIGGERS):
            raise FormalizationRegistryError("unknown refresh trigger")
        if self.currentness_mode not in CURRENTNESS_MODES:
            raise FormalizationRegistryError("unknown currentness_mode")
        if self.artifact_class not in ARTIFACT_CLASSES:
            raise FormalizationRegistryError("unknown artifact_class")
        return self

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FormalizationArtifact":
        return cls(
            artifact_id=value["artifact_id"], path=value["path"], schema_or_type=value["schema_or_type"],
            semantic_role=value["semantic_role"], semantic_owner_concept=value["semantic_owner_concept"],
            generator=value.get("generator"), source_dependencies=tuple(value.get("source_dependencies", ())),
            refresh_triggers=tuple(value.get("refresh_triggers", ())), validation_refs=tuple(value.get("validation_refs", ())),
            consumers=tuple(value.get("consumers", ())), currentness_mode=value["currentness_mode"],
            artifact_class=value["artifact_class"],
        ).validate()


@dataclass(frozen=True)
class FormalizationRegistry:
    registry_id: str
    architecture_epoch: str
    entries: Tuple[FormalizationArtifact, ...]
    authority_effect: str = AUTHORITY_EFFECT
    registry_digest: str = ""
    schema_id: str = SCHEMA_ID

    def canonical_payload(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("registry_digest", None)
        return data

    def compute_digest(self) -> str:
        return domain_digest(DIGEST_DOMAIN, self.canonical_payload())

    def validate(self, *, require_digest: bool = True) -> "FormalizationRegistry":
        if self.schema_id != SCHEMA_ID:
            raise FormalizationRegistryError("unsupported registry schema")
        _id(self.registry_id, "registry_id")
        _text(self.architecture_epoch, "architecture_epoch", limit=64)
        if self.authority_effect != AUTHORITY_EFFECT:
            raise FormalizationRegistryError("registry cannot carry authority")
        if type(self.entries) is not tuple or not self.entries:
            raise FormalizationRegistryError("entries must be non-empty tuple")
        for entry in self.entries:
            if not isinstance(entry, FormalizationArtifact):
                raise FormalizationRegistryError("entry type invalid")
            entry.validate()
        ids = [entry.artifact_id for entry in self.entries]
        paths = [entry.path for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise FormalizationRegistryError("duplicate artifact_id")
        if len(paths) != len(set(paths)):
            raise FormalizationRegistryError("duplicate artifact path")
        if require_digest:
            validate_sha256(self.registry_digest, "registry_digest")
            if self.registry_digest != self.compute_digest():
                raise FormalizationRegistryError("registry_digest mismatch")
        elif self.registry_digest:
            validate_sha256(self.registry_digest, "registry_digest")
        return self

    def sealed(self) -> "FormalizationRegistry":
        self.validate(require_digest=False)
        return replace(self, registry_digest=self.compute_digest()).validate()

    def by_id(self) -> dict[str, FormalizationArtifact]:
        self.validate()
        return {entry.artifact_id: entry for entry in self.entries}

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FormalizationRegistry":
        return cls(
            registry_id=value["registry_id"], architecture_epoch=value["architecture_epoch"],
            entries=tuple(FormalizationArtifact.from_dict(v) for v in value["entries"]),
            authority_effect=value.get("authority_effect", ""), registry_digest=value.get("registry_digest", ""),
            schema_id=value.get("schema_id", ""),
        ).validate()

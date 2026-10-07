"""Provider-neutral attachment identity and provider-specific projection contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import re
from typing import Any, Mapping

AUTHORITY_EFFECT = "NONE"
CAPABILITY_SCHEMA_ID = "lion.provider-capability-snapshot/v1"
ATTACHMENT_SCHEMA_ID = "lion.attachment-manifest/v1"
PROJECTION_SCHEMA_ID = "lion.attachment-projection/v1"

CAPABILITY_STATES = frozenset({"SUPPORTED", "UNSUPPORTED", "UNKNOWN"})
CURRENTNESS_STATES = frozenset({"CURRENT", "STALE", "UNKNOWN"})
PROJECTION_MODES = frozenset({
    "INLINE_TEXT", "STRUCTURED_EXTRACTION", "CHUNKED_TEXT",
    "NATIVE_IMAGE", "NATIVE_FILE", "MATERIALIZED_LOCAL_PATH", "UNSUPPORTED",
})
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")


class AttachmentProjectionError(ValueError):
    pass


def _canon(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AttachmentProjectionError("strict JSON required") from exc


def _digest(value: Any) -> str:
    return sha256(_canon(value)).hexdigest()


def _text(value: Any, name: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or "\x00" in value:
        raise AttachmentProjectionError(name)
    return value


def _id(value: Any, name: str) -> str:
    value = _text(value, name, 256)
    if _ID.fullmatch(value) is None:
        raise AttachmentProjectionError(name)
    return value


def _hex(value: Any, name: str, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise AttachmentProjectionError(name)
    return value


@dataclass(frozen=True)
class ProviderCapabilitySnapshot:
    provider: str
    endpoint_ref: str
    model_release_ref: str | None
    observed_at: str
    currentness: str
    text_input: str
    image_input: str
    native_file_input: str
    native_pdf_input: str
    structured_data_input: str
    workspace_access: str
    network_access: str
    session_persistence: str
    streaming: str
    max_payload_bytes: int | None
    parallel_calls: int | None
    context_budget: int | None
    evidence_refs: tuple[str, ...]
    authority_effect: str = AUTHORITY_EFFECT
    snapshot_digest: str = ""

    def validate(self, *, require_digest: bool = True) -> "ProviderCapabilitySnapshot":
        _id(self.provider, "provider")
        _text(self.endpoint_ref, "endpoint_ref", 1024)
        if self.model_release_ref is not None:
            _text(self.model_release_ref, "model_release_ref", 1024)
        _text(self.observed_at, "observed_at", 128)
        if self.currentness not in CURRENTNESS_STATES:
            raise AttachmentProjectionError("currentness")
        for value in (
            self.text_input, self.image_input, self.native_file_input, self.native_pdf_input,
            self.structured_data_input, self.workspace_access, self.network_access,
            self.session_persistence, self.streaming,
        ):
            if value not in CAPABILITY_STATES:
                raise AttachmentProjectionError("capability state")
        for value, name in (
            (self.max_payload_bytes, "max_payload_bytes"),
            (self.parallel_calls, "parallel_calls"),
            (self.context_budget, "context_budget"),
        ):
            if value is not None and (type(value) is not int or value < 1):
                raise AttachmentProjectionError(name)
        if type(self.evidence_refs) is not tuple or tuple(sorted(set(self.evidence_refs))) != self.evidence_refs:
            raise AttachmentProjectionError("evidence_refs")
        for ref in self.evidence_refs:
            _text(ref, "evidence_ref", 1024)
        if self.authority_effect != AUTHORITY_EFFECT:
            raise AttachmentProjectionError("authority_effect")
        if require_digest:
            _hex(self.snapshot_digest, "snapshot_digest")
            if self.snapshot_digest != self.compute_digest():
                raise AttachmentProjectionError("snapshot digest mismatch")
        return self

    def digest_payload(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("snapshot_digest", None)
        value["schema"] = CAPABILITY_SCHEMA_ID
        return value

    def compute_digest(self) -> str:
        return _digest(self.digest_payload())

    def sealed(self) -> "ProviderCapabilitySnapshot":
        self.validate(require_digest=False)
        return replace(self, snapshot_digest=self.compute_digest()).validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {"schema": CAPABILITY_SCHEMA_ID, **asdict(self)}


@dataclass(frozen=True)
class AttachmentManifest:
    attachment_id: str
    source_artifact_ref: str
    original_content_digest: str
    byte_size: int
    media_type: str
    display_name: str
    source_domain: str
    classification: str
    producer: str
    mission_id: str | None
    conversation_id: str | None
    assignment_id: str | None
    generation: int
    authority_effect: str = AUTHORITY_EFFECT
    manifest_digest: str = ""

    def validate(self, *, require_digest: bool = True) -> "AttachmentManifest":
        _id(self.attachment_id, "attachment_id")
        _text(self.source_artifact_ref, "source_artifact_ref", 1024)
        _hex(self.original_content_digest, "original_content_digest")
        if type(self.byte_size) is not int or self.byte_size < 0:
            raise AttachmentProjectionError("byte_size")
        _text(self.media_type, "media_type", 256)
        _text(self.display_name, "display_name", 512)
        _id(self.source_domain, "source_domain")
        _id(self.classification, "classification")
        _text(self.producer, "producer", 512)
        for value, name in (
            (self.mission_id, "mission_id"),
            (self.conversation_id, "conversation_id"),
            (self.assignment_id, "assignment_id"),
        ):
            if value is not None:
                _id(value, name)
        if type(self.generation) is not int or self.generation < 0:
            raise AttachmentProjectionError("generation")
        if self.authority_effect != AUTHORITY_EFFECT:
            raise AttachmentProjectionError("authority_effect")
        if require_digest:
            _hex(self.manifest_digest, "manifest_digest")
            if self.manifest_digest != self.compute_digest():
                raise AttachmentProjectionError("manifest digest mismatch")
        return self

    def digest_payload(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("manifest_digest", None)
        value["schema"] = ATTACHMENT_SCHEMA_ID
        return value

    def compute_digest(self) -> str:
        return _digest(self.digest_payload())

    def sealed(self) -> "AttachmentManifest":
        self.validate(require_digest=False)
        return replace(self, manifest_digest=self.compute_digest()).validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {"schema": ATTACHMENT_SCHEMA_ID, **asdict(self)}


@dataclass(frozen=True)
class AttachmentProjection:
    projection_id: str
    attachment_manifest_digest: str
    provider_capability_digest: str
    provider: str
    mode: str
    transformation_id: str
    derived_projection_digest: str | None
    actual_provider_payload_digest: str | None
    coverage: str
    truncated: bool
    currentness: str
    authority_effect: str = AUTHORITY_EFFECT
    projection_digest: str = ""

    def validate(self, *, require_digest: bool = True) -> "AttachmentProjection":
        _id(self.projection_id, "projection_id")
        _hex(self.attachment_manifest_digest, "attachment_manifest_digest")
        _hex(self.provider_capability_digest, "provider_capability_digest")
        _id(self.provider, "provider")
        if self.mode not in PROJECTION_MODES:
            raise AttachmentProjectionError("mode")
        _text(self.transformation_id, "transformation_id", 512)
        _hex(self.derived_projection_digest, "derived_projection_digest", allow_none=True)
        _hex(self.actual_provider_payload_digest, "actual_provider_payload_digest", allow_none=True)
        _text(self.coverage, "coverage", 256)
        if type(self.truncated) is not bool:
            raise AttachmentProjectionError("truncated")
        if self.currentness not in CURRENTNESS_STATES:
            raise AttachmentProjectionError("currentness")
        if self.authority_effect != AUTHORITY_EFFECT:
            raise AttachmentProjectionError("authority_effect")
        if self.mode == "UNSUPPORTED" and self.actual_provider_payload_digest is not None:
            raise AttachmentProjectionError("unsupported attachment cannot have provider payload")
        if require_digest:
            _hex(self.projection_digest, "projection_digest")
            if self.projection_digest != self.compute_digest():
                raise AttachmentProjectionError("projection digest mismatch")
        return self

    def digest_payload(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("projection_digest", None)
        value["schema"] = PROJECTION_SCHEMA_ID
        return value

    def compute_digest(self) -> str:
        return _digest(self.digest_payload())

    def sealed(self) -> "AttachmentProjection":
        self.validate(require_digest=False)
        return replace(self, projection_digest=self.compute_digest()).validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {"schema": PROJECTION_SCHEMA_ID, **asdict(self)}


def validate_mode_for_capabilities(
    manifest: AttachmentManifest,
    capabilities: ProviderCapabilitySnapshot,
    mode: str,
) -> None:
    manifest.validate()
    capabilities.validate()
    if capabilities.currentness != "CURRENT":
        raise AttachmentProjectionError("provider capability currentness")
    if mode == "INLINE_TEXT":
        if capabilities.text_input != "SUPPORTED" or not manifest.media_type.startswith("text/"):
            raise AttachmentProjectionError("inline text unsupported")
    elif mode == "NATIVE_IMAGE":
        if capabilities.image_input != "SUPPORTED" or not manifest.media_type.startswith("image/"):
            raise AttachmentProjectionError("native image unsupported")
    elif mode == "NATIVE_FILE":
        if capabilities.native_file_input != "SUPPORTED":
            raise AttachmentProjectionError("native file unsupported")
        if manifest.media_type == "application/pdf" and capabilities.native_pdf_input != "SUPPORTED":
            raise AttachmentProjectionError("native PDF unsupported")
    elif mode in {"STRUCTURED_EXTRACTION", "CHUNKED_TEXT", "MATERIALIZED_LOCAL_PATH"}:
        if capabilities.text_input != "SUPPORTED":
            raise AttachmentProjectionError("derived text path unsupported")
    elif mode == "UNSUPPORTED":
        return
    else:
        raise AttachmentProjectionError("mode")

"""Bounded attachment ingestion and provider-specific projection helpers.

This module owns no transport, artifact registry, scheduler or authority. It binds
actual request bytes to AttachmentManifest, then derives a provider-specific
text projection only when a CURRENT capability snapshot explicitly supports it.
Native image/file/PDF paths remain fail-closed until an observed provider
capability and a byte-preserving transport are wired.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import replace
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from cyber_lion.contracts.attachment_projection import (
    ATTACHMENT_SCHEMA_ID,
    CAPABILITY_SCHEMA_ID,
    PROJECTION_SCHEMA_ID,
    AttachmentManifest,
    AttachmentProjection,
    AttachmentProjectionError,
    ProviderCapabilitySnapshot,
    validate_mode_for_capabilities,
)

MAX_ATTACHMENTS = 8
MAX_ATTACHMENT_BYTES = 65536
MAX_TOTAL_ATTACHMENT_BYTES = 122880
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AttachmentProjectionError(name)
    return dict(value)


def provider_capability_from_mapping(value: Mapping[str, Any]) -> ProviderCapabilitySnapshot:
    data = _mapping(value, "provider capability")
    if data.pop("schema", None) != CAPABILITY_SCHEMA_ID:
        raise AttachmentProjectionError("provider capability schema")
    if isinstance(data.get("evidence_refs"), list):
        data["evidence_refs"] = tuple(data["evidence_refs"])
    try:
        return ProviderCapabilitySnapshot(**data).validate()
    except TypeError as exc:
        raise AttachmentProjectionError("provider capability fields") from exc


def attachment_manifest_from_mapping(value: Mapping[str, Any]) -> AttachmentManifest:
    data = _mapping(value, "attachment manifest")
    if data.pop("schema", None) != ATTACHMENT_SCHEMA_ID:
        raise AttachmentProjectionError("attachment manifest schema")
    try:
        return AttachmentManifest(**data).validate()
    except TypeError as exc:
        raise AttachmentProjectionError("attachment manifest fields") from exc


def attachment_projection_from_mapping(value: Mapping[str, Any]) -> AttachmentProjection:
    data = _mapping(value, "attachment projection")
    if data.pop("schema", None) != PROJECTION_SCHEMA_ID:
        raise AttachmentProjectionError("attachment projection schema")
    try:
        return AttachmentProjection(**data).validate()
    except TypeError as exc:
        raise AttachmentProjectionError("attachment projection fields") from exc


def ingest_inline_attachments(
    raw: Any,
    *,
    source_domain: str,
    producer: str,
    mission_id: str | None,
    conversation_id: str | None,
    assignment_id: str | None,
    generation: int,
    classification: str = "INTERNAL",
) -> tuple[dict[str, Any], ...]:
    """Decode bounded request bytes and create sealed manifests."""
    if raw in (None, ()):
        return ()
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_ATTACHMENTS:
        raise AttachmentProjectionError("attachments")
    total = 0
    out: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping) or set(item) != {"display_name", "media_type", "data_b64"}:
            raise AttachmentProjectionError(f"attachment[{index}] schema")
        display_name = item.get("display_name")
        media_type = item.get("media_type")
        encoded = item.get("data_b64")
        if not isinstance(display_name, str) or not display_name or len(display_name) > 512 or "\x00" in display_name:
            raise AttachmentProjectionError(f"attachment[{index}] display_name")
        if not isinstance(media_type, str) or not media_type or len(media_type) > 256 or "\x00" in media_type:
            raise AttachmentProjectionError(f"attachment[{index}] media_type")
        if not isinstance(encoded, str) or not encoded:
            raise AttachmentProjectionError(f"attachment[{index}] data_b64")
        try:
            data = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
            raise AttachmentProjectionError(f"attachment[{index}] base64") from exc
        if not 1 <= len(data) <= MAX_ATTACHMENT_BYTES:
            raise AttachmentProjectionError(f"attachment[{index}] byte_size")
        total += len(data)
        if total > MAX_TOTAL_ATTACHMENT_BYTES:
            raise AttachmentProjectionError("attachment aggregate byte_size")
        content_digest = sha256(data).hexdigest()
        manifest = AttachmentManifest(
            attachment_id="attachment-" + content_digest[:32],
            source_artifact_ref=f"{source_domain.lower()}-inline:{content_digest}",
            original_content_digest=content_digest,
            byte_size=len(data),
            media_type=media_type.lower(),
            display_name=display_name,
            source_domain=source_domain,
            classification=classification,
            producer=producer,
            mission_id=mission_id,
            conversation_id=conversation_id,
            assignment_id=assignment_id,
            generation=generation,
        ).sealed()
        text: str | None = None
        if manifest.media_type.startswith("text/"):
            try:
                text = data.decode("utf-8", "strict")
            except UnicodeDecodeError as exc:
                raise AttachmentProjectionError(f"attachment[{index}] utf8") from exc
            if "\x00" in text:
                raise AttachmentProjectionError(f"attachment[{index}] nul")
        out.append({"manifest": manifest.to_dict(), "text": text})
    return tuple(out)


def build_inline_text_projections(
    items: Sequence[Mapping[str, Any]],
    capabilities: ProviderCapabilitySnapshot,
) -> tuple[tuple[str, ...], tuple[dict[str, Any], ...]]:
    capabilities.validate()
    if capabilities.currentness != "CURRENT":
        raise AttachmentProjectionError("provider capability currentness")
    segments: list[str] = []
    projections: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise AttachmentProjectionError(f"attachment item[{index}]")
        manifest = attachment_manifest_from_mapping(_mapping(item.get("manifest"), "attachment manifest"))
        text = item.get("text")
        if not isinstance(text, str):
            raise AttachmentProjectionError("bounded attachment ingestion supports text/* only")
        validate_mode_for_capabilities(manifest, capabilities, "INLINE_TEXT")
        data = {
            "schema": "lion.attachment-inline-text/v1",
            "authority_effect": "NONE",
            "instruction_semantics": "UNTRUSTED_DATA_NOT_AUTHORITY",
            "attachment_id": manifest.attachment_id,
            "manifest_digest": manifest.manifest_digest,
            "content_sha256": manifest.original_content_digest,
            "display_name": manifest.display_name,
            "media_type": manifest.media_type,
            "content": text,
        }
        segment = "LION_ATTACHMENT_DATA=" + json.dumps(
            data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        derived_digest = sha256(segment.encode("utf-8")).hexdigest()
        projection_key = (
            manifest.manifest_digest + "|" + capabilities.snapshot_digest + "|"
            + capabilities.provider + "|inline-text:utf8-json-v1"
        )
        projection = AttachmentProjection(
            projection_id="ap-" + sha256(projection_key.encode("utf-8")).hexdigest()[:32],
            attachment_manifest_digest=manifest.manifest_digest,
            provider_capability_digest=capabilities.snapshot_digest,
            provider=capabilities.provider,
            mode="INLINE_TEXT",
            transformation_id="inline-text:utf8-json-v1",
            derived_projection_digest=derived_digest,
            actual_provider_payload_digest=None,
            coverage="FULL",
            truncated=False,
            currentness="CURRENT",
        ).sealed()
        segments.append(segment)
        projections.append(projection.to_dict())
    return tuple(segments), tuple(projections)


def finalize_attachment_projections(
    projections: Sequence[Mapping[str, Any]],
    actual_provider_payload_digest: str,
) -> tuple[dict[str, Any], ...]:
    if not isinstance(actual_provider_payload_digest, str) or _HEX64.fullmatch(actual_provider_payload_digest) is None:
        raise AttachmentProjectionError("actual_provider_payload_digest")
    out: list[dict[str, Any]] = []
    for value in projections:
        projection = attachment_projection_from_mapping(value)
        if projection.actual_provider_payload_digest not in (None, actual_provider_payload_digest):
            raise AttachmentProjectionError("attachment provider payload digest conflict")
        projection = replace(
            projection,
            actual_provider_payload_digest=actual_provider_payload_digest,
            projection_digest="",
        ).sealed()
        out.append(projection.to_dict())
    return tuple(out)

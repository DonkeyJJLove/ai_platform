"""Canonical transport-independent communication envelope for LION v1.5.

CommunicationEnvelope binds semantic message identity and payload provenance.
It does not own transport, delivery, cognition, authority, runtime admission,
or effects. Payload bytes remain external and are referenced by identity and
digest only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

SCHEMA_ID = "lion.communication-envelope/v1"
AUTHORITY_EFFECT = "NONE"
EFFECT = "NONE"
DIGEST_DOMAIN = b"LION/COMMUNICATION-ENVELOPE/1\0"
MAX_RECIPIENTS = 1024

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = frozenset({
    "schema_id",
    "envelope_id",
    "sender_ref",
    "recipient_refs",
    "conversation_ref",
    "mission_ref",
    "correlation_ref",
    "causation_ref",
    "causal_group_ref",
    "payload_schema_ref",
    "payload_ref",
    "payload_digest",
    "created_at",
    "authority_effect",
    "effect",
    "envelope_digest",
})


class CommunicationEnvelopeError(ValueError):
    """Raised when communication-envelope identity or semantics are invalid."""


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CommunicationEnvelopeError("value is not strict JSON") from exc


def _text(value: Any, name: str, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or "\x00" in value:
        raise CommunicationEnvelopeError(f"{name} invalid")
    return value


def _ref(value: Any, name: str, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    value = _text(value, name, maximum=256)
    if _ID.fullmatch(value) is None:
        raise CommunicationEnvelopeError(f"{name} invalid")
    return value


def _hex(value: Any, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise CommunicationEnvelopeError(f"{name} invalid")
    return value


def _utc_timestamp(value: Any, name: str) -> str:
    value = _text(value, name, maximum=64)
    if not value.endswith("Z"):
        raise CommunicationEnvelopeError(f"{name} must use canonical UTC Z form")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise CommunicationEnvelopeError(f"{name} invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise CommunicationEnvelopeError(f"{name} invalid")
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise CommunicationEnvelopeError(f"{name} is not canonical")
    return value


def _recipient_refs(value: Sequence[str]) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise CommunicationEnvelopeError("recipient_refs must be an array")
    refs = tuple(_ref(item, "recipient_ref") for item in value)
    if not refs:
        raise CommunicationEnvelopeError("recipient_refs must not be empty")
    if len(refs) > MAX_RECIPIENTS:
        raise CommunicationEnvelopeError("recipient_refs exceeds bound")
    if len(refs) != len(set(refs)):
        raise CommunicationEnvelopeError("recipient_refs must be unique")
    if refs != tuple(sorted(refs)):
        raise CommunicationEnvelopeError("recipient_refs must be canonical sorted set")
    return refs


@dataclass(frozen=True)
class CommunicationEnvelope:
    schema_id: str
    envelope_id: str
    sender_ref: str
    recipient_refs: tuple[str, ...]
    conversation_ref: str | None
    mission_ref: str | None
    correlation_ref: str
    causation_ref: str | None
    causal_group_ref: str | None
    payload_schema_ref: str
    payload_ref: str
    payload_digest: str
    created_at: str
    authority_effect: str = AUTHORITY_EFFECT
    effect: str = EFFECT
    envelope_digest: str = ""

    def payload_without_digest(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("envelope_digest", None)
        return value

    def compute_digest(self) -> str:
        return sha256(DIGEST_DOMAIN + _canonical_json(self.payload_without_digest())).hexdigest()

    def validate(self, *, require_digest: bool = True) -> "CommunicationEnvelope":
        if self.schema_id != SCHEMA_ID:
            raise CommunicationEnvelopeError("schema_id mismatch")
        _ref(self.envelope_id, "envelope_id")
        _ref(self.sender_ref, "sender_ref")
        _recipient_refs(self.recipient_refs)
        _ref(self.conversation_ref, "conversation_ref", allow_none=True)
        _ref(self.mission_ref, "mission_ref", allow_none=True)
        _ref(self.correlation_ref, "correlation_ref")
        _ref(self.causation_ref, "causation_ref", allow_none=True)
        _ref(self.causal_group_ref, "causal_group_ref", allow_none=True)
        _text(self.payload_schema_ref, "payload_schema_ref")
        _ref(self.payload_ref, "payload_ref")
        _hex(self.payload_digest, "payload_digest")
        _utc_timestamp(self.created_at, "created_at")
        if self.causation_ref == self.envelope_id:
            raise CommunicationEnvelopeError("self-causation denied")
        if self.authority_effect != AUTHORITY_EFFECT:
            raise CommunicationEnvelopeError("communication cannot mint authority")
        if self.effect != EFFECT:
            raise CommunicationEnvelopeError("communication cannot report an effect")
        if require_digest:
            _hex(self.envelope_digest, "envelope_digest")
            if self.envelope_digest != self.compute_digest():
                raise CommunicationEnvelopeError("envelope digest mismatch")
        elif self.envelope_digest:
            _hex(self.envelope_digest, "envelope_digest")
        return self

    def sealed(self) -> "CommunicationEnvelope":
        self.validate(require_digest=False)
        return replace(self, envelope_digest=self.compute_digest()).validate()

    def to_dict(self) -> dict[str, object]:
        self.validate()
        value = asdict(self)
        value["recipient_refs"] = list(self.recipient_refs)
        return value

    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.to_dict())

    @classmethod
    def build(
        cls,
        *,
        envelope_id: str,
        sender_ref: str,
        recipient_refs: Sequence[str],
        conversation_ref: str | None,
        mission_ref: str | None,
        correlation_ref: str,
        causation_ref: str | None,
        causal_group_ref: str | None,
        payload_schema_ref: str,
        payload_ref: str,
        payload_digest: str,
        created_at: str,
    ) -> "CommunicationEnvelope":
        refs = tuple(recipient_refs)
        if len(refs) != len(set(refs)):
            raise CommunicationEnvelopeError("recipient_refs must be unique")
        refs = tuple(sorted(refs))
        return cls(
            schema_id=SCHEMA_ID,
            envelope_id=envelope_id,
            sender_ref=sender_ref,
            recipient_refs=refs,
            conversation_ref=conversation_ref,
            mission_ref=mission_ref,
            correlation_ref=correlation_ref,
            causation_ref=causation_ref,
            causal_group_ref=causal_group_ref,
            payload_schema_ref=payload_schema_ref,
            payload_ref=payload_ref,
            payload_digest=payload_digest,
            created_at=created_at,
        ).sealed()


def communication_envelope_from_mapping(value: Mapping[str, object]) -> CommunicationEnvelope:
    if not isinstance(value, Mapping) or set(value) != _FIELDS:
        raise CommunicationEnvelopeError("communication envelope fields are not exact")
    data = dict(value)
    recipients = data.get("recipient_refs")
    if not isinstance(recipients, (list, tuple)):
        raise CommunicationEnvelopeError("recipient_refs must be an array")
    data["recipient_refs"] = tuple(recipients)
    try:
        return CommunicationEnvelope(**data).validate()
    except TypeError as exc:
        raise CommunicationEnvelopeError("communication envelope field types invalid") from exc

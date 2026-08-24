"""Evidence-only group channel contracts.

The channel transports opaque JSON data to an allowlisted audience.  A valid
message can produce a receipt artifact, but cannot grant authority or mutate the
repository.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

REPOSITORY = "DonkeyJJLove/ai_platform"
ALLOWED_TARGETS = frozenset({"architecture", "security", "runtime"})
MAX_ENVELOPE_BYTES = 8 * 1024
MAX_LIFETIME = timedelta(hours=1)
RECEIPT_STATE = "EMITTED_EVIDENCE_ONLY"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MESSAGE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_ENVELOPE_FIELDS = frozenset({
    "schema_version",
    "repository",
    "message_id",
    "target",
    "expected_master_head",
    "issued_at",
    "expires_at",
    "payload",
    "payload_digest",
    "envelope_digest",
})


class GroupChannelContractError(ValueError):
    """Raised when an evidence-only channel object is not exact."""


def canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise GroupChannelContractError("value is not strict JSON") from exc


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GroupChannelContractError("duplicate JSON object key")
        result[key] = value
    return result


def strict_json_loads(raw: bytes) -> object:
    try:
        text = raw.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                GroupChannelContractError("non-finite JSON number")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GroupChannelContractError("envelope is not strict UTF-8 JSON") from exc


def _utc(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise GroupChannelContractError(f"{name} is not an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise GroupChannelContractError(f"{name} must use explicit UTC offset")
    normalized = parsed.astimezone(timezone.utc)
    if normalized.isoformat() != value:
        raise GroupChannelContractError(f"{name} must use canonical UTC ISO form")
    return normalized


def _payload_digest(payload: object) -> str:
    return sha256(b"LION/GROUP-CHANNEL-PAYLOAD/1\0" + canonical_json(payload)).hexdigest()


@dataclass(frozen=True)
class GroupChannelEnvelope:
    schema_version: str
    repository: str
    message_id: str
    target: str
    expected_master_head: str
    issued_at: str
    expires_at: str
    payload: object
    payload_digest: str
    envelope_digest: str

    def payload_without_envelope_digest(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("envelope_digest")
        return value

    def compute_envelope_digest(self) -> str:
        return sha256(
            b"LION/GROUP-CHANNEL-ENVELOPE/1\0"
            + canonical_json(self.payload_without_envelope_digest())
        ).hexdigest()

    def validate(self, *, now: datetime) -> "GroupChannelEnvelope":
        if self.schema_version != "1.0.0":
            raise GroupChannelContractError("unsupported envelope schema")
        if self.repository != REPOSITORY:
            raise GroupChannelContractError("repository substitution denied")
        if _MESSAGE_ID.fullmatch(self.message_id) is None:
            raise GroupChannelContractError("message_id invalid")
        if self.target not in ALLOWED_TARGETS:
            raise GroupChannelContractError("target is not allowlisted")
        if _SHA40.fullmatch(self.expected_master_head) is None:
            raise GroupChannelContractError("expected master head must be lowercase sha40")
        if _SHA256.fullmatch(self.payload_digest) is None:
            raise GroupChannelContractError("payload digest invalid")
        if _SHA256.fullmatch(self.envelope_digest) is None:
            raise GroupChannelContractError("envelope digest invalid")
        issued = _utc(self.issued_at, "issued_at")
        expires = _utc(self.expires_at, "expires_at")
        if now.tzinfo is None:
            raise GroupChannelContractError("validation clock must be timezone-aware")
        current = now.astimezone(timezone.utc)
        if expires <= issued or expires - issued > MAX_LIFETIME:
            raise GroupChannelContractError("envelope lifetime invalid")
        if current < issued or current >= expires:
            raise GroupChannelContractError("envelope is not currently valid")
        if self.payload_digest != _payload_digest(self.payload):
            raise GroupChannelContractError("payload digest mismatch")
        if self.envelope_digest != self.compute_envelope_digest():
            raise GroupChannelContractError("envelope digest mismatch")
        return self

    @classmethod
    def build(
        cls,
        *,
        repository: str,
        message_id: str,
        target: str,
        expected_master_head: str,
        issued_at: str,
        expires_at: str,
        payload: object,
        now: datetime,
    ) -> "GroupChannelEnvelope":
        values: dict[str, object] = {
            "schema_version": "1.0.0",
            "repository": repository,
            "message_id": message_id,
            "target": target,
            "expected_master_head": expected_master_head,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "payload": payload,
            "payload_digest": _payload_digest(payload),
        }
        envelope_digest = sha256(
            b"LION/GROUP-CHANNEL-ENVELOPE/1\0" + canonical_json(values)
        ).hexdigest()
        return cls(**values, envelope_digest=envelope_digest).validate(now=now)


def encode_envelope(envelope: GroupChannelEnvelope) -> str:
    raw = canonical_json(asdict(envelope))
    if len(raw) > MAX_ENVELOPE_BYTES:
        raise GroupChannelContractError("envelope exceeds 8 KiB")
    return base64.b64encode(raw).decode("ascii")


def decode_envelope(encoded: str, *, now: datetime) -> GroupChannelEnvelope:
    if not isinstance(encoded, str) or not encoded or not encoded.isascii():
        raise GroupChannelContractError("envelope base64 must be non-empty ASCII")
    maximum_encoded = ((MAX_ENVELOPE_BYTES + 2) // 3) * 4
    if len(encoded) > maximum_encoded:
        raise GroupChannelContractError("encoded envelope exceeds bound")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise GroupChannelContractError("envelope base64 invalid") from exc
    if base64.b64encode(raw).decode("ascii") != encoded:
        raise GroupChannelContractError("envelope base64 is not canonical")
    if not raw or len(raw) > MAX_ENVELOPE_BYTES:
        raise GroupChannelContractError("decoded envelope size invalid")
    value = strict_json_loads(raw)
    if not isinstance(value, dict) or set(value) != _ENVELOPE_FIELDS:
        raise GroupChannelContractError("envelope fields are not exact")
    if canonical_json(value) != raw:
        raise GroupChannelContractError("envelope JSON is not canonical")
    try:
        envelope = GroupChannelEnvelope(**value)
    except TypeError as exc:
        raise GroupChannelContractError("envelope field types invalid") from exc
    return envelope.validate(now=now)


@dataclass(frozen=True)
class GroupChannelReceipt:
    schema_version: str
    repository: str
    message_id: str
    target: str
    expected_master_head: str
    envelope_digest: str
    payload_digest: str
    emitted_at: str
    workflow_run_id: int
    workflow_run_attempt: int
    state: str
    authority_effect: bool
    repository_effect: bool
    receipt_digest: str

    def payload_without_receipt_digest(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("receipt_digest")
        return value

    def validate(self) -> "GroupChannelReceipt":
        if self.schema_version != "1.0.0" or self.repository != REPOSITORY:
            raise GroupChannelContractError("receipt identity invalid")
        if _MESSAGE_ID.fullmatch(self.message_id) is None or self.target not in ALLOWED_TARGETS:
            raise GroupChannelContractError("receipt routing invalid")
        if _SHA40.fullmatch(self.expected_master_head) is None:
            raise GroupChannelContractError("receipt head invalid")
        for value in (self.envelope_digest, self.payload_digest, self.receipt_digest):
            if _SHA256.fullmatch(value) is None:
                raise GroupChannelContractError("receipt digest invalid")
        _utc(self.emitted_at, "emitted_at")
        if (
            isinstance(self.workflow_run_id, bool)
            or not isinstance(self.workflow_run_id, int)
            or self.workflow_run_id <= 0
            or isinstance(self.workflow_run_attempt, bool)
            or not isinstance(self.workflow_run_attempt, int)
            or self.workflow_run_attempt <= 0
        ):
            raise GroupChannelContractError("workflow run binding invalid")
        if self.state != RECEIPT_STATE:
            raise GroupChannelContractError("receipt is not evidence-only")
        if self.authority_effect is not False or self.repository_effect is not False:
            raise GroupChannelContractError("receipt cannot report an effect")
        expected = sha256(
            b"LION/GROUP-CHANNEL-RECEIPT/1\0"
            + canonical_json(self.payload_without_receipt_digest())
        ).hexdigest()
        if self.receipt_digest != expected:
            raise GroupChannelContractError("receipt digest mismatch")
        return self

    @classmethod
    def build(
        cls,
        *,
        envelope: GroupChannelEnvelope,
        emitted_at: str,
        workflow_run_id: int,
        workflow_run_attempt: int,
    ) -> "GroupChannelReceipt":
        values: dict[str, object] = {
            "schema_version": "1.0.0",
            "repository": envelope.repository,
            "message_id": envelope.message_id,
            "target": envelope.target,
            "expected_master_head": envelope.expected_master_head,
            "envelope_digest": envelope.envelope_digest,
            "payload_digest": envelope.payload_digest,
            "emitted_at": emitted_at,
            "workflow_run_id": workflow_run_id,
            "workflow_run_attempt": workflow_run_attempt,
            "state": RECEIPT_STATE,
            "authority_effect": False,
            "repository_effect": False,
        }
        receipt_digest = sha256(
            b"LION/GROUP-CHANNEL-RECEIPT/1\0" + canonical_json(values)
        ).hexdigest()
        return cls(**values, receipt_digest=receipt_digest).validate()


def receipt_json(receipt: GroupChannelReceipt) -> bytes:
    receipt.validate()
    return canonical_json(asdict(receipt)) + b"\n"


def envelope_from_mapping(value: Mapping[str, object], *, now: datetime) -> GroupChannelEnvelope:
    """Test/support adapter that retains the exact-field contract."""
    if set(value) != _ENVELOPE_FIELDS:
        raise GroupChannelContractError("envelope fields are not exact")
    try:
        return GroupChannelEnvelope(**dict(value)).validate(now=now)
    except TypeError as exc:
        raise GroupChannelContractError("envelope field types invalid") from exc

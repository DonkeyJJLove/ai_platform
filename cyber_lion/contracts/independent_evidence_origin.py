"""Immutable signed origin receipt for independently produced certification evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Any

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SIG = re.compile(r"^[0-9a-f]{512}$")
ORIGIN_KINDS = frozenset({"REPOSITORY_CURRENTNESS", "CANDIDATE_TREE", "PRE_SCHEMA", "SNAPSHOT"})
ORIGIN_RECEIPT_DOMAIN = b"LION/INDEPENDENT-EVIDENCE-ORIGIN-RECEIPT/1\0"
ORIGIN_SIGNATURE_DOMAIN = b"LION/INDEPENDENT-EVIDENCE-ORIGIN-SIGNATURE/1\0"


class IndependentEvidenceOriginContractError(ValueError):
    pass


def _text(value: Any, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise IndependentEvidenceOriginContractError(f"{name} invalid")
    return value


def _sha256_text(value: Any, name: str) -> str:
    value = _text(value, name, 64)
    if not _SHA256.fullmatch(value):
        raise IndependentEvidenceOriginContractError(f"{name} must be sha256")
    return value


def _utc(value: Any, name: str) -> None:
    value = _text(value, name, 128)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IndependentEvidenceOriginContractError(f"{name} invalid") from exc
    if parsed.tzinfo is None:
        raise IndependentEvidenceOriginContractError(f"{name} must be timezone aware")


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class IndependentEvidenceOriginReceipt:
    provider_id: str
    provider_instance_id: str
    trust_anchor_id: str
    algorithm: str
    observation_id: str
    observation_kind: str
    observed_object_identity: str
    observed_object_digest: str
    payload_digest: str
    issued_at: str
    nonce: str
    receipt_digest: str
    signature_hex: str

    def unsigned_wire(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_instance_id": self.provider_instance_id,
            "trust_anchor_id": self.trust_anchor_id,
            "algorithm": self.algorithm,
            "observation_id": self.observation_id,
            "observation_kind": self.observation_kind,
            "observed_object_identity": self.observed_object_identity,
            "observed_object_digest": self.observed_object_digest,
            "payload_digest": self.payload_digest,
            "issued_at": self.issued_at,
            "nonce": self.nonce,
        }

    def validate(self) -> "IndependentEvidenceOriginReceipt":
        for name in (
            "provider_id",
            "provider_instance_id",
            "trust_anchor_id",
            "algorithm",
            "observation_id",
            "observed_object_identity",
        ):
            _text(getattr(self, name), name)
        if self.observation_kind not in ORIGIN_KINDS:
            raise IndependentEvidenceOriginContractError("observation_kind invalid")
        _sha256_text(self.observed_object_digest, "observed_object_digest")
        _sha256_text(self.payload_digest, "payload_digest")
        _sha256_text(self.nonce, "nonce")
        _utc(self.issued_at, "issued_at")
        expected = sha256(ORIGIN_RECEIPT_DOMAIN + _canon(self.unsigned_wire())).hexdigest()
        if self.receipt_digest != expected:
            raise IndependentEvidenceOriginContractError("origin receipt digest mismatch")
        if not _SIG.fullmatch(self.signature_hex):
            raise IndependentEvidenceOriginContractError("origin signature shape invalid")
        return self

    def digest(self) -> str:
        self.validate()
        return self.receipt_digest

    def signing_bytes(self) -> bytes:
        self.validate()
        return ORIGIN_SIGNATURE_DOMAIN + bytes.fromhex(self.receipt_digest)


def origin_receipt_digest(
    *,
    provider_id: str,
    provider_instance_id: str,
    trust_anchor_id: str,
    algorithm: str,
    observation_id: str,
    observation_kind: str,
    observed_object_identity: str,
    observed_object_digest: str,
    payload_digest: str,
    issued_at: str,
    nonce: str,
) -> str:
    candidate = IndependentEvidenceOriginReceipt(
        provider_id,
        provider_instance_id,
        trust_anchor_id,
        algorithm,
        observation_id,
        observation_kind,
        observed_object_identity,
        observed_object_digest,
        payload_digest,
        issued_at,
        nonce,
        "0" * 64,
        "0" * 512,
    )
    wire = candidate.unsigned_wire()
    for name in ("provider_id", "provider_instance_id", "trust_anchor_id", "algorithm", "observation_id", "observed_object_identity"):
        _text(wire[name], name)
    if observation_kind not in ORIGIN_KINDS:
        raise IndependentEvidenceOriginContractError("observation_kind invalid")
    _sha256_text(observed_object_digest, "observed_object_digest")
    _sha256_text(payload_digest, "payload_digest")
    _sha256_text(nonce, "nonce")
    _utc(issued_at, "issued_at")
    return sha256(ORIGIN_RECEIPT_DOMAIN + _canon(wire)).hexdigest()

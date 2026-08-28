"""Immutable signed origin receipt and external-producer provisioning contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Any

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SIG = re.compile(r"^[0-9a-f]{512}$")
ORIGIN_KINDS = frozenset({"REPOSITORY_CURRENTNESS", "CANDIDATE_TREE", "PRE_SCHEMA", "SNAPSHOT"})
ORIGIN_RECEIPT_DOMAIN = b"LION/INDEPENDENT-EVIDENCE-ORIGIN-RECEIPT/1\0"
ORIGIN_SIGNATURE_DOMAIN = b"LION/INDEPENDENT-EVIDENCE-ORIGIN-SIGNATURE/1\0"

EXTERNAL_PRODUCER_REPOSITORY = "DonkeyJJLove/ai_platform"
EXTERNAL_PRODUCER_CONTROL_DOMAIN_CLASS = "EXTERNAL_SEPARATE_CONTROL_DOMAIN"
EXTERNAL_PRODUCER_KEY_STORAGE_CLASS = "NON_EXPORTABLE_EXTERNAL_KEYSTORE"
EXTERNAL_PRODUCER_PROVENANCE_CLASS = "PRODUCTION_EXTERNAL"
EXTERNAL_PRODUCER_HANDOFF_OPERATION = "EXTERNAL_EVIDENCE_PRODUCER_HANDOFF"


class IndependentEvidenceOriginContractError(ValueError):
    pass


def _text(value: Any, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise IndependentEvidenceOriginContractError(f"{name} invalid")
    return value


def _sha40_text(value: Any, name: str) -> str:
    value = _text(value, name, 40)
    if not _SHA40.fullmatch(value):
        raise IndependentEvidenceOriginContractError(f"{name} must be sha40")
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


@dataclass(frozen=True)
class ExternalEvidenceProducerProfile:
    producer_id: str
    trust_anchor_id: str
    algorithm: str
    public_key_sha256: str
    control_domain_class: str
    key_storage_class: str
    provenance_class: str
    provider_bindings: tuple[tuple[str, str], ...]
    key_material_exportable: bool
    key_material_on_lion_host: bool
    key_material_in_repository: bool
    consumer_can_sign: bool

    def validate(self) -> "ExternalEvidenceProducerProfile":
        for name in ("producer_id", "trust_anchor_id", "algorithm"):
            _text(getattr(self, name), name)
        _sha256_text(self.public_key_sha256, "public_key_sha256")
        if self.control_domain_class != EXTERNAL_PRODUCER_CONTROL_DOMAIN_CLASS:
            raise IndependentEvidenceOriginContractError("producer control domain must be externally separated")
        if self.key_storage_class != EXTERNAL_PRODUCER_KEY_STORAGE_CLASS:
            raise IndependentEvidenceOriginContractError("producer key storage must be non-exportable external keystore")
        if self.provenance_class != EXTERNAL_PRODUCER_PROVENANCE_CLASS:
            raise IndependentEvidenceOriginContractError("producer provenance must be production external")
        if type(self.provider_bindings) is not tuple or len(self.provider_bindings) != len(ORIGIN_KINDS):
            raise IndependentEvidenceOriginContractError("producer provider bindings incomplete")
        kinds: list[str] = []
        providers: list[str] = []
        for row in self.provider_bindings:
            if type(row) is not tuple or len(row) != 2:
                raise IndependentEvidenceOriginContractError("producer provider binding invalid")
            kind, provider = row
            if kind not in ORIGIN_KINDS:
                raise IndependentEvidenceOriginContractError("producer origin kind invalid")
            _text(provider, "provider_id")
            kinds.append(kind)
            providers.append(provider)
        if len(kinds) != len(set(kinds)) or set(kinds) != set(ORIGIN_KINDS):
            raise IndependentEvidenceOriginContractError("producer provider binding cardinality invalid")
        if len(providers) != len(set(providers)):
            raise IndependentEvidenceOriginContractError("producer provider identities must be distinct")
        for name in (
            "key_material_exportable",
            "key_material_on_lion_host",
            "key_material_in_repository",
            "consumer_can_sign",
        ):
            if getattr(self, name) is not False:
                raise IndependentEvidenceOriginContractError(f"{name} must be false")
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(
            b"LION/EXTERNAL-EVIDENCE-PRODUCER-PROFILE/1\0" + _canon(asdict(self))
        ).hexdigest()


@dataclass(frozen=True)
class ExternalEvidenceProducerProvisioningRequest:
    request_id: str
    repository: str
    candidate_sha: str
    candidate_tree: str
    profile_digest: str
    requester_subject_id: str
    consumer_subject_id: str
    requested_at: str

    def validate(self) -> "ExternalEvidenceProducerProvisioningRequest":
        _text(self.request_id, "request_id")
        if self.repository != EXTERNAL_PRODUCER_REPOSITORY:
            raise IndependentEvidenceOriginContractError("producer provisioning repository mismatch")
        _sha40_text(self.candidate_sha, "candidate_sha")
        _sha40_text(self.candidate_tree, "candidate_tree")
        _sha256_text(self.profile_digest, "profile_digest")
        _text(self.requester_subject_id, "requester_subject_id")
        _text(self.consumer_subject_id, "consumer_subject_id")
        if self.requester_subject_id == self.consumer_subject_id:
            raise IndependentEvidenceOriginContractError("requester/consumer separation required")
        _utc(self.requested_at, "requested_at")
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(
            b"LION/EXTERNAL-EVIDENCE-PRODUCER-PROVISIONING-REQUEST/1\0" + _canon(asdict(self))
        ).hexdigest()


@dataclass(frozen=True)
class ExternalEvidenceProducerObservation:
    producer_id: str
    producer_instance_id: str
    producer_subject_id: str
    trust_anchor_id: str
    algorithm: str
    public_key_sha256: str
    control_domain_class: str
    key_storage_class: str
    provenance_class: str
    provider_bindings: tuple[tuple[str, str], ...]
    key_material_exportable: bool
    key_material_on_lion_host: bool
    key_material_in_repository: bool
    consumer_can_sign: bool
    producer_ready: bool
    observation_channel_ready: bool
    observed_at: str

    def profile(self) -> ExternalEvidenceProducerProfile:
        return ExternalEvidenceProducerProfile(
            self.producer_id,
            self.trust_anchor_id,
            self.algorithm,
            self.public_key_sha256,
            self.control_domain_class,
            self.key_storage_class,
            self.provenance_class,
            self.provider_bindings,
            self.key_material_exportable,
            self.key_material_on_lion_host,
            self.key_material_in_repository,
            self.consumer_can_sign,
        ).validate()

    def validate(self) -> "ExternalEvidenceProducerObservation":
        self.profile()
        _text(self.producer_instance_id, "producer_instance_id")
        _text(self.producer_subject_id, "producer_subject_id")
        if type(self.producer_ready) is not bool or type(self.observation_channel_ready) is not bool:
            raise IndependentEvidenceOriginContractError("producer readiness flags must be bool")
        _utc(self.observed_at, "observed_at")
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(
            b"LION/EXTERNAL-EVIDENCE-PRODUCER-OBSERVATION/1\0" + _canon(asdict(self))
        ).hexdigest()


@dataclass(frozen=True)
class ExternalEvidenceProducerProvisioningReceipt:
    receipt_id: str
    request_digest: str
    profile_digest: str
    observation_digest: str
    producer_instance_id: str
    producer_subject_id: str
    operation: str
    evidence_only: bool
    effect_authority: bool
    secret_material_present: bool
    issued_at: str
    receipt_digest: str

    def validate(self) -> "ExternalEvidenceProducerProvisioningReceipt":
        _text(self.receipt_id, "receipt_id")
        for name in ("request_digest", "profile_digest", "observation_digest"):
            _sha256_text(getattr(self, name), name)
        _text(self.producer_instance_id, "producer_instance_id")
        _text(self.producer_subject_id, "producer_subject_id")
        if self.operation != EXTERNAL_PRODUCER_HANDOFF_OPERATION:
            raise IndependentEvidenceOriginContractError("producer provisioning operation invalid")
        if self.evidence_only is not True or self.effect_authority is not False or self.secret_material_present is not False:
            raise IndependentEvidenceOriginContractError("producer provisioning receipt may carry evidence only")
        _utc(self.issued_at, "issued_at")
        expected = sha256(
            b"LION/EXTERNAL-EVIDENCE-PRODUCER-PROVISIONING-RECEIPT/1\0"
            + _canon({k: v for k, v in asdict(self).items() if k != "receipt_digest"})
        ).hexdigest()
        if self.receipt_digest != expected:
            raise IndependentEvidenceOriginContractError("producer provisioning receipt digest mismatch")
        return self

    def sealed(self) -> "ExternalEvidenceProducerProvisioningReceipt":
        digest = sha256(
            b"LION/EXTERNAL-EVIDENCE-PRODUCER-PROVISIONING-RECEIPT/1\0"
            + _canon({k: v for k, v in asdict(self).items() if k != "receipt_digest"})
        ).hexdigest()
        return replace(self, receipt_digest=digest).validate()

    def digest(self) -> str:
        self.validate()
        return self.receipt_digest

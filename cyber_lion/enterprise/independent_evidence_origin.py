"""Pinned verifier and fail-closed provisioning boundary for independent evidence origins.

This module contains public verification material only. It intentionally exposes no signer,
private key, provider-capability mint, environment lookup, network lookup, or callback verifier.
External-producer provisioning here means validation and evidence handoff only; it does not
materialize credentials, create a keystore, or execute an external provisioning effect.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from hmac import compare_digest

from cyber_lion.contracts.host_authority_separation import (
    CANONICAL_REPOSITORY_PROVIDER,
    CANONICAL_SNAPSHOTTER_IDENTITY,
)
from cyber_lion.contracts.independent_evidence_origin import (
    EXTERNAL_PRODUCER_CONTROL_DOMAIN_CLASS,
    EXTERNAL_PRODUCER_HANDOFF_OPERATION,
    EXTERNAL_PRODUCER_KEY_STORAGE_CLASS,
    EXTERNAL_PRODUCER_PROVENANCE_CLASS,
    EXTERNAL_PRODUCER_REPOSITORY,
    ExternalEvidenceProducerObservation,
    ExternalEvidenceProducerProfile,
    ExternalEvidenceProducerProvisioningReceipt,
    ExternalEvidenceProducerProvisioningRequest,
    IndependentEvidenceOriginReceipt,
)

CANONICAL_ORIGIN_TRUST_ANCHOR_ID = "lion-e006-independent-evidence-origin-root/v1"
CANONICAL_ORIGIN_ALGORITHM = "rsa-pkcs1v15-sha256"
CANDIDATE_TREE_PROVIDER = "git-object-candidate-tree/v1"
SCHEMA_MANIFEST_PROVIDER = "sqlite-master-schema-observer/v1"

ORIGIN_REPOSITORY_CURRENTNESS = "REPOSITORY_CURRENTNESS"
ORIGIN_CANDIDATE_TREE = "CANDIDATE_TREE"
ORIGIN_PRE_SCHEMA = "PRE_SCHEMA"
ORIGIN_SNAPSHOT = "SNAPSHOT"

_EXPECTED_PROVIDER = {
    ORIGIN_REPOSITORY_CURRENTNESS: CANONICAL_REPOSITORY_PROVIDER,
    ORIGIN_CANDIDATE_TREE: CANDIDATE_TREE_PROVIDER,
    ORIGIN_PRE_SCHEMA: SCHEMA_MANIFEST_PROVIDER,
    ORIGIN_SNAPSHOT: CANONICAL_SNAPSHOTTER_IDENTITY,
}

_RSA_N = int(
    "98c406996bc19f10cca0e700b9f6a0e19136ed8435f1d97ee7d1d7c81b13521a1bd869b7b4919bb956b832b3559e2f647b2b90ff76c8c7eb7922e8aa84ec6afdcb02395fbc2942839e0fb743b32a10369dab7135903bc820020d8696cb8362d8809db35f2831ca9aa28b94d44ba7d9744a76458f6206139925535706058799497358cdf9a27361c43772fead717d45ecee0be2e193fdd92a27ec0d05f70ccd8a007197d7c8dbaec9f4f7b80695d4277614bcf8a2f1d493f9e9230c8c2f722f836bad7b84186bc816afbfe8e1ad813718899530d4681bb5ddc28fd0c206239f00743e5473c5599b8750eb04b67657226e84691b8f37048cebf1249ef9bbf3721d",
    16,
)
_RSA_E = 65537
_SHA256_DIGESTINFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")

CANONICAL_EXTERNAL_PRODUCER_ID = "lion-independent-evidence-producer/v1"
CANONICAL_ORIGIN_PUBLIC_KEY_SHA256 = "f822bed0c7ea1d9ff7e591bc930ce5b56a118c73663196bc1a21a31c4b00b779"
CANONICAL_PROVIDER_BINDINGS = tuple(_EXPECTED_PROVIDER.items())


class IndependentEvidenceOriginError(ValueError):
    pass


def _verify_rsa_pkcs1v15_sha256(message: bytes, signature_hex: str) -> bool:
    try:
        signature = bytes.fromhex(signature_hex)
    except ValueError:
        return False
    width = (_RSA_N.bit_length() + 7) // 8
    if len(signature) != width:
        return False
    value = int.from_bytes(signature, "big")
    if value <= 0 or value >= _RSA_N:
        return False
    encoded = pow(value, _RSA_E, _RSA_N).to_bytes(width, "big")
    digest_info = _SHA256_DIGESTINFO_PREFIX + sha256(message).digest()
    padding_len = width - len(digest_info) - 3
    if padding_len < 8:
        return False
    expected = b"\x00\x01" + (b"\xff" * padding_len) + b"\x00" + digest_info
    return compare_digest(encoded, expected)


def verify_independent_evidence_origin(
    receipt: IndependentEvidenceOriginReceipt,
    *,
    observation_kind: str,
    observed_object_identity: str,
    observed_object_digest: str,
    payload_digest: str,
) -> IndependentEvidenceOriginReceipt:
    if type(receipt) is not IndependentEvidenceOriginReceipt:
        raise IndependentEvidenceOriginError("independent origin receipt required")
    receipt.validate()
    expected_provider = _EXPECTED_PROVIDER.get(observation_kind)
    if expected_provider is None:
        raise IndependentEvidenceOriginError("unknown evidence origin kind")
    if receipt.observation_kind != observation_kind:
        raise IndependentEvidenceOriginError("cross-origin receipt confusion denied")
    if receipt.provider_id != expected_provider:
        raise IndependentEvidenceOriginError("evidence provider substitution denied")
    if receipt.trust_anchor_id != CANONICAL_ORIGIN_TRUST_ANCHOR_ID:
        raise IndependentEvidenceOriginError("origin trust-anchor substitution denied")
    if receipt.algorithm != CANONICAL_ORIGIN_ALGORITHM:
        raise IndependentEvidenceOriginError("origin verifier substitution denied")
    if receipt.observed_object_identity != observed_object_identity:
        raise IndependentEvidenceOriginError("observed object identity mismatch")
    if receipt.observed_object_digest != observed_object_digest:
        raise IndependentEvidenceOriginError("observed object digest mismatch")
    if receipt.payload_digest != payload_digest:
        raise IndependentEvidenceOriginError("origin payload digest mismatch")
    if not _verify_rsa_pkcs1v15_sha256(receipt.signing_bytes(), receipt.signature_hex):
        raise IndependentEvidenceOriginError("independent origin signature invalid")
    return receipt


def origin_public_key_fingerprint() -> str:
    width = (_RSA_N.bit_length() + 7) // 8
    modulus = _RSA_N.to_bytes(width, "big")
    exponent_width = max(1, (_RSA_E.bit_length() + 7) // 8)
    exponent = _RSA_E.to_bytes(exponent_width, "big")
    return sha256(
        b"LION/RSA-PUBLIC/1\0"
        + len(modulus).to_bytes(2, "big")
        + modulus
        + len(exponent).to_bytes(2, "big")
        + exponent
    ).hexdigest()


if origin_public_key_fingerprint() != CANONICAL_ORIGIN_PUBLIC_KEY_SHA256:
    raise RuntimeError("canonical origin public-key fingerprint drift")


def canonical_external_evidence_producer_profile() -> ExternalEvidenceProducerProfile:
    return ExternalEvidenceProducerProfile(
        producer_id=CANONICAL_EXTERNAL_PRODUCER_ID,
        trust_anchor_id=CANONICAL_ORIGIN_TRUST_ANCHOR_ID,
        algorithm=CANONICAL_ORIGIN_ALGORITHM,
        public_key_sha256=CANONICAL_ORIGIN_PUBLIC_KEY_SHA256,
        control_domain_class=EXTERNAL_PRODUCER_CONTROL_DOMAIN_CLASS,
        key_storage_class=EXTERNAL_PRODUCER_KEY_STORAGE_CLASS,
        provenance_class=EXTERNAL_PRODUCER_PROVENANCE_CLASS,
        provider_bindings=CANONICAL_PROVIDER_BINDINGS,
        key_material_exportable=False,
        key_material_on_lion_host=False,
        key_material_in_repository=False,
        consumer_can_sign=False,
    ).validate()


def derive_external_evidence_producer_provisioning_request(
    *,
    request_id: str,
    candidate_sha: str,
    candidate_tree: str,
    requester_subject_id: str,
    consumer_subject_id: str,
    requested_at: str,
) -> ExternalEvidenceProducerProvisioningRequest:
    profile = canonical_external_evidence_producer_profile()
    return ExternalEvidenceProducerProvisioningRequest(
        request_id=request_id,
        repository=EXTERNAL_PRODUCER_REPOSITORY,
        candidate_sha=candidate_sha,
        candidate_tree=candidate_tree,
        profile_digest=profile.digest(),
        requester_subject_id=requester_subject_id,
        consumer_subject_id=consumer_subject_id,
        requested_at=requested_at,
    ).validate()


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IndependentEvidenceOriginError("producer provisioning timestamp invalid") from exc
    if parsed.tzinfo is None:
        raise IndependentEvidenceOriginError("producer provisioning timestamp must be timezone aware")
    return parsed


class ExternalEvidenceProducerProvisioningBoundary:
    """Pure admission boundary for an externally materialized evidence producer.

    It validates externally observed state and emits evidence-only handoff metadata. It cannot
    create the external producer, provision a keystore, mint signing capability, or execute an
    observation. Operational provisioning must occur in a separately controlled domain.
    """

    @staticmethod
    def admit(
        request: ExternalEvidenceProducerProvisioningRequest,
        observation: ExternalEvidenceProducerObservation,
        *,
        expected_candidate_sha: str,
        expected_candidate_tree: str,
        issued_at: str,
    ) -> ExternalEvidenceProducerProvisioningReceipt:
        if type(request) is not ExternalEvidenceProducerProvisioningRequest:
            raise IndependentEvidenceOriginError("producer provisioning request required")
        if type(observation) is not ExternalEvidenceProducerObservation:
            raise IndependentEvidenceOriginError("external producer observation required")
        request.validate()
        observation.validate()
        profile = canonical_external_evidence_producer_profile()
        if request.profile_digest != profile.digest():
            raise IndependentEvidenceOriginError("producer profile substitution denied")
        if request.candidate_sha != expected_candidate_sha or request.candidate_tree != expected_candidate_tree:
            raise IndependentEvidenceOriginError("producer provisioning candidate currentness mismatch")
        if observation.profile() != profile:
            raise IndependentEvidenceOriginError("observed producer profile substitution denied")
        if observation.producer_ready is not True or observation.observation_channel_ready is not True:
            raise IndependentEvidenceOriginError("external producer not independently observable and ready")
        if observation.producer_subject_id in {request.requester_subject_id, request.consumer_subject_id}:
            raise IndependentEvidenceOriginError("producer/requester/consumer role separation required")
        issued = _time(issued_at)
        if not (_time(request.requested_at) <= _time(observation.observed_at) <= issued):
            raise IndependentEvidenceOriginError("producer provisioning chronology invalid")
        return ExternalEvidenceProducerProvisioningReceipt(
            receipt_id=f"external-producer:{request.digest()}",
            request_digest=request.digest(),
            profile_digest=profile.digest(),
            observation_digest=observation.digest(),
            producer_instance_id=observation.producer_instance_id,
            producer_subject_id=observation.producer_subject_id,
            operation=EXTERNAL_PRODUCER_HANDOFF_OPERATION,
            evidence_only=True,
            effect_authority=False,
            secret_material_present=False,
            issued_at=issued_at,
            receipt_digest="0" * 64,
        ).sealed()

    @staticmethod
    def verify_provisioned_origin(
        receipt: IndependentEvidenceOriginReceipt,
        provisioning_receipt: ExternalEvidenceProducerProvisioningReceipt,
        observation: ExternalEvidenceProducerObservation,
        *,
        observation_kind: str,
        observed_object_identity: str,
        observed_object_digest: str,
        payload_digest: str,
    ) -> IndependentEvidenceOriginReceipt:
        if type(provisioning_receipt) is not ExternalEvidenceProducerProvisioningReceipt:
            raise IndependentEvidenceOriginError("external producer provisioning receipt required")
        if type(observation) is not ExternalEvidenceProducerObservation:
            raise IndependentEvidenceOriginError("external producer observation required")
        if type(receipt) is not IndependentEvidenceOriginReceipt:
            raise IndependentEvidenceOriginError("independent origin receipt required")
        provisioning_receipt.validate()
        observation.validate()
        profile = canonical_external_evidence_producer_profile()
        if provisioning_receipt.profile_digest != profile.digest():
            raise IndependentEvidenceOriginError("provisioned producer profile mismatch")
        if provisioning_receipt.observation_digest != observation.digest():
            raise IndependentEvidenceOriginError("producer observation substitution denied")
        if observation.profile() != profile:
            raise IndependentEvidenceOriginError("observed producer profile substitution denied")
        if (
            provisioning_receipt.producer_instance_id != observation.producer_instance_id
            or provisioning_receipt.producer_subject_id != observation.producer_subject_id
        ):
            raise IndependentEvidenceOriginError("producer identity handoff mismatch")
        if receipt.provider_instance_id != observation.producer_instance_id:
            raise IndependentEvidenceOriginError("origin receipt not produced by provisioned instance")
        expected_provider = _EXPECTED_PROVIDER.get(observation_kind)
        if expected_provider is None or receipt.provider_id != expected_provider:
            raise IndependentEvidenceOriginError("origin provider not bound to provisioned profile")
        return verify_independent_evidence_origin(
            receipt,
            observation_kind=observation_kind,
            observed_object_identity=observed_object_identity,
            observed_object_digest=observed_object_digest,
            payload_digest=payload_digest,
        )

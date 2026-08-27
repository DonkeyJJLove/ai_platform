"""Pinned verifier for independently produced evidence-origin receipts.

This module contains a public verification key only.  It intentionally exposes no signer,
private key, provider-capability mint, environment lookup, network lookup, or callback verifier.
"""
from __future__ import annotations

from hashlib import sha256
from hmac import compare_digest

from cyber_lion.contracts.host_authority_separation import (
    CANONICAL_REPOSITORY_PROVIDER,
    CANONICAL_SNAPSHOTTER_IDENTITY,
)
from cyber_lion.contracts.independent_evidence_origin import IndependentEvidenceOriginReceipt

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

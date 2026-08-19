from __future__ import annotations
import dataclasses
from datetime import datetime, timezone
import hashlib
import hmac
import unittest

from cyber_lion.contracts.identity import EntityIdentity
from cyber_lion.contracts.workload_identity import (
    VerifiedWorkloadIdentity, WorkloadIdentityContext, WorkloadIdentityError,
    WorkloadIdentityProof, verify_workload_identity,
)
SECRET = b"test-only-not-production"
NOW = datetime(2026, 8, 19, 14, 0, tzinfo=timezone.utc)
CONTEXT = WorkloadIdentityContext(
    "cyber-lion.test", "tenant:a", "org:a", "cyber-lion-control-plane", "test",
    "DonkeyJJLove/ai_platform", "d3a0278be74d96221e15ccc165cf046e9f77a389", "issuer:test",
)

def unsigned() -> WorkloadIdentityProof:
    return WorkloadIdentityProof(
        "1.0.0", "proof:1", "workload:builder", "cyber-lion.test", "tenant:a",
        "org:a", "cyber-lion-control-plane", "test", "DonkeyJJLove/ai_platform",
        "d3a0278be74d96221e15ccc165cf046e9f77a389", "issuer:test", "key:test",
        "TEST-HMAC-SHA256", "2026-08-19T13:00:00Z", "2026-08-19T15:00:00Z", "pending",
    )

def signed(proof: WorkloadIdentityProof | None = None) -> WorkloadIdentityProof:
    proof = proof or unsigned()
    signature = hmac.new(SECRET, proof.canonical_payload(), hashlib.sha256).hexdigest()
    return dataclasses.replace(proof, signature=signature)

def verifier(payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
    if (key_id, algorithm) != ("key:test", "TEST-HMAC-SHA256"):
        return False
    expected = hmac.new(SECRET, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)

def verify(proof, checker=verifier, *, now=NOW, context=CONTEXT):
    return verify_workload_identity(proof, checker, now=now, context=context)

class WorkloadIdentityTests(unittest.TestCase):
    def test_valid_proof_returns_verified_identity_without_authority(self):
        verified = verify(signed())
        self.assertIsInstance(verified, VerifiedWorkloadIdentity)
        self.assertEqual(verified.subject_id, "workload:builder")
        self.assertFalse(hasattr(verified, "authority"))
        self.assertFalse(hasattr(verified, "capabilities"))

    def test_signed_field_tampering_fails_closed(self):
        base = signed()
        mutations = {
            "subject_id": "workload:other", "trust_domain": "other.test",
            "tenant_id": "tenant:b", "organization_id": "org:b", "audience": "other",
            "repository": "DonkeyJJLove/other", "vcs_ref": "0" * 40,
        }
        for field, value in mutations.items():
            with self.subTest(field=field), self.assertRaises(WorkloadIdentityError):
                verify(dataclasses.replace(base, **{field: value}))

    def test_valid_wrong_context_credentials_are_rejected(self):
        mutations = {
            "trust_domain": "other.test", "tenant_id": "tenant:b", "organization_id": "org:b",
            "audience": "other", "environment": "prod", "repository": "DonkeyJJLove/other",
            "vcs_ref": "0" * 40, "issuer_id": "issuer:other",
        }
        for field, value in mutations.items():
            proof = signed(dataclasses.replace(unsigned(), **{field: value}))
            with self.subTest(field=field), self.assertRaises(WorkloadIdentityError):
                verify(proof)

    def test_expired_and_not_yet_valid_proofs_are_rejected(self):
        proof = signed()
        with self.assertRaises(WorkloadIdentityError):
            verify(proof, now=datetime(2026, 8, 19, 15, 0, tzinfo=timezone.utc))
        with self.assertRaises(WorkloadIdentityError):
            verify(proof, now=datetime(2026, 8, 19, 12, 59, tzinfo=timezone.utc))

    def test_verifier_false_and_exception_fail_closed(self):
        with self.assertRaises(WorkloadIdentityError):
            verify(signed(), lambda *_: False)
        def broken(*_):
            raise RuntimeError("provider unavailable")
        with self.assertRaises(WorkloadIdentityError):
            verify(signed(), broken)

    def test_key_algorithm_confusion_and_invalid_shape_are_rejected(self):
        base = signed()
        for mutation in (
            {"key_id": "key:other"}, {"algorithm": "OTHER"}, {"repository": "not-a-repo"},
            {"issued_at": "2026-08-19T13:00:00"}, {"expires_at": "2026-08-19T12:00:00Z"},
        ):
            with self.assertRaises(WorkloadIdentityError):
                verify(dataclasses.replace(base, **mutation))

    def test_runtime_matches_schema_type_and_length_bounds(self):
        limits = {
            "proof_id": 256, "subject_id": 256, "trust_domain": 256, "tenant_id": 256,
            "organization_id": 256, "audience": 256, "environment": 128, "vcs_ref": 256,
            "issuer_id": 256, "key_id": 256, "algorithm": 128, "signature": 8192,
        }
        for field, limit in limits.items():
            with self.subTest(field=field), self.assertRaises(WorkloadIdentityError):
                dataclasses.replace(unsigned(), **{field: "x" * (limit + 1)}).validate()
        with self.assertRaises(WorkloadIdentityError):
            dataclasses.replace(unsigned(), subject_id=7).validate()

    def test_descriptive_entity_identity_is_not_verified_workload_identity(self):
        entity = EntityIdentity("1.0.0", "workload:builder", "workload", "team", "test").validate()
        self.assertNotIsInstance(entity, VerifiedWorkloadIdentity)
        self.assertEqual(signed().canonical_payload(), signed().canonical_payload())

if __name__ == "__main__":
    unittest.main()

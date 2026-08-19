from __future__ import annotations

import dataclasses
import hashlib
import hmac
import unittest

from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_verification import (
    AuthenticatedAuthorityGrant,
    AuthorityVerificationContext,
    AuthorityVerificationError,
    IssuerKeyBinding,
    authenticate_authority_grant,
    authority_grant_signature_payload,
)

SECRET = b"test-only-authority-grant-key"
CONTEXT = AuthorityVerificationContext("cyber-lion.test", "tenant:a", "org:a", "mission:a")
BINDING = IssuerKeyBinding(
    "workload:issuer", "cyber-lion.test", "key:issuer", "TEST-HMAC-SHA256"
)


def unsigned(**changes) -> AuthorityGrant:
    value = AuthorityGrant(
        "1.0.0",
        "grant:1",
        "workload:issuer",
        "workload:builder",
        "tenant:a",
        "org:a",
        "mission:a",
        "capability:change",
        "1.0.0",
        ("read", "write"),
        ("repo:a",),
        "local_write",
        ("observe",),
        None,
        "2026-08-19T13:00:00Z",
        "2026-08-19T15:00:00Z",
        7,
        "sha256:" + "a" * 64,
        "sha256:" + "b" * 64,
        "pending",
    )
    return dataclasses.replace(value, **changes)


def signed(value: AuthorityGrant | None = None, *, secret: bytes = SECRET) -> AuthorityGrant:
    value = value or unsigned()
    payload = authority_grant_signature_payload(value, CONTEXT.trust_domain)
    signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return dataclasses.replace(value, signature=signature)


def verifier(payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
    if (key_id, algorithm) != (BINDING.key_id, BINDING.algorithm):
        return False
    expected = hmac.new(SECRET, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def authenticate(
    value: AuthorityGrant,
    *,
    context: AuthorityVerificationContext = CONTEXT,
    bindings=(BINDING,),
    checker=verifier,
):
    return authenticate_authority_grant(value, bindings, checker, context=context)


class AuthorityVerificationTests(unittest.TestCase):
    def test_valid_externally_bound_grant_authenticates(self):
        result = authenticate(signed())
        self.assertIsInstance(result, AuthenticatedAuthorityGrant)
        self.assertEqual(result.grant_id, "grant:1")
        self.assertEqual(result.issuer_subject_id, "workload:issuer")
        self.assertEqual(result.key_id, "key:issuer")
        self.assertEqual(result.trust_domain, "cyber-lion.test")

    def test_forged_and_tampered_grants_fail_closed(self):
        value = signed()
        with self.assertRaises(AuthorityVerificationError):
            authenticate(dataclasses.replace(value, signature="0" * 64))
        with self.assertRaises(AuthorityVerificationError):
            authenticate(dataclasses.replace(value, subject_id="workload:attacker"))

    def test_wrong_trust_domain_and_issuer_binding_fail(self):
        wrong_domain = AuthorityVerificationContext(
            "other.test", "tenant:a", "org:a", "mission:a"
        )
        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), context=wrong_domain)
        other_issuer = IssuerKeyBinding(
            "workload:other", "cyber-lion.test", "key:issuer", "TEST-HMAC-SHA256"
        )
        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), bindings=(other_issuer,))

    def test_expected_tenant_organization_and_mission_are_mandatory(self):
        mutations = {
            "tenant_id": "tenant:b",
            "organization_id": "org:b",
            "mission_id": "mission:b",
        }
        for field, value in mutations.items():
            altered = unsigned(**{field: value})
            altered_context = dataclasses.replace(CONTEXT, **{field: value})
            payload = authority_grant_signature_payload(altered, altered_context.trust_domain)
            resigned = dataclasses.replace(
                altered, signature=hmac.new(SECRET, payload, hashlib.sha256).hexdigest()
            )
            with self.subTest(field=field), self.assertRaises(AuthorityVerificationError):
                authenticate(resigned)

    def test_verifier_false_and_exception_fail_closed(self):
        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), checker=lambda *_: False)

        def broken(*_):
            raise RuntimeError("provider unavailable")

        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), checker=broken)

    def test_zero_and_multiple_eligible_keys_fail_closed(self):
        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), bindings=())
        duplicate = dataclasses.replace(BINDING)
        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), bindings=(BINDING, duplicate))

    def test_key_or_algorithm_confusion_is_rejected_by_verifier(self):
        wrong_key = dataclasses.replace(BINDING, key_id="key:other")
        wrong_alg = dataclasses.replace(BINDING, algorithm="OTHER")
        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), bindings=(wrong_key,))
        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), bindings=(wrong_alg,))

    def test_domain_separated_payload_is_deterministic_and_domain_bound(self):
        value = unsigned()
        one = authority_grant_signature_payload(value, "cyber-lion.test")
        two = authority_grant_signature_payload(value, "cyber-lion.test")
        other = authority_grant_signature_payload(value, "other.test")
        self.assertEqual(one, two)
        self.assertNotEqual(one, other)
        self.assertTrue(one.startswith(b"CYBER-LION/AUTHORITY-GRANT/1.0.0\x00"))

    def test_invalid_external_binding_and_context_shapes_fail_closed(self):
        bad_binding = dataclasses.replace(BINDING, key_id="")
        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), bindings=(bad_binding,))
        bad_context = dataclasses.replace(CONTEXT, trust_domain="bad\x00domain")
        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), context=bad_context)

    def test_authenticated_result_is_not_effect_authority(self):
        result = authenticate(signed())
        for forbidden in (
            "authority",
            "authority_ceiling",
            "actions",
            "resource_scope",
            "capabilities",
            "permission",
            "decision",
            "execute",
        ):
            with self.subTest(field=forbidden):
                self.assertFalse(hasattr(result, forbidden))

    def test_signature_payload_and_result_bind_exact_bytes(self):
        value = signed()
        result = authenticate(value)
        expected = authority_grant_signature_payload(value, CONTEXT.trust_domain)
        self.assertEqual(result.signed_payload, expected)
        self.assertEqual(result.grant_digest, value.digest())


if __name__ == "__main__":
    unittest.main()

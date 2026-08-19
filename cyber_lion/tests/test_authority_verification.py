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
CONTEXT = AuthorityVerificationContext(
    "cyber-lion.test", "tenant:a", "org:a", "mission:a"
)
BINDING = IssuerKeyBinding(
    "workload:issuer",
    "cyber-lion.test",
    "key:issuer",
    "TEST-HMAC-SHA256",
)

LEGACY_V1_CANONICAL = b'{"actions":["read","write"],"authority_ceiling":"local_write","capability_id":"capability:change","capability_version":"1.0.0","constraints":["observe"],"epoch":7,"expires_at":"2026-08-19T15:00:00Z","grant_id":"grant:1","issued_at":"2026-08-19T13:00:00Z","issuer_subject_id":"workload:issuer","mission_id":"mission:a","observability_contract_digest":"sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","organization_id":"org:a","parent_grant_id":null,"policy_digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","resource_scope":["repo:a"],"schema_version":"1.0.0","subject_id":"workload:builder","tenant_id":"tenant:a"}'
LEGACY_V1_SIGNATURE = "1fa35870a5a89f39902e52e6217cc5b36e9a279e3275e2fb1b602910b33b612e"


def unsigned(**changes) -> AuthorityGrant:
    value = AuthorityGrant(
        "1.1.0",
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
        False,
        0,
    )
    return dataclasses.replace(value, **changes)


def legacy_unsigned(**changes) -> AuthorityGrant:
    return unsigned(schema_version="1.0.0", **changes)


def signed(
    value: AuthorityGrant | None = None, *, secret: bytes = SECRET
) -> AuthorityGrant:
    value = value or unsigned()
    payload = authority_grant_signature_payload(
        value, CONTEXT.trust_domain
    )
    signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return dataclasses.replace(value, signature=signature)


def verifier(
    payload: bytes, signature: str, key_id: str, algorithm: str
) -> bool:
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
    return authenticate_authority_grant(
        value, bindings, checker, context=context
    )


class AuthorityVerificationTests(unittest.TestCase):
    def test_valid_externally_bound_grant_authenticates(self):
        result = authenticate(signed())
        self.assertIsInstance(result, AuthenticatedAuthorityGrant)
        self.assertEqual(result.grant_id, "grant:1")
        self.assertEqual(
            result.issuer_subject_id, "workload:issuer"
        )
        self.assertEqual(result.key_id, "key:issuer")
        self.assertEqual(result.trust_domain, "cyber-lion.test")

    def test_historical_v1_golden_bytes_are_exactly_preserved(self):
        value = legacy_unsigned()
        self.assertEqual(value.canonical_payload(), LEGACY_V1_CANONICAL)
        expected_payload = (
            b"CYBER-LION/AUTHORITY-GRANT/1.0.0\x00"
            + b"cyber-lion.test\x00"
            + LEGACY_V1_CANONICAL
        )
        self.assertEqual(
            authority_grant_signature_payload(
                value, CONTEXT.trust_domain
            ),
            expected_payload,
        )

    def test_historical_v1_golden_signature_authenticates(self):
        value = dataclasses.replace(
            legacy_unsigned(), signature=LEGACY_V1_SIGNATURE
        )
        result = authenticate(value)
        self.assertEqual(
            result.signed_payload,
            b"CYBER-LION/AUTHORITY-GRANT/1.0.0\x00"
            + b"cyber-lion.test\x00"
            + LEGACY_V1_CANONICAL,
        )

    def test_version_domain_separation_and_cross_version_confusion_fail(self):
        legacy = dataclasses.replace(
            legacy_unsigned(), signature=LEGACY_V1_SIGNATURE
        )
        current = signed(unsigned())
        legacy_payload = authority_grant_signature_payload(
            legacy, CONTEXT.trust_domain
        )
        current_payload = authority_grant_signature_payload(
            current, CONTEXT.trust_domain
        )
        self.assertTrue(
            legacy_payload.startswith(
                b"CYBER-LION/AUTHORITY-GRANT/1.0.0\x00"
            )
        )
        self.assertTrue(
            current_payload.startswith(
                b"CYBER-LION/AUTHORITY-GRANT/1.1.0\x00"
            )
        )
        self.assertNotEqual(legacy_payload, current_payload)

        legacy_signature_on_current = dataclasses.replace(
            current, signature=LEGACY_V1_SIGNATURE
        )
        with self.assertRaises(AuthorityVerificationError):
            authenticate(legacy_signature_on_current)

        current_signature_on_legacy = dataclasses.replace(
            legacy, signature=current.signature
        )
        with self.assertRaises(AuthorityVerificationError):
            authenticate(current_signature_on_legacy)

    def test_subclass_object_substitution_fails_before_verifier(self):
        calls = {
            "validate": 0,
            "canonical_payload": 0,
            "digest": 0,
            "verifier": 0,
        }

        class SubstitutedAuthorityGrant(AuthorityGrant):
            def validate(self):
                calls["validate"] += 1
                return self

            def canonical_payload(self):
                calls["canonical_payload"] += 1
                return b"attacker-controlled-signed-payload"

            def digest(self):
                calls["digest"] += 1
                return "attacker-controlled-digest"

        base = unsigned()
        value = SubstitutedAuthorityGrant(
            **{
                field.name: getattr(base, field.name)
                for field in dataclasses.fields(AuthorityGrant)
            }
        )
        self.assertIsInstance(value, AuthorityGrant)
        self.assertIsNot(type(value), AuthorityGrant)

        with self.assertRaises(AuthorityVerificationError):
            authority_grant_signature_payload(
                value, CONTEXT.trust_domain
            )
        self.assertEqual(
            calls,
            {
                "validate": 0,
                "canonical_payload": 0,
                "digest": 0,
                "verifier": 0,
            },
        )

        def accepting_verifier(*_):
            calls["verifier"] += 1
            return True

        with self.assertRaises(AuthorityVerificationError):
            authenticate(value, checker=accepting_verifier)
        self.assertEqual(
            calls,
            {
                "validate": 0,
                "canonical_payload": 0,
                "digest": 0,
                "verifier": 0,
            },
        )

    def test_forged_and_tampered_grants_fail_closed(self):
        value = signed()
        with self.assertRaises(AuthorityVerificationError):
            authenticate(
                dataclasses.replace(value, signature="0" * 64)
            )
        with self.assertRaises(AuthorityVerificationError):
            authenticate(
                dataclasses.replace(
                    value, subject_id="workload:attacker"
                )
            )

    def test_wrong_trust_domain_and_issuer_binding_fail(self):
        wrong_domain = AuthorityVerificationContext(
            "other.test", "tenant:a", "org:a", "mission:a"
        )
        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), context=wrong_domain)
        other_issuer = IssuerKeyBinding(
            "workload:other",
            "cyber-lion.test",
            "key:issuer",
            "TEST-HMAC-SHA256",
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
            altered_context = dataclasses.replace(
                CONTEXT, **{field: value}
            )
            payload = authority_grant_signature_payload(
                altered, altered_context.trust_domain
            )
            resigned = dataclasses.replace(
                altered,
                signature=hmac.new(
                    SECRET, payload, hashlib.sha256
                ).hexdigest(),
            )
            with self.subTest(
                field=field
            ), self.assertRaises(AuthorityVerificationError):
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
        wrong_key = dataclasses.replace(
            BINDING, key_id="key:other"
        )
        wrong_alg = dataclasses.replace(
            BINDING, algorithm="OTHER"
        )
        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), bindings=(wrong_key,))
        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), bindings=(wrong_alg,))

    def test_domain_separated_payload_is_deterministic_and_domain_bound(self):
        value = unsigned()
        one = authority_grant_signature_payload(
            value, "cyber-lion.test"
        )
        two = authority_grant_signature_payload(
            value, "cyber-lion.test"
        )
        other = authority_grant_signature_payload(
            value, "other.test"
        )
        self.assertEqual(one, two)
        self.assertNotEqual(one, other)
        self.assertTrue(
            one.startswith(
                b"CYBER-LION/AUTHORITY-GRANT/1.1.0\x00"
            )
        )

    def test_invalid_external_binding_and_context_shapes_fail_closed(self):
        bad_binding = dataclasses.replace(BINDING, key_id="")
        with self.assertRaises(AuthorityVerificationError):
            authenticate(signed(), bindings=(bad_binding,))
        bad_context = dataclasses.replace(
            CONTEXT, trust_domain="bad\x00domain"
        )
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
        expected = authority_grant_signature_payload(
            value, CONTEXT.trust_domain
        )
        self.assertEqual(result.signed_payload, expected)
        self.assertEqual(result.grant_digest, value.digest())


if __name__ == "__main__":
    unittest.main()

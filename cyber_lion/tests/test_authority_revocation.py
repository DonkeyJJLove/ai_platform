from __future__ import annotations

import dataclasses
import hashlib
import hmac
import unittest
from unittest.mock import patch

from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_revocation import (
    AuthorityEpochState,
    AuthorityRevocationError,
    EpochAdmittedAuthorityGrant,
    authenticate_and_admit_authority_grant,
    validate_epoch_transition,
)
from cyber_lion.enterprise.authority_verification import (
    AuthenticatedAuthorityGrant,
    AuthorityVerificationContext,
    AuthorityVerificationError,
    IssuerKeyBinding,
    authority_grant_signature_payload,
)

SECRET = b"test-only-authority-revocation-key"
CONTEXT = AuthorityVerificationContext(
    "cyber-lion.test",
    "tenant:a",
    "org:a",
    "RCCM-1E-BF-B2",
)
BINDING = IssuerKeyBinding(
    "workload:issuer",
    "cyber-lion.test",
    "key:issuer",
    "TEST-HMAC-SHA256",
)


def unsigned(**changes) -> AuthorityGrant:
    value = AuthorityGrant(
        "1.0.0",
        "grant:1",
        "workload:issuer",
        "workload:builder",
        "tenant:a",
        "org:a",
        "RCCM-1E-BF-B2",
        "capability:change",
        "1.0.0",
        ("read", "write"),
        ("repo:ai_platform",),
        "local_write",
        ("observe",),
        None,
        "2026-08-19T16:00:00Z",
        "2026-08-19T20:00:00Z",
        7,
        "sha256:" + "a" * 64,
        "sha256:" + "b" * 64,
        "pending",
    )
    return dataclasses.replace(value, **changes)


def signed(value: AuthorityGrant | None = None) -> AuthorityGrant:
    value = value or unsigned()
    payload = authority_grant_signature_payload(value, CONTEXT.trust_domain)
    signature = hmac.new(SECRET, payload, hashlib.sha256).hexdigest()
    return dataclasses.replace(value, signature=signature)


def verifier(payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
    if (key_id, algorithm) != (BINDING.key_id, BINDING.algorithm):
        return False
    expected = hmac.new(SECRET, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def state(
    epoch: int = 7,
    revoked: tuple[str, ...] = (),
    **changes,
) -> AuthorityEpochState:
    value = AuthorityEpochState(
        trust_domain="cyber-lion.test",
        tenant_id="tenant:a",
        organization_id="org:a",
        mission_id="RCCM-1E-BF-B2",
        epoch=epoch,
        revoked_grant_ids=revoked,
    )
    return dataclasses.replace(value, **changes)


def admit(
    value: AuthorityGrant,
    *,
    epoch_state: AuthorityEpochState | None = None,
    context: AuthorityVerificationContext = CONTEXT,
    checker=verifier,
):
    return authenticate_and_admit_authority_grant(
        value,
        (BINDING,),
        checker,
        context=context,
        epoch_state=epoch_state or state(),
    )


class AuthorityEpochTransitionTests(unittest.TestCase):
    def test_same_epoch_idempotence_and_revocation_growth_are_valid(self):
        previous = state(revoked=("grant:a",))
        same = state(revoked=("grant:a",))
        expanded = state(revoked=("grant:a", "grant:b"))
        self.assertIs(validate_epoch_transition(previous, same), same)
        self.assertIs(validate_epoch_transition(previous, expanded), expanded)

    def test_epoch_rollback_and_same_epoch_unrevocation_fail(self):
        with self.assertRaises(AuthorityRevocationError):
            validate_epoch_transition(state(epoch=8), state(epoch=7))

        previous = state(revoked=("grant:a", "grant:b"))
        candidate = state(revoked=("grant:b",))
        with self.assertRaises(AuthorityRevocationError):
            validate_epoch_transition(previous, candidate)

    def test_forward_epoch_may_start_a_fresh_revocation_set(self):
        previous = state(epoch=7, revoked=("grant:1", "grant:2"))
        candidate = state(epoch=8, revoked=())
        self.assertIs(validate_epoch_transition(previous, candidate), candidate)

    def test_epoch_context_cannot_migrate(self):
        mutations = (
            {"trust_domain": "other.test"},
            {"tenant_id": "tenant:b"},
            {"organization_id": "org:b"},
            {"mission_id": "mission:other"},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(
                AuthorityRevocationError
            ):
                validate_epoch_transition(state(), state(**mutation))

    def test_invalid_state_shapes_fail_closed(self):
        invalid_states = (
            state(epoch=True),
            state(epoch=-1),
            state(revoked=("grant:1", "grant:1")),
            state(revoked=("",)),
            dataclasses.replace(state(), revoked_grant_ids=["grant:1"]),
        )
        for value in invalid_states:
            with self.subTest(value=value), self.assertRaises(AuthorityRevocationError):
                value.validate()


class AuthorityRevocationAdmissionTests(unittest.TestCase):
    def test_authenticated_current_non_revoked_grant_is_admitted(self):
        value = signed()
        result = admit(value)
        self.assertIsInstance(result, EpochAdmittedAuthorityGrant)
        self.assertEqual(result.grant_id, value.grant_id)
        self.assertEqual(result.epoch, 7)
        self.assertEqual(result.grant_digest, value.digest())

    def test_current_epoch_revoked_grant_is_rejected(self):
        with self.assertRaises(AuthorityRevocationError):
            admit(signed(), epoch_state=state(revoked=("grant:1",)))

    def test_stale_and_future_epoch_grants_are_rejected(self):
        for grant_epoch in (6, 8):
            value = signed(unsigned(epoch=grant_epoch))
            with self.subTest(grant_epoch=grant_epoch), self.assertRaises(
                AuthorityRevocationError
            ):
                admit(value)

    def test_revocation_is_specific_to_one_epoch(self):
        old = signed(unsigned(epoch=7, grant_id="grant:stable-id"))
        with self.assertRaises(AuthorityRevocationError):
            admit(
                old,
                epoch_state=state(epoch=7, revoked=("grant:stable-id",)),
            )

        fresh = signed(unsigned(epoch=8, grant_id="grant:stable-id"))
        result = admit(fresh, epoch_state=state(epoch=8, revoked=()))
        self.assertEqual((result.grant_id, result.epoch), ("grant:stable-id", 8))

    def test_epoch_state_must_match_trusted_context(self):
        mutations = (
            {"trust_domain": "other.test"},
            {"tenant_id": "tenant:b"},
            {"organization_id": "org:b"},
            {"mission_id": "mission:other"},
        )

        for mutation in mutations:
            calls = {"verifier": 0}

            def counting_verifier(*_):
                calls["verifier"] += 1
                return True

            with self.subTest(mutation=mutation), self.assertRaises(
                AuthorityRevocationError
            ):
                admit(
                    signed(),
                    epoch_state=state(**mutation),
                    checker=counting_verifier,
                )
            self.assertEqual(calls["verifier"], 0)

    def test_authenticated_result_must_bind_exact_payload_and_digest(self):
        value = signed()
        legitimate_payload = authority_grant_signature_payload(
            value,
            CONTEXT.trust_domain,
        )
        legitimate_digest = value.digest()
        base = AuthenticatedAuthorityGrant(
            grant_id=value.grant_id,
            issuer_subject_id=value.issuer_subject_id,
            subject_id=value.subject_id,
            trust_domain=CONTEXT.trust_domain,
            tenant_id=value.tenant_id,
            organization_id=value.organization_id,
            mission_id=value.mission_id,
            key_id=BINDING.key_id,
            algorithm=BINDING.algorithm,
            signed_payload=legitimate_payload,
            grant_digest=legitimate_digest,
        )

        mismatches = (
            dataclasses.replace(base, signed_payload=b"wrong-payload"),
            dataclasses.replace(base, grant_digest="wrong-digest"),
            dataclasses.replace(base, subject_id="workload:other"),
        )
        for authenticated in mismatches:
            with self.subTest(authenticated=authenticated), patch(
                "cyber_lion.enterprise.authority_revocation.authenticate_authority_grant",
                return_value=authenticated,
            ), self.assertRaises(AuthorityRevocationError):
                admit(value)

    def test_subclass_object_substitution_fails_before_admission(self):
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
                return b"attacker-controlled"

            def digest(self):
                calls["digest"] += 1
                return "attacker-controlled"

        base = signed()
        value = SubstitutedAuthorityGrant(
            **{
                field.name: getattr(base, field.name)
                for field in dataclasses.fields(AuthorityGrant)
            }
        )

        def accepting_verifier(*_):
            calls["verifier"] += 1
            return True

        with self.assertRaises(AuthorityRevocationError):
            admit(value, checker=accepting_verifier)
        self.assertEqual(
            calls,
            {
                "validate": 0,
                "canonical_payload": 0,
                "digest": 0,
                "verifier": 0,
            },
        )

    def test_authentication_failure_and_exception_remain_fail_closed(self):
        with self.assertRaises(AuthorityVerificationError):
            admit(signed(), checker=lambda *_: False)

        def broken(*_):
            raise RuntimeError("provider unavailable")

        with self.assertRaises(AuthorityVerificationError):
            admit(signed(), checker=broken)

    def test_epoch_admission_result_is_not_effect_authority(self):
        result = admit(signed())
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


if __name__ == "__main__":
    unittest.main()

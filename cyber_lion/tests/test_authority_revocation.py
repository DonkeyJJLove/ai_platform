from __future__ import annotations

import dataclasses
import hashlib
import hmac
import inspect
import unittest
from unittest.mock import patch

from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_revocation import (
    AuthorityEpochState,
    AuthorityEpochStateOwner,
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


def owner(initial_state: AuthorityEpochState | None = None) -> AuthorityEpochStateOwner:
    return AuthorityEpochStateOwner(initial_state if initial_state is not None else state())


def admit(
    value: AuthorityGrant,
    *,
    state_owner: AuthorityEpochStateOwner | None = None,
    context: AuthorityVerificationContext = CONTEXT,
    checker=verifier,
):
    return authenticate_and_admit_authority_grant(
        value,
        (BINDING,),
        checker,
        context=context,
        epoch_state_owner=state_owner if state_owner is not None else owner(),
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


class AuthorityEpochStateOwnerTests(unittest.TestCase):
    def test_owner_requires_exact_valid_initial_state(self):
        with self.assertRaises(AuthorityRevocationError):
            owner(state(epoch=-1))

        class SubstitutedAuthorityEpochState(AuthorityEpochState):
            pass

        base = state()
        substituted = SubstitutedAuthorityEpochState(
            **{
                field.name: getattr(base, field.name)
                for field in dataclasses.fields(AuthorityEpochState)
            }
        )
        with self.assertRaises(AuthorityRevocationError):
            owner(substituted)

    def test_owner_advance_is_atomic_and_rejected_transition_keeps_current(self):
        current = state(epoch=7, revoked=("grant:1",))
        state_owner = owner(current)

        expanded = state(epoch=7, revoked=("grant:1", "grant:2"))
        self.assertIs(state_owner.advance(expanded), expanded)
        self.assertIs(state_owner.current(), expanded)

        invalid = state(epoch=7, revoked=("grant:2",))
        with self.assertRaises(AuthorityRevocationError):
            state_owner.advance(invalid)
        self.assertIs(state_owner.current(), expanded)

        forward = state(epoch=8, revoked=())
        self.assertIs(state_owner.advance(forward), forward)
        self.assertIs(state_owner.current(), forward)


class AuthorityRevocationAdmissionTests(unittest.TestCase):
    def test_authenticated_current_non_revoked_grant_is_admitted(self):
        value = signed()
        result = admit(value)
        self.assertIsInstance(result, EpochAdmittedAuthorityGrant)
        self.assertEqual(result.grant_id, value.grant_id)
        self.assertEqual(result.epoch, 7)
        self.assertEqual(result.grant_digest, value.digest())

    def test_public_admission_requires_owner_not_raw_snapshot(self):
        parameters = inspect.signature(
            authenticate_and_admit_authority_grant
        ).parameters
        self.assertIn("epoch_state_owner", parameters)
        self.assertNotIn("epoch_state", parameters)
        with self.assertRaises(TypeError):
            authenticate_and_admit_authority_grant(
                signed(),
                (BINDING,),
                verifier,
                context=CONTEXT,
                epoch_state=state(),
            )

    def test_current_epoch_revoked_grant_is_rejected(self):
        with self.assertRaises(AuthorityRevocationError):
            admit(
                signed(),
                state_owner=owner(state(revoked=("grant:1",))),
            )

    def test_stale_and_future_epoch_grants_are_rejected(self):
        state_owner = owner(state(epoch=7))
        for grant_epoch in (6, 8):
            value = signed(unsigned(epoch=grant_epoch))
            with self.subTest(grant_epoch=grant_epoch), self.assertRaises(
                AuthorityRevocationError
            ):
                admit(value, state_owner=state_owner)

    def test_revocation_is_specific_to_one_epoch(self):
        state_owner = owner(
            state(epoch=7, revoked=("grant:stable-id",))
        )
        old = signed(unsigned(epoch=7, grant_id="grant:stable-id"))
        with self.assertRaises(AuthorityRevocationError):
            admit(old, state_owner=state_owner)

        fresh_state = state(epoch=8, revoked=())
        self.assertIs(state_owner.advance(fresh_state), fresh_state)
        fresh = signed(unsigned(epoch=8, grant_id="grant:stable-id"))
        result = admit(fresh, state_owner=state_owner)
        self.assertEqual((result.grant_id, result.epoch), ("grant:stable-id", 8))

    def test_owner_context_must_match_trusted_context_before_verifier(self):
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
                    state_owner=owner(state(**mutation)),
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

    def test_admission_rechecks_owner_state_after_authentication(self):
        value = signed()
        state_owner = owner(state(epoch=7))

        def revoking_verifier(payload, signature, key_id, algorithm):
            state_owner.advance(state(epoch=7, revoked=("grant:1",)))
            return verifier(payload, signature, key_id, algorithm)

        with self.assertRaises(AuthorityRevocationError):
            admit(
                value,
                state_owner=state_owner,
                checker=revoking_verifier,
            )
        self.assertEqual(
            state_owner.current().revoked_grant_ids,
            ("grant:1",),
        )

    def test_rollback_or_unrevoked_snapshot_cannot_bypass_admission(self):
        rollback_owner = owner(state(epoch=7))
        current_epoch = state(epoch=8)
        self.assertIs(rollback_owner.advance(current_epoch), current_epoch)

        rollback_snapshot = state(epoch=7)
        with self.assertRaises(AuthorityRevocationError):
            rollback_owner.advance(rollback_snapshot)
        self.assertIs(rollback_owner.current(), current_epoch)

        with self.assertRaises(AuthorityRevocationError):
            admit(
                signed(unsigned(epoch=7)),
                state_owner=rollback_owner,
            )
        self.assertIs(rollback_owner.current(), current_epoch)

        revoked_state = state(epoch=7, revoked=("grant:1",))
        unrevocation_owner = owner(revoked_state)
        unrevoked_snapshot = state(epoch=7, revoked=())
        with self.assertRaises(AuthorityRevocationError):
            unrevocation_owner.advance(unrevoked_snapshot)
        self.assertIs(unrevocation_owner.current(), revoked_state)

        with self.assertRaises(AuthorityRevocationError):
            admit(
                signed(unsigned(epoch=7, grant_id="grant:1")),
                state_owner=unrevocation_owner,
            )
        self.assertIs(unrevocation_owner.current(), revoked_state)

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

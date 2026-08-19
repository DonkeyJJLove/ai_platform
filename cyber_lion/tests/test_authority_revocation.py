from __future__ import annotations

import dataclasses
import hashlib
import hmac
import inspect
import unittest
from unittest.mock import patch

import cyber_lion.enterprise.authority_revocation as authority_revocation_module
from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_revocation import (
    AuthorityEpochState,
    AuthorityEpochStateOwner,
    AuthorityRevocationError,
    EpochAdmittedAuthorityGrant,
    advance_canonical_authority_epoch_state,
    authenticate_and_admit_authority_grant,
    register_canonical_authority_epoch_state,
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


def context_key(
    context: AuthorityVerificationContext = CONTEXT,
) -> tuple[str, str, str, str]:
    return (
        context.trust_domain,
        context.tenant_id,
        context.organization_id,
        context.mission_id,
    )


def admit(
    value: AuthorityGrant,
    *,
    context: AuthorityVerificationContext = CONTEXT,
    checker=verifier,
):
    return authenticate_and_admit_authority_grant(
        value,
        (BINDING,),
        checker,
        context=context,
    )


class CanonicalRegistryIsolation:
    def setUp(self):
        self._registry_patcher = patch.object(
            authority_revocation_module,
            "_CANONICAL_AUTHORITY_EPOCH_REGISTRY",
            authority_revocation_module._AuthorityEpochRegistry(),
        )
        self.registry = self._registry_patcher.start()

    def tearDown(self):
        self._registry_patcher.stop()

    def reset_registry(self):
        self.registry = authority_revocation_module._AuthorityEpochRegistry()
        authority_revocation_module._CANONICAL_AUTHORITY_EPOCH_REGISTRY = self.registry

    def register(self, initial_state: AuthorityEpochState | None = None):
        return register_canonical_authority_epoch_state(
            initial_state if initial_state is not None else state()
        )

    def current(self, context: AuthorityVerificationContext = CONTEXT):
        return self.registry.resolve(context_key(context)).current()


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


class AuthorityEpochRegistryTests(CanonicalRegistryIsolation, unittest.TestCase):
    def test_registration_is_one_shot_and_duplicate_cannot_replace_owner(self):
        canonical = state(revoked=("grant:1",))
        self.assertIs(self.register(canonical), canonical)
        canonical_owner = self.registry.resolve(context_key())

        with self.assertRaises(AuthorityRevocationError):
            self.register(state(revoked=()))

        self.assertIs(self.registry.resolve(context_key()), canonical_owner)
        self.assertIs(canonical_owner.current(), canonical)

    def test_registry_advance_requires_registration_and_preserves_owner_identity(self):
        with self.assertRaises(AuthorityRevocationError):
            advance_canonical_authority_epoch_state(state(epoch=8))

        initial = state(epoch=7, revoked=("grant:1",))
        self.register(initial)
        canonical_owner = self.registry.resolve(context_key())

        expanded = state(epoch=7, revoked=("grant:1", "grant:2"))
        self.assertIs(advance_canonical_authority_epoch_state(expanded), expanded)
        self.assertIs(self.registry.resolve(context_key()), canonical_owner)
        self.assertIs(canonical_owner.current(), expanded)

        invalid = state(epoch=7, revoked=("grant:2",))
        with self.assertRaises(AuthorityRevocationError):
            advance_canonical_authority_epoch_state(invalid)
        self.assertIs(canonical_owner.current(), expanded)

    def test_registry_has_no_unregister_or_owner_replacement_path(self):
        self.assertFalse(hasattr(self.registry, "unregister"))
        self.assertFalse(hasattr(self.registry, "replace_owner"))
        self.assertFalse(hasattr(self.registry, "set_owner"))


class AuthorityRevocationAdmissionTests(CanonicalRegistryIsolation, unittest.TestCase):
    def test_authenticated_current_non_revoked_grant_is_admitted(self):
        self.register()
        value = signed()
        result = admit(value)
        self.assertIsInstance(result, EpochAdmittedAuthorityGrant)
        self.assertEqual(result.grant_id, value.grant_id)
        self.assertEqual(result.epoch, 7)
        self.assertEqual(result.grant_digest, value.digest())

    def test_public_admission_accepts_no_caller_selected_state_owner_or_registry(self):
        parameters = inspect.signature(
            authenticate_and_admit_authority_grant
        ).parameters
        self.assertNotIn("epoch_state", parameters)
        self.assertNotIn("epoch_state_owner", parameters)
        self.assertNotIn("registry", parameters)

        parallel = owner(state())
        with self.assertRaises(TypeError):
            authenticate_and_admit_authority_grant(
                signed(),
                (BINDING,),
                verifier,
                context=CONTEXT,
                epoch_state_owner=parallel,
            )

    def test_unregistered_context_fails_before_verifier(self):
        calls = {"verifier": 0}

        def counting_verifier(*_):
            calls["verifier"] += 1
            return True

        with self.assertRaises(AuthorityRevocationError):
            admit(signed(), checker=counting_verifier)
        self.assertEqual(calls["verifier"], 0)

    def test_current_epoch_revoked_grant_is_rejected(self):
        self.register(state(revoked=("grant:1",)))
        with self.assertRaises(AuthorityRevocationError):
            admit(signed())

    def test_stale_and_future_epoch_grants_are_rejected(self):
        self.register(state(epoch=7))
        for grant_epoch in (6, 8):
            value = signed(unsigned(epoch=grant_epoch))
            with self.subTest(grant_epoch=grant_epoch), self.assertRaises(
                AuthorityRevocationError
            ):
                admit(value)

    def test_revocation_is_specific_to_one_epoch(self):
        self.register(state(epoch=7, revoked=("grant:stable-id",)))
        old = signed(unsigned(epoch=7, grant_id="grant:stable-id"))
        with self.assertRaises(AuthorityRevocationError):
            admit(old)

        fresh_state = state(epoch=8, revoked=())
        self.assertIs(advance_canonical_authority_epoch_state(fresh_state), fresh_state)
        fresh = signed(unsigned(epoch=8, grant_id="grant:stable-id"))
        result = admit(fresh)
        self.assertEqual((result.grant_id, result.epoch), ("grant:stable-id", 8))

    def test_registered_different_context_cannot_satisfy_trusted_context(self):
        mutations = (
            {"trust_domain": "other.test"},
            {"tenant_id": "tenant:b"},
            {"organization_id": "org:b"},
            {"mission_id": "mission:other"},
        )

        for mutation in mutations:
            self.reset_registry()
            self.register(state(**mutation))
            calls = {"verifier": 0}

            def counting_verifier(*_):
                calls["verifier"] += 1
                return True

            with self.subTest(mutation=mutation), self.assertRaises(
                AuthorityRevocationError
            ):
                admit(signed(), checker=counting_verifier)
            self.assertEqual(calls["verifier"], 0)

    def test_authenticated_result_must_bind_exact_payload_and_digest(self):
        self.register()
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
        self.register()
        with self.assertRaises(AuthorityVerificationError):
            admit(signed(), checker=lambda *_: False)

        def broken(*_):
            raise RuntimeError("provider unavailable")

        with self.assertRaises(AuthorityVerificationError):
            admit(signed(), checker=broken)

    def test_admission_rechecks_canonical_state_after_authentication(self):
        self.register(state(epoch=7))
        value = signed()

        def revoking_verifier(payload, signature, key_id, algorithm):
            advance_canonical_authority_epoch_state(
                state(epoch=7, revoked=("grant:1",))
            )
            return verifier(payload, signature, key_id, algorithm)

        with self.assertRaises(AuthorityRevocationError):
            admit(value, checker=revoking_verifier)
        self.assertEqual(self.current().revoked_grant_ids, ("grant:1",))

    def test_rollback_or_unrevoked_snapshot_cannot_bypass_admission(self):
        self.register(state(epoch=7))
        current_epoch = state(epoch=8)
        self.assertIs(advance_canonical_authority_epoch_state(current_epoch), current_epoch)

        rollback_snapshot = state(epoch=7)
        with self.assertRaises(AuthorityRevocationError):
            advance_canonical_authority_epoch_state(rollback_snapshot)
        self.assertIs(self.current(), current_epoch)

        with self.assertRaises(AuthorityRevocationError):
            admit(signed(unsigned(epoch=7)))
        self.assertIs(self.current(), current_epoch)

        self.reset_registry()
        revoked_state = state(epoch=7, revoked=("grant:1",))
        self.register(revoked_state)
        unrevoked_snapshot = state(epoch=7, revoked=())
        with self.assertRaises(AuthorityRevocationError):
            advance_canonical_authority_epoch_state(unrevoked_snapshot)
        self.assertIs(self.current(), revoked_state)

        with self.assertRaises(AuthorityRevocationError):
            admit(signed(unsigned(epoch=7, grant_id="grant:1")))
        self.assertIs(self.current(), revoked_state)

    def test_fresh_or_parallel_owner_cannot_substitute_current_authority_state(self):
        canonical_revoked = state(epoch=7, revoked=("grant:1",))
        self.register(canonical_revoked)
        canonical_owner = self.registry.resolve(context_key())
        parallel_unrevoked = owner(state(epoch=7, revoked=()))
        self.assertIsNot(parallel_unrevoked, canonical_owner)

        with self.assertRaises(AuthorityRevocationError):
            self.register(state(epoch=7, revoked=()))
        self.assertIs(self.registry.resolve(context_key()), canonical_owner)
        self.assertIs(self.current(), canonical_revoked)

        with self.assertRaises(TypeError):
            authenticate_and_admit_authority_grant(
                signed(unsigned(epoch=7, grant_id="grant:1")),
                (BINDING,),
                verifier,
                context=CONTEXT,
                epoch_state_owner=parallel_unrevoked,
            )
        with self.assertRaises(AuthorityRevocationError):
            admit(signed(unsigned(epoch=7, grant_id="grant:1")))
        self.assertIs(self.current(), canonical_revoked)

        self.reset_registry()
        self.register(state(epoch=7))
        current_epoch = state(epoch=8)
        self.assertIs(advance_canonical_authority_epoch_state(current_epoch), current_epoch)
        canonical_owner = self.registry.resolve(context_key())
        parallel_stale = owner(state(epoch=7))
        self.assertIsNot(parallel_stale, canonical_owner)

        old_grant = signed(unsigned(epoch=7))
        with self.assertRaises(TypeError):
            authenticate_and_admit_authority_grant(
                old_grant,
                (BINDING,),
                verifier,
                context=CONTEXT,
                epoch_state_owner=parallel_stale,
            )
        with self.assertRaises(AuthorityRevocationError):
            admit(old_grant)
        self.assertIs(self.current(), current_epoch)

    def test_epoch_admission_result_is_not_effect_authority(self):
        self.register()
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

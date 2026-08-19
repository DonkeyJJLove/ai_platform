from __future__ import annotations

import dataclasses
import hashlib
import hmac
import inspect
import unittest
from unittest.mock import patch

import cyber_lion.enterprise.authority_revocation as authority_revocation_module
from cyber_lion.enterprise.authority_grant import AuthorityGrant, AuthorityGrantError
from cyber_lion.enterprise.authority_revocation import (
    AuthorityEpochState,
    AuthorityLineageRootAnchor,
    EpochAdmittedAuthorityLineage,
    advance_canonical_authority_epoch_state,
    authenticate_and_admit_authority_lineage,
    register_canonical_authority_epoch_state,
    register_canonical_authority_lineage_root_anchor,
)
from cyber_lion.enterprise.authority_verification import (
    AuthorityVerificationContext,
    IssuerKeyBinding,
    authority_grant_signature_payload,
)

CONTEXT = AuthorityVerificationContext(
    "cyber-lion.test",
    "tenant:a",
    "org:a",
    "RCCM-1E-G2",
)
OTHER_CONTEXT = AuthorityVerificationContext(
    "cyber-lion.test",
    "tenant:a",
    "org:a",
    "RCCM-1E-G2-OTHER",
)
POLICY = "sha256:" + "a" * 64
OBS = "sha256:" + "b" * 64
ALGORITHM = "TEST-HMAC-SHA256"

ISSUER_SECRETS = {
    "root:governance": b"test-only-root-key",
    "workload:parent": b"test-only-parent-key",
    "workload:mid": b"test-only-mid-key",
}
KEY_TO_SECRET = {
    "key:root": ISSUER_SECRETS["root:governance"],
    "key:parent": ISSUER_SECRETS["workload:parent"],
    "key:mid": ISSUER_SECRETS["workload:mid"],
}
BINDINGS = (
    IssuerKeyBinding("root:governance", CONTEXT.trust_domain, "key:root", ALGORITHM),
    IssuerKeyBinding("workload:parent", CONTEXT.trust_domain, "key:parent", ALGORITHM),
    IssuerKeyBinding("workload:mid", CONTEXT.trust_domain, "key:mid", ALGORITHM),
)


def root_unsigned(**changes) -> AuthorityGrant:
    value = AuthorityGrant(
        schema_version="1.1.0",
        grant_id="grant:root",
        issuer_subject_id="root:governance",
        subject_id="workload:parent",
        tenant_id=CONTEXT.tenant_id,
        organization_id=CONTEXT.organization_id,
        mission_id=CONTEXT.mission_id,
        capability_id="code.write",
        capability_version="1.0.0",
        actions=("read", "write", "test"),
        resource_scope=("repo:ai_platform", "path:cyber_lion"),
        authority_ceiling="local_write",
        constraints=("no-default-branch-write",),
        parent_grant_id=None,
        issued_at="2026-08-19T14:00:00Z",
        expires_at="2026-08-19T18:00:00Z",
        epoch=7,
        policy_digest=POLICY,
        observability_contract_digest=OBS,
        signature="pending",
        delegation_allowed=True,
        delegation_depth_budget=3,
    )
    return dataclasses.replace(value, **changes)


def mid_unsigned(**changes) -> AuthorityGrant:
    value = AuthorityGrant(
        schema_version="1.1.0",
        grant_id="grant:mid",
        issuer_subject_id="workload:parent",
        subject_id="workload:mid",
        tenant_id=CONTEXT.tenant_id,
        organization_id=CONTEXT.organization_id,
        mission_id=CONTEXT.mission_id,
        capability_id="code.write",
        capability_version="1.0.0",
        actions=("read", "test"),
        resource_scope=("repo:ai_platform",),
        authority_ceiling="read",
        constraints=("no-default-branch-write", "mid-bound"),
        parent_grant_id="grant:root",
        issued_at="2026-08-19T14:10:00Z",
        expires_at="2026-08-19T17:00:00Z",
        epoch=7,
        policy_digest=POLICY,
        observability_contract_digest=OBS,
        signature="pending",
        delegation_allowed=True,
        delegation_depth_budget=2,
    )
    return dataclasses.replace(value, **changes)


def leaf_unsigned(**changes) -> AuthorityGrant:
    value = AuthorityGrant(
        schema_version="1.1.0",
        grant_id="grant:leaf",
        issuer_subject_id="workload:mid",
        subject_id="workload:executor",
        tenant_id=CONTEXT.tenant_id,
        organization_id=CONTEXT.organization_id,
        mission_id=CONTEXT.mission_id,
        capability_id="code.write",
        capability_version="1.0.0",
        actions=("read",),
        resource_scope=("repo:ai_platform",),
        authority_ceiling="read",
        constraints=("no-default-branch-write", "mid-bound", "leaf-bound"),
        parent_grant_id="grant:mid",
        issued_at="2026-08-19T14:20:00Z",
        expires_at="2026-08-19T16:00:00Z",
        epoch=7,
        policy_digest=POLICY,
        observability_contract_digest=OBS,
        signature="pending",
        delegation_allowed=False,
        delegation_depth_budget=0,
    )
    return dataclasses.replace(value, **changes)


def sign(value: AuthorityGrant) -> AuthorityGrant:
    payload = authority_grant_signature_payload(value, CONTEXT.trust_domain)
    signature = hmac.new(
        ISSUER_SECRETS[value.issuer_subject_id], payload, hashlib.sha256
    ).hexdigest()
    return dataclasses.replace(value, signature=signature)


def lineage(epoch: int = 7) -> tuple[AuthorityGrant, ...]:
    return (
        sign(root_unsigned(epoch=epoch)),
        sign(mid_unsigned(epoch=epoch)),
        sign(leaf_unsigned(epoch=epoch)),
    )


def verifier(payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
    if algorithm != ALGORITHM or key_id not in KEY_TO_SECRET:
        return False
    expected = hmac.new(KEY_TO_SECRET[key_id], payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def anchor(value: AuthorityGrant) -> AuthorityLineageRootAnchor:
    return AuthorityLineageRootAnchor(value.grant_id, value.digest())


def epoch_state(
    epoch: int = 7,
    revoked: tuple[str, ...] = (),
    *,
    context: AuthorityVerificationContext = CONTEXT,
) -> AuthorityEpochState:
    return AuthorityEpochState(
        trust_domain=context.trust_domain,
        tenant_id=context.tenant_id,
        organization_id=context.organization_id,
        mission_id=context.mission_id,
        epoch=epoch,
        revoked_grant_ids=revoked,
    )


class CanonicalRegistryIsolation:
    def setUp(self):
        self._epoch_registry_patcher = patch.object(
            authority_revocation_module,
            "_CANONICAL_AUTHORITY_EPOCH_REGISTRY",
            authority_revocation_module._AuthorityEpochRegistry(),
        )
        self.epoch_registry = self._epoch_registry_patcher.start()
        self._root_registry_patcher = patch.object(
            authority_revocation_module,
            "_CANONICAL_AUTHORITY_LINEAGE_ROOT_REGISTRY",
            authority_revocation_module._AuthorityLineageRootRegistry(),
        )
        self.root_registry = self._root_registry_patcher.start()

    def tearDown(self):
        self._root_registry_patcher.stop()
        self._epoch_registry_patcher.stop()

    def reset_registry(self):
        self.epoch_registry = authority_revocation_module._AuthorityEpochRegistry()
        self.root_registry = authority_revocation_module._AuthorityLineageRootRegistry()
        authority_revocation_module._CANONICAL_AUTHORITY_EPOCH_REGISTRY = self.epoch_registry
        authority_revocation_module._CANONICAL_AUTHORITY_LINEAGE_ROOT_REGISTRY = self.root_registry

    def register(self, value: AuthorityEpochState | None = None):
        return register_canonical_authority_epoch_state(value or epoch_state())

    def register_root(
        self,
        root: AuthorityGrant,
        *,
        context: AuthorityVerificationContext = CONTEXT,
        root_anchor: AuthorityLineageRootAnchor | None = None,
    ):
        return register_canonical_authority_lineage_root_anchor(
            context,
            root.epoch,
            root_anchor or anchor(root),
        )

    def bootstrap_chain(
        self,
        chain: tuple[AuthorityGrant, ...],
        *,
        state: AuthorityEpochState | None = None,
    ) -> None:
        self.register(state or epoch_state(epoch=chain[0].epoch))
        self.register_root(chain[0])


class AuthorityLineageAdmissionTests(CanonicalRegistryIsolation, unittest.TestCase):
    def admit(
        self,
        chain: tuple[AuthorityGrant, ...],
        *,
        bindings=BINDINGS,
        checker=verifier,
        context: AuthorityVerificationContext = CONTEXT,
    ):
        return authenticate_and_admit_authority_lineage(
            chain,
            bindings,
            checker,
            context=context,
        )

    def test_valid_three_hop_lineage_is_admitted_as_evidence_only(self):
        chain = lineage()
        self.bootstrap_chain(chain)
        result = self.admit(chain)
        self.assertIsInstance(result, EpochAdmittedAuthorityLineage)
        self.assertEqual(result.root_grant_id, "grant:root")
        self.assertEqual(result.leaf_grant_id, "grant:leaf")
        self.assertEqual(result.leaf_subject_id, "workload:executor")
        self.assertEqual(result.grant_ids, tuple(item.grant_id for item in chain))
        self.assertEqual(result.grant_digests, tuple(item.digest() for item in chain))
        self.assertEqual(len(result.lineage_digest), 64)
        self.assertEqual(result.epoch, 7)
        for forbidden in (
            "actions", "resource_scope", "authority_ceiling", "capabilities",
            "permission", "decision", "execute",
        ):
            with self.subTest(field=forbidden):
                self.assertFalse(hasattr(result, forbidden))

    def test_root_only_legacy_v1_grant_can_be_admitted(self):
        legacy = sign(root_unsigned(
            schema_version="1.0.0",
            delegation_allowed=False,
            delegation_depth_budget=0,
        ))
        self.bootstrap_chain((legacy,))
        result = self.admit((legacy,))
        self.assertEqual(result.grant_ids, (legacy.grant_id,))
        self.assertEqual(result.root_grant_id, result.leaf_grant_id)

    def test_public_lineage_api_accepts_no_caller_selected_root_or_state(self):
        parameters = inspect.signature(authenticate_and_admit_authority_lineage).parameters
        for forbidden in (
            "root_anchor", "root_registry", "epoch_state", "epoch_state_owner", "registry",
        ):
            with self.subTest(parameter=forbidden):
                self.assertNotIn(forbidden, parameters)

    def test_unregistered_root_binding_fails_before_verifier(self):
        self.register()
        calls = {"verifier": 0}
        def counting_verifier(*args):
            calls["verifier"] += 1
            return verifier(*args)
        with self.assertRaises(AuthorityGrantError):
            self.admit(lineage(), checker=counting_verifier)
        self.assertEqual(calls["verifier"], 0)

    def test_canonical_root_anchor_is_external_and_exact(self):
        chain = lineage()
        bad_anchors = (
            AuthorityLineageRootAnchor("grant:other", chain[0].digest()),
            AuthorityLineageRootAnchor(chain[0].grant_id, "0" * 64),
        )
        for bad in bad_anchors:
            self.reset_registry()
            self.register()
            self.register_root(chain[0], root_anchor=bad)
            calls = {"verifier": 0}
            def counting_verifier(*args):
                calls["verifier"] += 1
                return verifier(*args)
            with self.subTest(anchor=bad), self.assertRaises(AuthorityGrantError):
                self.admit(chain, checker=counting_verifier)
            self.assertEqual(calls["verifier"], 0)

    def test_lineage_cannot_self_select_arbitrary_root(self):
        canonical = lineage()
        self.bootstrap_chain(canonical)
        attacker_root = sign(root_unsigned(grant_id="grant:attacker"))
        attacker_mid = sign(mid_unsigned(parent_grant_id="grant:attacker"))
        attacker_chain = (attacker_root, attacker_mid, canonical[2])
        calls = {"verifier": 0}
        def counting_verifier(*args):
            calls["verifier"] += 1
            return verifier(*args)
        with self.assertRaises(AuthorityGrantError):
            self.admit(attacker_chain, checker=counting_verifier)
        self.assertEqual(calls["verifier"], 0)

    def test_invalid_root_anchor_shape_fails_closed_at_bootstrap(self):
        self.register()
        chain = lineage()
        bad = AuthorityLineageRootAnchor(chain[0].grant_id, "not-a-digest")
        with self.assertRaises(AuthorityGrantError):
            self.register_root(chain[0], root_anchor=bad)

    def test_root_registration_is_one_shot_and_has_no_replacement_path(self):
        chain = lineage()
        self.bootstrap_chain(chain)
        with self.assertRaises(AuthorityGrantError):
            self.register_root(chain[0])
        replacement = AuthorityLineageRootAnchor(chain[0].grant_id, "0" * 64)
        with self.assertRaises(AuthorityGrantError):
            self.register_root(chain[0], root_anchor=replacement)
        self.assertFalse(hasattr(self.root_registry, "unregister"))
        self.assertFalse(hasattr(self.root_registry, "replace"))

    def test_root_registration_requires_registered_current_context_epoch(self):
        root = lineage()[0]
        with self.assertRaises(AuthorityGrantError):
            self.register_root(root)
        self.register(epoch_state(epoch=7))
        future_root = sign(root_unsigned(epoch=8))
        with self.assertRaises(AuthorityGrantError):
            self.register_root(future_root)
        with self.assertRaises(AuthorityGrantError):
            register_canonical_authority_lineage_root_anchor(OTHER_CONTEXT, 7, anchor(root))

    def test_root_must_have_no_parent(self):
        root = sign(root_unsigned(parent_grant_id="grant:outside"))
        chain = (root, sign(mid_unsigned()), sign(leaf_unsigned()))
        self.bootstrap_chain(chain)
        with self.assertRaises(AuthorityGrantError):
            self.admit(chain)

    def test_duplicate_or_cyclic_grant_ids_fail_before_verifier(self):
        chain = lineage()
        self.bootstrap_chain(chain)
        duplicate_leaf = dataclasses.replace(chain[2], grant_id=chain[1].grant_id)
        calls = {"verifier": 0}
        def counting_verifier(*args):
            calls["verifier"] += 1
            return verifier(*args)
        with self.assertRaises(AuthorityGrantError):
            self.admit((chain[0], chain[1], duplicate_leaf), checker=counting_verifier)
        self.assertEqual(calls["verifier"], 0)

    def test_reordered_skipped_and_back_edge_lineages_fail(self):
        root, mid, leaf = lineage()
        self.bootstrap_chain((root, mid, leaf))
        variants = (
            (root, leaf, mid),
            (root, dataclasses.replace(leaf, parent_grant_id="grant:mid")),
            (root, mid, dataclasses.replace(leaf, parent_grant_id="grant:root")),
        )
        for chain in variants:
            with self.subTest(ids=tuple(item.grant_id for item in chain)), self.assertRaises(AuthorityGrantError):
                self.admit(chain)

    def test_legacy_v1_cannot_enter_delegated_lineage(self):
        legacy_root = sign(root_unsigned(
            schema_version="1.0.0",
            delegation_allowed=False,
            delegation_depth_budget=0,
        ))
        child = sign(mid_unsigned())
        chain = (legacy_root, child)
        self.bootstrap_chain(chain)
        with self.assertRaises(AuthorityGrantError):
            self.admit(chain)

    def test_context_and_attenuation_drift_fail_before_authentication(self):
        root, mid, leaf = lineage()
        mutations = (
            dataclasses.replace(mid, mission_id="mission:other"),
            dataclasses.replace(mid, resource_scope=("repo:other",)),
            dataclasses.replace(mid, actions=("read", "test", "deploy")),
            dataclasses.replace(mid, delegation_depth_budget=3),
            dataclasses.replace(root, delegation_allowed=False, delegation_depth_budget=0),
        )
        for changed in mutations:
            self.reset_registry()
            chain = (changed, mid, leaf) if changed.grant_id == root.grant_id else (root, changed, leaf)
            self.bootstrap_chain(chain)
            with self.subTest(grant=changed.grant_id), self.assertRaises(AuthorityGrantError):
                self.admit(chain)

    def test_forged_signature_at_any_hop_rejects_entire_lineage(self):
        base = lineage()
        for index in range(len(base)):
            self.reset_registry()
            self.bootstrap_chain(base)
            altered = list(base)
            altered[index] = dataclasses.replace(altered[index], signature="0" * 64)
            with self.subTest(index=index), self.assertRaises(AuthorityGrantError):
                self.admit(tuple(altered))

    def test_unregistered_context_fails_before_verifier(self):
        calls = {"verifier": 0}
        def counting_verifier(*args):
            calls["verifier"] += 1
            return verifier(*args)
        with self.assertRaises(AuthorityGrantError):
            self.admit(lineage(), checker=counting_verifier)
        self.assertEqual(calls["verifier"], 0)

    def test_revoked_root_intermediate_or_leaf_rejects_whole_lineage(self):
        chain = lineage()
        for grant_id in ("grant:root", "grant:mid", "grant:leaf"):
            self.reset_registry()
            self.register(epoch_state(revoked=(grant_id,)))
            self.register_root(chain[0])
            with self.subTest(grant_id=grant_id), self.assertRaises(AuthorityGrantError):
                self.admit(chain)

    def test_stale_and_future_epoch_lineages_are_rejected(self):
        stale = lineage(epoch=6)
        self.register(epoch_state(epoch=6))
        self.register_root(stale[0])
        advance_canonical_authority_epoch_state(epoch_state(epoch=7))
        with self.assertRaises(AuthorityGrantError):
            self.admit(stale)
        self.reset_registry()
        self.register(epoch_state(epoch=7))
        with self.assertRaises(AuthorityGrantError):
            self.admit(lineage(epoch=8))

    def test_epoch_advance_without_new_root_binding_denies_before_verifier(self):
        old = lineage(epoch=7)
        self.bootstrap_chain(old)
        advance_canonical_authority_epoch_state(epoch_state(epoch=8))
        new = lineage(epoch=8)
        calls = {"verifier": 0}
        def counting_verifier(*args):
            calls["verifier"] += 1
            return verifier(*args)
        with self.assertRaises(AuthorityGrantError):
            self.admit(new, checker=counting_verifier)
        self.assertEqual(calls["verifier"], 0)

    def test_new_epoch_requires_separately_bootstrapped_root_binding(self):
        old = lineage(epoch=7)
        self.bootstrap_chain(old)
        advance_canonical_authority_epoch_state(epoch_state(epoch=8))
        new = lineage(epoch=8)
        self.register_root(new[0])
        result = self.admit(new)
        self.assertEqual(result.epoch, 8)
        self.assertEqual(result.root_grant_id, new[0].grant_id)

    def test_epoch_advance_during_verification_is_seen_by_atomic_final_admission(self):
        chain = lineage()
        self.bootstrap_chain(chain)
        calls = {"count": 0}
        def advancing_verifier(*args):
            calls["count"] += 1
            if calls["count"] == 2:
                advance_canonical_authority_epoch_state(epoch_state(epoch=8))
            return verifier(*args)
        with self.assertRaises(AuthorityGrantError):
            self.admit(chain, checker=advancing_verifier)
        self.assertEqual(calls["count"], 3)

    def test_same_epoch_ancestor_revocation_during_verification_rejects_whole_lineage(self):
        chain = lineage()
        self.bootstrap_chain(chain)
        calls = {"count": 0}
        def revoking_verifier(*args):
            calls["count"] += 1
            if calls["count"] == 2:
                advance_canonical_authority_epoch_state(epoch_state(revoked=("grant:root",)))
            return verifier(*args)
        with self.assertRaises(AuthorityGrantError):
            self.admit(chain, checker=revoking_verifier)
        self.assertEqual(calls["count"], 3)

    def test_issuer_key_generator_is_materialized_once_for_all_hops(self):
        chain = lineage()
        self.bootstrap_chain(chain)
        result = self.admit(chain, bindings=(binding for binding in BINDINGS))
        self.assertEqual(result.leaf_grant_id, "grant:leaf")

    def test_subclass_substitution_fails_before_verifier(self):
        calls = {"verifier": 0}
        class SubstitutedAuthorityGrant(AuthorityGrant):
            pass
        root, mid, leaf = lineage()
        self.bootstrap_chain((root, mid, leaf))
        substituted = SubstitutedAuthorityGrant(**{
            field.name: getattr(mid, field.name)
            for field in dataclasses.fields(AuthorityGrant)
        })
        def counting_verifier(*args):
            calls["verifier"] += 1
            return verifier(*args)
        with self.assertRaises(AuthorityGrantError):
            self.admit((root, substituted, leaf), checker=counting_verifier)
        self.assertEqual(calls["verifier"], 0)

    def test_zero_or_ambiguous_binding_at_one_hop_fails_closed(self):
        chain = lineage()
        self.bootstrap_chain(chain)
        missing_mid = tuple(
            binding for binding in BINDINGS
            if binding.issuer_subject_id != "workload:parent"
        )
        duplicate_mid = BINDINGS + (
            IssuerKeyBinding("workload:parent", CONTEXT.trust_domain, "key:parent", ALGORITHM),
        )
        for bindings in (missing_mid, duplicate_mid):
            with self.subTest(bindings=len(bindings)), self.assertRaises(AuthorityGrantError):
                self.admit(chain, bindings=bindings)

    def test_verifier_exception_at_intermediate_hop_fails_closed(self):
        chain = lineage()
        self.bootstrap_chain(chain)
        calls = {"count": 0}
        def broken_verifier(*args):
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("provider unavailable")
            return verifier(*args)
        with self.assertRaises(AuthorityGrantError):
            self.admit(chain, checker=broken_verifier)
        self.assertEqual(calls["count"], 2)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import inspect
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.runtime_authority_binding import RuntimeEvidenceReference
from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_source import (
    AuthorityLineageRecord,
    AuthorityLookupKey,
    AuthoritySource,
    canonical_pr_authority_resource,
    canonical_source_lineage_digest,
)
from cyber_lion.enterprise.authority_verification import AuthorityVerificationContext, IssuerKeyBinding
from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.enterprise.persistent_authority_state import (
    DurableReplayGuard,
    PersistentBindingFinalizer,
    PersistentEpochStateProvider,
    PersistentRootAnchorProvider,
    SQLiteAuthorityStateStore,
)
from cyber_lion.enterprise.runtime_authority_bridge import (
    RuntimeAuthorityBridge,
    RuntimeAuthorityBridgeError,
    verify_authority_bound_n2_pair,
)

REPO = "DonkeyJJLove/ai_platform"
BASE = "1" * 40
HEAD = "2" * 40
MISSION = "LION-FLEET-EXECUTOR-ATTESTATION-V1"
GRANT_ID = "grant-fleet-n2"
CONTEXT = ("lion.test", "tenant-1", "org-1", MISSION)
NOW = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)


def runtime(slot: str, **overrides) -> RuntimeEvidenceReference:
    values = dict(
        runtime_evidence_digest=("a" if slot == "a" else "b") * 64,
        runtime_instance_id=f"runtime-{slot}",
        repository=REPO,
        base_sha=BASE,
        head_sha=HEAD,
        run_id="32388249699",
        run_attempt=1,
        provenance_ref=f"github-attestation:{slot}",
        artifact_digest=("c" if slot == "a" else "d") * 64,
        mission_id=MISSION,
    )
    values.update(overrides)
    return RuntimeEvidenceReference(**values)


def grant(*, epoch: int = 9, mission_id: str = MISSION, grant_id: str = GRANT_ID):
    key = AuthorityLookupKey(REPO, 41, BASE, HEAD, mission_id, grant_id)
    return AuthorityGrant(
        schema_version="1.1.0",
        grant_id=grant_id,
        issuer_subject_id="issuer-root",
        subject_id="fleet-runtime-bridge",
        tenant_id="tenant-1",
        organization_id="org-1",
        mission_id=mission_id,
        capability_id="fleet-runtime-authority-bind",
        capability_version="1.0.0",
        actions=("bind_runtime_authority",),
        resource_scope=(canonical_pr_authority_resource(key),),
        authority_ceiling="read",
        constraints=("post-execution-only",),
        parent_grant_id=None,
        issued_at="2026-08-20T14:00:00+00:00",
        expires_at="2026-08-21T14:00:00+00:00",
        epoch=epoch,
        policy_digest="sha256:" + "e" * 64,
        observability_contract_digest="sha256:" + "f" * 64,
        signature="externally-verified-signature",
        delegation_allowed=False,
        delegation_depth_budget=0,
    )


def record(value: AuthorityGrant | None = None, *, provenance="control-plane:authority:n2"):
    value = value or grant()
    key = AuthorityLookupKey(REPO, 41, BASE, HEAD, value.mission_id, value.grant_id)
    lineage = (value,)
    return AuthorityLineageRecord(
        lookup_key=key,
        lineage=lineage,
        lineage_digest=canonical_source_lineage_digest(lineage),
        provenance_id=provenance,
        source_kind="trusted-control-plane",
    )


class MutableSource(AuthoritySource):
    def __init__(self, value: AuthorityLineageRecord):
        self.value = value

    def _lookup_exact(self, key):
        return (self.value,)


class SignatureVerifier:
    def __init__(self, callback=None):
        self.callback = callback
        self.calls = 0

    def __call__(self, payload, signature, key_id, algorithm):
        self.calls += 1
        if self.callback:
            self.callback(self.calls)
        return signature == "externally-verified-signature" and key_id == "authority-key-1" and algorithm == "test-ed25519"


def admission(*, verifier=None):
    value = grant()
    temp = tempfile.TemporaryDirectory()
    store = SQLiteAuthorityStateStore(str(Path(temp.name) / "authority.db"))
    store.bootstrap_context(CONTEXT, epoch=value.epoch)
    store.register_root(CONTEXT, epoch=value.epoch, root_grant_id=value.grant_id, root_grant_digest=value.digest())
    source = MutableSource(record(value))
    verifier = verifier or SignatureVerifier()
    finalizer = PersistentBindingFinalizer(store)
    subject = LiveAuthorityAdmission(
        authority_source=source,
        context=AuthorityVerificationContext("lion.test", "tenant-1", "org-1", MISSION),
        issuer_keys=(IssuerKeyBinding("issuer-root", "lion.test", "authority-key-1", "test-ed25519"),),
        signature_verifier=verifier,
        epoch_provider=PersistentEpochStateProvider(store),
        root_provider=PersistentRootAnchorProvider(store),
        replay_guard=DurableReplayGuard(store, domain="live-authority-admission"),
        binding_finalizer=finalizer,
    )
    return subject, source, store, finalizer, verifier, temp


def bridge(live):
    return RuntimeAuthorityBridge(
        live_admission=live,
        repository=REPO,
        pr_number=41,
        base_sha=BASE,
        head_sha=HEAD,
        mission_id=MISSION,
    )


def bind(subject, slot="a", **kwargs):
    values = dict(
        grant_id=GRANT_ID,
        admission_nonce=f"admit-{slot}-{kwargs.pop('nonce_suffix', 'x')}",
        binding_nonce=f"bind-{slot}-{kwargs.pop('bind_suffix', 'x')}",
        now=NOW,
    )
    values.update(kwargs)
    return subject.bind(runtime(slot), **values)


class RuntimeAuthorityBridgeTests(unittest.TestCase):
    def make_bridge(self, *, verifier=None):
        live, source, store, finalizer, verifier, temp = admission(verifier=verifier)
        self.addCleanup(temp.cleanup)
        return bridge(live), live, source, store, finalizer, verifier

    def test_valid_live_admission_binding_pass(self):
        subject, *_ = self.make_bridge()
        result = bind(subject)
        self.assertEqual(result.runtime_instance_id, "runtime-a")
        self.assertEqual(result.authority_state_version, 1)
        self.assertEqual(len(result.live_admission_digest), 64)
        self.assertEqual(len(result.live_admission_replay_digest), 64)
        self.assertEqual(len(result.live_finalization_digest), 64)
        self.assertEqual(len(result.live_finalization_key_digest), 64)
        self.assertEqual(len(result.binding_digest), 64)

    def test_authentication_only_constructor_path_absent(self):
        parameters = inspect.signature(RuntimeAuthorityBridge).parameters
        self.assertIn("live_admission", parameters)
        self.assertNotIn("authority_source", parameters)
        self.assertNotIn("authenticator", parameters)
        self.assertNotIn("replay_guard", parameters)

    def test_caller_cannot_inject_admission_or_finalization_receipt(self):
        parameters = inspect.signature(RuntimeAuthorityBridge.bind).parameters
        self.assertNotIn("admitted", parameters)
        self.assertNotIn("live_admitted_authority", parameters)
        self.assertNotIn("finalized", parameters)

    def test_forged_live_admitted_authority_denied(self):
        _, live, _, _, _, _ = self.make_bridge()
        receipt = live.admit(repository=REPO, pr_number=41, base_sha=BASE, head_sha=HEAD, mission_id=MISSION, grant_id=GRANT_ID, now=NOW, replay_nonce="one")
        forged = replace(receipt, authority_ceiling="external_write")
        with self.assertRaises(Exception):
            live.revalidate(forged, now=NOW)

    def test_wrong_lineage_provenance_root_state_and_key_denied(self):
        _, live, _, _, _, _ = self.make_bridge()
        receipt = live.admit(repository=REPO, pr_number=41, base_sha=BASE, head_sha=HEAD, mission_id=MISSION, grant_id=GRANT_ID, now=NOW, replay_nonce="one")
        for altered in (
            replace(receipt, lineage_digest="0" * 64),
            replace(receipt, provenance_id="control-plane:other"),
            replace(receipt, root_grant_digest="1" * 64),
            replace(receipt, epoch_state_version=99),
            replace(receipt, leaf_key_id="other-key"),
            replace(receipt, leaf_algorithm="other-alg"),
            replace(receipt, authenticated_grant_digests=("2" * 64,)),
        ):
            with self.assertRaises(Exception):
                live.revalidate(altered, now=NOW)

    def test_revoked_during_authentication_denied(self):
        holder = {}
        verifier = SignatureVerifier(lambda call: holder["store"].advance_epoch(CONTEXT, epoch=9, revoked_grant_ids=(GRANT_ID,)) if call == 1 else None)
        subject, _, _, store, _, _ = self.make_bridge(verifier=verifier)
        holder["store"] = store
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bind(subject)

    def test_epoch_change_during_authentication_denied(self):
        holder = {}
        verifier = SignatureVerifier(lambda call: holder["store"].advance_epoch(CONTEXT, epoch=10, revoked_grant_ids=()) if call == 1 else None)
        subject, _, _, store, _, _ = self.make_bridge(verifier=verifier)
        holder["store"] = store
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bind(subject)

    def test_revoke_after_revalidate_before_finalize_denied(self):
        subject, _, _, store, finalizer, _ = self.make_bridge()
        original = finalizer.finalize

        def revoke_then_finalize(context, **kwargs):
            store.advance_epoch(CONTEXT, epoch=9, revoked_grant_ids=(GRANT_ID,))
            return original(context, **kwargs)

        finalizer.finalize = revoke_then_finalize
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bind(subject)

    def test_epoch_advance_after_revalidate_before_finalize_denied(self):
        subject, _, _, store, finalizer, _ = self.make_bridge()
        original = finalizer.finalize

        def advance_then_finalize(context, **kwargs):
            store.advance_epoch(CONTEXT, epoch=10, revoked_grant_ids=())
            return original(context, **kwargs)

        finalizer.finalize = advance_then_finalize
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bind(subject)

    def test_no_signature_verification_occurs_inside_finalization(self):
        subject, _, _, _, finalizer, verifier = self.make_bridge()
        original = finalizer.finalize
        observed = []

        def checked_finalize(context, **kwargs):
            observed.append(verifier.calls)
            result = original(context, **kwargs)
            observed.append(verifier.calls)
            return result

        finalizer.finalize = checked_finalize
        bind(subject)
        self.assertEqual(observed[0], observed[1])
        self.assertGreater(observed[0], 0)

    def test_expired_before_binding_denied(self):
        subject, *_ = self.make_bridge()
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bind(subject, now=datetime(2026, 8, 22, 15, 0, tzinfo=timezone.utc))

    def test_wrong_runtime_head_denied_before_admission(self):
        subject, *_ = self.make_bridge()
        with self.assertRaises(RuntimeAuthorityBridgeError):
            subject.bind(runtime("a", head_sha="3" * 40), grant_id=GRANT_ID, admission_nonce="a", binding_nonce="b", now=NOW)

    def test_binding_finalization_replay_denied(self):
        _, live, _, _, _, _ = self.make_bridge()
        runtime_digest = runtime("a").runtime_evidence_digest
        binding_nonce = "bind-a-same"

        receipt = live.admit(
            repository=REPO,
            pr_number=41,
            base_sha=BASE,
            head_sha=HEAD,
            mission_id=MISSION,
            grant_id=GRANT_ID,
            now=NOW,
            replay_nonce="manual-1",
        )
        first = live.finalize_binding(
            receipt,
            runtime_evidence_digest=runtime_digest,
            binding_nonce=binding_nonce,
            now=NOW,
        )
        self.assertEqual(len(first.finalization_key_digest), 64)

        with self.assertRaises(Exception):
            live.finalize_binding(
                receipt,
                runtime_evidence_digest=runtime_digest,
                binding_nonce=binding_nonce,
                now=NOW,
            )

        fresh_receipt = live.admit(
            repository=REPO,
            pr_number=41,
            base_sha=BASE,
            head_sha=HEAD,
            mission_id=MISSION,
            grant_id=GRANT_ID,
            now=NOW,
            replay_nonce="manual-2",
        )
        second = live.finalize_binding(
            fresh_receipt,
            runtime_evidence_digest=runtime_digest,
            binding_nonce=binding_nonce,
            now=NOW,
        )
        self.assertNotEqual(first.finalization_key_digest, second.finalization_key_digest)

    def test_two_distinct_runtime_records_share_one_live_authority_root(self):
        subject, *_ = self.make_bridge()
        first = bind(subject, "a", nonce_suffix="1", bind_suffix="1")
        second = bind(subject, "b", nonce_suffix="2", bind_suffix="2")
        pair = verify_authority_bound_n2_pair(first, second)
        self.assertNotEqual(pair[0].runtime_instance_id, pair[1].runtime_instance_id)
        self.assertEqual(pair[0].authority_root_grant_digest, pair[1].authority_root_grant_digest)
        self.assertEqual(pair[0].authority_state_version, pair[1].authority_state_version)
        self.assertNotEqual(pair[0].live_finalization_digest, pair[1].live_finalization_digest)

    def test_duplicate_runtime_cannot_satisfy_authority_bound_n2(self):
        subject, *_ = self.make_bridge()
        first = bind(subject, "a", nonce_suffix="1", bind_suffix="1")
        with self.assertRaises(RuntimeAuthorityBridgeError):
            verify_authority_bound_n2_pair(first, first)

    def test_different_live_authority_root_denied_for_n2(self):
        subject, *_ = self.make_bridge()
        first = bind(subject, "a", nonce_suffix="1", bind_suffix="1")
        second = bind(subject, "b", nonce_suffix="2", bind_suffix="2")
        altered = replace(second, authority_root_grant_digest="9" * 64)
        with self.assertRaises(RuntimeAuthorityBridgeError):
            verify_authority_bound_n2_pair(first, altered)

    def test_binding_digest_changes_with_live_admission_and_finalization(self):
        subject, *_ = self.make_bridge()
        first = bind(subject, "a", nonce_suffix="1", bind_suffix="1")
        second = bind(subject, "b", nonce_suffix="2", bind_suffix="2")
        self.assertNotEqual(first.live_admission_digest, second.live_admission_digest)
        self.assertNotEqual(first.live_admission_replay_digest, second.live_admission_replay_digest)
        self.assertNotEqual(first.live_finalization_digest, second.live_finalization_digest)
        self.assertNotEqual(first.live_finalization_key_digest, second.live_finalization_key_digest)
        self.assertNotEqual(first.binding_digest, second.binding_digest)

    def test_runtime_reference_has_no_authority_input(self):
        self.assertFalse(hasattr(runtime("a"), "authority_digest"))
        self.assertFalse(hasattr(runtime("a"), "live_admission_digest"))
        self.assertFalse(hasattr(runtime("a"), "live_finalization_digest"))


if __name__ == "__main__":
    unittest.main()

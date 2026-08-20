from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import inspect
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
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority, LiveAuthorityAdmission
from cyber_lion.enterprise.persistent_authority_state import PersistentEpochSnapshot, PersistentRootAnchor
from cyber_lion.enterprise.runtime_authority_bridge import (
    InMemoryRuntimeAuthorityReplayGuard,
    RuntimeAuthorityBridge,
    RuntimeAuthorityBridgeError,
    verify_authority_bound_n2_pair,
)

REPO = "DonkeyJJLove/ai_platform"
BASE = "1" * 40
HEAD = "2" * 40
MISSION = "LION-FLEET-EXECUTOR-ATTESTATION-V1"
GRANT_ID = "grant-fleet-n2"
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


class MutableEpochProvider:
    def __init__(self, epoch=9, version=1, revoked=()):
        self.epoch = epoch
        self.version = version
        self.revoked = tuple(revoked)

    def current(self, context):
        return PersistentEpochSnapshot(*context, self.epoch, self.revoked, self.version)

    def revoke(self, grant_id):
        if grant_id not in self.revoked:
            self.revoked = self.revoked + (grant_id,)
            self.version += 1

    def advance(self):
        self.epoch += 1
        self.version += 1
        self.revoked = ()


class MutableRootProvider:
    def __init__(self, value: AuthorityGrant):
        self.by_epoch = {value.epoch: PersistentRootAnchor("lion.test", "tenant-1", "org-1", MISSION, value.epoch, value.grant_id, value.digest())}

    def resolve(self, context, epoch):
        return self.by_epoch[epoch]

    def replace_digest(self, epoch, digest):
        current = self.by_epoch[epoch]
        self.by_epoch[epoch] = replace(current, root_grant_digest=digest)


class AdmissionReplay:
    def __init__(self):
        self.seen = set()

    def consume(self, digest, *, consumed_at):
        if digest in self.seen:
            return False
        self.seen.add(digest)
        return True


class SignatureVerifier:
    def __init__(self, callback=None):
        self.callback = callback
        self.calls = 0

    def __call__(self, payload, signature, key_id, algorithm):
        self.calls += 1
        if self.callback:
            self.callback(self.calls)
        return signature == "externally-verified-signature" and key_id == "authority-key-1" and algorithm == "test-ed25519"


def admission(*, value=None, state=None, root=None, verifier=None, source=None):
    value = value or grant()
    source = source or MutableSource(record(value))
    state = state or MutableEpochProvider(epoch=value.epoch)
    root = root or MutableRootProvider(value)
    verifier = verifier or SignatureVerifier()
    subject = LiveAuthorityAdmission(
        authority_source=source,
        context=AuthorityVerificationContext("lion.test", "tenant-1", "org-1", MISSION),
        issuer_keys=(IssuerKeyBinding("issuer-root", "lion.test", "authority-key-1", "test-ed25519"),),
        signature_verifier=verifier,
        epoch_provider=state,
        root_provider=root,
        replay_guard=AdmissionReplay(),
    )
    return subject, source, state, root, verifier


def bridge(live=None, replay=None):
    live = live or admission()[0]
    return RuntimeAuthorityBridge(
        live_admission=live,
        replay_guard=replay or InMemoryRuntimeAuthorityReplayGuard(),
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
    def test_valid_live_admission_binding_pass(self):
        result = bind(bridge())
        self.assertEqual(result.runtime_instance_id, "runtime-a")
        self.assertEqual(result.authority_state_version, 1)
        self.assertEqual(len(result.live_admission_digest), 64)
        self.assertEqual(len(result.live_admission_replay_digest), 64)
        self.assertEqual(len(result.binding_digest), 64)

    def test_authentication_only_constructor_path_absent(self):
        parameters = inspect.signature(RuntimeAuthorityBridge).parameters
        self.assertIn("live_admission", parameters)
        self.assertNotIn("authority_source", parameters)
        self.assertNotIn("authenticator", parameters)

    def test_caller_cannot_inject_admission_receipt(self):
        parameters = inspect.signature(RuntimeAuthorityBridge.bind).parameters
        self.assertNotIn("admitted", parameters)
        self.assertNotIn("live_admitted_authority", parameters)

    def test_forged_live_admitted_authority_denied(self):
        live, *_ = admission()
        receipt = live.admit(repository=REPO, pr_number=41, base_sha=BASE, head_sha=HEAD, mission_id=MISSION, grant_id=GRANT_ID, now=NOW, replay_nonce="one")
        forged = replace(receipt, authority_ceiling="external_write")
        with self.assertRaises(Exception):
            live.revalidate(forged, now=NOW)

    def test_wrong_lineage_provenance_root_state_and_key_denied(self):
        live, source, state, root, _ = admission()
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
        state = MutableEpochProvider()
        verifier = SignatureVerifier(lambda call: state.revoke(GRANT_ID) if call == 1 else None)
        live, *_ = admission(state=state, verifier=verifier)
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bind(bridge(live))

    def test_epoch_change_during_authentication_denied(self):
        state = MutableEpochProvider()
        verifier = SignatureVerifier(lambda call: state.advance() if call == 1 else None)
        live, *_ = admission(state=state, verifier=verifier)
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bind(bridge(live))

    def test_revocation_during_revalidation_denied(self):
        state = MutableEpochProvider()
        verifier = SignatureVerifier(lambda call: state.revoke(GRANT_ID) if call == 2 else None)
        live, *_ = admission(state=state, verifier=verifier)
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bind(bridge(live))

    def test_epoch_change_during_revalidation_denied(self):
        state = MutableEpochProvider()
        verifier = SignatureVerifier(lambda call: state.advance() if call == 2 else None)
        live, *_ = admission(state=state, verifier=verifier)
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bind(bridge(live))

    def test_expired_before_binding_denied(self):
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bind(bridge(), now=datetime(2026, 8, 22, 15, 0, tzinfo=timezone.utc))

    def test_wrong_runtime_head_denied_before_admission(self):
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bridge().bind(runtime("a", head_sha="3" * 40), grant_id=GRANT_ID, admission_nonce="a", binding_nonce="b", now=NOW)

    def test_binding_replay_denied(self):
        subject = bridge()
        bind(subject, nonce_suffix="1", bind_suffix="same")
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bind(subject, nonce_suffix="2", bind_suffix="same")

    def test_two_distinct_runtime_records_share_one_live_authority_root(self):
        subject = bridge()
        first = bind(subject, "a", nonce_suffix="1", bind_suffix="1")
        second = bind(subject, "b", nonce_suffix="2", bind_suffix="2")
        pair = verify_authority_bound_n2_pair(first, second)
        self.assertNotEqual(pair[0].runtime_instance_id, pair[1].runtime_instance_id)
        self.assertEqual(pair[0].authority_root_grant_digest, pair[1].authority_root_grant_digest)
        self.assertEqual(pair[0].authority_state_version, pair[1].authority_state_version)

    def test_duplicate_runtime_cannot_satisfy_authority_bound_n2(self):
        subject = bridge()
        first = bind(subject, "a", nonce_suffix="1", bind_suffix="1")
        with self.assertRaises(RuntimeAuthorityBridgeError):
            verify_authority_bound_n2_pair(first, first)

    def test_different_live_authority_root_denied_for_n2(self):
        subject = bridge()
        first = bind(subject, "a", nonce_suffix="1", bind_suffix="1")
        second = bind(subject, "b", nonce_suffix="2", bind_suffix="2")
        altered = replace(second, authority_root_grant_digest="9" * 64)
        with self.assertRaises(RuntimeAuthorityBridgeError):
            verify_authority_bound_n2_pair(first, altered)

    def test_binding_digest_changes_with_live_admission_fields(self):
        subject = bridge()
        first = bind(subject, "a", nonce_suffix="1", bind_suffix="1")
        second = bind(subject, "b", nonce_suffix="2", bind_suffix="2")
        self.assertNotEqual(first.live_admission_digest, second.live_admission_digest)
        self.assertNotEqual(first.live_admission_replay_digest, second.live_admission_replay_digest)
        self.assertNotEqual(first.binding_digest, second.binding_digest)

    def test_runtime_reference_has_no_authority_input(self):
        self.assertFalse(hasattr(runtime("a"), "authority_digest"))
        self.assertFalse(hasattr(runtime("a"), "live_admission_digest"))


if __name__ == "__main__":
    unittest.main()

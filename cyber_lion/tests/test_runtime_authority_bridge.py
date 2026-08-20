from __future__ import annotations

from dataclasses import replace
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
from cyber_lion.enterprise.authority_verification import AuthenticatedAuthorityGrant
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


def grant(*, mission_id: str = MISSION, resource_scope=None, grant_id: str = GRANT_ID):
    key = AuthorityLookupKey(REPO, 41, BASE, HEAD, mission_id, grant_id)
    if resource_scope is None:
        resource_scope = (canonical_pr_authority_resource(key),)
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
        resource_scope=resource_scope,
        authority_ceiling="read",
        constraints=("post-execution-only",),
        parent_grant_id=None,
        issued_at="2026-08-20T14:00:00+00:00",
        expires_at="2026-08-21T14:00:00+00:00",
        epoch=9,
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


class StaticSource(AuthoritySource):
    def __init__(self, candidates):
        self.candidates = candidates

    def _lookup_exact(self, key):
        return self.candidates


class Authenticator:
    def __init__(self, *, forged_digest: str | None = None):
        self.forged_digest = forged_digest

    def authenticate(self, value: AuthorityGrant) -> AuthenticatedAuthorityGrant:
        return AuthenticatedAuthorityGrant(
            grant_id=value.grant_id,
            issuer_subject_id=value.issuer_subject_id,
            subject_id=value.subject_id,
            trust_domain="lion.test",
            tenant_id=value.tenant_id,
            organization_id=value.organization_id,
            mission_id=value.mission_id,
            key_id="authority-key-1",
            algorithm="test-ed25519",
            signed_payload=b"authenticated-outside-runtime",
            grant_digest=self.forged_digest or value.digest(),
        )


def bridge(source: AuthoritySource, authenticator=None, replay=None) -> RuntimeAuthorityBridge:
    return RuntimeAuthorityBridge(
        authority_source=source,
        authenticator=authenticator or Authenticator(),
        replay_guard=replay or InMemoryRuntimeAuthorityReplayGuard(),
        repository=REPO,
        pr_number=41,
        base_sha=BASE,
        head_sha=HEAD,
        mission_id=MISSION,
    )


class RuntimeAuthorityBridgeTests(unittest.TestCase):
    def test_exact_canonical_authority_binds_runtime(self):
        result = bridge(StaticSource((record(),))).bind(
            runtime("a"), grant_id=GRANT_ID, binding_nonce="nonce-a"
        )
        self.assertEqual(result.runtime_instance_id, "runtime-a")
        self.assertEqual(result.authority_provenance_id, "control-plane:authority:n2")
        self.assertEqual(result.authority_epoch, 9)
        self.assertEqual(len(result.binding_digest), 64)

    def test_missing_authority_fails_closed(self):
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bridge(StaticSource(())).bind(runtime("a"), grant_id=GRANT_ID, binding_nonce="n")

    def test_ambiguous_authority_fails_closed(self):
        value = record()
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bridge(StaticSource((value, value))).bind(
                runtime("a"), grant_id=GRANT_ID, binding_nonce="n"
            )

    def test_wrong_runtime_mission_denied_before_authority_use(self):
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bridge(StaticSource((record(),))).bind(
                runtime("a", mission_id="OTHER"), grant_id=GRANT_ID, binding_nonce="n"
            )

    def test_wrong_runtime_head_denied(self):
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bridge(StaticSource((record(),))).bind(
                runtime("a", head_sha="3" * 40), grant_id=GRANT_ID, binding_nonce="n"
            )

    def test_forged_authenticated_grant_digest_denied(self):
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bridge(
                StaticSource((record(),)),
                Authenticator(forged_digest="0" * 64),
            ).bind(runtime("a"), grant_id=GRANT_ID, binding_nonce="n")

    def test_repository_tree_cannot_pose_as_authority_source(self):
        bad = replace(record(), source_kind="github-pr-tree")
        with self.assertRaises(RuntimeAuthorityBridgeError):
            bridge(StaticSource((bad,))).bind(
                runtime("a"), grant_id=GRANT_ID, binding_nonce="n"
            )

    def test_replayed_binding_denied(self):
        guard = InMemoryRuntimeAuthorityReplayGuard()
        subject = bridge(StaticSource((record(),)), replay=guard)
        subject.bind(runtime("a"), grant_id=GRANT_ID, binding_nonce="same")
        with self.assertRaises(RuntimeAuthorityBridgeError):
            subject.bind(runtime("a"), grant_id=GRANT_ID, binding_nonce="same")

    def test_two_distinct_runtime_records_share_one_authority_root(self):
        source = StaticSource((record(),))
        subject = bridge(source)
        first = subject.bind(runtime("a"), grant_id=GRANT_ID, binding_nonce="a")
        second = subject.bind(runtime("b"), grant_id=GRANT_ID, binding_nonce="b")
        pair = verify_authority_bound_n2_pair(first, second)
        self.assertNotEqual(pair[0].runtime_instance_id, pair[1].runtime_instance_id)

    def test_duplicate_runtime_cannot_satisfy_authority_bound_n2(self):
        subject = bridge(StaticSource((record(),)))
        first = subject.bind(runtime("a"), grant_id=GRANT_ID, binding_nonce="a")
        with self.assertRaises(RuntimeAuthorityBridgeError):
            verify_authority_bound_n2_pair(first, first)

    def test_mismatched_authority_root_denied_for_n2(self):
        source = StaticSource((record(),))
        subject = bridge(source)
        first = subject.bind(runtime("a"), grant_id=GRANT_ID, binding_nonce="a")
        second = subject.bind(runtime("b"), grant_id=GRANT_ID, binding_nonce="b")
        altered = replace(second, authority_lineage_digest="9" * 64)
        with self.assertRaises(RuntimeAuthorityBridgeError):
            verify_authority_bound_n2_pair(first, altered)

    def test_runtime_reference_has_no_authority_digest_input(self):
        self.assertFalse(hasattr(runtime("a"), "authority_digest"))


if __name__ == "__main__":
    unittest.main()

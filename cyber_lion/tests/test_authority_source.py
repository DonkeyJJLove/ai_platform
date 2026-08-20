import unittest
from dataclasses import FrozenInstanceError

from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_source import (
    AuthorityLineageRecord,
    AuthorityLookupKey,
    AuthoritySource,
    AuthoritySourceError,
    canonical_pr_authority_resource,
    canonical_source_lineage_digest,
)


REPO = "DonkeyJJLove/ai_platform"
BASE = "1" * 40
HEAD = "2" * 40
MISSION = "RCCM-1E-GOV"
GRANT = "grant-live-merge-1"


def make_grant(
    *,
    grant_id=GRANT,
    mission_id=MISSION,
    parent_grant_id=None,
    resource_scope=None,
):
    if resource_scope is None:
        resource_scope = (
            f"github:repo:{REPO}:pr:31:base:{BASE}:head:{HEAD}",
        )
    return AuthorityGrant(
        schema_version="1.1.0",
        grant_id=grant_id,
        issuer_subject_id="issuer-root",
        subject_id="merge-executor",
        tenant_id="tenant-1",
        organization_id="org-1",
        mission_id=mission_id,
        capability_id="github-merge",
        capability_version="1.0.0",
        actions=("merge_pull_request",),
        resource_scope=resource_scope,
        authority_ceiling="external_write",
        constraints=("merge_method:merge",),
        parent_grant_id=parent_grant_id,
        issued_at="2026-08-19T20:00:00+00:00",
        expires_at="2026-08-21T20:00:00+00:00",
        epoch=7,
        policy_digest="sha256:" + "a" * 64,
        observability_contract_digest="sha256:" + "b" * 64,
        signature="test-signature-not-secret",
        delegation_allowed=False,
        delegation_depth_budget=0,
    )


def make_key(**overrides):
    values = dict(
        repository=REPO,
        pr_number=31,
        base_sha=BASE,
        head_sha=HEAD,
        mission_id=MISSION,
        grant_id=GRANT,
    )
    values.update(overrides)
    return AuthorityLookupKey(**values)


def make_record(
    *,
    key=None,
    lineage=None,
    digest=None,
    provenance="control-plane:record:1",
    source_kind="trusted-control-plane",
):
    key = key or make_key()
    if lineage is None:
        lineage = (make_grant(resource_scope=(canonical_pr_authority_resource(key),)),)
    return AuthorityLineageRecord(
        lookup_key=key,
        lineage=lineage,
        lineage_digest=digest or canonical_source_lineage_digest(lineage),
        provenance_id=provenance,
        source_kind=source_kind,
    )


class StaticAuthoritySource(AuthoritySource):
    def __init__(self, candidates):
        self.candidates = candidates

    def _lookup_exact(self, key):
        return self.candidates


class AuthoritySourceContractTests(unittest.TestCase):
    def test_exact_lookup_key_is_valid_and_immutable(self):
        key = make_key().validate()
        self.assertEqual(key.binding(), (REPO, 31, BASE, HEAD, MISSION, GRANT))
        with self.assertRaises(FrozenInstanceError):
            key.pr_number = 32

    def test_lookup_key_rejects_partial_sha(self):
        with self.assertRaises(AuthoritySourceError):
            make_key(head_sha="abc123").validate()

    def test_canonical_pr_resource_binding_is_exact(self):
        key = make_key()
        self.assertEqual(
            canonical_pr_authority_resource(key),
            f"github:repo:{REPO}:pr:31:base:{BASE}:head:{HEAD}",
        )
        self.assertIs(make_record(key=key).validate().lookup_key, key)

    def test_lineage_digest_is_deterministic(self):
        lineage = (make_grant(),)
        first = canonical_source_lineage_digest(lineage)
        second = canonical_source_lineage_digest(lineage)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_record_requires_exact_leaf_grant_binding(self):
        wrong_leaf = make_grant(grant_id="other-grant")
        record = make_record(lineage=(wrong_leaf,))
        with self.assertRaisesRegex(AuthoritySourceError, "leaf"):
            record.validate()

    def test_record_requires_matching_mission(self):
        wrong_mission = make_grant(mission_id="OTHER-MISSION")
        record = make_record(lineage=(wrong_mission,))
        with self.assertRaisesRegex(AuthoritySourceError, "mission_id"):
            record.validate()

    def test_record_rejects_resource_scope_repository_mismatch(self):
        wrong = make_grant(
            resource_scope=(
                f"github:repo:OtherOwner/other:pr:31:base:{BASE}:head:{HEAD}",
            )
        )
        with self.assertRaisesRegex(AuthoritySourceError, "exact PR resource"):
            make_record(lineage=(wrong,)).validate()

    def test_record_rejects_resource_scope_pr_mismatch(self):
        wrong = make_grant(
            resource_scope=(
                f"github:repo:{REPO}:pr:32:base:{BASE}:head:{HEAD}",
            )
        )
        with self.assertRaisesRegex(AuthoritySourceError, "exact PR resource"):
            make_record(lineage=(wrong,)).validate()

    def test_record_rejects_resource_scope_base_mismatch(self):
        wrong = make_grant(
            resource_scope=(
                f"github:repo:{REPO}:pr:31:base:{'3' * 40}:head:{HEAD}",
            )
        )
        with self.assertRaisesRegex(AuthoritySourceError, "exact PR resource"):
            make_record(lineage=(wrong,)).validate()

    def test_record_rejects_resource_scope_head_mismatch(self):
        wrong = make_grant(
            resource_scope=(
                f"github:repo:{REPO}:pr:31:base:{BASE}:head:{'4' * 40}",
            )
        )
        with self.assertRaisesRegex(AuthoritySourceError, "exact PR resource"):
            make_record(lineage=(wrong,)).validate()

    def test_record_rejects_tampered_lineage_digest(self):
        record = make_record(digest="0" * 64)
        with self.assertRaisesRegex(AuthoritySourceError, "lineage_digest"):
            record.validate()

    def test_record_rejects_pr_tree_as_authority_source(self):
        record = make_record(source_kind="github-pr-tree")
        with self.assertRaisesRegex(AuthoritySourceError, "trusted-control-plane"):
            record.validate()

    def test_record_is_immutable(self):
        record = make_record().validate()
        with self.assertRaises(FrozenInstanceError):
            record.provenance_id = "control-plane:record:2"

    def test_zero_candidates_fail_closed(self):
        source = StaticAuthoritySource(())
        with self.assertRaisesRegex(AuthoritySourceError, "not found"):
            source.resolve_exact(make_key())

    def test_exactly_one_candidate_resolves(self):
        record = make_record()
        source = StaticAuthoritySource((record,))
        self.assertIs(source.resolve_exact(make_key()), record)

    def test_many_candidates_fail_closed_as_ambiguous(self):
        record = make_record()
        source = StaticAuthoritySource((record, record))
        with self.assertRaisesRegex(AuthoritySourceError, "ambiguous"):
            source.resolve_exact(make_key())

    def test_backend_must_return_immutable_tuple(self):
        source = StaticAuthoritySource([make_record()])
        with self.assertRaisesRegex(AuthoritySourceError, "immutable tuple"):
            source.resolve_exact(make_key())

    def test_single_candidate_with_wrong_exact_key_fails_closed(self):
        record = make_record(key=make_key(pr_number=32))
        source = StaticAuthoritySource((record,))
        with self.assertRaisesRegex(AuthoritySourceError, "exact lookup key"):
            source.resolve_exact(make_key())

    def test_provenance_id_is_required_and_bounded(self):
        with self.assertRaisesRegex(AuthoritySourceError, "provenance_id"):
            make_record(provenance="").validate()


if __name__ == "__main__":
    unittest.main()

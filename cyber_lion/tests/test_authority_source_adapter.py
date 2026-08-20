import inspect
import unittest
from dataclasses import asdict

from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_source import (
    AuthorityLookupKey,
    AuthoritySourceError,
    canonical_pr_authority_resource,
    canonical_source_lineage_digest,
)
from cyber_lion.enterprise.authority_source_adapter import (
    AuthoritySourceTransport,
    TrustedControlPlaneAuthoritySource,
)


REPO = "DonkeyJJLove/ai_platform"
BASE = "1" * 40
HEAD = "2" * 40
MISSION = "RCCM-1E-GOV"
GRANT = "grant-live-merge-1"


def make_key(**overrides):
    values = dict(
        repository=REPO,
        pr_number=33,
        base_sha=BASE,
        head_sha=HEAD,
        mission_id=MISSION,
        grant_id=GRANT,
    )
    values.update(overrides)
    return AuthorityLookupKey(**values).validate()


def make_grant(*, key=None):
    key = key or make_key()
    return AuthorityGrant(
        schema_version="1.1.0",
        grant_id=key.grant_id,
        issuer_subject_id="issuer-root",
        subject_id="merge-executor",
        tenant_id="tenant-1",
        organization_id="org-1",
        mission_id=key.mission_id,
        capability_id="github-merge",
        capability_version="1.0.0",
        actions=("merge_pull_request",),
        resource_scope=(canonical_pr_authority_resource(key),),
        authority_ceiling="external_write",
        constraints=("merge_method:merge",),
        parent_grant_id=None,
        issued_at="2026-08-19T20:00:00+00:00",
        expires_at="2026-08-21T20:00:00+00:00",
        epoch=7,
        policy_digest="sha256:" + "a" * 64,
        observability_contract_digest="sha256:" + "b" * 64,
        signature="test-signature-not-secret",
        delegation_allowed=False,
        delegation_depth_budget=0,
    ).validate()


def raw_key(key):
    return {
        "repository": key.repository,
        "pr_number": key.pr_number,
        "base_sha": key.base_sha,
        "head_sha": key.head_sha,
        "mission_id": key.mission_id,
        "grant_id": key.grant_id,
    }


def raw_grant(grant):
    value = asdict(grant)
    value["actions"] = list(grant.actions)
    value["resource_scope"] = list(grant.resource_scope)
    value["constraints"] = list(grant.constraints)
    return value


def raw_record(*, key=None, digest=None, source_kind="trusted-control-plane"):
    key = key or make_key()
    lineage = (make_grant(key=key),)
    return {
        "lookup_key": raw_key(key),
        "lineage": [raw_grant(lineage[0])],
        "lineage_digest": digest or canonical_source_lineage_digest(lineage),
        "provenance_id": "control-plane:record:1",
        "source_kind": source_kind,
    }


class StaticTransport(AuthoritySourceTransport):
    def __init__(self, records):
        self.records = records
        self.calls = []

    def lookup_exact(self, **kwargs):
        self.calls.append(kwargs)
        return self.records


class FailingTransport(AuthoritySourceTransport):
    def lookup_exact(self, **kwargs):
        raise RuntimeError("backend unavailable")


class AuthoritySourceAdapterTests(unittest.TestCase):
    def test_exact_lookup_parameters_are_forwarded_once(self):
        key = make_key()
        transport = StaticTransport((raw_record(key=key),))
        record = TrustedControlPlaneAuthoritySource(transport).resolve_exact(key)
        self.assertEqual(record.lookup_key.binding(), key.binding())
        self.assertEqual(
            transport.calls,
            [
                {
                    "repository": key.repository,
                    "pr_number": key.pr_number,
                    "base_sha": key.base_sha,
                    "head_sha": key.head_sha,
                    "mission_id": key.mission_id,
                    "grant_id": key.grant_id,
                }
            ],
        )

    def test_one_canonical_record_resolves_to_immutable_contract(self):
        key = make_key()
        record = TrustedControlPlaneAuthoritySource(
            StaticTransport((raw_record(key=key),))
        ).resolve_exact(key)
        self.assertEqual(record.source_kind, "trusted-control-plane")
        self.assertIs(type(record.lineage), tuple)
        self.assertIs(type(record.lineage[0]), AuthorityGrant)

    def test_zero_records_deny(self):
        with self.assertRaisesRegex(AuthoritySourceError, "not found"):
            TrustedControlPlaneAuthoritySource(StaticTransport(())).resolve_exact(make_key())

    def test_multiple_records_deny(self):
        record = raw_record()
        with self.assertRaisesRegex(AuthoritySourceError, "ambiguous"):
            TrustedControlPlaneAuthoritySource(
                StaticTransport((record, dict(record)))
            ).resolve_exact(make_key())

    def test_transport_failure_denies(self):
        with self.assertRaisesRegex(AuthoritySourceError, "unavailable"):
            TrustedControlPlaneAuthoritySource(FailingTransport()).resolve_exact(make_key())

    def test_mutable_transport_result_denies(self):
        with self.assertRaisesRegex(AuthoritySourceError, "immutable tuple"):
            TrustedControlPlaneAuthoritySource(
                StaticTransport([raw_record()])
            ).resolve_exact(make_key())

    def test_malformed_record_denies_unknown_fields(self):
        record = raw_record()
        record["unexpected"] = "value"
        with self.assertRaisesRegex(AuthoritySourceError, "not canonical"):
            TrustedControlPlaneAuthoritySource(
                StaticTransport((record,))
            ).resolve_exact(make_key())

    def test_malformed_grant_denies_unknown_fields(self):
        record = raw_record()
        record["lineage"][0]["unexpected"] = "value"
        with self.assertRaisesRegex(AuthoritySourceError, "not canonical"):
            TrustedControlPlaneAuthoritySource(
                StaticTransport((record,))
            ).resolve_exact(make_key())

    def test_tampered_lineage_digest_denies(self):
        with self.assertRaisesRegex(AuthoritySourceError, "lineage_digest"):
            TrustedControlPlaneAuthoritySource(
                StaticTransport((raw_record(digest="0" * 64),))
            ).resolve_exact(make_key())

    def test_pr_tree_source_denies(self):
        with self.assertRaisesRegex(AuthoritySourceError, "trusted-control-plane"):
            TrustedControlPlaneAuthoritySource(
                StaticTransport((raw_record(source_kind="pr-tree"),))
            ).resolve_exact(make_key())

    def test_exact_lookup_binding_mismatches_deny(self):
        requested = make_key()
        mismatches = {
            "repository": make_key(repository="OtherOwner/other"),
            "pr": make_key(pr_number=34),
            "base": make_key(base_sha="3" * 40),
            "head": make_key(head_sha="4" * 40),
            "mission": make_key(mission_id="OTHER-MISSION"),
            "grant": make_key(grant_id="other-grant"),
        }
        for name, returned_key in mismatches.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(AuthoritySourceError, "different exact lookup key"):
                    TrustedControlPlaneAuthoritySource(
                        StaticTransport((raw_record(key=returned_key),))
                    ).resolve_exact(requested)

    def test_transport_contract_exposes_only_read_operation(self):
        declared_public_callables = {
            name
            for name, value in AuthoritySourceTransport.__dict__.items()
            if not name.startswith("_") and callable(value)
        }
        self.assertEqual(declared_public_callables, {"lookup_exact"})

    def test_adapter_has_no_secret_material_configuration_surface(self):
        self.assertEqual(TrustedControlPlaneAuthoritySource.__slots__, ("_transport",))
        parameters = tuple(inspect.signature(TrustedControlPlaneAuthoritySource.__init__).parameters)
        self.assertEqual(parameters, ("self", "transport"))
        forbidden = {"secret", "password", "token", "credential", "private_key"}
        self.assertTrue(forbidden.isdisjoint(parameters))


if __name__ == "__main__":
    unittest.main()

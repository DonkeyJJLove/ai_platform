from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict, replace
import unittest

from cyber_lion.enterprise.authority_verification import IssuerKeyBinding
from cyber_lion.enterprise.pr_authority_bootstrap import (
    PRAuthorityBootstrapError,
    PRAuthorityBootstrapLookupKey,
    PRAuthorityBootstrapRecord,
    PRAuthorityBootstrapSource,
    PRAuthorityBootstrapTransport,
    TrustedControlPlanePRAuthorityBootstrapSource,
    canonical_pr_bootstrap_digest,
    decode_pr_authority_bootstrap_record,
)

REPO = "DonkeyJJLove/ai_platform"
BASE = "a" * 40
HEAD = "b" * 40
ROOT = "c" * 64


def key() -> PRAuthorityBootstrapLookupKey:
    return PRAuthorityBootstrapLookupKey(
        repository=REPO,
        pr_number=37,
        base_sha=BASE,
        head_sha=HEAD,
        merge_method="merge",
    ).validate()


def issuer() -> IssuerKeyBinding:
    return IssuerKeyBinding(
        issuer_subject_id="issuer-1",
        trust_domain="github-ci",
        key_id="key-1",
        algorithm="test",
    ).validate()


def record(*, lookup_key=None, source_kind="trusted-control-plane"):
    provisional = PRAuthorityBootstrapRecord(
        lookup_key=lookup_key or key(),
        mission_id="mission-37",
        grant_id="grant-37",
        trust_domain="github-ci",
        tenant_id="tenant-1",
        organization_id="org-1",
        epoch=7,
        root_grant_id="root-37",
        root_grant_digest=ROOT,
        issuer_key_bindings=(issuer(),),
        provenance_id="control-plane:bootstrap:37",
        bootstrap_digest="0" * 64,
        source_kind=source_kind,
    )
    return replace(
        provisional,
        bootstrap_digest=canonical_pr_bootstrap_digest(provisional),
    ).validate()


def wire(value: PRAuthorityBootstrapRecord) -> dict[str, object]:
    payload = {
        "lookup_key": asdict(value.lookup_key),
        "mission_id": value.mission_id,
        "grant_id": value.grant_id,
        "trust_domain": value.trust_domain,
        "tenant_id": value.tenant_id,
        "organization_id": value.organization_id,
        "epoch": value.epoch,
        "root_grant_id": value.root_grant_id,
        "root_grant_digest": value.root_grant_digest,
        "issuer_key_bindings": [asdict(item) for item in value.issuer_key_bindings],
        "provenance_id": value.provenance_id,
        "bootstrap_digest": value.bootstrap_digest,
        "source_kind": value.source_kind,
    }
    return payload


class StaticSource(PRAuthorityBootstrapSource):
    def __init__(self, candidates):
        self.candidates = candidates

    def _lookup_exact(self, lookup_key):
        return self.candidates


class StaticTransport(PRAuthorityBootstrapTransport):
    def __init__(self, candidates, *, fail=False):
        self.candidates = candidates
        self.fail = fail
        self.calls = []

    def lookup_exact(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("transport secret must not escape")
        return self.candidates


class PRAuthorityBootstrapTests(unittest.TestCase):
    def test_lookup_key_is_exact_and_immutable(self):
        value = key()
        self.assertEqual(
            value.binding(), (REPO, 37, BASE, HEAD, "merge")
        )
        with self.assertRaises(FrozenInstanceError):
            value.pr_number = 38

    def test_partial_sha_denied(self):
        with self.assertRaises(PRAuthorityBootstrapError):
            PRAuthorityBootstrapLookupKey(
                REPO, 37, "abc", HEAD, "merge"
            ).validate()

    def test_invalid_merge_method_denied(self):
        with self.assertRaises(PRAuthorityBootstrapError):
            PRAuthorityBootstrapLookupKey(
                REPO, 37, BASE, HEAD, "octopus"
            ).validate()

    def test_record_is_immutable_and_converts_to_live_bootstrap(self):
        value = record()
        with self.assertRaises(FrozenInstanceError):
            value.epoch = 8
        bootstrap = value.to_live_admission_bootstrap()
        self.assertEqual(bootstrap.mission_id, "mission-37")
        self.assertEqual(bootstrap.grant_id, "grant-37")
        self.assertEqual(bootstrap.epoch, 7)
        self.assertEqual(value.issuer_key_bindings, (issuer(),))

    def test_canonical_digest_detects_mutation(self):
        value = record()
        bad = replace(value, mission_id="other")
        with self.assertRaises(PRAuthorityBootstrapError):
            bad.validate()

    def test_non_trusted_source_denied(self):
        provisional = record()
        bad = replace(
            provisional,
            source_kind="pr-tree",
            bootstrap_digest="0" * 64,
        )
        bad = replace(
            bad,
            bootstrap_digest=canonical_pr_bootstrap_digest(bad),
        )
        with self.assertRaises(PRAuthorityBootstrapError):
            bad.validate()

    def test_zero_one_many_fail_closed(self):
        lookup = key()
        with self.assertRaises(PRAuthorityBootstrapError):
            StaticSource(()).resolve_exact(lookup)
        self.assertEqual(
            StaticSource((record(),)).resolve_exact(lookup),
            record(),
        )
        with self.assertRaises(PRAuthorityBootstrapError):
            StaticSource((record(), record())).resolve_exact(lookup)

    def test_exact_record_binding_required(self):
        lookup = key()
        other_key = replace(lookup, head_sha="d" * 40)
        other = record(lookup_key=other_key)
        with self.assertRaises(PRAuthorityBootstrapError):
            StaticSource((other,)).resolve_exact(lookup)

    def test_strict_wire_decode_round_trip(self):
        original = record()
        decoded = decode_pr_authority_bootstrap_record(wire(original))
        self.assertEqual(decoded, original)
        self.assertIsInstance(decoded.issuer_key_bindings, tuple)

    def test_unknown_secret_wire_field_denied(self):
        payload = wire(record())
        payload["private_key"] = "secret"
        with self.assertRaises(PRAuthorityBootstrapError):
            decode_pr_authority_bootstrap_record(payload)

    def test_unknown_nested_lookup_field_denied(self):
        payload = wire(record())
        payload["lookup_key"]["mission_id"] = "self-selected"
        with self.assertRaises(PRAuthorityBootstrapError):
            decode_pr_authority_bootstrap_record(payload)

    def test_unknown_issuer_field_denied(self):
        payload = wire(record())
        payload["issuer_key_bindings"][0]["token"] = "secret"
        with self.assertRaises(PRAuthorityBootstrapError):
            decode_pr_authority_bootstrap_record(payload)

    def test_empty_issuer_bindings_denied(self):
        payload = wire(record())
        payload["issuer_key_bindings"] = []
        with self.assertRaises(PRAuthorityBootstrapError):
            decode_pr_authority_bootstrap_record(payload)

    def test_transport_is_read_only_exact_lookup_surface(self):
        public = {
            name
            for name in dir(PRAuthorityBootstrapTransport)
            if not name.startswith("_")
        }
        self.assertEqual(public, {"lookup_exact"})

    def test_trusted_transport_called_once_with_exact_pr_identity(self):
        transport = StaticTransport((wire(record()),))
        source = TrustedControlPlanePRAuthorityBootstrapSource(transport)
        resolved = source.resolve_exact(key())
        self.assertEqual(resolved, record())
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(
            transport.calls[0],
            {
                "repository": REPO,
                "pr_number": 37,
                "base_sha": BASE,
                "head_sha": HEAD,
                "merge_method": "merge",
            },
        )

    def test_transport_failure_denied_without_raw_error_contract(self):
        transport = StaticTransport((), fail=True)
        source = TrustedControlPlanePRAuthorityBootstrapSource(transport)
        with self.assertRaisesRegex(
            PRAuthorityBootstrapError, "trusted bootstrap transport failed"
        ):
            source.resolve_exact(key())

    def test_transport_many_is_ambiguous(self):
        transport = StaticTransport((wire(record()), wire(record())))
        source = TrustedControlPlanePRAuthorityBootstrapSource(transport)
        with self.assertRaisesRegex(
            PRAuthorityBootstrapError, "ambiguous"
        ):
            source.resolve_exact(key())

    def test_transport_non_tuple_denied(self):
        transport = StaticTransport([wire(record())])
        source = TrustedControlPlanePRAuthorityBootstrapSource(transport)
        with self.assertRaisesRegex(
            PRAuthorityBootstrapError, "immutable tuple"
        ):
            source.resolve_exact(key())

    def test_discovery_record_does_not_expose_permission_or_consumption(self):
        names = set(PRAuthorityBootstrapRecord.__dataclass_fields__)
        self.assertNotIn("decision", names)
        self.assertNotIn("authorized", names)
        self.assertNotIn("consumed", names)
        self.assertNotIn("token", names)
        self.assertNotIn("private_key", names)


if __name__ == "__main__":
    unittest.main()

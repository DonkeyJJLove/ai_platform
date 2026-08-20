from __future__ import annotations

import inspect
import unittest
from dataclasses import FrozenInstanceError, asdict

from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_source import (
    AuthorityLookupKey,
    canonical_pr_authority_resource,
    canonical_source_lineage_digest,
)
from cyber_lion.enterprise.authority_verification import IssuerKeyBinding
from cyber_lion.enterprise.ci_live_admission import (
    CILiveAdmissionBootstrap,
    ReadOnlyAuthorityControlPlaneTransport,
    admission_exit_code,
    run_live_admission,
)
from cyber_lion.enterprise.merge_admission import TrustedPullRequestState

REPO = "DonkeyJJLove/ai_platform"
BASE = "a" * 40
HEAD = "b" * 40
POLICY = "sha256:" + "1" * 64
OBS = "sha256:" + "2" * 64


def verifier(payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
    return signature == "sig" and key_id == "key-1" and algorithm == "test"


def rejecting_verifier(payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
    return False


class CILiveAdmissionRuntimeTests(unittest.TestCase):
    def _fixture(
        self,
        suffix: str,
        *,
        merge_method: str = "merge",
        constraint: str | None = None,
        source_kind: str = "trusted-control-plane",
        returned_head: str = HEAD,
        records: int = 1,
    ):
        mission = f"ci-runtime-{suffix}"
        grant_id = f"grant-{suffix}"
        key = AuthorityLookupKey(
            repository=REPO,
            pr_number=35,
            base_sha=BASE,
            head_sha=returned_head,
            mission_id=mission,
            grant_id=grant_id,
        ).validate()
        grant = AuthorityGrant(
            schema_version="1.1.0",
            grant_id=grant_id,
            issuer_subject_id="issuer",
            subject_id="merge-executor",
            tenant_id="tenant",
            organization_id="org",
            mission_id=mission,
            capability_id="github.merge",
            capability_version="1.0.0",
            actions=("merge_pull_request",),
            resource_scope=(canonical_pr_authority_resource(key),),
            authority_ceiling="external_write",
            constraints=(constraint or f"merge_method:{merge_method}",),
            parent_grant_id=None,
            issued_at="2026-08-20T00:00:00+00:00",
            expires_at="2026-08-21T00:00:00+00:00",
            epoch=7,
            policy_digest=POLICY,
            observability_contract_digest=OBS,
            signature="sig",
            delegation_allowed=False,
            delegation_depth_budget=0,
        ).validate()
        raw_grant = asdict(grant)
        raw_grant["actions"] = list(grant.actions)
        raw_grant["resource_scope"] = list(grant.resource_scope)
        raw_grant["constraints"] = list(grant.constraints)
        raw_record = {
            "lookup_key": {
                "repository": key.repository,
                "pr_number": key.pr_number,
                "base_sha": key.base_sha,
                "head_sha": key.head_sha,
                "mission_id": key.mission_id,
                "grant_id": key.grant_id,
            },
            "lineage": [raw_grant],
            "lineage_digest": canonical_source_lineage_digest((grant,)),
            "provenance_id": f"control-plane:ci:{suffix}",
            "source_kind": source_kind,
        }
        calls = []

        def lookup(**kwargs):
            calls.append(kwargs)
            if records == 0:
                return ()
            if records == 2:
                return (raw_record, dict(raw_record))
            return (raw_record,)

        bootstrap = CILiveAdmissionBootstrap(
            trust_domain="github.test",
            tenant_id="tenant",
            organization_id="org",
            mission_id=mission,
            grant_id=grant_id,
            epoch=7,
            root_grant_id=grant.grant_id,
            root_grant_digest=grant.digest(),
        ).validate()
        trusted = TrustedPullRequestState(
            repository=REPO,
            pr_number=35,
            base_sha=BASE,
            head_sha=HEAD,
            merge_method=merge_method,
        ).validate()
        keys = (
            IssuerKeyBinding(
                issuer_subject_id="issuer",
                trust_domain="github.test",
                key_id="key-1",
                algorithm="test",
            ).validate(),
        )
        transport = ReadOnlyAuthorityControlPlaneTransport(lookup)
        return trusted, bootstrap, transport, keys, calls

    def _run(self, suffix: str, **kwargs):
        trusted, bootstrap, transport, keys, calls = self._fixture(suffix, **kwargs)
        receipt = run_live_admission(
            pr_state=trusted,
            bootstrap=bootstrap,
            authority_transport=transport,
            issuer_keys=keys,
            verifier=verifier,
            admission_id=f"admission-{suffix}",
        )
        return receipt, trusted, bootstrap, transport, keys, calls

    def test_exact_live_admission_allows_with_immutable_evidence(self):
        receipt, trusted, bootstrap, _, _, calls = self._run("allow")
        self.assertEqual(receipt.decision, "ALLOW")
        self.assertEqual(admission_exit_code(receipt), 0)
        self.assertEqual(receipt.repository, trusted.repository)
        self.assertEqual(receipt.head_sha, trusted.head_sha)
        self.assertEqual(receipt.mission_id, bootstrap.mission_id)
        self.assertIsNotNone(receipt.evidence)
        with self.assertRaises(FrozenInstanceError):
            receipt.decision = "DENY"
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0],
            {
                "repository": REPO,
                "pr_number": 35,
                "base_sha": BASE,
                "head_sha": HEAD,
                "mission_id": bootstrap.mission_id,
                "grant_id": bootstrap.grant_id,
            },
        )

    def test_zero_authority_records_denies(self):
        receipt, *_ = self._run("zero", records=0)
        self.assertEqual(receipt.decision, "DENY")
        self.assertEqual(admission_exit_code(receipt), 1)
        self.assertIsNone(receipt.evidence)

    def test_ambiguous_authority_records_denies(self):
        receipt, *_ = self._run("many", records=2)
        self.assertEqual(receipt.decision, "DENY")
        self.assertIsNone(receipt.evidence)

    def test_pr_tree_authority_denies(self):
        receipt, *_ = self._run("pr-tree", source_kind="pr-tree")
        self.assertEqual(receipt.decision, "DENY")
        self.assertIsNone(receipt.evidence)

    def test_exact_authority_lookup_head_mismatch_denies(self):
        receipt, _, _, _, _, calls = self._run("head-mismatch", returned_head="c" * 40)
        self.assertEqual(receipt.decision, "DENY")
        self.assertEqual(len(calls), 1)

    def test_invalid_signature_denies(self):
        trusted, bootstrap, transport, keys, _ = self._fixture("signature")
        receipt = run_live_admission(
            pr_state=trusted,
            bootstrap=bootstrap,
            authority_transport=transport,
            issuer_keys=keys,
            verifier=rejecting_verifier,
            admission_id="admission-signature",
        )
        self.assertEqual(receipt.decision, "DENY")

    def test_wrong_merge_method_constraint_denies(self):
        receipt, *_ = self._run("method", merge_method="merge", constraint="merge_method:squash")
        self.assertEqual(receipt.decision, "DENY")

    def test_wrong_root_anchor_denies(self):
        trusted, bootstrap, transport, keys, _ = self._fixture("root")
        wrong = CILiveAdmissionBootstrap(
            trust_domain=bootstrap.trust_domain,
            tenant_id=bootstrap.tenant_id,
            organization_id=bootstrap.organization_id,
            mission_id=bootstrap.mission_id,
            grant_id=bootstrap.grant_id,
            epoch=bootstrap.epoch,
            root_grant_id=bootstrap.root_grant_id,
            root_grant_digest="0" * 64,
        ).validate()
        receipt = run_live_admission(
            pr_state=trusted,
            bootstrap=wrong,
            authority_transport=transport,
            issuer_keys=keys,
            verifier=verifier,
            admission_id="admission-root",
        )
        self.assertEqual(receipt.decision, "DENY")

    def test_transport_contract_exposes_only_exact_read_operation(self):
        declared_public_callables = {
            name
            for name, value in ReadOnlyAuthorityControlPlaneTransport.__dict__.items()
            if not name.startswith("_") and callable(value)
        }
        self.assertEqual(declared_public_callables, {"lookup_exact"})
        self.assertEqual(ReadOnlyAuthorityControlPlaneTransport.__slots__, ("_lookup",))

    def test_runtime_has_no_consumption_or_secret_configuration_surface(self):
        runtime_parameters = set(inspect.signature(run_live_admission).parameters)
        self.assertNotIn("consumption_owner", runtime_parameters)
        self.assertNotIn("secret", runtime_parameters)
        self.assertNotIn("token", runtime_parameters)
        bootstrap_fields = set(CILiveAdmissionBootstrap.__dataclass_fields__)
        forbidden = {"secret", "password", "token", "credential", "private_key", "authority_payload"}
        self.assertTrue(forbidden.isdisjoint(bootstrap_fields))
        transport_parameters = set(inspect.signature(ReadOnlyAuthorityControlPlaneTransport.__init__).parameters)
        self.assertEqual(transport_parameters, {"self", "lookup"})


if __name__ == "__main__":
    unittest.main()

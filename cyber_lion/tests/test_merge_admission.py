from __future__ import annotations

import inspect
import threading
import unittest
from dataclasses import FrozenInstanceError

from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_revocation import (
    AuthorityEpochState,
    AuthorityLineageRootAnchor,
    advance_canonical_authority_epoch_state,
    register_canonical_authority_epoch_state,
    register_canonical_authority_lineage_root_anchor,
)
from cyber_lion.enterprise.authority_source import (
    AuthorityLineageRecord,
    AuthorityLookupKey,
    AuthoritySource,
    canonical_source_lineage_digest,
)
from cyber_lion.enterprise.authority_verification import (
    AuthorityVerificationContext,
    IssuerKeyBinding,
)
from cyber_lion.enterprise.merge_admission import (
    MergeAdmissionError,
    MergeAuthorityConsumptionOwner,
    MergeIntent,
    NonConsumingMergeAdmissionEvidence,
    TrustedPullRequestState,
    admit_merge,
    admit_merge_non_consuming,
    canonical_merge_method_constraint,
    canonical_merge_resource,
    issue_merge_execution_receipt,
)

BASE = "a" * 40
HEAD = "b" * 40
MERGE = "c" * 40
POLICY = "sha256:" + "1" * 64
OBS = "sha256:" + "2" * 64
REPO = "DonkeyJJLove/ai_platform"


def _verifier(payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
    return signature == "sig" and key_id == "key-1" and algorithm == "test"


def _rejecting_verifier(payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
    return False


class StaticAuthoritySource(AuthoritySource):
    def __init__(self, records):
        self.records = records
        self.calls = []

    def _lookup_exact(self, key):
        self.calls.append(key)
        return self.records


class MergeAdmissionTests(unittest.TestCase):
    def _fixture(
        self,
        suffix: str,
        *,
        repository: str = REPO,
        pr_number: int = 31,
        base_sha: str = BASE,
        head_sha: str = HEAD,
        merge_method: str = "merge",
        include_action: bool = True,
        resource_override: str | None = None,
        constraint_override: str | None = None,
        epoch: int = 1,
    ):
        context = AuthorityVerificationContext(
            trust_domain="github.test",
            tenant_id="tenant",
            organization_id="org",
            mission_id=f"mission-{suffix}",
        )
        intent = MergeIntent(
            repository=repository,
            pr_number=pr_number,
            base_sha=base_sha,
            head_sha=head_sha,
            merge_method=merge_method,
        )
        resource = resource_override or canonical_merge_resource(intent)
        constraint = constraint_override or canonical_merge_method_constraint(intent)
        grant = AuthorityGrant(
            schema_version="1.1.0",
            grant_id=f"grant-{suffix}",
            issuer_subject_id="issuer",
            subject_id="executor",
            tenant_id=context.tenant_id,
            organization_id=context.organization_id,
            mission_id=context.mission_id,
            capability_id="github.merge",
            capability_version="1",
            actions=("merge_pull_request",) if include_action else ("read",),
            resource_scope=(resource,),
            authority_ceiling="external_write",
            constraints=(constraint,),
            parent_grant_id=None,
            issued_at="2026-08-20T00:00:00+02:00",
            expires_at="2026-08-21T00:00:00+02:00",
            epoch=epoch,
            policy_digest=POLICY,
            observability_contract_digest=OBS,
            signature="sig",
            delegation_allowed=False,
            delegation_depth_budget=0,
        ).validate()
        register_canonical_authority_epoch_state(
            AuthorityEpochState(
                trust_domain=context.trust_domain,
                tenant_id=context.tenant_id,
                organization_id=context.organization_id,
                mission_id=context.mission_id,
                epoch=epoch,
            )
        )
        register_canonical_authority_lineage_root_anchor(
            context,
            epoch,
            AuthorityLineageRootAnchor(
                root_grant_id=grant.grant_id,
                root_grant_digest=grant.digest(),
            ),
        )
        keys = (
            IssuerKeyBinding(
                issuer_subject_id="issuer",
                trust_domain=context.trust_domain,
                key_id="key-1",
                algorithm="test",
            ),
        )
        trusted = TrustedPullRequestState(
            repository=repository,
            pr_number=pr_number,
            base_sha=base_sha,
            head_sha=head_sha,
            merge_method=merge_method,
        )
        key = AuthorityLookupKey(
            repository=repository,
            pr_number=pr_number,
            base_sha=base_sha,
            head_sha=head_sha,
            mission_id=context.mission_id,
            grant_id=grant.grant_id,
        ).validate()
        lineage = (grant,)
        record = AuthorityLineageRecord(
            lookup_key=key,
            lineage=lineage,
            lineage_digest=canonical_source_lineage_digest(lineage),
            provenance_id=f"control-plane:merge:{suffix}",
            source_kind="trusted-control-plane",
        ).validate()
        source = StaticAuthoritySource((record,))
        return context, intent, trusted, lineage, keys, key, source

    def _admit_consuming(self, suffix: str, **kwargs):
        context, intent, trusted, lineage, keys, _, _ = self._fixture(suffix, **kwargs)
        owner = MergeAuthorityConsumptionOwner()
        decision = admit_merge(
            intent=intent,
            trusted_state=trusted,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=owner,
            admission_id=f"admission-{suffix}",
        )
        return decision, owner, context, intent, trusted, lineage, keys

    def _admit_non_consuming(self, suffix: str, **kwargs):
        context, intent, trusted, lineage, keys, key, source = self._fixture(suffix, **kwargs)
        result = admit_merge_non_consuming(
            intent=intent,
            trusted_state=trusted,
            authority_source=source,
            lookup_key=key,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            admission_id=f"live-{suffix}",
        )
        return result, context, intent, trusted, lineage, keys, key, source

    def test_non_consuming_exact_match_allows_with_immutable_evidence(self):
        result, context, intent, _, lineage, _, key, source = self._admit_non_consuming("live-allow")
        self.assertEqual(result.decision, "ALLOW")
        self.assertIs(type(result.evidence), NonConsumingMergeAdmissionEvidence)
        evidence = result.evidence
        assert evidence is not None
        self.assertEqual(evidence.repository, intent.repository)
        self.assertEqual(evidence.pr_number, intent.pr_number)
        self.assertEqual(evidence.base_sha, intent.base_sha)
        self.assertEqual(evidence.head_sha, intent.head_sha)
        self.assertEqual(evidence.merge_method, intent.merge_method)
        self.assertEqual(evidence.mission_id, context.mission_id)
        self.assertEqual(evidence.grant_id, key.grant_id)
        self.assertEqual(evidence.grant_digest, lineage[-1].digest())
        self.assertEqual(evidence.authority_source_kind, "trusted-control-plane")
        self.assertEqual(source.calls, [key])
        with self.assertRaises(FrozenInstanceError):
            evidence.epoch = 99

    def test_non_consuming_can_repeat_without_consumption(self):
        context, intent, trusted, _, keys, key, source = self._fixture("repeat")
        first = admit_merge_non_consuming(
            intent=intent,
            trusted_state=trusted,
            authority_source=source,
            lookup_key=key,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            admission_id="live-repeat-1",
        )
        second = admit_merge_non_consuming(
            intent=intent,
            trusted_state=trusted,
            authority_source=source,
            lookup_key=key,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            admission_id="live-repeat-2",
        )
        self.assertEqual(first.decision, "ALLOW")
        self.assertEqual(second.decision, "ALLOW")
        self.assertNotIn("consumption_owner", inspect.signature(admit_merge_non_consuming).parameters)

    def test_non_consuming_zero_source_records_denies(self):
        context, intent, trusted, _, keys, key, _ = self._fixture("zero")
        result = admit_merge_non_consuming(
            intent=intent,
            trusted_state=trusted,
            authority_source=StaticAuthoritySource(()),
            lookup_key=key,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            admission_id="live-zero",
        )
        self.assertEqual(result.decision, "DENY")
        self.assertIsNone(result.evidence)

    def test_non_consuming_ambiguous_source_denies(self):
        context, intent, trusted, _, keys, key, source = self._fixture("ambiguous")
        record = source.records[0]
        result = admit_merge_non_consuming(
            intent=intent,
            trusted_state=trusted,
            authority_source=StaticAuthoritySource((record, record)),
            lookup_key=key,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            admission_id="live-ambiguous",
        )
        self.assertEqual(result.decision, "DENY")

    def test_non_consuming_exact_lookup_binding_mismatch_denies_before_source(self):
        context, intent, trusted, _, keys, key, source = self._fixture("lookup-mismatch")
        wrong = AuthorityLookupKey(
            key.repository,
            key.pr_number,
            key.base_sha,
            "d" * 40,
            key.mission_id,
            key.grant_id,
        ).validate()
        result = admit_merge_non_consuming(
            intent=intent,
            trusted_state=trusted,
            authority_source=source,
            lookup_key=wrong,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            admission_id="live-lookup-mismatch",
        )
        self.assertEqual(result.decision, "DENY")
        self.assertEqual(source.calls, [])

    def test_non_consuming_trusted_pr_head_mismatch_denies(self):
        context, intent, trusted, _, keys, key, source = self._fixture("trusted-head")
        moved = TrustedPullRequestState(
            trusted.repository,
            trusted.pr_number,
            trusted.base_sha,
            "d" * 40,
            trusted.merge_method,
        )
        result = admit_merge_non_consuming(
            intent=intent,
            trusted_state=moved,
            authority_source=source,
            lookup_key=key,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            admission_id="live-trusted-head",
        )
        self.assertEqual(result.decision, "DENY")

    def test_non_consuming_invalid_signature_denies(self):
        context, intent, trusted, _, keys, key, source = self._fixture("bad-signature")
        result = admit_merge_non_consuming(
            intent=intent,
            trusted_state=trusted,
            authority_source=source,
            lookup_key=key,
            issuer_keys=keys,
            verifier=_rejecting_verifier,
            context=context,
            admission_id="live-bad-signature",
        )
        self.assertEqual(result.decision, "DENY")

    def test_non_consuming_current_epoch_change_denies(self):
        context, intent, trusted, _, keys, key, source = self._fixture("epoch", epoch=2)
        advance_canonical_authority_epoch_state(
            AuthorityEpochState(
                trust_domain=context.trust_domain,
                tenant_id=context.tenant_id,
                organization_id=context.organization_id,
                mission_id=context.mission_id,
                epoch=3,
            )
        )
        result = admit_merge_non_consuming(
            intent=intent,
            trusted_state=trusted,
            authority_source=source,
            lookup_key=key,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            admission_id="live-epoch",
        )
        self.assertEqual(result.decision, "DENY")

    def test_non_consuming_wrong_merge_method_constraint_denies(self):
        result, *_ = self._admit_non_consuming(
            "wrong-method",
            constraint_override="merge_method:squash",
        )
        self.assertEqual(result.decision, "DENY")

    def test_non_consuming_wrong_action_denies(self):
        result, *_ = self._admit_non_consuming("wrong-action", include_action=False)
        self.assertEqual(result.decision, "DENY")

    def test_existing_consuming_exact_match_allows_and_consumes(self):
        decision, owner, *_ = self._admit_consuming("consume-allow")
        self.assertEqual(decision.decision, "ALLOW")
        self.assertTrue(
            owner.is_consumed(
                grant_id=decision.grant_id,
                grant_digest=decision.grant_digest,
                epoch=decision.epoch,
            )
        )

    def test_existing_consuming_same_grant_replay_denies(self):
        context, intent, trusted, lineage, keys, _, _ = self._fixture("consume-replay")
        owner = MergeAuthorityConsumptionOwner()
        first = admit_merge(
            intent=intent,
            trusted_state=trusted,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=owner,
            admission_id="consume-replay-1",
        )
        second = admit_merge(
            intent=intent,
            trusted_state=trusted,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=owner,
            admission_id="consume-replay-2",
        )
        self.assertEqual(first.decision, "ALLOW")
        self.assertEqual(second.decision, "DENY")

    def test_existing_consuming_concurrent_replay_allows_exactly_once(self):
        context, intent, trusted, lineage, keys, _, _ = self._fixture("consume-race")
        owner = MergeAuthorityConsumptionOwner()
        decisions = []
        lock = threading.Lock()

        def run(index):
            decision = admit_merge(
                intent=intent,
                trusted_state=trusted,
                lineage=lineage,
                issuer_keys=keys,
                verifier=_verifier,
                context=context,
                consumption_owner=owner,
                admission_id=f"consume-race-{index}",
            )
            with lock:
                decisions.append(decision.decision)

        threads = [threading.Thread(target=run, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(decisions.count("ALLOW"), 1)
        self.assertEqual(decisions.count("DENY"), 7)

    def test_existing_consuming_exact_pr_binding_is_preserved(self):
        context, intent, trusted, lineage, keys, _, _ = self._fixture("consume-bind")
        moved = TrustedPullRequestState(
            trusted.repository,
            trusted.pr_number,
            trusted.base_sha,
            "d" * 40,
            trusted.merge_method,
        )
        decision = admit_merge(
            intent=intent,
            trusted_state=moved,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=MergeAuthorityConsumptionOwner(),
            admission_id="consume-bind",
        )
        self.assertEqual(decision.decision, "DENY")

    def test_execution_receipt_semantics_are_preserved(self):
        decision, *_ = self._admit_consuming("receipt")
        receipt = issue_merge_execution_receipt(
            decision=decision,
            merge_sha=MERGE,
            executor="github",
            outcome="SUCCEEDED",
        )
        self.assertEqual(receipt.admission_id, decision.admission_id)
        self.assertEqual(receipt.repository, decision.repository)
        self.assertEqual(receipt.head_sha, decision.head_sha)
        self.assertEqual(receipt.grant_digest, decision.grant_digest)

    def test_execution_receipt_rejects_denied_admission(self):
        context, intent, trusted, lineage, keys, _, _ = self._fixture("receipt-deny")
        moved = TrustedPullRequestState(
            trusted.repository,
            trusted.pr_number,
            trusted.base_sha,
            "d" * 40,
            trusted.merge_method,
        )
        denied = admit_merge(
            intent=intent,
            trusted_state=moved,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=MergeAuthorityConsumptionOwner(),
            admission_id="receipt-deny",
        )
        with self.assertRaises(MergeAdmissionError):
            issue_merge_execution_receipt(
                decision=denied,
                merge_sha=MERGE,
                executor="github",
                outcome="SUCCEEDED",
            )


if __name__ == "__main__":
    unittest.main()

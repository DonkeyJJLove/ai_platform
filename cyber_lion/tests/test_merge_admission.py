from __future__ import annotations

import threading
import unittest

from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_revocation import (
    AuthorityEpochState,
    AuthorityLineageRootAnchor,
    register_canonical_authority_epoch_state,
    register_canonical_authority_lineage_root_anchor,
)
from cyber_lion.enterprise.authority_verification import (
    AuthorityVerificationContext,
    IssuerKeyBinding,
)
from cyber_lion.enterprise.merge_admission import (
    MergeAdmissionError,
    MergeAuthorityConsumptionOwner,
    MergeIntent,
    TrustedPullRequestState,
    admit_merge,
    canonical_merge_method_constraint,
    canonical_merge_resource,
    issue_merge_execution_receipt,
)

BASE = "a" * 40
HEAD = "b" * 40
MERGE = "c" * 40
POLICY = "sha256:" + "1" * 64
OBS = "sha256:" + "2" * 64


def _verifier(payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
    return signature == "sig" and key_id == "key-1" and algorithm == "test"


class MergeAdmissionTests(unittest.TestCase):
    def _fixture(
        self,
        suffix: str,
        *,
        repository: str = "DonkeyJJLove/ai_platform",
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
        return context, intent, trusted, (grant,), keys

    def _admit(self, suffix: str, **kwargs):
        context, intent, trusted, lineage, keys = self._fixture(suffix, **kwargs)
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

    def test_exact_match_allows_and_consumes(self):
        decision, owner, _, _, _, _, _ = self._admit("allow")
        self.assertEqual(decision.decision, "ALLOW")
        self.assertTrue(
            owner.is_consumed(
                grant_id=decision.grant_id,
                grant_digest=decision.grant_digest,
                epoch=decision.epoch,
            )
        )

    def test_head_moved_after_authorization_denies(self):
        context, intent, trusted, lineage, keys = self._fixture("head")
        moved = TrustedPullRequestState(
            trusted.repository, trusted.pr_number, trusted.base_sha, "d" * 40, trusted.merge_method
        )
        decision = admit_merge(
            intent=intent,
            trusted_state=moved,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=MergeAuthorityConsumptionOwner(),
            admission_id="admission-head",
        )
        self.assertEqual(decision.decision, "DENY")

    def test_base_moved_denies(self):
        context, intent, trusted, lineage, keys = self._fixture("base")
        moved = TrustedPullRequestState(
            trusted.repository, trusted.pr_number, "d" * 40, trusted.head_sha, trusted.merge_method
        )
        decision = admit_merge(
            intent=intent,
            trusted_state=moved,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=MergeAuthorityConsumptionOwner(),
            admission_id="admission-base",
        )
        self.assertEqual(decision.decision, "DENY")

    def test_wrong_repository_denies(self):
        context, intent, trusted, lineage, keys = self._fixture("repo")
        wrong = TrustedPullRequestState(
            "DonkeyJJLove/other", trusted.pr_number, trusted.base_sha, trusted.head_sha, trusted.merge_method
        )
        decision = admit_merge(
            intent=intent,
            trusted_state=wrong,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=MergeAuthorityConsumptionOwner(),
            admission_id="admission-repo",
        )
        self.assertEqual(decision.decision, "DENY")

    def test_wrong_pr_denies(self):
        context, intent, trusted, lineage, keys = self._fixture("pr")
        wrong = TrustedPullRequestState(
            trusted.repository, 999, trusted.base_sha, trusted.head_sha, trusted.merge_method
        )
        decision = admit_merge(
            intent=intent,
            trusted_state=wrong,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=MergeAuthorityConsumptionOwner(),
            admission_id="admission-pr",
        )
        self.assertEqual(decision.decision, "DENY")

    def test_merge_action_absent_denies(self):
        decision, *_ = self._admit("action", include_action=False)
        self.assertEqual(decision.decision, "DENY")

    def test_resource_outside_scope_denies(self):
        wrong_resource = (
            "github:repo:DonkeyJJLove/ai_platform:pr:31:"
            f"base:{BASE}:head:{'d' * 40}"
        )
        decision, *_ = self._admit("scope", resource_override=wrong_resource)
        self.assertEqual(decision.decision, "DENY")

    def test_wrong_merge_method_constraint_denies(self):
        decision, *_ = self._admit(
            "method",
            constraint_override="merge_method:squash",
        )
        self.assertEqual(decision.decision, "DENY")

    def test_lineage_from_another_mission_denies(self):
        context, intent, trusted, lineage, keys = self._fixture("mission-source")
        wrong_context = AuthorityVerificationContext(
            trust_domain=context.trust_domain,
            tenant_id=context.tenant_id,
            organization_id=context.organization_id,
            mission_id="mission-other",
        )
        decision = admit_merge(
            intent=intent,
            trusted_state=trusted,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=wrong_context,
            consumption_owner=MergeAuthorityConsumptionOwner(),
            admission_id="admission-mission",
        )
        self.assertEqual(decision.decision, "DENY")

    def test_lineage_from_another_epoch_denies(self):
        context, intent, trusted, lineage, keys = self._fixture("epoch", epoch=2)
        from cyber_lion.enterprise.authority_revocation import advance_canonical_authority_epoch_state

        advance_canonical_authority_epoch_state(
            AuthorityEpochState(
                trust_domain=context.trust_domain,
                tenant_id=context.tenant_id,
                organization_id=context.organization_id,
                mission_id=context.mission_id,
                epoch=3,
            )
        )
        decision = admit_merge(
            intent=intent,
            trusted_state=trusted,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=MergeAuthorityConsumptionOwner(),
            admission_id="admission-epoch",
        )
        self.assertEqual(decision.decision, "DENY")

    def test_same_grant_replay_denies(self):
        context, intent, trusted, lineage, keys = self._fixture("replay")
        owner = MergeAuthorityConsumptionOwner()
        first = admit_merge(
            intent=intent,
            trusted_state=trusted,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=owner,
            admission_id="admission-replay-1",
        )
        second = admit_merge(
            intent=intent,
            trusted_state=trusted,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=owner,
            admission_id="admission-replay-2",
        )
        self.assertEqual(first.decision, "ALLOW")
        self.assertEqual(second.decision, "DENY")

    def test_concurrent_replay_allows_exactly_once(self):
        context, intent, trusted, lineage, keys = self._fixture("race")
        owner = MergeAuthorityConsumptionOwner()
        decisions: list[str] = []
        lock = threading.Lock()

        def run(index: int) -> None:
            decision = admit_merge(
                intent=intent,
                trusted_state=trusted,
                lineage=lineage,
                issuer_keys=keys,
                verifier=_verifier,
                context=context,
                consumption_owner=owner,
                admission_id=f"admission-race-{index}",
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

    def test_receipt_requires_allow(self):
        context, intent, trusted, lineage, keys = self._fixture("receipt-deny")
        wrong = TrustedPullRequestState(
            trusted.repository, trusted.pr_number, trusted.base_sha, "d" * 40, trusted.merge_method
        )
        denied = admit_merge(
            intent=intent,
            trusted_state=wrong,
            lineage=lineage,
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=MergeAuthorityConsumptionOwner(),
            admission_id="admission-receipt-deny",
        )
        with self.assertRaises(MergeAdmissionError):
            issue_merge_execution_receipt(
                decision=denied,
                merge_sha=MERGE,
                executor="github",
                outcome="SUCCEEDED",
            )

    def test_allow_produces_exact_receipt(self):
        decision, *_ = self._admit("receipt")
        receipt = issue_merge_execution_receipt(
            decision=decision,
            merge_sha=MERGE,
            executor="github",
            outcome="SUCCEEDED",
        )
        self.assertEqual(receipt.admission_id, decision.admission_id)
        self.assertEqual(receipt.repository, decision.repository)
        self.assertEqual(receipt.pr_number, decision.pr_number)
        self.assertEqual(receipt.base_sha, decision.base_sha)
        self.assertEqual(receipt.head_sha, decision.head_sha)
        self.assertEqual(receipt.grant_digest, decision.grant_digest)
        self.assertEqual(receipt.lineage_digest, decision.lineage_digest)

    def test_missing_lineage_fails_closed(self):
        context, intent, trusted, _, keys = self._fixture("missing")
        decision = admit_merge(
            intent=intent,
            trusted_state=trusted,
            lineage=(),
            issuer_keys=keys,
            verifier=_verifier,
            context=context,
            consumption_owner=MergeAuthorityConsumptionOwner(),
            admission_id="admission-missing",
        )
        self.assertEqual(decision.decision, "DENY")


if __name__ == "__main__":
    unittest.main()

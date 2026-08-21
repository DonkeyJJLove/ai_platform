from __future__ import annotations

import unittest

from cyber_lion.contracts.repository_mutation import (
    CandidateVerificationSource,
    DetachedRepositoryCandidate,
    ExactRefAttachIntent,
    RepositoryMutationContractError,
    TrustedDependencyPin,
    TrustedVerifierPin,
    VerifiedDetachedCandidate,
    changed_paths_digest,
)

HEAD = "a" * 40
COMMIT = "b" * 40
TREE = "c" * 40


def candidate(**overrides):
    values = dict(
        repository="DonkeyJJLove/ai_platform",
        branch="mission/lion-fleet-control-plane-v0",
        expected_head_sha=HEAD,
        expected_parent_sha=HEAD,
        candidate_commit_sha=COMMIT,
        candidate_tree_sha=TREE,
        changed_paths=("cyber_lion/a.py", "cyber_lion/tests/test_a.py"),
        builder_id="builder-1",
        prepared_at="2026-08-21T00:00:00+02:00",
    )
    values.update(overrides)
    return DetachedRepositoryCandidate(**values)


def pin(**overrides):
    values = dict(
        verifier_id="verifier-1",
        verifier_identity_digest="1" * 64,
        verifier_implementation_digest="2" * 64,
        verification_source_id="verified-candidate-store",
        verification_source_identity_digest="3" * 64,
        verification_source_implementation_digest="4" * 64,
    )
    values.update(overrides)
    return TrustedVerifierPin(**values).validate()


def verified(item: DetachedRepositoryCandidate, **overrides):
    values = dict(
        candidate_digest=item.digest(),
        repository=item.repository,
        branch=item.branch,
        expected_head_sha=item.expected_head_sha,
        expected_parent_sha=item.expected_parent_sha,
        candidate_commit_sha=item.candidate_commit_sha,
        candidate_tree_sha=item.candidate_tree_sha,
        changed_paths_digest=changed_paths_digest(item.changed_paths),
        verifier_id="verifier-1",
        verifier_identity_digest="1" * 64,
        verifier_implementation_digest="2" * 64,
        evidence_refs=("evidence:unit-test",),
        verified_at="2026-08-21T00:01:00+02:00",
    )
    values.update(overrides)
    return VerifiedDetachedCandidate(**values)


class StaticVerificationSource(CandidateVerificationSource):
    source_id = "verified-candidate-store"
    source_identity_digest = "3" * 64
    source_implementation_digest = "4" * 64

    def __init__(self, records):
        self.records = records

    def _lookup_exact(self, candidate_digest):
        return self.records


class RepositoryMutationContractTests(unittest.TestCase):
    def test_candidate_canonical_digest_is_stable(self):
        item = candidate().validate()
        self.assertEqual(item.digest(), item.digest())
        self.assertEqual(len(item.digest()), 64)

    def test_candidate_parent_must_equal_expected_head(self):
        with self.assertRaises(RepositoryMutationContractError):
            candidate(expected_parent_sha="d" * 40).validate()

    def test_force_true_is_unrepresentable(self):
        self.assertNotIn("force", ExactRefAttachIntent.__dataclass_fields__)

    def test_builder_cannot_self_verify(self):
        item = candidate()
        record = verified(item, verifier_id=item.builder_id)
        with self.assertRaises(RepositoryMutationContractError):
            record.validate_for(item, pin=pin())

    def test_fake_verifier_identity_is_denied(self):
        item = candidate()
        with self.assertRaises(RepositoryMutationContractError):
            verified(item, verifier_identity_digest="9" * 64).validate_for(
                item, pin=pin()
            )

    def test_fake_verifier_implementation_is_denied(self):
        item = candidate()
        with self.assertRaises(RepositoryMutationContractError):
            verified(item, verifier_implementation_digest="9" * 64).validate_for(
                item, pin=pin()
            )

    def test_forged_source_identity_is_denied(self):
        class ForgedSource(StaticVerificationSource):
            source_identity_digest = "9" * 64

        item = candidate()
        source = ForgedSource((verified(item),))
        with self.assertRaises(RepositoryMutationContractError):
            source.resolve_exact(item, pin=pin())

    def test_verification_source_zero_and_ambiguous_deny(self):
        item = candidate()
        with self.assertRaises(RepositoryMutationContractError):
            StaticVerificationSource(()).resolve_exact(item, pin=pin())
        record = verified(item)
        with self.assertRaises(RepositoryMutationContractError):
            StaticVerificationSource((record, record)).resolve_exact(item, pin=pin())

    def test_verification_binds_exact_candidate_tree(self):
        item = candidate()
        with self.assertRaises(RepositoryMutationContractError):
            verified(item, candidate_tree_sha="d" * 40).validate_for(item, pin=pin())

    def test_dependency_pin_requires_nonzero_deployment_evidence(self):
        with self.assertRaises(RepositoryMutationContractError):
            TrustedDependencyPin(
                dependency_id="provider",
                identity_digest="1" * 64,
                implementation_digest="2" * 64,
                deployment_evidence_digest="0" * 64,
            ).validate()


if __name__ == "__main__":
    unittest.main()

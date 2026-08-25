from dataclasses import replace
import unittest

from cyber_lion.contracts.bean import BeanContractError, BeanSpec
from cyber_lion.contracts.bean_candidate import BeanCandidate, bind_candidate_to_spec, verify_candidate


class BeanCandidateTests(unittest.TestCase):
    def spec(self):
        return BeanSpec(
            bean_id="e006-builder-output",
            bean_type="adapter",
            version="1.0.0",
            purpose="provide a previously missing adapter capability",
            goal_digest="1" * 64,
            success_conditions=("acceptance passes",),
            stop_conditions=("candidate materialized",),
            defer_conditions=("evidence unavailable",),
            inputs=("input.v1",),
            outputs=("output.v1",),
            interfaces=("adapter.v1",),
            required_capabilities=("input.read",),
            provided_capabilities=("adapter.transform",),
            authority_ceiling="none",
            required_grants=(),
            epistemic_requirements=("OBSERVED",),
            evidence_requirements=("build-receipt",),
            provenance_policy=("exact-lineage",),
            memory_policy=("candidate-only",),
            context_policy=("typed-only",),
            observability_requirements=(),
            resource_budget=("cpu<=1",),
            cost_budget="1-unit",
            time_budget="60s",
            runtime_class="local-candidate",
            sandbox_class="detached",
            dependencies=(),
            compatibility_constraints=("adapter.v1",),
            failure_modes=("build-failure",),
            degradation_policy=("reject",),
            revocation_policy=("discard",),
            security_invariants=("candidate-has-no-effect-authority",),
            acceptance_tests=("transform-test",),
            falsification_conditions=("transform-test-fails",),
            evolution_hooks=("gap-derived",),
            replacement_policy=("exact-digest",),
            supersession_policy=("preserve-lineage",),
        ).validate()

    def candidate(self, spec=None, **overrides):
        spec = spec or self.spec()
        values = dict(
            candidate_id="candidate-1",
            bean_id=spec.bean_id,
            spec_digest=spec.spec_digest(),
            implementation_digest="2" * 64,
            builder_identity_digest="3" * 64,
            build_evidence_refs=("build:e1",),
            acceptance_evidence_refs=(),
            verifier_identity_digests=(),
            verification_evidence_refs=(),
        )
        values.update(overrides)
        return BeanCandidate(**values)

    def test_built_candidate_exact_binding(self):
        spec = self.spec()
        candidate = self.candidate(spec).validate()
        bind_candidate_to_spec(candidate, spec)

    def test_spec_substitution_denied(self):
        spec = self.spec()
        candidate = self.candidate(spec).validate()
        substituted = replace(spec, purpose="different semantic meaning")
        with self.assertRaises(BeanContractError):
            bind_candidate_to_spec(candidate, substituted)

    def test_effectful_candidate_is_structurally_denied(self):
        with self.assertRaises(BeanContractError):
            self.candidate(authority_effect="WRITE").validate()

    def test_verified_requires_independent_verifier(self):
        spec = self.spec()
        with self.assertRaises(BeanContractError):
            verify_candidate(
                candidate=self.candidate(spec),
                spec=spec,
                verifier_identity_digests=("3" * 64,),
                verification_evidence_refs=("verify:e1",),
                acceptance_evidence_refs=("accept:e1",),
            )

    def test_independent_verification_passes_but_does_not_authorize(self):
        spec = self.spec()
        verified = verify_candidate(
            candidate=self.candidate(spec),
            spec=spec,
            verifier_identity_digests=("4" * 64,),
            verification_evidence_refs=("verify:e1",),
            acceptance_evidence_refs=("accept:e1",),
        )
        self.assertEqual(verified.state, "VERIFIED")
        self.assertEqual(verified.authority_effect, "NONE")
        self.assertEqual(verified.repository_ref_effect, "NONE")

    def test_verification_replay_from_verified_candidate_denied(self):
        spec = self.spec()
        verified = verify_candidate(
            candidate=self.candidate(spec),
            spec=spec,
            verifier_identity_digests=("4" * 64,),
            verification_evidence_refs=("verify:e1",),
            acceptance_evidence_refs=("accept:e1",),
        )
        with self.assertRaises(BeanContractError):
            verify_candidate(
                candidate=verified,
                spec=spec,
                verifier_identity_digests=("5" * 64,),
                verification_evidence_refs=("verify:e2",),
                acceptance_evidence_refs=("accept:e2",),
            )


if __name__ == "__main__":
    unittest.main()

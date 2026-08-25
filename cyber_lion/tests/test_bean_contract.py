from dataclasses import replace
import unittest

from cyber_lion.contracts.bean import (
    BeanContractError,
    BeanInstance,
    BeanSpec,
    assert_instance_matches_spec,
)


class BeanContractTests(unittest.TestCase):
    def spec(self, **overrides):
        values = dict(
            bean_id="e006-observer",
            bean_type="observer",
            version="1.0.0",
            purpose="observe an exact post-effect state",
            goal_digest="1" * 64,
            success_conditions=("sealed observation emitted",),
            stop_conditions=("observation complete",),
            defer_conditions=("source unavailable",),
            inputs=("effect_ref",),
            outputs=("observation",),
            interfaces=("observe.v1",),
            required_capabilities=("source.read",),
            provided_capabilities=("effect.observe",),
            authority_ceiling="read",
            required_grants=("read-source-grant",),
            epistemic_requirements=("OBSERVED",),
            evidence_requirements=("source_digest",),
            provenance_policy=("exact-source-ref",),
            memory_policy=("no-promotion-without-reconciliation",),
            context_policy=("typed-only",),
            observability_requirements=("source-identity", "captured-at"),
            resource_budget=("cpu<=1", "ram_mb<=256"),
            cost_budget="1-unit",
            time_budget="60s",
            runtime_class="provider",
            sandbox_class="network-readonly",
            dependencies=(),
            compatibility_constraints=("observe.v1",),
            failure_modes=("source-unavailable",),
            degradation_policy=("DEFER",),
            revocation_policy=("stop-on-revoke",),
            security_invariants=("observation-does-not-mint-authority",),
            acceptance_tests=("exact-source-binding",),
            falsification_conditions=("source-cannot-be-reconstructed",),
            evolution_hooks=("new-gap",),
            replacement_policy=("exact-successor-digest",),
            supersession_policy=("preserve-history",),
        )
        values.update(overrides)
        return BeanSpec(**values)

    def instance(self, spec=None, **overrides):
        spec = spec or self.spec()
        values = dict(
            instance_id="bean-instance-1",
            bean_id=spec.bean_id,
            spec_digest=spec.spec_digest(),
            implementation_digest="2" * 64,
            runtime_identity_digest="3" * 64,
            mission_id="E006-MISSION",
            state="ADMITTED",
            generation=0,
            created_at="2026-08-25T22:00:00Z",
            updated_at="2026-08-25T22:00:00Z",
            evidence_refs=("admission:e1",),
        )
        values.update(overrides)
        return BeanInstance(**values)

    def test_spec_is_immutable_valid_and_digest_deterministic(self):
        spec = self.spec().validate()
        self.assertEqual(spec.spec_digest(), self.spec().spec_digest())
        with self.assertRaises(Exception):
            spec.bean_id = "changed"

    def test_every_semantic_change_changes_spec_digest(self):
        spec = self.spec().validate()
        variants = (
            replace(spec, purpose="different purpose"),
            replace(spec, version="1.0.1"),
            replace(spec, provided_capabilities=("effect.observe.v2",)),
            replace(spec, security_invariants=("different invariant",)),
        )
        for variant in variants:
            self.assertNotEqual(spec.spec_digest(), variant.spec_digest())

    def test_duplicate_capability_denied(self):
        with self.assertRaises(BeanContractError):
            self.spec(provided_capabilities=("a", "a")).validate()

    def test_capability_cannot_self_satisfy(self):
        with self.assertRaises(BeanContractError):
            self.spec(required_capabilities=("same",), provided_capabilities=("same",)).validate()

    def test_nonzero_authority_without_observability_denied(self):
        with self.assertRaises(BeanContractError):
            self.spec(observability_requirements=()).validate()

    def test_credential_like_required_grant_denied(self):
        with self.assertRaises(BeanContractError):
            self.spec(required_grants=("token=supersecret",)).validate()

    def test_spec_has_no_effect_or_credential_surface(self):
        spec = self.spec().validate()
        for field in ("grant", "credential", "authority_effect", "execution_effect", "repository_ref_effect", "external_effect"):
            self.assertFalse(hasattr(spec, field))

    def test_duplicate_lineage_parent_is_denied(self):
        parent = "4" * 64
        with self.assertRaises(BeanContractError):
            self.spec(lineage_parent_digests=(parent, parent)).validate()

    def test_instance_exact_binding_passes(self):
        spec = self.spec().validate()
        instance = self.instance(spec).validate()
        assert_instance_matches_spec(instance, spec)

    def test_instance_spec_substitution_denied(self):
        spec = self.spec().validate()
        instance = self.instance(spec).validate()
        changed = replace(spec, purpose="substituted")
        with self.assertRaises(BeanContractError):
            assert_instance_matches_spec(instance, changed)

    def test_instance_cannot_self_supersede(self):
        with self.assertRaises(BeanContractError):
            self.instance(supersedes_instance_id="bean-instance-1").validate()


if __name__ == "__main__":
    unittest.main()

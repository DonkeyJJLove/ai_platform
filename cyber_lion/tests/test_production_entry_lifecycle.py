from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from cyber_lion.contracts.environment_lifecycle import (
    AssuranceDimension,
    AssuranceState,
    EnvironmentLifecycleContractError,
    EnvironmentWorld,
    LifecycleState,
    LogicalNodeObservation,
    PhysicalControlDomainObservation,
    WorldClass,
)
from cyber_lion.contracts.production_entry import (
    AuthorityState,
    PHYSICAL_EXTERNAL_CONTROL_DOMAIN_REQUIRED,
    ProductionEntryContractError,
)
from cyber_lion.enterprise.production_entry import (
    CANONICAL_REPOSITORY,
    PRODUCTION_PROCESS_CHAIN,
    REFERENCE_BASELINE_BRANCH,
    REFERENCE_BASELINE_SHA,
    REFERENCE_BASELINE_TREE,
    REFERENCE_OBSERVED_AT,
    canonical_future_physical_world,
    canonical_future_production_claim,
    canonical_three_wsl_claim,
    canonical_three_wsl_world,
    classify_world,
    derive_assurance_vector,
    derive_production_entry_dossier,
    evaluate_lifecycle_transition,
    render_reference_document,
)


class ProductionEntryLifecycleTests(unittest.TestCase):
    def lab_dossier(self):
        return derive_production_entry_dossier(
            canonical_three_wsl_world(),
            (canonical_three_wsl_claim(),),
            repository=CANONICAL_REPOSITORY,
            candidate_sha=REFERENCE_BASELINE_SHA,
            candidate_tree=REFERENCE_BASELINE_TREE,
            candidate_branch=REFERENCE_BASELINE_BRANCH,
            generated_at=REFERENCE_OBSERVED_AT,
        )

    def future_dossier(self):
        world = canonical_future_physical_world()
        candidate = "a" * 40
        tree = "b" * 40
        return derive_production_entry_dossier(
            world,
            (canonical_future_production_claim(candidate, tree),),
            repository=CANONICAL_REPOSITORY,
            candidate_sha=candidate,
            candidate_tree=tree,
            candidate_branch="mission/future-production-candidate",
            generated_at=world.observed_at,
        )

    def test_current_three_wsl_world_is_one_physical_domain(self):
        world = canonical_three_wsl_world()
        self.assertEqual(world.logical_node_count, 3)
        self.assertEqual(world.physical_domain_count, 1)
        self.assertIs(classify_world(world), WorldClass.MULTI_LOGICAL_NODE_LAB)
        self.assertEqual({node.physical_domain_id for node in world.logical_nodes}, {"WINDOWS-MOON"})

    def test_current_lab_is_validated_but_production_denied(self):
        dossier = self.lab_dossier()
        self.assertIs(dossier.lifecycle_state, LifecycleState.PRODUCTION_ENTRY_BLOCKED)
        self.assertFalse(dossier.production_eligible)
        self.assertIs(dossier.authority_state, AuthorityState.NONE)
        self.assertEqual(dossier.current_blockers, (PHYSICAL_EXTERNAL_CONTROL_DOMAIN_REQUIRED,))
        self.assertEqual(dossier.missing_dimensions, ())
        self.assertIs(dossier.assurance_vector.state_for(AssuranceDimension.PHYSICAL_TOPOLOGY), AssuranceState.FAIL)
        self.assertIs(dossier.assurance_vector.state_for(AssuranceDimension.FAILURE_DOMAIN_INDEPENDENCE), AssuranceState.FAIL)
        self.assertIs(dossier.assurance_vector.state_for(AssuranceDimension.NON_EXPORTABLE_KEY_STORAGE), AssuranceState.BLOCKED)

    def test_logical_consensus_does_not_mint_authority(self):
        dossier = self.lab_dossier()
        self.assertIs(dossier.assurance_vector.state_for(AssuranceDimension.AUTHORITY), AssuranceState.BLOCKED)
        self.assertIs(dossier.authority_state, AuthorityState.NONE)

    def test_readiness_transition_cannot_skip_authority_plane(self):
        dossier = self.future_dossier()
        decision = evaluate_lifecycle_transition(
            LifecycleState.PRODUCTION_ENTRY_ELIGIBLE,
            LifecycleState.PRODUCTION_AUTHORIZED,
            dossier,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "SEPARATE_AUTHORITY_PLANE_REQUIRED")

    def test_lab_protocol_cannot_jump_to_production_authorized(self):
        dossier = self.lab_dossier()
        decision = evaluate_lifecycle_transition(
            LifecycleState.LAB_PROTOCOL_VALIDATED,
            LifecycleState.PRODUCTION_AUTHORIZED,
            dossier,
        )
        self.assertFalse(decision.allowed)

    def test_future_two_physical_domain_fixture_is_only_entry_eligible(self):
        dossier = self.future_dossier()
        self.assertTrue(dossier.production_eligible)
        self.assertIs(dossier.lifecycle_state, LifecycleState.PRODUCTION_ENTRY_ELIGIBLE)
        self.assertIs(dossier.authority_state, AuthorityState.NONE)
        self.assertEqual(dossier.current_blockers, ())
        self.assertEqual(dossier.missing_dimensions, ())
        self.assertIn("PRODUCTION_READINESS_CERTIFICATION_REQUIRED", dossier.required_next_evidence)

    def test_manual_production_eligibility_injection_is_rejected(self):
        dossier = self.lab_dossier()
        forged = replace(
            dossier,
            production_eligible=True,
            lifecycle_state=LifecycleState.PRODUCTION_ENTRY_ELIGIBLE,
            dossier_digest="",
        )
        with self.assertRaises(ProductionEntryContractError):
            forged.sealed()

    def test_assurance_claim_cannot_mint_authority(self):
        claim = canonical_three_wsl_claim()
        with self.assertRaises(EnvironmentLifecycleContractError):
            replace(claim, authority_effect="ALLOW").validate()

    def test_unique_host_ids_are_not_physical_independence(self):
        world = canonical_three_wsl_world()
        self.assertEqual(len({node.host_id for node in world.logical_nodes}), 3)
        vector, _ = derive_assurance_vector(
            world,
            (canonical_three_wsl_claim(),),
            candidate_sha=REFERENCE_BASELINE_SHA,
            candidate_tree=REFERENCE_BASELINE_TREE,
            generated_at=REFERENCE_OBSERVED_AT,
        )
        self.assertIs(vector.state_for(AssuranceDimension.IDENTITY_SEPARATION), AssuranceState.PASS)
        self.assertIs(vector.state_for(AssuranceDimension.PHYSICAL_TOPOLOGY), AssuranceState.FAIL)

    def test_different_hostnames_are_not_control_domain_separation(self):
        world = canonical_three_wsl_world()
        self.assertEqual(len({node.hostname for node in world.logical_nodes}), 3)
        self.assertEqual(world.physical_domain_count, 1)
        self.assertFalse(self.lab_dossier().production_eligible)

    def test_four_wsl_nodes_on_same_machine_still_fail_physical_gate(self):
        world = canonical_three_wsl_world()
        extra = LogicalNodeObservation(
            "host-fourth", "LAB-FOURTH", "WSL2", "WINDOWS-MOON",
            "LAB-CONTROL-PLANE", "LAB_OBSERVER", "NONE", REFERENCE_OBSERVED_AT,
        ).validate()
        four = replace(
            world,
            logical_nodes=world.logical_nodes + (extra,),
            observer_locations=world.observer_locations + ("host-fourth",),
        ).validate()
        claim = replace(canonical_three_wsl_claim(), world_id=four.world_id).validate()
        dossier = derive_production_entry_dossier(
            four,
            (claim,),
            repository=CANONICAL_REPOSITORY,
            candidate_sha=REFERENCE_BASELINE_SHA,
            candidate_tree=REFERENCE_BASELINE_TREE,
            candidate_branch=REFERENCE_BASELINE_BRANCH,
            generated_at=REFERENCE_OBSERVED_AT,
        )
        self.assertEqual(four.logical_node_count, 4)
        self.assertEqual(four.physical_domain_count, 1)
        self.assertFalse(dossier.production_eligible)
        self.assertIn(PHYSICAL_EXTERNAL_CONTROL_DOMAIN_REQUIRED, dossier.current_blockers)

    def test_caller_supplied_fake_physical_ids_on_wsl_do_not_satisfy_gate(self):
        observed = "2026-08-28T13:40:00Z"
        domains = (
            PhysicalControlDomainObservation(
                "fake-a", "same-machine-a", "WSL2", False, None, False, False, observed
            ).validate(),
            PhysicalControlDomainObservation(
                "fake-b", "same-machine-b", "WSL2", True, 2, True, True, observed
            ).validate(),
        )
        nodes = (
            LogicalNodeObservation(
                "a", "A", "WSL2", "fake-a", "same", "CONSUMER", "NONE", observed
            ).validate(),
            LogicalNodeObservation(
                "b", "B", "WSL2", "fake-b", "same", "PRODUCER", "TEST_ONLY", observed
            ).validate(),
        )
        world = EnvironmentWorld(
            "fake-two-domain-wsl",
            WorldClass.MULTI_PHYSICAL_NODE_LAB,
            nodes,
            domains,
            ("b",),
            ("a",),
            ("a",),
            (),
            ("same-windows-host",),
            ("caller-provided physical ids are not physical evidence",),
            observed,
        ).validate()
        base_claim = canonical_future_production_claim("a" * 40, "b" * 40)
        claim = replace(base_claim, world_id=world.world_id, observed_at=observed, issued_at=observed).validate()
        dossier = derive_production_entry_dossier(
            world,
            (claim,),
            repository=CANONICAL_REPOSITORY,
            candidate_sha="a" * 40,
            candidate_tree="b" * 40,
            candidate_branch="fake",
            generated_at=observed,
        )
        self.assertFalse(dossier.production_eligible)
        self.assertIs(dossier.assurance_vector.state_for(AssuranceDimension.PHYSICAL_TOPOLOGY), AssuranceState.FAIL)

    def test_software_rsa_claim_cannot_override_non_exportable_hardware_gate(self):
        world = canonical_three_wsl_world()
        claim = canonical_three_wsl_claim()
        promoted = replace(
            claim,
            supported_assurance_dimensions=claim.supported_assurance_dimensions + (
                AssuranceDimension.NON_EXPORTABLE_KEY_STORAGE,
            ),
            unsupported_assurance_dimensions=tuple(
                d for d in claim.unsupported_assurance_dimensions
                if d is not AssuranceDimension.NON_EXPORTABLE_KEY_STORAGE
            ),
        ).validate()
        vector, _ = derive_assurance_vector(
            world,
            (promoted,),
            candidate_sha=REFERENCE_BASELINE_SHA,
            candidate_tree=REFERENCE_BASELINE_TREE,
            generated_at=REFERENCE_OBSERVED_AT,
        )
        self.assertIs(vector.state_for(AssuranceDimension.NON_EXPORTABLE_KEY_STORAGE), AssuranceState.BLOCKED)

    def test_test_only_relabel_does_not_change_world_truth(self):
        world = canonical_three_wsl_world()
        claim = replace(canonical_three_wsl_claim(), production_relevance="PRODUCTION_REQUIRED").validate()
        dossier = derive_production_entry_dossier(
            world,
            (claim,),
            repository=CANONICAL_REPOSITORY,
            candidate_sha=REFERENCE_BASELINE_SHA,
            candidate_tree=REFERENCE_BASELINE_TREE,
            candidate_branch=REFERENCE_BASELINE_BRANCH,
            generated_at=REFERENCE_OBSERVED_AT,
        )
        self.assertFalse(dossier.production_eligible)
        self.assertIn(PHYSICAL_EXTERNAL_CONTROL_DOMAIN_REQUIRED, dossier.current_blockers)

    def test_candidate_drift_marks_claim_stale(self):
        world = canonical_three_wsl_world()
        vector, classification = derive_assurance_vector(
            world,
            (canonical_three_wsl_claim(),),
            candidate_sha="f" * 40,
            candidate_tree="e" * 40,
            generated_at=REFERENCE_OBSERVED_AT,
        )
        self.assertEqual(tuple(x.claim_id for x in classification.stale), ("e006-r9d-9g3a1-three-wsl-consensus",))
        self.assertIs(vector.state_for(AssuranceDimension.CURRENTNESS), AssuranceState.STALE)

    def test_expired_evidence_is_stale_not_success(self):
        claim = replace(
            canonical_three_wsl_claim(),
            issued_at="2026-08-28T13:30:30Z",
            observed_at="2026-08-28T13:30:00Z",
            expires_at_or_currentness_rule="expires:2026-08-28T13:31:00Z",
        ).validate()
        vector, classification = derive_assurance_vector(
            canonical_three_wsl_world(),
            (claim,),
            candidate_sha=REFERENCE_BASELINE_SHA,
            candidate_tree=REFERENCE_BASELINE_TREE,
            generated_at="2026-08-28T13:31:01Z",
        )
        self.assertTrue(classification.stale)
        self.assertIs(vector.state_for(AssuranceDimension.CURRENTNESS), AssuranceState.STALE)

    def test_unknown_or_untested_never_becomes_success(self):
        world = canonical_three_wsl_world()
        vector, _ = derive_assurance_vector(
            world,
            (),
            candidate_sha=REFERENCE_BASELINE_SHA,
            candidate_tree=REFERENCE_BASELINE_TREE,
            generated_at=REFERENCE_OBSERVED_AT,
        )
        self.assertIs(vector.state_for(AssuranceDimension.PROTOCOL_CORRECTNESS), AssuranceState.UNTESTED)
        self.assertIs(vector.state_for(AssuranceDimension.CURRENTNESS), AssuranceState.UNTESTED)

    def test_conflicting_claims_are_not_canonicalized_by_majority(self):
        world = canonical_three_wsl_world()
        first = canonical_three_wsl_claim()
        second = replace(
            first,
            claim_id="conflicting-second",
            claim_statement="same experiment interpreted as production external",
            evidence_digests=("1" * 64,),
        ).validate()
        vector, classification = derive_assurance_vector(
            world,
            (first, second),
            candidate_sha=REFERENCE_BASELINE_SHA,
            candidate_tree=REFERENCE_BASELINE_TREE,
            generated_at=REFERENCE_OBSERVED_AT,
        )
        self.assertEqual({x.claim_id for x in classification.conflicting}, {first.claim_id, second.claim_id})
        self.assertIs(vector.state_for(AssuranceDimension.PROTOCOL_CORRECTNESS), AssuranceState.CONFLICT)
        self.assertIs(vector.state_for(AssuranceDimension.AUTHORITY), AssuranceState.BLOCKED)

    def test_wrong_world_claim_is_rejected(self):
        world = canonical_three_wsl_world()
        claim = replace(canonical_three_wsl_claim(), world_id="another-world").validate()
        _, classification = derive_assurance_vector(
            world,
            (claim,),
            candidate_sha=REFERENCE_BASELINE_SHA,
            candidate_tree=REFERENCE_BASELINE_TREE,
            generated_at=REFERENCE_OBSERVED_AT,
        )
        self.assertEqual(tuple(x.claim_id for x in classification.rejected), (claim.claim_id,))

    def test_dossier_digest_detects_tampering(self):
        dossier = self.lab_dossier()
        with self.assertRaises(ProductionEntryContractError):
            replace(dossier, current_blockers=("SILENTLY_REMOVED",)).validate()

    def test_entry_eligibility_does_not_pin_v2_or_create_key(self):
        dossier = self.future_dossier()
        self.assertIs(dossier.authority_state, AuthorityState.NONE)
        self.assertIsNone(dossier.authority_evidence_digest)
        self.assertFalse(hasattr(dossier, "private_key"))
        self.assertFalse(hasattr(dossier, "key_material"))
        self.assertFalse(hasattr(dossier, "v2_pinned"))

    def test_process_chain_has_separate_readiness_authority_canary_reconciliation(self):
        self.assertEqual(len(PRODUCTION_PROCESS_CHAIN), 13)
        readiness = PRODUCTION_PROCESS_CHAIN.index("PRODUCTION_READINESS_CERTIFICATION")
        authority = PRODUCTION_PROCESS_CHAIN.index("PRODUCTION_AUTHORITY_DECISION")
        canary = PRODUCTION_PROCESS_CHAIN.index("PRODUCTION_DEPLOYMENT_CANARY")
        reconcile = PRODUCTION_PROCESS_CHAIN.index("PRODUCTION_EFFECT_RECONCILIATION")
        self.assertLess(readiness, authority)
        self.assertLess(authority, canary)
        self.assertLess(canary, reconcile)

    def test_lab_track_can_continue_while_production_entry_blocked(self):
        dossier = self.lab_dossier()
        decision = evaluate_lifecycle_transition(
            LifecycleState.PRODUCTION_ENTRY_BLOCKED,
            LifecycleState.LAB_EXPERIMENT_ACTIVE,
            dossier,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "LAB_RESEARCH_TRACK_MAY_CONTINUE")

    def test_reference_document_is_rendered_from_canonical_model(self):
        path = Path("docs/architecture/production-entry/README.md")
        self.assertEqual(path.read_text(encoding="utf-8"), render_reference_document())

    def test_reference_document_contains_non_promotion_invariants(self):
        text = render_reference_document()
        for invariant in (
            "LOGICAL_HOST_COUNT != PHYSICAL_DOMAIN_COUNT",
            "MULTI_NODE_CONSENSUS != PHYSICAL_INDEPENDENCE",
            "LAB_VALIDATION_PASS != PRODUCTION_ADMISSION",
            "READINESS != AUTHORITY",
            "UNKNOWN != SUCCESS",
        ):
            self.assertIn(invariant, text)


if __name__ == "__main__":
    unittest.main()

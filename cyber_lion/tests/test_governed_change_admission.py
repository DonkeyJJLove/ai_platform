from __future__ import annotations

from dataclasses import replace
import inspect
import unittest

from cyber_lion.contracts.governed_change_proposal import GovernedChangeProposal, SCHEMA_VERSION as GCP_SCHEMA_VERSION
from cyber_lion.enterprise.governed_change_admission import (
    GovernedChangeAdmissionEngine,
    GovernedChangeAdmissionError,
)


class GovernedChangeAdmissionEngineTests(unittest.TestCase):
    def _proposal(self, *, risk: str = "GREEN", target: str = "cyber_lion.evolution", dependencies: tuple[str, ...] = ()) -> GovernedChangeProposal:
        return GovernedChangeProposal(
            schema_version=GCP_SCHEMA_VERSION,
            proposal_id="gcp:test",
            epoch_id="E004",
            source_delta_id="delta:test",
            source_delta_digest="1" * 64,
            source_epoch_transition_digest="2" * 64,
            source_memory_head="3" * 64,
            source_promotion_digest="4" * 64,
            source_pdp_decision_digest="5" * 64,
            target_component=target,
            candidate_scope=(
                "cyber_lion/contracts/example.py",
                "cyber_lion/tests/test_example.py",
            ),
            dependency_ids=dependencies,
            falsification_conditions=("candidate must fail closed",),
            evidence_refs=("obs:1",),
            risk_class=risk,
            authority_effect="NONE",
            execution_effect="NONE",
        ).sealed()

    def test_build_candidate_derives_amber_local_write_exact_scope(self) -> None:
        engine = GovernedChangeAdmissionEngine()
        proposal = self._proposal()
        request = engine.derive_request(
            proposal=proposal,
            action_class="BUILD_CANDIDATE",
            trusted_repository="DonkeyJJLove/ai_platform",
        )
        self.assertEqual(request.proposal_digest, proposal.proposal_digest)
        self.assertEqual(request.candidate_scope, proposal.candidate_scope)
        self.assertEqual(request.requested_action, "BUILD_CANDIDATE")
        self.assertEqual(request.requested_authority, "local_write")
        self.assertEqual(request.lane, "AMBER")
        self.assertEqual(
            request.requested_resource_scope,
            tuple(f"repo-path:DonkeyJJLove/ai_platform:{path}" for path in proposal.candidate_scope),
        )
        self.assertEqual(request.authority_effect, "NONE")
        self.assertEqual(request.execution_effect, "NONE")

    def test_red_proposal_cannot_lane_downgrade(self) -> None:
        engine = GovernedChangeAdmissionEngine()
        request = engine.derive_request(
            proposal=self._proposal(risk="RED"),
            action_class="BUILD_CANDIDATE",
            trusted_repository="DonkeyJJLove/ai_platform",
        )
        self.assertEqual(request.lane, "RED")

    def test_request_pr_maps_to_external_write(self) -> None:
        engine = GovernedChangeAdmissionEngine()
        request = engine.derive_request(
            proposal=self._proposal(),
            action_class="REQUEST_PR",
            trusted_repository="DonkeyJJLove/ai_platform",
        )
        self.assertEqual(request.requested_authority, "external_write")
        self.assertEqual(request.lane, "AMBER")

    def test_fresh_gate_requested_projection_is_bound_to_admission_request(self) -> None:
        engine = GovernedChangeAdmissionEngine()
        proposal = self._proposal()
        request = engine.derive_request(
            proposal=proposal,
            action_class="RUN_TEST",
            trusted_repository="DonkeyJJLove/ai_platform",
        )
        gate = engine.derive_gate_request(
            admission_request=request,
            gate_request_id="gate:e004:r9:1",
            policy_binding="policy:e004@1:sha256:" + "a" * 64,
            authority_lineage_digest="b" * 64,
            enterprise_graph_digest="c" * 64,
            status_digest="d" * 64,
            observability_state="HEALTHY",
        )
        self.assertEqual(gate.proposal_id, request.request_id)
        self.assertEqual(gate.lane, request.lane)
        self.assertEqual(gate.requested_authority, request.requested_authority)
        self.assertIn(proposal.proposal_digest, gate.evidence_refs)
        self.assertIn(request.admission_request_digest, gate.evidence_refs)
        self.assertNotEqual(gate.request_digest, proposal.source_pdp_decision_digest)

    def test_exact_request_replay_denied(self) -> None:
        engine = GovernedChangeAdmissionEngine()
        proposal = self._proposal()
        engine.derive_request(
            proposal=proposal,
            action_class="BUILD_CANDIDATE",
            trusted_repository="DonkeyJJLove/ai_platform",
        )
        with self.assertRaises(GovernedChangeAdmissionError):
            engine.derive_request(
                proposal=proposal,
                action_class="BUILD_CANDIDATE",
                trusted_repository="DonkeyJJLove/ai_platform",
            )

    def test_gate_request_replay_denied(self) -> None:
        engine = GovernedChangeAdmissionEngine()
        request = engine.derive_request(
            proposal=self._proposal(),
            action_class="RUN_TEST",
            trusted_repository="DonkeyJJLove/ai_platform",
        )
        kwargs = dict(
            admission_request=request,
            gate_request_id="gate:e004:r9:replay",
            policy_binding="policy:e004@1:sha256:" + "a" * 64,
            authority_lineage_digest="b" * 64,
            enterprise_graph_digest="c" * 64,
            status_digest="d" * 64,
            observability_state="HEALTHY",
        )
        engine.derive_gate_request(**kwargs)
        with self.assertRaises(GovernedChangeAdmissionError):
            engine.derive_gate_request(**kwargs)

    def test_unsupported_consequential_actions_denied(self) -> None:
        for action in ("MERGE", "WRITE_MASTER", "DEPLOY", "RELEASE", "EXECUTE_RUNTIME", "ISSUE_GRANT", "DELEGATE_AUTHORITY", "UNKNOWN"):
            with self.subTest(action=action):
                with self.assertRaises(GovernedChangeAdmissionError):
                    GovernedChangeAdmissionEngine().derive_request(
                        proposal=self._proposal(),
                        action_class=action,
                        trusted_repository="DonkeyJJLove/ai_platform",
                    )

    def test_repository_substitution_and_wildcards_denied(self) -> None:
        for repository in ("other/repo/extra", "../repo", "owner/*", "/owner/repo"):
            with self.subTest(repository=repository):
                with self.assertRaises(GovernedChangeAdmissionError):
                    GovernedChangeAdmissionEngine().derive_request(
                        proposal=self._proposal(),
                        action_class="BUILD_CANDIDATE",
                        trusted_repository=repository,
                    )

    def test_unsealed_and_tampered_proposals_denied(self) -> None:
        sealed = self._proposal()
        unsealed = replace(sealed, proposal_digest="")
        with self.assertRaises(GovernedChangeAdmissionError):
            GovernedChangeAdmissionEngine().derive_request(
                proposal=unsealed,
                action_class="BUILD_CANDIDATE",
                trusted_repository="DonkeyJJLove/ai_platform",
            )
        tampered = replace(sealed, candidate_scope=("cyber_lion/extra.py",))
        with self.assertRaises(Exception):
            GovernedChangeAdmissionEngine().derive_request(
                proposal=tampered,
                action_class="BUILD_CANDIDATE",
                trusted_repository="DonkeyJJLove/ai_platform",
            )

    def test_f005_target_and_dependency_denied(self) -> None:
        for proposal in (
            self._proposal(target="F005 execution mesh"),
            self._proposal(dependencies=("F005-runtime",)),
        ):
            with self.assertRaises(GovernedChangeAdmissionError):
                GovernedChangeAdmissionEngine().derive_request(
                    proposal=proposal,
                    action_class="BUILD_CANDIDATE",
                    trusted_repository="DonkeyJJLove/ai_platform",
                )

    def test_public_derivation_api_does_not_accept_lane_authority_or_scope(self) -> None:
        params = inspect.signature(GovernedChangeAdmissionEngine.derive_request).parameters
        self.assertNotIn("candidate_scope", params)
        self.assertNotIn("requested_resource_scope", params)
        self.assertNotIn("lane", params)
        self.assertNotIn("requested_authority", params)
        self.assertNotIn("risk_class", params)
        self.assertNotIn("epoch", params)

    def test_no_effect_or_authority_minting_surface(self) -> None:
        GovernedChangeAdmissionEngine.assert_no_effect_surface()
        for name in ("create_branch", "create_pr", "merge", "execute", "deploy", "release", "issue_grant", "revoke_grant"):
            self.assertFalse(hasattr(GovernedChangeAdmissionEngine, name))

    def test_state_digest_changes_only_with_non_effectful_request_state(self) -> None:
        engine = GovernedChangeAdmissionEngine()
        before = engine.state_digest()
        engine.derive_request(
            proposal=self._proposal(),
            action_class="BUILD_CANDIDATE",
            trusted_repository="DonkeyJJLove/ai_platform",
        )
        after = engine.state_digest()
        self.assertNotEqual(before, after)
        self.assertEqual(len(before), 64)
        self.assertEqual(len(after), 64)


if __name__ == "__main__":
    unittest.main()

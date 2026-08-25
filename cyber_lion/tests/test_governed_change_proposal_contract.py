import unittest
from dataclasses import replace

from cyber_lion.contracts.governed_change_proposal import (
    GovernedChangeProposal,
    GovernedChangeProposalContractError,
    SCHEMA_VERSION,
)

H = "a" * 64


class GovernedChangeProposalContractTests(unittest.TestCase):
    def proposal(self):
        return GovernedChangeProposal(
            schema_version=SCHEMA_VERSION,
            proposal_id="gcp:test",
            epoch_id="E004",
            source_delta_id="delta:1",
            source_delta_digest=H,
            source_epoch_transition_digest="b" * 64,
            source_memory_head="c" * 64,
            source_promotion_digest="d" * 64,
            source_pdp_decision_digest="e" * 64,
            target_component="epistemic-scoring",
            candidate_scope=("cyber_lion/example.py", "cyber_lion/tests/test_example.py"),
            dependency_ids=("dep:1",),
            falsification_conditions=("regression remains bounded",),
            evidence_refs=("obs:1",),
            risk_class="AMBER",
        ).sealed()

    def test_sealed_digest_is_deterministic_and_binds_payload(self):
        a = self.proposal()
        b = self.proposal()
        self.assertEqual(a.proposal_digest, b.proposal_digest)
        self.assertEqual(a.compute_digest(), a.proposal_digest)
        with self.assertRaises(GovernedChangeProposalContractError):
            replace(a, target_component="substituted").validate()

    def test_effect_authority_is_structurally_denied(self):
        p = self.proposal()
        with self.assertRaises(GovernedChangeProposalContractError):
            replace(p, proposal_digest="", authority_effect="WRITE_REPOSITORY").validate()
        with self.assertRaises(GovernedChangeProposalContractError):
            replace(p, proposal_digest="", execution_effect="RUN").validate()

    def test_scope_is_concrete_unique_posix(self):
        p = self.proposal()
        with self.assertRaises(GovernedChangeProposalContractError):
            replace(p, proposal_digest="", candidate_scope=("../escape",)).validate()
        with self.assertRaises(GovernedChangeProposalContractError):
            replace(p, proposal_digest="", candidate_scope=("x.py", "x.py")).validate()
        with self.assertRaises(GovernedChangeProposalContractError):
            replace(p, proposal_digest="", candidate_scope=("x\\y.py",)).validate()

    def test_source_digests_are_exact_sha256(self):
        p = self.proposal()
        with self.assertRaises(GovernedChangeProposalContractError):
            replace(p, proposal_digest="", source_memory_head="GENESIS").validate()
        with self.assertRaises(GovernedChangeProposalContractError):
            replace(p, proposal_digest="", source_pdp_decision_digest="short").validate()


if __name__ == "__main__":
    unittest.main()

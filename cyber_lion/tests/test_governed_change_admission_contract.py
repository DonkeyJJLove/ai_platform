from __future__ import annotations

from dataclasses import replace
import unittest

from cyber_lion.contracts.governed_change_admission import (
    GovernedChangeAdmissionContractError,
    GovernedChangeAdmissionRequest,
    SCHEMA_VERSION,
)


class GovernedChangeAdmissionContractTests(unittest.TestCase):
    def _request(self) -> GovernedChangeAdmissionRequest:
        return GovernedChangeAdmissionRequest(
            schema_version=SCHEMA_VERSION,
            request_id="gca:test",
            proposal_id="gcp:test",
            proposal_digest="1" * 64,
            epoch_id="E004",
            source_delta_digest="2" * 64,
            source_epoch_transition_digest="3" * 64,
            source_memory_head="4" * 64,
            source_promotion_digest="5" * 64,
            repository="DonkeyJJLove/ai_platform",
            target_component="cyber_lion.evolution",
            candidate_scope=("cyber_lion/contracts/example.py",),
            requested_action="BUILD_CANDIDATE",
            requested_resource_scope=("repo-path:DonkeyJJLove/ai_platform:cyber_lion/contracts/example.py",),
            risk_class="GREEN",
            lane="AMBER",
            requested_authority="local_write",
            evidence_refs=("obs:1",),
            authority_effect="NONE",
            execution_effect="NONE",
        ).sealed()

    def test_sealed_request_is_deterministic_and_valid(self) -> None:
        first = self._request()
        second = self._request()
        self.assertEqual(first.admission_request_digest, second.admission_request_digest)
        self.assertEqual(first.validate(), first)

    def test_digest_substitution_denied(self) -> None:
        request = self._request()
        with self.assertRaises(GovernedChangeAdmissionContractError):
            replace(request, admission_request_digest="f" * 64).validate()

    def test_effect_authority_denied(self) -> None:
        request = self._request()
        with self.assertRaises(GovernedChangeAdmissionContractError):
            replace(request, authority_effect="WRITE").validate()
        with self.assertRaises(GovernedChangeAdmissionContractError):
            replace(request, execution_effect="EXECUTE").validate()

    def test_unsupported_actions_denied(self) -> None:
        request = self._request()
        for action in ("MERGE", "WRITE_MASTER", "DEPLOY", "RELEASE", "EXECUTE_RUNTIME", "ISSUE_GRANT", "DELEGATE_AUTHORITY"):
            with self.subTest(action=action):
                with self.assertRaises(GovernedChangeAdmissionContractError):
                    replace(request, requested_action=action, admission_request_digest="").validate()

    def test_wildcard_and_traversal_scope_denied(self) -> None:
        request = self._request()
        bad_candidates = (
            ("cyber_lion/*",),
            ("../secret",),
            ("/absolute",),
        )
        for scope in bad_candidates:
            with self.subTest(scope=scope):
                with self.assertRaises(GovernedChangeAdmissionContractError):
                    replace(request, candidate_scope=scope, admission_request_digest="").validate()
        with self.assertRaises(GovernedChangeAdmissionContractError):
            replace(request, requested_resource_scope=("repo-path:DonkeyJJLove/ai_platform:*",), admission_request_digest="").validate()

    def test_lane_and_authority_vocabulary_is_closed(self) -> None:
        request = self._request()
        with self.assertRaises(GovernedChangeAdmissionContractError):
            replace(request, lane="BLUE", admission_request_digest="").validate()
        with self.assertRaises(GovernedChangeAdmissionContractError):
            replace(request, requested_authority="god_mode", admission_request_digest="").validate()


if __name__ == "__main__":
    unittest.main()

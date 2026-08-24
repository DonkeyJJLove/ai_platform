import unittest

from cyber_lion.contracts.repository_maintenance_sandbox import (
    RepositoryMaintenanceContractError,
    RepositoryMaintenanceExecutionReceipt,
    RepositoryMaintenanceOperation,
    RepositoryMaintenancePolicy,
    evidence_digest,
)


class RepositoryMaintenanceContractTests(unittest.TestCase):
    def _policy(self):
        return RepositoryMaintenancePolicy(
            schema_version="1.0.0",
            repository="DonkeyJJLove/ai_platform",
            mission_id="E003-BRANCH-ZERO-SANDBOX-AUTONOMIZATION",
            protected_ref="master",
            allowed_prefixes=("docs/", "mission/"),
            max_deletions=45,
        ).validate()

    def _operation(self, branch="mission/example", classification="A"):
        p = self._policy()
        a = evidence_digest({"x": 1}, "ANCESTRY")
        pr = evidence_digest({"x": 2}, "PR")
        o = evidence_digest({"x": 3}, "OWNERSHIP")
        c = evidence_digest({"x": 4}, "CLASSIFICATION")
        return RepositoryMaintenanceOperation(
            schema_version="1.0.0",
            repository="DonkeyJJLove/ai_platform",
            mission_id=p.mission_id,
            drone_id="F48-001",
            operation_id="delete-001",
            dispatch_id="dispatch-001",
            fencing_token=1,
            generation=1,
            protected_master_sha="a"*40,
            branch_name=branch,
            expected_branch_head="b"*40,
            ancestry_evidence_digest=a,
            pr_state_evidence_digest=pr,
            ownership_evidence_digest=o,
            classification_digest=c,
            classification=classification,
            requested_effect="DELETE_EXACT_REF",
            policy_digest=p.digest(),
        )

    def test_policy_is_exact_and_evidence_only(self):
        p = self._policy()
        self.assertFalse(p.authority_effect)
        self.assertFalse(p.master_effect)
        self.assertEqual(len(p.digest()), 64)

    def test_protected_or_unsafe_branch_denied(self):
        for branch in ("master", "main", "refs/heads/x", "feature/x", "../x", "mission/../x"):
            with self.subTest(branch=branch):
                with self.assertRaises(RepositoryMaintenanceContractError):
                    self._operation(branch=branch).validate()

    def test_non_delete_classification_denied(self):
        with self.assertRaises(RepositoryMaintenanceContractError):
            self._operation(classification="C").validate()

    def test_receipt_cannot_report_master_or_authority_effect(self):
        values = dict(
            schema_version="1.0.0",
            receipt_id="r1",
            operation_id="op1",
            operation_digest="a"*64,
            policy_digest="b"*64,
            mission_id="E003-BRANCH-ZERO-SANDBOX-AUTONOMIZATION",
            drone_id="F48-001",
            dispatch_id="d1",
            fencing_token=1,
            generation=1,
            repository="DonkeyJJLove/ai_platform",
            master_sha_before="c"*40,
            master_sha_after="c"*40,
            branch_name="mission/x",
            branch_head_before="d"*40,
            branch_exists_after=False,
            effect="DELETE_BRANCH_REF",
            outcome="SUCCEEDED",
            observed_event_refs=("event:1",),
            authority_effect=False,
            master_effect=False,
        )
        receipt = RepositoryMaintenanceExecutionReceipt.build(**values)
        self.assertEqual(receipt.validate(), receipt)
        with self.assertRaises(RepositoryMaintenanceContractError):
            RepositoryMaintenanceExecutionReceipt.build(**{**values, "authority_effect": True})


if __name__ == "__main__":
    unittest.main()

from dataclasses import dataclass
import unittest

from cyber_lion.contracts.branch_ownership_registry import BranchOwnershipRecord
from cyber_lion.contracts.repository_maintenance_sandbox import (
    RepositoryMaintenanceOperation,
    RepositoryMaintenancePolicy,
    evidence_digest,
)
from cyber_lion.enterprise.repository_maintenance_sandbox import (
    ReplayGuard,
    RepositoryMaintenanceError,
    RepositoryMaintenanceSandbox,
)

MASTER = "a"*40
HEAD = "b"*40


@dataclass
class FakeBackend:
    branch_exists: bool = True
    head: str = HEAD
    master: str = MASTER
    compare_status: str = "ahead"
    ahead_by: int = 10
    behind_by: int = 0
    open_prs: tuple = ()
    ownership: str = "UNOWNED"
    deleted: bool = False

    def master_sha(self):
        return self.master

    def branch_sha(self, branch):
        return self.head if self.branch_exists else None

    def compare_branch_to_master(self, branch):
        return {"status": self.compare_status, "ahead_by": self.ahead_by, "behind_by": self.behind_by}

    def open_prs_for_branch(self, branch):
        return list(self.open_prs)

    def ownership_observation(self, branch, master_sha):
        if self.ownership == "ACTIVE":
            return BranchOwnershipRecord(
                repository="DonkeyJJLove/ai_platform",
                branch=branch,
                branch_head_sha=self.head,
                ownership_state="ACTIVE",
                mission_id="active-mission",
                baseline_sha=master_sha,
                superseded_by_branch=None,
                supersession_provenance_ref=None,
                source_provenance_ref="fake:active",
                epistemic_class="OBSERVED",
                record_revision=1,
            ).validate()
        return BranchOwnershipRecord(
            repository="DonkeyJJLove/ai_platform",
            branch=branch,
            branch_head_sha=self.head,
            ownership_state="UNOWNED",
            mission_id=None,
            baseline_sha=None,
            superseded_by_branch=None,
            supersession_provenance_ref=None,
            source_provenance_ref="fake:unowned",
            epistemic_class="OBSERVED",
            record_revision=1,
        ).validate()

    def delete_exact_branch_ref(self, branch, expected_head):
        if expected_head != self.head:
            raise RepositoryMaintenanceError("stale")
        self.branch_exists = False
        self.deleted = True


class RepositoryMaintenanceSandboxTests(unittest.TestCase):
    def policy(self):
        return RepositoryMaintenancePolicy(
            schema_version="1.0.0",
            repository="DonkeyJJLove/ai_platform",
            mission_id="E003-BRANCH-ZERO-SANDBOX-AUTONOMIZATION",
            protected_ref="master",
            allowed_prefixes=("docs/", "mission/"),
            max_deletions=45,
        ).validate()

    def operation(self, backend, *, branch="mission/x", master=MASTER, head=HEAD):
        p = self.policy()
        ancestry = {
            "branch": branch,
            "head": head,
            "master": master,
            "status": backend.compare_status,
            "ahead_by": backend.ahead_by,
            "behind_by": backend.behind_by,
        }
        pr_state = {
            "branch": branch,
            "open_pr_ids": sorted(
                int(item["number"]) for item in backend.open_prs
                if isinstance(item.get("number"), int)
            ),
        }
        ownership = backend.ownership_observation(branch, master).canonical_dict()
        ad = evidence_digest(ancestry, "ANCESTRY")
        pd = evidence_digest(pr_state, "PR")
        od = evidence_digest(ownership, "OWNERSHIP")
        classification = {
            "classification": "A",
            "branch": branch,
            "head": head,
            "master": master,
            "ancestry": ad,
            "pr": pd,
            "ownership": od,
        }
        return RepositoryMaintenanceOperation(
            schema_version="1.0.0",
            repository="DonkeyJJLove/ai_platform",
            mission_id=p.mission_id,
            drone_id="F48-001",
            operation_id="delete-001",
            dispatch_id="dispatch-001",
            fencing_token=1,
            generation=1,
            protected_master_sha=master,
            branch_name=branch,
            expected_branch_head=head,
            ancestry_evidence_digest=ad,
            pr_state_evidence_digest=pd,
            ownership_evidence_digest=od,
            classification_digest=evidence_digest(classification, "CLASSIFICATION"),
            classification="A",
            requested_effect="DELETE_EXACT_REF",
            policy_digest=p.digest(),
        ).validate()

    def test_exact_success_deletes_branch_and_preserves_master(self):
        backend = FakeBackend()
        sandbox = RepositoryMaintenanceSandbox(policy=self.policy(), backend=backend)
        receipt = sandbox.execute_delete(self.operation(backend))
        self.assertEqual(receipt.outcome, "SUCCEEDED")
        self.assertFalse(receipt.branch_exists_after)
        self.assertEqual(receipt.master_sha_before, MASTER)
        self.assertEqual(receipt.master_sha_after, MASTER)
        self.assertTrue(backend.deleted)

    def test_stale_master_denied(self):
        backend = FakeBackend(master="c"*40)
        sandbox = RepositoryMaintenanceSandbox(policy=self.policy(), backend=backend)
        with self.assertRaisesRegex(RepositoryMaintenanceError, "stale master"):
            sandbox.execute_delete(self.operation(backend, master=MASTER))

    def test_stale_branch_head_denied(self):
        backend = FakeBackend(head="c"*40)
        sandbox = RepositoryMaintenanceSandbox(policy=self.policy(), backend=backend)
        with self.assertRaisesRegex(RepositoryMaintenanceError, "stale branch"):
            sandbox.execute_delete(self.operation(backend, head=HEAD))

    def test_open_pr_denied(self):
        backend = FakeBackend(open_prs=({"number": 9},))
        sandbox = RepositoryMaintenanceSandbox(policy=self.policy(), backend=backend)
        with self.assertRaisesRegex(RepositoryMaintenanceError, "deletion eligible"):
            sandbox.execute_delete(self.operation(backend))

    def test_active_ownership_denied(self):
        backend = FakeBackend(ownership="ACTIVE")
        sandbox = RepositoryMaintenanceSandbox(policy=self.policy(), backend=backend)
        with self.assertRaisesRegex(RepositoryMaintenanceError, "deletion eligible"):
            sandbox.execute_delete(self.operation(backend))

    def test_unique_or_diverged_branch_denied(self):
        backend = FakeBackend(compare_status="diverged", behind_by=2)
        sandbox = RepositoryMaintenanceSandbox(policy=self.policy(), backend=backend)
        with self.assertRaisesRegex(RepositoryMaintenanceError, "deletion eligible"):
            sandbox.execute_delete(self.operation(backend))

    def test_replay_denied(self):
        backend = FakeBackend()
        guard = ReplayGuard()
        sandbox = RepositoryMaintenanceSandbox(policy=self.policy(), backend=backend, replay_guard=guard)
        op = self.operation(backend)
        sandbox.execute_delete(op)
        backend.branch_exists = True
        with self.assertRaisesRegex(RepositoryMaintenanceError, "replay"):
            sandbox.execute_delete(op)

    def test_already_absent_is_terminal_without_master_effect(self):
        backend = FakeBackend(branch_exists=False)
        sandbox = RepositoryMaintenanceSandbox(policy=self.policy(), backend=backend)
        receipt = sandbox.execute_delete(self.operation(FakeBackend()))
        self.assertEqual(receipt.outcome, "ALREADY_ABSENT")
        self.assertFalse(receipt.master_effect)


if __name__ == "__main__":
    unittest.main()

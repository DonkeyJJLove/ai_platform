from __future__ import annotations

import dataclasses
import unittest

from cyber_lion.contracts.fleet_reconciliation import (
    BranchEvidence,
    BranchReconciliation,
    ClosurePreconditions,
    ConvergenceReceipt,
    FleetReconciliationContractError,
    ReconciliationReport,
    ReconciliationTrustPins,
    RepositoryInventory,
)


REPO = "DonkeyJJLove/ai_platform"
DEFAULT = "a" * 40
HEAD = "b" * 40
IMPL = "1" * 64


def branch(**overrides) -> BranchEvidence:
    values = dict(
        repository=REPO,
        branch="mission/a",
        branch_head_sha=HEAD,
        mission_id="mission-a",
        baseline_sha=DEFAULT,
        ownership_state="TERMINAL",
        ancestry_state="DEFAULT_ANCESTOR_OF_HEAD",
        ahead_by=2,
        behind_by=0,
        superseded_by_branch=None,
        supersession_provenance_ref=None,
        source_provenance_ref="github:compare:a",
        epistemic_class="OBSERVED",
        observed_at="2026-08-21T12:00:00+00:00",
    )
    values.update(overrides)
    return BranchEvidence.build(**values)


def inventory(*branches: BranchEvidence, revision: int = 1, default_head: str = DEFAULT) -> RepositoryInventory:
    return RepositoryInventory.build(
        schema_version="1.0.0",
        inventory_id=f"inventory-{revision}",
        inventory_revision=revision,
        repository=REPO,
        default_branch="master",
        default_head_sha=default_head,
        source_id="github-inventory",
        source_instance_id="installation-1",
        source_implementation_digest=IMPL,
        trust_anchor_id="github-app:1",
        observed_at=f"2026-08-21T12:{revision:02d}:00+00:00",
        branches=branches,
    )


def closure(inv: RepositoryInventory, **overrides) -> ClosurePreconditions:
    values = dict(
        repository=REPO,
        inventory_digest=inv.inventory_digest,
        active_unknown_mission_count=0,
        unknown_result_count=0,
        unresolved_write_lease_count=0,
        unreconciled_effect_count=0,
        reconciliation_disagreement_count=0,
        source_provenance_refs=("fleet-status:snapshot", "repository-reconciliation:snapshot"),
        epistemic_class="ANCHORED",
        observed_at=inv.observed_at,
    )
    values.update(overrides)
    return ClosurePreconditions.build(**values)


class FleetReconciliationContractTests(unittest.TestCase):
    def test_branch_evidence_is_immutable_and_digest_bound(self) -> None:
        item = branch().validate()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            item.branch = "mission/x"  # type: ignore[misc]
        self.assertEqual(len(item.evidence_digest), 64)
        tampered = dataclasses.replace(item, ahead_by=3)
        with self.assertRaises(FleetReconciliationContractError):
            tampered.validate()

    def test_ancestry_counts_fail_closed(self) -> None:
        with self.assertRaises(FleetReconciliationContractError):
            branch(ancestry_state="DIVERGED", ahead_by=1, behind_by=0)
        with self.assertRaises(FleetReconciliationContractError):
            branch(ancestry_state="UNKNOWN", ahead_by=0, behind_by=0)

    def test_active_mission_requires_mission_and_baseline(self) -> None:
        with self.assertRaises(FleetReconciliationContractError):
            branch(ownership_state="ACTIVE", mission_id=None)

    def test_inventory_digest_and_source_pins_are_exact(self) -> None:
        inv = inventory(branch())
        self.assertEqual(
            inv.source_pins().binding(),
            ReconciliationTrustPins(
                "github-inventory", "installation-1", IMPL, "github-app:1"
            ).binding(),
        )
        with self.assertRaises(FleetReconciliationContractError):
            dataclasses.replace(inv, default_head_sha="c" * 40).validate()

    def test_inventory_rejects_default_branch_as_candidate(self) -> None:
        with self.assertRaises(FleetReconciliationContractError):
            inventory(branch(branch="master"))

    def test_closure_preconditions_are_digest_bound_and_fail_closed(self) -> None:
        inv = inventory(branch())
        ready = closure(inv)
        self.assertTrue(ready.satisfied())
        blocked = closure(inv, unresolved_write_lease_count=1)
        self.assertFalse(blocked.satisfied())
        self.assertEqual(blocked.blocker_codes(), ("UNRESOLVED_WRITE_LEASE",))
        with self.assertRaises(FleetReconciliationContractError):
            dataclasses.replace(blocked, unresolved_write_lease_count=0).validate()

    def test_untrusted_closure_evidence_is_a_blocker(self) -> None:
        inv = inventory(branch())
        blocked = closure(inv, epistemic_class="INFERRED")
        self.assertIn("CLOSURE_EVIDENCE_UNTRUSTED", blocked.blocker_codes())

    def test_converged_report_cannot_launder_merge_candidate(self) -> None:
        inv = inventory(branch())
        pre = closure(inv)
        rec = BranchReconciliation(
            repository=REPO,
            inventory_digest=inv.inventory_digest,
            branch="mission/a",
            branch_head_sha=HEAD,
            mission_id="mission-a",
            baseline_sha=DEFAULT,
            classification="MERGE_CANDIDATE",
            rationale_code="BRANCH_AHEAD_OF_CURRENT_DEFAULT",
            evidence_digest=inv.branches[0].evidence_digest,
            observed_at=inv.branches[0].observed_at,
        ).validate()
        with self.assertRaises(FleetReconciliationContractError):
            ReconciliationReport.build(
                schema_version="1.0.0",
                report_id="report-1",
                repository=REPO,
                inventory_id=inv.inventory_id,
                inventory_revision=inv.inventory_revision,
                inventory_digest=inv.inventory_digest,
                default_head_sha=inv.default_head_sha,
                closure_preconditions=pre,
                closure_preconditions_digest=pre.preconditions_digest,
                observed_at=inv.observed_at,
                disposition="CONVERGED",
                anomaly_codes=("MERGE_CANDIDATE",),
                branches=(rec,),
            )

    def test_converged_report_cannot_ignore_closure_blocker(self) -> None:
        integrated = branch(ancestry_state="HEAD_ANCESTOR_OF_DEFAULT", ahead_by=0, behind_by=1)
        inv = inventory(integrated)
        pre = closure(inv, unreconciled_effect_count=1)
        rec = BranchReconciliation(
            repository=REPO,
            inventory_digest=inv.inventory_digest,
            branch=integrated.branch,
            branch_head_sha=integrated.branch_head_sha,
            mission_id=integrated.mission_id,
            baseline_sha=integrated.baseline_sha,
            classification="ALREADY_INTEGRATED",
            rationale_code="HEAD_ALREADY_IN_DEFAULT_HISTORY",
            evidence_digest=integrated.evidence_digest,
            observed_at=integrated.observed_at,
        ).validate()
        with self.assertRaises(FleetReconciliationContractError):
            ReconciliationReport.build(
                schema_version="1.0.0",
                report_id="report-2",
                repository=REPO,
                inventory_id=inv.inventory_id,
                inventory_revision=inv.inventory_revision,
                inventory_digest=inv.inventory_digest,
                default_head_sha=inv.default_head_sha,
                closure_preconditions=pre,
                closure_preconditions_digest=pre.preconditions_digest,
                observed_at=inv.observed_at,
                disposition="CONVERGED",
                anomaly_codes=("UNRECONCILED_EFFECT",),
                branches=(rec,),
            )

    def test_convergence_receipt_is_evidence_only_and_binds_closure(self) -> None:
        receipt = ConvergenceReceipt.build(
            schema_version="1.0.0",
            receipt_id="receipt-1",
            repository=REPO,
            inventory_id="inventory-1",
            inventory_revision=1,
            inventory_digest="2" * 64,
            report_id="report-1",
            report_digest="3" * 64,
            closure_preconditions_digest="4" * 64,
            default_head_sha=DEFAULT,
            issued_at="2026-08-21T12:10:00+00:00",
        )
        self.assertEqual(receipt.purpose, "MISSION_CLOSE_EVIDENCE_ONLY")
        self.assertEqual(receipt.closure_preconditions_digest, "4" * 64)
        forbidden = {"authority", "merge_permission", "action", "release", "deploy"}
        self.assertTrue(forbidden.isdisjoint({field.name for field in dataclasses.fields(receipt)}))
        with self.assertRaises(FleetReconciliationContractError):
            dataclasses.replace(receipt, purpose="MERGE_PERMISSION").validate()


if __name__ == "__main__":
    unittest.main()

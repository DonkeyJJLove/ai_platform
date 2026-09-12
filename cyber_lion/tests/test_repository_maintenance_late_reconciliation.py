from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from cyber_lion.enterprise.repository_delete_fence import RepositoryDeleteFence, RepositoryDeleteFenceRecord
from cyber_lion.enterprise.repository_maintenance_mediated_cleanup import (
    CanonicalSlashSafeGitHubRepositoryMaintenanceBackend,
    MediatedRepositoryMaintenanceError,
    late_reconcile_unknown_delete,
)

MASTER = "a" * 40
TREE = "b" * 40
HEAD = "c" * 40
EFFECT = "1" * 64


def record():
    return RepositoryDeleteFenceRecord(
        effect_key=EFFECT, admission_digest="2" * 64, repository="DonkeyJJLove/ai_platform",
        mission_id="LION-V1_4-R2-POST306-FINAL-BRANCH-CLOSURE-R1",
        authority_lineage_digest="3" * 64, policy_digest="4" * 64, control_comment_id=123,
        branch="cyber-lion/example", expected_branch_head=HEAD, expected_master=MASTER,
        expected_master_tree=TREE, provider_id="5" * 64, execution_id="github:1:1",
        authority_epoch=1, state="PREPARED", prepared_at="2026-09-09T19:00:00+00:00",
    ).validate()


class RepositoryMaintenanceLateReconciliationTests(unittest.TestCase):
    def make(self, td, *, branch_absent=True):
        path = str(Path(td) / "fence.sqlite")
        fence = RepositoryDeleteFence(path)
        r = record(); fence.prepare(r); fence.mark_attempted(EFFECT, attempted_at="2026-09-09T19:00:01+00:00"); fence.mark_unknown(EFFECT)
        backend = CanonicalSlashSafeGitHubRepositoryMaintenanceBackend("DonkeyJJLove/ai_platform", "token")
        backend.master_sha = lambda: MASTER
        backend.master_tree = lambda _master: TREE
        backend.branch_sha = lambda _branch: None if branch_absent else HEAD
        return path, fence, backend

    def test_late_reconciliation_requires_absent_branch_and_preserves_unknown_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            path, fence, backend = self.make(td)
            out = late_reconcile_unknown_delete(
                fence=fence, backend=backend, effect_key=EFFECT, expected_master=MASTER, expected_tree=TREE
            )
            self.assertEqual(out["fence_state"], "RECONCILED")
            self.assertEqual(out["mode"], "LATE_UNKNOWN_ABSENCE")
            self.assertFalse(out["repository_effect"])
            self.assertEqual(fence.get(EFFECT).state, "RECONCILED")
            c = sqlite3.connect(path)
            try:
                row = c.execute("SELECT prior_state,source_ref FROM repository_delete_late_reconciliation WHERE effect_key=?", (EFFECT,)).fetchone()
            finally:
                c.close()
            self.assertEqual(row[0], "UNKNOWN")
            self.assertIn("cyber-lion/example:absent@" + MASTER, row[1])

    def test_late_reconciliation_denies_if_ref_is_still_visible(self):
        with tempfile.TemporaryDirectory() as td:
            _path, fence, backend = self.make(td, branch_absent=False)
            with self.assertRaisesRegex(MediatedRepositoryMaintenanceError, "repository observation mismatch"):
                late_reconcile_unknown_delete(
                    fence=fence, backend=backend, effect_key=EFFECT, expected_master=MASTER, expected_tree=TREE
                )
            self.assertEqual(fence.get(EFFECT).state, "UNKNOWN")

    def test_late_reconciliation_denies_master_drift(self):
        with tempfile.TemporaryDirectory() as td:
            _path, fence, backend = self.make(td)
            backend.master_sha = lambda: "d" * 40
            with self.assertRaisesRegex(MediatedRepositoryMaintenanceError, "repository observation mismatch"):
                late_reconcile_unknown_delete(
                    fence=fence, backend=backend, effect_key=EFFECT, expected_master=MASTER, expected_tree=TREE
                )
            self.assertEqual(fence.get(EFFECT).state, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()

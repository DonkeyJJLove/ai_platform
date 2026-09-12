from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cyber_lion.enterprise.repository_delete_fence import (
    RepositoryDeleteFence,
    RepositoryDeleteFenceError,
    RepositoryDeleteFenceRecord,
)


class RepositoryDeleteFenceTests(unittest.TestCase):
    def _record(self, *, effect_key: str = "1" * 64, execution_id: str = "exec:1") -> RepositoryDeleteFenceRecord:
        return RepositoryDeleteFenceRecord(
            effect_key=effect_key,
            admission_digest="2" * 64,
            repository="DonkeyJJLove/ai_platform",
            mission_id="E003-BRANCH-ZERO-SANDBOX-AUTONOMIZATION",
            authority_lineage_digest="3" * 64,
            policy_digest="4" * 64,
            control_comment_id=144001,
            branch="mission/example",
            expected_branch_head="a" * 40,
            expected_master="b" * 40,
            expected_master_tree="c" * 40,
            provider_id="github-rest-ref-maintenance-v1",
            execution_id=execution_id,
            authority_epoch=6,
            state="PREPARED",
            prepared_at="2026-08-26T06:30:00+00:00",
        ).validate()

    def test_connection_context_closes_after_read(self):
        with tempfile.TemporaryDirectory() as td:
            fence = RepositoryDeleteFence(str(Path(td) / "delete.sqlite3"))
            connection = fence._connect()
            with connection as active:
                self.assertEqual(active.execute("SELECT 1").fetchone(), (1,))
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")

    def test_connection_context_rolls_back_and_closes(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "delete.sqlite3")
            fence = RepositoryDeleteFence(path)
            connection = fence._connect()
            with self.assertRaisesRegex(RuntimeError, "rollback-probe"):
                with connection as active:
                    active.execute("BEGIN IMMEDIATE")
                    active.execute("INSERT INTO repository_delete_late_reconciliation VALUES(?,?,?,?,?,?,?)", ("1"*64,"UNKNOWN","2"*64,"3"*64,"a","b","c"))
                    raise RuntimeError("rollback-probe")
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")
            check = sqlite3.connect(path)
            try:
                self.assertEqual(check.execute("SELECT COUNT(*) FROM repository_delete_late_reconciliation").fetchone(), (0,))
            finally:
                check.close()

    def test_restart_durable_exact_replay_is_denied(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "delete.sqlite3")
            first = RepositoryDeleteFence(path)
            record = self._record()
            self.assertEqual(first.prepare(record).state, "PREPARED")
            reopened = RepositoryDeleteFence(path)
            with self.assertRaisesRegex(RepositoryDeleteFenceError, "replay or binding collision"):
                reopened.prepare(record)
            self.assertEqual(reopened.get(record.effect_key).state, "PREPARED")

    def test_concurrent_identical_prepare_has_exactly_one_winner(self):
        with tempfile.TemporaryDirectory() as td:
            fence = RepositoryDeleteFence(str(Path(td) / "delete.sqlite3"))
            record = self._record()

            def attempt() -> bool:
                try:
                    fence.prepare(record)
                    return True
                except RepositoryDeleteFenceError:
                    return False

            with ThreadPoolExecutor(max_workers=8) as pool:
                outcomes = list(pool.map(lambda _: attempt(), range(8)))
            self.assertEqual(sum(outcomes), 1)

    def test_attempt_is_persisted_before_observation_and_reconciliation(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "delete.sqlite3")
            fence = RepositoryDeleteFence(path)
            record = self._record()
            fence.prepare(record)
            attempted = fence.mark_attempted(record.effect_key, attempted_at="2026-08-26T06:30:01+00:00")
            self.assertEqual(attempted.state, "ATTEMPTED")
            reopened = RepositoryDeleteFence(path)
            self.assertEqual(reopened.get(record.effect_key).state, "ATTEMPTED")
            observed = reopened.mark_observed(
                record.effect_key,
                observation_digest="5" * 64,
                observed_at="2026-08-26T06:30:02+00:00",
            )
            self.assertEqual(observed.state, "OBSERVED")
            reconciled = reopened.mark_reconciled(
                record.effect_key,
                reconciliation_digest="6" * 64,
                reconciled_at="2026-08-26T06:30:03+00:00",
            )
            self.assertEqual(reconciled.state, "RECONCILED")

    def test_unknown_is_terminal_for_retry_in_this_fence(self):
        with tempfile.TemporaryDirectory() as td:
            fence = RepositoryDeleteFence(str(Path(td) / "delete.sqlite3"))
            record = self._record()
            fence.prepare(record)
            fence.mark_attempted(record.effect_key, attempted_at="2026-08-26T06:30:01+00:00")
            self.assertEqual(fence.mark_unknown(record.effect_key).state, "UNKNOWN")
            with self.assertRaises(RepositoryDeleteFenceError):
                fence.mark_attempted(record.effect_key, attempted_at="2026-08-26T06:31:00+00:00")

    def test_attempted_unknown_can_be_late_reconciled_without_retry(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "delete.sqlite3")
            fence = RepositoryDeleteFence(path)
            record = self._record()
            fence.prepare(record)
            fence.mark_attempted(record.effect_key, attempted_at="2026-08-26T06:30:01+00:00")
            fence.mark_unknown(record.effect_key)
            final = fence.late_reconcile_unknown(
                record.effect_key,
                observation_digest="5" * 64,
                observed_at="2026-08-26T06:31:00+00:00",
                reconciliation_digest="6" * 64,
                reconciled_at="2026-08-26T06:31:01+00:00",
                source_ref="github:late-readback:mission/example:absent",
            )
            self.assertEqual(final.state, "RECONCILED")
            self.assertEqual(final.attempted_at, "2026-08-26T06:30:01+00:00")
            with self.assertRaises(RepositoryDeleteFenceError):
                fence.mark_attempted(record.effect_key, attempted_at="2026-08-26T06:32:00+00:00")
            with self.assertRaisesRegex(RepositoryDeleteFenceError, "only attempted UNKNOWN"):
                fence.late_reconcile_unknown(
                    record.effect_key, observation_digest="7" * 64, observed_at="x",
                    reconciliation_digest="8" * 64, reconciled_at="y", source_ref="replay",
                )
            c = sqlite3.connect(path)
            try:
                row = c.execute(
                    "SELECT prior_state,observation_digest,reconciliation_digest,source_ref FROM repository_delete_late_reconciliation WHERE effect_key=?",
                    (record.effect_key,),
                ).fetchone()
            finally:
                c.close()
            self.assertEqual(row, ("UNKNOWN", "5" * 64, "6" * 64, "github:late-readback:mission/example:absent"))

    def test_prepared_unknown_without_attempt_cannot_be_late_reconciled(self):
        with tempfile.TemporaryDirectory() as td:
            fence = RepositoryDeleteFence(str(Path(td) / "delete.sqlite3"))
            record = self._record()
            fence.prepare(record)
            fence.mark_unknown(record.effect_key)
            with self.assertRaisesRegex(RepositoryDeleteFenceError, "only attempted UNKNOWN"):
                fence.late_reconcile_unknown(
                    record.effect_key, observation_digest="5" * 64, observed_at="x",
                    reconciliation_digest="6" * 64, reconciled_at="y", source_ref="late",
                )

    def test_cross_execution_binding_collision_is_denied(self):
        with tempfile.TemporaryDirectory() as td:
            fence = RepositoryDeleteFence(str(Path(td) / "delete.sqlite3"))
            first = self._record()
            fence.prepare(first)
            second = self._record(effect_key="7" * 64, execution_id="exec:2")
            # Same admission digest is itself an exact-once domain and cannot be rebound.
            with self.assertRaises(RepositoryDeleteFenceError):
                fence.prepare(second)


if __name__ == "__main__":
    unittest.main()

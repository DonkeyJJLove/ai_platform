import sqlite3
import tempfile
import unittest
from pathlib import Path

from cyber_lion.mission_control import dual_result_join as dual
from cyber_lion.mission_control import execution_driver


def now():
    return "2026-09-14T12:00:00Z"


class DualReceiptImmutabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "receipts.db"
        self.conn = self.connect()
        self.conn.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,schema_id TEXT UNIQUE,applied_at TEXT,source_head TEXT,source_tree TEXT,migration_digest TEXT,note TEXT)")
        execution_driver.migrate(self.conn, now)
        self.request = dual.create_dual(self.conn, "M1", "P1", "Describe current state", {"head": "a" * 40}, now)["request_id"]

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def record(self, provider, answer="original", **kwargs):
        return dual.record_response(self.conn, self.request, provider, answer, now, **kwargs)

    def snapshot(self):
        return (
            [tuple(r) for r in self.conn.execute("SELECT * FROM mission_dual_receipts ORDER BY provider")],
            [tuple(r) for r in self.conn.execute("SELECT * FROM mission_dual_evaluations")],
        )

    def test_identical_replay_rejected_for_both_providers_after_reopen(self):
        for provider in (dual.LOCAL_PROVIDER, dual.SAAS_PROVIDER):
            self.record(provider, transport="LOCAL_OR_MEDIATED")
        before = self.snapshot()
        self.conn.close()
        self.conn = self.connect()
        for provider in (dual.LOCAL_PROVIDER, dual.SAAS_PROVIDER):
            with self.subTest(provider=provider):
                with self.assertRaisesRegex(ValueError, "^dual response duplicate$"):
                    self.record(provider, " original ", transport="LOCAL_OR_MEDIATED")
                self.assertEqual(before, self.snapshot())
        self.assertEqual(self.conn.execute("SELECT state FROM mission_dual_evaluations").fetchone()[0], "JOIN_READY")
        self.assertEqual(dual.join_result(self.conn, self.request)["state"], "JOINED")

    def test_conflicting_answer_or_metadata_never_changes_first_receipt(self):
        for provider in (dual.LOCAL_PROVIDER, dual.SAAS_PROVIDER):
            self.record(provider, transport="ORIGINAL")
        before = self.snapshot()
        for provider in (dual.LOCAL_PROVIDER, dual.SAAS_PROVIDER):
            for answer, transport, effect in (("changed", "ORIGINAL", "NONE"), ("original", "CHANGED", "NONE"), ("original", "ORIGINAL", "CHANGED")):
                with self.subTest(provider=provider, answer=answer, transport=transport, effect=effect):
                    with self.assertRaisesRegex(ValueError, "^dual response conflict$"):
                        self.record(provider, answer, transport=transport, authority_effect=effect)
                    self.assertEqual(before, self.snapshot())
        self.conn.close()
        self.conn = self.connect()
        self.assertEqual(before, self.snapshot())

    def test_conflict_from_second_connection_preserves_durable_receipt(self):
        self.record(dual.LOCAL_PROVIDER)
        before = self.snapshot()
        other = self.connect()
        try:
            with self.assertRaisesRegex(ValueError, "^dual response conflict$"):
                dual.record_response(other, self.request, dual.LOCAL_PROVIDER, "different", now)
        finally:
            other.close()
        self.assertEqual(before, self.snapshot())
        self.record(dual.SAAS_PROVIDER)
        self.assertEqual(dual.join_result(self.conn, self.request)["state"], "JOINED")


if __name__ == "__main__":
    unittest.main()

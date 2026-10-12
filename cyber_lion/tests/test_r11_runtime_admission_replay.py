"""Durable R11 replay guard: atomic one-shot admission and fail-closed drift."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import sqlite3
import tempfile
import unittest

from cyber_lion.enterprise.r11_runtime_admission_replay import (
    SCHEMA,
    TABLE,
    R11AdmissionReplayError,
    SQLiteR11RuntimeAdmissionReplayGuard,
)


class R11RuntimeAdmissionReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="lion-r11-replay-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.db=self.root/"admission-issuance.sqlite"

    def test_first_consume_true_exact_replay_false(self):
        guard=SQLiteR11RuntimeAdmissionReplayGuard(self.db)
        key="a"*64
        self.assertTrue(guard.consume(key))
        self.assertFalse(guard.consume(key))
        with sqlite3.connect(self.db) as conn:
            rows=conn.execute("SELECT replay_key,schema_id FROM "+TABLE).fetchall()
        self.assertEqual(rows,[(key,SCHEMA)])

    def test_restart_rejects_consumed_replay_key(self):
        key="b"*64
        first=SQLiteR11RuntimeAdmissionReplayGuard(self.db)
        self.assertTrue(first.consume(key))
        second=SQLiteR11RuntimeAdmissionReplayGuard(self.db)
        self.assertFalse(second.consume(key))
        self.assertTrue(second.consume("c"*64))
        third=SQLiteR11RuntimeAdmissionReplayGuard(self.db)
        self.assertFalse(third.consume("c"*64))

    def test_concurrent_consumers_only_one_passes(self):
        key="d"*64
        guards=[SQLiteR11RuntimeAdmissionReplayGuard(self.db) for _ in range(12)]
        with ThreadPoolExecutor(max_workers=12) as pool:
            outcomes=list(pool.map(lambda g: g.consume(key),guards))
        self.assertEqual(outcomes.count(True),1)
        self.assertEqual(outcomes.count(False),11)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM "+TABLE).fetchone()[0],1)

    def test_allows_distinct_exact_64_digit_keys(self):
        guard=SQLiteR11RuntimeAdmissionReplayGuard(self.db)
        for key in ("0"*64,"1"*64,"f"*64):
            self.assertTrue(guard.consume(key))

    def test_invalid_keys_fail_closed_without_inserts(self):
        guard=SQLiteR11RuntimeAdmissionReplayGuard(self.db)
        for key in ("a"*63,"A"*64,"g"*64,"",None,64,True):
            with self.assertRaisesRegex(R11AdmissionReplayError,
                                         "canonical admission replay digest"):
                guard.consume(key)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM "+TABLE).fetchone()[0],0)

    def test_hardlinked_file_denied_before_sqlite_open(self):
        self.db.write_bytes(b"")
        os.link(self.db,self.root/"alias.sqlite")
        with self.assertRaisesRegex(R11AdmissionReplayError,"file type"):
            SQLiteR11RuntimeAdmissionReplayGuard(self.db)

    def test_symlink_file_denied(self):
        actual=self.root/"actual.sqlite"
        actual.write_bytes(b"")
        self.db.symlink_to(actual)
        with self.assertRaisesRegex(R11AdmissionReplayError,"direct absolute"):
            SQLiteR11RuntimeAdmissionReplayGuard(self.db)

    def test_symlink_parent_denied(self):
        target=self.root/"data"
        target.mkdir()
        parent=self.root/"link"
        parent.symlink_to(target,target_is_directory=True)
        with self.assertRaisesRegex(R11AdmissionReplayError,
                                     "replay parent not private or indirect"):
            SQLiteR11RuntimeAdmissionReplayGuard(parent/"replay.sqlite")

    def test_world_writable_parent_denied(self):
        sub=self.root/"untrusted"
        sub.mkdir()
        sub.chmod(0o777)
        with self.assertRaisesRegex(R11AdmissionReplayError,"replay parent not private"):
            SQLiteR11RuntimeAdmissionReplayGuard(sub/"replay.sqlite")

    def test_world_readable_existing_state_denied(self):
        self.db.write_bytes(b"")
        self.db.chmod(0o644)
        with self.assertRaisesRegex(R11AdmissionReplayError,"owner/mode not private"):
            SQLiteR11RuntimeAdmissionReplayGuard(self.db)

    def test_substituted_path_after_open_denied(self):
        guard=SQLiteR11RuntimeAdmissionReplayGuard(self.db)
        old=self.root/"old.sqlite"
        self.db.rename(old)
        replacement=SQLiteR11RuntimeAdmissionReplayGuard(self.db)
        self.assertIsNotNone(replacement)
        with self.assertRaisesRegex(R11AdmissionReplayError,"identity drift"):
            guard.consume("e"*64)

    def test_removed_state_cannot_be_silently_recreated(self):
        guard=SQLiteR11RuntimeAdmissionReplayGuard(self.db)
        self.db.unlink()
        with self.assertRaisesRegex(R11AdmissionReplayError,"unavailable"):
            guard.consume("e"*64)
        self.assertFalse(self.db.exists())

    def test_schema_substitution_denied(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE "+TABLE+"(replay_key TEXT PRIMARY KEY)")
        self.db.chmod(0o600)
        with self.assertRaisesRegex(R11AdmissionReplayError,"schema incompatible"):
            SQLiteR11RuntimeAdmissionReplayGuard(self.db)


if __name__=="__main__":
    unittest.main()

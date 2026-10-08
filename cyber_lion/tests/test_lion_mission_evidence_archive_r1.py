import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from hashlib import sha256

MODULE = Path(__file__).resolve().parents[2] / "tools" / "lion_mission_evidence_archive_r1.py"
spec = importlib.util.spec_from_file_location("lion_mission_evidence_archive_r1", MODULE)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)

def fixture(root, *, orphan=False):
    p = root / "mission-control-v3.db"
    conn = sqlite3.connect(p)
    conn.executescript("""
      CREATE TABLE missions (
       mission_id TEXT PRIMARY KEY, title TEXT, state TEXT, runtime_state TEXT,
       source_head TEXT,source_tree TEXT,spec_digest TEXT,created_at TEXT,updated_at TEXT);
      CREATE TABLE mission_events (mission_id TEXT,event_type TEXT,payload_json TEXT);
      CREATE TABLE operator_events (mission_id TEXT,event_type TEXT,payload_json TEXT);
      CREATE TABLE mission_model_calls (mission_id TEXT,provider TEXT,state TEXT);
      CREATE TABLE mission_artifacts (mission_id TEXT,content_json TEXT);
    """)
    rows = [
        ("DONE-001", "Done", "COMPLETE", "DRIVER_COMPLETE", "a"*40, "b"*40, "c"*64, "2026-10-01", "2026-10-02"),
        ("SUPER-002", "Superseded", "SUPERSEDED", "SUPERSEDED_BY:DONE-001", "b"*40, "c"*40, "d"*64, "2026-10-01", "2026-10-02"),
        ("RUNNING-003", "Still running", "AUTHORIZED", "NOT_STARTED", "c"*40, "d"*40, "e"*64, "2026-10-01", "2026-10-08"),
    ]
    conn.executemany("INSERT INTO missions VALUES (?,?,?,?,?,?,?,?,?)", rows)
    conn.executemany("INSERT INTO mission_events VALUES (?,?,?)", [
        ("DONE-001", "COMPLETE", '{"safe":true}'),
        ("RUNNING-003", "ERROR", '{"request":"pending"}'),
    ])
    conn.executemany("INSERT INTO operator_events VALUES (?,?,?)", [
        ("DONE-001", "DECISION_OBSERVED", '{"decision":"archivable"}'),
        ("DONE-001", "DECISION_OBSERVED", '{"decision":"audited"}'),
        ("RUNNING-003", "BROKER_PENDING", '{"status":"PENDING"}'),
    ])
    conn.executemany("INSERT INTO mission_model_calls VALUES (?,?,?)", [
        ("DONE-001", "LOCAL", "COMPLETE"),
        ("DONE-001", "SAAS", "COMPLETE"),
        ("RUNNING-003", "SAAS", "PENDING"),
    ])
    conn.executemany("INSERT INTO mission_artifacts VALUES (?,?)", [
        ("DONE-001", '{"bytes":"hash"}'),
        ("RUNNING-003", '{"not_completed":true}'),
    ])
    if orphan:
        conn.execute("INSERT INTO operator_events VALUES (?,?,?)",
                     ("UNKNOWN-ORPHAN", "EVENT", "{}"))
    conn.commit()
    conn.close()
    return p


class MissionArchiveTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.root = Path(self._t.name)
        self.db = fixture(self.root)
        self.out = self.root / "archives"

    def test_plan_2_terminal_one_protected(self):
        c = archive.open_readonly(self.db)
        try:
            x = archive.describe_snapshot(c, expect_terminal=2, expect_protected=1)
        finally:
            c.close()
        self.assertEqual(x["terminal_count"], 2)
        self.assertEqual(x["protected_states"], {"AUTHORIZED":1})
        self.assertEqual(x["evidence_count_totals"]["operator_events"],2)
        self.assertEqual(x["evidence_count_totals"]["mission_model_calls"],2)
        self.assertEqual(x["trails"][0]["hypothesis_reconstruction"],
                         "UNKNOWN_NOT_STRUCTURED_IN_PREVIOUS_RECORD")

    def test_archival_live_db_is_not_changed_and_copy_is_validated(self):
        before = archive.file_sha(self.db)
        x = archive.archive(self.db,self.out,"test-terminal-20261008",
                            expected_terminal=2,expected_protected=1)
        self.assertEqual(x["result"], "PASS_VERIFIED_ARCHIVE_READBACK")
        self.assertEqual(x["terminal_count"], 2)
        self.assertEqual(x["protected_count"], 1)
        self.assertEqual(archive.file_sha(self.db),before)
        archive_root = self.out/"test-terminal-20261008"
        self.assertEqual(archive_root.stat().st_mode&0o777,0o700)
        self.assertEqual((archive_root/"snapshot.sqlite3").stat().st_mode&0o777,0o600)
        self.assertEqual(archive.verify_archive(archive_root),{
            key:x[key] for key in ("result","archive_id","terminal_count",
                                  "protected_count","sqlite_sha256",
                                  "manifest_digest","authority_effect")})
        with (archive_root/"reasoning_trails.jsonl").open() as f:
            rows=[json.loads(line) for line in f]
        self.assertEqual({r["mission_id"] for r in rows},{"DONE-001","SUPER-002"})
        self.assertEqual(rows[0]["archival_effect"],
                         "COPY_ONLY_NOT_A_MISSION_COMPLETION_RECEIPT")

    def test_repeated_archive_is_idempotent(self):
        first=archive.archive(self.db,self.out,"test-terminal-20261008",
                              expected_terminal=2,expected_protected=1)
        second=archive.archive(self.db,self.out,"test-terminal-20261008",
                               expected_terminal=2,expected_protected=1)
        self.assertTrue(second["idempotent_existing"])
        self.assertEqual(first["sqlite_sha256"],second["sqlite_sha256"])

    def test_archive_receipt_detects_tamper(self):
        archive.archive(self.db,self.out,"test-terminal-20261008",
                        expected_terminal=2,expected_protected=1)
        trail=self.out/"test-terminal-20261008"/"reasoning_trails.jsonl"
        with trail.open("ab") as f:f.write(b"\n")
        with self.assertRaisesRegex(archive.ArchiveError,"TRAIL_BYTES_CHANGED"):
            archive.verify_archive(trail.parent)

    def test_protected_state_cannot_be_silently_reclassified(self):
        with self.assertRaisesRegex(archive.ArchiveError,"MISSION_COUNTS_DRIFT"):
            archive.archive(self.db,self.out,"test-terminal-20261008",
                            expected_terminal=3,expected_protected=0)

    def test_orphan_mission_link_requires_review(self):
        other=self.root/"other"
        other.mkdir()
        db=fixture(other,orphan=True)
        c=archive.open_readonly(db)
        try:
            with self.assertRaisesRegex(archive.ArchiveError,"ORPHAN_MISSION_REFERENCES"):
                archive.describe_snapshot(c)
        finally:
            c.close()

    def test_invalid_id_and_missing_source_fail_closed(self):
        with self.assertRaisesRegex(archive.ArchiveError,"ARCHIVE_ID_INVALID"):
            archive.archive(self.db,self.out,"../escape",
                            expected_terminal=2,expected_protected=1)
        with self.assertRaisesRegex(archive.ArchiveError,"CANONICAL_DB_PATH_REQUIRED"):
            archive.open_readonly(self.root/"unknown.db")


if __name__ == "__main__":
    unittest.main()

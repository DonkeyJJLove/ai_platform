from __future__ import annotations
from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
import unittest

from tools.lion_legacy_conversation_inventory import audit, LegacyConversationAuditError

class LegacyAuditTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(prefix="lion-canonical-legacy-census-")
        self.addCleanup(t.cleanup)
        self.db = Path(t.name) / "canonical.db"
        with closing(sqlite3.connect(self.db)) as c, c:
            c.executescript("""
                CREATE TABLE conversations(conversation_id TEXT PRIMARY KEY,state TEXT);
                CREATE TABLE conversation_bindings(
                    conversation_id TEXT,binding_epoch INTEGER,mission_id TEXT,state TEXT);
                CREATE TABLE conversation_provider_lanes(
                    conversation_id TEXT,binding_epoch INTEGER,lane_id TEXT,provider TEXT);
                CREATE TABLE conversation_external_bridges(
                    conversation_id TEXT,external_system TEXT);
                CREATE TABLE conversation_delivery_events(
                    conversation_id TEXT,binding_epoch INTEGER,lane_id TEXT,state TEXT);
            """)

    def add(self, cid, state="UNBOUND", mission=None, saas=False, bridge=False, persisted=False):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("INSERT INTO conversations VALUES(?,?)", (cid, state))
            c.execute("INSERT INTO conversation_bindings VALUES(?,?,?,?)",
                      (cid,1,mission,state))
            if saas or persisted:
                c.execute("INSERT INTO conversation_provider_lanes VALUES(?,?,?,?)",
                          (cid,1,"lane-1","SAAS"))
            if bridge:
                c.execute("INSERT INTO conversation_external_bridges VALUES(?,?)",
                          (cid,"CHATGPT_SAAS"))
            if persisted:
                c.execute("INSERT INTO conversation_delivery_events VALUES(?,?,?,?)",
                          (cid,1,"lane-1","PERSISTED"))

    def test_separate_candidates_from_existing_bridges_and_legacy_claims(self):
        self.add("fresh-ad-hoc")
        self.add("fresh-mission", state="BOUND", mission="M1")
        self.add("past-saas", saas=True, persisted=True)
        self.add("already-linked", bridge=True)
        self.add("frozen", state="FROZEN", mission="M2", bridge=True)
        result = audit(self.db)
        r = {v["conversation_id"]:v for v in result["rows"]}
        self.assertEqual(r["fresh-ad-hoc"]["classification"],"NEW_EXPLICIT_OPERATOR_LINK_CANDIDATE")
        self.assertEqual(r["fresh-mission"]["mission_scope"],"MISSION")
        self.assertEqual(r["fresh-mission"]["classification"],"NEW_EXPLICIT_OPERATOR_LINK_CANDIDATE")
        self.assertEqual(r["past-saas"]["classification"],"LEGACY_SAAS_CLAIM_RECONCILIATION_REQUIRED")
        self.assertEqual(r["already-linked"]["classification"],"BRIDGE_RECORD_REVALIDATION_REQUIRED")
        self.assertEqual(r["frozen"]["classification"],"FROZEN_HISTORICAL_PRESERVE")
        self.assertTrue(all(not x["ready_to_send"] and not x["authorized_to_bind"] and not x["authorized_to_delete"] for x in r.values()))
        self.assertEqual(result["conversation_count"],5)
        self.assertEqual(result["effects"],[])

    def test_missing_original_schema_denied(self):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("DROP TABLE conversation_delivery_events")
        with self.assertRaisesRegex(LegacyConversationAuditError,"incomplete"):
            audit(self.db)

    def test_ambiguous_missing_binding_hold(self):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("INSERT INTO conversations VALUES('orphan','UNBOUND')")
        result=audit(self.db)
        self.assertEqual(result["rows"][0]["classification"],"INCOMPLETE_CANONICAL_BINDING_HOLD")

    def test_query_only_does_not_mutate_sqlite(self):
        self.add("fresh")
        with closing(sqlite3.connect(self.db)) as c, c:
            before=c.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        result=audit(self.db)
        with closing(sqlite3.connect(self.db)) as c, c:
            after=c.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        self.assertEqual(before,after)
        self.assertEqual(result["sql_mode"],"mode=ro/query_only=ON/consistent-read-transaction")

    def test_missing_file_no_sqlite_created(self):
        missing=self.db.parent/"missing.db"
        with self.assertRaisesRegex(LegacyConversationAuditError,"existing"):
            audit(missing)
        self.assertFalse(missing.exists())

if __name__=="__main__":
    unittest.main()

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cyber_lion.app_coordination.conversation_schema import (
    EXPECTED_TABLES,
    SCHEMA_DIGEST,
    SCHEMA_ID,
    ConversationSchemaMigrationInterrupted,
    migrate_conversation_schema,
    verify_conversation_schema,
)
from tools.lion_local_intelligence_runtime import ThreadStore


def _conn(path=":memory:"):
    c = sqlite3.connect(path)
    c.execute("PRAGMA foreign_keys=ON")
    return c


def _legacy_schema(c):
    c.executescript(
        """
        CREATE TABLE threads(thread_id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL);
        CREATE TABLE messages(message_id TEXT PRIMARY KEY,thread_id TEXT NOT NULL,seq INTEGER NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,created_at REAL NOT NULL,meta_json TEXT NOT NULL,FOREIGN KEY(thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE,UNIQUE(thread_id,seq));
        CREATE TABLE thread_bindings(thread_id TEXT PRIMARY KEY,mission_id TEXT,target TEXT NOT NULL,channel TEXT NOT NULL,binding_revision INTEGER NOT NULL,binding_state TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL,FOREIGN KEY(thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE);
        CREATE TABLE thread_model_routes(thread_id TEXT PRIMARY KEY,model_route TEXT NOT NULL,route_revision INTEGER NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL,FOREIGN KEY(thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE);
        """
    )


def _seed_conversation(c, cid="conv-1", epoch=1, mission="M1", provider="LOCAL", session="session-local-1"):
    t = 100.0
    digest = "a" * 64
    c.execute("INSERT INTO conversations VALUES(?,?,?,?,?)", (cid, "T", "BOUND" if mission else "UNBOUND", t, t))
    c.execute(
        "INSERT INTO conversation_lineage VALUES(?,?,?,?,?)",
        (cid, None, "CREATE", t, "{}"),
    )
    if mission:
        c.execute(
            "INSERT INTO conversation_bindings VALUES(?,?,?,?,?,?,?,?)",
            (cid, epoch, mission, "BOUND", digest, t, None, "{}"),
        )
    else:
        c.execute(
            "INSERT INTO conversation_bindings VALUES(?,?,?,?,?,?,?,?)",
            (cid, epoch, None, "UNBOUND", digest, None, None, "{}"),
        )
    c.execute(
        "INSERT INTO conversation_provider_lanes VALUES(?,?,?,?,?,?,?,?,?)",
        (cid, epoch, "lane-1", provider, session, "ACTIVE", digest, t, t),
    )


class R24ConversationSchemaMigrationTests(unittest.TestCase):
    def test_clean_database_migration_is_forward_verifiable(self):
        c = _conn()
        receipt = migrate_conversation_schema(c, now_fn=lambda: 123.0)
        self.assertEqual(receipt["schema"], SCHEMA_ID)
        self.assertEqual(receipt["schema_digest"], SCHEMA_DIGEST)
        self.assertEqual(set(receipt["tables"]), EXPECTED_TABLES)
        self.assertEqual(receipt["foreign_key_check"], "PASS")
        self.assertEqual(receipt["routing_switch"], "NONE")
        self.assertEqual(receipt["backfill"], "NONE")

    def test_populated_legacy_database_is_byte_semantically_preserved(self):
        c = _conn()
        _legacy_schema(c)
        c.execute("INSERT INTO threads VALUES('t1','legacy',1.0,2.0)")
        c.execute("INSERT INTO messages VALUES('m1','t1',1,'user','hello',1.5,'{}')")
        c.execute("INSERT INTO thread_bindings VALUES('t1','M1','mission:M1','LION_BUS',3,'MISSION_BOUND',1.0,2.0)")
        c.execute("INSERT INTO thread_model_routes VALUES('t1','SAAS',4,1.0,2.0)")
        before = {
            name: [tuple(x) for x in c.execute("SELECT * FROM " + name)]
            for name in ("threads", "messages", "thread_bindings", "thread_model_routes")
        }
        migrate_conversation_schema(c, now_fn=lambda: 123.0)
        after = {
            name: [tuple(x) for x in c.execute("SELECT * FROM " + name)]
            for name in ("threads", "messages", "thread_bindings", "thread_model_routes")
        }
        self.assertEqual(before, after)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 0)

    def test_migration_twice_is_idempotent_and_receipt_is_stable(self):
        c = _conn()
        first = migrate_conversation_schema(c, now_fn=lambda: 123.0)
        second = migrate_conversation_schema(c, now_fn=lambda: 999.0)
        self.assertEqual(first, second)
        self.assertEqual(
            c.execute("SELECT COUNT(*) FROM conversation_schema_migrations").fetchone()[0],
            1,
        )
        self.assertEqual(
            c.execute("SELECT applied_at FROM conversation_schema_migrations").fetchone()[0],
            123.0,
        )

    def test_interrupted_migration_rolls_back_without_partial_schema(self):
        c = _conn()
        with self.assertRaises(ConversationSchemaMigrationInterrupted):
            migrate_conversation_schema(c, _fail_after_statement=5)
        present = {
            row[0]
            for row in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'conversation%'"
            )
        }
        self.assertEqual(present, set())

    def test_outer_transaction_rollback_removes_successful_additive_migration(self):
        c = _conn()
        c.execute("BEGIN")
        migrate_conversation_schema(c, now_fn=lambda: 123.0)
        self.assertIn(
            "conversations",
            {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")},
        )
        c.execute("ROLLBACK")
        self.assertNotIn(
            "conversations",
            {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")},
        )

    def test_uniqueness_prevents_provider_session_and_external_thread_reuse(self):
        c = _conn()
        migrate_conversation_schema(c)
        _seed_conversation(c, "conv-a", session="provider-session-1")
        _seed_conversation(c, "conv-b", session="provider-session-2")
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO conversation_provider_lanes VALUES(?,?,?,?,?,?,?,?,?)",
                ("conv-b", 1, "lane-2", "LOCAL", "provider-session-1", "ACTIVE", "a"*64, 100.0, 100.0),
            )
        c.execute(
            "INSERT INTO conversation_external_bridges VALUES(?,?,?,?,?,?,?,?)",
            ("bridge-a", "conv-a", "native-thread-1", "CHATGPT_SAAS", 100.0, "{}", "a"*64, "NONE"),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO conversation_external_bridges VALUES(?,?,?,?,?,?,?,?)",
                ("bridge-b", "conv-b", "native-thread-1", "CHATGPT_SAAS", 100.0, "{}", "a"*64, "NONE"),
            )

    def test_foreign_keys_and_binding_invariants_fail_closed(self):
        c = _conn()
        migrate_conversation_schema(c)
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO conversation_bindings VALUES(?,?,?,?,?,?,?,?)",
                ("missing", 1, "M1", "BOUND", "a"*64, 100.0, None, "{}"),
            )
        c.execute("INSERT INTO conversations VALUES('conv-x','T','UNBOUND',1.0,1.0)")
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO conversation_bindings VALUES(?,?,?,?,?,?,?,?)",
                ("conv-x", 1, None, "BOUND", "a"*64, 100.0, None, "{}"),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO conversation_bindings VALUES(?,?,?,?,?,?,?,?)",
                ("conv-x", 1, "M1", "BOUND", "not-a-digest", 100.0, None, "{}"),
            )

    def test_legacy_thread_runtime_still_operates_without_implicit_backfill_or_cutover(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "threads.db"
            store = ThreadStore(path)
            created = store("create", {"title": "legacy"})
            store("append_pair", {"thread_id": created["thread_id"], "user": "u", "assistant": "a"})
            got = store("get", {"thread_id": created["thread_id"]})
            self.assertEqual([m["role"] for m in got["messages"]], ["user", "assistant"])
            c = sqlite3.connect(path)
            try:
                self.assertEqual(c.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 0)
                self.assertEqual(c.execute("SELECT COUNT(*) FROM conversation_schema_migrations").fetchone()[0], 1)
                verify_conversation_schema(c)
            finally:
                c.close()


if __name__ == "__main__":
    unittest.main()

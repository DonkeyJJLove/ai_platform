"""Additive R24 conversation-domain schema migration.

Phase 2 deliberately creates only dormant schema.  It does not route traffic,
backfill legacy threads, create conversations, or change runtime behavior.
"""
from __future__ import annotations

from hashlib import sha256
import sqlite3
import time
from typing import Callable

SCHEMA_VERSION = 1
SCHEMA_ID = "lion.r24.conversation-schema/v1"

_HEX64 = "length({0})=64 AND {0} NOT GLOB '*[^0-9a-f]*'"

DDL = (
    """
    CREATE TABLE IF NOT EXISTS conversation_schema_migrations(
      version INTEGER PRIMARY KEY,
      schema_id TEXT NOT NULL,
      schema_digest TEXT NOT NULL,
      applied_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations(
      conversation_id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      state TEXT NOT NULL CHECK(state IN ('UNBOUND','BOUND','FROZEN','MIGRATED')),
      created_at REAL NOT NULL,
      updated_at REAL NOT NULL,
      CHECK(length(conversation_id) BETWEEN 1 AND 256),
      CHECK(updated_at >= created_at)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_lineage(
      conversation_id TEXT PRIMARY KEY,
      predecessor_conversation_id TEXT,
      transition TEXT NOT NULL CHECK(transition IN ('CREATE','BIND','DETACH','MIGRATE')),
      created_at REAL NOT NULL,
      provenance_json TEXT NOT NULL,
      FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id) ON DELETE RESTRICT,
      FOREIGN KEY(predecessor_conversation_id) REFERENCES conversations(conversation_id) ON DELETE RESTRICT,
      CHECK(predecessor_conversation_id IS NULL OR predecessor_conversation_id != conversation_id)
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS conversation_bindings(
      conversation_id TEXT NOT NULL,
      binding_epoch INTEGER NOT NULL CHECK(binding_epoch >= 1),
      mission_id TEXT,
      state TEXT NOT NULL CHECK(state IN ('UNBOUND','BOUND','FROZEN')),
      context_digest TEXT NOT NULL CHECK({_HEX64.format('context_digest')}),
      bound_at REAL,
      detached_at REAL,
      provenance_json TEXT NOT NULL,
      PRIMARY KEY(conversation_id,binding_epoch),
      FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id) ON DELETE RESTRICT,
      CHECK(
        (state='BOUND' AND mission_id IS NOT NULL AND bound_at IS NOT NULL AND detached_at IS NULL)
        OR (state='UNBOUND' AND mission_id IS NULL AND detached_at IS NULL)
        OR (state='FROZEN' AND detached_at IS NOT NULL)
      )
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS conversation_provider_lanes(
      conversation_id TEXT NOT NULL,
      binding_epoch INTEGER NOT NULL,
      lane_id TEXT NOT NULL,
      provider TEXT NOT NULL CHECK(provider IN ('LOCAL','SAAS','DETERMINISTIC')),
      provider_session_ref TEXT,
      state TEXT NOT NULL CHECK(state IN ('READY','ACTIVE','WAITING','CLOSED','FAILED')),
      context_digest TEXT NOT NULL CHECK({_HEX64.format('context_digest')}),
      created_at REAL NOT NULL,
      updated_at REAL NOT NULL,
      PRIMARY KEY(conversation_id,binding_epoch,lane_id),
      FOREIGN KEY(conversation_id,binding_epoch)
        REFERENCES conversation_bindings(conversation_id,binding_epoch) ON DELETE RESTRICT,
      UNIQUE(provider,provider_session_ref),
      CHECK(updated_at >= created_at)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_threads(
      thread_map_id TEXT PRIMARY KEY,
      conversation_id TEXT NOT NULL,
      binding_epoch INTEGER NOT NULL,
      lane_id TEXT NOT NULL,
      thread_ref TEXT NOT NULL,
      thread_system TEXT NOT NULL,
      state TEXT NOT NULL CHECK(state IN ('ACTIVE','FROZEN','CLOSED')),
      created_at REAL NOT NULL,
      provenance_json TEXT NOT NULL,
      FOREIGN KEY(conversation_id,binding_epoch,lane_id)
        REFERENCES conversation_provider_lanes(conversation_id,binding_epoch,lane_id) ON DELETE RESTRICT,
      UNIQUE(thread_system,thread_ref)
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS conversation_messages(
      message_id TEXT PRIMARY KEY,
      conversation_id TEXT NOT NULL,
      binding_epoch INTEGER NOT NULL,
      lane_id TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('USER','ASSISTANT','SYSTEM','TOOL')),
      content TEXT NOT NULL,
      causation_id TEXT NOT NULL,
      correlation_id TEXT NOT NULL,
      context_digest TEXT NOT NULL CHECK({_HEX64.format('context_digest')}),
      created_at REAL NOT NULL,
      metadata_json TEXT NOT NULL,
      FOREIGN KEY(conversation_id,binding_epoch,lane_id)
        REFERENCES conversation_provider_lanes(conversation_id,binding_epoch,lane_id) ON DELETE RESTRICT
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS conversation_delivery_events(
      event_id TEXT PRIMARY KEY,
      conversation_id TEXT NOT NULL,
      binding_epoch INTEGER NOT NULL,
      lane_id TEXT NOT NULL,
      message_id TEXT NOT NULL,
      participant_id TEXT,
      causation_id TEXT NOT NULL,
      correlation_id TEXT NOT NULL,
      context_digest TEXT NOT NULL CHECK({_HEX64.format('context_digest')}),
      sequence INTEGER NOT NULL CHECK(sequence >= 1),
      state TEXT NOT NULL CHECK(state IN ('PERSISTED','DISPATCHED','DELIVERED','APPLIED','DENIED','FAILED','SUPERSEDED')),
      response_message_id TEXT,
      created_at REAL NOT NULL,
      FOREIGN KEY(conversation_id,binding_epoch,lane_id)
        REFERENCES conversation_provider_lanes(conversation_id,binding_epoch,lane_id) ON DELETE RESTRICT,
      FOREIGN KEY(message_id) REFERENCES conversation_messages(message_id) ON DELETE RESTRICT,
      UNIQUE(conversation_id,binding_epoch,lane_id,sequence)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_delivery_cursors(
      conversation_id TEXT NOT NULL,
      binding_epoch INTEGER NOT NULL,
      consumer_id TEXT NOT NULL,
      last_sequence INTEGER NOT NULL CHECK(last_sequence >= 0),
      updated_at REAL NOT NULL,
      PRIMARY KEY(conversation_id,binding_epoch,consumer_id),
      FOREIGN KEY(conversation_id,binding_epoch)
        REFERENCES conversation_bindings(conversation_id,binding_epoch) ON DELETE RESTRICT
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS conversation_external_bridges(
      bridge_id TEXT PRIMARY KEY,
      conversation_id TEXT NOT NULL,
      external_thread_ref TEXT NOT NULL,
      external_system TEXT NOT NULL,
      created_at REAL NOT NULL,
      provenance_json TEXT NOT NULL,
      context_snapshot_digest TEXT NOT NULL CHECK({_HEX64.format('context_snapshot_digest')}),
      authority_effect TEXT NOT NULL CHECK(authority_effect='NONE'),
      FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id) ON DELETE RESTRICT,
      UNIQUE(external_system,external_thread_ref)
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS conversation_migration_provenance(
      migration_version INTEGER NOT NULL,
      mission_id TEXT,
      conversation_id TEXT NOT NULL,
      source_digest TEXT NOT NULL CHECK({_HEX64.format('source_digest')}),
      history_classification TEXT NOT NULL CHECK(history_classification IN ('CURRENT','HISTORICAL','SUPERSEDED','LEGACY_REVIEW_REQUIRED')),
      created_at REAL NOT NULL,
      details_json TEXT NOT NULL,
      PRIMARY KEY(migration_version,source_digest,conversation_id),
      FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id) ON DELETE RESTRICT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_conversation_bindings_mission ON conversation_bindings(mission_id,state)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_messages_lane_created ON conversation_messages(conversation_id,binding_epoch,lane_id,created_at,message_id)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_delivery_state ON conversation_delivery_events(state,conversation_id,binding_epoch,lane_id,sequence)",
    "CREATE INDEX IF NOT EXISTS idx_conversation_lineage_predecessor ON conversation_lineage(predecessor_conversation_id)",
)

SCHEMA_DIGEST = sha256(
    (SCHEMA_ID + "\n" + "\n".join(" ".join(x.split()) for x in DDL)).encode("utf-8")
).hexdigest()

EXPECTED_TABLES = frozenset({
    "conversation_schema_migrations",
    "conversations",
    "conversation_lineage",
    "conversation_bindings",
    "conversation_provider_lanes",
    "conversation_threads",
    "conversation_messages",
    "conversation_delivery_events",
    "conversation_delivery_cursors",
    "conversation_external_bridges",
    "conversation_migration_provenance",
})


class ConversationSchemaMigrationInterrupted(RuntimeError):
    pass


def migrate_conversation_schema(
    conn: sqlite3.Connection,
    *,
    now_fn: Callable[[], float] = time.time,
    _fail_after_statement: int | None = None,
) -> dict:
    """Apply the dormant schema atomically and idempotently.

    The private failure hook exists only so the migration's rollback behavior can
    be deterministically falsified by tests.  No data is backfilled here.
    """
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("SAVEPOINT lion_r24_conversation_schema_v1")
    try:
        # Keep each mutating SQL statement literal at its execution site.  This
        # makes the consequential-effect inventory exact instead of hiding the
        # migration behind dynamic SQL.
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_schema_migrations(
          version INTEGER PRIMARY KEY,
          schema_id TEXT NOT NULL,
          schema_digest TEXT NOT NULL,
          applied_at REAL NOT NULL
        )
        """)
        if _fail_after_statement == 1: raise ConversationSchemaMigrationInterrupted("interrupted after statement 1")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations(
          conversation_id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          state TEXT NOT NULL CHECK(state IN ('UNBOUND','BOUND','FROZEN','MIGRATED')),
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL,
          CHECK(length(conversation_id) BETWEEN 1 AND 256),
          CHECK(updated_at >= created_at)
        )
        """)
        if _fail_after_statement == 2: raise ConversationSchemaMigrationInterrupted("interrupted after statement 2")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_lineage(
          conversation_id TEXT PRIMARY KEY,
          predecessor_conversation_id TEXT,
          transition TEXT NOT NULL CHECK(transition IN ('CREATE','BIND','DETACH','MIGRATE')),
          created_at REAL NOT NULL,
          provenance_json TEXT NOT NULL,
          FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id) ON DELETE RESTRICT,
          FOREIGN KEY(predecessor_conversation_id) REFERENCES conversations(conversation_id) ON DELETE RESTRICT,
          CHECK(predecessor_conversation_id IS NULL OR predecessor_conversation_id != conversation_id)
        )
        """)
        if _fail_after_statement == 3: raise ConversationSchemaMigrationInterrupted("interrupted after statement 3")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_bindings(
          conversation_id TEXT NOT NULL,
          binding_epoch INTEGER NOT NULL CHECK(binding_epoch >= 1),
          mission_id TEXT,
          state TEXT NOT NULL CHECK(state IN ('UNBOUND','BOUND','FROZEN')),
          context_digest TEXT NOT NULL CHECK(length(context_digest)=64 AND context_digest NOT GLOB '*[^0-9a-f]*'),
          bound_at REAL,
          detached_at REAL,
          provenance_json TEXT NOT NULL,
          PRIMARY KEY(conversation_id,binding_epoch),
          FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id) ON DELETE RESTRICT,
          CHECK(
            (state='BOUND' AND mission_id IS NOT NULL AND bound_at IS NOT NULL AND detached_at IS NULL)
            OR (state='UNBOUND' AND mission_id IS NULL AND detached_at IS NULL)
            OR (state='FROZEN' AND detached_at IS NOT NULL)
          )
        )
        """)
        if _fail_after_statement == 4: raise ConversationSchemaMigrationInterrupted("interrupted after statement 4")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_provider_lanes(
          conversation_id TEXT NOT NULL,
          binding_epoch INTEGER NOT NULL,
          lane_id TEXT NOT NULL,
          provider TEXT NOT NULL CHECK(provider IN ('LOCAL','SAAS','DETERMINISTIC')),
          provider_session_ref TEXT,
          state TEXT NOT NULL CHECK(state IN ('READY','ACTIVE','WAITING','CLOSED','FAILED')),
          context_digest TEXT NOT NULL CHECK(length(context_digest)=64 AND context_digest NOT GLOB '*[^0-9a-f]*'),
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL,
          PRIMARY KEY(conversation_id,binding_epoch,lane_id),
          FOREIGN KEY(conversation_id,binding_epoch)
            REFERENCES conversation_bindings(conversation_id,binding_epoch) ON DELETE RESTRICT,
          UNIQUE(provider,provider_session_ref),
          CHECK(updated_at >= created_at)
        )
        """)
        if _fail_after_statement == 5: raise ConversationSchemaMigrationInterrupted("interrupted after statement 5")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_threads(
          thread_map_id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL,
          binding_epoch INTEGER NOT NULL,
          lane_id TEXT NOT NULL,
          thread_ref TEXT NOT NULL,
          thread_system TEXT NOT NULL,
          state TEXT NOT NULL CHECK(state IN ('ACTIVE','FROZEN','CLOSED')),
          created_at REAL NOT NULL,
          provenance_json TEXT NOT NULL,
          FOREIGN KEY(conversation_id,binding_epoch,lane_id)
            REFERENCES conversation_provider_lanes(conversation_id,binding_epoch,lane_id) ON DELETE RESTRICT,
          UNIQUE(thread_system,thread_ref)
        )
        """)
        if _fail_after_statement == 6: raise ConversationSchemaMigrationInterrupted("interrupted after statement 6")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_messages(
          message_id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL,
          binding_epoch INTEGER NOT NULL,
          lane_id TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('USER','ASSISTANT','SYSTEM','TOOL')),
          content TEXT NOT NULL,
          causation_id TEXT NOT NULL,
          correlation_id TEXT NOT NULL,
          context_digest TEXT NOT NULL CHECK(length(context_digest)=64 AND context_digest NOT GLOB '*[^0-9a-f]*'),
          created_at REAL NOT NULL,
          metadata_json TEXT NOT NULL,
          FOREIGN KEY(conversation_id,binding_epoch,lane_id)
            REFERENCES conversation_provider_lanes(conversation_id,binding_epoch,lane_id) ON DELETE RESTRICT
        )
        """)
        if _fail_after_statement == 7: raise ConversationSchemaMigrationInterrupted("interrupted after statement 7")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_delivery_events(
          event_id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL,
          binding_epoch INTEGER NOT NULL,
          lane_id TEXT NOT NULL,
          message_id TEXT NOT NULL,
          participant_id TEXT,
          causation_id TEXT NOT NULL,
          correlation_id TEXT NOT NULL,
          context_digest TEXT NOT NULL CHECK(length(context_digest)=64 AND context_digest NOT GLOB '*[^0-9a-f]*'),
          sequence INTEGER NOT NULL CHECK(sequence >= 1),
          state TEXT NOT NULL CHECK(state IN ('PERSISTED','DISPATCHED','DELIVERED','APPLIED','DENIED','FAILED','SUPERSEDED')),
          response_message_id TEXT,
          created_at REAL NOT NULL,
          FOREIGN KEY(conversation_id,binding_epoch,lane_id)
            REFERENCES conversation_provider_lanes(conversation_id,binding_epoch,lane_id) ON DELETE RESTRICT,
          FOREIGN KEY(message_id) REFERENCES conversation_messages(message_id) ON DELETE RESTRICT,
          UNIQUE(conversation_id,binding_epoch,lane_id,sequence)
        )
        """)
        if _fail_after_statement == 8: raise ConversationSchemaMigrationInterrupted("interrupted after statement 8")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_delivery_cursors(
          conversation_id TEXT NOT NULL,
          binding_epoch INTEGER NOT NULL,
          consumer_id TEXT NOT NULL,
          last_sequence INTEGER NOT NULL CHECK(last_sequence >= 0),
          updated_at REAL NOT NULL,
          PRIMARY KEY(conversation_id,binding_epoch,consumer_id),
          FOREIGN KEY(conversation_id,binding_epoch)
            REFERENCES conversation_bindings(conversation_id,binding_epoch) ON DELETE RESTRICT
        )
        """)
        if _fail_after_statement == 9: raise ConversationSchemaMigrationInterrupted("interrupted after statement 9")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_external_bridges(
          bridge_id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL,
          external_thread_ref TEXT NOT NULL,
          external_system TEXT NOT NULL,
          created_at REAL NOT NULL,
          provenance_json TEXT NOT NULL,
          context_snapshot_digest TEXT NOT NULL CHECK(length(context_snapshot_digest)=64 AND context_snapshot_digest NOT GLOB '*[^0-9a-f]*'),
          authority_effect TEXT NOT NULL CHECK(authority_effect='NONE'),
          FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id) ON DELETE RESTRICT,
          UNIQUE(external_system,external_thread_ref)
        )
        """)
        if _fail_after_statement == 10: raise ConversationSchemaMigrationInterrupted("interrupted after statement 10")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_migration_provenance(
          migration_version INTEGER NOT NULL,
          mission_id TEXT,
          conversation_id TEXT NOT NULL,
          source_digest TEXT NOT NULL CHECK(length(source_digest)=64 AND source_digest NOT GLOB '*[^0-9a-f]*'),
          history_classification TEXT NOT NULL CHECK(history_classification IN ('CURRENT','HISTORICAL','SUPERSEDED','LEGACY_REVIEW_REQUIRED')),
          created_at REAL NOT NULL,
          details_json TEXT NOT NULL,
          PRIMARY KEY(migration_version,source_digest,conversation_id),
          FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id) ON DELETE RESTRICT
        )
        """)
        if _fail_after_statement == 11: raise ConversationSchemaMigrationInterrupted("interrupted after statement 11")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversation_bindings_mission ON conversation_bindings(mission_id,state)")
        if _fail_after_statement == 12: raise ConversationSchemaMigrationInterrupted("interrupted after statement 12")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversation_messages_lane_created ON conversation_messages(conversation_id,binding_epoch,lane_id,created_at,message_id)")
        if _fail_after_statement == 13: raise ConversationSchemaMigrationInterrupted("interrupted after statement 13")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversation_delivery_state ON conversation_delivery_events(state,conversation_id,binding_epoch,lane_id,sequence)")
        if _fail_after_statement == 14: raise ConversationSchemaMigrationInterrupted("interrupted after statement 14")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversation_lineage_predecessor ON conversation_lineage(predecessor_conversation_id)")
        if _fail_after_statement == 15: raise ConversationSchemaMigrationInterrupted("interrupted after statement 15")
        conn.execute(
            "INSERT OR IGNORE INTO conversation_schema_migrations(version,schema_id,schema_digest,applied_at) VALUES(?,?,?,?)",
            (SCHEMA_VERSION, SCHEMA_ID, SCHEMA_DIGEST, float(now_fn())),
        )
        row = conn.execute(
            "SELECT schema_id,schema_digest FROM conversation_schema_migrations WHERE version=?",
            (SCHEMA_VERSION,),
        ).fetchone()
        if row is None or row[0] != SCHEMA_ID or row[1] != SCHEMA_DIGEST:
            raise RuntimeError("conversation schema migration identity mismatch")
        conn.execute("RELEASE SAVEPOINT lion_r24_conversation_schema_v1")
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT lion_r24_conversation_schema_v1")
        conn.execute("RELEASE SAVEPOINT lion_r24_conversation_schema_v1")
        raise
    return verify_conversation_schema(conn)


def verify_conversation_schema(conn: sqlite3.Connection) -> dict:
    present = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'conversation%'"
        )
    }
    missing = sorted(EXPECTED_TABLES - present)
    if missing:
        raise RuntimeError("conversation schema tables missing:" + ",".join(missing))
    row = conn.execute(
        "SELECT schema_id,schema_digest,applied_at FROM conversation_schema_migrations WHERE version=?",
        (SCHEMA_VERSION,),
    ).fetchone()
    if row is None or row[0] != SCHEMA_ID or row[1] != SCHEMA_DIGEST:
        raise RuntimeError("conversation schema migration receipt mismatch")
    fk_errors = list(conn.execute("PRAGMA foreign_key_check"))
    if fk_errors:
        raise RuntimeError("conversation schema foreign key check failed")
    return {
        "schema": SCHEMA_ID,
        "version": SCHEMA_VERSION,
        "schema_digest": SCHEMA_DIGEST,
        "applied_at": row[2],
        "table_count": len(EXPECTED_TABLES),
        "tables": sorted(EXPECTED_TABLES),
        "foreign_key_check": "PASS",
        "routing_switch": "NONE",
        "backfill": "NONE",
        "authority_effect": "NONE",
    }

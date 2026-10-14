"""Bounded read-only legacy canonical conversation reconciliation candidates.

Reuses the ORIGINAL LION canonical SQLite tables. Classifies only; never
creates, deletes, binds, retries, rotates, clears or reconstructs a SaaS turn.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sqlite3

SCHEMA = "lion.canonical-conversation-legacy-eligibility/v1"
REQUIRED = frozenset({
    "conversations", "conversation_bindings", "conversation_provider_lanes",
    "conversation_external_bridges", "conversation_delivery_events",
})
LIMIT = 5000

class LegacyConversationAuditError(RuntimeError):
    pass

def audit(path: str | Path) -> dict:
    db_path = Path(path)
    if not db_path.is_absolute() or db_path.is_symlink() or not db_path.is_file():
        raise LegacyConversationAuditError("exact existing direct canonical SQLite required")
    if db_path.resolve(strict=True) != db_path:
        raise LegacyConversationAuditError("canonical SQLite path indirection denied")
    conn = None
    try:
        # mode=ro ensures this code cannot update, migrate or create the DB.
        conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=3)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        if conn.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise LegacyConversationAuditError("query-only SQLite unavailable")
        conn.execute("BEGIN")
        tables = frozenset(row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ))
        if not REQUIRED.issubset(tables):
            raise LegacyConversationAuditError("canonical conversation tables incomplete")
        count = int(conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0])
        if count > LIMIT:
            raise LegacyConversationAuditError("conversation audit bound exceeded")
        rows = conn.execute("""
            SELECT c.conversation_id,c.state AS canonical_state,
                   b.state AS binding_state,b.binding_epoch,b.mission_id,
                   (SELECT COUNT(*) FROM conversation_provider_lanes l
                    WHERE l.conversation_id=c.conversation_id
                      AND l.provider='SAAS') AS historical_saas_lanes,
                   (SELECT COUNT(*) FROM conversation_external_bridges e
                    WHERE e.conversation_id=c.conversation_id
                      AND e.external_system='CHATGPT_SAAS') AS recorded_bridges,
                   (SELECT COUNT(*) FROM conversation_delivery_events d
                    JOIN conversation_provider_lanes l
                      ON l.conversation_id=d.conversation_id
                     AND l.binding_epoch=d.binding_epoch
                     AND l.lane_id=d.lane_id
                    WHERE d.conversation_id=c.conversation_id
                      AND l.provider='SAAS' AND d.state='PERSISTED'
                   ) AS persisted_saas_events
            FROM conversations c
            LEFT JOIN conversation_bindings b
              ON b.conversation_id=c.conversation_id
             AND b.binding_epoch=(SELECT MAX(x.binding_epoch)
                 FROM conversation_bindings x
                 WHERE x.conversation_id=c.conversation_id)
            ORDER BY c.conversation_id
        """).fetchall()
        if len(rows) != count:
            raise LegacyConversationAuditError("canonical conversation census mismatch")
        out = []
        for row in rows:
            r = dict(row)
            if not r["conversation_id"] or r["binding_epoch"] is None:
                classification = "INCOMPLETE_CANONICAL_BINDING_HOLD"
            elif r["canonical_state"] == "FROZEN" or r["binding_state"] == "FROZEN":
                classification = "FROZEN_HISTORICAL_PRESERVE"
            elif r["canonical_state"] != r["binding_state"] or r["canonical_state"] not in {"BOUND", "UNBOUND"}:
                classification = "CANONICAL_STATE_CONFLICT_HOLD"
            elif r["recorded_bridges"] > 0:
                classification = "BRIDGE_RECORD_REVALIDATION_REQUIRED"
            elif r["historical_saas_lanes"] > 0 or r["persisted_saas_events"] > 0:
                classification = "LEGACY_SAAS_CLAIM_RECONCILIATION_REQUIRED"
            else:
                classification = "NEW_EXPLICIT_OPERATOR_LINK_CANDIDATE"
            out.append({
                "conversation_id": r["conversation_id"],
                "mission_scope": "MISSION" if r["mission_id"] else "AD_HOC",
                "binding_epoch": r["binding_epoch"],
                "canonical_state": r["canonical_state"],
                "recorded_bridge_count": r["recorded_bridges"],
                "historical_saas_lane_count": r["historical_saas_lanes"],
                "persisted_saas_event_count": r["persisted_saas_events"],
                "classification": classification,
                "ready_to_send": False,
                "authorized_to_bind": False,
                "authorized_to_delete": False,
            })
        counts = Counter(row["classification"] for row in out)
        conn.rollback()
        return {
            "schema": SCHEMA,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "ORIGINAL_CANONICAL_SQLITE_READ_ONLY",
            "sql_mode": "mode=ro/query_only=ON/consistent-read-transaction",
            "conversation_count": len(out),
            "classification_counts": dict(sorted(counts.items())),
            "rows": out,
            "authority_effect": "NONE",
            "effects": [],
            "next": "Review original broker request/currentness and concrete project-thread proof; never bulk migrate",
        }
    except sqlite3.Error as e:
        raise LegacyConversationAuditError("canonical SQLite read failed") from e
    finally:
        if conn is not None:
            conn.close()

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = audit(args.database)
    data = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        dest = args.output.resolve(strict=False)
        if dest == args.database.resolve(strict=True):
            raise LegacyConversationAuditError("cannot write to canonical DB")
        dest.write_text(data, encoding="utf-8")
    else:
        print(data, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

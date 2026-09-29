"""R24 active-mission conversation backfill.

Phase 7 is dry-run first.  This module keeps migration identity deterministic,
never reinterprets protocol events as chat messages, and requires an explicit
approved-mission allowlist before any canonical conversation row is created.
"""
from __future__ import annotations

from hashlib import sha256
import json
import sqlite3
import time
import uuid
from typing import Any, Iterable, Mapping

from .conversation_domain import create_conversation, get_conversation

MIGRATION_VERSION = "r24-conversation-backfill-v1"
_NAMESPACE = uuid.UUID("266486de-ecaa-46b1-92f8-f55d489151a4")
ACTIVE_TRAVERSABLE_STATES = frozenset({"RUNNING", "AUTHORIZED", "REGISTERED", "RECORDED_RUNNING"})
TASK_HISTORY_CLASSES = frozenset({"EXACT_ATTRIBUTABLE", "AMBIGUOUS", "ABSENT"})


class ConversationBackfillError(ValueError):
    pass


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canon(value).encode("utf-8")).hexdigest()


def deterministic_conversation_id(mission_id: str, migration_version: str = MIGRATION_VERSION) -> str:
    mission_id = str(mission_id or "").strip()
    if not mission_id:
        raise ConversationBackfillError("mission_id")
    return "conv-mig-" + uuid.uuid5(_NAMESPACE, migration_version + "|" + mission_id).hex


def _safe_meta(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _legacy_tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def legacy_evidence_for_mission(conn: sqlite3.Connection, mission_id: str) -> dict[str, Any]:
    """Return content-free legacy attribution evidence for one mission."""
    tables = _legacy_tables(conn)
    if not {"threads", "thread_bindings", "messages"}.issubset(tables):
        return {
            "legacy_thread_refs": [],
            "history_classification": "ABSENT",
            "history_copy_policy": "EMPTY_CANONICAL_TRANSCRIPT",
            "legacy_evidence_digest": _digest({"mission_id": mission_id, "legacy_schema": "ABSENT"}),
        }

    routes: dict[str, dict[str, Any]] = {}
    if "thread_model_routes" in tables:
        for row in conn.execute(
            "SELECT thread_id,model_route,route_revision,created_at,updated_at FROM thread_model_routes"
        ):
            routes[str(row[0])] = {
                "model_route": row[1],
                "route_revision": row[2],
                "created_at": row[3],
                "updated_at": row[4],
            }

    refs = []
    exact_all = True
    any_messages = False
    for binding in conn.execute(
        """SELECT b.thread_id,b.mission_id,b.target,b.channel,b.binding_revision,
                  b.binding_state,b.created_at,b.updated_at,t.title,t.created_at,t.updated_at
           FROM thread_bindings b
           JOIN threads t ON t.thread_id=b.thread_id
           WHERE b.mission_id=? ORDER BY b.thread_id""",
        (mission_id,),
    ):
        thread_id = str(binding[0])
        messages = []
        for row in conn.execute(
            """SELECT message_id,seq,role,content,created_at,meta_json
               FROM messages WHERE thread_id=? ORDER BY seq,message_id""",
            (thread_id,),
        ):
            meta = _safe_meta(row[5])
            attributable = (
                meta.get("mission_id") == mission_id
                and meta.get("legacy_history_attribution") == "EXACT"
            )
            exact_all = exact_all and attributable
            any_messages = True
            messages.append({
                "message_id": row[0],
                "seq": row[1],
                "role": row[2],
                "created_at": row[4],
                "content_digest": sha256(str(row[3]).encode("utf-8")).hexdigest(),
                "meta_digest": _digest(meta),
                "exact_attribution": bool(attributable),
            })
        ref = {
            "thread_id": thread_id,
            "title": binding[8],
            "binding": {
                "mission_id": binding[1],
                "target": binding[2],
                "channel": binding[3],
                "binding_revision": binding[4],
                "binding_state": binding[5],
                "created_at": binding[6],
                "updated_at": binding[7],
            },
            "thread_created_at": binding[9],
            "thread_updated_at": binding[10],
            "route": routes.get(thread_id),
            "message_count": len(messages),
            "messages": messages,
        }
        ref["source_digest"] = _digest(ref)
        refs.append(ref)

    if not refs or not any_messages:
        classification = "ABSENT"
        policy = "EMPTY_CANONICAL_TRANSCRIPT"
    elif exact_all:
        classification = "EXACT_ATTRIBUTABLE"
        policy = "EXACT_HISTORY_MAY_BE_IMPORTED_READ_ONLY"
    else:
        classification = "AMBIGUOUS"
        policy = "FORBID_CANONICAL_COPY_ARCHIVE_LINK_ONLY"

    evidence = {
        "mission_id": mission_id,
        "legacy_thread_refs": refs,
        "history_classification": classification,
        "history_copy_policy": policy,
    }
    evidence["legacy_evidence_digest"] = _digest(evidence)
    return evidence


def _mission_identity(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "mission_id": snapshot.get("mission_id"),
        "title": snapshot.get("title"),
        "adapter": snapshot.get("adapter"),
        "spec_digest": snapshot.get("spec_digest"),
        "source_head": snapshot.get("source_head"),
        "source_tree": snapshot.get("source_tree"),
        "created_at": snapshot.get("created_at"),
    }


def _mission_runtime(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "mission_id": snapshot.get("mission_id"),
        "state": snapshot.get("state"),
        "runtime_state": snapshot.get("runtime_state"),
        "material_target": snapshot.get("material_target"),
        "materialized": snapshot.get("materialized"),
        "ready": snapshot.get("ready"),
        "updated_at": snapshot.get("updated_at"),
        "last_error": snapshot.get("last_error"),
    }


def build_mission_dry_run_entry(
    mission_snapshot: Mapping[str, Any],
    legacy_conn: sqlite3.Connection,
    *,
    migration_version: str = MIGRATION_VERSION,
) -> dict[str, Any]:
    mission_id = str(mission_snapshot.get("mission_id") or "").strip()
    state = str(mission_snapshot.get("state") or "").upper()
    if not mission_id:
        raise ConversationBackfillError("mission_id")
    evidence = legacy_evidence_for_mission(legacy_conn, mission_id)
    identity = _mission_identity(mission_snapshot)
    runtime = _mission_runtime(mission_snapshot)
    mission_identity_digest = _digest(identity)
    mission_runtime_digest = _digest(runtime)
    cutover_source_digest = _digest({
        "migration_version": migration_version,
        "mission_identity_digest": mission_identity_digest,
        "legacy_evidence_digest": evidence["legacy_evidence_digest"],
    })
    conversation_id = deterministic_conversation_id(mission_id, migration_version)
    classification = evidence["history_classification"]
    legacy_adapter = str(mission_snapshot.get("adapter") or "").upper().startswith("LEGACY_")
    if state not in ACTIVE_TRAVERSABLE_STATES:
        eligibility = "NOT_ACTIVE_TRAVERSABLE"
    elif legacy_adapter or state == "RECORDED_RUNNING":
        eligibility = "H4_REVIEW_LEGACY_RECORDED_MISSION"
    elif classification == "EXACT_ATTRIBUTABLE":
        eligibility = "H4_ELIGIBLE_EXACT_HISTORY_OPTIONAL"
    elif classification == "AMBIGUOUS":
        eligibility = "H4_ELIGIBLE_EMPTY_CANONICAL_WITH_LEGACY_EVIDENCE_ONLY"
    else:
        eligibility = "H4_ELIGIBLE_EMPTY_CANONICAL"
    rollback_pointer = {
        "kind": "R24_MISSION_BACKFILL_ROLLBACK_POINTER",
        "migration_version": migration_version,
        "mission_id": mission_id,
        "conversation_id": conversation_id,
        "cutover_source_digest": cutover_source_digest,
        "pre_apply_state": "NO_CANONICAL_MUTATION_IN_DRY_RUN",
    }
    return {
        "mission_id": mission_id,
        "mission_state": state,
        "mission_title": mission_snapshot.get("title"),
        "existing_legacy_thread_refs": evidence["legacy_thread_refs"],
        "proposed_conversation_id": conversation_id,
        "proposed_binding_epoch": 1,
        "proposed_binding_state": "BOUND",
        "history_classification": classification,
        "history_copy_policy": evidence["history_copy_policy"],
        "provenance": {
            "migration_version": migration_version,
            "source_systems": ["MISSION_CONTROL", "LEGACY_WINDOWS_THREAD_DB"],
            "authority_effect": "NONE",
            "no_protocol_event_reinterpretation": True,
        },
        "source_digests": {
            "mission_identity_digest": mission_identity_digest,
            "mission_runtime_digest": mission_runtime_digest,
            "legacy_evidence_digest": evidence["legacy_evidence_digest"],
            "cutover_source_digest": cutover_source_digest,
        },
        "cutover_eligibility": eligibility,
        "rollback_pointer": rollback_pointer,
    }


def build_dry_run_manifest(
    mission_snapshots: Iterable[Mapping[str, Any]],
    legacy_conn: sqlite3.Connection,
    *,
    migration_version: str = MIGRATION_VERSION,
    generated_at: str | None = None,
) -> dict[str, Any]:
    entries = [
        build_mission_dry_run_entry(x, legacy_conn, migration_version=migration_version)
        for x in mission_snapshots
        if str(x.get("state") or "").upper() in ACTIVE_TRAVERSABLE_STATES
    ]
    entries.sort(key=lambda x: x["mission_id"])
    manifest_digest = _digest({
        "migration_version": migration_version,
        "entries": entries,
    })
    return {
        "schema": "lion.r24.conversation-migration-dry-run/v1",
        "task_id": "LION-R24-WHOLE-INTEGRATION-CLOSURE-R1",
        "phase": 7,
        "mode": "DRY_RUN",
        "migration_version": migration_version,
        "generated_at": generated_at,
        "mission_count": len(entries),
        "manifest_digest": manifest_digest,
        "active_mission_mutation": "NONE",
        "entries": entries,
        "authority_effect": "NONE",
    }


def _provenance_column_class(task_classification: str) -> str:
    if task_classification == "AMBIGUOUS":
        return "LEGACY_REVIEW_REQUIRED"
    if task_classification in {"EXACT_ATTRIBUTABLE", "ABSENT"}:
        return "CURRENT"
    raise ConversationBackfillError("history_classification")


def apply_mission_entry(
    conn: sqlite3.Connection,
    entry: Mapping[str, Any],
    *,
    approved_mission_ids: set[str],
    now_fn=time.time,
) -> dict[str, Any]:
    """Apply one approved mission atomically.  No legacy message copy is performed."""
    mission_id = str(entry.get("mission_id") or "")
    if mission_id not in approved_mission_ids:
        raise ConversationBackfillError("mission not approved by H4")
    expected_cid = deterministic_conversation_id(mission_id, MIGRATION_VERSION)
    if entry.get("proposed_conversation_id") != expected_cid:
        raise ConversationBackfillError("conversation migration identity drift")
    classification = str(entry.get("history_classification") or "")
    if classification not in TASK_HISTORY_CLASSES:
        raise ConversationBackfillError("history_classification")
    source_digests = entry.get("source_digests") or {}
    source_digest = str(source_digests.get("cutover_source_digest") or "")
    if len(source_digest) != 64:
        raise ConversationBackfillError("cutover source digest")
    context_digest = _digest({
        "migration_version": MIGRATION_VERSION,
        "mission_id": mission_id,
        "cutover_source_digest": source_digest,
    })
    title = str(entry.get("mission_title") or mission_id)[:120]
    conn.execute("SAVEPOINT r24_backfill_one_mission")
    try:
        existing = conn.execute(
            """SELECT source_digest,history_classification,details_json
               FROM conversation_migration_provenance
               WHERE migration_version=? AND mission_id=? AND conversation_id=?
               ORDER BY created_at LIMIT 1""",
            (1, mission_id, expected_cid),
        ).fetchone()
        if existing is not None:
            if existing[0] != source_digest:
                raise ConversationBackfillError("migration source digest conflict")
            out = get_conversation(conn, expected_cid)
            conn.execute("RELEASE SAVEPOINT r24_backfill_one_mission")
            return {
                "mission_id": mission_id,
                "conversation_id": expected_cid,
                "idempotent_replay": True,
                "conversation": out,
                "rollback_pointer": entry.get("rollback_pointer"),
            }

        conversation = create_conversation(conn, {
            "conversation_id": expected_cid,
            "idempotency_key": "migration:" + MIGRATION_VERSION + ":" + mission_id,
            "title": title,
            "mission_id": mission_id,
            "context_digest": context_digest,
            "provenance": {
                "kind": "ACTIVE_MISSION_BACKFILL",
                "migration_version": MIGRATION_VERSION,
                "cutover_source_digest": source_digest,
                "history_classification": classification,
                "history_copy_policy": entry.get("history_copy_policy"),
                "authority_effect": "NONE",
            },
        }, now=float(now_fn()))
        details = {
            "schema": "lion.r24.conversation-migration-provenance/v1",
            "task_history_classification": classification,
            "history_copy_policy": entry.get("history_copy_policy"),
            "legacy_thread_refs": entry.get("existing_legacy_thread_refs") or [],
            "rollback_pointer": entry.get("rollback_pointer"),
            "authority_effect": "NONE",
            "protocol_events_imported_as_chat_messages": False,
        }
        conn.execute(
            """INSERT INTO conversation_migration_provenance(
                 migration_version,mission_id,conversation_id,source_digest,
                 history_classification,created_at,details_json
               ) VALUES(?,?,?,?,?,?,?)""",
            (
                1, mission_id, expected_cid, source_digest,
                _provenance_column_class(classification), float(now_fn()), _canon(details),
            ),
        )
        conn.execute("RELEASE SAVEPOINT r24_backfill_one_mission")
        return {
            "mission_id": mission_id,
            "conversation_id": expected_cid,
            "idempotent_replay": False,
            "conversation": conversation,
            "rollback_pointer": entry.get("rollback_pointer"),
        }
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT r24_backfill_one_mission")
        conn.execute("RELEASE SAVEPOINT r24_backfill_one_mission")
        raise


def apply_manifest(
    conn: sqlite3.Connection,
    manifest: Mapping[str, Any],
    *,
    approved_mission_ids: set[str],
    now_fn=time.time,
) -> dict[str, Any]:
    if manifest.get("mode") != "DRY_RUN":
        raise ConversationBackfillError("manifest mode")
    results = []
    failures = []
    for entry in manifest.get("entries") or []:
        mission_id = str(entry.get("mission_id") or "")
        if mission_id not in approved_mission_ids:
            continue
        try:
            result = apply_mission_entry(
                conn, entry, approved_mission_ids=approved_mission_ids, now_fn=now_fn
            )
            conn.commit()
            results.append(result)
        except Exception as error:
            conn.rollback()
            failures.append({
                "mission_id": mission_id,
                "error_class": type(error).__name__,
                "error": str(error),
            })
            break
    return {
        "applied": results,
        "failures": failures,
        "resume_from_mission_id": failures[0]["mission_id"] if failures else None,
        "authority_effect": "NONE",
    }


def verify_mission_entry(conn: sqlite3.Connection, entry: Mapping[str, Any]) -> dict[str, Any]:
    mission_id = str(entry.get("mission_id") or "")
    cid = deterministic_conversation_id(mission_id, MIGRATION_VERSION)
    conversation = get_conversation(conn, cid)
    binding = conversation.get("current_binding") or {}
    provenance = conn.execute(
        """SELECT source_digest,history_classification,details_json
           FROM conversation_migration_provenance
           WHERE migration_version=? AND mission_id=? AND conversation_id=?""",
        (1, mission_id, cid),
    ).fetchone()
    if provenance is None:
        raise ConversationBackfillError("migration provenance missing")
    if binding.get("mission_id") != mission_id or int(binding.get("binding_epoch") or 0) != 1:
        raise ConversationBackfillError("mission binding verification failed")
    expected_digest = (entry.get("source_digests") or {}).get("cutover_source_digest")
    if provenance[0] != expected_digest:
        raise ConversationBackfillError("source digest verification failed")
    details = _safe_meta(provenance[2])
    if details.get("protocol_events_imported_as_chat_messages") is not False:
        raise ConversationBackfillError("protocol/chat separation verification failed")
    return {
        "mission_id": mission_id,
        "conversation_id": cid,
        "binding_epoch": 1,
        "binding_state": binding.get("state"),
        "history_classification": details.get("task_history_classification"),
        "source_digest": provenance[0],
        "verified": True,
        "authority_effect": "NONE",
    }

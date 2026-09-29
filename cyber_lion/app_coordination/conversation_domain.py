"""R24 conversation domain over the additive schema.

Phase 3 materializes dormant domain/service semantics only. Existing Model Chat UI
and legacy thread routes remain unchanged until a later cutover phase.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
import sqlite3
import time
import uuid
from typing import Any, Mapping

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
REF_RE = re.compile(r"^\S{1,512}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
PROVIDERS = frozenset({"LOCAL", "SAAS", "DETERMINISTIC"})
LANE_STATES = frozenset({"READY", "ACTIVE", "WAITING", "CLOSED", "FAILED"})
_NAMESPACE = uuid.UUID("de1d8d6d-154d-4f8a-bf2a-4afaa88fa93f")


class ConversationDomainError(ValueError):
    pass


class ConversationNotFound(KeyError):
    pass


class ConversationConflict(ConversationDomainError):
    pass


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return sha256(_canon(value).encode("utf-8")).hexdigest()


def _id(value: Any, name: str) -> str:
    value = str(value or "").strip()
    if ID_RE.fullmatch(value) is None:
        raise ConversationDomainError(name)
    return value


def _ref(value: Any, name: str) -> str:
    value = str(value or "").strip()
    if REF_RE.fullmatch(value) is None:
        raise ConversationDomainError(name)
    return value


def _hex64(value: Any, name: str) -> str:
    value = str(value or "")
    if DIGEST_RE.fullmatch(value) is None:
        raise ConversationDomainError(name)
    return value


def _stable(prefix: str, *parts: str) -> str:
    return prefix + uuid.uuid5(_NAMESPACE, "|".join(parts)).hex


def _random(prefix: str) -> str:
    return prefix + uuid.uuid4().hex


def _prov(kind: str, operation_key: str | None, fingerprint: str, supplied: Any) -> str:
    if supplied is None:
        supplied = {}
    if not isinstance(supplied, Mapping):
        raise ConversationDomainError("provenance")
    return _canon({
        "authority_effect": "NONE",
        "kind": kind,
        "operation_key": operation_key,
        "operation_fingerprint": fingerprint,
        "supplied": dict(supplied),
    })


def _prov_load(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except Exception as error:
        raise ConversationConflict("stored provenance invalid") from error
    return parsed if isinstance(parsed, dict) else {}


def _row(conn: sqlite3.Connection, conversation_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM conversations WHERE conversation_id=?", (conversation_id,)
    ).fetchone()
    if row is None:
        raise ConversationNotFound(conversation_id)
    return row


def _binding(conn: sqlite3.Connection, conversation_id: str) -> sqlite3.Row:
    row = conn.execute(
        """SELECT * FROM conversation_bindings
           WHERE conversation_id=? ORDER BY binding_epoch DESC LIMIT 1""",
        (conversation_id,),
    ).fetchone()
    if row is None:
        raise ConversationConflict("conversation binding missing")
    return row


def get_conversation(conn: sqlite3.Connection, conversation_id: str) -> dict[str, Any]:
    conversation_id = _id(conversation_id, "conversation_id")
    base = dict(_row(conn, conversation_id))
    bindings = [
        dict(x) for x in conn.execute(
            "SELECT * FROM conversation_bindings WHERE conversation_id=? ORDER BY binding_epoch",
            (conversation_id,),
        )
    ]
    lanes = [
        dict(x) for x in conn.execute(
            """SELECT * FROM conversation_provider_lanes
               WHERE conversation_id=? ORDER BY binding_epoch,lane_id""",
            (conversation_id,),
        )
    ]
    bridges = [
        dict(x) for x in conn.execute(
            """SELECT * FROM conversation_external_bridges
               WHERE conversation_id=? ORDER BY created_at,bridge_id""",
            (conversation_id,),
        )
    ]
    lineage = conn.execute(
        "SELECT * FROM conversation_lineage WHERE conversation_id=?",
        (conversation_id,),
    ).fetchone()
    successors = [
        x[0] for x in conn.execute(
            """SELECT conversation_id FROM conversation_lineage
               WHERE predecessor_conversation_id=? ORDER BY created_at,conversation_id""",
            (conversation_id,),
        )
    ]
    base.update({
        "bindings": bindings,
        "current_binding": bindings[-1] if bindings else None,
        "lanes": lanes,
        "external_bridges": bridges,
        "lineage": dict(lineage) if lineage else None,
        "successor_conversation_ids": successors,
        "authority_effect": "NONE",
    })
    return base


def list_conversations(
    conn: sqlite3.Connection,
    limit: int = 500,
    mission_id: str | None = None,
) -> dict[str, Any]:
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ConversationDomainError("limit")
    if mission_id is not None:
        mission_id = _id(mission_id, "mission_id")
        ids = [
            x[0] for x in conn.execute(
                """SELECT DISTINCT c.conversation_id
                   FROM conversations c
                   JOIN conversation_bindings b ON b.conversation_id=c.conversation_id
                   WHERE b.mission_id=?
                   ORDER BY c.created_at DESC,c.conversation_id
                   LIMIT ?""",
                (mission_id, limit),
            )
        ]
    else:
        ids = [
            x[0] for x in conn.execute(
                "SELECT conversation_id FROM conversations ORDER BY created_at DESC,conversation_id LIMIT ?",
                (limit,),
            )
        ]
    rows = [get_conversation(conn, cid) for cid in ids]
    return {
        "conversations": rows,
        "mission_id": mission_id,
        "authority_effect": "NONE",
    }


def create_conversation(
    conn: sqlite3.Connection, args: Mapping[str, Any], *, now: float | None = None
) -> dict[str, Any]:
    if not isinstance(args, Mapping):
        raise ConversationDomainError("create schema")
    allowed = {
        "title", "mission_id", "conversation_id", "idempotency_key",
        "context_digest", "provenance",
    }
    if set(args) - allowed:
        raise ConversationDomainError("create schema")
    title = str(args.get("title") or "Nowa rozmowa").strip()[:120] or "Nowa rozmowa"
    mission_id = args.get("mission_id")
    if mission_id is not None:
        mission_id = _id(mission_id, "mission_id")
    idempotency_key = args.get("idempotency_key")
    if idempotency_key is not None:
        idempotency_key = _id(idempotency_key, "idempotency_key")
    explicit = args.get("conversation_id")
    if explicit is not None:
        conversation_id = _id(explicit, "conversation_id")
    elif idempotency_key:
        conversation_id = _stable("conv-", "CREATE", idempotency_key)
    else:
        conversation_id = _random("conv-")
    context_digest = args.get("context_digest")
    if context_digest is None:
        context_digest = _digest({"conversation_id": conversation_id, "initial_context": []})
    context_digest = _hex64(context_digest, "context_digest")
    payload = {
        "conversation_id": conversation_id,
        "title": title,
        "mission_id": mission_id,
        "context_digest": context_digest,
    }
    fingerprint = _digest(payload)
    provenance = _prov("CREATE", idempotency_key, fingerprint, args.get("provenance"))
    t = float(time.time() if now is None else now)
    conn.execute("SAVEPOINT conversation_create")
    try:
        existing = conn.execute(
            "SELECT conversation_id FROM conversations WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        if existing is not None:
            lineage = conn.execute(
                "SELECT provenance_json FROM conversation_lineage WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            stored = _prov_load(lineage[0] if lineage else "{}")
            if stored.get("operation_fingerprint") != fingerprint:
                raise ConversationConflict("create idempotency conflict")
            out = get_conversation(conn, conversation_id)
            out["idempotent_replay"] = True
            conn.execute("RELEASE SAVEPOINT conversation_create")
            return out
        state = "BOUND" if mission_id else "UNBOUND"
        conn.execute(
            "INSERT INTO conversations VALUES(?,?,?,?,?)",
            (conversation_id, title, state, t, t),
        )
        conn.execute(
            "INSERT INTO conversation_lineage VALUES(?,?,?,?,?)",
            (conversation_id, None, "CREATE", t, provenance),
        )
        conn.execute(
            "INSERT INTO conversation_bindings VALUES(?,?,?,?,?,?,?,?)",
            (
                conversation_id, 1, mission_id, state, context_digest,
                t if mission_id else None, None, provenance,
            ),
        )
        out = get_conversation(conn, conversation_id)
        out["idempotent_replay"] = False
        conn.execute("RELEASE SAVEPOINT conversation_create")
        return out
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT conversation_create")
        conn.execute("RELEASE SAVEPOINT conversation_create")
        raise


def transition_conversation(
    conn: sqlite3.Connection,
    conversation_id: str,
    action: str,
    args: Mapping[str, Any],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    conversation_id = _id(conversation_id, "conversation_id")
    action = str(action or "").upper()
    if action not in {"BIND", "DETACH"}:
        raise ConversationDomainError("transition action")
    if not isinstance(args, Mapping):
        raise ConversationDomainError("transition schema")
    if set(args) - {"mission_id", "operation_id", "provenance"}:
        raise ConversationDomainError("transition schema")
    operation_id = _id(args.get("operation_id"), "operation_id")
    mission_id = args.get("mission_id")
    if action == "BIND":
        mission_id = _id(mission_id, "mission_id")
    elif mission_id is not None:
        raise ConversationDomainError("DETACH mission_id forbidden")
    successor_id = _stable("conv-", action, conversation_id, operation_id)
    payload = {
        "predecessor_conversation_id": conversation_id,
        "successor_conversation_id": successor_id,
        "action": action,
        "mission_id": mission_id,
        "operation_id": operation_id,
    }
    fingerprint = _digest(payload)
    provenance = _prov(action, operation_id, fingerprint, args.get("provenance"))
    t = float(time.time() if now is None else now)
    conn.execute("SAVEPOINT conversation_transition")
    try:
        existing = conn.execute(
            "SELECT provenance_json FROM conversation_lineage WHERE conversation_id=?",
            (successor_id,),
        ).fetchone()
        if existing is not None:
            if _prov_load(existing[0]).get("operation_fingerprint") != fingerprint:
                raise ConversationConflict("transition idempotency conflict")
            out = get_conversation(conn, successor_id)
            out["idempotent_replay"] = True
            conn.execute("RELEASE SAVEPOINT conversation_transition")
            return out
        predecessor = _row(conn, conversation_id)
        if predecessor["state"] == "FROZEN":
            raise ConversationConflict("predecessor already frozen")
        prior = _binding(conn, conversation_id)
        if prior["state"] == "FROZEN":
            raise ConversationConflict("predecessor binding already frozen")
        if action == "BIND" and prior["state"] != "UNBOUND":
            raise ConversationConflict("BIND requires an UNBOUND predecessor")
        if action == "DETACH" and (prior["state"] != "BOUND" or prior["mission_id"] is None):
            raise ConversationConflict("DETACH requires a BOUND predecessor")
        next_epoch = int(prior["binding_epoch"]) + 1
        conn.execute(
            "UPDATE conversations SET state='FROZEN',updated_at=? WHERE conversation_id=?",
            (t, conversation_id),
        )
        conn.execute(
            """UPDATE conversation_bindings SET state='FROZEN',detached_at=?
               WHERE conversation_id=? AND binding_epoch=?""",
            (t, conversation_id, prior["binding_epoch"]),
        )
        successor_state = "BOUND" if action == "BIND" else "UNBOUND"
        conn.execute(
            "INSERT INTO conversations VALUES(?,?,?,?,?)",
            (successor_id, predecessor["title"], successor_state, t, t),
        )
        conn.execute(
            "INSERT INTO conversation_lineage VALUES(?,?,?,?,?)",
            (successor_id, conversation_id, action, t, provenance),
        )
        conn.execute(
            "INSERT INTO conversation_bindings VALUES(?,?,?,?,?,?,?,?)",
            (
                successor_id,
                next_epoch,
                mission_id if action == "BIND" else None,
                successor_state,
                prior["context_digest"],
                t if action == "BIND" else None,
                None,
                provenance,
            ),
        )
        out = get_conversation(conn, successor_id)
        out["idempotent_replay"] = False
        conn.execute("RELEASE SAVEPOINT conversation_transition")
        return out
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT conversation_transition")
        conn.execute("RELEASE SAVEPOINT conversation_transition")
        raise


def lineage(conn: sqlite3.Connection, conversation_id: str) -> dict[str, Any]:
    conversation_id = _id(conversation_id, "conversation_id")
    _row(conn, conversation_id)
    ancestors = []
    current = conversation_id
    seen = set()
    while current:
        if current in seen:
            raise ConversationConflict("lineage cycle")
        seen.add(current)
        item = conn.execute(
            "SELECT * FROM conversation_lineage WHERE conversation_id=?", (current,)
        ).fetchone()
        if item is None:
            raise ConversationConflict("lineage row missing")
        ancestors.append(dict(item))
        current = item["predecessor_conversation_id"]
    descendants = []
    frontier = [conversation_id]
    visited = {conversation_id}
    while frontier:
        parent = frontier.pop(0)
        for item in conn.execute(
            """SELECT * FROM conversation_lineage WHERE predecessor_conversation_id=?
               ORDER BY created_at,conversation_id""",
            (parent,),
        ):
            cid = item["conversation_id"]
            if cid in visited:
                raise ConversationConflict("lineage cycle")
            visited.add(cid)
            descendants.append(dict(item))
            frontier.append(cid)
    return {
        "conversation_id": conversation_id,
        "ancestors": ancestors,
        "descendants": descendants,
        "authority_effect": "NONE",
    }


def create_lane(
    conn: sqlite3.Connection, conversation_id: str, args: Mapping[str, Any], *, now: float | None = None
) -> dict[str, Any]:
    conversation_id = _id(conversation_id, "conversation_id")
    if not isinstance(args, Mapping):
        raise ConversationDomainError("lane schema")
    if set(args) - {
        "binding_epoch", "lane_id", "provider", "provider_session_ref",
        "state", "context_digest",
    }:
        raise ConversationDomainError("lane schema")
    conversation = _row(conn, conversation_id)
    if conversation["state"] == "FROZEN":
        raise ConversationConflict("frozen conversation lane mutation")
    binding = _binding(conn, conversation_id)
    binding_epoch = int(args.get("binding_epoch") or binding["binding_epoch"])
    if binding_epoch != int(binding["binding_epoch"]):
        raise ConversationConflict("lane binding epoch mismatch")
    lane_id = _id(args.get("lane_id"), "lane_id")
    provider = str(args.get("provider") or "").upper()
    if provider not in PROVIDERS:
        raise ConversationDomainError("provider")
    provider_session_ref = args.get("provider_session_ref")
    if provider_session_ref is not None:
        provider_session_ref = _ref(provider_session_ref, "provider_session_ref")
        if provider_session_ref == conversation_id:
            raise ConversationDomainError("provider session cannot equal conversation identity")
    state = str(args.get("state") or "READY").upper()
    if state not in LANE_STATES:
        raise ConversationDomainError("lane state")
    context_digest = _hex64(
        args.get("context_digest") or binding["context_digest"], "context_digest"
    )
    if context_digest != binding["context_digest"]:
        raise ConversationConflict("lane context digest mismatch")
    t = float(time.time() if now is None else now)
    values = (
        conversation_id, binding_epoch, lane_id, provider, provider_session_ref,
        state, context_digest, t, t,
    )
    conn.execute("SAVEPOINT conversation_lane")
    try:
        existing = conn.execute(
            """SELECT * FROM conversation_provider_lanes
               WHERE conversation_id=? AND binding_epoch=? AND lane_id=?""",
            (conversation_id, binding_epoch, lane_id),
        ).fetchone()
        if existing is not None:
            comparable = (
                existing["conversation_id"], existing["binding_epoch"], existing["lane_id"],
                existing["provider"], existing["provider_session_ref"], existing["state"],
                existing["context_digest"],
            )
            if comparable != values[:7]:
                raise ConversationConflict("lane idempotency conflict")
            out = dict(existing)
            out.update({"idempotent_replay": True, "authority_effect": "NONE"})
            conn.execute("RELEASE SAVEPOINT conversation_lane")
            return out
        conn.execute("INSERT INTO conversation_provider_lanes VALUES(?,?,?,?,?,?,?,?,?)", values)
        out = dict(conn.execute(
            """SELECT * FROM conversation_provider_lanes
               WHERE conversation_id=? AND binding_epoch=? AND lane_id=?""",
            (conversation_id, binding_epoch, lane_id),
        ).fetchone())
        out.update({"idempotent_replay": False, "authority_effect": "NONE"})
        conn.execute("RELEASE SAVEPOINT conversation_lane")
        return out
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT conversation_lane")
        conn.execute("RELEASE SAVEPOINT conversation_lane")
        raise


def list_lanes(conn: sqlite3.Connection, conversation_id: str) -> dict[str, Any]:
    conversation_id = _id(conversation_id, "conversation_id")
    _row(conn, conversation_id)
    return {
        "conversation_id": conversation_id,
        "lanes": [
            dict(x) for x in conn.execute(
                """SELECT * FROM conversation_provider_lanes
                   WHERE conversation_id=? ORDER BY binding_epoch,lane_id""",
                (conversation_id,),
            )
        ],
        "authority_effect": "NONE",
    }


def create_bridge(
    conn: sqlite3.Connection, conversation_id: str, args: Mapping[str, Any], *, now: float | None = None
) -> dict[str, Any]:
    conversation_id = _id(conversation_id, "conversation_id")
    _row(conn, conversation_id)
    if not isinstance(args, Mapping):
        raise ConversationDomainError("bridge schema")
    if set(args) - {
        "bridge_id", "external_thread_ref", "external_system",
        "context_snapshot_digest", "provenance",
    }:
        raise ConversationDomainError("bridge schema")
    external_thread_ref = _ref(args.get("external_thread_ref"), "external_thread_ref")
    external_system = _id(args.get("external_system"), "external_system")
    if external_thread_ref == conversation_id:
        raise ConversationDomainError("external thread cannot equal conversation identity")
    bridge_id = _id(
        args.get("bridge_id") or _stable("bridge-", external_system, external_thread_ref),
        "bridge_id",
    )
    context_snapshot_digest = _hex64(
        args.get("context_snapshot_digest"), "context_snapshot_digest"
    )
    fingerprint = _digest({
        "conversation_id": conversation_id,
        "external_thread_ref": external_thread_ref,
        "external_system": external_system,
        "context_snapshot_digest": context_snapshot_digest,
    })
    provenance = _prov("EXTERNAL_BRIDGE", bridge_id, fingerprint, args.get("provenance"))
    t = float(time.time() if now is None else now)
    conn.execute("SAVEPOINT conversation_bridge")
    try:
        existing = conn.execute(
            """SELECT * FROM conversation_external_bridges
               WHERE external_system=? AND external_thread_ref=?""",
            (external_system, external_thread_ref),
        ).fetchone()
        if existing is not None:
            stored = _prov_load(existing["provenance_json"])
            if existing["conversation_id"] != conversation_id or stored.get("operation_fingerprint") != fingerprint:
                raise ConversationConflict("external thread already bridged differently")
            out = dict(existing)
            out["idempotent_replay"] = True
            conn.execute("RELEASE SAVEPOINT conversation_bridge")
            return out
        conn.execute(
            "INSERT INTO conversation_external_bridges VALUES(?,?,?,?,?,?,?,?)",
            (
                bridge_id, conversation_id, external_thread_ref, external_system,
                t, provenance, context_snapshot_digest, "NONE",
            ),
        )
        out = dict(conn.execute(
            "SELECT * FROM conversation_external_bridges WHERE bridge_id=?", (bridge_id,)
        ).fetchone())
        out["idempotent_replay"] = False
        conn.execute("RELEASE SAVEPOINT conversation_bridge")
        return out
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT conversation_bridge")
        conn.execute("RELEASE SAVEPOINT conversation_bridge")
        raise


def list_bridges(conn: sqlite3.Connection, conversation_id: str) -> dict[str, Any]:
    conversation_id = _id(conversation_id, "conversation_id")
    _row(conn, conversation_id)
    return {
        "conversation_id": conversation_id,
        "external_bridges": [
            dict(x) for x in conn.execute(
                """SELECT * FROM conversation_external_bridges
                   WHERE conversation_id=? ORDER BY created_at,bridge_id""",
                (conversation_id,),
            )
        ],
        "authority_effect": "NONE",
    }


def conversation_domain_operation(
    conn: sqlite3.Connection, op: str, args: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    args = args or {}
    if op == "list":
        return list_conversations(
            conn,
            int(args.get("limit") or 500),
            args.get("mission_id"),
        )
    if op == "create":
        return create_conversation(conn, args)
    conversation_id = args.get("conversation_id")
    if op == "get":
        return get_conversation(conn, conversation_id)
    if op == "bind":
        return transition_conversation(conn, conversation_id, "BIND", args.get("transition") or {})
    if op == "detach":
        return transition_conversation(conn, conversation_id, "DETACH", args.get("transition") or {})
    if op == "lineage":
        return lineage(conn, conversation_id)
    if op == "lane_create":
        return create_lane(conn, conversation_id, args.get("lane") or {})
    if op == "lanes":
        return list_lanes(conn, conversation_id)
    if op == "bridge_create":
        return create_bridge(conn, conversation_id, args.get("bridge") or {})
    if op == "bridges":
        return list_bridges(conn, conversation_id)
    raise ConversationDomainError("conversation operation denied")

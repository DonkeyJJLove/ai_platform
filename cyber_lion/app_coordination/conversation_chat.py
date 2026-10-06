"""R24 Model Chat lanes and durable reactive delivery.

The store functions operate only on the additive conversation schema. The service
functions orchestrate LOCAL/SAAS/DUAL without making provider identity,
mission identity, or broker correlation equal to conversation identity.
"""
from __future__ import annotations

from hashlib import sha256
import json
import logging
import re
import sqlite3
import time
import uuid
from typing import Any, Mapping

from .conversation_domain import (
    ConversationConflict,
    ConversationDomainError,
    ConversationNotFound,
)

LOGGER = logging.getLogger(__name__)
ROUTES = frozenset({"LOCAL", "SAAS", "DUAL"})
PROVIDER_FOR_LEG = {"LOCAL": "LOCAL", "SAAS": "SAAS"}
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_NAMESPACE = uuid.UUID("cb90965e-f0b3-4c9d-bbec-825fe68eea0d")


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return sha256(_canon(value).encode("utf-8")).hexdigest()


def _id(value: Any, name: str) -> str:
    value = str(value or "").strip()
    if _ID.fullmatch(value) is None:
        raise ConversationDomainError(name)
    return value


def _stable(prefix: str, *parts: str) -> str:
    return prefix + uuid.uuid5(_NAMESPACE, "|".join(parts)).hex


def _json(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except Exception as error:
        raise ConversationConflict("message metadata invalid") from error
    return parsed if isinstance(parsed, dict) else {}


def _conversation(conn: sqlite3.Connection, conversation_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM conversations WHERE conversation_id=?",
        (conversation_id,),
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


def _canonical_history(conn: sqlite3.Connection, conversation_id: str) -> list[dict[str, str]]:
    rows = []
    for row in conn.execute(
        """SELECT role,content,metadata_json FROM conversation_messages
           WHERE conversation_id=? ORDER BY created_at,message_id""",
        (conversation_id,),
    ):
        meta = _json(row["metadata_json"])
        if not meta.get("canonical_context"):
            continue
        role = str(row["role"]).lower()
        if role not in {"user", "assistant"}:
            continue
        rows.append({"role": role, "content": str(row["content"])[:1400]})
    selected = []
    total = 0
    for item in reversed(rows[-8:]):
        size = len(item["content"])
        if total + size > 4200:
            break
        selected.append(item)
        total += size
    selected.reverse()
    return selected


def _next_sequence(conn: sqlite3.Connection, conversation_id: str, binding_epoch: int) -> int:
    return int(conn.execute(
        """SELECT COALESCE(MAX(sequence),0)+1 FROM conversation_delivery_events
           WHERE conversation_id=? AND binding_epoch=?""",
        (conversation_id, binding_epoch),
    ).fetchone()[0])


def _event(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    conversation_id: str,
    binding_epoch: int,
    lane_id: str,
    message_id: str,
    participant_id: str | None,
    causation_id: str,
    correlation_id: str,
    context_digest: str,
    state: str,
    response_message_id: str | None,
    created_at: float,
) -> sqlite3.Row:
    existing = conn.execute(
        "SELECT * FROM conversation_delivery_events WHERE event_id=?",
        (event_id,),
    ).fetchone()
    if existing is not None:
        expected = (
            conversation_id, binding_epoch, lane_id, message_id, participant_id,
            causation_id, correlation_id, context_digest, state, response_message_id,
        )
        observed = (
            existing["conversation_id"], existing["binding_epoch"], existing["lane_id"],
            existing["message_id"], existing["participant_id"], existing["causation_id"],
            existing["correlation_id"], existing["context_digest"], existing["state"],
            existing["response_message_id"],
        )
        if observed != expected:
            raise ConversationConflict("delivery event identity conflict")
        return existing
    sequence = _next_sequence(conn, conversation_id, binding_epoch)
    conn.execute(
        """INSERT INTO conversation_delivery_events(
             event_id,conversation_id,binding_epoch,lane_id,message_id,participant_id,
             causation_id,correlation_id,context_digest,sequence,state,response_message_id,created_at
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            event_id, conversation_id, binding_epoch, lane_id, message_id, participant_id,
            causation_id, correlation_id, context_digest, sequence, state,
            response_message_id, created_at,
        ),
    )
    return conn.execute(
        "SELECT * FROM conversation_delivery_events WHERE event_id=?",
        (event_id,),
    ).fetchone()


def _request_rows(
    conn: sqlite3.Connection, conversation_id: str, correlation_id: str
) -> list[sqlite3.Row]:
    return list(conn.execute(
        """SELECT m.*,l.provider,l.provider_session_ref
           FROM conversation_messages m
           JOIN conversation_provider_lanes l
             ON l.conversation_id=m.conversation_id
            AND l.binding_epoch=m.binding_epoch
            AND l.lane_id=m.lane_id
           WHERE m.conversation_id=? AND m.correlation_id=? AND m.role='USER'
           ORDER BY CASE l.provider WHEN 'LOCAL' THEN 0 WHEN 'SAAS' THEN 1 ELSE 2 END,m.message_id""",
        (conversation_id, correlation_id),
    ))


def prepare_chat(
    conn: sqlite3.Connection,
    args: Mapping[str, Any],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    if not isinstance(args, Mapping):
        raise ConversationDomainError("chat prepare schema")
    allowed = {"conversation_id", "message", "route", "client_request_id", "output_language", "shared_context_digest"}
    if set(args) - allowed:
        raise ConversationDomainError("chat prepare schema")
    conversation_id = _id(args.get("conversation_id"), "conversation_id")
    message = str(args.get("message") or "").strip()
    if not 1 <= len(message) <= 16000:
        raise ConversationDomainError("message")
    route = str(args.get("route") or "LOCAL").upper()
    if route not in ROUTES:
        raise ConversationDomainError("route")
    client_request_id = _id(args.get("client_request_id"), "client_request_id")
    output_language = str(args.get("output_language") or "auto")[:32]
    shared_context_digest = str(args.get("shared_context_digest") or "")
    if _HEX64.fullmatch(shared_context_digest) is None:
        raise ConversationDomainError("shared_context_digest")
    conversation = _conversation(conn, conversation_id)
    if conversation["state"] == "FROZEN":
        raise ConversationConflict("frozen conversation cannot accept Model Chat")
    binding = _binding(conn, conversation_id)
    binding_epoch = int(binding["binding_epoch"])
    correlation_id = _stable("corr-", conversation_id, str(binding_epoch), client_request_id)
    causation_id = _stable("cause-", conversation_id, str(binding_epoch), client_request_id)
    existing = _request_rows(conn, conversation_id, correlation_id)
    if existing:
        first_meta = _json(existing[0]["metadata_json"])
        if (
            first_meta.get("client_request_id") != client_request_id
            or first_meta.get("request_route") != route
            or first_meta.get("request_content_digest") != _digest(message)
            or first_meta.get("shared_context_digest") != shared_context_digest
        ):
            raise ConversationConflict("chat request idempotency conflict")
        history = first_meta.get("frozen_history")
        if not isinstance(history, list):
            raise ConversationConflict("frozen history missing")
        return {
            "conversation_id": conversation_id,
            "binding_epoch": binding_epoch,
            "mission_id": binding["mission_id"],
            "route": route,
            "client_request_id": client_request_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "context_digest": existing[0]["context_digest"],
            "shared_context_digest": shared_context_digest,
            "history": history,
            "message": message,
            "output_language": output_language,
            "legs": [
                {
                    "provider": row["provider"],
                    "lane_id": row["lane_id"],
                    "provider_session_ref": row["provider_session_ref"],
                    "message_id": row["message_id"],
                }
                for row in existing
            ],
            "idempotent_replay": True,
            "authority_effect": "NONE",
        }

    history = _canonical_history(conn, conversation_id)
    snapshot = {
        "shared_context_digest": shared_context_digest,
        "conversation_id": conversation_id,
        "binding_epoch": binding_epoch,
        "history": history,
        "user": message,
    }
    context_digest = _digest(snapshot)
    providers = ["LOCAL", "SAAS"] if route == "DUAL" else [route]
    t = float(time.time() if now is None else now)
    conn.execute("SAVEPOINT conversation_chat_prepare")
    try:
        legs = []
        for index, provider in enumerate(providers):
            suffix = correlation_id[-16:]
            lane_id = f"lane-{provider.lower()}-{suffix}"
            provider_session_ref = _stable(
                "ps-", provider, conversation_id, str(binding_epoch), correlation_id
            )
            message_id = _stable("msg-user-", provider, conversation_id, correlation_id)
            conn.execute(
                """INSERT INTO conversation_provider_lanes(
                     conversation_id,binding_epoch,lane_id,provider,provider_session_ref,
                     state,context_digest,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    conversation_id, binding_epoch, lane_id, provider,
                    provider_session_ref, "ACTIVE", context_digest, t, t,
                ),
            )
            metadata = {
                "authority_effect": "NONE",
                "canonical_context": index == 0,
                "client_request_id": client_request_id,
                "request_route": route,
                "request_leg": provider,
                "request_content_digest": _digest(message),
                "shared_context_digest": shared_context_digest,
                "frozen_history": history,
                "provider_session_ref": provider_session_ref,
            }
            conn.execute(
                """INSERT INTO conversation_messages(
                     message_id,conversation_id,binding_epoch,lane_id,role,content,
                     causation_id,correlation_id,context_digest,created_at,metadata_json
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    message_id, conversation_id, binding_epoch, lane_id, "USER", message,
                    causation_id, correlation_id, context_digest, t, _canon(metadata),
                ),
            )
            event_id = _stable("evt-", "QUEUED", provider, conversation_id, correlation_id)
            _event(
                conn,
                event_id=event_id,
                conversation_id=conversation_id,
                binding_epoch=binding_epoch,
                lane_id=lane_id,
                message_id=message_id,
                participant_id=None,
                causation_id=causation_id,
                correlation_id=correlation_id,
                context_digest=context_digest,
                state="PERSISTED",
                response_message_id=None,
                created_at=t,
            )
            legs.append({
                "provider": provider,
                "lane_id": lane_id,
                "provider_session_ref": provider_session_ref,
                "message_id": message_id,
            })
        conn.execute("RELEASE SAVEPOINT conversation_chat_prepare")
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT conversation_chat_prepare")
        conn.execute("RELEASE SAVEPOINT conversation_chat_prepare")
        raise
    return {
        "conversation_id": conversation_id,
        "binding_epoch": binding_epoch,
        "mission_id": binding["mission_id"],
        "route": route,
        "client_request_id": client_request_id,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "context_digest": context_digest,
        "shared_context_digest": shared_context_digest,
        "history": history,
        "message": message,
        "output_language": output_language,
        "legs": legs,
        "idempotent_replay": False,
        "authority_effect": "NONE",
    }


def link_saas_request(
    conn: sqlite3.Connection,
    args: Mapping[str, Any],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    conversation_id = _id(args.get("conversation_id"), "conversation_id")
    message_id = _id(args.get("message_id"), "message_id")
    request_id = _id(args.get("request_id"), "request_id")
    projection_digest = str(args.get("projection_digest") or "")
    shared_context_digest = str(args.get("shared_context_digest") or "")
    if _HEX64.fullmatch(projection_digest) is None or _HEX64.fullmatch(shared_context_digest) is None:
        raise ConversationDomainError("SaaS projection/shared digest")
    row = conn.execute(
        """SELECT m.*,l.provider FROM conversation_messages m
           JOIN conversation_provider_lanes l
             ON l.conversation_id=m.conversation_id
            AND l.binding_epoch=m.binding_epoch
            AND l.lane_id=m.lane_id
           WHERE m.message_id=? AND m.conversation_id=?""",
        (message_id, conversation_id),
    ).fetchone()
    if row is None:
        raise ConversationNotFound(message_id)
    if row["provider"] != "SAAS" or row["role"] != "USER":
        raise ConversationConflict("SaaS link target is not a SAAS request leg")
    map_id = _stable("threadmap-", "LION_SAAS_BROKER", request_id)
    t = float(time.time() if now is None else now)
    provenance = _canon({
        "authority_effect": "NONE",
        "kind": "SAAS_BROKER_REQUEST",
        "request_message_id": message_id,
        "correlation_id": row["correlation_id"],
        "shared_context_digest": shared_context_digest,
        "projection_digest": projection_digest,
    })
    conn.execute("SAVEPOINT conversation_saas_link")
    try:
        existing = conn.execute(
            """SELECT * FROM conversation_threads
               WHERE thread_system='LION_SAAS_BROKER' AND thread_ref=?""",
            (request_id,),
        ).fetchone()
        if existing is not None:
            if (
                existing["conversation_id"] != conversation_id
                or existing["lane_id"] != row["lane_id"]
            ):
                raise ConversationConflict("broker request already mapped elsewhere")
            out = dict(existing)
            out["idempotent_replay"] = True
            conn.execute("RELEASE SAVEPOINT conversation_saas_link")
            return out
        conn.execute(
            "INSERT INTO conversation_threads VALUES(?,?,?,?,?,?,?,?,?)",
            (
                map_id, conversation_id, row["binding_epoch"], row["lane_id"],
                request_id, "LION_SAAS_BROKER", "ACTIVE", t, provenance,
            ),
        )
        out = dict(conn.execute(
            "SELECT * FROM conversation_threads WHERE thread_map_id=?",
            (map_id,),
        ).fetchone())
        out["idempotent_replay"] = False
        conn.execute("RELEASE SAVEPOINT conversation_saas_link")
        return out
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT conversation_saas_link")
        conn.execute("RELEASE SAVEPOINT conversation_saas_link")
        raise


def _response_row(
    conn: sqlite3.Connection, correlation_id: str, provider: str
) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT m.* FROM conversation_messages m
           JOIN conversation_provider_lanes l
             ON l.conversation_id=m.conversation_id
            AND l.binding_epoch=m.binding_epoch
            AND l.lane_id=m.lane_id
           WHERE m.role='ASSISTANT' AND m.correlation_id=? AND l.provider=?
           ORDER BY m.created_at,m.message_id LIMIT 1""",
        (correlation_id, provider),
    ).fetchone()


def _maybe_join_dual(
    conn: sqlite3.Connection,
    request: sqlite3.Row,
    *,
    now: float,
) -> dict[str, Any] | None:
    meta = _json(request["metadata_json"])
    if meta.get("request_route") != "DUAL":
        return None
    conversation_id = request["conversation_id"]
    correlation_id = request["correlation_id"]
    requests = _request_rows(conn, conversation_id, correlation_id)
    by_provider = {row["provider"]: row for row in requests}
    if set(by_provider) != {"LOCAL", "SAAS"}:
        raise ConversationConflict("DUAL legs incomplete")
    local_response = _response_row(conn, correlation_id, "LOCAL")
    saas_response = _response_row(conn, correlation_id, "SAAS")
    if local_response is None or saas_response is None:
        return None
    join_lane = "lane-join-" + correlation_id[-16:]
    join_message_id = _stable("msg-join-", conversation_id, correlation_id)
    existing = conn.execute(
        "SELECT * FROM conversation_messages WHERE message_id=?",
        (join_message_id,),
    ).fetchone()
    if existing is not None:
        return dict(existing)
    context_digest = request["context_digest"]
    binding_epoch = int(request["binding_epoch"])
    conn.execute(
        """INSERT INTO conversation_provider_lanes(
             conversation_id,binding_epoch,lane_id,provider,provider_session_ref,
             state,context_digest,created_at,updated_at
           ) VALUES(?,?,?,?,?,?,?,?,?)""",
        (
            conversation_id, binding_epoch, join_lane, "DETERMINISTIC", None,
            "CLOSED", context_digest, now, now,
        ),
    )
    answer = (
        "### LOCAL\n" + local_response["content"] +
        "\n\n### SAAS\n" + saas_response["content"]
    )
    join_meta = {
        "authority_effect": "NONE",
        "canonical_context": True,
        "request_route": "DUAL",
        "request_leg": "JOIN",
        "source_response_ids": [local_response["message_id"], saas_response["message_id"]],
        "join_policy": "NO_CROSS_PROVIDER_HIDDEN_STATE",
    }
    conn.execute(
        """INSERT INTO conversation_messages(
             message_id,conversation_id,binding_epoch,lane_id,role,content,
             causation_id,correlation_id,context_digest,created_at,metadata_json
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            join_message_id, conversation_id, binding_epoch, join_lane, "ASSISTANT",
            answer, request["causation_id"], correlation_id, context_digest, now,
            _canon(join_meta),
        ),
    )
    _event(
        conn,
        event_id=_stable("evt-", "JOINED", conversation_id, correlation_id),
        conversation_id=conversation_id,
        binding_epoch=binding_epoch,
        lane_id=join_lane,
        message_id=request["message_id"],
        participant_id=None,
        causation_id=request["causation_id"],
        correlation_id=correlation_id,
        context_digest=context_digest,
        state="DELIVERED",
        response_message_id=join_message_id,
        created_at=now,
    )
    return dict(conn.execute(
        "SELECT * FROM conversation_messages WHERE message_id=?",
        (join_message_id,),
    ).fetchone())


def record_response(
    conn: sqlite3.Connection,
    args: Mapping[str, Any],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    conversation_id = _id(args.get("conversation_id"), "conversation_id")
    request_message_id = _id(args.get("request_message_id"), "request_message_id")
    provider = str(args.get("provider") or "").upper()
    if provider not in {"LOCAL", "SAAS"}:
        raise ConversationDomainError("provider")
    response_text = str(args.get("response_text") or "")
    if not response_text:
        raise ConversationDomainError("response_text")
    response_meta = args.get("response_meta") or {}
    if not isinstance(response_meta, Mapping):
        raise ConversationDomainError("response_meta")
    request = conn.execute(
        """SELECT m.*,l.provider FROM conversation_messages m
           JOIN conversation_provider_lanes l
             ON l.conversation_id=m.conversation_id
            AND l.binding_epoch=m.binding_epoch
            AND l.lane_id=m.lane_id
           WHERE m.message_id=? AND m.conversation_id=?""",
        (request_message_id, conversation_id),
    ).fetchone()
    if request is None:
        raise ConversationNotFound(request_message_id)
    if request["role"] != "USER" or request["provider"] != provider:
        raise ConversationConflict("response provider/request mismatch")
    request_meta = _json(request["metadata_json"])
    canonical = request_meta.get("request_route") == provider
    response_message_id = _stable(
        "msg-assistant-", provider, conversation_id, request["correlation_id"]
    )
    t = float(time.time() if now is None else now)
    conn.execute("SAVEPOINT conversation_response")
    try:
        existing = conn.execute(
            "SELECT * FROM conversation_messages WHERE message_id=?",
            (response_message_id,),
        ).fetchone()
        if existing is not None:
            if existing["content"] != response_text:
                raise ConversationConflict("response replay content conflict")
            join = _maybe_join_dual(conn, request, now=t)
            conn.execute("RELEASE SAVEPOINT conversation_response")
            return {
                "response": dict(existing),
                "join": join,
                "idempotent_replay": True,
                "authority_effect": "NONE",
            }
        metadata = {
            "authority_effect": "NONE",
            "canonical_context": canonical,
            "request_route": request_meta.get("request_route"),
            "request_leg": provider,
            "provider_session_ref": request_meta.get("provider_session_ref"),
            "request_message_id": request_message_id,
            "response_meta": dict(response_meta),
        }
        conn.execute(
            """INSERT INTO conversation_messages(
                 message_id,conversation_id,binding_epoch,lane_id,role,content,
                 causation_id,correlation_id,context_digest,created_at,metadata_json
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                response_message_id, conversation_id, request["binding_epoch"],
                request["lane_id"], "ASSISTANT", response_text, request["causation_id"],
                request["correlation_id"], request["context_digest"], t,
                _canon(metadata),
            ),
        )
        conn.execute(
            """UPDATE conversation_provider_lanes SET state='CLOSED',updated_at=?
               WHERE conversation_id=? AND binding_epoch=? AND lane_id=?""",
            (t, conversation_id, request["binding_epoch"], request["lane_id"]),
        )
        _event(
            conn,
            event_id=_stable(
                "evt-", "RESPONSE", provider, conversation_id, request["correlation_id"]
            ),
            conversation_id=conversation_id,
            binding_epoch=request["binding_epoch"],
            lane_id=request["lane_id"],
            message_id=request_message_id,
            participant_id=None,
            causation_id=request["causation_id"],
            correlation_id=request["correlation_id"],
            context_digest=request["context_digest"],
            state="DELIVERED",
            response_message_id=response_message_id,
            created_at=t,
        )
        join = _maybe_join_dual(conn, request, now=t)
        response = dict(conn.execute(
            "SELECT * FROM conversation_messages WHERE message_id=?",
            (response_message_id,),
        ).fetchone())
        conn.execute("RELEASE SAVEPOINT conversation_response")
        return {
            "response": response,
            "join": join,
            "idempotent_replay": False,
            "authority_effect": "NONE",
        }
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT conversation_response")
        conn.execute("RELEASE SAVEPOINT conversation_response")
        raise


def record_leg_failure(
    conn: sqlite3.Connection,
    args: Mapping[str, Any],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    conversation_id = _id(args.get("conversation_id"), "conversation_id")
    request_message_id = _id(args.get("request_message_id"), "request_message_id")
    error_class = _id(args.get("error_class"), "error_class")
    request = conn.execute(
        "SELECT * FROM conversation_messages WHERE message_id=? AND conversation_id=?",
        (request_message_id, conversation_id),
    ).fetchone()
    if request is None:
        raise ConversationNotFound(request_message_id)
    t = float(time.time() if now is None else now)
    conn.execute("SAVEPOINT conversation_leg_failure")
    try:
        conn.execute(
            """UPDATE conversation_provider_lanes SET state='FAILED',updated_at=?
               WHERE conversation_id=? AND binding_epoch=? AND lane_id=?""",
            (t, conversation_id, request["binding_epoch"], request["lane_id"]),
        )
        event = _event(
            conn,
            event_id=_stable(
                "evt-", "FAILED", conversation_id, request["correlation_id"], request["lane_id"]
            ),
            conversation_id=conversation_id,
            binding_epoch=request["binding_epoch"],
            lane_id=request["lane_id"],
            message_id=request_message_id,
            participant_id=None,
            causation_id=request["causation_id"],
            correlation_id=request["correlation_id"],
            context_digest=request["context_digest"],
            state="FAILED",
            response_message_id=None,
            created_at=t,
        )
        conn.execute("RELEASE SAVEPOINT conversation_leg_failure")
        return {
            "event": dict(event),
            "error_class": error_class,
            "authority_effect": "NONE",
        }
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT conversation_leg_failure")
        conn.execute("RELEASE SAVEPOINT conversation_leg_failure")
        raise


TERMINAL_SAAS_NO_RESPONSE = frozenset({"CANCELLED", "SUPERSEDED"})


def close_saas_delivery_without_response(
    conn: sqlite3.Connection,
    args: Mapping[str, Any],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    request_id = _id(args.get("request_id"), "request_id")
    broker_status = str(args.get("broker_status") or "").upper()
    if broker_status not in TERMINAL_SAAS_NO_RESPONSE:
        raise ConversationDomainError("broker terminal status")
    candidate = conn.execute(
        """SELECT t.*,m.message_id
           FROM conversation_threads t
           JOIN conversation_messages m
             ON m.conversation_id=t.conversation_id
            AND m.binding_epoch=t.binding_epoch
            AND m.lane_id=t.lane_id
            AND m.role='USER'
           WHERE t.thread_system='LION_SAAS_BROKER' AND t.thread_ref=?""",
        (request_id,),
    ).fetchone()
    if candidate is None:
        raise ConversationNotFound(request_id)
    t = float(time.time() if now is None else now)
    if candidate["state"] == "CLOSED":
        return {
            "request_id": request_id,
            "conversation_id": candidate["conversation_id"],
            "broker_status": broker_status,
            "closed_at": t,
            "idempotent_replay": True,
            "authority_effect": "NONE",
        }
    conn.execute("SAVEPOINT conversation_saas_terminal")
    try:
        record_leg_failure(
            conn,
            {
                "conversation_id": candidate["conversation_id"],
                "request_message_id": candidate["message_id"],
                "error_class": "SAAS_" + broker_status,
            },
            now=t,
        )
        conn.execute(
            """UPDATE conversation_threads SET state='CLOSED'
               WHERE thread_system='LION_SAAS_BROKER' AND thread_ref=?""",
            (request_id,),
        )
        conn.execute("RELEASE SAVEPOINT conversation_saas_terminal")
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT conversation_saas_terminal")
        conn.execute("RELEASE SAVEPOINT conversation_saas_terminal")
        raise
    return {
        "request_id": request_id,
        "conversation_id": candidate["conversation_id"],
        "broker_status": broker_status,
        "closed_at": t,
        "idempotent_replay": False,
        "authority_effect": "NONE",
    }


def saas_delivery_candidates(conn: sqlite3.Connection, limit: int = 128) -> dict[str, Any]:
    rows = []
    for row in conn.execute(
        """SELECT t.thread_ref AS request_id,t.thread_map_id,t.conversation_id,
                  t.binding_epoch,t.lane_id,t.provenance_json,m.message_id,
                  m.message_id AS request_message_id,m.causation_id,
                  m.correlation_id,m.context_digest,l.provider_session_ref,
                  b.mission_id,b.context_digest AS binding_context_digest
           FROM conversation_threads t
           JOIN conversation_provider_lanes l
             ON l.conversation_id=t.conversation_id
            AND l.binding_epoch=t.binding_epoch
            AND l.lane_id=t.lane_id
           JOIN conversation_messages m
             ON m.conversation_id=t.conversation_id
            AND m.binding_epoch=t.binding_epoch
            AND m.lane_id=t.lane_id
            AND m.role='USER'
           JOIN conversation_bindings b
             ON b.conversation_id=t.conversation_id
            AND b.binding_epoch=t.binding_epoch
           WHERE t.thread_system='LION_SAAS_BROKER'
             AND t.state='ACTIVE'
             AND l.provider='SAAS'
           ORDER BY t.created_at,t.thread_map_id LIMIT ?""",
        (int(limit),),
    ):
        item=dict(row)
        provenance=_json(item.pop("provenance_json", "{}"))
        item["shared_context_digest"]=provenance.get("shared_context_digest")
        item["projection_digest"]=provenance.get("projection_digest")
        rows.append(item)
    return {"candidates": rows, "authority_effect": "NONE"}


def complete_saas_delivery(
    conn: sqlite3.Connection,
    args: Mapping[str, Any],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    request_id = _id(args.get("request_id"), "request_id")
    candidate = conn.execute(
        """SELECT t.*,m.message_id
           FROM conversation_threads t
           JOIN conversation_messages m
             ON m.conversation_id=t.conversation_id
            AND m.binding_epoch=t.binding_epoch
            AND m.lane_id=t.lane_id
            AND m.role='USER'
           WHERE t.thread_system='LION_SAAS_BROKER' AND t.thread_ref=?""",
        (request_id,),
    ).fetchone()
    if candidate is None:
        raise ConversationNotFound(request_id)
    t = float(time.time() if now is None else now)
    conn.execute("SAVEPOINT conversation_saas_complete")
    try:
        result = record_response(
            conn,
            {
                "conversation_id": candidate["conversation_id"],
                "request_message_id": candidate["message_id"],
                "provider": "SAAS",
                "response_text": args.get("response_text"),
                "response_meta": args.get("response_meta") or {},
            },
            now=t,
        )
        conn.execute(
            """UPDATE conversation_threads SET state='CLOSED'
               WHERE thread_system='LION_SAAS_BROKER' AND thread_ref=?""",
            (request_id,),
        )
        conn.execute("RELEASE SAVEPOINT conversation_saas_complete")
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT conversation_saas_complete")
        conn.execute("RELEASE SAVEPOINT conversation_saas_complete")
        raise
    return {
        **result,
        "request_id": request_id,
        "conversation_id": candidate["conversation_id"],
        "closed_at": t,
    }

def transcript(conn: sqlite3.Connection, conversation_id: str) -> dict[str, Any]:
    conversation_id = _id(conversation_id, "conversation_id")
    _conversation(conn, conversation_id)
    rows = []
    for row in conn.execute(
        """SELECT * FROM conversation_messages
           WHERE conversation_id=? ORDER BY created_at,message_id""",
        (conversation_id,),
    ):
        meta = _json(row["metadata_json"])
        if not meta.get("canonical_context"):
            continue
        item = dict(row)
        item["metadata"] = meta
        item.pop("metadata_json", None)
        rows.append(item)
    return {
        "conversation_id": conversation_id,
        "messages": rows,
        "authority_effect": "NONE",
    }


def delivery_events(
    conn: sqlite3.Connection,
    args: Mapping[str, Any],
) -> dict[str, Any]:
    conversation_id = _id(args.get("conversation_id"), "conversation_id")
    consumer_id = _id(args.get("consumer_id"), "consumer_id")
    limit = int(args.get("limit") or 100)
    if not 1 <= limit <= 500:
        raise ConversationDomainError("limit")
    binding = _binding(conn, conversation_id)
    binding_epoch = int(binding["binding_epoch"])
    supplied_after = args.get("after")
    if supplied_after is None:
        cursor = conn.execute(
            """SELECT last_sequence FROM conversation_delivery_cursors
               WHERE conversation_id=? AND binding_epoch=? AND consumer_id=?""",
            (conversation_id, binding_epoch, consumer_id),
        ).fetchone()
        after = int(cursor[0]) if cursor else 0
    else:
        after = int(supplied_after)
        if after < 0:
            raise ConversationDomainError("after")
    rows = []
    for event in conn.execute(
        """SELECT e.*,m.role AS response_role,m.content AS response_content,
                  m.metadata_json AS response_metadata_json
           FROM conversation_delivery_events e
           LEFT JOIN conversation_messages m ON m.message_id=e.response_message_id
           WHERE e.conversation_id=? AND e.binding_epoch=? AND e.sequence>?
           ORDER BY e.sequence,e.event_id LIMIT ?""",
        (conversation_id, binding_epoch, after, limit),
    ):
        item = dict(event)
        metadata_json = item.pop("response_metadata_json", None)
        if item.get("response_message_id"):
            item["response_message"] = {
                "message_id": item["response_message_id"],
                "role": item.pop("response_role"),
                "content": item.pop("response_content"),
                "metadata": _json(metadata_json or "{}"),
            }
        else:
            item.pop("response_role", None)
            item.pop("response_content", None)
            item["response_message"] = None
        rows.append(item)
    next_cursor = max([after] + [int(x["sequence"]) for x in rows])
    return {
        "conversation_id": conversation_id,
        "binding_epoch": binding_epoch,
        "consumer_id": consumer_id,
        "after": after,
        "events": rows,
        "next_cursor": next_cursor,
        "authority_effect": "NONE",
    }


def acknowledge_cursor(
    conn: sqlite3.Connection,
    args: Mapping[str, Any],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    conversation_id = _id(args.get("conversation_id"), "conversation_id")
    consumer_id = _id(args.get("consumer_id"), "consumer_id")
    last_sequence = int(args.get("last_sequence"))
    if last_sequence < 0:
        raise ConversationDomainError("last_sequence")
    binding = _binding(conn, conversation_id)
    binding_epoch = int(binding["binding_epoch"])
    max_sequence = int(conn.execute(
        """SELECT COALESCE(MAX(sequence),0) FROM conversation_delivery_events
           WHERE conversation_id=? AND binding_epoch=?""",
        (conversation_id, binding_epoch),
    ).fetchone()[0])
    if last_sequence > max_sequence:
        raise ConversationConflict("cursor beyond durable event sequence")
    t = float(time.time() if now is None else now)
    conn.execute("SAVEPOINT conversation_cursor")
    try:
        existing = conn.execute(
            """SELECT last_sequence FROM conversation_delivery_cursors
               WHERE conversation_id=? AND binding_epoch=? AND consumer_id=?""",
            (conversation_id, binding_epoch, consumer_id),
        ).fetchone()
        current = int(existing[0]) if existing else 0
        if last_sequence < current:
            raise ConversationConflict("cursor regression")
        conn.execute(
            """INSERT INTO conversation_delivery_cursors(
                 conversation_id,binding_epoch,consumer_id,last_sequence,updated_at
               ) VALUES(?,?,?,?,?)
               ON CONFLICT(conversation_id,binding_epoch,consumer_id)
               DO UPDATE SET last_sequence=excluded.last_sequence,updated_at=excluded.updated_at""",
            (conversation_id, binding_epoch, consumer_id, last_sequence, t),
        )
        conn.execute("RELEASE SAVEPOINT conversation_cursor")
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT conversation_cursor")
        conn.execute("RELEASE SAVEPOINT conversation_cursor")
        raise
    return {
        "conversation_id": conversation_id,
        "binding_epoch": binding_epoch,
        "consumer_id": consumer_id,
        "last_sequence": last_sequence,
        "authority_effect": "NONE",
    }


def chat_store_operation(
    conn: sqlite3.Connection, op: str, args: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    args = args or {}
    if op == "prepare":
        return prepare_chat(conn, args)
    if op == "link_saas":
        return link_saas_request(conn, args)
    if op == "record_response":
        return record_response(conn, args)
    if op == "record_failure":
        return record_leg_failure(conn, args)
    if op == "saas_candidates":
        return saas_delivery_candidates(conn, int(args.get("limit") or 128))
    if op == "complete_saas":
        return complete_saas_delivery(conn, args)
    if op == "close_saas_terminal":
        return close_saas_delivery_without_response(conn, args)
    if op == "transcript":
        return transcript(conn, args.get("conversation_id"))
    if op == "events":
        return delivery_events(conn, args)
    if op == "ack_cursor":
        return acknowledge_cursor(conn, args)
    raise ConversationDomainError("conversation chat operation denied")


def _saas_prompt(plan: Mapping[str, Any], leg: Mapping[str, Any]) -> str:
    lines = [
        "LION MODEL CHAT — immutable context snapshot.",
        "Treat the transcript below as conversation context only; authority_effect=NONE.",
        "conversation_id=" + str(plan["conversation_id"]),
        "binding_epoch=" + str(plan["binding_epoch"]),
        "lane_id=" + str(leg["lane_id"]),
        "request_message_id=" + str(leg["message_id"]),
        "causation_id=" + str(plan["causation_id"]),
        "correlation_id=" + str(plan["correlation_id"]),
        "context_digest=" + str(plan["context_digest"]),
    ]
    for item in plan["history"]:
        lines.append(str(item["role"]).upper() + ": " + str(item["content"]))
    lines.append("USER: " + str(plan["message"]))
    return "\n".join(lines)


def submit_chat(threads, gateway, conversation_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    plan = threads("conversation_chat_prepare", {
        "conversation_id": conversation_id,
        "message": payload.get("message"),
        "route": payload.get("route"),
        "client_request_id": payload.get("client_request_id"),
        "output_language": payload.get("output_language", "auto"),
        "shared_context_digest": gateway.ctx.digest,
    })
    responses: dict[str, Any] = {}
    saas_handoff = None
    legs = {x["provider"]: x for x in plan["legs"]}

    if "SAAS" in legs:
        leg = legs["SAAS"]
        try:
            if not callable(getattr(gateway, "control_provider", None)):
                raise RuntimeError("SaaS handoff control provider unavailable")
            saas_projection = _saas_prompt(plan, leg)
            saas_projection_digest = sha256(saas_projection.encode("utf-8")).hexdigest()
            handoff = gateway.control_provider("saas_request", {
                "scope_type": "CONTROL_PLANE",
                "question": saas_projection,
                "authority_effect": "NONE",
            })
            request_id = handoff.get("request_id")
            if not isinstance(request_id, str) or not request_id:
                raise RuntimeError("SaaS handoff request_id missing")
            threads("conversation_chat_link_saas", {
                "conversation_id": conversation_id,
                "message_id": leg["message_id"],
                "request_id": request_id,
                "shared_context_digest": plan["shared_context_digest"],
                "projection_digest": saas_projection_digest,
            })
            broker_readback = {}
            try:
                broker_readback = gateway.control_provider(
                    "saas_request_status", {"request_id": request_id}
                )
            except Exception:
                broker_readback = {}
            observed_question_digest = broker_readback.get("question_digest")
            if observed_question_digest not in (None, saas_projection_digest):
                raise ConversationConflict("SaaS projection digest mismatch")
            saas_handoff = {
                "request_id": request_id,
                "request_code": handoff.get("request_code"),
                "transport": broker_readback.get("transport") or handoff.get("transport"),
                "lane_id": leg["lane_id"],
                "provider_session_ref": leg["provider_session_ref"],
                "context_digest": plan["context_digest"],
                "shared_context_digest": plan["shared_context_digest"],
                "projection_digest": saas_projection_digest,
                "broker_question_digest": observed_question_digest,
                "actual_provider_payload_bytes_digest": None,
            }
        except Exception as error:
            threads("conversation_chat_record_failure", {
                "conversation_id": conversation_id,
                "request_message_id": leg["message_id"],
                "error_class": type(error).__name__,
            })
            responses["SAAS"] = {"state": "FAILED", "error_class": type(error).__name__}

    if "LOCAL" in legs:
        leg = legs["LOCAL"]
        try:
            from .saas_handoff_extension import ROUTE_CONTEXT
            token = ROUTE_CONTEXT.set("LOCAL")
            try:
                local = gateway.chat(
                    plan["message"],
                    history=list(plan["history"]),
                    output_language=plan["output_language"],
                    provider_binding={
                        "conversation_id": conversation_id,
                        "binding_epoch": plan["binding_epoch"],
                        "lane_id": leg["lane_id"],
                        "provider_session_ref": leg["provider_session_ref"],
                        "correlation_id": plan["correlation_id"],
                        "causation_id": plan["causation_id"],
                        "context_digest": plan["context_digest"],
                    },
                )
            finally:
                ROUTE_CONTEXT.reset(token)
            answer = str(local.get("answer") or "")
            if not answer:
                raise RuntimeError("LOCAL empty response")
            stored = threads("conversation_chat_record_response", {
                "conversation_id": conversation_id,
                "request_message_id": leg["message_id"],
                "provider": "LOCAL",
                "response_text": answer,
                "response_meta": {
                    "result_route": local.get("route"),
                    "provider_provenance": local.get("provider_provenance"),
                    "authority_effect": "NONE",
                },
            })
            responses["LOCAL"] = {
                "state": "DELIVERED",
                "response_message_id": stored["response"]["message_id"],
                "answer": answer,
                "lane_id": leg["lane_id"],
                "provider_session_ref": leg["provider_session_ref"],
                "context_digest": plan["context_digest"],
                "shared_context_digest": plan["shared_context_digest"],
                "provider_provenance": local.get("provider_provenance"),
            }
            if stored.get("join"):
                responses["JOIN"] = {
                    "state": "DELIVERED",
                    "response_message_id": stored["join"]["message_id"],
                    "answer": stored["join"]["content"],
                }
        except Exception as error:
            threads("conversation_chat_record_failure", {
                "conversation_id": conversation_id,
                "request_message_id": leg["message_id"],
                "error_class": type(error).__name__,
            })
            responses["LOCAL"] = {"state": "FAILED", "error_class": type(error).__name__}

    state = (
        "LOCAL_COMPLETE" if plan["route"] == "LOCAL" and responses.get("LOCAL", {}).get("state") == "DELIVERED"
        else "SAAS_QUEUED" if plan["route"] == "SAAS" and saas_handoff
        else "DUAL_WAITING" if plan["route"] == "DUAL" and saas_handoff
        else "PARTIAL_OR_FAILED"
    )
    return {
        "conversation_id": conversation_id,
        "binding_epoch": plan["binding_epoch"],
        "route": plan["route"],
        "state": state,
        "correlation_id": plan["correlation_id"],
        "causation_id": plan["causation_id"],
        "context_digest": plan["context_digest"],
        "shared_context_digest": plan["shared_context_digest"],
        "legs": plan["legs"],
        "responses": responses,
        "saas_handoff": saas_handoff,
        "idempotent_replay": plan["idempotent_replay"],
        "authority_effect": "NONE",
    }


def deliver_saas_once(threads, control) -> list[dict[str, Any]]:
    delivered = []
    batch = threads("conversation_chat_saas_candidates", {"limit": 128})
    for candidate in batch.get("candidates") or []:
        try:
            result = control("saas_request_status", {"request_id": candidate["request_id"]})
            status = str(result.get("status") or "").upper()
            if status in TERMINAL_SAAS_NO_RESPONSE:
                threads("conversation_chat_close_saas_terminal", {
                    "request_id": candidate["request_id"],
                    "broker_status": status,
                })
                continue
            if status != "RESPONDED" or not result.get("receipt_digest"):
                continue
            if result.get("thread_id") not in (None, ""):
                raise ConversationConflict("conversation SaaS request unexpectedly bound to legacy thread")
            response_meta = json.loads(result.get("response_meta_json") or "{}")
            if not isinstance(response_meta, dict):
                response_meta = {}
            response_meta = {
                **response_meta,
                "receipt_digest": result["receipt_digest"],
                "saas_request_id": candidate["request_id"],
                "authority_effect": "NONE",
            }
            saved = threads("conversation_chat_complete_saas", {
                "request_id": candidate["request_id"],
                "response_text": result.get("response_text"),
                "response_meta": response_meta,
            })
            delivered.append(saved)
        except (ConversationDomainError, ConversationConflict, ConversationNotFound, ValueError, OSError) as error:
            LOGGER.warning(
                "Conversation SaaS delivery deferred request=%s error_class=%s",
                candidate.get("request_id"),
                type(error).__name__,
            )
    return delivered


def delivery_loop(threads, control, stop) -> None:
    while not stop.is_set():
        try:
            deliver_saas_once(threads, control)
        except Exception as error:
            LOGGER.warning(
                "Conversation SaaS delivery scan deferred error_class=%s",
                type(error).__name__,
            )
        stop.wait(1)

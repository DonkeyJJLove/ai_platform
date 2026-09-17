"""Persistent mission/channel bindings and operator-message correlation for LION chat."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import re
import sqlite3
import time

_CHANNELS = frozenset({"LOCAL", "LION_OPERATOR", "SAAS", "DUAL"})
_THREAD_RE = re.compile(r"^[0-9a-f]{32}$")
_CLIENT_RE = re.compile(r"^[0-9a-f]{32}$")
_TARGET_RE = re.compile(r"^(?:mission:[A-Za-z0-9._:-]{1,128}|swarm:[A-Za-z0-9._:-]{1,128}|group:(?:architecture|security|runtime)|drone:[A-Za-z0-9._:-]{1,180})$")


def _canon(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _thread_id(value: str) -> str:
    value = str(value or "")
    if not _THREAD_RE.fullmatch(value):
        raise ValueError("thread_id")
    return value


def _thread_db_path(gateway) -> Path:
    provider = getattr(gateway, "thread_provider", None)
    path = getattr(provider, "path", None)
    if path is None:
        raise RuntimeError("thread store path unavailable")
    return Path(path).resolve()


def _connect(gateway):
    conn = sqlite3.connect(_thread_db_path(gateway), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate(conn)
    return conn


def _migrate(conn) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS thread_channel_bindings(
          thread_id TEXT PRIMARY KEY,
          mission_id TEXT,
          channel TEXT NOT NULL,
          target TEXT,
          updated_at REAL NOT NULL,
          FOREIGN KEY(thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS thread_operator_requests(
          client_request_id TEXT PRIMARY KEY,
          thread_id TEXT NOT NULL,
          mission_id TEXT NOT NULL,
          command_id TEXT NOT NULL UNIQUE,
          operator_message_id TEXT,
          target TEXT NOT NULL,
          content_digest TEXT NOT NULL,
          state TEXT NOT NULL,
          receipt_digest TEXT,
          created_at REAL NOT NULL,
          updated_at REAL NOT NULL,
          FOREIGN KEY(thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_thread_operator_requests_thread
          ON thread_operator_requests(thread_id, created_at);
        """
    )
    conn.commit()


def _ensure_thread(conn, thread_id: str) -> None:
    if conn.execute("SELECT 1 FROM threads WHERE thread_id=?", (thread_id,)).fetchone() is None:
        raise KeyError("thread not found")


def _binding_get(gateway, thread_id: str):
    thread_id = _thread_id(thread_id)
    conn = _connect(gateway)
    try:
        _ensure_thread(conn, thread_id)
        row = conn.execute(
            "SELECT thread_id,mission_id,channel,target,updated_at FROM thread_channel_bindings WHERE thread_id=?",
            (thread_id,),
        ).fetchone()
        if row is None:
            return {
                "thread_id": thread_id,
                "mission_id": None,
                "channel": "LOCAL",
                "target": None,
                "persisted": False,
                "control_lane": "OPERATOR_BUS",
                "ingress": "PANEL_PROXY_WHEN_PAIRED",
                "browser_transport": False,
                "authority_effect": "NONE",
            }
        out = dict(row)
        out.update(
            persisted=True,
            control_lane="OPERATOR_BUS",
            ingress="PANEL_PROXY_WHEN_PAIRED",
            browser_transport=out["channel"] in {"SAAS", "DUAL"},
            authority_effect="NONE",
        )
        return out
    finally:
        conn.close()


def _validate_target(mission_id: str | None, target: str | None) -> str | None:
    if target in (None, ""):
        return "mission:" + mission_id if mission_id else None
    target = str(target).strip()
    if not _TARGET_RE.fullmatch(target):
        raise ValueError("operator target")
    if target.startswith("mission:") or target.startswith("swarm:"):
        if mission_id and target.split(":", 1)[1] != mission_id:
            raise ValueError("target mission mismatch")
    return target


def _binding_put(gateway, thread_id: str, value: dict):
    thread_id = _thread_id(thread_id)
    if type(value) is not dict:
        raise ValueError("binding schema")
    if set(value) - {"mission_id", "channel", "target"}:
        raise ValueError("binding schema")
    channel = str(value.get("channel") or "LOCAL").upper()
    if channel not in _CHANNELS:
        raise ValueError("channel")
    mission_id = value.get("mission_id")
    if mission_id is not None:
        mission_id = str(mission_id).strip()
        if not mission_id or len(mission_id) > 128 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", mission_id):
            raise ValueError("mission_id")
        control = getattr(gateway, "control_provider", None)
        if not callable(control):
            raise RuntimeError("mission control unavailable")
        control("process", {"mission_id": mission_id})
    if channel == "LION_OPERATOR" and not mission_id:
        raise ValueError("LION_OPERATOR requires mission binding")
    target = _validate_target(mission_id, value.get("target"))
    now = time.time()
    conn = _connect(gateway)
    try:
        _ensure_thread(conn, thread_id)
        conn.execute(
            "INSERT INTO thread_channel_bindings(thread_id,mission_id,channel,target,updated_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(thread_id) DO UPDATE SET mission_id=excluded.mission_id,channel=excluded.channel,target=excluded.target,updated_at=excluded.updated_at",
            (thread_id, mission_id, channel, target, now),
        )
        conn.commit()
    finally:
        conn.close()
    return _binding_get(gateway, thread_id)


def _binding_delete(gateway, thread_id: str):
    thread_id = _thread_id(thread_id)
    conn = _connect(gateway)
    try:
        _ensure_thread(conn, thread_id)
        conn.execute("DELETE FROM thread_channel_bindings WHERE thread_id=?", (thread_id,))
        conn.commit()
    finally:
        conn.close()
    return _binding_get(gateway, thread_id)


def _begin_operator_request(gateway, thread_id: str, mission_id: str, target: str, client_request_id: str, message: str):
    thread_id = _thread_id(thread_id)
    client_request_id = str(client_request_id or "")
    if not _CLIENT_RE.fullmatch(client_request_id):
        raise ValueError("client_request_id")
    message = str(message or "").strip()
    if not message or len(message) > 8000:
        raise ValueError("message")
    digest = sha256(message.encode("utf-8")).hexdigest()
    command_id = "panel-chat-" + client_request_id
    now = time.time()
    conn = _connect(gateway)
    try:
        conn.execute("BEGIN IMMEDIATE")
        _ensure_thread(conn, thread_id)
        existing = conn.execute("SELECT * FROM thread_operator_requests WHERE client_request_id=?", (client_request_id,)).fetchone()
        if existing is not None:
            existing = dict(existing)
            if existing["thread_id"] != thread_id or existing["mission_id"] != mission_id or existing["target"] != target or existing["content_digest"] != digest:
                raise ValueError("client_request_id conflict")
            conn.commit()
            return existing, True
        seq = int(conn.execute("SELECT COALESCE(MAX(seq),0) FROM messages WHERE thread_id=?", (thread_id,)).fetchone()[0])
        title_row = conn.execute("SELECT title FROM threads WHERE thread_id=?", (thread_id,)).fetchone()
        meta = {"operator_client_request_id": client_request_id, "mission_id": mission_id, "channel": "LION_OPERATOR", "target": target}
        conn.execute(
            "INSERT INTO messages(message_id,thread_id,seq,role,content,created_at,meta_json) VALUES(?,?,?,?,?,?,?)",
            (client_request_id, thread_id, seq + 1, "user", message, now, _canon(meta)),
        )
        title = title_row["title"]
        if title == "Nowa rozmowa":
            title = " ".join(message.split())[:64] or title
        conn.execute("UPDATE threads SET title=?,updated_at=? WHERE thread_id=?", (title, now, thread_id))
        conn.execute(
            "INSERT INTO thread_operator_requests(client_request_id,thread_id,mission_id,command_id,operator_message_id,target,content_digest,state,receipt_digest,created_at,updated_at) VALUES(?,?,?,?,NULL,?,?,?,NULL,?,?)",
            (client_request_id, thread_id, mission_id, command_id, target, digest, "SUBMITTING", now, now),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM thread_operator_requests WHERE client_request_id=?", (client_request_id,)).fetchone()), False
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _update_request(gateway, client_request_id: str, **fields):
    allowed = {"operator_message_id", "state", "receipt_digest"}
    if set(fields) - allowed:
        raise ValueError("request update fields")
    if not fields:
        return
    conn = _connect(gateway)
    try:
        conn.execute(
            "UPDATE thread_operator_requests SET operator_message_id=COALESCE(?,operator_message_id),state=COALESCE(?,state),receipt_digest=COALESCE(?,receipt_digest),updated_at=? WHERE client_request_id=?",
            (fields.get("operator_message_id"), fields.get("state"), fields.get("receipt_digest"), time.time(), client_request_id),
        )
        conn.commit()
    finally:
        conn.close()


def _thread_requests(gateway, thread_id: str):
    conn = _connect(gateway)
    try:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM thread_operator_requests WHERE thread_id=? AND state NOT IN ('COMPLETE','NO_RECIPIENT','REJECTED') ORDER BY created_at",
            (_thread_id(thread_id),),
        )]
    finally:
        conn.close()


def _operator_submit(gateway, session_token: str, thread_id: str, message: str, client_request_id: str):
    binding = _binding_get(gateway, thread_id)
    if binding.get("channel") != "LION_OPERATOR" or not binding.get("mission_id"):
        raise ValueError("thread is not bound to LION_OPERATOR mission channel")
    target = binding.get("target") or ("mission:" + binding["mission_id"])
    request, _ = _begin_operator_request(gateway, thread_id, binding["mission_id"], target, client_request_id, message)
    command = {
        "command_id": request["command_id"],
        "mission_id": binding["mission_id"],
        "action": "MESSAGE",
        "target": target,
        "payload": {"content": message.strip()},
        "__session_token": session_token,
    }
    try:
        result = gateway.operator_provider("command", command)
    except Exception:
        _update_request(gateway, client_request_id, state="UNKNOWN_RECONCILE_BY_COMMAND_ID")
        raise
    operator_message_id = ((result.get("result") or {}).get("message_id") if isinstance(result, dict) else None)
    receipt_digest = result.get("receipt_digest") or ((result.get("receipt") or {}).get("receipt_digest") if isinstance(result, dict) else None)
    state = "PERSISTED" if result.get("admission_state") == "ACCEPTED" else "REJECTED"
    _update_request(gateway, client_request_id, operator_message_id=operator_message_id, receipt_digest=receipt_digest, state=state)
    return {
        "schema": "lion.thread-operator-chat/v1",
        "thread_id": thread_id,
        "mission_id": binding["mission_id"],
        "target": target,
        "channel": "LION_OPERATOR",
        "client_request_id": client_request_id,
        "command_id": request["command_id"],
        "operator_message_id": operator_message_id,
        "admission_state": result.get("admission_state"),
        "execution_state": result.get("execution_state"),
        "observation_state": result.get("observation_state"),
        "receipt_digest": receipt_digest,
        "idempotent": bool(result.get("idempotent")),
        "browser_transport": False,
        "authority_effect": "NONE",
    }


def _poll_operator(gateway, session_token: str, thread_id: str):
    binding = _binding_get(gateway, thread_id)
    mission_id = binding.get("mission_id")
    if not mission_id:
        return {"thread_id": thread_id, "responses": [], "requests": [], "authority_effect": "NONE"}
    projection = gateway.operator_provider("state", {"mission_id": mission_id, "session_token": session_token})
    events = gateway.operator_provider("events", {"mission_id": mission_id, "after": 0, "limit": 200, "session_token": session_token})
    messages = {row.get("message_id"): row for row in (projection.get("messages") or []) if row.get("message_id")}
    deliveries = projection.get("message_deliveries") or []
    new_responses = []
    states = []
    for request in _thread_requests(gateway, thread_id):
        outbound_id = request.get("operator_message_id")
        outbound = messages.get(outbound_id) if outbound_id else None
        response_ids = []
        for event in events.get("events") or []:
            payload = event.get("payload") or {}
            if event.get("event_type") == "OPERATOR_MESSAGE_APPLIED" and outbound_id and outbound_id in (payload.get("message_ids") or []):
                response_ids.extend(payload.get("response_message_ids") or [])
        if outbound and outbound.get("applied_assignment_id"):
            assignment_id = outbound.get("applied_assignment_id")
            response_ids.extend(
                row.get("message_id") for row in messages.values()
                if row.get("kind") == "RESPONSE" and row.get("applied_assignment_id") == assignment_id
            )
        seen = set()
        request_new_responses = 0
        for response_id in response_ids:
            if not response_id or response_id in seen:
                continue
            seen.add(response_id)
            response = messages.get(response_id)
            if not response or response.get("kind") != "RESPONSE" or not str(response.get("content") or "").strip():
                continue
            from_participant = str(response.get("from_participant") or "LION")
            content = str(response.get("content") or "").strip()
            rendered = f"**{from_participant}**\n\n{content}"
            stored = gateway.thread_provider(
                "append_assistant_once",
                {
                    "thread_id": thread_id,
                    "assistant": rendered,
                    "dedupe_key": "operator:" + response_id,
                    "meta": {
                        "delivery_kind": "OPERATOR_RESPONSE",
                        "operator_response_message_id": response_id,
                        "operator_request_message_id": outbound_id,
                        "mission_id": mission_id,
                        "channel": "LION_OPERATOR",
                        "from_participant": from_participant,
                    },
                },
            )
            if stored.get("inserted"):
                new_responses.append({"message_id": response_id, "from_participant": from_participant, "content": rendered})
                request_new_responses += 1
        ds = [d for d in deliveries if d.get("message_id") == outbound_id]
        no_recipient = bool(outbound and outbound.get("state") == "PERSISTED_NO_CURRENT_RECIPIENT")
        all_applied = bool(ds) and all(d.get("delivery_state") == "APPLIED" for d in ds)
        if no_recipient:
            state = "NO_RECIPIENT"
        elif all_applied:
            state = "COMPLETE"
        elif request_new_responses:
            state = "PARTIAL"
        else:
            state = request.get("state") or "WAITING"
        _update_request(gateway, request["client_request_id"], state=state)
        states.append({
            "client_request_id": request["client_request_id"],
            "command_id": request["command_id"],
            "operator_message_id": outbound_id,
            "state": state,
            "receipt_digest": request.get("receipt_digest"),
        })
    return {
        "schema": "lion.thread-operator-poll/v1",
        "thread_id": thread_id,
        "mission_id": mission_id,
        "responses": new_responses,
        "requests": states,
        "control": projection.get("control"),
        "browser_transport": False,
        "authority_effect": "NONE",
    }
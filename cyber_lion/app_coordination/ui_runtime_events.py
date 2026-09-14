"""Durable, bounded frontend diagnostics; reports never authorize effects."""
from __future__ import annotations

import json
import re
import time


def migrate(connection):
    if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise ValueError('UI event migration: database integrity failure')
    with connection:
        connection.execute('''CREATE TABLE IF NOT EXISTS ui_runtime_events (
            event_id TEXT PRIMARY KEY, received_at REAL NOT NULL,
            event_class TEXT NOT NULL, payload_json TEXT NOT NULL)''')
        connection.execute('''CREATE TABLE IF NOT EXISTS ui_event_migrations (
            version INTEGER PRIMARY KEY, applied_at REAL NOT NULL)''')
        connection.execute('INSERT OR IGNORE INTO ui_event_migrations VALUES(1,?)', (time.time(),))
    if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise ValueError('UI event migration: database integrity failure')


def record(connection, event):
    fields = {'event_id', 'event_class', 'operation', 'error_name', 'message', 'thread_id'}
    if type(event) is not dict or set(event) != fields:
        raise ValueError('UI runtime event schema')
    if event['event_class'] != 'UI_RUNTIME_ERROR':
        raise ValueError('UI event class')
    if not isinstance(event['event_id'], str) or not re.fullmatch(r'[0-9a-f-]{36}', event['event_id']):
        raise ValueError('UI event identity')
    for key, limit in [('operation', 80), ('error_name', 80), ('message', 500), ('thread_id', 32)]:
        if not isinstance(event[key], str) or len(event[key]) > limit:
            raise ValueError('UI event field: ' + key)
    payload = {**event, 'authority_effect': 'NONE', 'source': 'UNTRUSTED_BROWSER_REPORT'}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    with connection:
        existing = connection.execute('SELECT payload_json FROM ui_runtime_events WHERE event_id=?', (event['event_id'],)).fetchone()
        if existing is not None:
            if existing[0] != encoded:
                raise ValueError('UI event identity collision')
            return {'event_id': event['event_id'], 'recorded': True, 'duplicate': True}
        connection.execute('INSERT INTO ui_runtime_events VALUES(?,?,?,?)',
                           (event['event_id'], time.time(), event['event_class'], encoded))
    return {'event_id': event['event_id'], 'recorded': True, 'duplicate': False}

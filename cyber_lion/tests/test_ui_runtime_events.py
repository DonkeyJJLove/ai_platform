import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from cyber_lion.app_coordination import ui_runtime_events
from tools.lion_local_intelligence_runtime import ThreadStore


def browser_event(**changes):
    return {
        'event_id': 'ea10990c-4ac8-427e-9d03-764a3ab59cba',
        'event_class': 'UI_RUNTIME_ERROR',
        'operation': 'load_threads',
        'error_name': 'TypeError',
        'message': 'Unable to render conversation',
        'thread_id': '',
        **changes,
    }


class UiRuntimeEventsTests(unittest.TestCase):
    def test_extended_error_context_is_persisted_without_raw_stack(self):
        with closing(sqlite3.connect(':memory:')) as conn:
            ui_runtime_events.migrate(conn)
            event=browser_event(error_id='ea10990c-4ac8-427e-9d03-764a3ab59cba',component='LPCL_PANEL',error_class='TypeError',stack_digest='a'*64,timestamp='2026-09-15T00:00:00Z',request_id='saas-'+'b'*32,frontend_revision='c'*64)
            ui_runtime_events.record(conn,event)
            saved=json.loads(conn.execute('SELECT payload_json FROM ui_runtime_events').fetchone()[0])
            for field in ('error_id','component','error_class','stack_digest','timestamp','request_id','frontend_revision'):
                self.assertEqual(saved[field],event[field])
            self.assertNotIn('stack',saved)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'threads.db'

    def test_migration_preserves_existing_data_and_integrity(self):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute('CREATE TABLE existing_data(value TEXT NOT NULL)')
            conn.execute('INSERT INTO existing_data VALUES(?)', ('retain me',))
            conn.commit()
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            ui_runtime_events.migrate(conn)
            applied_at = conn.execute('SELECT applied_at FROM ui_event_migrations WHERE version=1').fetchone()[0]
            ui_runtime_events.migrate(conn)
            self.assertEqual(conn.execute('SELECT value FROM existing_data').fetchall(), [('retain me',)])
            self.assertEqual(conn.execute('SELECT version,applied_at FROM ui_event_migrations').fetchall(), [(1, applied_at)])
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_record_survives_reopen_and_marks_untrusted_source(self):
        event = browser_event(message='Zażółć: display failed')
        with closing(sqlite3.connect(self.path)) as conn:
            ui_runtime_events.migrate(conn)
            result = ui_runtime_events.record(conn, event)
            self.assertEqual(result, {'event_id': event['event_id'], 'recorded': True, 'duplicate': False})
        with closing(sqlite3.connect(self.path)) as conn:
            row = conn.execute('SELECT event_class,payload_json FROM ui_runtime_events').fetchone()
            self.assertEqual(row[0], 'UI_RUNTIME_ERROR')
            payload = json.loads(row[1])
            self.assertEqual(payload['message'], event['message'])
            self.assertEqual(payload['authority_effect'], 'NONE')
            self.assertEqual(payload['source'], 'UNTRUSTED_BROWSER_REPORT')
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_repeat_after_reopen_is_idempotent_and_preserves_timestamp(self):
        event = browser_event()
        with closing(sqlite3.connect(self.path)) as conn:
            ui_runtime_events.migrate(conn)
            ui_runtime_events.record(conn, event)
            original = conn.execute('SELECT * FROM ui_runtime_events').fetchone()
        with closing(sqlite3.connect(self.path)) as conn:
            # Reordering a JSON object's fields must not create another report.
            duplicate = ui_runtime_events.record(conn, dict(reversed(list(event.items()))))
            self.assertTrue(duplicate['duplicate'])
            self.assertEqual(conn.execute('SELECT * FROM ui_runtime_events').fetchall(), [original])

    def test_conflicting_identity_is_rejected_without_overwriting_event(self):
        with closing(sqlite3.connect(self.path)) as conn:
            ui_runtime_events.migrate(conn)
            ui_runtime_events.record(conn, browser_event())
            original = conn.execute('SELECT * FROM ui_runtime_events').fetchone()
            with self.assertRaisesRegex(ValueError, 'identity collision'):
                ui_runtime_events.record(conn, browser_event(message='different report'))
            self.assertEqual(conn.execute('SELECT * FROM ui_runtime_events').fetchall(), [original])
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_malformed_reports_do_not_persist(self):
        invalid = [None, [], {}, browser_event(event_id='invalid'),
                   browser_event(event_class='AUTHORITY_GRANTED'),
                   {**browser_event(), 'authority_effect': 'GRANTED'}]
        missing = browser_event()
        del missing['message']
        invalid.append(missing)
        for field, limit in [('operation', 80), ('error_name', 80), ('message', 500), ('thread_id', 32)]:
            invalid.extend([browser_event(**{field: 1}), browser_event(**{field: 'x' * (limit + 1)})])
        with closing(sqlite3.connect(self.path)) as conn:
            ui_runtime_events.migrate(conn)
            for event in invalid:
                with self.subTest(event=event), self.assertRaises(ValueError):
                    ui_runtime_events.record(conn, event)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM ui_runtime_events').fetchone()[0], 0)
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_thread_store_reopen_preserves_conversation_and_ui_events(self):
        store = ThreadStore(self.path)
        thread = store('create', {'title': 'Durable conversation'})
        store('append_pair', {'thread_id': thread['thread_id'], 'user': 'Question', 'assistant': 'Answer'})
        event = browser_event(thread_id=thread['thread_id'])
        self.assertFalse(store('ui_runtime_event', event)['duplicate'])
        reopened = ThreadStore(self.path)
        self.assertTrue(reopened('ui_runtime_event', event)['duplicate'])
        self.assertEqual([message['content'] for message in reopened('get', {'thread_id': thread['thread_id']})['messages']], ['Question', 'Answer'])
        with self.assertRaises(ValueError):
            reopened('ui_runtime_event', browser_event(thread_id=thread['thread_id'], operation='different'))
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM ui_runtime_events').fetchone()[0], 1)
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(), [])


if __name__ == '__main__':
    unittest.main()

from contextlib import closing
import importlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import lion_mission_control_compat

with patch.dict(sys.modules, {'mission_control_compat': lion_mission_control_compat}):
    service = importlib.import_module('tools.lion_mission_control_v3')


class MissionFocusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(service, 'DB', Path(self.temp.name)/'focus.db')
        self.db_patch.start()
        with patch.object(service, 'import_legacy'):
            service.migrate()
        with closing(service.connect()) as conn, conn:
            row = list(conn.execute('SELECT * FROM missions WHERE mission_id=?',(service.MISSION,)).fetchone())
            row[0] = 'historical';row[2] = 'LEGACY_OBSERVATION:fixture';row[7] = 'RECORDED_PASS'
            conn.execute('INSERT INTO missions VALUES('+','.join('?' for _ in row)+')',row)

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def protected_state(self):
        with closing(service.connect()) as conn, conn:
            names=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('mission_meta','mission_events','mission_action_receipts','sqlite_sequence') ORDER BY name")]
            return {name:[tuple(r) for r in conn.execute('SELECT * FROM "'+name+'"')] for name in names}

    def ledger(self):
        with closing(service.connect()) as conn, conn:
            return {name:[tuple(r) for r in conn.execute('SELECT * FROM '+name)] for name in ('mission_meta','mission_events','mission_action_receipts')}

    def test_historical_and_current_focus_only_with_atomic_readback(self):
        before = self.protected_state()
        for mid in ('historical',service.MISSION):
            with self.subTest(mid=mid):
                out = service.set_focus_mission(mid,{})
                self.assertEqual(out['focus_mission_id'],mid)
                self.assertEqual(out['readback']['mission_id'],mid)
                self.assertEqual(out['authority_effect'],'NONE')
                self.assertTrue(out['changed'])
                self.assertEqual(service.focus_mission_id(),mid)
                self.assertEqual(self.protected_state(),before)
                receipt_id=out['receipt']['receipt_id']
                self.assertTrue(any(r['receipt_id']==receipt_id for r in out['readback']['action_receipts']))
                with closing(service.connect()) as conn, conn:
                    row=conn.execute('SELECT * FROM mission_action_receipts WHERE receipt_id=?',(receipt_id,)).fetchone()
                    self.assertEqual((row['action'],row['effect_class'],row['status']),('FOCUS','CONTROL_DB_METADATA_ONLY','PASS'))
                    self.assertEqual(json.loads(row['result_json'])['authority_effect'],'NONE')
                ledger=self.ledger()
                replay=service.set_focus_mission(mid,{})
                self.assertFalse(replay['changed'])
                self.assertIsNone(replay['receipt'])
                self.assertEqual(self.ledger(),ledger)

    def test_unknown_or_nonempty_request_has_no_effects(self):
        before=(self.protected_state(),self.ledger())
        for mid,request in [('missing',{}),('historical',{'activate':True})]:
            with self.assertRaises(ValueError):
                service.set_focus_mission(mid,request)
            self.assertEqual((self.protected_state(),self.ledger()),before)

    def test_receipt_failure_rolls_back_focus_and_event(self):
        with closing(service.connect()) as conn, conn:
            conn.execute("CREATE TRIGGER reject_focus_receipt BEFORE INSERT ON mission_action_receipts WHEN NEW.action='FOCUS' BEGIN SELECT RAISE(ABORT,'test receipt failure'); END")
        before=(self.protected_state(),self.ledger())
        with self.assertRaisesRegex(sqlite3.IntegrityError,'test receipt failure'):
            service.set_focus_mission('historical',{})
        self.assertEqual((self.protected_state(),self.ledger()),before)

    def test_http_route_accepts_empty_body_object_without_activation(self):
        handler=object.__new__(service.H)
        handler.path='/api/v3/missions/historical/focus'
        handler.headers={'Content-Length':'2','Content-Type':'application/json'}
        handler.rfile=io.BytesIO(b'{}')
        handler.json=lambda payload,*args:payload
        with patch.object(service,'driver_activate') as activate:
            out=handler.do_POST()
        activate.assert_not_called()
        self.assertEqual(out['focus_mission_id'],'historical')
        self.assertEqual(out['authority_effect'],'NONE')


if __name__ == '__main__':
    unittest.main()

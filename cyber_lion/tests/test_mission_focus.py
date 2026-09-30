from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import threading
import importlib
import io
import json
import sqlite3
import sys
import tempfile
import urllib.request
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
                self.assertEqual(service.focus_mission_id('history' if mid=='historical' else 'operational'),mid)
                if mid=='historical':self.assertEqual(service.focus_mission_id(),service.MISSION)
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

    def test_concurrent_recent_reads_share_inflight_work_without_retaining_cache(self):
        original=service._read_recent_process_missions
        started=threading.Event();release=threading.Event();owner=[]
        def held_read(view='operational'):
            owner.append(threading.get_ident())
            started.set()
            if not release.wait(5):raise RuntimeError('test release timeout')
            return original(view)
        with patch.object(service,'_read_recent_process_missions',side_effect=held_read) as read:
            with ThreadPoolExecutor(max_workers=8) as pool:
                first=pool.submit(service.recent_process_missions)
                self.assertTrue(started.wait(2))
                pending=service.RECENT_PROJECTION_PENDING['operational']
                joined=threading.Barrier(8)
                result=pending.result
                def joined_result():
                    if threading.get_ident()!=owner[0]:joined.wait(timeout=5)
                    return result()
                with patch.object(pending,'result',side_effect=joined_result):
                    others=[pool.submit(service.recent_process_missions) for _ in range(7)]
                    joined.wait(timeout=5);release.set()
                    values=[f.result(timeout=5) for f in others]
                values.append(first.result(timeout=5))
            self.assertEqual(read.call_count,1)
        self.assertTrue(all(value==values[0] for value in values))
        values[0][0]['title']='client-local edit'
        self.assertNotEqual(values[0],values[1])
        with closing(service.connect()) as conn,conn:
            conn.execute('UPDATE missions SET title=? WHERE mission_id=?',('fresh title','historical'))
        self.assertEqual(next(r for r in service.recent_process_missions('history') if r['mission_id']=='historical')['title'],'fresh title')

    def test_failed_recent_read_does_not_poison_next_read(self):
        with patch.object(service,'_read_recent_process_missions',side_effect=ValueError('read failure')):
            with self.assertRaisesRegex(ValueError,'read failure'):service.recent_process_missions()
        self.assertEqual(len(service.recent_process_missions()),1)
        self.assertEqual(len(service.recent_process_missions('all')),2)

    def test_concurrent_http_recent_reads_do_not_contend_on_journal_mode(self):
        with closing(service.connect()) as conn:
            self.assertEqual(conn.execute('PRAGMA journal_mode').fetchone()[0].lower(),'wal')
        server=service.FleetThreadingHTTPServer(('127.0.0.1',0),service.H)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_address[1]}/api/v3/missions/recent?view=all'
        gate=threading.Barrier(7)
        def read_recent():
            gate.wait(timeout=3)
            with urllib.request.urlopen(url,timeout=3) as response:
                return json.load(response)
        try:
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures=[pool.submit(read_recent) for _ in range(6)]
                gate.wait(timeout=3)
                values=[future.result(timeout=4) for future in futures]
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
        self.assertEqual([len(value['missions']) for value in values],[2]*6)

    def test_recent_summary_matches_detail_without_full_snapshot(self):
        detail=service.process_snapshot(service.MISSION,read_only=True)
        expected=detail['mission_summary']
        lifecycle=detail['lifecycle']
        with patch.object(service,'process_snapshot',side_effect=AssertionError('recent must not build full process snapshot')):
            row=next(x for x in service.recent_process_missions('operational') if x['mission_id']==service.MISSION)
        for key in (
            'mission_id','title','adapter','state','runtime_state','objective',
            'current_phase','current_phase_reason','progress','authority_state',
            'normalized_schema_version','projection_version','controllable',
        ):
            self.assertEqual(row.get(key),expected.get(key),key)
        for key in (
            'lifecycle_class','record_class','operational','historical','legacy',
            'execution_controls_allowed','history_reason',
        ):
            self.assertEqual(row.get(key),lifecycle.get(key),key)


if __name__ == '__main__':
    unittest.main()

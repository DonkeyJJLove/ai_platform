from copy import deepcopy
import unittest
import sqlite3
import tempfile
from pathlib import Path
from contextlib import closing
from unittest.mock import Mock, patch
import importlib
import sys

from cyber_lion.mission_control.phase_control import phase_capabilities, apply_phase_action, fence_phase_action


def active():
    return {'mission_id': 'test', 'adapter': 'LPCL_MISSION', 'state': 'RUNNING', 'source_head': 'a'*40, 'source_tree': 'b'*40, 'process': {'current_phase': 'ONE', 'authority_state': 'EXPLICIT_USER_ACTIVATION'}, 'execution_driver': {'driver_id': 'driver', 'generation': 1, 'state': 'ACTIVE', 'current_phase': 'ONE'}, 'phases': [{'phase_id': 'ONE', 'status': 'RUNNING'}], 'phase_execution_specs': [{'phase_id': 'ONE', 'handler_id': 'VERIFY_PHASE_PLAN'}]}


class PhaseControlTests(unittest.TestCase):
    def request(self, snapshot, action='PAUSE'):
        return {'phase_id': 'ONE', 'action': action, 'control_token': phase_capabilities(snapshot, 'ONE')[action]['control_token']}

    def test_only_containment_actions_are_projected(self):
        caps = phase_capabilities(active(), 'ONE')
        self.assertEqual(set(caps), {'INSPECT', 'PAUSE', 'STOP'})
        self.assertTrue(caps['PAUSE']['supported'])
        self.assertTrue(caps['STOP']['supported'])
        self.assertEqual(caps['PAUSE']['effect'], 'CONTROL_STATE')

    def test_stale_generation_source_or_phase_token_prevents_action(self):
        for kind in ('generation', 'source', 'phase'):
            snapshot = active(); request = self.request(snapshot)
            if kind == 'generation': snapshot['execution_driver']['generation'] += 1
            elif kind == 'source': snapshot['source_head'] = 'c'*40
            else: snapshot['process']['current_phase'] = 'TWO'
            mutate = Mock()
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                apply_phase_action('test', request, lambda _: snapshot, mutate)
            mutate.assert_not_called()

    def test_historical_inactive_unactivated_and_unknown_handler_fail_closed(self):
        for kind in ('historical', 'activation', 'handler', 'source', 'driver', 'verdict'):
            snapshot = active()
            if kind == 'historical': snapshot['adapter'] = 'LEGACY_OBSERVATION:VKT'
            elif kind == 'activation': snapshot['process']['authority_state'] = 'NONE'
            elif kind == 'handler': snapshot['phase_execution_specs'][0]['handler_id'] = 'UNKNOWN'
            elif kind == 'source': snapshot['source_tree'] = None
            elif kind == 'driver': snapshot['execution_driver']['state'] = 'COMPLETE'
            else: snapshot['phases'][0]['status'] = 'PASS'
            with self.subTest(kind=kind):
                self.assertFalse(phase_capabilities(snapshot, 'ONE')['PAUSE']['supported'])
                mutate = Mock()
                with self.assertRaises(ValueError):
                    apply_phase_action('test', {'phase_id': 'ONE', 'action': 'PAUSE', 'control_token': 'x'}, lambda _: snapshot, mutate)
                mutate.assert_not_called()

    def test_receipt_and_state_readback_required_without_phase_verdict_mutation(self):
        for action, expected in [('PAUSE', 'PAUSED'), ('STOP', 'STOPPED')]:
            before = active(); after = deepcopy(before)
            after['execution_driver']['state'] = expected
            receipt = {'receipt_id': 'receipt1', 'receipt_digest': 'd'*64}
            after['action_receipts'] = [{**receipt, 'action': action, 'status': 'PASS'}]
            reads = Mock(side_effect=[before, after])
            mutate = Mock(return_value={'receipt': receipt, 'action': action, 'status': 'PASS'})
            with self.subTest(action=action):
                result = apply_phase_action('test', self.request(before, action), reads, mutate)
                self.assertEqual(result['readback']['driver_state'], expected)
                self.assertEqual(result['readback']['phase_status'], 'RUNNING')
                self.assertEqual(mutate.call_args.args[1]['action'], action)
                self.assertNotIn('status', mutate.call_args.args[1])

    def test_missing_receipt_wrong_state_and_changed_verdict_never_report_success(self):
        for kind in ('receipt', 'state', 'verdict'):
            before = active(); after = deepcopy(before)
            after['execution_driver']['state'] = 'PAUSED'
            receipt = {'receipt_id': 'receipt1', 'receipt_digest': 'd'*64}
            after['action_receipts'] = [{**receipt, 'action': 'PAUSE', 'status': 'PASS'}]
            if kind == 'receipt': after['action_receipts'] = []
            elif kind == 'state': after['execution_driver']['state'] = 'ACTIVE'
            else: after['phases'][0]['status'] = 'PASS'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                apply_phase_action('test', self.request(before), Mock(side_effect=[before, after]), Mock(return_value={'receipt': receipt}))

    def test_start_resume_retry_are_never_dispatched(self):
        mutate = Mock(); read = Mock()
        for action in ('START', 'RESUME', 'RETRY', 'SKIP'):
            with self.subTest(action=action), self.assertRaises(ValueError):
                apply_phase_action('test', {'phase_id': 'ONE', 'action': action, 'control_token': 'x'}, read, mutate)
        read.assert_not_called(); mutate.assert_not_called()

    def test_cross_connection_stale_fence_and_writer_reservation(self):
        snapshot = active()
        with tempfile.TemporaryDirectory() as directory:
            with closing(sqlite3.connect(Path(directory)/'control.db', timeout=.05)) as first, closing(sqlite3.connect(Path(directory)/'control.db', timeout=.05)) as second:
                first.row_factory = sqlite3.Row; second.row_factory = sqlite3.Row
                first.executescript('''
                  CREATE TABLE missions(mission_id TEXT,adapter TEXT,state TEXT,source_head TEXT,source_tree TEXT);
                  CREATE TABLE mission_process_specs(mission_id TEXT,current_phase TEXT,authority_state TEXT);
                  CREATE TABLE mission_execution_drivers(mission_id TEXT,driver_id TEXT,generation INTEGER,state TEXT,current_phase TEXT);
                  CREATE TABLE mission_phases(mission_id TEXT,phase_id TEXT,status TEXT);
                  CREATE TABLE mission_phase_execution_specs(mission_id TEXT,phase_id TEXT,handler_id TEXT);
                  CREATE TABLE mission_action_receipts(receipt_id TEXT);
                ''')
                first.execute('INSERT INTO missions VALUES(?,?,?,?,?)', ('test','LPCL_MISSION','RUNNING','a'*40,'b'*40))
                first.execute('INSERT INTO mission_process_specs VALUES(?,?,?)', ('test','ONE','EXPLICIT_USER_ACTIVATION'))
                first.execute('INSERT INTO mission_execution_drivers VALUES(?,?,?,?,?)', ('test','driver',1,'ACTIVE','ONE'))
                first.execute('INSERT INTO mission_phases VALUES(?,?,?)', ('test','ONE','RUNNING'))
                first.execute('INSERT INTO mission_phase_execution_specs VALUES(?,?,?)', ('test','ONE','VERIFY_PHASE_PLAN'))
                first.commit()
                stale = self.request(snapshot)
                second.execute('UPDATE mission_execution_drivers SET generation=2'); second.commit()
                with self.assertRaisesRegex(ValueError, 'stale'):
                    fence_phase_action(first, 'test', stale)
                self.assertFalse(first.in_transaction)
                self.assertEqual(tuple(first.execute('SELECT state,generation FROM mission_execution_drivers').fetchone()), ('ACTIVE',2))
                self.assertEqual(first.execute('SELECT COUNT(*) FROM mission_action_receipts').fetchone()[0], 0)
                snapshot['execution_driver']['generation'] = 2
                fence_phase_action(first, 'test', self.request(snapshot))
                self.assertTrue(first.in_transaction)
                with self.assertRaises(sqlite3.OperationalError):
                    second.execute("UPDATE mission_execution_drivers SET state='STOPPED'")
                second.rollback()
                first.execute("UPDATE mission_execution_drivers SET state='PAUSED'"); first.commit()
                self.assertEqual(second.execute('SELECT state FROM mission_execution_drivers').fetchone()[0], 'PAUSED')
                self.assertEqual(first.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_8780_forwarding_is_exact_and_containment_only(self):
        from tools.lion_local_intelligence_runtime import LpclControlBridge
        bridge = LpclControlBridge(None)
        bridge._post = Mock(return_value={'status': 'PASS'})
        args = {'mission_id': 'test', 'phase_id': 'ONE', 'action': 'PAUSE', 'control_token': 'a'*64}
        bridge('phase_action', args)
        bridge._post.assert_called_once_with('/api/v3/missions/test/phase-actions', {'phase_id': 'ONE', 'action': 'PAUSE', 'control_token': 'a'*64})
        bridge._post.reset_mock()
        for bad in ({**args, 'action': 'RESUME'}, {**args, 'control_token': 'bad'}, {**args, 'status': 'PASS'}):
            with self.assertRaises(ValueError):bridge('phase_action', bad)
        bridge._post.assert_not_called()

    def test_real_mission_action_commits_state_checkpoint_and_receipt_together(self):
        self._real_atomic_action(fail_receipt=False)

    def test_real_mission_action_receipt_failure_rolls_back_state_and_checkpoint(self):
        self._real_atomic_action(fail_receipt=True)

    def _real_atomic_action(self, *, fail_receipt):
        from tools import lion_mission_control_compat, lion_mission_lifecycle_db
        from cyber_lion.mission_control import execution_driver
        with patch.dict(sys.modules, {'mission_control_compat': lion_mission_control_compat}):
            service = importlib.import_module('tools.lion_mission_control_v3')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'atomic.db'
            def connect():
                conn = sqlite3.connect(path, timeout=.2)
                conn.row_factory = sqlite3.Row
                return conn
            with closing(connect()) as conn:
                conn.executescript(lion_mission_lifecycle_db.DDL + execution_driver.DDL + '''
                  CREATE TABLE missions(mission_id TEXT,adapter TEXT,state TEXT,source_head TEXT,source_tree TEXT);
                  CREATE TABLE mission_process_specs(mission_id TEXT,current_phase TEXT,authority_state TEXT);
                  CREATE TABLE mission_phases(mission_id TEXT,phase_id TEXT,status TEXT);
                  CREATE TABLE mission_phase_execution_specs(mission_id TEXT,phase_id TEXT,handler_id TEXT);
                ''')
                conn.execute('INSERT INTO missions VALUES(?,?,?,?,?)', ('test','LPCL_MISSION','RUNNING','a'*40,'b'*40))
                conn.execute('INSERT INTO mission_process_specs VALUES(?,?,?)', ('test','ONE','EXPLICIT_USER_ACTIVATION'))
                conn.execute('INSERT INTO mission_phases VALUES(?,?,?)', ('test','ONE','RUNNING'))
                conn.execute('INSERT INTO mission_phase_execution_specs VALUES(?,?,?)', ('test','ONE','VERIFY_PHASE_PLAN'))
                execution_driver.ensure_driver(conn, 'test', lambda: '2026-09-14T00:00:00Z', initial_state='ACTIVE')
                conn.execute("UPDATE mission_execution_drivers SET driver_id='driver',current_phase='ONE'")
                conn.commit()
            original_receipt = lion_mission_lifecycle_db.create_action_receipt
            def checked_receipt(conn, mid, action, effect, status, request, result, now):
                if status == 'PASS':
                    self.assertTrue(conn.in_transaction)
                    self.assertEqual(conn.execute('SELECT state FROM mission_execution_drivers').fetchone()[0], 'PAUSED')
                    self.assertEqual(conn.execute('SELECT COUNT(*) FROM mission_execution_checkpoints').fetchone()[0], 1)
                    with closing(connect()) as observer:
                        self.assertEqual(observer.execute('SELECT state FROM mission_execution_drivers').fetchone()[0], 'ACTIVE')
                        self.assertEqual(observer.execute('SELECT COUNT(*) FROM mission_execution_checkpoints').fetchone()[0], 0)
                    if fail_receipt:
                        conn.execute('INSERT INTO mission_action_receipts VALUES(?,?,?,?,?,?,?,?,?)', ('partial','test','PAUSE','CONTROL_STATE','PASS','{}','{}','d'*64,'now'))
                        raise RuntimeError('injected receipt failure before commit')
                return original_receipt(conn,mid,action,effect,status,request,result,now)
            request = self.request(active())
            with patch.object(service, 'connect', connect), patch.object(service, 'lifecycle_create_action_receipt', checked_receipt):
                if fail_receipt:
                    with self.assertRaisesRegex(ValueError, 'injected receipt failure'):
                        service.mission_action('test', {'action': 'PAUSE'}, phase_guard=request)
                else:
                    result = service.mission_action('test', {'action': 'PAUSE'}, phase_guard=request)
                    self.assertTrue(result['receipt']['receipt_id'])
            with closing(connect()) as observer:
                self.assertEqual(observer.execute('SELECT state FROM mission_execution_drivers').fetchone()[0], 'ACTIVE' if fail_receipt else 'PAUSED')
                self.assertEqual(observer.execute('SELECT COUNT(*) FROM mission_execution_checkpoints').fetchone()[0], 0 if fail_receipt else 1)
                self.assertEqual(observer.execute("SELECT COUNT(*) FROM mission_action_receipts WHERE status='PASS'").fetchone()[0], 0 if fail_receipt else 1)
                self.assertEqual(observer.execute('SELECT status FROM mission_phases').fetchone()[0], 'RUNNING')
                self.assertEqual(observer.execute('PRAGMA integrity_check').fetchone()[0], 'ok')


if __name__ == '__main__':
    unittest.main()

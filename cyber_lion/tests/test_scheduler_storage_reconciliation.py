import concurrent.futures
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from cyber_lion.mission_control import global_scheduler as scheduler


def now():
    # Equal timestamps must not prevent fair rotation.
    return '2026-09-14T12:00:00Z'


class SchedulerStorageReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'scheduler.db'
        self.conn = self.connect()
        self.conn.executescript('''
            CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT,updated_at TEXT);
            CREATE TABLE mission_execution_drivers(mission_id TEXT PRIMARY KEY,state TEXT,heartbeat_at TEXT,current_phase TEXT);
        ''')
        scheduler.migrate(self.conn, now)

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def add_mission(self, mid, driver_state):
        self.conn.execute('INSERT INTO missions VALUES(?,?,?)', (mid, 'RUNNING', now()))
        self.conn.execute('INSERT INTO mission_execution_drivers VALUES(?,?,?,?)', (mid, driver_state, now(), 'P'))
        self.conn.commit()

    def assignment(self):
        return scheduler.create_assignment(self.conn, 'M', 'P', 'LD001', 'MD001', {'message': 'fixture'}, now, lease_generation=1)

    def receipt_snapshot(self):
        return (
            [tuple(r) for r in self.conn.execute('SELECT * FROM mission_execution_receipts ORDER BY receipt_id')],
            [tuple(r) for r in self.conn.execute('SELECT * FROM mission_execution_assignments ORDER BY assignment_id')],
        )

    def test_restart_preserves_fair_turns_across_eligible_states(self):
        self.add_mission('A', 'WAITING')
        self.add_mission('B', 'ACTIVE')
        self.add_mission('C', 'BLOCKED')
        self.add_mission('D', 'PAUSED')
        self.assertEqual(scheduler.next_dispatch(self.conn, now)['mission_id'], 'B')
        self.conn.close()
        self.conn = self.connect()
        scheduler.migrate(self.conn, now)
        observed = [scheduler.next_dispatch(self.conn, now)['mission_id'] for _ in range(5)]
        self.assertEqual(observed, ['A', 'C', 'B', 'A', 'C'])
        self.assertEqual([r[0] for r in self.conn.execute('SELECT dispatch_count FROM mission_scheduler_turns ORDER BY mission_id')], [2, 2, 2])

    def test_two_connections_select_distinct_next_turns(self):
        self.add_mission('A', 'ACTIVE')
        self.add_mission('B', 'ACTIVE')
        barrier = threading.Barrier(2)
        def choose():
            conn = self.connect()
            try:
                barrier.wait(timeout=5)
                return scheduler.next_dispatch(conn, now)['mission_id']
            finally:
                conn.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = [f.result(timeout=15) for f in [pool.submit(choose), pool.submit(choose)]]
        self.assertEqual(set(results), {'A', 'B'})

    def test_no_eligible_mission_does_not_create_turn(self):
        self.add_mission('P', 'PAUSED')
        self.assertIsNone(scheduler.next_dispatch(self.conn, now))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM mission_scheduler_turns').fetchone()[0], 0)

    def test_duplicate_and_changed_metadata_fail_closed_after_restart(self):
        aid = self.assignment()
        first = scheduler.record_receipt(self.conn, aid, {'ok': True}, now)
        self.assertFalse(first['duplicate'])
        before = self.receipt_snapshot()
        self.conn.close()
        self.conn = self.connect()
        for result, kwargs, reason in [
            ({'ok': True}, {}, 'duplicate'),
            ({'ok': False}, {}, 'conflict'),
            ({'ok': True}, {'status': 'FAIL'}, 'conflict'),
            ({'ok': True}, {'authority_effect': 'CHANGED'}, 'conflict'),
            ({'ok': True}, {'effect_receipt_digest': 'changed'}, 'conflict'),
        ]:
            with self.subTest(result=result, kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, '^assignment receipt ' + reason + '$'):
                    scheduler.record_receipt(self.conn, aid, result, now, **kwargs)
                self.assertEqual(self.receipt_snapshot(), before)

    def test_concurrent_identical_and_conflicting_ingress_has_one_winner(self):
        for same in (True, False):
            with self.subTest(identical=same):
                aid = scheduler.create_assignment(self.conn, 'M' + str(same), 'P', 'LD001', 'MD001', {}, now, lease_generation=1)
                barrier = threading.Barrier(2)
                def record(value):
                    conn = self.connect()
                    try:
                        barrier.wait(timeout=5)
                        try:
                            return ('accepted', scheduler.record_receipt(conn, aid, {'value': value}, now))
                        except ValueError as exc:
                            return ('rejected', str(exc))
                    finally:
                        conn.close()
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(record, 1), pool.submit(record, 1 if same else 2)]
                    results = [f.result(timeout=15) for f in futures]
                self.assertEqual(sorted(r[0] for r in results), ['accepted', 'rejected'])
                rejected = next(r[1] for r in results if r[0] == 'rejected')
                self.assertEqual(rejected, 'assignment receipt ' + ('duplicate' if same else 'conflict'))
                self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM mission_execution_receipts WHERE assignment_id=?', (aid,)).fetchone()[0], 1)

    def test_forward_migration_preserves_historical_conflicts_and_old_turns(self):
        aid = self.assignment()
        scheduler.record_receipt(self.conn, aid, {'version': 1}, now)
        # Reproduce existing historical rows without invoking any executor.
        self.conn.execute('INSERT INTO mission_execution_receipts VALUES(?,?,?,?,?,?,?,?,?)', ('legacy-second', aid, 'M', 'P', scheduler.digest({'version': 2}), None, 'NONE', 'FAIL', now()))
        self.conn.execute('DROP TABLE mission_scheduler_turns')
        self.conn.execute('CREATE TABLE mission_scheduler_turns(mission_id TEXT PRIMARY KEY,last_dispatched_at TEXT,dispatch_count INTEGER NOT NULL DEFAULT 0)')
        self.conn.execute('INSERT INTO mission_scheduler_turns VALUES(?,?,?)', ('M', now(), 9))
        self.conn.commit()
        before = self.receipt_snapshot()
        self.assertEqual(self.conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        scheduler.migrate(self.conn, now)
        scheduler.migrate(self.conn, now)
        self.assertEqual(self.receipt_snapshot(), before)
        self.assertEqual(tuple(self.conn.execute('SELECT dispatch_count,last_dispatched_at,last_dispatch_order FROM mission_scheduler_turns').fetchone()), (9, now(), 0))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM mission_scheduler_migrations').fetchone()[0], 1)
        self.assertEqual(self.conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        with self.assertRaisesRegex(ValueError, '^assignment receipt conflict$'):
            scheduler.record_receipt(self.conn, aid, {'version': 1}, now)
        self.assertEqual(self.receipt_snapshot(), before)


if __name__ == '__main__':
    unittest.main()

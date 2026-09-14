import sqlite3
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_lion.mission_control import global_scheduler as scheduler
from tools.lion_local_intelligence_runtime import LpclControlBridge


def now():
    return '2026-09-14T12:00:00Z'


class WorkerReceiptFenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'receipts.db'
        self.conn = self.connect()
        self.conn.execute('CREATE TABLE mission_execution_drivers(mission_id TEXT PRIMARY KEY,generation INTEGER)')
        self.conn.execute("INSERT INTO mission_execution_drivers VALUES('M',7)")
        self.conn.commit()
        scheduler.migrate(self.conn, now)
        self.aid = scheduler.create_assignment(self.conn, 'M', 'P', 'LD1', 'MD1', {}, now, lease_generation=7)

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def receipt(self, **kwargs):
        args = {'material_drone_id': 'MD1', 'lease_generation': 7}
        args.update(kwargs)
        return scheduler.record_receipt(self.conn, self.aid, {'observed': True}, now, **args)

    def snapshot(self):
        return tuple(tuple(r) for r in self.conn.execute('SELECT * FROM mission_execution_assignments')), tuple(tuple(r) for r in self.conn.execute('SELECT * FROM mission_execution_receipts'))

    def claim(self):
        scheduler.claim_assignment(self.conn, self.aid, now, expected_material_drone_id='MD1')

    def test_ready_and_wrong_worker_never_terminalize(self):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'not claimed'):
            self.receipt()
        self.assertEqual(before, self.snapshot())
        self.claim()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'material identity mismatch'):
            self.receipt(material_drone_id='MD2')
        self.assertEqual(before, self.snapshot())

    def test_stale_request_and_new_driver_generation_preserve_claim(self):
        self.claim()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'stale assignment generation'):
            self.receipt(lease_generation=6)
        self.assertEqual(before, self.snapshot())
        other = self.connect()
        try:
            other.execute("UPDATE mission_execution_drivers SET generation=8 WHERE mission_id='M'")
            other.commit()
        finally:
            other.close()
        with self.assertRaisesRegex(ValueError, 'stale assignment generation'):
            self.receipt()
        self.assertEqual(before, self.snapshot())

    def test_missing_driver_fails_closed(self):
        self.claim()
        self.conn.execute('DELETE FROM mission_execution_drivers')
        self.conn.commit()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'stale assignment generation'):
            self.receipt()
        self.assertEqual(before, self.snapshot())

    def test_valid_receipt_persists_and_stale_repeat_cannot_overwrite(self):
        self.claim()
        first = self.receipt()
        before = self.snapshot()
        self.conn.close()
        self.conn = self.connect()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.receipt()
        with self.assertRaisesRegex(ValueError, 'conflict'):
            self.receipt(status='FAIL')
        self.conn.execute("UPDATE mission_execution_drivers SET generation=8 WHERE mission_id='M'")
        self.conn.commit()
        with self.assertRaisesRegex(ValueError, 'stale assignment generation'):
            self.receipt(status='FAIL')
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.conn.execute('SELECT receipt_id FROM mission_execution_receipts').fetchone()[0], first['receipt_id'])

    def test_public_binding_cannot_be_omitted_or_boolean(self):
        self.claim()
        before = self.snapshot()
        with self.assertRaises(TypeError):
            scheduler.record_receipt(self.conn, self.aid, {}, now)
        with self.assertRaisesRegex(ValueError, 'lease generation required'):
            self.receipt(lease_generation=True)
        self.assertEqual(before, self.snapshot())

    def test_bridge_forwards_exact_claim_binding(self):
        bridge = LpclControlBridge(None)
        with patch.object(bridge, '_post', return_value={}) as post:
            bridge('local_assignment_receipt', {'assignment_id': 'a', 'material_drone_id': 'MD1', 'lease_generation': 7, 'status': 'PASS', 'result': {}})
        payload = post.call_args.args[1]
        self.assertEqual(payload['material_drone_id'], 'MD1')
        self.assertEqual(payload['lease_generation'], 7)
        self.assertEqual(payload['authority_effect'], 'NONE')

    def test_v3_requires_binding_and_rejects_wrong_worker_before_event(self):
        from tools import lion_mission_control_compat
        with patch.dict(sys.modules, {'mission_control_compat': lion_mission_control_compat}):
            service = importlib.import_module('tools.lion_mission_control_v3')
        request = {'assignment_id': self.aid, 'status': 'PASS', 'result': {}, 'effect_receipt_digest': None, 'authority_effect': 'NONE'}
        with patch.object(service, 'connect', side_effect=self.connect) as connect, patch.object(service, '_process_message') as event:
            with self.assertRaisesRegex(ValueError, 'schema'):
                service.local_assignment_receipt(request)
            connect.assert_not_called()
            self.claim()
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, 'material identity mismatch'):
                service.local_assignment_receipt(dict(request, material_drone_id='MD2', lease_generation=7))
            event.assert_not_called()
            self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()

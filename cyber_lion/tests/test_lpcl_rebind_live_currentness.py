from __future__ import annotations

import hashlib
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class LpclRebindLiveCurrentnessTests(unittest.TestCase):
    def setUp(self):
        tools = Path(__file__).resolve().parents[2] / 'tools'
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
        compat = importlib.import_module('lion_mission_control_compat')
        sys.modules['mission_control_compat'] = compat
        self.mc = importlib.import_module('lion_mission_control_v3')
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.old_db, self.old_legacy = self.mc.DB, self.mc.LEGACY_DB
        self.addCleanup(lambda: setattr(self.mc, 'DB', self.old_db))
        self.addCleanup(lambda: setattr(self.mc, 'LEGACY_DB', self.old_legacy))
        self.mc.DB = Path(self.td.name) / 'mc.db'
        self.mc.LEGACY_DB = Path(self.td.name) / 'none.db'
        self.mc.migrate()
        self.parent = self.mc.LPCL_REBIND_SOURCE
        self.mc.register_lpcl_mission(self.spec(self.parent, 'PROJECT=LION_EVOLUSION\n'))
        c = self.mc.connect()
        for i in range(1, 13):
            lid = f'LD{i:02d}'
            n = 6 if i <= 4 else 5
            c.execute('INSERT INTO logical_drones VALUES(?,?,?,?,?,?)', (self.parent, lid, 'STALE_PARENT', n, n, n))
            for j in range(n):
                c.execute(
                    'INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)',
                    (self.parent, f'parent-{lid}-{j}', f'stale-parent-{lid}-{j}', lid, 'Running', 1, 0, f'10.0.{i}.{j+1}', self.mc.now()),
                )
        c.execute("UPDATE missions SET state='RUNNING',runtime_state='RUNNING',materialized=64,ready=64 WHERE mission_id=?", (self.parent,))
        c.execute("UPDATE mission_process_specs SET authority_state='EXPLICIT_USER_ACTIVATION' WHERE mission_id=?", (self.parent,))
        c.commit(); c.close()

    def spec(self, mid, text):
        return {
            'mission_id': mid,
            'title': mid,
            'objective': 'o',
            'description': 'd',
            'lpcl_digest': hashlib.sha256(text.encode()).hexdigest(),
            'lpcl_text': text,
            'source_head': 'a' * 40,
            'source_tree': 'b' * 40,
            'logical_count': 12,
            'material_target': 64,
            'phases': [{'id': 'CURRENTNESS_REACQUIRE', 'title': 'Currentness'}],
            'protocols': list(self.mc.PROTOCOLS),
        }

    @staticmethod
    def runtime(prefix='fresh-live'):
        pods = []
        for i in range(1, 13):
            lid = f'LD{i:02d}'
            n = 6 if i <= 4 else 5
            for j in range(n):
                pods.append({
                    'name': f'e3-{lid.lower()}-worker-{j}',
                    'uid': f'{prefix}-{lid}-{j}',
                    'logical_drone': lid.lower(),
                    'phase': 'Running',
                    'ready': True,
                    'restarts': 0,
                    'pod_ip': f'10.42.{i}.{j+1}',
                })
        return {'state': 'RUNNING', 'materialized': 64, 'ready': 64, 'unique_uid_count': 64, 'pods': pods}

    @staticmethod
    def child_text(parent):
        return (
            f'PARENT_MISSION_ID={parent}\n'
            'CONTINUE_EXISTING_EPOCH3_MISSION=TRUE\n'
            'CREATE_PARALLEL_COMPETING_EPOCH3_MISSION=FALSE\n'
            'REUSE_EXISTING_HEALTHY_MATERIAL_FLEET=ALLOWED_AFTER_EXACT_IDENTITY_READBACK\n'
            'PARENT_MISSION_REMAINS_AUTHORITY_CARRIER_UNTIL_SELF_HOSTING_TAKEOVER=TRUE\n'
            + ''.join(f'LD{i:02d}=ROLE_{i:02d}\n' for i in range(1, 13))
        )

    def activate_child(self, mid='LIVE-CHILD-R1', prefix='fresh-live'):
        child = self.spec(mid, self.child_text(self.parent))
        self.mc.register_lpcl_mission(child)
        with patch.object(self.mc, 'epoch3_broker', return_value=(self.runtime(prefix), 'live-read-request')):
            out = self.mc.activate_lpcl_mission(mid, {'lpcl_digest': child['lpcl_digest'], 'activation_event': 'EXPLICIT_UI_ACTIVATION'})
        return child, out

    def test_first_bind_uses_live_epoch3_read_not_stale_parent_workers(self):
        _, out = self.activate_child()
        uids = {row['pod_uid'] for row in out['workers']}
        self.assertIn('fresh-live-LD12-0', uids)
        self.assertNotIn('stale-parent-LD12-0', uids)
        assignment = next(
            msg['payload'] for msg in out['protocol_messages']
            if msg['protocol'] == 'ASSIGNMENT' and msg['payload'].get('event') == 'EXISTING_HEALTHY_FLEET_REBOUND'
        )
        self.assertEqual(assignment['material_currentness_source'], 'EPOCH3_M64_READ')
        self.assertEqual(assignment['material_request_id'], 'live-read-request')

    def test_restart_reconciliation_preserves_bound_child_snapshot_instead_of_rewinding_parent(self):
        child, _ = self.activate_child()
        with patch.object(self.mc, 'epoch3_broker', side_effect=AssertionError('exact persisted child must not be replaced from parent')):
            out = self.mc.bind_lpcl_execution(child['mission_id'])
        uids = {row['pod_uid'] for row in out['workers']}
        self.assertIn('fresh-live-LD12-0', uids)
        self.assertNotIn('stale-parent-LD12-0', uids)
        self.assertEqual((out['materialized'], out['ready'], len(uids)), (64, 64, 64))

    def test_incomplete_rebound_snapshot_reacquires_fresh_live_epoch3_read(self):
        child, _ = self.activate_child(prefix='first-live')
        c = self.mc.connect()
        victim = c.execute('SELECT pod_name FROM material_workers WHERE mission_id=? ORDER BY pod_name LIMIT 1', (child['mission_id'],)).fetchone()[0]
        c.execute('DELETE FROM material_workers WHERE mission_id=? AND pod_name=?', (child['mission_id'], victim))
        c.commit(); c.close()
        with patch.object(self.mc, 'epoch3_broker', return_value=(self.runtime('reacquired-live'), 'reacquire-request')):
            out = self.mc.bind_lpcl_execution(child['mission_id'])
        uids = {row['pod_uid'] for row in out['workers']}
        self.assertIn('reacquired-live-LD12-0', uids)
        self.assertNotIn('stale-parent-LD12-0', uids)
        self.assertEqual((out['materialized'], out['ready'], len(uids)), (64, 64, 64))
        currentness = next(
            msg['payload'] for msg in out['protocol_messages']
            if msg['protocol'] == 'CURRENTNESS' and msg['payload'].get('material_request_id') == 'reacquire-request'
        )
        self.assertEqual(currentness['material_currentness_source'], 'EPOCH3_M64_READ')


if __name__ == '__main__':
    unittest.main()

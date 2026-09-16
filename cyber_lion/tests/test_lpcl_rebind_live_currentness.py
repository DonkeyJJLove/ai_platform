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
        self.old_current_master_resolver = self.mc.CURRENT_MASTER_IDENTITY_RESOLVER
        self.mc.CURRENT_MASTER_IDENTITY_RESOLVER = lambda: ('f'*40, 'e'*40)
        self.addCleanup(lambda: setattr(self.mc, 'CURRENT_MASTER_IDENTITY_RESOLVER', self.old_current_master_resolver))
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

    @staticmethod
    def legacy_child_text(parent):
        return (
            f'PARENT_MISSION_ID={parent}\n'
            'CONTINUE_EXISTING_EPOCH3_LINEAGE=TRUE\n'
            'CREATE_PARALLEL_COMPETING_EPOCH3_MISSION=FALSE\n'
            'MATERIAL_REUSE_POLICY=REUSE_EXISTING_HEALTHY_EPOCH3_M64_AFTER_EXACT_IDENTITY_READBACK\n'
            + ''.join(f'LD{i:02d}=ROLE_{i:02d}\n' for i in range(1, 13))
        )

    def activate_child(self, mid='LIVE-CHILD-R1', prefix='fresh-live'):
        child = self.spec(mid, self.child_text(self.parent))
        self.mc.register_lpcl_mission(child)
        with patch.object(self.mc, 'epoch3_broker', return_value=(self.runtime(prefix), 'live-read-request')):
            out = self.mc.activate_lpcl_mission(mid, {'lpcl_digest': child['lpcl_digest'], 'activation_event': 'EXPLICIT_UI_ACTIVATION'})
        return child, out

    def test_legacy_explicit_lineage_and_material_reuse_contract_is_accepted(self):
        child = self.spec('LIVE-LEGACY-CONTRACT-R1', self.legacy_child_text(self.parent))
        self.mc.register_lpcl_mission(child)
        with patch.object(self.mc, 'epoch3_broker', return_value=(self.runtime('legacy-live'), 'legacy-live-read')):
            out = self.mc.activate_lpcl_mission(child['mission_id'], {'lpcl_digest': child['lpcl_digest'], 'activation_event': 'EXPLICIT_UI_ACTIVATION'})
        self.assertEqual((out['state'], out['materialized'], out['ready']), ('RUNNING', 64, 64))
        self.assertIn('legacy-live-LD12-0', {row['pod_uid'] for row in out['workers']})

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

    def test_explicit_parent_is_used_even_when_legacy_rebind_source_is_absent(self):
        explicit_parent = 'EXPLICIT-HEALTHY-PARENT-R1'
        self.mc.register_lpcl_mission(self.spec(explicit_parent, 'PROJECT=LION_EVOLUSION\n'))
        c = self.mc.connect()
        c.execute('DELETE FROM missions WHERE mission_id=?', (self.parent,))
        c.commit(); c.close()
        child = self.spec('EXPLICIT-PARENT-CHILD-R1', self.child_text(explicit_parent))
        self.mc.register_lpcl_mission(child)
        runtime_head='d'*40;runtime_tree='e'*40
        with patch.object(self.mc, '_current_master_identity', return_value=(runtime_head,runtime_tree)), patch.object(self.mc, '_send_broker_request', return_value=(self.runtime('explicit-parent-live'), 'explicit-parent-read')) as send:
            out = self.mc.activate_lpcl_mission(child['mission_id'], {'lpcl_digest': child['lpcl_digest'], 'activation_event': 'EXPLICIT_UI_ACTIVATION'})
        self.assertEqual((out['state'], out['materialized'], out['ready']), ('RUNNING', 64, 64))
        request = send.call_args.args[0]
        self.assertEqual(request['mission_id'], self.mc.EPOCH3_MATERIAL_CARRIER_ID)
        self.assertEqual(request['spec_digest'], self.mc.EPOCH3_MATERIAL_CARRIER_SPEC_DIGEST)
        self.assertEqual(request['source_head'], runtime_head)
        self.assertEqual(request['source_tree'], runtime_tree)
        self.assertEqual(out['source_head'], child['source_head'])
        self.assertEqual(out['source_tree'], child['source_tree'])
        self.assertIn('explicit-parent-live-LD12-0', {row['pod_uid'] for row in out['workers']})

    def test_fresh_128l64m_mission_binds_without_epoch3_parent_and_compiles_generic_phases(self):
        mid='FRESH-GENERIC-128L64M-R1'
        text='PROJECT=LION_EVOLUSION\n'
        fresh=self.spec(mid,text);fresh['logical_count']=128;fresh['phases']=[{'id':'GENERIC_STEP','title':'Generic step'}]
        self.mc.register_lpcl_mission(fresh)
        with patch.object(self.mc,'epoch3_broker',return_value=(self.runtime('fresh-generic'),'fresh-generic-read')):
            out=self.mc.activate_lpcl_mission(mid,{'lpcl_digest':fresh['lpcl_digest'],'activation_event':'EXPLICIT_UI_ACTIVATION'})
        self.assertEqual((out['state'],out['adapter'],out['materialized'],out['ready']),('RUNNING','LPCL_GENERIC_128L64M',64,64))
        self.assertEqual(len(out['logical']),128);self.assertEqual(len(out['workers']),64)
        self.assertEqual(out['process']['current_phase'],'GENERIC_STEP')
        self.assertEqual(out['phases'][0]['status'],'RUNNING')
        self.assertEqual(out['phase_execution_specs'][0]['handler_id'],'GENERIC_LPCL_PHASE')
        self.assertEqual(out['execution_driver']['state'],'ACTIVE')

    def test_generic_scheduler_creates_local_plan_assignment_then_waits_fail_closed(self):
        mid='GENERIC-DISPATCH-R1'
        text='PROJECT=LION_EVOLUSION\n'
        fresh=self.spec(mid,text);fresh['logical_count']=128;fresh['phases']=[{'id':'GENERIC_STEP','title':'Generic step'}]
        self.mc.register_lpcl_mission(fresh)
        with patch.object(self.mc,'epoch3_broker',return_value=(self.runtime('generic-dispatch'),'generic-read')):
            self.mc.activate_lpcl_mission(mid,{'lpcl_digest':fresh['lpcl_digest'],'activation_event':'EXPLICIT_UI_ACTIVATION'})
        with patch.object(self.mc.global_sched,'next_dispatch',return_value={'mission_id':mid}): self.mc.global_scheduler_once()
        c=self.mc.connect();d=self.mc.driver_snapshot(c,mid)
        self.assertEqual(d['state'],'WAITING');self.assertEqual(d['blocking_gate'],'GENERIC_PHASE_LOCAL_PLAN_RECEIPT')
        self.assertIsNone(d['lease_owner']);self.assertEqual(d['current_phase'],'GENERIC_STEP')
        rows=c.execute("SELECT phase_id,logical_drone_id,material_drone_id,state,input_json FROM mission_execution_assignments WHERE mission_id=? AND phase_id!='__TOPOLOGY__'",(mid,)).fetchall()
        self.assertEqual(len(rows),1);self.assertEqual((rows[0]['phase_id'],rows[0]['logical_drone_id'],rows[0]['material_drone_id'],rows[0]['state']),('GENERIC_STEP','LD001','MD025','READY'))
        self.assertIn('LOCAL_MODEL_INFERENCE',rows[0]['input_json']);c.close()

    def test_nonexistent_explicit_parent_fails_closed_before_broker_request(self):
        missing_parent = 'NONEXISTENT-PARENT-R1'
        child = self.spec('MISSING-PARENT-CHILD-R1', self.child_text(missing_parent))
        self.mc.register_lpcl_mission(child)
        with patch.object(self.mc, '_send_broker_request', side_effect=AssertionError('broker must not run for nonexistent explicit parent')):
            out = self.mc.activate_lpcl_mission(child['mission_id'], {'lpcl_digest': child['lpcl_digest'], 'activation_event': 'EXPLICIT_UI_ACTIVATION'})
        self.assertEqual(out['state'], 'AUTHORIZED')
        self.assertEqual(out['runtime_state'], 'NOT_STARTED')
        self.assertIn('lpcl source mission missing:'+missing_parent, out['last_error'])

    def test_orphan_active_driver_is_parked_without_replaying_stale_owner(self):
        mid='ORPHAN-ACTIVE-R1'
        spec=self.spec(mid,'PROJECT=LION_EVOLUSION\n')
        self.mc.register_lpcl_mission(spec)
        c=self.mc.connect()
        c.execute("UPDATE missions SET state='AUTHORIZED',runtime_state='NOT_STARTED',last_error='LPCL_EXECUTION_BIND:ValueError:test' WHERE mission_id=?",(mid,))
        c.execute("UPDATE mission_process_specs SET authority_state='EXPLICIT_USER_ACTIVATION' WHERE mission_id=?",(mid,))
        self.mc.ensure_driver(c,mid,self.mc.now,initial_state='BOOTSTRAP_PAUSED')
        self.mc.driver_activate(c,mid,self.mc.now,owner_id='obsolete-owner',lease_seconds=60)
        c.close()
        with patch.object(self.mc.global_sched,'next_dispatch',return_value={'mission_id':mid}):
            self.mc.global_scheduler_once()
            self.mc.global_scheduler_once()
        c=self.mc.connect();d=self.mc.driver_snapshot(c,mid)
        self.assertEqual(d['state'],'WAITING');self.assertIsNone(d['lease_owner']);self.assertIsNone(d['lease_expires_at'])
        self.assertIsNone(d['current_phase']);self.assertIsNone(d['current_attempt_id'])
        self.assertEqual(d['blocking_gate'],'GLOBAL_DRIVER_NOT_REGISTERED');self.assertEqual(d['next_action'],'WAIT_FOR_EXECUTION_BINDING')
        self.assertIn('execution binding failed',d['waiting_reason'])
        cps=c.execute('SELECT COUNT(*) FROM mission_execution_checkpoints WHERE mission_id=?',(mid,)).fetchone()[0]
        c.close()
        with patch.object(self.mc.global_sched,'next_dispatch',return_value={'mission_id':mid}): self.mc.global_scheduler_once()
        c=self.mc.connect();self.assertEqual(cps,c.execute('SELECT COUNT(*) FROM mission_execution_checkpoints WHERE mission_id=?',(mid,)).fetchone()[0]);c.close()

    def test_global_scheduler_routes_any_mission_with_registered_early_handler(self):
        mid = 'GENERIC-EARLY-HANDLER-R1'
        spec = self.spec(mid, self.child_text(self.parent))
        spec['phases'] = [{'id': 'EXACT_128L64M_TOPOLOGY_BIND', 'title': 'Topology'}]
        self.mc.register_lpcl_mission(spec)
        c = self.mc.connect()
        c.execute("UPDATE missions SET state='RUNNING' WHERE mission_id=?", (mid,))
        c.execute("UPDATE mission_process_specs SET authority_state='EXPLICIT_USER_ACTIVATION',current_phase='EXACT_128L64M_TOPOLOGY_BIND' WHERE mission_id=?", (mid,))
        c.execute("UPDATE mission_phases SET status='RUNNING' WHERE mission_id=? AND phase_id='EXACT_128L64M_TOPOLOGY_BIND'", (mid,))
        self.mc.global_sched.compile_phase_specs(c, mid, {'EXACT_128L64M_TOPOLOGY_BIND': {'handler_id':'VERIFY_128L64M_BIND','effect_class':'NONE','gate_class':'EVIDENCE','retry_policy':'IDEMPOTENT','authority_class':'NONE'}})
        self.mc.ensure_driver(c, mid, self.mc.now, initial_state='BOOTSTRAP_PAUSED')
        self.mc.driver_activate(c, mid, self.mc.now, next_action='GLOBAL_SCHEDULER_DISPATCH', owner_id=self.mc.DRIVER_PROCESS_ID)
        c.close()
        with patch.object(self.mc.global_sched, 'next_dispatch', return_value={'mission_id': mid}), patch.object(self.mc, 'drive_control_plane_once') as drive:
            self.mc.global_scheduler_once()
        drive.assert_called_once_with(mid)

    def test_complete_mission_reconciliation_persists_terminal_driver_checkpoint(self):
        mid='TERMINAL-RECONCILE-R1'
        child=self.spec(mid,self.child_text(self.parent))
        self.mc.register_lpcl_mission(child)
        c=self.mc.connect()
        c.execute("UPDATE missions SET state='COMPLETE',runtime_state='DRIVER_COMPLETE' WHERE mission_id=?",(mid,))
        c.execute("UPDATE mission_process_specs SET authority_state='EXPLICIT_USER_ACTIVATION' WHERE mission_id=?",(mid,))
        self.mc.ensure_driver(c,mid,self.mc.now,initial_state='BOOTSTRAP_PAUSED')
        self.mc.driver_activate(c,mid,self.mc.now,owner_id='test-owner',lease_seconds=60)
        self.mc.driver_transition(c,mid,'PAUSED',self.mc.now,next_action='OPERATOR_RESUME')
        before=self.mc.driver_snapshot(c,mid);self.assertEqual(before['state'],'PAUSED')
        changed=self.mc._normalize_complete_driver(c,mid);self.assertTrue(changed)
        after=self.mc.driver_snapshot(c,mid)
        self.assertEqual(after['state'],'COMPLETE')
        self.assertIsNone(after['lease_owner']);self.assertIsNone(after['lease_expires_at'])
        self.assertIsNone(after['current_phase']);self.assertIsNone(after['current_attempt_id'])
        self.assertEqual(after['latest_checkpoint']['state'],'COMPLETE')
        self.assertEqual(after['checkpoint_digest'],after['latest_checkpoint']['cursor_digest'])
        count=c.execute('SELECT COUNT(*) FROM mission_execution_checkpoints WHERE mission_id=?',(mid,)).fetchone()[0]
        self.assertFalse(self.mc._normalize_complete_driver(c,mid))
        self.assertEqual(count,c.execute('SELECT COUNT(*) FROM mission_execution_checkpoints WHERE mission_id=?',(mid,)).fetchone()[0])
        c.close()

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
        runtime_head='f'*40;runtime_tree='1'*40
        with patch.object(self.mc, '_current_master_identity', return_value=(runtime_head,runtime_tree)), patch.object(self.mc, 'epoch3_broker', return_value=(self.runtime('reacquired-live'), 'reacquire-request')):
            out = self.mc.bind_lpcl_execution(child['mission_id'])
        uids = {row['pod_uid'] for row in out['workers']}
        self.assertIn('reacquired-live-LD12-0', uids)
        self.assertNotIn('stale-parent-LD12-0', uids)
        self.assertEqual((out['materialized'], out['ready'], len(uids)), (64, 64, 64))
        currentness = next(
            msg['payload'] for msg in out['protocol_messages']
            if msg['protocol'] == 'CURRENTNESS' and msg['payload'].get('material_request_id') == 'reacquire-request'
        )
        self.assertEqual(currentness['material_currentness_source'], 'GITHUB_MASTER_PLUS_EPOCH3_M64_READ')
        self.assertEqual(currentness['registered_source_head'], child['source_head'])
        self.assertEqual(currentness['registered_source_tree'], child['source_tree'])
        self.assertEqual(currentness['runtime_source_head'], runtime_head)
        self.assertEqual(currentness['runtime_source_tree'], runtime_tree)


    def test_generic_effect_evidence_executor_advances_first_two_phases_without_duplicate_planning(self):
        import sqlite3, json
        from cyber_lion.contracts.action_ir import CanonicalActionIR
        mid='GENERIC-EFFECT-EVIDENCE-R1'
        spec=self.spec(mid,'PROJECT=LION_EVOLUSION\n')
        spec['logical_count']=128
        spec['phases']=[
            {'id':'REPRODUCE_BIND_FAILURE','title':'Reproduce bind failure'},
            {'id':'SEPARATE_NEW_AND_CONTINUATION_LINEAGE','title':'Separate fresh lineage'},
            {'id':'REPAIR_EXECUTION_BINDER','title':'Repair executor'},
        ]
        self.mc.register_lpcl_mission(spec)
        # Exact historical snapshot used by the read-only evidence capability.
        backup_dir=self.mc.DB.parent/'backups'/'fixture-bind-failure';backup_dir.mkdir(parents=True,exist_ok=True)
        bp=backup_dir/'mission-control-v3.db';bc=sqlite3.connect(bp)
        bc.execute('CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT,runtime_state TEXT,materialized INTEGER,ready INTEGER,last_error TEXT,updated_at TEXT)')
        bc.execute('INSERT INTO missions VALUES(?,?,?,?,?,?,?)',(mid,'AUTHORIZED','NOT_STARTED',0,0,'LPCL_EXECUTION_BIND:ValueError:lpcl continuation contract',self.mc.now()))
        bc.commit();bc.close()
        with patch.object(self.mc,'epoch3_broker',return_value=(self.runtime('generic-evidence'),'read-1')):
            out=self.mc.activate_lpcl_mission(mid,{'lpcl_digest':spec['lpcl_digest'],'activation_event':'EXPLICIT_UI_ACTIVATION'})
        self.assertEqual((out['adapter'],out['materialized'],out['ready']),('LPCL_GENERIC_128L64M',64,64))
        # Phase 1 planning assignment, then legacy digest-only receipt (no retained payload).
        self.mc.drive_generic_once(mid)
        c=self.mc.connect();a=c.execute("SELECT * FROM mission_execution_assignments WHERE mission_id=? AND phase_id='REPRODUCE_BIND_FAILURE' AND phase_id!='__TOPOLOGY__'",(mid,)).fetchone();gen=c.execute('SELECT generation FROM mission_execution_drivers WHERE mission_id=?',(mid,)).fetchone()[0]
        self.mc.global_sched.claim_assignment(c,a['assignment_id'],self.mc.now,expected_material_drone_id='MD025')
        r1=self.mc.global_sched.record_receipt(c,a['assignment_id'],{'kind':'LOCAL_MODEL_INFERENCE','response_text':'legacy plan not retained','authority_effect':'NONE'},self.mc.now,material_drone_id='MD025',lease_generation=gen,status='PASS',authority_effect='NONE');c.close()
        self.mc.drive_generic_once(mid)
        c=self.mc.connect();p1=c.execute("SELECT * FROM mission_generic_phase_plans WHERE mission_id=? AND phase_id='REPRODUCE_BIND_FAILURE'",(mid,)).fetchone();phase1=c.execute("SELECT status FROM mission_phases WHERE mission_id=? AND phase_id='REPRODUCE_BIND_FAILURE'",(mid,)).fetchone()[0]
        self.assertEqual(p1['planning_payload_state'],'LEGACY_DIGEST_ONLY');self.assertEqual(p1['state'],'PASS');self.assertEqual(phase1,'PASS')
        CanonicalActionIR.from_json(p1['action_ir_json']).validate()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='REPRODUCE_BIND_FAILURE'",(mid,)).fetchone()[0],1)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_generic_action_receipts WHERE plan_id=?",(p1['plan_id'],)).fetchone()[0],1);c.close()
        # Phase 2 plans again; this time the bounded planning payload is retained.
        self.mc.drive_generic_once(mid)
        c=self.mc.connect();a2=c.execute("SELECT * FROM mission_execution_assignments WHERE mission_id=? AND phase_id='SEPARATE_NEW_AND_CONTINUATION_LINEAGE'",(mid,)).fetchone();gen2=c.execute('SELECT generation FROM mission_execution_drivers WHERE mission_id=?',(mid,)).fetchone()[0]
        self.mc.global_sched.claim_assignment(c,a2['assignment_id'],self.mc.now,expected_material_drone_id='MD025')
        result2={'kind':'LOCAL_MODEL_INFERENCE','response_text':'proposal only','authority_effect':'NONE'}
        r2=self.mc.global_sched.record_receipt(c,a2['assignment_id'],result2,self.mc.now,material_drone_id='MD025',lease_generation=gen2,status='PASS',authority_effect='NONE')
        self.mc.global_sched.store_assignment_payload(c,a2['assignment_id'],r2['receipt_id'],result2,self.mc.now);c.close()
        self.mc.drive_generic_once(mid)
        c=self.mc.connect();p2=c.execute("SELECT * FROM mission_generic_phase_plans WHERE mission_id=? AND phase_id='SEPARATE_NEW_AND_CONTINUATION_LINEAGE'",(mid,)).fetchone();phase2=c.execute("SELECT status FROM mission_phases WHERE mission_id=? AND phase_id='SEPARATE_NEW_AND_CONTINUATION_LINEAGE'",(mid,)).fetchone()[0];proc=c.execute('SELECT current_phase FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone()[0]
        self.assertEqual(p2['planning_payload_state'],'RETAINED');self.assertEqual(p2['state'],'PASS');self.assertEqual(phase2,'PASS');self.assertEqual(proc,'REPAIR_EXECUTION_BINDER')
        CanonicalActionIR.from_json(p2['action_ir_json']).validate()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_generic_action_receipts WHERE plan_id=?",(p2['plan_id'],)).fetchone()[0],1);c.close()


    def _make_waiting_generic(self, mid='WAITING-CONTROLS-R1'):
        spec=self.spec(mid,'PROJECT=LION_EVOLUSION\n');spec['logical_count']=128;spec['phases']=[{'id':'GENERIC_STEP','title':'Generic step'}]
        self.mc.register_lpcl_mission(spec)
        with patch.object(self.mc,'epoch3_broker',return_value=(self.runtime('waiting-controls'),'waiting-controls-read')):
            self.mc.activate_lpcl_mission(mid,{'lpcl_digest':spec['lpcl_digest'],'activation_event':'EXPLICIT_UI_ACTIVATION'})
        self.mc.drive_generic_once(mid)
        c=self.mc.connect();a=c.execute("SELECT * FROM mission_execution_assignments WHERE mission_id=? AND phase_id='GENERIC_STEP'",(mid,)).fetchone();gen=c.execute('SELECT generation FROM mission_execution_drivers WHERE mission_id=?',(mid,)).fetchone()[0]
        self.mc.global_sched.claim_assignment(c,a['assignment_id'],self.mc.now,expected_material_drone_id='MD025')
        result={'kind':'LOCAL_MODEL_INFERENCE','response_text':'proposal only','authority_effect':'NONE'}
        rec=self.mc.global_sched.record_receipt(c,a['assignment_id'],result,self.mc.now,material_drone_id='MD025',lease_generation=gen,status='PASS',authority_effect='NONE')
        self.mc.global_sched.store_assignment_payload(c,a['assignment_id'],rec['receipt_id'],result,self.mc.now)
        self.mc.global_sched.heartbeat(c,self.mc.now,queue_depth=1,active_run_count=0)
        c.close();self.mc.drive_generic_once(mid)
        return mid

    def test_waiting_driver_controls_and_liveness_are_backend_projected(self):
        mid=self._make_waiting_generic()
        snap=self.mc.process_snapshot(mid)
        self.assertEqual(snap['execution_driver']['state'],'WAITING')
        self.assertEqual(snap['execution_driver']['blocking_gate'],'CAPABILITY_NOT_AVAILABLE')
        self.assertEqual(snap['liveness']['state'],'WAITING_HEALTHY')
        self.assertTrue(snap['liveness']['auto_resume_armed'])
        self.assertTrue(snap['driver_controls']['REACQUIRE_CAPABILITIES']['supported'])
        self.assertTrue(snap['driver_controls']['PAUSE_AUTO_RESUME']['supported'])
        self.assertFalse(snap['driver_controls']['PAUSE']['supported'])
        self.assertFalse(snap['driver_controls']['RESUME']['supported'])
        self.assertTrue(snap['driver_controls']['STOP']['supported'])

    def test_reacquire_capabilities_rechecks_without_duplicate_planning(self):
        mid=self._make_waiting_generic('WAITING-RECHECK-R1')
        c=self.mc.connect();before=(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='GENERIC_STEP'",(mid,)).fetchone()[0],c.execute("SELECT COUNT(*) FROM mission_execution_receipts WHERE mission_id=? AND phase_id='GENERIC_STEP'",(mid,)).fetchone()[0],c.execute("SELECT COUNT(*) FROM mission_generic_phase_plans WHERE mission_id=? AND phase_id='GENERIC_STEP'",(mid,)).fetchone()[0]);c.close()
        out=self.mc.mission_action(mid,{'action':'REACQUIRE_CAPABILITIES'})
        self.assertTrue(out['result']['still_unavailable'])
        self.assertEqual((out['result']['planning_assignments_delta'],out['result']['planning_receipts_delta'],out['result']['action_ir_delta']),(0,0,0))
        c=self.mc.connect();after=(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='GENERIC_STEP'",(mid,)).fetchone()[0],c.execute("SELECT COUNT(*) FROM mission_execution_receipts WHERE mission_id=? AND phase_id='GENERIC_STEP'",(mid,)).fetchone()[0],c.execute("SELECT COUNT(*) FROM mission_generic_phase_plans WHERE mission_id=? AND phase_id='GENERIC_STEP'",(mid,)).fetchone()[0]);events=[json.loads(r[0]).get('event') for r in c.execute("SELECT payload_json FROM protocol_messages WHERE mission_id=? AND protocol='CONTROL' ORDER BY id",(mid,)).fetchall()];c.close()
        self.assertEqual(before,after);self.assertIn('CAPABILITY_RECHECK_REQUESTED',events);self.assertIn('CAPABILITY_RECHECK_RESULT',events)
        snap=self.mc.process_snapshot(mid);self.assertEqual(snap['execution_driver']['state'],'WAITING');self.assertEqual(snap['process']['progress'],0.0)
        self.assertTrue(any(x['action']=='REACQUIRE_CAPABILITIES' and x['status']=='PASS' for x in snap['action_receipts']))

    def test_pause_auto_resume_is_the_only_path_that_makes_waiting_resumable(self):
        mid=self._make_waiting_generic('WAITING-PAUSE-R1')
        before=self.mc.process_snapshot(mid);self.assertFalse(before['driver_controls']['RESUME']['supported'])
        self.mc.mission_action(mid,{'action':'PAUSE_AUTO_RESUME'})
        paused=self.mc.process_snapshot(mid);self.assertEqual(paused['execution_driver']['state'],'PAUSED');self.assertFalse(paused['liveness']['auto_resume_armed']);self.assertTrue(paused['driver_controls']['RESUME']['supported']);self.assertFalse(paused['driver_controls']['PAUSE_AUTO_RESUME']['supported'])
        self.mc.mission_action(mid,{'action':'RESUME'})
        resumed=self.mc.process_snapshot(mid);self.assertEqual(resumed['execution_driver']['state'],'ACTIVE');self.assertFalse(resumed['driver_controls']['RESUME']['supported'])

    def test_liveness_stale_is_derived_from_scheduler_cadence_not_progress(self):
        interval=int(self.mc.MISSION_DRIVER_LOOP_INTERVAL_SECONDS*1000)
        state,reason=self.mc._derive_liveness_state(mission_state='RUNNING',driver_state='WAITING',blocking_gate='CAPABILITY_NOT_AVAILABLE',current_phase='P',scheduler_age_ms=interval*self.mc.LIVENESS_STALE_MULTIPLIER+1,driver_age_ms=None,interval_ms=interval)
        self.assertEqual(state,'STALE');self.assertIn('scheduler',reason.lower())
        state2,_=self.mc._derive_liveness_state(mission_state='RUNNING',driver_state='WAITING',blocking_gate='CAPABILITY_NOT_AVAILABLE',current_phase='P',scheduler_age_ms=interval,driver_age_ms=interval*100,interval_ms=interval)
        self.assertEqual(state2,'WAITING_HEALTHY')

    def test_waiting_mission_is_redispatched_without_manual_resume(self):
        mid=self._make_waiting_generic('WAITING-AUTO-REEVAL-R1')
        with patch.object(self.mc.global_sched,'next_dispatch',return_value={'mission_id':mid}), patch.object(self.mc,'drive_generic_once') as drive:
            self.mc.global_scheduler_once()
        drive.assert_called_once_with(mid)
        self.assertEqual(self.mc.process_snapshot(mid)['execution_driver']['state'],'WAITING')


    def test_process_contract_plane_migrates_phase3_binds_capability_and_reconciles_without_replanning(self):
        import sqlite3
        mid=self.mc.PROCESS_CONTRACT_TARGET_MISSION
        spec=self.spec(mid,'CONTROL_LANGUAGE=LPCL/1.1\nPROJECT=LION_EVOLUSION\n')
        spec['logical_count']=128
        spec['phases']=[
            {'id':'REPRODUCE_BIND_FAILURE','title':'Reproduce'},
            {'id':'SEPARATE_NEW_AND_CONTINUATION_LINEAGE','title':'Separate'},
            {'id':'REPAIR_EXECUTION_BINDER','title':'Repair binder'},
            {'id':'REPAIR_BASE_TOPOLOGY_BOOTSTRAP','title':'Topology'},
        ]
        self.mc.register_lpcl_mission(spec)
        with patch.object(self.mc,'epoch3_broker',return_value=(self.runtime('pcp'),'pcp-read')):
            self.mc.activate_lpcl_mission(mid,{'lpcl_digest':spec['lpcl_digest'],'activation_event':'EXPLICIT_UI_ACTIVATION'})
        # Recompile contracts with the explicit migration for the known counterexample.
        self.mc.reconcile_phase_execution_contracts()
        c=self.mc.connect();contract=self.mc.global_sched.phase_execution_contract(c,mid,'REPAIR_EXECUTION_BINDER');pre=self.mc.global_sched.execution_preflight(c,mid)
        self.assertEqual(contract['contract_source'],'MIGRATED_EXPLICIT')
        self.assertEqual(contract['execution_class'],'VERIFY_THEN_REPAIR')
        self.assertEqual(contract['capability_classes'],['REPOSITORY_AND_RUNTIME_RECONCILIATION'])
        self.assertIn(pre['mission_readiness'],{'VALID_WITH_DYNAMIC_BINDING','READY_BOUND'})
        c.close()
        # Close phases 1/2 through the already proven bounded read-only path.
        backup_dir=self.mc.DB.parent/'backups'/'fixture-bind-failure-pcp';backup_dir.mkdir(parents=True,exist_ok=True)
        bp=backup_dir/'mission-control-v3.db';bc=sqlite3.connect(bp)
        bc.execute('CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT,runtime_state TEXT,materialized INTEGER,ready INTEGER,last_error TEXT,updated_at TEXT)')
        bc.execute('INSERT INTO missions VALUES(?,?,?,?,?,?,?)',(mid,'AUTHORIZED','NOT_STARTED',0,0,'LPCL_EXECUTION_BIND:ValueError:lpcl continuation contract',self.mc.now()));bc.commit();bc.close()
        for phase in ('REPRODUCE_BIND_FAILURE','SEPARATE_NEW_AND_CONTINUATION_LINEAGE'):
            self.mc.drive_generic_once(mid)
            c=self.mc.connect();a=c.execute('SELECT * FROM mission_execution_assignments WHERE mission_id=? AND phase_id=?',(mid,phase)).fetchone();gen=c.execute('SELECT generation FROM mission_execution_drivers WHERE mission_id=?',(mid,)).fetchone()[0]
            self.mc.global_sched.claim_assignment(c,a['assignment_id'],self.mc.now,expected_material_drone_id='MD025')
            result={'kind':'LOCAL_MODEL_INFERENCE','response_text':'proposal-only','authority_effect':'NONE'}
            rr=self.mc.global_sched.record_receipt(c,a['assignment_id'],result,self.mc.now,material_drone_id='MD025',lease_generation=gen,status='PASS',authority_effect='NONE')
            self.mc.global_sched.store_assignment_payload(c,a['assignment_id'],rr['receipt_id'],result,self.mc.now);c.close();self.mc.drive_generic_once(mid)
        # Phase 3 first observes the missing-capability state with the registry intentionally absent.
        saved=self.mc.PROCESS_CAPABILITY_REGISTRY
        self.mc.PROCESS_CAPABILITY_REGISTRY={}
        try:
            self.mc.drive_generic_once(mid)
            c=self.mc.connect();a=c.execute("SELECT * FROM mission_execution_assignments WHERE mission_id=? AND phase_id='REPAIR_EXECUTION_BINDER'",(mid,)).fetchone();gen=c.execute('SELECT generation FROM mission_execution_drivers WHERE mission_id=?',(mid,)).fetchone()[0]
            self.mc.global_sched.claim_assignment(c,a['assignment_id'],self.mc.now,expected_material_drone_id='MD025')
            result={'kind':'LOCAL_MODEL_INFERENCE','response_text':'binder proposal only','authority_effect':'NONE'}
            rr=self.mc.global_sched.record_receipt(c,a['assignment_id'],result,self.mc.now,material_drone_id='MD025',lease_generation=gen,status='PASS',authority_effect='NONE')
            self.mc.global_sched.store_assignment_payload(c,a['assignment_id'],rr['receipt_id'],result,self.mc.now);c.close();self.mc.drive_generic_once(mid)
        finally:self.mc.PROCESS_CAPABILITY_REGISTRY=saved
        c=self.mc.connect();d=self.mc.driver_snapshot(c,mid);self.assertEqual(d['blocking_gate'],'CAPABILITY_NOT_AVAILABLE');assign_count=c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='REPAIR_EXECUTION_BINDER'",(mid,)).fetchone()[0]
        # Create an exact pre-restart snapshot carrying the same assignment/receipt as restart durability evidence.
        rbdir=self.mc.DB.parent/'backups'/'pcp-pre-restart';rbdir.mkdir(parents=True,exist_ok=True);rb=sqlite3.connect(rbdir/'mission-control-v3.db');c.backup(rb);rb.close();c.close()
        # Capability appears. No Resume and no second planning assignment.
        self.mc.drive_generic_once(mid)
        c=self.mc.connect();phase3=c.execute("SELECT status FROM mission_phases WHERE mission_id=? AND phase_id='REPAIR_EXECUTION_BINDER'",(mid,)).fetchone()[0];proc=c.execute('SELECT current_phase,progress FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone();binding=self.mc.global_sched.phase_capability_bindings(c,mid,'REPAIR_EXECUTION_BINDER');plan=c.execute("SELECT * FROM mission_generic_phase_plans WHERE mission_id=? AND phase_id='REPAIR_EXECUTION_BINDER'",(mid,)).fetchone();action_receipts=c.execute('SELECT COUNT(*) FROM mission_generic_action_receipts WHERE plan_id=?',(plan['plan_id'],)).fetchone()[0]
        self.assertEqual(phase3,'PASS');self.assertEqual(proc['current_phase'],'REPAIR_BASE_TOPOLOGY_BOOTSTRAP');self.assertAlmostEqual(proc['progress'],75.0)  # 3/4 in this compact fixture
        self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='REPAIR_EXECUTION_BINDER'",(mid,)).fetchone()[0],assign_count)
        self.assertEqual(action_receipts,1);self.assertEqual(binding[0]['capability_id'],'GENERIC_EXECUTION_BINDER_RECONCILIATION');self.assertEqual(plan['state'],'PASS');c.close()

    def test_phase4_runtime_reconciliation_accepts_exact_128l64m_topology(self):
        from cyber_lion.mission_control.mission_reconciliation import evaluate_completion_predicates
        mid=self.mc.PROCESS_CONTRACT_TARGET_MISSION
        spec=self.spec(mid,'CONTROL_LANGUAGE=LPCL/1.1\nPROJECT=LION_EVOLUSION\n');spec['logical_count']=128
        phase_ids=('REPRODUCE_BIND_FAILURE','SEPARATE_NEW_AND_CONTINUATION_LINEAGE','REPAIR_EXECUTION_BINDER','REPAIR_BASE_TOPOLOGY_BOOTSTRAP','IMPLEMENT_GENERIC_PHASE_COMPILER','IMPLEMENT_GENERIC_PHASE_HANDLER','MATERIALIZE_DRIVER','GLOBAL_SCHEDULER_ACCEPTANCE','DYNAMIC_DELEGATION_ACCEPTANCE','RESTART_DURABILITY','REAL_PANEL_MISSION_ACCEPTANCE','RETRY_POST_ASTRA_SAAS_MISSION')
        spec['phases']=[{'id':pid,'title':pid} for pid in phase_ids]
        self.mc.register_lpcl_mission(spec)
        with patch.object(self.mc,'epoch3_broker',return_value=(self.runtime('phase4-topology'),'phase4-read')):
            self.mc.activate_lpcl_mission(mid,{'lpcl_digest':spec['lpcl_digest'],'activation_event':'EXPLICIT_UI_ACTIVATION'})
        self.mc.reconcile_phase_execution_contracts();c=self.mc.connect();contract=self.mc.global_sched.phase_execution_contract(c,mid,'REPAIR_BASE_TOPOLOGY_BOOTSTRAP')
        ok,evidence=evaluate_completion_predicates(c,mid,'REPAIR_BASE_TOPOLOGY_BOOTSTRAP',contract['completion_predicates'],db_path=self.mc.DB);c.close()
        self.assertTrue(ok,evidence)
        self.assertEqual(set(evidence['checks'].values()),{'PASS'})
        self.assertEqual(evidence['logical_count'],128);self.assertEqual(evidence['material_count'],64);self.assertEqual(evidence['topology_assignment_count'],128)

    def test_successor_capability_package_closes_generated_proposal_preflight_without_widening_effects(self):
        from cyber_lion.mission_control import control_plane_reconnaissance as cr
        proposal=cr._successor_proposal({"findings":[],"claim_to_evidence":[],"root_cause_candidates":[],"unknowns":[],"bundle_digest":"f"*64},{"recommended_control_language":"LPCL/1.2"})
        pairs=cr._generated_lpcl_pairs(proposal["lpcl_text"]);phases=[{"id":spec["id"]} for spec in cr._successor_phase_profiles()]
        contracts=self.mc.compile_panel_phase_contracts(pairs,pairs["MISSION_ID"],phases,pairs["CONTROL_LANGUAGE"])
        pf=self.mc.preflight_execution_contracts(contracts,self.mc.PROCESS_CAPABILITY_REGISTRY)
        self.assertEqual((pf.contract_count,pf.bound_count,pf.unbound_count,pf.invalid_count,pf.mission_readiness),(8,8,0,0,'READY_BOUND'))
        for cls in ('REPOSITORY_CANDIDATE_PREPARE','CONTROL_PLANE_REPAIR','BROKER_RECONCILIATION','PANEL_ACCEPTANCE'):
            rows=self.mc.PROCESS_CAPABILITY_REGISTRY[cls]
            self.assertEqual(rows[0]['capability_id'],'GENERIC_MISSION_CONTRACT_RECONCILIATION')
            self.assertEqual(rows[0]['executor_id'],'MISSION_CONTROL_PROCESS_CONTRACT_RECONCILER')
            self.assertEqual(rows[0]['effect_ceiling'],'NONE')

    def test_successor_reconciler_requires_exact_bootstrap_evidence_for_revision_convergence(self):
        from cyber_lion.mission_control.mission_reconciliation import evaluate_completion_predicates
        mid='SUCCESSOR-BOOTSTRAP-EVIDENCE-R1';spec=self.spec(mid,'PROJECT=LION_EVOLUSION\n');self.mc.register_lpcl_mission(spec)
        c=self.mc.connect();ok,evidence=evaluate_completion_predicates(c,mid,'CURRENTNESS_REACQUIRE',['RUNTIME_REVISIONS_CONVERGED=PASS'],db_path=self.mc.DB);c.close()
        self.assertFalse(ok,evidence)
        self.mc.post_protocol_message(mid,{'protocol':'EVIDENCE','from_id':'BOOTSTRAP_RECONCILER','to_id':'MISSION_CONTROL','phase':'CURRENTNESS_REACQUIRE','payload':{'event':'SUCCESSOR_RUNTIME_REVISIONS_CONVERGED','source_head':'a'*40,'source_tree':'b'*40,'authority_effect':'NONE'}})
        c=self.mc.connect();ok,evidence=evaluate_completion_predicates(c,mid,'CURRENTNESS_REACQUIRE',['RUNTIME_REVISIONS_CONVERGED=PASS'],db_path=self.mc.DB);c.close()
        self.assertTrue(ok,evidence)

    def test_generic_terminal_reconciliation_closes_waiting_driver_idempotently(self):
        mid=self._make_waiting_generic('GENERIC-TERMINAL-RECONCILE-R1')
        c=self.mc.connect()
        c.execute("UPDATE mission_phases SET status='PASS',progress=100,finished_at=?,updated_at=? WHERE mission_id=?",(self.mc.now(),self.mc.now(),mid))
        c.execute("UPDATE mission_process_specs SET current_phase=NULL,progress=100,updated_at=? WHERE mission_id=?",(self.mc.now(),mid))
        before_cp=c.execute('SELECT COUNT(*) FROM mission_execution_checkpoints WHERE mission_id=?',(mid,)).fetchone()[0]
        c.commit();c.close()
        self.mc.drive_generic_once(mid)
        snap=self.mc.process_snapshot(mid);d=snap['execution_driver']
        self.assertEqual((snap['state'],snap['runtime_state'],snap['process']['progress']),('COMPLETE','DRIVER_COMPLETE',100.0))
        self.assertIsNone(snap['process']['current_phase'])
        self.assertEqual(d['state'],'COMPLETE');self.assertIsNone(d['current_phase']);self.assertIsNone(d['current_attempt_id'])
        self.assertIsNone(d['lease_owner']);self.assertIsNone(d['lease_expires_at']);self.assertIsNone(d['waiting_reason']);self.assertIsNone(d['blocking_gate'])
        self.assertEqual(d['next_action'],'TERMINAL_RECONCILED')
        c=self.mc.connect();after_cp=c.execute('SELECT COUNT(*) FROM mission_execution_checkpoints WHERE mission_id=?',(mid,)).fetchone()[0];c.close()
        self.assertGreater(after_cp,before_cp)
        for _ in range(3):self.mc.drive_generic_once(mid)
        c=self.mc.connect();self.assertEqual(c.execute('SELECT COUNT(*) FROM mission_execution_checkpoints WHERE mission_id=?',(mid,)).fetchone()[0],after_cp);c.close()

    def test_known_repair_mission_migrates_all_remaining_legacy_phase_contracts(self):
        mid=self.mc.PROCESS_CONTRACT_TARGET_MISSION
        spec=self.spec(mid,'CONTROL_LANGUAGE=LPCL/1.1\nPROJECT=LION_EVOLUSION\n')
        spec['logical_count']=128
        phase_ids=('REPRODUCE_BIND_FAILURE','SEPARATE_NEW_AND_CONTINUATION_LINEAGE','REPAIR_EXECUTION_BINDER','REPAIR_BASE_TOPOLOGY_BOOTSTRAP','IMPLEMENT_GENERIC_PHASE_COMPILER','IMPLEMENT_GENERIC_PHASE_HANDLER','MATERIALIZE_DRIVER','GLOBAL_SCHEDULER_ACCEPTANCE','DYNAMIC_DELEGATION_ACCEPTANCE','RESTART_DURABILITY','REAL_PANEL_MISSION_ACCEPTANCE','RETRY_POST_ASTRA_SAAS_MISSION')
        spec['phases']=[{'id':pid,'title':pid} for pid in phase_ids]
        self.mc.register_lpcl_mission(spec);self.mc.reconcile_phase_execution_contracts()
        c=self.mc.connect();rows={r['phase_id']:self.mc.global_sched.phase_execution_contract(c,mid,r['phase_id']) for r in c.execute('SELECT phase_id FROM mission_phases WHERE mission_id=?',(mid,))};c.close()
        self.assertEqual(rows['REPRODUCE_BIND_FAILURE']['contract_source'],'LEGACY_INFERRED_SAFE')
        self.assertEqual(rows['SEPARATE_NEW_AND_CONTINUATION_LINEAGE']['contract_source'],'LEGACY_INFERRED_SAFE')
        for pid in phase_ids[2:]:self.assertEqual(rows[pid]['contract_source'],'MIGRATED_EXPLICIT',pid)
        for pid in phase_ids[3:]:
            self.assertEqual(rows[pid]['capability_classes'],['MISSION_RUNTIME_RECONCILIATION'],pid)
            self.assertEqual(rows[pid]['effect_ceiling'],'NONE',pid)
            self.assertTrue(rows[pid]['completion_predicates'],pid)

    def test_server_rejects_lpcl_1_2_with_intent_only_phase(self):
        mid='LPCL-1_2-MISSING-CONTRACT-R1';text='CONTROL_LANGUAGE=LPCL/1.2\nPROJECT=LION_EVOLUSION\n'
        spec=self.spec(mid,text);spec['logical_count']=128;spec['phases']=[{'id':'INTENT_ONLY','title':'Intent only'}]
        with self.assertRaisesRegex(Exception,'missing execution contract fields'):
            self.mc.register_lpcl_mission(spec)



if __name__ == '__main__':
    unittest.main()

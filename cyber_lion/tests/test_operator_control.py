import sqlite3
import unittest
from datetime import datetime, timezone

from cyber_lion.mission_control import execution_driver, global_scheduler, operator_control


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')


class OperatorControlTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.execute('CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT NOT NULL DEFAULT "RUNNING",updated_at TEXT)')
        self.c.execute("INSERT INTO missions(mission_id,state,updated_at) VALUES('M1','RUNNING',?)",(now(),))
        self.c.execute('CREATE TABLE material_workers(mission_id TEXT,pod_name TEXT,logical_id TEXT)')
        self.c.executemany('INSERT INTO material_workers VALUES(?,?,?)',[('M1','MD025','LD1'),('M1','MD026','LD2')])
        self.c.execute('''CREATE TABLE schema_migrations(
            version INTEGER, schema_id TEXT, applied_at TEXT, source_head TEXT, source_tree TEXT,
            migration_digest TEXT, note TEXT, UNIQUE(version,schema_id))''')
        execution_driver.migrate(self.c,now,source_head='a'*40,source_tree='b'*40)
        global_scheduler.migrate(self.c,now)
        operator_control.migrate(self.c,now)
        operator_control.ensure_primary_operator(self.c,now)
        execution_driver.ensure_driver(self.c,'M1',now,initial_state='ACTIVE')

    def tearDown(self):self.c.close()

    def command(self,command_id,action,payload=None,target='mission:M1',expected=None):
        value={'command_id':command_id,'mission_id':'M1','action':action,'target':target,'payload':payload or {}}
        if action in {'RESUME_SCOPE','RELEASE_CONTROL','AMEND_PLAN','REASSIGN','APPROVE_PROPOSAL'}:
            value['expected_revision']=operator_control.control_state(self.c,'M1',now)['control_epoch'] if expected is None else expected
        elif expected is not None:value['expected_revision']=expected
        return operator_control.apply_command(self.c,value,now)

    def test_message_idempotency_and_payload_conflict(self):
        first=self.command('c1','MESSAGE',{'content':'check this'},'drone:MD025')
        again=self.command('c1','MESSAGE',{'content':'check this'},'drone:MD025')
        self.assertFalse(first['idempotent']);self.assertTrue(again['idempotent'])
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM operator_messages').fetchone()[0],1)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM operator_command_receipts').fetchone()[0],1)
        with self.assertRaisesRegex(ValueError,'payload conflict'):
            self.command('c1','MESSAGE',{'content':'different'},'drone:MD025')

    def test_client_cannot_supply_priority_field(self):
        with self.assertRaisesRegex(ValueError,'command fields'):
            operator_control.apply_command(self.c,{
                'command_id':'spoof','mission_id':'M1','action':'MESSAGE','target':'mission:M1',
                'payload':{'content':'x'},'priority':999999
            },now)

    def test_take_control_fences_driver_scheduler_and_old_assignment(self):
        d=execution_driver.snapshot(self.c,'M1')
        aid=global_scheduler.create_assignment(self.c,'M1','P1','LD1','MD025',{'kind':'LOCAL_MODEL_INFERENCE'},now,lease_generation=d['generation'])
        before=operator_control.control_state(self.c,'M1',now)
        out=self.command('take','TAKE_CONTROL')
        after=out['result']['control']
        driver=execution_driver.snapshot(self.c,'M1')
        self.assertEqual(after['control_owner'],operator_control.PRIMARY_OPERATOR)
        self.assertGreater(after['control_epoch'],before['control_epoch'])
        self.assertGreater(driver['generation'],d['generation'])
        self.assertEqual(self.c.execute('SELECT state FROM mission_execution_assignments WHERE assignment_id=?',(aid,)).fetchone()[0],'CANCELLED')
        self.assertFalse(operator_control.autonomy_allowed(self.c,'M1'))
        self.assertEqual(global_scheduler.eligible_missions(self.c),[])

    def test_release_does_not_clear_pause_and_resume_is_explicit(self):
        self.command('pause','PAUSE_SCOPE')
        self.command('take','TAKE_CONTROL')
        self.command('release','RELEASE_CONTROL')
        state=operator_control.control_state(self.c,'M1')
        self.assertEqual(state['control_owner'],'AUTONOMOUS')
        self.assertEqual(state['pause_latch'],1)
        self.assertFalse(operator_control.autonomy_allowed(self.c,'M1'))
        resumed=self.command('resume','RESUME_SCOPE',{'latch':'PAUSE'})
        self.assertTrue(resumed['result']['driver_resume_required'])
        self.assertTrue(operator_control.autonomy_allowed(self.c,'M1'))
        self.assertEqual(execution_driver.snapshot(self.c,'M1')['state'],'PAUSED')

    def test_stop_latch_survives_loss_of_session_concept(self):
        self.command('stop','STOP_SCOPE')
        state=operator_control.control_state(self.c,'M1')
        self.assertEqual(state['stop_latch'],1)
        self.assertFalse(operator_control.autonomy_allowed(self.c,'M1'))
        self.assertEqual(execution_driver.snapshot(self.c,'M1')['state'],'STOPPED')

    def test_context_and_message_are_visible_to_target_drone(self):
        self.command('ctx','AMEND_CONTEXT',{'content':{'rule':'use evidence A'}})
        msg=self.command('msg','MESSAGE',{'content':'verify branch X'},'drone:MD025')
        view=operator_control.assignment_context(self.c,'M1','MD025','LD1')
        self.assertEqual(view['context']['revision'],1)
        self.assertEqual(len(view['messages']),1)
        self.assertEqual(view['messages'][0]['message_id'],msg['result']['message_id'])

    def test_operator_reassign_uses_current_fence(self):
        self.command('take','TAKE_CONTROL')
        driver=execution_driver.snapshot(self.c,'M1')
        aid=global_scheduler.create_assignment(self.c,'M1','P1','LD1','MD025',{'kind':'LOCAL_MODEL_INFERENCE'},now,
            lease_generation=driver['generation'],dispatch_authority=operator_control.PRIMARY_OPERATOR)
        out=self.command('move','REASSIGN',{'assignment_id':aid,'material_drone_id':'MD026'})
        nid=out['result']['assignment_id']
        old=self.c.execute('SELECT state FROM mission_execution_assignments WHERE assignment_id=?',(aid,)).fetchone()[0]
        new=dict(self.c.execute('SELECT * FROM mission_execution_assignments WHERE assignment_id=?',(nid,)).fetchone())
        self.assertEqual(old,'CANCELLED');self.assertEqual(new['material_drone_id'],'MD026')
        self.assertEqual(new['dispatch_authority'],operator_control.PRIMARY_OPERATOR)
        claimed=global_scheduler.claim_assignment(self.c,nid,now,expected_material_drone_id='MD026')
        self.assertEqual(claimed['state'],'CLAIMED')

    def test_stale_control_epoch_receipt_is_rejected(self):
        d=execution_driver.snapshot(self.c,'M1')
        aid=global_scheduler.create_assignment(self.c,'M1','P1','LD1','MD025',{'kind':'LOCAL_MODEL_INFERENCE'},now,lease_generation=d['generation'])
        claimed=global_scheduler.claim_assignment(self.c,aid,now,expected_material_drone_id='MD025')
        self.command('take','TAKE_CONTROL')
        with self.assertRaises(ValueError):
            global_scheduler.record_receipt(self.c,aid,{'answer':'late'},now,material_drone_id='MD025',lease_generation=claimed['lease_generation'])

    def test_worker_application_marks_operator_message(self):
        self.command('msg','MESSAGE',{'content':'use this input'},'drone:MD025')
        d=execution_driver.snapshot(self.c,'M1')
        aid=global_scheduler.create_assignment(self.c,'M1','P1','LD1','MD025',{'kind':'LOCAL_MODEL_INFERENCE'},now,lease_generation=d['generation'])
        view=operator_control.assignment_context(self.c,'M1','MD025','LD1')
        mid=view['messages'][0]['message_id']
        result=operator_control.note_assignment_application(self.c,aid,{'operator_message_ids':[mid]},now)
        self.assertEqual(result['applied_messages'],1)
        self.assertEqual(self.c.execute('SELECT state FROM operator_messages WHERE message_id=?',(mid,)).fetchone()[0],'APPLIED')

    def test_unknown_drone_target_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'unresolved drone target'):
            self.command('unknown','MESSAGE',{'content':'x'},'drone:MD999')

    def test_broadcast_remains_partial_until_all_recipients_apply_and_drone_replies(self):
        msg=self.command('broadcast','MESSAGE',{'content':'report status'},'mission:M1')
        mid=msg['result']['message_id'];self.assertEqual(msg['result']['recipient_count'],2)
        d=execution_driver.snapshot(self.c,'M1')
        aid=global_scheduler.create_assignment(self.c,'M1','P1','LD1','MD025',{'kind':'LOCAL_MODEL_INFERENCE'},now,lease_generation=d['generation'])
        out=operator_control.note_assignment_application(self.c,aid,{'operator_message_ids':[mid],'response_text':'MD025 response'},now)
        self.assertEqual(out['partial_messages'],1)
        self.assertEqual(self.c.execute('SELECT state FROM operator_messages WHERE message_id=?',(mid,)).fetchone()[0],'PARTIAL')
        reply=self.c.execute("SELECT from_participant,target,content FROM operator_messages WHERE kind='RESPONSE'").fetchone()
        self.assertEqual((reply['from_participant'],reply['target'],reply['content']),('worker:MD025','operator:primary','MD025 response'))

    def test_stale_resume_after_stop_is_conflict(self):
        before=operator_control.control_state(self.c,'M1',now)['control_epoch']
        self.command('stop2','STOP_SCOPE')
        with self.assertRaisesRegex(ValueError,'expected control revision mismatch'):
            self.command('stale-resume','RESUME_SCOPE',{'latch':'ALL'},expected=before)
        self.assertEqual(operator_control.control_state(self.c,'M1')['stop_latch'],1)

    def test_child_resume_cannot_clear_parent_pause(self):
        self.command('parent-pause','PAUSE_SCOPE')
        current=operator_control.control_state(self.c,'M1')['control_epoch']
        with self.assertRaisesRegex(ValueError,'mission scope target'):
            self.command('child-resume','RESUME_SCOPE',{'latch':'ALL'},target='drone:MD025',expected=current)
        self.assertEqual(operator_control.control_state(self.c,'M1')['pause_latch'],1)

    def test_stop_reassign_release_resume_preserves_remaining_ready_work(self):
        d=execution_driver.snapshot(self.c,'M1')
        original=global_scheduler.create_assignment(self.c,'M1','P1','LD1','MD025',{'remaining':'work'},now,lease_generation=d['generation'])
        self.command('sat-take','TAKE_CONTROL')
        self.command('sat-stop','STOP_SCOPE')
        current=operator_control.control_state(self.c,'M1')['control_epoch']
        moved=self.command('sat-move','REASSIGN',{'assignment_id':original,'material_drone_id':'MD026'},expected=current)
        new_id=moved['result']['assignment_id'];self.assertEqual(moved['result']['state'],'READY')
        current=operator_control.control_state(self.c,'M1')['control_epoch']
        released=self.command('sat-release','RELEASE_CONTROL',expected=current)
        self.assertEqual(released['result']['assignments']['rebound_ready'],1)
        row=dict(self.c.execute('SELECT * FROM mission_execution_assignments WHERE assignment_id=?',(new_id,)).fetchone())
        self.assertEqual(row['dispatch_authority'],operator_control.AUTONOMOUS_OWNER);self.assertEqual(row['state'],'READY')
        self.assertEqual(operator_control.control_state(self.c,'M1')['stop_latch'],1)
        current=operator_control.control_state(self.c,'M1')['control_epoch'];self.command('sat-resume','RESUME_SCOPE',{'latch':'ALL'},expected=current)
        activated=execution_driver.activate(self.c,'M1',now,next_action='SELECT_NEXT_PHASE',owner_id='test-scheduler')
        operator_control.rebind_ready_assignments(self.c,'M1',now,authority_owner=operator_control.AUTONOMOUS_OWNER,generation=activated['generation']);self.c.commit()
        claimed=global_scheduler.claim_assignment(self.c,new_id,now,expected_material_drone_id='MD026')
        self.assertEqual(claimed['state'],'CLAIMED')

    def test_recorded_historical_mission_keeps_no_intervention_policy(self):
        self.c.execute("UPDATE missions SET state='RECORDED_PASS' WHERE mission_id='M1'");self.c.commit()
        with self.assertRaisesRegex(ValueError,'mission terminal state:RECORDED_PASS'):
            self.command('history-stop','STOP_SCOPE')
        with self.assertRaisesRegex(ValueError,'mission terminal state:RECORDED_PASS'):
            self.command('history-msg','MESSAGE',{'content':'rewrite history'},'mission:M1')
        self.assertEqual(self.command('history-status','REQUEST_STATUS')['result']['mission_id'],'M1')

    def test_terminal_mission_cannot_resume_or_reassign(self):
        self.c.execute("UPDATE missions SET state='COMPLETE' WHERE mission_id='M1'");self.c.commit()
        rev=operator_control.control_state(self.c,'M1',now)['control_epoch']
        with self.assertRaisesRegex(ValueError,'mission terminal state:COMPLETE'):
            self.command('terminal-resume','RESUME_SCOPE',{'latch':'ALL'},expected=rev)
        with self.assertRaisesRegex(ValueError,'mission terminal state:COMPLETE'):
            self.command('terminal-move','REASSIGN',{'assignment_id':'missing','material_drone_id':'MD026'},expected=rev)
        self.assertEqual(self.c.execute("SELECT state FROM missions WHERE mission_id='M1'").fetchone()[0],'COMPLETE')
        with self.assertRaisesRegex(ValueError,'mission terminal state:COMPLETE'):
            self.command('terminal-take','TAKE_CONTROL')
        status=self.command('terminal-status','REQUEST_STATUS')
        self.assertEqual(status['result']['mission_id'],'M1')

    def test_stop_with_claimed_worker_is_partial_until_reconciled(self):
        d=execution_driver.snapshot(self.c,'M1')
        aid=global_scheduler.create_assignment(self.c,'M1','P1','LD1','MD025',{'kind':'LOCAL_MODEL_INFERENCE'},now,lease_generation=d['generation'])
        global_scheduler.claim_assignment(self.c,aid,now,expected_material_drone_id='MD025')
        out=self.command('partial-stop','STOP_SCOPE')
        self.assertEqual(out['execution_state'],'CONTAINMENT_PENDING')
        self.assertEqual(out['observation_state'],'PARTIAL')
        self.assertEqual(self.c.execute('SELECT state FROM mission_execution_assignments WHERE assignment_id=?',(aid,)).fetchone()[0],'CANCEL_REQUESTED')

    def test_scope_extending_plan_is_pending_not_active_revision(self):
        before=operator_control.control_state(self.c,'M1',now)['plan_revision']
        out=self.command('scope-plan','AMEND_PLAN',{'content':{'step':'write external target'},'scope_change':{'effect_ceiling':'EXTERNAL_WRITE'}})
        self.assertEqual(out['execution_state'],'AWAITING_SCOPE_ACTIVATION')
        self.assertEqual(out['observation_state'],'PENDING_AUTHORITY')
        self.assertEqual(operator_control.control_state(self.c,'M1')['plan_revision'],before)
        row=self.c.execute("SELECT state,requested_scope_json FROM operator_pending_plan_amendments WHERE command_id='scope-plan'").fetchone()
        self.assertEqual(row['state'],'AWAITING_SCOPE_ACTIVATION')
        self.assertIn('EXTERNAL_WRITE',row['requested_scope_json'])
        self.assertIsNone(operator_control.assignment_context(self.c,'M1','MD025','LD1')['plan'])

    def test_claimed_reassign_waits_for_checkpoint_and_late_result_is_historical(self):
        self.command('take-claimed','TAKE_CONTROL')
        d=execution_driver.snapshot(self.c,'M1')
        aid=global_scheduler.create_assignment(self.c,'M1','P1','LD1','MD025',{'kind':'LOCAL_MODEL_INFERENCE'},now,
            lease_generation=d['generation'],dispatch_authority=operator_control.PRIMARY_OPERATOR)
        claimed=global_scheduler.claim_assignment(self.c,aid,now,expected_material_drone_id='MD025')
        move=self.command('move-claimed','REASSIGN',{'assignment_id':aid,'material_drone_id':'MD026'})
        self.assertEqual(move['execution_state'],'WAITING_CHECKPOINT')
        self.assertEqual(move['observation_state'],'PARTIAL')
        self.assertNotIn('assignment_id',move['result'])
        with self.assertRaisesRegex(ValueError,'historical_result='):
            global_scheduler.record_receipt(self.c,aid,{'answer':'late old generation'},now,material_drone_id='MD025',lease_generation=claimed['lease_generation'])
        stale=self.c.execute('SELECT reason,result_json FROM mission_stale_assignment_results WHERE assignment_id=?',(aid,)).fetchone()
        self.assertIn(stale['reason'],{'STALE_CONTROL_EPOCH','STALE_DRIVER_GENERATION'})
        self.assertIn('late old generation',stale['result_json'])
        self.assertEqual(self.c.execute('SELECT state FROM mission_execution_assignments WHERE assignment_id=?',(aid,)).fetchone()[0],'STALE_RESULT')
        current=operator_control.control_state(self.c,'M1')['control_epoch']
        moved=self.command('move-after-checkpoint','REASSIGN',{'assignment_id':aid,'material_drone_id':'MD026'},expected=current)
        self.assertEqual(moved['result']['state'],'READY')
        self.assertEqual(self.c.execute('SELECT material_drone_id FROM mission_execution_assignments WHERE assignment_id=?',(moved['result']['assignment_id'],)).fetchone()[0],'MD026')

    def test_general_sentinelx_channel_is_durable_idempotent_and_preserves_correlated_schema(self):
        operator_control.ensure_operator_proxy(self.c,now,mission_scope='*',actions={'MESSAGE','REQUEST_STATUS'})
        first=operator_control.post_general_message(self.c,operator_control.PRIMARY_OPERATOR,'general-1','hello sentinelx',now)
        again=operator_control.post_general_message(self.c,operator_control.PRIMARY_OPERATOR,'general-1','hello sentinelx',now)
        self.assertFalse(first['idempotent']);self.assertTrue(again['idempotent'])
        self.assertEqual(first['receipt_digest'],again['receipt_digest'])
        proxy=operator_control.general_channel_snapshot(self.c,operator_control.SENTINELX_PROXY_PRINCIPAL,now)
        self.assertEqual(proxy['channel_id'],operator_control.GENERAL_CHANNEL_ID);self.assertEqual(proxy['delivered_now'],1)
        self.assertEqual(proxy['messages'][0]['payload']['text'],'hello sentinelx')
        repeat=operator_control.general_channel_snapshot(self.c,operator_control.SENTINELX_PROXY_PRINCIPAL,now)
        self.assertEqual(repeat['delivered_now'],0)
        reply=operator_control.post_general_message(self.c,operator_control.SENTINELX_PROXY_PRINCIPAL,'general-2','ack',now)
        self.assertFalse(reply['idempotent'])
        primary=operator_control.general_channel_snapshot(self.c,operator_control.PRIMARY_OPERATOR,now)
        self.assertEqual(primary['delivered_now'],1)
        self.assertTrue(any(x['payload']['text']=='ack' for x in primary['messages']))
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM operator_general_message_receipts').fetchone()[0],2)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM operator_general_delivery_receipts').fetchone()[0],2)
        cols={r[1] for r in self.c.execute('PRAGMA table_info(operator_messages)')}
        self.assertTrue({'correlation_id','causation_id'}.issubset(cols))


if __name__=='__main__':unittest.main()

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cyber_lion.mission_control import execution_driver, global_scheduler, operator_control
from tools.lion_operator_gateway import Runtime, reconcile_pending_conversations_once


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')


class OperatorConversationDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name)
        def secret(name,ch):
            p=root/name;p.write_text(ch*64,encoding='utf-8');return p
        self.runtime=Runtime(
            root/'operator.db',
            secret('gateway.key','a'),
            secret('proxy.key','b'),
            secret('panel.key','c'),
            secret('pairing.key','d'),
            root/'floor.json',
            'http://127.0.0.1:8766',
            bootstrap_primary=True,
        )
        c=self.runtime.connect()
        c.execute('''CREATE TABLE missions(
            mission_id TEXT PRIMARY KEY,
            adapter TEXT,
            state TEXT NOT NULL DEFAULT "RUNNING",
            runtime_state TEXT,
            materialized INTEGER DEFAULT 0,
            ready INTEGER DEFAULT 0,
            updated_at TEXT,
            last_error TEXT
        )''')
        c.execute("INSERT INTO missions(mission_id,state,updated_at) VALUES('M1','RUNNING',?)",(now(),))
        c.execute('''CREATE TABLE logical_drones(
            mission_id TEXT NOT NULL,logical_id TEXT NOT NULL,role TEXT NOT NULL,
            material_target INTEGER NOT NULL,materialized INTEGER NOT NULL DEFAULT 0,ready INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(mission_id,logical_id))''')
        c.execute('''CREATE TABLE material_workers(
            mission_id TEXT NOT NULL,pod_name TEXT NOT NULL,pod_uid TEXT,logical_id TEXT,phase TEXT,
            ready INTEGER NOT NULL,restarts INTEGER NOT NULL,pod_ip TEXT,observed_at TEXT NOT NULL,
            PRIMARY KEY(mission_id,pod_name))''')
        c.execute('''CREATE TABLE schema_migrations(
            version INTEGER, schema_id TEXT, applied_at TEXT, source_head TEXT, source_tree TEXT,
            migration_digest TEXT, note TEXT, UNIQUE(version,schema_id))''')
        execution_driver.migrate(c,now,source_head='a'*40,source_tree='b'*40)
        global_scheduler.migrate(c,now)
        execution_driver.ensure_driver(c,'M1',now,initial_state='ACTIVE')
        c.execute("UPDATE mission_execution_drivers SET current_phase='P1' WHERE mission_id='M1'")
        workers=[
            {'material_worker_id':'MD001','pod_uid':'container-1','pod_name':'lion-md001','ready':1,'restarts':0},
            {'material_worker_id':'MD002','pod_uid':'container-2','pod_name':'lion-md002','ready':1,'restarts':0},
        ]
        global_scheduler.bind_dynamic_local_model_fleet(c,'M1',4,workers,now)
        c.close()

    def command(self,command_id='panel-'+('1'*32),correlation='a'*32,content='Model?'):
        return {
            'command_id':command_id,
            'mission_id':'M1',
            'action':'MESSAGE',
            'target':'mission:M1',
            'payload':{'content':content},
            'correlation_id':correlation,
        }

    def test_mission_message_collapses_to_one_stable_conversation_executor(self):
        value=self.command()
        routed,meta=self.runtime.route_conversation_command(value)
        self.assertTrue(routed['target'].startswith('worker:MD'))
        self.assertEqual(meta['scope_target'],'mission:M1')
        routed2,meta2=self.runtime.route_conversation_command(self.command(command_id='panel-'+('2'*32)))
        self.assertEqual(routed2['target'],routed['target'])
        self.assertEqual(meta2['material_drone_id'],meta['material_drone_id'])

    def test_persisted_message_creates_exactly_one_model_assignment_and_correlated_reply(self):
        value=self.command()
        routed,meta=self.runtime.route_conversation_command(value)
        applied=self.runtime.apply(routed,principal_id=operator_control.PRIMARY_OPERATOR)
        dispatch=self.runtime.dispatch_conversation_message(routed,applied)
        self.assertEqual(dispatch['state'],'READY')
        c=self.runtime.connect()
        try:
            mid=applied['result']['message_id']
            deliveries=[dict(r) for r in c.execute('SELECT * FROM operator_message_deliveries WHERE message_id=?',(mid,))]
            self.assertEqual(len(deliveries),1)
            self.assertEqual(deliveries[0]['recipient'],'worker:'+meta['material_drone_id'])
            row=dict(c.execute('SELECT * FROM mission_execution_assignments WHERE assignment_id=?',(dispatch['assignment_id'],)).fetchone())
            payload=json.loads(row['input_json'])
            self.assertTrue(row['phase_id'].startswith('OPERATOR_BUS_'))
            self.assertEqual(payload['mission_phase_context'],'P1')
            self.assertEqual(payload['operator_message_ids'],[mid])
            self.assertEqual(payload['purpose'],'OPERATOR_BUS_CONVERSATION_R1')
            self.assertEqual(payload['conversation_protocol_version'],2)
            self.assertTrue(payload['conversation_turn_created_at'])
            self.assertEqual(payload['messages'][-1],{'role':'user','content':'Model?'})
            result=operator_control.note_assignment_application(
                c,dispatch['assignment_id'],
                {'operator_message_ids':[mid],'response_text':'Model answer'},
                now,
            )
            self.assertEqual(result['applied_messages'],1)
            original=c.execute('SELECT state FROM operator_messages WHERE message_id=?',(mid,)).fetchone()[0]
            reply=dict(c.execute("SELECT * FROM operator_messages WHERE kind='RESPONSE' AND causation_id=?",(mid,)).fetchone())
            self.assertEqual(original,'APPLIED')
            self.assertEqual(reply['content'],'Model answer')
            self.assertEqual(reply['correlation_id'],'a'*32)
            projected=operator_control.mission_snapshot(c,'M1',now)
            projected_reply=next(m for m in projected['messages'] if m['message_id']==reply['message_id'])
            self.assertTrue(projected_reply['conversation_valid'])
        finally:
            c.close()

    def test_dispatch_is_idempotent_for_same_message(self):
        value=self.command()
        routed,_=self.runtime.route_conversation_command(value)
        first=self.runtime.apply(routed,principal_id=operator_control.PRIMARY_OPERATOR)
        d1=self.runtime.dispatch_conversation_message(routed,first)
        again=self.runtime.apply(routed,principal_id=operator_control.PRIMARY_OPERATOR)
        d2=self.runtime.dispatch_conversation_message(routed,again)
        self.assertFalse(d1['idempotent'])
        self.assertTrue(d2['idempotent'])
        self.assertEqual(d1['assignment_id'],d2['assignment_id'])

    def test_thread_snapshot_survives_mission_rebind_and_marks_answered_turn(self):
        corr='f'*32
        first_value=self.command(command_id='panel-'+('9'*32),correlation=corr,content='M1 question')
        routed,_=self.runtime.route_conversation_command(first_value)
        first=self.runtime.apply(routed,principal_id=operator_control.PRIMARY_OPERATOR)
        mid=first['result']['message_id']
        dispatch=self.runtime.dispatch_conversation_message(routed,first)
        c=self.runtime.connect()
        try:
            row=c.execute("SELECT material_drone_id FROM mission_execution_assignments WHERE assignment_id=?",(dispatch['assignment_id'],)).fetchone()
            claimed=global_scheduler.claim_assignment(c,dispatch['assignment_id'],now,expected_material_drone_id=row['material_drone_id'])
            result={'operator_message_ids':[mid],'response_text':'M1 answer'}
            global_scheduler.record_receipt(c,dispatch['assignment_id'],result,now,material_drone_id=row['material_drone_id'],lease_generation=claimed['lease_generation'])
            operator_control.note_assignment_application(c,dispatch['assignment_id'],result,now)
            c.commit()
        finally:c.close()
        c=self.runtime.connect()
        try:
            c.execute("INSERT INTO missions(mission_id,state,updated_at) VALUES('M2','RUNNING',?)",(now(),))
            c.commit()
        finally:c.close()
        second_value=self.command(command_id='panel-'+('a'*32),correlation=corr,content='M2 question')
        second_value['mission_id']='M2';second_value['target']='mission:M2'
        second=self.runtime.apply(second_value,principal_id=operator_control.PRIMARY_OPERATOR)
        c=self.runtime.connect()
        try:
            snap=operator_control.thread_snapshot(c,corr,now)
            self.assertEqual(snap['mission_ids'],['M1','M2'])
            self.assertEqual([m['content'] for m in snap['messages']],['M1 question','M1 answer','M2 question'])
            first_msg=next(m for m in snap['messages'] if m['message_id']==mid)
            second_msg=next(m for m in snap['messages'] if m['message_id']==second['result']['message_id'])
            self.assertEqual(first_msg['conversation_state'],'ANSWERED')
            self.assertNotEqual(second_msg['conversation_state'],'ANSWERED')
            self.assertEqual(snap['suppressed_response_ids'],[])
        finally:c.close()

    def test_thread_snapshot_pairs_rapid_questions_with_their_causal_answers(self):
        corr='2'*32
        turns=[]
        for suffix,content in [('c','Q1'),('d','Q2'),('e','Q3')]:
            value=self.command(command_id='panel-'+(suffix*32),correlation=corr,content=content)
            routed,meta=self.runtime.route_conversation_command(value)
            applied=self.runtime.apply(routed,principal_id=operator_control.PRIMARY_OPERATOR)
            turns.append((applied['result']['message_id'],meta,content))
        c=self.runtime.connect()
        try:
            driver=execution_driver.snapshot(c,'M1')
            for index,(mid,meta,content) in enumerate(turns,1):
                aid=global_scheduler.create_assignment(c,'M1',f'OPERATOR_BUS_TEST_{index}',meta['logical_drone_id'],meta['material_drone_id'],{
                    'kind':'LOCAL_MODEL_INFERENCE',
                    'purpose':'OPERATOR_BUS_CONVERSATION_R1',
                    'conversation_protocol_version':2,
                    'operator_message_ids':[mid],
                    'messages':[{'role':'user','content':content}],
                },now,lease_generation=driver['generation'])
                operator_control.note_assignment_application(c,aid,{'operator_message_ids':[mid],'response_text':f'A{index}'},now)
            c.commit()
            snap=operator_control.thread_snapshot(c,corr,now)
            self.assertEqual([m['content'] for m in snap['messages']],['Q1','A1','Q2','A2','Q3','A3'])
            self.assertTrue(all(m.get('conversation_state')=='ANSWERED' for m in snap['messages'] if m.get('kind')=='MESSAGE'))
            self.assertTrue(all(m.get('conversation_state')=='DELIVERED' for m in snap['messages'] if m.get('kind')=='RESPONSE'))
        finally:c.close()

    def test_stale_generation_ready_is_not_listed_and_is_retried_on_current_generation(self):
        value=self.command(command_id='panel-'+('8'*32),correlation='e'*32,content='Generation?')
        routed,_=self.runtime.route_conversation_command(value)
        applied=self.runtime.apply(routed,principal_id=operator_control.PRIMARY_OPERATOR)
        first=self.runtime.dispatch_conversation_message(routed,applied)
        c=self.runtime.connect()
        try:
            first_row=c.execute("SELECT lease_generation,state FROM mission_execution_assignments WHERE assignment_id=?",(first['assignment_id'],)).fetchone()
            self.assertEqual(first_row['state'],'READY')
            current=c.execute("SELECT generation FROM mission_execution_drivers WHERE mission_id='M1'").fetchone()['generation']
            self.assertEqual(first_row['lease_generation'],current)
            c.execute("UPDATE mission_execution_drivers SET generation=? WHERE mission_id='M1'",(current+1,))
            c.commit()
            pending=global_scheduler.pending_local_assignments(c,mission_id='M1',limit=64)
            self.assertNotIn(first['assignment_id'],[x['assignment_id'] for x in pending])
        finally:c.close()
        out=reconcile_pending_conversations_once(self.runtime)
        self.assertEqual(out['dispatched'],1,out)
        c=self.runtime.connect()
        try:
            rows=c.execute("SELECT assignment_id,lease_generation FROM mission_execution_assignments WHERE input_json LIKE ? ORDER BY created_at",('%"operator_message_ids":["'+applied['result']['message_id']+'"]%',)).fetchall()
            self.assertEqual(len(rows),2)
            self.assertNotEqual(rows[0]['assignment_id'],rows[1]['assignment_id'])
            self.assertEqual(rows[1]['lease_generation'],rows[0]['lease_generation']+1)
        finally:c.close()

    def test_pass_is_terminal_across_driver_generations(self):
        value=self.command(command_id='panel-'+('b'*32),correlation='1'*32,content='Once only')
        routed,_=self.runtime.route_conversation_command(value)
        applied=self.runtime.apply(routed,principal_id=operator_control.PRIMARY_OPERATOR)
        mid=applied['result']['message_id']
        first=self.runtime.dispatch_conversation_message(routed,applied)
        c=self.runtime.connect()
        try:
            row=c.execute("SELECT material_drone_id FROM mission_execution_assignments WHERE assignment_id=?",(first['assignment_id'],)).fetchone()
            claimed=global_scheduler.claim_assignment(c,first['assignment_id'],now,expected_material_drone_id=row['material_drone_id'])
            result={'operator_message_ids':[mid],'response_text':'Only answer'}
            global_scheduler.record_receipt(c,first['assignment_id'],result,now,material_drone_id=row['material_drone_id'],lease_generation=claimed['lease_generation'])
            operator_control.note_assignment_application(c,first['assignment_id'],result,now)
            current=c.execute("SELECT generation FROM mission_execution_drivers WHERE mission_id='M1'").fetchone()['generation']
            c.execute("UPDATE mission_execution_drivers SET generation=? WHERE mission_id='M1'",(current+1,))
            c.commit()
        finally:c.close()
        out=reconcile_pending_conversations_once(self.runtime)
        self.assertEqual(out['dispatched'],0,out)
        again=self.runtime.dispatch_conversation_message(routed,applied)
        self.assertTrue(again['idempotent'])
        self.assertEqual(again['state'],'PASS')
        self.assertEqual(again['assignment_id'],first['assignment_id'])
        c=self.runtime.connect()
        try:
            rows=c.execute("SELECT assignment_id FROM mission_execution_assignments WHERE input_json LIKE ?",('%"operator_message_ids":["'+mid+'"]%',)).fetchall()
            self.assertEqual(len(rows),1)
        finally:c.close()

    def test_assignment_operator_message_filter_excludes_unrelated_pending_messages(self):
        rows=[{'message_id':'m1','content':'old'},{'message_id':'m2','content':'current'}]
        selected=operator_control.assignment_messages_for_input(rows,json.dumps({'operator_message_ids':['m2']}))
        self.assertEqual(selected,[{'message_id':'m2','content':'current'}])
        self.assertEqual(operator_control.assignment_messages_for_input(rows,'{}'),[])

    def test_v1_correlated_response_is_retained_but_not_valid_conversation_output(self):
        value=self.command(command_id='panel-'+('7'*32),correlation='d'*32,content='Old protocol')
        routed,meta=self.runtime.route_conversation_command(value)
        applied=self.runtime.apply(routed,principal_id=operator_control.PRIMARY_OPERATOR)
        mid=applied['result']['message_id']
        c=self.runtime.connect()
        try:
            driver=execution_driver.snapshot(c,'M1')
            aid=global_scheduler.create_assignment(c,'M1','P1',meta['logical_drone_id'],meta['material_drone_id'],{
                'kind':'LOCAL_MODEL_INFERENCE',
                'purpose':'OPERATOR_BUS_CONVERSATION_R1',
                'operator_message_ids':[mid],
                'messages':[{'role':'user','content':'Old protocol'}],
            },now,lease_generation=driver['generation'])
            operator_control.note_assignment_application(c,aid,{'operator_message_ids':[mid],'response_text':'legacy answer'},now)
            snapshot=operator_control.mission_snapshot(c,'M1',now)
            reply=next(m for m in snapshot['messages'] if m.get('causation_id')==mid)
            self.assertFalse(reply['conversation_valid'])
        finally:c.close()

    def test_v2_response_is_recorded_even_when_legacy_delivery_was_already_applied(self):
        value=self.command(command_id='panel-'+('9'*32),correlation='f'*32,content='Legacy delivery?')
        routed,_=self.runtime.route_conversation_command(value)
        applied=self.runtime.apply(routed,principal_id=operator_control.PRIMARY_OPERATOR)
        mid=applied['result']['message_id']
        dispatch=self.runtime.dispatch_conversation_message(routed,applied)
        c=self.runtime.connect()
        try:
            c.execute("UPDATE operator_message_deliveries SET delivery_state='APPLIED' WHERE message_id=?",(mid,))
            out=operator_control.note_assignment_application(c,dispatch['assignment_id'],{'operator_message_ids':[mid],'response_text':'v2 repaired response'},now)
            c.commit()
            self.assertEqual(len(out['response_message_ids']),1)
            snapshot=operator_control.mission_snapshot(c,'M1',now)
            reply=next(m for m in snapshot['messages'] if m.get('causation_id')==mid and m.get('content')=='v2 repaired response')
            self.assertTrue(reply['conversation_valid'])
        finally:c.close()

    def test_reconciler_repairs_missing_response_from_retained_pass_payload(self):
        value=self.command(command_id='panel-'+('a'*32),correlation='1'*32,content='Retained?')
        routed,_=self.runtime.route_conversation_command(value)
        applied=self.runtime.apply(routed,principal_id=operator_control.PRIMARY_OPERATOR)
        mid=applied['result']['message_id']
        dispatch=self.runtime.dispatch_conversation_message(routed,applied)
        c=self.runtime.connect()
        try:
            claimed=global_scheduler.claim_assignment(c,dispatch['assignment_id'],now,expected_material_drone_id=dispatch['material_drone_id'])
            result={'operator_message_ids':[mid],'response_text':'retained response'}
            receipt=global_scheduler.record_receipt(c,dispatch['assignment_id'],result,now,material_drone_id=dispatch['material_drone_id'],lease_generation=claimed['lease_generation'])
            global_scheduler.store_assignment_payload(c,dispatch['assignment_id'],receipt['receipt_id'],result,now)
            c.execute("UPDATE operator_message_deliveries SET delivery_state='APPLIED' WHERE message_id=?",(mid,))
            c.commit()
            self.assertIsNone(c.execute("SELECT 1 FROM operator_messages WHERE kind='RESPONSE' AND causation_id=?",(mid,)).fetchone())
        finally:c.close()
        out=reconcile_pending_conversations_once(self.runtime)
        self.assertEqual(out['repaired'],1,out)
        self.assertEqual(out['failed'],0,out)
        c=self.runtime.connect()
        try:
            snapshot=operator_control.mission_snapshot(c,'M1',now)
            reply=next(m for m in snapshot['messages'] if m.get('causation_id')==mid and m.get('content')=='retained response')
            self.assertTrue(reply['conversation_valid'])
        finally:c.close()

    def test_backlog_reconciler_materializes_missing_panel_assignment_once(self):
        value=self.command(command_id='panel-'+('3'*32),correlation='b'*32,content='Misja?')
        applied=self.runtime.apply(value,principal_id=operator_control.PRIMARY_OPERATOR)
        mid=applied['result']['message_id']
        c=self.runtime.connect()
        try:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE input_json LIKE ?",('%"operator_message_ids":["'+mid+'"]%',)).fetchone()[0],0)
        finally:c.close()
        first=reconcile_pending_conversations_once(self.runtime)
        self.assertEqual(first['dispatched'],1)
        self.assertEqual(first['failed'],0)
        second=reconcile_pending_conversations_once(self.runtime)
        self.assertEqual(second['existing'],1)
        c=self.runtime.connect()
        try:
            rows=c.execute("SELECT assignment_id FROM mission_execution_assignments WHERE input_json LIKE ?",('%"operator_message_ids":["'+mid+'"]%',)).fetchall()
            self.assertEqual(len(rows),1)
        finally:c.close()

    def test_backlog_is_serial_and_history_never_reads_future_turns(self):
        corr='c'*32
        first=self.runtime.apply(self.command(command_id='panel-'+('4'*32),correlation=corr,content='Misja?'),principal_id=operator_control.PRIMARY_OPERATOR)
        second=self.runtime.apply(self.command(command_id='panel-'+('5'*32),correlation=corr,content='Model'),principal_id=operator_control.PRIMARY_OPERATOR)
        third=self.runtime.apply(self.command(command_id='panel-'+('6'*32),correlation=corr,content='SaaS: Model?'),principal_id=operator_control.PRIMARY_OPERATOR)
        mids=[first['result']['message_id'],second['result']['message_id'],third['result']['message_id']]
        out1=reconcile_pending_conversations_once(self.runtime)
        self.assertEqual(out1['dispatched'],1)
        c=self.runtime.connect()
        try:
            rows=c.execute("SELECT assignment_id,material_drone_id,input_json,state FROM mission_execution_assignments WHERE input_json LIKE '%\"conversation_protocol_version\":2%' ORDER BY created_at").fetchall()
            selected=[]
            for row in rows:
                payload=json.loads(row['input_json'])
                if payload.get('correlation_id')==corr:selected.append((row,payload))
            self.assertEqual(len(selected),1)
            row,payload=selected[0]
            self.assertEqual(payload['operator_message_ids'],[mids[0]])
            self.assertEqual(payload['messages'],[{'role':'user','content':'Misja?'}])
            claimed=global_scheduler.claim_assignment(c,row['assignment_id'],now,expected_material_drone_id=row['material_drone_id'])
            result={'operator_message_ids':[mids[0]],'response_text':'Odpowiedź na pierwsze pytanie'}
            global_scheduler.record_receipt(c,row['assignment_id'],result,now,material_drone_id=row['material_drone_id'],lease_generation=claimed['lease_generation'])
            operator_control.note_assignment_application(c,row['assignment_id'],result,now)
            c.commit()
        finally:c.close()
        out2=reconcile_pending_conversations_once(self.runtime)
        self.assertEqual(out2['dispatched'],1,out2)
        c=self.runtime.connect()
        try:
            rows=c.execute("SELECT input_json FROM mission_execution_assignments WHERE input_json LIKE '%\"conversation_protocol_version\":2%' ORDER BY created_at").fetchall()
            payloads=[json.loads(r['input_json']) for r in rows if json.loads(r['input_json']).get('correlation_id')==corr]
            self.assertEqual(len(payloads),2)
            self.assertEqual(payloads[1]['operator_message_ids'],[mids[1]])
            self.assertEqual(payloads[1]['messages'],[
                {'role':'user','content':'Misja?'},
                {'role':'assistant','content':'Odpowiedź na pierwsze pytanie'},
                {'role':'user','content':'Model'},
            ])
            self.assertNotIn('SaaS: Model?',[m['content'] for m in payloads[1]['messages']])
        finally:c.close()


if __name__=='__main__':
    unittest.main()

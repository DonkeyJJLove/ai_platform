import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cyber_lion.mission_control import execution_driver, global_scheduler, operator_control
from tools.lion_operator_gateway import Runtime


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
            self.assertEqual(row['phase_id'],'__OPERATOR_BUS__')
            self.assertEqual(payload['operator_message_ids'],[mid])
            self.assertEqual(payload['purpose'],'OPERATOR_BUS_CONVERSATION_R1')
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

    def test_assignment_operator_message_filter_excludes_unrelated_pending_messages(self):
        rows=[{'message_id':'m1','content':'old'},{'message_id':'m2','content':'current'}]
        selected=operator_control.assignment_messages_for_input(rows,json.dumps({'operator_message_ids':['m2']}))
        self.assertEqual(selected,[{'message_id':'m2','content':'current'}])


if __name__=='__main__':
    unittest.main()

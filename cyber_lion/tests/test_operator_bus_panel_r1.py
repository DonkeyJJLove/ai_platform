import http.cookiejar
import json
import re
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from datetime import datetime, timezone
from pathlib import Path

from cyber_lion.mission_control import execution_driver, global_scheduler, operator_control
from tools.lion_local_intelligence_runtime import ThreadStore
from cyber_lion.app_coordination.local_intelligence_gateway import make_handler


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')


class OperatorBusCorrelationTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.execute('CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT NOT NULL DEFAULT "RUNNING",updated_at TEXT)')
        self.c.execute("INSERT INTO missions VALUES('M1','RUNNING',?)",(now(),))
        self.c.execute('CREATE TABLE material_workers(mission_id TEXT,pod_name TEXT,logical_id TEXT)')
        self.c.execute("INSERT INTO material_workers VALUES('M1','MD025','LD1')")
        self.c.execute('''CREATE TABLE schema_migrations(version INTEGER,schema_id TEXT,applied_at TEXT,source_head TEXT,source_tree TEXT,migration_digest TEXT,note TEXT,UNIQUE(version,schema_id))''')
        execution_driver.migrate(self.c,now,source_head='a'*40,source_tree='b'*40)
        global_scheduler.migrate(self.c,now)
        operator_control.migrate(self.c,now);operator_control.ensure_primary_operator(self.c,now)
        execution_driver.ensure_driver(self.c,'M1',now,initial_state='ACTIVE')

    def tearDown(self):self.c.close()

    def test_message_and_drone_response_preserve_thread_correlation(self):
        tid='a'*32
        cmd={'command_id':'panel-'+('b'*32),'mission_id':'M1','action':'MESSAGE','target':'drone:MD025','payload':{'content':'status'},'correlation_id':tid}
        out=operator_control.apply_command(self.c,cmd,now)
        mid=out['result']['message_id']
        row=self.c.execute('SELECT correlation_id,causation_id FROM operator_messages WHERE message_id=?',(mid,)).fetchone()
        self.assertEqual(row['correlation_id'],tid);self.assertIsNone(row['causation_id'])
        d=execution_driver.snapshot(self.c,'M1')
        aid=global_scheduler.create_assignment(self.c,'M1','P1','LD1','MD025',{'kind':'LOCAL_MODEL_INFERENCE'},now,lease_generation=d['generation'])
        operator_control.note_assignment_application(self.c,aid,{'operator_message_ids':[mid],'response_text':'ack'},now)
        reply=self.c.execute("SELECT correlation_id,causation_id,content FROM operator_messages WHERE kind='RESPONSE'").fetchone()
        self.assertEqual((reply['correlation_id'],reply['causation_id'],reply['content']),(tid,mid,'ack'))
        snap=operator_control.mission_snapshot(self.c,'M1',now)
        correlated=[m for m in snap['messages'] if m.get('correlation_id')==tid]
        self.assertEqual(len(correlated),2)

    def test_same_client_identity_content_conflict_is_denied_by_canonical_command_store(self):
        tid='a'*32;client_id='c'*32
        import hashlib
        command_id='panel-'+hashlib.sha256((tid+'|'+client_id).encode()).hexdigest()[:32]
        base={'command_id':command_id,'mission_id':'M1','action':'MESSAGE','target':'drone:MD025','payload':{'content':'hello'},'correlation_id':tid}
        first=operator_control.apply_command(self.c,base,now);second=operator_control.apply_command(self.c,base,now)
        self.assertFalse(first['idempotent']);self.assertTrue(second['idempotent'])
        changed={**base,'payload':{'content':'changed'}}
        with self.assertRaisesRegex(ValueError,'command_id payload conflict'):
            operator_control.apply_command(self.c,changed,now)

    def test_additive_migration_upgrades_legacy_message_table(self):
        c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
        c.execute('CREATE TABLE operator_messages(message_id TEXT PRIMARY KEY,mission_id TEXT NOT NULL,command_id TEXT NOT NULL,from_participant TEXT NOT NULL,target TEXT NOT NULL,kind TEXT NOT NULL,content TEXT NOT NULL,content_digest TEXT NOT NULL,context_revision INTEGER NOT NULL,plan_revision INTEGER NOT NULL,state TEXT NOT NULL,created_at TEXT NOT NULL,applied_at TEXT,applied_assignment_id TEXT)')
        operator_control.migrate(c,now)
        cols={r['name'] for r in c.execute('PRAGMA table_info(operator_messages)')}
        self.assertIn('correlation_id',cols);self.assertIn('causation_id',cols)
        c.close()


class ThreadBindingTests(unittest.TestCase):
    def test_binding_requires_mission_and_rejects_cross_mission_target(self):
        with tempfile.TemporaryDirectory() as td:
            store=ThreadStore(Path(td)/'threads.db');thread=store('create',{});tid=thread['thread_id']
            with self.assertRaisesRegex(ValueError,'thread binding'):
                store('bind',{'thread_id':tid,'mission_id':'','target':'mission:M1'})
            with self.assertRaisesRegex(ValueError,'thread target mission mismatch'):
                store('bind',{'thread_id':tid,'mission_id':'M1','target':'mission:M2'})

    def test_binding_persists_and_thread_list_order_is_stable(self):
        with tempfile.TemporaryDirectory() as td:
            store=ThreadStore(Path(td)/'threads.db')
            a=store('create',{'title':'A'});time.sleep(.01);b=store('create',{'title':'B'})
            bound=store('bind',{'thread_id':a['thread_id'],'mission_id':'M1','target':'drone:MD025'})
            self.assertEqual(bound['channel'],'LION_BUS');self.assertEqual(bound['binding_state'],'MISSION_BOUND')
            got=store('get',{'thread_id':a['thread_id']});self.assertEqual(got['context']['mission_id'],'M1');self.assertEqual(got['context']['target'],'drone:MD025')
            store('rename',{'thread_id':a['thread_id'],'title':'A2'})
            order=[x['thread_id'] for x in store('list',{})['threads']]
            self.assertEqual(order,[b['thread_id'],a['thread_id']])
            reopened=ThreadStore(Path(td)/'threads.db');self.assertEqual(reopened('get',{'thread_id':a['thread_id']})['context']['mission_id'],'M1')
            with self.assertRaises(ValueError):reopened('bind',{'thread_id':a['thread_id'],'mission_id':'M1','target':'http://not-a-lion-target'})
            unbound=reopened('unbind',{'thread_id':a['thread_id']});self.assertEqual(unbound['binding_state'],'MISSION_UNBOUND')


class PanelBusHttpIntegrationTests(unittest.TestCase):
    def test_panel_pair_bind_send_and_read_share_exact_operator_correlation(self):
        with tempfile.TemporaryDirectory() as td:
            store=ThreadStore(Path(td)/'threads.db')
            class FakeGateway:
                def __init__(self):
                    self.thread_provider=store;self.messages=[];self.commands=[]
                    self.control_provider=self.control;self.operator_provider=self.operator
                def control(self,op,args):
                    if op=='process':return {'process':{'mission_id':args['mission_id'],'state':'RUNNING'}}
                    raise AssertionError((op,args))
                def operator(self,op,args):
                    if op=='pair':return {'paired':True,'principal_id':'OPERATOR_PRIMARY','session_token':'gateway-session'}
                    if op=='session':return {'paired':True,'principal_id':'OPERATOR_PRIMARY'}
                    if op=='command':
                        command={k:v for k,v in args.items() if k!='__session_token'};self.commands.append(command)
                        self.messages.append({'message_id':'opmsg-http-1','command_id':command['command_id'],'from_participant':'operator:primary','target':command['target'],'kind':'MESSAGE','content':command['payload']['content'],'context_revision':0,'plan_revision':0,'state':'PENDING','created_at':'2026-09-17T12:00:00Z','applied_at':None,'applied_assignment_id':None,'correlation_id':command.get('correlation_id'),'causation_id':command.get('causation_id')})
                        return {'execution_state':'APPLIED','admission_state':'ACCEPTED','receipt_digest':'f'*64,'result':{'message_id':'opmsg-http-1'}}
                    if op=='state':return {'control':{'control_owner':'AUTONOMOUS','control_epoch':1},'operator':{'principal_id':'OPERATOR_PRIMARY'},'operator_proxy':{'principal_id':'OPERATOR_SENTINELX_PROXY'}}
                    if op=='thread':return {'schema':'lion.operator-thread-projection/v1','correlation_id':args['correlation_id'],'messages':list(self.messages),'message_deliveries':[{'message_id':'opmsg-http-1','recipient':'drone:MD025','delivery_state':'PERSISTED'}] if self.messages else [],'mission_ids':['M1'],'suppressed_response_ids':[],'authority_effect':'NONE'}
                    if op=='events':return {'events':[],'next_cursor':0}
                    raise AssertionError((op,args))
            g=FakeGateway();server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(g));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_address[1]}'
            jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            def req(path,body=None,csrf=None):
                data=None;headers={}
                if body is not None:data=json.dumps(body).encode();headers['Content-Type']='application/json'
                if csrf:headers['X-LION-CSRF']=csrf
                r=opener.open(urllib.request.Request(base+path,data=data,headers=headers,method='POST' if body is not None else 'GET'),timeout=5);return r.status,json.loads(r.read()) if 'json' in r.headers.get('Content-Type','') else r.read().decode()
            try:
                root=opener.open(base+'/',timeout=5).read().decode();csrf=re.search(r"const OPERATOR_CSRF='([^']+)'",root).group(1)
                status,pair=req('/api/operator/pair',{},csrf);self.assertEqual(status,201);self.assertTrue(pair['paired'])
                status,created=req('/api/threads',{});self.assertEqual(status,201);tid=created['thread_id']
                status,bound=req('/api/threads/'+tid+'/context',{'action':'BIND','mission_id':'M1','target':'drone:MD025'},csrf);self.assertEqual(bound['binding_state'],'MISSION_BOUND')
                client_id='c'*32
                status,sent=req('/api/threads/'+tid+'/bus',{'content':'status now','client_id':client_id},csrf);self.assertEqual(status,201);self.assertEqual(g.commands[0]['correlation_id'],tid);self.assertEqual(g.commands[0]['target'],'drone:MD025')
                status,sent2=req('/api/threads/'+tid+'/bus',{'content':'status now','client_id':client_id},csrf);self.assertEqual(status,201);self.assertEqual(g.commands[0]['command_id'],g.commands[1]['command_id'])
                status,view=req('/api/threads/'+tid+'/bus');self.assertEqual(status,200);self.assertEqual(view['messages'][0]['correlation_id'],tid);self.assertEqual(view['messages'][0]['content'],'status now')
                try:req('/api/threads/'+tid+'/chat',{'message':'must not route','route':'SAAS'})
                except urllib.error.HTTPError as exc:self.assertEqual(exc.code,410);self.assertIn('SUPERSEDED_BY_LION_BUS',exc.read().decode())
                else:self.fail('legacy chat route must be gone')
            finally:
                server.shutdown();server.server_close();thread.join(timeout=2)


if __name__=='__main__':unittest.main()

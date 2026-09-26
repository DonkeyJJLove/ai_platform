import json
import sqlite3
import tempfile
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from tools.lion_operator_gateway import FleetThreadingHTTPServer,Runtime,make_handler,now
from cyber_lion.mission_control import execution_driver, global_scheduler, operator_control


class OperatorGatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.db=root/'mc.db';self.key=root/'operator.key';self.proxy_key=root/'proxy.key';self.panel_key=root/'panel.key';self.pair_key=root/'pair.key';self.floor=root/'floor.json'
        self.key.write_text('k'*64,encoding='utf-8');self.proxy_key.write_text('p'*64,encoding='utf-8');self.panel_key.write_text('n'*64,encoding='utf-8');self.pair_key.write_text('z'*64,encoding='utf-8')
        c=sqlite3.connect(self.db);c.execute('CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT)');c.execute("INSERT INTO missions VALUES('M1','RUNNING')");c.commit();c.close()
        self.runtime=Runtime(self.db,self.key,self.proxy_key,self.panel_key,self.pair_key,self.floor,'http://127.0.0.1:9',bootstrap_primary=True)
        self.server=FleetThreadingHTTPServer(('127.0.0.1',0),make_handler(self.runtime));self.port=self.server.server_address[1]
        self.thread=Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.tmp.cleanup()
    def req(self,path,body=None,auth=True,proxy=False,panel=False,session=None):
        data=None;headers={}
        if auth:
            if panel:headers['X-LION-Panel-Proxy-Key']='n'*64
            else:headers['X-LION-Operator-Proxy-Key' if proxy else 'X-LION-Operator-Key']=('p' if proxy else 'k')*64
        if session:headers['X-LION-Operator-Session']=session
        if body is not None:data=json.dumps(body).encode();headers['Content-Type']='application/json'
        r=urllib.request.Request(f'http://127.0.0.1:{self.port}'+path,data=data,headers=headers,method='POST' if body is not None else 'GET')
        try:
            with urllib.request.urlopen(r,timeout=3) as x:return x.status,json.loads(x.read())
        except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
    def command(self,cid,action,payload=None,expected=None):
        value={'command_id':cid,'mission_id':'M1','action':action,'target':'mission:M1','payload':payload or {}}
        if action in {'RESUME_SCOPE','RELEASE_CONTROL','AMEND_PLAN','REASSIGN','APPROVE_PROPOSAL'}:
            c=self.runtime.connect();row=c.execute("SELECT control_epoch FROM mission_operator_control WHERE mission_id='M1'").fetchone();c.close();value['expected_revision']=int(row[0]) if row else 1 if expected is None else expected
            if expected is not None:value['expected_revision']=expected
        return value
    def test_fleet_backlog_is_bounded_above_default(self):
        self.assertGreaterEqual(self.server.request_queue_size,128)
        self.assertTrue(self.server.daemon_threads)

    def test_auth_and_message(self):
        self.assertEqual(self.req('/v1/state?mission_id=M1',auth=False)[0],403)
        code,out=self.req('/v1/commands',self.command('m','MESSAGE',{'content':'hello'}));self.assertEqual(code,201);self.assertFalse(out['idempotent'])
        code,state=self.req('/v1/state?mission_id=M1');self.assertEqual(code,200);self.assertEqual(state['messages'][0]['content'],'hello')
    def test_floor_recovers_rollback_as_contained(self):
        _,out=self.req('/v1/commands',self.command('stop','STOP_SCOPE'));floor=out['receipt']['control_epoch']
        c=sqlite3.connect(self.db);c.execute("UPDATE mission_operator_control SET control_epoch=1,control_owner='AUTONOMOUS',pause_latch=0,stop_latch=0 WHERE mission_id='M1'");c.commit();c.close()
        recovered=Runtime(self.db,self.key,self.proxy_key,self.panel_key,self.pair_key,self.floor,'http://127.0.0.1:9')
        c=recovered.connect();state=dict(c.execute("SELECT * FROM mission_operator_control WHERE mission_id='M1'").fetchone());c.close()
        self.assertGreaterEqual(state['control_epoch'],floor);self.assertEqual(state['control_owner'],'OPERATOR_PRIMARY');self.assertEqual((state['pause_latch'],state['stop_latch']),(1,1))
    def test_resume_without_main_service_is_partial_not_fake_success(self):
        self.req('/v1/commands',self.command('stop','STOP_SCOPE'))
        code,out=self.req('/v1/commands',self.command('resume','RESUME_SCOPE',{'latch':'ALL'}));self.assertEqual(code,201)
        self.assertEqual(out['execution_state'],'WAITING_DRIVER_SERVICE');self.assertEqual(out['observation_state'],'PARTIAL')
    def test_sentinelx_proxy_has_distinct_identity_and_limited_grant(self):
        code,who=self.req('/v1/participants',proxy=True);self.assertEqual(code,200);self.assertEqual(who['participant']['principal_id'],'OPERATOR_SENTINELX_PROXY')
        code,out=self.req('/v1/commands',self.command('proxystop','STOP_SCOPE'),proxy=True);self.assertEqual(code,201);self.assertEqual(out['principal_id'],'OPERATOR_SENTINELX_PROXY')
        self.assertEqual(out['result']['control']['control_owner'],'AUTONOMOUS')
        code,denied=self.req('/v1/commands',self.command('proxyresume','RESUME_SCOPE',{'latch':'ALL'}),proxy=True);self.assertEqual(code,409);self.assertIn('not granted',denied['error'])
    def test_revoked_proxy_grant_denies_still_valid_transport_key(self):
        c=self.runtime.connect();operator_control.revoke_active_grants(c,operator_control.SENTINELX_PROXY_PRINCIPAL,now);c.close()
        code,out=self.req('/v1/commands',self.command('afterrevoke','STOP_SCOPE'),proxy=True);self.assertEqual(code,409);self.assertIn('not granted',out['error'])
    def test_panel_transport_requires_human_pairing_for_primary_command(self):
        code,out=self.req('/v1/commands',self.command('panel-unpaired','STOP_SCOPE'),panel=True);self.assertEqual(code,403)
        code,paired=self.req('/v1/session/pair',{'pairing_code':'z'*64},panel=True);self.assertEqual(code,201);self.assertTrue(paired['paired']);token=paired['session_token']
        code,out=self.req('/v1/commands',self.command('panel-paired','STOP_SCOPE'),panel=True,session=token);self.assertEqual(code,201);self.assertEqual(out['principal_id'],'OPERATOR_PRIMARY')
        code,status=self.req('/v1/session',panel=True,session=token);self.assertEqual(code,200);self.assertTrue(status['paired'])
    def test_expired_proxy_grant_does_not_reauthorize_via_transport(self):
        c=self.runtime.connect();operator_control.revoke_active_grants(c,operator_control.SENTINELX_PROXY_PRINCIPAL,now)
        c.execute("INSERT INTO operator_grants(grant_id,principal_id,mission_scope,actions_json,issued_at,expires_at,revoked_at) VALUES(?,?,?,?,?,?,NULL)",('expired',operator_control.SENTINELX_PROXY_PRINCIPAL,'*',json.dumps(['STOP_SCOPE']),'1999-01-01T00:00:00Z','2000-01-01T00:00:00Z'));c.commit();c.close()
        code,out=self.req('/v1/commands',self.command('expired-stop','STOP_SCOPE'),proxy=True);self.assertEqual(code,409);self.assertIn('not granted',out['error'])
    def test_proxy_mission_scope_denies_foreign_mission(self):
        c=self.runtime.connect();c.execute("INSERT INTO missions VALUES('M2','RUNNING')");operator_control.revoke_active_grants(c,operator_control.SENTINELX_PROXY_PRINCIPAL,now);operator_control.ensure_operator_proxy(c,now,mission_scope='M1',actions={'REQUEST_STATUS','STOP_SCOPE'});c.close()
        foreign={'command_id':'foreign','mission_id':'M2','action':'STOP_SCOPE','target':'mission:M2','payload':{}}
        code,out=self.req('/v1/commands',foreign,proxy=True);self.assertEqual(code,409);self.assertIn('not granted',out['error'])
    def test_revoked_panel_session_loses_private_read_and_write(self):
        code,paired=self.req('/v1/session/pair',{'pairing_code':'z'*64},panel=True);self.assertEqual(code,201);token=paired['session_token']
        self.assertEqual(self.req('/v1/state?mission_id=M1',panel=True,session=token)[0],200)
        code,out=self.req('/v1/session/revoke',{},panel=True,session=token);self.assertEqual(code,200);self.assertTrue(out['revoked'])
        self.assertEqual(self.req('/v1/state?mission_id=M1',panel=True,session=token)[0],403)
        self.assertEqual(self.req('/v1/commands',self.command('revoked-panel','STOP_SCOPE'),panel=True,session=token)[0],403)

    def test_conversation_fallback_creates_one_assignment_and_correlated_response(self):
        c=self.runtime.connect()
        try:
            c.execute('''CREATE TABLE IF NOT EXISTS schema_migrations(
                version INTEGER, schema_id TEXT, applied_at TEXT, source_head TEXT, source_tree TEXT,
                migration_digest TEXT, note TEXT, UNIQUE(version,schema_id))''')
            execution_driver.migrate(c,now,source_head='a'*40,source_tree='b'*40)
            global_scheduler.migrate(c,now)
            execution_driver.ensure_driver(c,'M1',now,initial_state='ACTIVE')
            c.execute("UPDATE mission_execution_drivers SET current_phase='P1' WHERE mission_id='M1'")
            c.execute('''CREATE TABLE IF NOT EXISTS material_workers(
                mission_id TEXT NOT NULL,pod_name TEXT NOT NULL,pod_uid TEXT,logical_id TEXT,phase TEXT,
                ready INTEGER NOT NULL,restarts INTEGER NOT NULL,pod_ip TEXT,observed_at TEXT NOT NULL,
                PRIMARY KEY(mission_id,pod_name))''')
            stamp=now()
            c.execute("INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)",('POOL','lion-md001','uid-1','MD001','DOCKER_LOCAL_MODEL',1,0,None,stamp))
            c.execute("INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)",('POOL','lion-md002','uid-2','MD002','DOCKER_LOCAL_MODEL',1,0,None,stamp))
            for lid,mid in [('LD001','MD001'),('LD002','MD002')]:
                c.execute("""INSERT INTO mission_execution_assignments(
                    assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,
                    input_digest,input_json,state,lease_generation,created_at,claimed_at,finished_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                ('topology-'+lid,'M1','__TOPOLOGY__',lid,mid,'d'*64,'{}','BOUND',1,stamp,stamp,stamp))
            c.commit()
        finally:c.close()
        value={
            'command_id':'conversation-1','mission_id':'M1','action':'MESSAGE','target':'mission:M1',
            'payload':{'content':'Model?'},
            'correlation_id':'thread-000000000000000000000000000001',
        }
        routed,meta=self.runtime.route_conversation_command(value)
        self.assertEqual(routed['target'],'operatorbus:'+meta['material_drone_id'])
        self.assertIn(meta['logical_drone_id'],{'LD001','LD002'})
        applied=self.runtime.apply(routed,principal_id=operator_control.PRIMARY_OPERATOR)
        self.assertEqual(applied['result']['recipient_count'],1)
        message_id=applied['result']['message_id']
        dispatched=self.runtime.dispatch_conversation_message(routed,applied)
        aid=dispatched['assignment_id']
        self.assertFalse(dispatched['idempotent'])
        c=self.runtime.connect()
        try:
            row=c.execute("SELECT phase_id,logical_drone_id,material_drone_id,input_json FROM mission_execution_assignments WHERE assignment_id=?",(aid,)).fetchone()
            payload=json.loads(row['input_json'])
            self.assertTrue(row['phase_id'].startswith('OPERATOR_BUS_'))
            self.assertEqual(payload['mission_phase_context'],'P1')
            self.assertEqual(payload['operator_message_ids'],[message_id])
            self.assertEqual(payload['correlation_id'],value['correlation_id'])
            self.assertEqual(payload['purpose'],'OPERATOR_BUS_CONVERSATION_R1')
        finally:c.close()
        again=self.runtime.dispatch_conversation_message(routed,applied)
        self.assertTrue(again['idempotent']);self.assertEqual(again['assignment_id'],aid)
        c=self.runtime.connect()
        try:
            result=operator_control.note_assignment_application(c,aid,{'operator_message_ids':[message_id],'response_text':'Odpowiedź modelu'},now)
            self.assertEqual(result['applied_messages'],1)
            reply=c.execute("SELECT kind,content,correlation_id,causation_id FROM operator_messages WHERE kind='RESPONSE' AND causation_id=?",(message_id,)).fetchone()
            self.assertIsNotNone(reply)
            self.assertEqual(reply['content'],'Odpowiedź modelu')
            self.assertEqual(reply['correlation_id'],value['correlation_id'])
        finally:c.close()

    def test_saas_request_and_response_are_linked_to_operator_message(self):
        value={
            'command_id':'saas-conversation-1','mission_id':'M1','action':'MESSAGE','target':'mission:M1',
            'payload':{'content':'Remote model?','model_route':'SAAS'},
            'correlation_id':'thread-saas-000000000000000000000001',
        }
        applied=self.runtime.apply(value,principal_id=operator_control.PRIMARY_OPERATOR)
        mid=applied['result']['message_id']
        calls=[]
        def fake(path,*,method='GET',body=None,timeout=10):
            calls.append((path,method,body))
            if method=='POST':
                self.assertEqual(body['thread_id'],value['correlation_id']);self.assertEqual(body['question'],'Remote model?')
                return {'request_id':'saas-gateway-1'}
            self.assertEqual(path,'/api/v3/saas-broker/requests/saas-gateway-1')
            return {'status':'RESPONDED','response_text':'Remote gateway answer','receipt_digest':'c'*64}
        self.runtime._mission_control_json=fake
        linked=self.runtime.ensure_saas_request(mid)
        self.assertEqual(linked['request_id'],'saas-gateway-1');self.assertFalse(linked['idempotent'])
        linked2=self.runtime.ensure_saas_request(mid)
        self.assertTrue(linked2['idempotent'])
        out=self.runtime.reconcile_saas_message(mid)
        self.assertTrue(out['delivered']);self.assertEqual(out['state'],'RESPONDED')
        c=self.runtime.connect()
        try:
            snap=operator_control.thread_snapshot(c,value['correlation_id'],now)
            source=next(m for m in snap['messages'] if m['message_id']==mid)
            reply=next(m for m in snap['messages'] if m.get('causation_id')==mid)
            self.assertEqual(source['conversation_state'],'ANSWERED')
            self.assertEqual(reply['from_participant'],'model:saas')
            self.assertEqual(reply['conversation_leg'],'SAAS')
        finally:c.close()
        self.assertEqual(sum(1 for path,method,_ in calls if method=='POST'),1)


if __name__=='__main__':unittest.main()

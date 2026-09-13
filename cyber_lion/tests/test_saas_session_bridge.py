import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools import lion_mission_lifecycle_db as lifecycle
from tools import lion_saas_session_bridge as saas
from cyber_lion.app_coordination.saas_handoff_extension import apply_saas_handoff_extension

T='2026-09-13T15:10:00Z'

class SaaSSessionBridgeTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory();self.addCleanup(self.td.cleanup)
        self.db=Path(self.td.name)/'mc.db'
        self.c=sqlite3.connect(self.db);self.c.row_factory=sqlite3.Row
        self.c.executescript('''
        CREATE TABLE missions(mission_id TEXT PRIMARY KEY,title TEXT,adapter TEXT,spec_digest TEXT,source_head TEXT,source_tree TEXT,namespace TEXT,state TEXT,runtime_state TEXT,logical_count INTEGER,material_target INTEGER,materialized INTEGER,ready INTEGER,created_at TEXT,authorized_at TEXT,updated_at TEXT,last_error TEXT,spec_json TEXT);
        CREATE TABLE mission_process_specs(mission_id TEXT PRIMARY KEY,title TEXT,objective TEXT,description TEXT,lpcl_digest TEXT,lpcl_text TEXT,protocols_json TEXT,authority_state TEXT,current_phase TEXT,progress REAL,created_at TEXT,updated_at TEXT);
        CREATE TABLE logical_drones(mission_id TEXT,logical_id TEXT,role TEXT,material_target INTEGER,materialized INTEGER,ready INTEGER,PRIMARY KEY(mission_id,logical_id));
        ''')
        mid='M1';dg='a'*64
        self.c.execute('INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,'m','LPCL_REBOUND_EPOCH3_64',dg,'b'*40,'c'*40,None,'RUNNING','RUNNING',12,64,64,64,T,T,T,None,'{}'))
        self.c.execute('INSERT INTO mission_process_specs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(mid,'m','o','d',dg,'x','[]','EXPLICIT_USER_ACTIVATION','HYBRID_COGNITIVE_PLANE_RECONCILIATION',30.0,T,T))
        lifecycle.migrate(self.c,lambda:T,current_mission_id=mid,source_head='b'*40,source_tree='c'*40)
        saas.migrate(self.c,lambda:T,source_head='b'*40,source_tree='c'*40)

    def test_roundtrip_binds_session_without_api_authority(self):
        req=saas.create_request(self.c,'M1','Kim jesteś?',lambda:T)
        self.assertEqual(req['authority_effect'],'NONE')
        pending=saas.pending_request(self.c,lambda:T,mission_id='M1')
        self.assertEqual(pending['request_id'],req['request_id'])
        out=saas.respond(self.c,pending['request_id'],pending['response_token'],'Jestem GPT-5.6 Sol.',lambda:T,model_identity='GPT-5.6 Sol')
        self.assertEqual(out['binding']['transport'],saas.TRANSPORT)
        self.assertFalse(out['binding']['cryptographic_provider_attestation'])
        self.assertEqual(out['binding']['authority_effect'],'NONE')
        status=saas.bridge_status(self.c,'M1',lambda:T)
        self.assertEqual(status['state'],'BOUND')
        saved=saas.request_status(self.c,req['request_id'],lambda:T)
        self.assertEqual(saved['status'],'RESPONDED')
        self.assertNotIn('response_token',saved)

    def test_wrong_response_token_fails_closed(self):
        req=saas.create_request(self.c,'M1','test',lambda:T)
        with self.assertRaisesRegex(ValueError,'response token'):
            saas.respond(self.c,req['request_id'],'wrong','answer',lambda:T,model_identity='GPT-5.6 Sol')

    def test_only_one_pending_per_mission(self):
        a=saas.create_request(self.c,'M1','one',lambda:T)
        b=saas.create_request(self.c,'M1','two',lambda:T)
        ra=self.c.execute('SELECT status FROM saas_handoff_requests WHERE request_id=?',(a['request_id'],)).fetchone()['status']
        self.assertEqual(ra,'SUPERSEDED')
        self.assertEqual(saas.pending_request(self.c,lambda:T,mission_id='M1')['request_id'],b['request_id'])

class SaaSHandoffExtensionTests(unittest.TestCase):
    def test_explicit_saas_route_is_not_capability_answer(self):
        class Dummy:
            def _route(self,m):return ('LOCAL','x')
            def state(self):return {'status':'ok'}
            def chat(self,message,use_web=False,history=None,output_language='auto'):return {'route':'LOCAL','answer':'local'}
        apply_saas_handoff_extension(Dummy)
        d=Dummy();d.control_provider=lambda op,args: ({'focus_mission_id':'M1','missions':[]} if op=='recent' else ({'request_code':'ABCD1234','request_id':'saas-'+'1'*32,'authority_effect':'NONE'} if op=='saas_request' else {'state':'UNBOUND'}))
        self.assertEqual(d._route('No to wykonaj na SaaS zapytanie: Kim jesteś?')[0],'SAAS_HANDOFF')
        out=d.chat('No to wykonaj na SaaS zapytanie: Kim jesteś?',output_language='pl')
        self.assertEqual(out['route'],'SAAS_HANDOFF')
        self.assertIn('LION SaaS',out['answer'])

    def test_capability_answer_reports_bound_session(self):
        class Dummy:
            @staticmethod
            def _capability_answer(message,mission,state,output_language):return 'fallback'
            def _route(self,m):return ('LION_CAPABILITY_CURRENTNESS','x')
            def state(self):return {'saas_session_bridge':{'state':'BOUND','binding':{'model_identity':'GPT-5.6 Sol','transport':'CHATGPT_SENTINELX_SESSION_MEDIATED','expires_at':'2026-09-13T16:00:00Z','authority_effect':'NONE'}}}
            def chat(self,message,use_web=False,history=None,output_language='auto'):return {'route':'LOCAL','answer':'local'}
        apply_saas_handoff_extension(Dummy)
        d=Dummy();d.control_provider=None
        answer=d._capability_answer('Masz łączność z SaaS?',{},d.state(),'pl')
        self.assertIn('GPT-5.6 Sol',answer)
        self.assertIn('CHATGPT_SENTINELX_SESSION_MEDIATED',answer)
        self.assertIn('authority_effect=NONE',answer)

    def test_dual_evaluation_stays_on_existing_hybrid_route(self):
        class Dummy:
            def _route(self,m):return ('DUAL_EVALUATION','dual')
            def state(self):return {'status':'ok'}
            def chat(self,message,use_web=False,history=None,output_language='auto'):return {'route':'DUAL_EVALUATION','answer':'dual'}
        apply_saas_handoff_extension(Dummy)
        d=Dummy();d.control_provider=None
        self.assertEqual(d._route('Zapytaj model SaaS i model lokalny o to samo pytanie: Co to LION')[0],'DUAL_EVALUATION')

if __name__=='__main__':unittest.main()

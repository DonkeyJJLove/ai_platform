import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools import lion_mission_lifecycle_db as lifecycle
from tools import lion_saas_session_bridge as saas
from tools.lion_local_intelligence_runtime import ThreadStore
from cyber_lion.app_coordination.saas_handoff_extension import apply_saas_handoff_extension, ROUTE_CONTEXT

T='2026-09-13T15:10:00Z'

class SaaSSessionBridgeTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory();self.addCleanup(self.td.cleanup)
        self.db=Path(self.td.name)/'mc.db'
        self.c=sqlite3.connect(self.db);self.c.row_factory=sqlite3.Row
        self.addCleanup(self.c.close)
        self.c.executescript('''
        CREATE TABLE missions(mission_id TEXT PRIMARY KEY,title TEXT,adapter TEXT,spec_digest TEXT,source_head TEXT,source_tree TEXT,namespace TEXT,state TEXT,runtime_state TEXT,logical_count INTEGER,material_target INTEGER,materialized INTEGER,ready INTEGER,created_at TEXT,authorized_at TEXT,updated_at TEXT,last_error TEXT,spec_json TEXT);
        CREATE TABLE mission_process_specs(mission_id TEXT PRIMARY KEY,title TEXT,objective TEXT,description TEXT,lpcl_digest TEXT,lpcl_text TEXT,protocols_json TEXT,authority_state TEXT,current_phase TEXT,progress REAL,created_at TEXT,updated_at TEXT);
        CREATE TABLE logical_drones(mission_id TEXT,logical_id TEXT,role TEXT,material_target INTEGER,materialized INTEGER,ready INTEGER,PRIMARY KEY(mission_id,logical_id));
        ''')
        mid='M1';dg='a'*64
        self.c.execute('INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,'m','LPCL_REBOUND_EPOCH3_64',dg,'b'*40,'c'*40,None,'RUNNING','RUNNING',12,64,64,64,T,T,T,None,'{}'))
        self.c.execute('INSERT INTO mission_process_specs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(mid,'m','o','d',dg,'x','[]','EXPLICIT_USER_ACTIVATION','HYBRID_COGNITIVE_PLANE_RECONCILIATION',30.0,T,T))
        mid2='M2'
        self.c.execute('INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid2,'m2','LPCL_MISSION','d'*64,'e'*40,'f'*40,None,'AUTHORIZED','NOT_STARTED',12,64,0,0,T,T,T,None,'{}'))
        self.c.execute('INSERT INTO mission_process_specs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(mid2,'m2','o2','d2','d'*64,'x2','[]','EXPLICIT_USER_ACTIVATION',None,0.0,T,T))
        lifecycle.migrate(self.c,lambda:T,current_mission_id=mid,source_head='b'*40,source_tree='c'*40)
        saas.migrate(self.c,lambda:T,source_head='b'*40,source_tree='c'*40)
        self.c.execute('CREATE TABLE IF NOT EXISTS mission_dual_evaluations(request_id TEXT PRIMARY KEY,saas_request_id TEXT,updated_at TEXT)')
        self.c.commit()

    def test_cancellation_is_idempotent_and_removes_only_owned_pending_request(self):
        first=saas.create_request(self.c,'M1','first',lambda:T)
        second=saas.create_request(self.c,'M2','second',lambda:T)
        for _ in range(2):
            result=saas.cancel_request(self.c,first['request_id'],lambda:T)
            self.assertEqual(result['status'],'CANCELLED')
        self.assertEqual(saas.pending_request(self.c,lambda:T)['request_id'],second['request_id'])
        self.assertEqual(saas.request_status(self.c,first['request_id'],lambda:T)['status'],'CANCELLED')

    def test_cancellation_preserves_accepted_response_and_session(self):
        req=saas.create_request(self.c,'M1','question',lambda:T)
        pending=saas.pending_request(self.c,lambda:T)
        saas.respond(self.c,req['request_id'],pending['response_token'],'answer',lambda:T,model_identity='test')
        before=saas.request_status(self.c,req['request_id'],lambda:T)
        self.assertEqual(saas.cancel_request(self.c,req['request_id'],lambda:T)['status'],'RESPONDED')
        self.assertEqual(saas.request_status(self.c,req['request_id'],lambda:T),before)
        self.assertEqual(saas.bridge_status(self.c,'M1',lambda:T)['state'],'BOUND')

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

    def test_global_supervisor_binding_is_visible_across_mission_focus(self):
        req=saas.create_request(self.c,'M1','bind global supervisor',lambda:T)
        pending=saas.pending_request(self.c,lambda:T,mission_id='M1')
        out=saas.respond(self.c,req['request_id'],pending['response_token'],'GLOBAL SESSION OK',lambda:T,model_identity='GPT-5.6 Sol')
        self.assertEqual(out['binding']['binding_scope'],'GLOBAL_SUPERVISOR_CHANNEL')
        other=saas.bridge_status(self.c,'M2',lambda:T)
        self.assertEqual(other['state'],'BOUND')
        self.assertEqual(other['session_attestation_state'],'BOUND')
        self.assertEqual(other['session_scope'],'GLOBAL_SUPERVISOR_CHANNEL')
        self.assertEqual(other['binding']['mission_id'],'M1')
        self.assertEqual(other['binding']['model_identity'],'GPT-5.6 Sol')

    def test_request_deadline_becomes_overdue_but_remains_answerable(self):
        later='2026-09-13T15:12:00Z'
        req=saas.create_request(self.c,'M1','slow operator',lambda:T,ttl_seconds=30)
        pending=saas.pending_request(self.c,lambda:later,mission_id='M1')
        self.assertIsNotNone(pending)
        self.assertEqual(pending['request_id'],req['request_id'])
        self.assertEqual(pending['status'],'PENDING')
        self.assertEqual(pending['progress_state'],'WAITING_OPERATOR_OVERDUE')
        self.assertEqual(pending['deadline_elapsed_at'],later)
        out=saas.respond(self.c,req['request_id'],pending['response_token'],'late but valid',lambda:later,model_identity='GPT-5.6 Sol')
        self.assertEqual(out['status'],'RESPONDED')
        saved=saas.request_status(self.c,req['request_id'],lambda:later)
        self.assertEqual(saved['status'],'RESPONDED')
        self.assertEqual(saved['progress_state'],'RECEIPT_BOUND')

    def test_session_lease_expires_independently_of_responded_request(self):
        req=saas.create_request(self.c,'M1','lease test',lambda:T)
        pending=saas.pending_request(self.c,lambda:T,mission_id='M1')
        saas.respond(self.c,req['request_id'],pending['response_token'],'ok',lambda:T,model_identity='GPT-5.6 Sol',lease_seconds=30)
        later='2026-09-13T15:11:00Z'
        status=saas.bridge_status(self.c,'M2',lambda:later)
        self.assertEqual(status['session_attestation_state'],'EXPIRED')
        saved=saas.request_status(self.c,req['request_id'],lambda:later)
        self.assertEqual(saved['status'],'RESPONDED')
        self.assertEqual(saved['progress_state'],'RECEIPT_BOUND')

    def test_schema_v2_forward_columns_are_materialized(self):
        bindings={r[1] for r in self.c.execute('PRAGMA table_info(saas_session_bindings)').fetchall()}
        requests={r[1] for r in self.c.execute('PRAGMA table_info(saas_handoff_requests)').fetchall()}
        self.assertIn('binding_scope',bindings)
        self.assertTrue({'progress_state','deadline_elapsed_at','retry_of_request_id'} <= requests)

    def test_wrong_response_token_fails_closed(self):
        req=saas.create_request(self.c,'M1','test',lambda:T)
        with self.assertRaisesRegex(ValueError,'response token'):
            saas.respond(self.c,req['request_id'],'wrong','answer',lambda:T,model_identity='GPT-5.6 Sol')

    def test_multiple_pending_requests_are_fifo_and_not_superseded(self):
        a=saas.create_request(self.c,'M1','one',lambda:T)
        b=saas.create_request(self.c,'M1','two',lambda:T)
        rows={r['request_id']:r['status'] for r in self.c.execute('SELECT request_id,status FROM saas_handoff_requests WHERE mission_id=?',('M1',)).fetchall()}
        self.assertEqual(rows[a['request_id']],'PENDING')
        self.assertEqual(rows[b['request_id']],'PENDING')
        self.assertEqual(saas.pending_request(self.c,lambda:T,mission_id='M1')['request_id'],a['request_id'])
        status=saas.bridge_status(self.c,'M1',lambda:T)
        self.assertEqual(status['pending_count'],2)
        self.assertEqual(status['queue_policy'],'FIFO_MULTI_PENDING')

    def test_bridge_exposes_exact_dual_link_and_truthful_session_channel_state(self):
        req=saas.create_request(self.c,'M1','dual test',lambda:T)
        dual_id='dual-'+'3'*32
        self.c.execute('INSERT INTO mission_dual_evaluations(request_id,saas_request_id,updated_at) VALUES(?,?,?)',(dual_id,req['request_id'],T));self.c.commit()
        pending=saas.pending_request(self.c,lambda:T,mission_id='M1')
        self.assertEqual(pending['dual_request_id'],dual_id)
        status=saas.bridge_status(self.c,'M1',lambda:T)
        self.assertEqual(status['channel_state'],'READY_FOR_HANDOFF')
        self.assertEqual(status['session_attestation_state'],'NOT_ATTESTED')
        self.assertEqual(status['pending']['dual_request_id'],dual_id)
        saved=saas.request_status(self.c,req['request_id'],lambda:T)
        self.assertEqual(saved['dual_request_id'],dual_id)
        self.assertNotIn('response_token',saved)
        token=self.c.execute('SELECT response_token FROM saas_handoff_requests WHERE request_id=?',(req['request_id'],)).fetchone()[0]
        saas.respond(self.c,req['request_id'],token,'SAAS OK',lambda:T,model_identity='GPT-5.6 Sol')
        after=saas.bridge_status(self.c,'M1',lambda:T)
        self.assertEqual(after['session_attestation_state'],'BOUND')
        self.assertEqual(after['last_response']['request_id'],req['request_id'])
        self.assertIsNotNone(after['last_response']['receipt_digest'])

class SaaSHandoffExtensionTests(unittest.TestCase):
    def test_explicit_saas_route_is_not_capability_answer(self):
        class Dummy:
            def _route(self,m):return ('LOCAL','x')
            def state(self):return {'status':'ok'}
            def chat(self,message,use_web=False,history=None,output_language='auto'):return {'route':'LOCAL','answer':'local'}
        apply_saas_handoff_extension(Dummy)
        d=Dummy();d.control_provider=lambda op,args: ({'focus_mission_id':'M1','missions':[]} if op=='recent' else ({'request_code':'ABCD1234','request_id':'saas-'+'1'*32,'authority_effect':'NONE'} if op=='saas_request' else {'state':'UNBOUND'}))
        self.assertEqual(d._route('No to wykonaj na SaaS zapytanie: Kim jesteś?')[0],'LOCAL')
        token=ROUTE_CONTEXT.set('SAAS');self.addCleanup(lambda: ROUTE_CONTEXT.reset(token))
        self.assertEqual(d._route('No to wykonaj na SaaS zapytanie: Kim jesteś?')[0],'SAAS_HANDOFF')
        out=d.chat('No to wykonaj na SaaS zapytanie: Kim jesteś?',output_language='pl')
        self.assertEqual(out['route'],'SAAS_HANDOFF')
        self.assertIn('automatycznie',out['answer'])
        self.assertIn('EXTERNAL_SESSION_MEDIATED',out['answer'])

    def test_explicit_saas_route_reports_firefox_mediator_when_request_is_browser_bound(self):
        class Dummy:
            def _route(self,m):return ('LOCAL','x')
            def state(self):return {'status':'ok'}
            def chat(self,message,use_web=False,history=None,output_language='auto'):return {'route':'LOCAL','answer':'local'}
        apply_saas_handoff_extension(Dummy)
        d=Dummy();d.control_provider=lambda op,args: ({'focus_mission_id':'M1','missions':[]} if op=='recent' else ({'request_code':'FIRE1234','request_id':'saas-'+'f'*32,'transport':'CHATGPT_FIREFOX_PROJECT_MEDIATED','authority_effect':'NONE'} if op=='saas_request' else {'state':'UNBOUND'}))
        token=ROUTE_CONTEXT.set('SAAS');self.addCleanup(lambda: ROUTE_CONTEXT.reset(token))
        out=d.chat('SaaS: gotów?',output_language='pl')
        self.assertIn('CHATGPT_FIREFOX_PROJECT_MEDIATED',out['answer'])
        self.assertNotIn('nie istnieje automatyczny local',out['answer'])

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

    def test_dual_evaluation_dispatches_local_and_live_saas_handoff(self):
        class Dummy:
            def _route(self,m):return ('MODEL_ONLY','local')
            def state(self):return {'status':'ok'}
            def chat(self,message,use_web=False,history=None,output_language='auto'):
                return {'route':'MODEL_ONLY','answer':'LOCAL:'+message,'tool_calls':['local.model'],'material_receipts':[]}
        apply_saas_handoff_extension(Dummy)
        d=Dummy()
        def control(op,args):
            if op=='recent':return {'focus_mission_id':'M1','missions':[]}
            if op=='saas_request':return {'request_code':'DUAL1234','request_id':'saas-'+'2'*32,'authority_effect':'NONE'}
            if op=='saas_status':return {'state':'BOUND'}
            raise AssertionError(op)
        d.control_provider=control
        q='Zapytaj model SaaS i model lokalny o to samo pytanie: Co to LION'
        self.assertEqual(d._route(q)[0],'MODEL_ONLY')
        token=ROUTE_CONTEXT.set('DUAL');self.addCleanup(lambda: ROUTE_CONTEXT.reset(token))
        self.assertEqual(d._route(q)[0],'DUAL_EVALUATION_LIVE')
        out=d.chat(q,output_language='pl')
        self.assertEqual(out['route'],'DUAL_EVALUATION_LIVE')
        self.assertEqual(out['local_evaluation']['answer'],'LOCAL:Co to LION')
        self.assertEqual(out['saas_handoff']['request_code'],'DUAL1234')
        self.assertIn('lion.saas.handoff.create',out['tool_calls'])

class PanelThreadDeliveryTests(unittest.TestCase):
    def test_delete_cancels_only_saved_handoffs_and_preserves_thread_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            store=ThreadStore(Path(directory)/'threads.db')
            first=store('create',{})['thread_id'];second=store('create',{})['thread_id']
            for tid,rid in [(first,'owned'),(second,'other')]:
                store('append_pair',{'thread_id':tid,'user':'question','assistant':'waiting','meta':{'saas_request_id':rid}})
            def fail(rid):raise RuntimeError('service unavailable')
            with self.assertRaisesRegex(RuntimeError,'service unavailable'):
                store('delete',{'thread_id':first,'cancel_handoff':fail})
            self.assertEqual(len(store('get',{'thread_id':first})['messages']),2)
            cancelled=[]
            result=store('delete',{'thread_id':first,'cancel_handoff':lambda rid:cancelled.append(rid)})
            self.assertTrue(result['deleted']);self.assertEqual(cancelled,['owned'])
            with self.assertRaises(KeyError):store('get',{'thread_id':first})
            self.assertEqual(len(store('get',{'thread_id':second})['messages']),2)

    def test_saas_assistant_delivery_is_persistent_and_exactly_once(self):
        with tempfile.TemporaryDirectory() as td:
            store=ThreadStore(Path(td)/'threads.db')
            t=store('create',{})
            store('append_pair',{'thread_id':t['thread_id'],'user':'Na SaaS: test','assistant':'queued','meta':{'saas_request_id':'saas-'+'1'*32,'saas_request_code':'ABCDEF12'}})
            a=store('append_assistant_once',{'thread_id':t['thread_id'],'assistant':'real SaaS response','dedupe_key':'saas:'+'saas-'+'1'*32,'meta':{'saas_request_id':'saas-'+'1'*32,'receipt_digest':'d'*64}})
            b=store('append_assistant_once',{'thread_id':t['thread_id'],'assistant':'duplicate must not append','dedupe_key':'saas:'+'saas-'+'1'*32,'meta':{'saas_request_id':'saas-'+'1'*32}})
            self.assertTrue(a['inserted']);self.assertFalse(b['inserted'])
            snap=store('get',{'thread_id':t['thread_id']})
            self.assertEqual([m['content'] for m in snap['messages']].count('real SaaS response'),1)
            self.assertEqual(len(snap['messages']),3)
            self.assertEqual(snap['messages'][-1]['meta']['external_receipt_key'],'saas:'+'saas-'+'1'*32)

    def test_panel_thread_reopen_recovers_shared_operator_bus_by_correlation(self):
        from cyber_lion.app_coordination import local_intelligence_gateway as gateway
        ui=gateway.UI
        self.assertIn("'/api/threads/'+encodeURIComponent(activeThreadId)+'/bus'",ui)
        self.assertIn('correlation_id',Path(__import__('tools.lion_operator_client',fromlist=['x']).__file__).read_text(encoding='utf-8'))
        self.assertIn('activeThreadContext=x.context||null',ui)
        self.assertIn('await refreshActiveBus(false)',ui)
        self.assertNotIn('resumeThreadSaas',ui)
        self.assertIn('Restart material runtime',ui)

    def test_panel_keeps_bus_messages_owned_by_exact_thread_correlation(self):
        from cyber_lion.app_coordination import local_intelligence_gateway as gateway
        ui=gateway.UI
        source=Path(gateway.__file__).read_text(encoding='utf-8')
        self.assertNotIn('adoptPendingSaas',ui)
        self.assertNotIn('stopThreadPolling',ui)
        self.assertNotIn('renderSupervisor(x.supervisor_projection)',ui)
        self.assertIn("m.get('correlation_id')==tid",source)
        self.assertIn("'correlation_id':tid",source)
        self.assertIn('missionPinned=false',ui)
        self.assertIn('FOLLOW_FOCUS',ui)
        self.assertIn('missionsRefreshing',ui)

    def test_browser_no_longer_posts_dual_saas_receipt_and_has_stable_raw_ui(self):
        from cyber_lion.app_coordination import local_intelligence_gateway as gateway
        ui=gateway.UI
        self.assertNotIn("fetch('/api/dual/response'",ui)
        self.assertIn('Return to focus',ui)
        self.assertIn('missionRenderKey',ui)
        self.assertIn('stateRenderKey',ui)
        self.assertIn('html,body{height:100%;overflow:hidden}',ui)
        self.assertIn('position:fixed;left:280px;right:0;bottom:0',ui)
        self.assertIn('<summary>RAW</summary>',ui)

    def test_global_control_view_has_focus_follow_refresh_guard_and_stable_render_key(self):
        root=Path(__file__).resolve().parents[2]
        js=(root/'deploy/mission-control/v3/control-v3.js').read_text(encoding='utf-8')
        self.assertIn('MC_PINNED=false',js)
        self.assertIn('MC_REFRESHING=false',js)
        self.assertIn('mcRenderKey',js)
        self.assertIn('FOLLOW_FOCUS',js)
        self.assertIn('if(!MC_PINNED||!MC_SELECTED',js)


if __name__=='__main__':unittest.main()

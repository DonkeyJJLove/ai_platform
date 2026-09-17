import sqlite3,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from tools import lion_saas_broker as broker
from tools.lion_direct_supervisor_bridge import Bridge,DIRECT_TRANSPORT,DIRECT_ATTESTATION,PROVIDER,CONTROL_TRANSPORT

class DirectBridgeHarness(Bridge):
    def __init__(self,conn,key_file,state_db,clock):
        self.conn=conn;self.clock=clock;self.provider_calls=[];self.conversation_calls=0;self.response_calls=0
        super().__init__('http://127.0.0.1:8766',key_file,state_db,'TEST_KEY_NOT_SENT','https://api.openai.com/v1','gpt-5.6-sol',0.2)
    def broker_json(self,path,method='GET',body=None,timeout=15):
        if path=='/api/v3/saas-broker/pending':return broker.broker_pending(self.conn,self.clock)
        if path=='/api/v3/saas-broker/direct/heartbeat':return broker.record_direct_bridge_heartbeat(self.conn,body,self.clock)
        if path.startswith('/api/v3/saas-broker/requests/'):
            tail=path[len('/api/v3/saas-broker/requests/'):]
            rid,*rest=tail.split('/')
            if not rest:return broker.request_status(self.conn,rid,self.clock)
            if rest[0]=='claim':return broker.claim(self.conn,rid,self.clock)
            if rest[0]=='respond':return broker.respond(self.conn,rid,body['response_token'],body['answer'],self.clock,model_identity=body['model_identity'],transport=body['transport'],attestation_class=body['attestation_class'],claim_generation=body['claim_generation'],provider=body.get('provider'),provider_conversation_id=body.get('provider_conversation_id'),provider_response_id=body.get('provider_response_id'))
        raise AssertionError((path,method,body))
    def provider_json(self,path,body=None,timeout=120,request_key=None,method='POST'):
        self.provider_calls.append((path,body))
        if path=='/conversations':
            self.conversation_calls+=1;return {'id':'conv-test-001','object':'conversation'}
        if method=='GET' and path.startswith('/responses/'):
            rid=path.rsplit('/',1)[-1];return {'id':rid,'status':'completed','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'recovered-answer'}]}]}
        if path=='/responses':
            self.response_calls+=1
            return {'id':f'resp-test-{self.response_calls:03d}','status':'completed','conversation':{'id':body['conversation']},'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':f'answer-{self.response_calls}'}]}]}
        raise AssertionError(path)

class DirectSupervisorBridgeR1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.key=self.root/'mediator.key';self.key.write_text('k'*64)
        self.conn=sqlite3.connect(':memory:');self.conn.row_factory=sqlite3.Row
        self.conn.executescript('CREATE TABLE schema_migrations(version INTEGER,schema_id TEXT,applied_at TEXT,source_head TEXT,source_tree TEXT,migration_digest TEXT,note TEXT);CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT,spec_digest TEXT);CREATE TABLE mission_process_specs(mission_id TEXT PRIMARY KEY,authority_state TEXT,current_phase TEXT);')
        self.now=datetime(2026,9,17,10,0,tzinfo=timezone.utc)
        broker.migrate(self.conn,self.clock,source_head='a'*40,source_tree='b'*40)
        self.bridge=DirectBridgeHarness(self.conn,self.key,self.root/'bridge.db',self.clock)
    def tearDown(self):self.conn.close();self.tmp.cleanup()
    def clock(self):return self.now.isoformat().replace('+00:00','Z')
    def request(self,question='hello',thread='1'*32):
        return broker.create_request(self.conn,None,question,self.clock,scope_type='THREAD',thread_id=thread,authority_effect='NONE',control_transport=CONTROL_TRANSPORT,inference_transport=DIRECT_TRANSPORT,provider=PROVIDER)
    def test_browserless_direct_roundtrip_binds_exact_provider_receipt(self):
        req=self.request();self.assertEqual(req['status'],'WAITING_PROVIDER');self.assertEqual(req['control_transport'],CONTROL_TRANSPORT);self.assertEqual(req['inference_transport'],DIRECT_TRANSPORT)
        out=self.bridge.process_one();self.assertEqual(out['status'],'RESPONDED')
        row=broker.request_status(self.conn,req['request_id'],self.clock)
        self.assertEqual(row['status'],'RESPONDED');self.assertEqual(row['provider'],PROVIDER);self.assertEqual(row['provider_conversation_id'],'conv-test-001');self.assertEqual(row['provider_response_id'],'resp-test-001');self.assertRegex(row['receipt_digest'],r'^[0-9a-f]{64}$')
        receipt=self.conn.execute('SELECT receipt_json FROM saas_broker_receipts WHERE request_id=?',(req['request_id'],)).fetchone()[0]
        self.assertIn('OPENAI_RESPONSES_API_MEDIATED',receipt);self.assertIn('SENTINELX_OPERATOR_CONTROL',receipt);self.assertNotIn('CHATGPT_FIREFOX_PROJECT_MEDIATED',receipt)
    def test_same_lion_thread_reuses_provider_conversation(self):
        a=self.request('first');self.bridge.process_one();b=self.request('second');self.bridge.process_one()
        self.assertEqual(self.bridge.conversation_calls,1);self.assertEqual(self.bridge.response_calls,2)
        row=broker.request_status(self.conn,b['request_id'],self.clock);self.assertEqual(row['provider_conversation_id'],'conv-test-001')
    def test_completed_provider_attempt_reconciles_after_restart_without_second_inference(self):
        req=self.request('restart-window');row=broker.broker_pending(self.conn,self.clock)['requests'][0];claim=broker.claim(self.conn,req['request_id'],self.clock);key,cid=self.bridge.conversation(row);attempt=self.bridge.store.prepare_attempt(req['request_id'],claim['claim_generation'],key);self.bridge.store.finish_attempt(req['request_id'],'resp-recover-001')
        self.now+=timedelta(seconds=301);broker.request_status(self.conn,req['request_id'],self.clock)
        out=self.bridge.process_one();self.assertEqual(out['status'],'RESPONDED');self.assertEqual(self.bridge.response_calls,0);saved=broker.request_status(self.conn,req['request_id'],self.clock);self.assertEqual(saved['provider_response_id'],'resp-recover-001')

    def test_same_thread_rebind_refreshes_metadata_without_forking_provider_conversation(self):
        self.conn.execute("INSERT INTO missions(mission_id,state,spec_digest) VALUES('M1','RUNNING',?)",('1'*64,));self.conn.execute("INSERT INTO missions(mission_id,state,spec_digest) VALUES('M2','RUNNING',?)",('2'*64,));self.conn.commit()
        tid='d'*32
        a=broker.create_request(self.conn,'M1','first',self.clock,scope_type='THREAD',thread_id=tid,inference_transport=broker.DIRECT_TRANSPORT,provider=broker.DIRECT_PROVIDER);self.bridge.process_one()
        b=broker.create_request(self.conn,'M2','second',self.clock,scope_type='THREAD',thread_id=tid,inference_transport=broker.DIRECT_TRANSPORT,provider=broker.DIRECT_PROVIDER);self.bridge.process_one()
        self.assertEqual(self.bridge.conversation_calls,1)
        row=self.bridge.store.get(tid);self.assertEqual(row['conversation_id'],'conv-test-001');self.assertEqual(row['mission_id'],'M2')

    def test_absent_credential_never_claims(self):
        blocked=DirectBridgeHarness(self.conn,self.key,self.root/'blocked.db',self.clock);blocked.api_key=''
        req=self.request();self.assertFalse(blocked.process_one());self.assertEqual(broker.request_status(self.conn,req['request_id'],self.clock)['status'],'WAITING_PROVIDER');self.assertEqual(blocked.status()['credential_state'],'ABSENT')
    def test_claim_expiry_fences_stale_generation(self):
        req=self.request();claim1=broker.claim(self.conn,req['request_id'],self.clock,lease_seconds=1);self.now+=timedelta(seconds=2);broker.request_status(self.conn,req['request_id'],self.clock);claim2=broker.claim(self.conn,req['request_id'],self.clock,lease_seconds=30);self.assertGreater(claim2['claim_generation'],claim1['claim_generation'])
        with self.assertRaises(ValueError):broker.respond(self.conn,req['request_id'],claim1['response_token'],'stale',self.clock,model_identity='gpt-5.6-sol',transport=DIRECT_TRANSPORT,attestation_class=DIRECT_ATTESTATION,claim_generation=claim1['claim_generation'],provider=PROVIDER,provider_conversation_id='conv',provider_response_id='resp-old')

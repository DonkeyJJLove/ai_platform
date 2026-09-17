"""Cognitive broker acceptance without any mission records or executor."""
import sqlite3
import unittest
import tempfile
from pathlib import Path
from tools.lion_local_intelligence_runtime import ThreadStore
from cyber_lion.app_coordination.saas_thread_delivery import deliver_once

from tools import lion_saas_broker as broker


class CognitiveBrokerTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        self.conn.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, schema_id TEXT, applied_at TEXT, source_head TEXT, source_tree TEXT, migration_digest TEXT, note TEXT)')
        self.stamp = '2026-09-15T00:00:00Z'
        broker.migrate(self.conn, self.now, source_head='a'*40, source_tree='b'*40)

    def now(self):
        return self.stamp

    def request(self, **options):
        return broker.create_request(self.conn, None, 'Connectivity test', self.now, scope_type='THREAD', thread_id='a'*32, **options)

    def answer(self, claim, **options):
        options.setdefault('transport',broker.DIRECT_TRANSPORT);options.setdefault('attestation_class',broker.DIRECT_ATTESTATION_CLASS);options.setdefault('provider',broker.DIRECT_PROVIDER);options.setdefault('provider_conversation_id','conv-unit');options.setdefault('provider_response_id','resp-unit-'+claim['request_id'][-6:]);return broker.respond(self.conn, claim['request_id'], claim['response_token'], 'Connected', self.now, model_identity='gpt-5.6-sol', claim_generation=claim['claim_generation'], **options)

    def test_zero_mission_roundtrip_and_redacted_reads(self):
        request = self.request()
        self.assertIsNone(request['mission_id'])
        self.assertEqual(request['status'], 'WAITING_PROVIDER')
        self.assertNotIn('response_token', broker.broker_pending(self.conn, self.now)['requests'][0])
        claim = broker.claim(self.conn, request['request_id'], self.now)
        self.assertNotIn('response_token', broker.request_status(self.conn, request['request_id'], self.now))
        result = self.answer(claim)
        self.assertEqual(result['binding']['binding_scope'], 'GLOBAL_SUPERVISOR_CHANNEL')
        saved = broker.request_status(self.conn, request['request_id'], self.now)
        self.assertEqual((saved['status'], saved['progress_state']), ('RESPONDED', 'RECEIPT_BOUND'))
        self.assertEqual(broker.broker_pending(self.conn, self.now)['requests'], [])
        with self.assertRaises(ValueError):
            self.answer(claim)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM saas_broker_receipts').fetchone()[0], 1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE saas_broker_receipts SET receipt_json='{}'")
        self.conn.rollback()

    def test_expired_claim_cannot_answer_after_reclaim(self):
        request = self.request(ttl_seconds=1)
        first = broker.claim(self.conn, request['request_id'], self.now, lease_seconds=1)
        self.stamp = '2026-09-15T00:00:02Z'
        self.assertEqual(broker.request_status(self.conn, request['request_id'], self.now)['status'], 'WAITING_PROVIDER_OVERDUE')
        second = broker.claim(self.conn, request['request_id'], self.now)
        with self.assertRaises(ValueError):
            self.answer(first)
        self.answer(second)

    def test_wrong_token_rolls_back_and_valid_claim_still_works(self):
        claim = broker.claim(self.conn, self.request()['request_id'], self.now)
        with self.assertRaises(ValueError):
            self.answer({**claim, 'response_token':'invalid'})
        self.assertFalse(self.conn.in_transaction)
        self.answer(claim)

    def test_expired_failure_claim_is_rejected_without_prior_status_poll(self):
        request=self.request();claim=broker.claim(self.conn,request['request_id'],self.now,lease_seconds=1);self.stamp='2026-09-15T00:00:02Z'
        with self.assertRaisesRegex(ValueError,'not claimed'):
            broker.fail_request(self.conn,request['request_id'],claim['response_token'],claim['claim_generation'],'ProviderError',self.now)
        saved=broker.request_status(self.conn,request['request_id'],self.now);self.assertEqual(saved['status'],'WAITING_PROVIDER');self.assertIsNone(saved['failure_class'])

    def test_direct_failure_is_claim_fenced_and_terminal(self):
        request=self.request();claim=broker.claim(self.conn,request['request_id'],self.now,lease_seconds=1)
        with self.assertRaisesRegex(ValueError,'response token'):
            broker.fail_request(self.conn,request['request_id'],'bad',claim['claim_generation'],'ProviderError',self.now)
        self.assertEqual(broker.request_status(self.conn,request['request_id'],self.now)['status'],'CLAIMED')
        self.stamp='2026-09-15T00:00:02Z';broker.request_status(self.conn,request['request_id'],self.now);fresh=broker.claim(self.conn,request['request_id'],self.now)
        with self.assertRaisesRegex(ValueError,'stale claim generation'):
            broker.fail_request(self.conn,request['request_id'],fresh['response_token'],claim['claim_generation'],'ProviderError',self.now)
        out=broker.fail_request(self.conn,request['request_id'],fresh['response_token'],fresh['claim_generation'],'ProviderError',self.now)
        self.assertEqual((out['status'],out['progress_state']),('FAILED','PROVIDER_FAILED'));self.assertEqual(broker.broker_pending(self.conn,self.now)['requests'],[])
        saved=broker.request_status(self.conn,request['request_id'],self.now);self.assertEqual(saved['failure_class'],'ProviderError');self.assertIsNotNone(saved['failed_at'])

    def test_session_expiry_preserves_pending_request_and_old_receipt(self):
        claim = broker.claim(self.conn, self.request()['request_id'], self.now)
        first = self.answer(claim, lease_seconds=1)
        pending = self.request(ttl_seconds=1)
        self.stamp = '2026-09-15T00:00:02Z'
        self.assertEqual(broker.bridge_status(self.conn, None, self.now)['session_attestation_state'], 'EXPIRED')
        self.assertEqual(broker.request_status(self.conn, pending['request_id'], self.now)['status'], 'WAITING_PROVIDER_OVERDUE')
        second = self.answer(broker.claim(self.conn, pending['request_id'], self.now))
        self.assertNotEqual(first['binding']['binding_id'], second['binding']['binding_id'])
        self.assertEqual(broker.bridge_status(self.conn, None, self.now)['state'], 'BOUND')
        self.assertEqual(broker.request_status(self.conn, claim['request_id'], self.now)['receipt_digest'], first['receipt']['receipt_digest'])

    def test_same_live_thread_question_is_deduplicated_without_fanout(self):
        first=self.request()
        second=self.request()
        self.assertEqual(second['request_id'],first['request_id'])
        self.assertTrue(second['deduplicated'])
        rows=self.conn.execute("SELECT request_id,status FROM saas_handoff_requests").fetchall()
        self.assertEqual([(r['request_id'],r['status']) for r in rows],[(first['request_id'],'WAITING_PROVIDER')])

    def test_overdue_same_thread_question_creates_one_retry_and_supersedes_predecessor(self):
        first=self.request(ttl_seconds=1)
        self.stamp='2026-09-15T00:00:02Z'
        retry=self.request(ttl_seconds=30)
        self.assertNotEqual(retry['request_id'],first['request_id'])
        self.assertEqual(retry['retry_of_request_id'],first['request_id'])
        rows={r['request_id']:(r['status'],r['progress_state']) for r in self.conn.execute("SELECT request_id,status,progress_state FROM saas_handoff_requests")}
        self.assertEqual(rows[first['request_id']],('SUPERSEDED','SUPERSEDED_BY_RETRY'))
        self.assertEqual(rows[retry['request_id']][0],'WAITING_PROVIDER')
        status=broker.bridge_status(self.conn,None,self.now);self.assertEqual(status['pending_count'],1);self.assertEqual(status['duplicate_policy'],'EXACT_SCOPE_QUESTION_DEDUPE_WITH_OVERDUE_RETRY_LINEAGE')

    def test_distinct_thread_questions_remain_independent_fifo_handoffs(self):
        first=self.request()
        second=broker.create_request(self.conn,None,'Different question',self.now,scope_type='THREAD',thread_id='a'*32)
        self.assertNotEqual(first['request_id'],second['request_id'])
        self.assertEqual(broker.bridge_status(self.conn,None,self.now)['pending_count'],2)

    def test_terminal_mission_advisory_is_preserved_but_removed_from_active_queue(self):
        self.conn.execute("CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT NOT NULL)")
        self.conn.execute("INSERT INTO missions VALUES('M-TERM','RUNNING')")
        request=broker.create_request(self.conn,'M-TERM','advisory',self.now,scope_type='MISSION')
        self.conn.execute("UPDATE missions SET state='COMPLETE' WHERE mission_id='M-TERM'");self.conn.commit()
        self.assertEqual(len(broker.broker_pending(self.conn,self.now)['requests']),0)
        saved=broker.request_status(self.conn,request['request_id'],self.now)
        self.assertEqual((saved['status'],saved['progress_state']),('SUPERSEDED','SUPERSEDED_TERMINAL_MISSION'))

    def test_control_plane_and_authority_boundary(self):
        request = broker.create_request(self.conn, None, 'Question', self.now, scope_type='CONTROL_PLANE')
        self.assertEqual(request['scope_id'], 'GLOBAL_SUPERVISOR_CHANNEL')
        with self.assertRaises(ValueError):
            self.request(authority_effect='EXECUTE')
        with self.assertRaises(ValueError):
            broker.create_request(self.conn, None, 'Question', self.now, scope_type='MISSION')

    def _firefox_heartbeat(self, state='READY'):
        return broker.record_mediator_heartbeat(self.conn,{
            'mediator_id':'LION_FIREFOX_MEDIATOR_R1','transport':broker.FIREFOX_TRANSPORT,'state':state,
            'project_title':'LION_EVOLUSION','chat_title':'[LION MEDIATOR] SaaS Control Channel',
            'browser':'Firefox Developer Edition','authority_effect':'NONE'},self.now)


    def test_ready_heartbeat_does_not_relabel_direct_request(self):
        request=self.request();self.assertEqual(request['inference_transport'],broker.DIRECT_TRANSPORT)
        out=self._firefox_heartbeat();self.assertEqual(out['promoted_request_ids'],[])
        saved=broker.request_status(self.conn,request['request_id'],self.now)
        self.assertEqual(saved['inference_transport'],broker.DIRECT_TRANSPORT)
        self.assertEqual(saved['status'],'WAITING_PROVIDER')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM saas_transport_transitions').fetchone()[0],0)

    def test_ready_heartbeat_never_relabels_claimed_direct_request(self):
        request=self.request();broker.claim(self.conn,request['request_id'],self.now);self._firefox_heartbeat()
        saved=broker.request_status(self.conn,request['request_id'],self.now)
        self.assertEqual(saved['status'],'CLAIMED');self.assertEqual(saved['inference_transport'],broker.DIRECT_TRANSPORT)

    def test_firefox_transport_requires_explicit_request(self):
        self._firefox_heartbeat()
        status=broker.bridge_status(self.conn,None,self.now)
        self.assertEqual(status['inference_transport'],broker.DIRECT_TRANSPORT)
        self.assertTrue(status['browser_ready']);self.assertFalse(status['automatic_local_to_saas_hop'])
        request=broker.create_request(self.conn,None,'browser explicit',self.now,scope_type='THREAD',thread_id='b'*32,inference_transport=broker.FIREFOX_TRANSPORT,provider=broker.FIREFOX_PROVIDER)
        self.assertEqual(request['status'],'WAITING_BROWSER_MEDIATOR');self.assertEqual(request['inference_transport'],broker.FIREFOX_TRANSPORT)
        claim=broker.claim(self.conn,request['request_id'],self.now)
        result=broker.respond(self.conn,claim['request_id'],claim['response_token'],'Connected through Firefox',self.now,model_identity='ChatGPT UI / LION_EVOLUSION',transport=broker.FIREFOX_TRANSPORT,attestation_class=broker.FIREFOX_ATTESTATION_CLASS,claim_generation=claim['claim_generation'],provider=broker.FIREFOX_PROVIDER)
        self.assertEqual(result['binding']['transport'],broker.FIREFOX_TRANSPORT)

    def test_explicit_browser_request_does_not_mutate_existing_direct_request(self):
        direct=self.request()
        browser=broker.create_request(self.conn,None,'Connectivity test',self.now,scope_type='THREAD',thread_id='a'*32,inference_transport=broker.FIREFOX_TRANSPORT,provider=broker.FIREFOX_PROVIDER)
        self.assertNotEqual(browser['request_id'],direct['request_id'])
        old=broker.request_status(self.conn,direct['request_id'],self.now)
        self.assertEqual(old['status'],'SUPERSEDED');self.assertEqual(old['progress_state'],'SUPERSEDED_EXPLICIT_TRANSPORT_CHANGE')
        self.assertEqual(browser['inference_transport'],broker.FIREFOX_TRANSPORT)
        tr=self.conn.execute('SELECT from_transport,to_transport,reason,authority_effect FROM saas_transport_transitions WHERE request_id=?',(direct['request_id'],)).fetchone();self.assertEqual(tuple(tr),(broker.DIRECT_TRANSPORT,broker.FIREFOX_TRANSPORT,'EXPLICIT_REQUEST_TRANSPORT_CHANGE','NONE'))

    def test_stale_firefox_heartbeat_does_not_change_direct_transport(self):
        self._firefox_heartbeat();self.stamp='2026-09-15T00:00:46Z'
        status=broker.bridge_status(self.conn,None,self.now)
        self.assertEqual(status['inference_transport'],broker.DIRECT_TRANSPORT);self.assertEqual(status['browser_mediator']['state'],'STALE')
        request=self.request();self.assertEqual(request['inference_transport'],broker.DIRECT_TRANSPORT)

    def test_firefox_request_rejects_wrong_attestation_class(self):
        request=broker.create_request(self.conn,None,'browser explicit',self.now,scope_type='THREAD',thread_id='c'*32,inference_transport=broker.FIREFOX_TRANSPORT,provider=broker.FIREFOX_PROVIDER)
        claim=broker.claim(self.conn,request['request_id'],self.now)
        with self.assertRaisesRegex(ValueError,'transport/attestation'):
            broker.respond(self.conn,claim['request_id'],claim['response_token'],'answer',self.now,model_identity='ChatGPT UI',transport=broker.FIREFOX_TRANSPORT,attestation_class=broker.ATTESTATION_CLASS,claim_generation=claim['claim_generation'],provider=broker.FIREFOX_PROVIDER)

    def test_browser_independent_delivery_survives_restart_without_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'threads.db'
            store=ThreadStore(path)
            tid=store('create',{})['thread_id']
            request=broker.create_request(self.conn,None,'Question',self.now,scope_type='THREAD',thread_id=tid)
            store('append_pair',{'thread_id':tid,'user':'Question','assistant':'SAAS · WAITING','meta':{'saas_request_id':request['request_id']}})
            self.answer(broker.claim(self.conn,request['request_id'],self.now))
            def control(operation,args):
                self.assertEqual(operation,'saas_request_status')
                return broker.request_status(self.conn,args['request_id'],self.now)
            self.assertEqual(len(deliver_once(store,control)),1)
            reopened=ThreadStore(path)
            self.assertEqual(deliver_once(reopened,control),[])
            messages=reopened('get',{'thread_id':tid})['messages']
            receipts=[m for m in messages if m['meta'].get('external_receipt_key')=='saas:'+request['request_id']]
            self.assertEqual(len(receipts),1)
            self.assertIn('Connected',receipts[0]['content'])


if __name__ == '__main__':
    unittest.main()

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
        return broker.respond(self.conn, claim['request_id'], claim['response_token'], 'Connected', self.now, model_identity='UNIT_TEST_MEDIATOR', claim_generation=claim['claim_generation'], **options)

    def test_zero_mission_roundtrip_and_redacted_reads(self):
        request = self.request()
        self.assertIsNone(request['mission_id'])
        self.assertEqual(request['status'], 'WAITING_SUPERVISOR')
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
        self.assertEqual(broker.request_status(self.conn, request['request_id'], self.now)['status'], 'WAITING_OPERATOR_OVERDUE')
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

    def test_session_expiry_preserves_pending_request_and_old_receipt(self):
        claim = broker.claim(self.conn, self.request()['request_id'], self.now)
        first = self.answer(claim, lease_seconds=1)
        pending = self.request(ttl_seconds=1)
        self.stamp = '2026-09-15T00:00:02Z'
        self.assertEqual(broker.bridge_status(self.conn, None, self.now)['session_attestation_state'], 'EXPIRED')
        self.assertEqual(broker.request_status(self.conn, pending['request_id'], self.now)['status'], 'WAITING_OPERATOR_OVERDUE')
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
        self.assertEqual([(r['request_id'],r['status']) for r in rows],[(first['request_id'],'WAITING_SUPERVISOR')])

    def test_overdue_same_thread_question_preserves_one_request_without_automatic_retry(self):
        first=self.request(ttl_seconds=1)
        self.stamp='2026-09-15T00:00:02Z'
        same=self.request(ttl_seconds=30)
        self.assertEqual(same['request_id'],first['request_id'])
        self.assertTrue(same['deduplicated'])
        rows={r['request_id']:(r['status'],r['progress_state']) for r in self.conn.execute("SELECT request_id,status,progress_state FROM saas_handoff_requests")}
        self.assertEqual(rows[first['request_id']],('WAITING_OPERATOR_OVERDUE','WAITING_OPERATOR_OVERDUE'))
        status=broker.bridge_status(self.conn,None,self.now)
        self.assertEqual(status['pending_count'],1)
        self.assertEqual(status['duplicate_policy'],'EXACT_SCOPE_QUESTION_DEDUPE_PRESERVE_OVERDUE')

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


    def test_ready_heartbeat_promotes_existing_manual_request_in_place_with_immutable_transition(self):
        request=self.request()
        self.assertEqual(request['transport'],broker.TRANSPORT)
        heartbeat={
            'mediator_id':'LION_FIREFOX_MEDIATOR_R1','transport':broker.FIREFOX_TRANSPORT,'state':'READY',
            'project_title':'LION_EVOLUSION','chat_title':'[LION MEDIATOR] SaaS Control Channel',
            'browser':'Firefox Developer Edition','authority_effect':'NONE',
        }
        out=broker.record_mediator_heartbeat(self.conn,heartbeat,self.now)
        self.assertEqual(out['promoted_request_ids'],[request['request_id']])
        saved=broker.request_status(self.conn,request['request_id'],self.now)
        self.assertEqual(saved['request_id'],request['request_id'])
        self.assertEqual(saved['transport'],broker.FIREFOX_TRANSPORT)
        self.assertEqual(saved['progress_state'],'WAITING_BROWSER_MEDIATOR')
        row=self.conn.execute('SELECT * FROM saas_transport_transitions WHERE request_id=?',(request['request_id'],)).fetchone()
        self.assertEqual((row['from_transport'],row['to_transport'],row['authority_effect']),(broker.TRANSPORT,broker.FIREFOX_TRANSPORT,'NONE'))
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE saas_transport_transitions SET reason='tampered' WHERE request_id=?",(request['request_id'],))
        self.conn.rollback()

    def test_ready_heartbeat_never_relabels_claimed_manual_request(self):
        request=self.request();claim=broker.claim(self.conn,request['request_id'],self.now)
        heartbeat={
            'mediator_id':'LION_FIREFOX_MEDIATOR_R1','transport':broker.FIREFOX_TRANSPORT,'state':'READY',
            'project_title':'LION_EVOLUSION','chat_title':'[LION MEDIATOR] SaaS Control Channel',
            'browser':'Firefox Developer Edition','authority_effect':'NONE',
        }
        out=broker.record_mediator_heartbeat(self.conn,heartbeat,self.now)
        self.assertEqual(out['promoted_request_ids'],[])
        saved=broker.request_status(self.conn,request['request_id'],self.now)
        self.assertEqual(saved['status'],'CLAIMED')
        self.assertEqual(saved['transport'],broker.TRANSPORT)

    def test_ready_firefox_mediator_switches_transport_and_real_response_binding(self):
        self._firefox_heartbeat()
        status=broker.bridge_status(self.conn,None,self.now)
        self.assertTrue(status['automatic_local_to_saas_hop'])
        self.assertFalse(status['operator_mediation_required'])
        self.assertEqual(status['transport'],broker.FIREFOX_TRANSPORT)
        self.assertEqual(status['mediator']['state'],'READY')
        request=self.request()
        self.assertEqual(request['transport'],broker.FIREFOX_TRANSPORT)
        claim=broker.claim(self.conn,request['request_id'],self.now)
        result=broker.respond(self.conn,claim['request_id'],claim['response_token'],'Connected through Firefox',self.now,
            model_identity='ChatGPT UI / LION_EVOLUSION',transport=broker.FIREFOX_TRANSPORT,
            attestation_class=broker.FIREFOX_ATTESTATION_CLASS,claim_generation=claim['claim_generation'])
        self.assertEqual(result['binding']['transport'],broker.FIREFOX_TRANSPORT)
        self.assertEqual(result['binding']['supervisor_role'],'CHATGPT_FIREFOX_PROJECT_MEDIATOR')

    def test_transport_migration_preserves_exact_pending_request_id_without_fanout(self):
        old=self.request()
        self.assertEqual(old['transport'],broker.TRANSPORT)
        self._firefox_heartbeat()
        saved=broker.request_status(self.conn,old['request_id'],self.now)
        self.assertEqual(saved['request_id'],old['request_id'])
        self.assertEqual(saved['transport'],broker.FIREFOX_TRANSPORT)
        self.assertEqual(saved['progress_state'],'WAITING_BROWSER_MEDIATOR')
        same=self.request()
        self.assertEqual(same['request_id'],old['request_id'])
        self.assertTrue(same['deduplicated'])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM saas_handoff_requests').fetchone()[0],1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM saas_transport_transitions WHERE request_id=?',(old['request_id'],)).fetchone()[0],1)

    def test_stale_firefox_heartbeat_fails_back_to_manual_transport(self):
        self._firefox_heartbeat()
        self.stamp='2026-09-15T00:00:46Z'
        status=broker.bridge_status(self.conn,None,self.now)
        self.assertFalse(status['automatic_local_to_saas_hop'])
        self.assertEqual(status['transport'],broker.TRANSPORT)
        self.assertEqual(status['mediator']['state'],'STALE')
        request=self.request()
        self.assertEqual(request['transport'],broker.TRANSPORT)

    def test_firefox_request_rejects_wrong_attestation_class(self):
        self._firefox_heartbeat()
        claim=broker.claim(self.conn,self.request()['request_id'],self.now)
        with self.assertRaisesRegex(ValueError,'transport/attestation'):
            broker.respond(self.conn,claim['request_id'],claim['response_token'],'answer',self.now,
                model_identity='ChatGPT UI',transport=broker.FIREFOX_TRANSPORT,
                attestation_class=broker.ATTESTATION_CLASS,claim_generation=claim['claim_generation'])

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

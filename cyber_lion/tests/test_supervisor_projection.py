import copy
import unittest

from cyber_lion.mission_control.supervisor_projection import supervisor_projection
from cyber_lion.app_coordination.saas_handoff_extension import apply_saas_handoff_extension

NOW = '2026-09-14T12:00:00Z'

def bridge():
    return {
        'state': 'BOUND', 'channel_state': 'READY_FOR_HANDOFF',
        'session_attestation_state': 'BOUND', 'session_scope': 'GLOBAL_SUPERVISOR_CHANNEL',
        'binding': {'model_identity': 'GPT-5.6 Sol', 'expires_at': '2026-09-14T13:00:00Z'},
        'transport': 'CHATGPT_SENTINELX_SESSION_MEDIATED',
        'automatic_local_to_saas_hop': False, 'authority_effect': 'NONE',
        'pending': None, 'pending_count': 0, 'last_response': None,
    }

class SupervisorProjectionTests(unittest.TestCase):
    def project(self, value, **kw):
        return supervisor_projection(value, now=NOW, observed_at=kw.get('observed_at', NOW))

    def test_bound_is_not_automatic_hop_and_does_not_mutate_source(self):
        value = bridge(); original = copy.deepcopy(value)
        view = self.project(value)
        self.assertEqual(view['session'], 'BOUND')
        self.assertEqual(view['lease']['state'], 'ACTIVE')
        self.assertFalse(view['automatic_hop'])
        self.assertEqual(view['authority'], 'NONE')
        self.assertEqual(value, original)

    def test_expired_binding_does_not_claim_current_session(self):
        value = bridge(); value['binding']['expires_at'] = NOW
        view = self.project(value)
        self.assertEqual(view['session'], 'EXPIRED')
        self.assertEqual(view['lease']['state'], 'EXPIRED')

    def test_stale_or_missing_observation_does_not_claim_current_session(self):
        for observed_at in ('2026-09-14T11:00:00Z', None, 'invalid', '2026-09-14T13:00:00Z'):
            with self.subTest(observed_at=observed_at):
                view = self.project(bridge(), observed_at=observed_at)
                self.assertEqual(view['session'], 'UNKNOWN')
                self.assertIn('BOUND_CURRENTNESS_UNVERIFIED', view['unknown_reasons'])

    def test_absent_bridge_is_unknown_not_unbound(self):
        view = self.project(None)
        self.assertEqual(view['session'], 'UNKNOWN')
        self.assertIsNone(view['automatic_hop'])
        self.assertIn('BRIDGE_UNAVAILABLE', view['unknown_reasons'])

    def test_pending_and_receipt_are_independent_of_bound_state_and_sanitized(self):
        value = bridge()
        value['pending'] = {'request_id': 'req-1', 'request_code': 'code', 'response_token': 'secret'}
        value['pending_count'] = 1
        value['last_response'] = {'request_id': 'req-0', 'receipt_digest': 'digest'}
        view = self.project(value)
        self.assertEqual(view['session'], 'BOUND')
        self.assertEqual(view['pending']['request_id'], 'req-1')
        self.assertEqual(view['last_receipt']['receipt_digest'], 'digest')
        self.assertNotIn('response_token', view['pending'])

    def test_unattested_pending_stays_unattested(self):
        value = bridge(); value.update(state='PENDING_HANDOFF', binding=None, session_attestation_state='NOT_ATTESTED', pending={'request_id':'req-1'})
        self.assertEqual(self.project(value)['session'], 'NOT_ATTESTED')

    def test_expired_history_is_retained_without_active_binding(self):
        value = bridge()
        value['last_binding'] = dict(value['binding'], status='EXPIRED', expires_at=NOW)
        value.update(binding=None, session_attestation_state='NOT_ATTESTED', state='UNBOUND')
        view = self.project(value)
        self.assertEqual(view['session'], 'EXPIRED')
        self.assertEqual(view['lease']['state'], 'EXPIRED')
        self.assertEqual(view['model'], 'GPT-5.6 Sol')

    def test_invalid_expiry_and_missing_model_are_explicit(self):
        value = bridge(); value['binding'] = {'expires_at': 'invalid'}
        view = self.project(value)
        self.assertEqual(view['session'], 'UNKNOWN')
        self.assertIn('LEASE_UNKNOWN', view['unknown_reasons'])
        self.assertIn('MODEL_UNKNOWN', view['unknown_reasons'])

class SupervisorCapabilityTests(unittest.TestCase):
    def setUp(self):
        class Dummy:
            def _route(self, message): return 'MODEL_ONLY', 'fallback'
            def state(self): return {}
            def chat(self, message, **kwargs): return {'answer':'fallback'}
            @staticmethod
            def _capability_answer(*args): return 'fallback'
        apply_saas_handoff_extension(Dummy)
        self.dummy = Dummy()

    def test_polish_connection_variants_route_and_read_exact_projection(self):
        view = supervisor_projection(bridge(), now=NOW, observed_at=NOW)
        for question in ('mamy łączność z SaaS?', 'Masz łączność z SaaS?', 'czy mamy lacznosc z ChatGPT?'):
            with self.subTest(question=question):
                self.assertEqual(self.dummy._route(question)[0], 'LION_CAPABILITY_CURRENTNESS')
                answer = self.dummy._capability_answer(question, {}, {'supervisor_projection':view, 'saas_session_bridge':{'state':'UNBOUND'}}, 'pl')
                self.assertIn('sesja: BOUND', answer)
                self.assertIn('GPT-5.6 Sol', answer)
                self.assertIn('automatic_local_to_saas_hop=false', answer)
                self.assertIn('authority_effect=NONE', answer)

    def test_unknown_does_not_claim_live_connection(self):
        answer = self.dummy._capability_answer('mamy łączność z SaaS?', {}, {}, 'pl')
        self.assertIn('sesja: UNKNOWN', answer)
        self.assertIn('BRIDGE_UNAVAILABLE', answer)

    def test_state_without_focus_is_unknown(self):
        calls = []
        def provider(op, args):
            calls.append((op,args))
            return {'focus_mission_id': None} if op == 'recent' else bridge()
        self.dummy.control_provider = provider
        state = self.dummy.state()
        self.assertEqual(calls, [('recent', {})])
        self.assertEqual(state['supervisor_projection']['session'], 'UNKNOWN')
        self.assertIn('BRIDGE_READ_FAILED:NO_FOCUS_MISSION', state['supervisor_projection']['unknown_reasons'])

    def test_state_reuses_supplied_canonical_snapshot_without_recomputing(self):
        projection = supervisor_projection(bridge(), now=NOW, observed_at=NOW)
        value = dict(bridge(), supervisor_projection=projection)
        self.dummy.control_provider = lambda op,args: {'focus_mission_id':'M1'} if op == 'recent' else value
        self.assertIs(self.dummy.state()['supervisor_projection'], projection)

    def test_provider_failure_does_not_reuse_cached_bound_projection(self):
        def provider(op,args): raise RuntimeError('unavailable')
        self.dummy.control_provider = provider
        view = self.dummy.state()['supervisor_projection']
        self.assertEqual(view['session'], 'UNKNOWN')
        self.assertIn('BRIDGE_READ_FAILED:RuntimeError', view['unknown_reasons'])

class ActualGatewaySupervisorTests(unittest.TestCase):
    def test_connection_question_uses_one_snapshot_without_model_call(self):
        from unittest.mock import Mock, patch
        from cyber_lion.tests.test_r10_local_intelligence import T
        # Use the same Gateway extension wiring as the production launcher.
        from tools.lion_local_intelligence_runtime import Gateway

        fixture = T()
        temporary, repository = fixture.ctxrepo()
        self.addCleanup(temporary.cleanup)
        view = supervisor_projection(bridge(), now=NOW, observed_at=NOW)
        bridge_value = dict(bridge(), supervisor_projection=view)
        control = Mock(side_effect=lambda operation, arguments: (
            {'focus_mission_id': 'M1', 'missions': [{'mission_id': 'M1', 'state': 'RUNNING'}]}
            if operation == 'recent' else bridge_value
        ))
        model = Mock(side_effect=AssertionError('Capability question must not invoke a model'))
        gateway = Gateway(
            repository, None, None, None, 'http://127.0.0.1:8772', 'b' * 64,
            model, fixture.curprov, fixture.gitprov, control_provider=control,
        )
        question = 'mamy łączność z SaaS?'
        answer_snapshot = {}
        original_answer = gateway._capability_answer

        def capture_answer(message, mission, state, language):
            answer_snapshot['projection'] = state['supervisor_projection']
            answer_snapshot['answer'] = original_answer(message, mission, state, language)
            return answer_snapshot['answer']

        with patch.object(gateway, 'state', wraps=gateway.state) as state_read:
            with patch.object(gateway, '_capability_answer', side_effect=capture_answer) as answer_render:
                result = gateway.chat(question, output_language='pl')
        model.assert_not_called()
        state_read.assert_called_once_with()
        answer_render.assert_called_once()
        self.assertEqual(result['route'], 'LION_CAPABILITY_CURRENTNESS')
        self.assertEqual(result['answer'], answer_snapshot['answer'])
        self.assertIs(result['supervisor_projection'], answer_snapshot['projection'])
        self.assertIs(result['supervisor_projection'], view)
        self.assertIn('sesja: BOUND', result['answer'])
        self.assertIn('GPT-5.6 Sol', result['answer'])
        self.assertIn('automatic_local_to_saas_hop=false', result['answer'])
        self.assertEqual(sum(call.args[0] == 'saas_status' for call in control.call_args_list), 1)


class SupervisorBridgeProjectionTests(unittest.TestCase):
    def test_bridge_status_retains_expired_lease_and_uses_shared_projection(self):
        import sqlite3
        from tools import lion_saas_session_bridge as saas
        connection = sqlite3.connect(':memory:')
        self.addCleanup(connection.close)
        connection.row_factory = sqlite3.Row
        connection.executescript(saas.DDL)
        connection.execute(
            "INSERT INTO saas_session_bindings(binding_id,mission_id,lpcl_digest,supervisor_role,model_identity,transport,attestation_class,authority_effect,status,created_at,bound_at,expires_at,attestation_json,attestation_digest,binding_scope) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ('binding-1', 'M1', 'digest', 'supervisor', 'GPT-5.6 Sol', saas.TRANSPORT, 'operator', 'NONE', 'BOUND', NOW, NOW, '2026-09-14T13:00:00Z', '{}', 'digest', 'GLOBAL_SUPERVISOR_CHANNEL'),
        )
        active = saas.bridge_status(connection, 'M2', lambda: NOW)
        self.assertEqual(active['supervisor_projection']['session'], 'BOUND')
        self.assertFalse(active['supervisor_projection']['automatic_hop'])
        later = '2026-09-14T14:00:00Z'
        expired = saas.bridge_status(connection, 'M2', lambda: later)
        self.assertIsNone(expired['binding'])
        self.assertEqual(expired['session_attestation_state'], 'NOT_ATTESTED')
        self.assertEqual(expired['supervisor_projection']['session'], 'EXPIRED')
        self.assertEqual(expired['supervisor_projection']['lease']['expires_at'], '2026-09-14T13:00:00Z')
        self.assertEqual(expired['supervisor_projection'], supervisor_projection(expired, now=later, observed_at=later))

if __name__ == '__main__':
    unittest.main()

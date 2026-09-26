from copy import deepcopy
import unittest

from cyber_lion.mission_control.runtime_projection import normalize_snapshot, validate_registration, SCHEMA_VERSION


def mission():
    return {'mission_id': 'test', 'title': 'Test mission', 'adapter': 'LPCL_MISSION', 'state': 'RUNNING', 'runtime_state': 'DRIVER_ACTIVE', 'updated_at': '2026-09-14T12:00:00Z', 'process': {'objective': 'Observe', 'description': 'Read observations', 'progress': 30, 'current_phase': None, 'authority_state': 'NONE'}, 'phases': [{'phase_id': 'ONE', 'status': 'RUNNING', 'progress': 30}], 'workers': [{'pod_uid': 'uid-one', 'pod_name': 'worker-one', 'ready': 1}], 'protocol_messages': [{'phase': 'ONE', 'protocol': 'EVIDENCE', 'id': 1}], 'phase_execution_specs': [{'phase_id': 'ONE', 'handler_id': 'EXISTING', 'handler_version': 'v1'}]}


class RuntimeProjectionTests(unittest.TestCase):
    def test_pure_additive_projection_and_shared_summary(self):
        raw = mission(); before = deepcopy(raw)
        result = normalize_snapshot(raw)
        self.assertEqual(raw, before)
        for key, value in raw.items():
            self.assertEqual(result[key], value)
        self.assertEqual(result['normalized_schema_version'], SCHEMA_VERSION)
        self.assertEqual(result['mission_summary']['current_phase'], result['normalized_runtime']['runtime']['current_phase'])
        self.assertEqual(result['mission_summary']['objective'], result['normalized_runtime']['objective']['text'])
        self.assertEqual(result['mission_summary']['projection_revision'], result['projection_revision'])

    def test_derivation_requires_unambiguous_active_phase(self):
        raw = mission()
        self.assertEqual(normalize_snapshot(raw)['mission_summary']['current_phase_reason'], 'DERIVED_SINGLE_ACTIVE_PHASE')
        raw['phases'].append({'phase_id': 'TWO', 'status': 'ACTIVE'})
        projected = normalize_snapshot(raw)['mission_summary']
        self.assertIsNone(projected['current_phase'])
        self.assertEqual(projected['current_phase_reason'], 'AMBIGUOUS_ACTIVE_PHASES')
        raw['process']['current_phase'] = 'ONE'
        self.assertEqual(normalize_snapshot(raw)['mission_summary']['current_phase_reason'], 'RECORDED_PROCESS_CURSOR')
        raw['process']['current_phase'] = None
        for phase in raw['phases']: phase['status'] = 'COMPLETE'
        self.assertEqual(normalize_snapshot(raw)['mission_summary']['current_phase_reason'], 'NO_ACTIVE_PHASE_RECORDED')

    def test_driver_state_does_not_invent_material_readiness(self):
        projected = normalize_snapshot(mission())['normalized_runtime']
        self.assertIsNone(projected['runtime']['material_state'])
        self.assertEqual(projected['runtime']['material_state_reason'], 'RAW_VALUE_IS_DRIVER_STATE')
        self.assertIsNone(projected['environment']['node'])
        self.assertIsNone(projected['environment']['hosts'])
        self.assertEqual(projected['fleet']['material_workers'][0]['pod_uid'], 'uid-one')

    def test_waiting_driver_cursor_is_observable_without_inventing_completed_phase(self):
        raw = mission()
        raw['phases'][0]['status'] = 'WAITING'
        raw['execution_driver'] = {'state': 'WAITING', 'current_phase': 'ONE'}
        summary = normalize_snapshot(raw)['mission_summary']
        self.assertEqual((summary['current_phase'], summary['current_phase_reason']), ('ONE', 'RECORDED_DRIVER_CURSOR'))
        raw['phases'][0]['status'] = 'COMPLETE'
        self.assertIsNone(normalize_snapshot(raw)['mission_summary']['current_phase'])

    def test_supervisor_wait_state_is_distinct_from_generic_blocked(self):
        raw=mission()
        raw['process']['current_phase']='ONE'
        raw['phases'][0]['status']='BLOCKED'
        raw['execution_driver']={
            'driver_id':'driver','generation':3,'state':'BLOCKED','current_phase':'ONE',
            'blocking_gate':'EVIDENCE_REQUIREMENTS_NOT_SATISFIED','next_action':'WAIT_FOR_EVIDENCE',
            'heartbeat_at':'2026-09-26T11:39:45Z',
        }
        raw['scheduler']={'heartbeat_at':'2026-09-26T11:39:46Z'}
        raw['phase_activity']={'ONE':{'last_activity_at':'2026-09-26T11:39:41Z','last_activity_kind':'ASSIGNMENT'}}
        raw['phase_curriculum']={'runs':{'ONE':{
            'state':'WAITING_SUPERVISOR',
            'resolution':{
                'state':'WAITING_SUPERVISOR','step':'AWAIT_SUPERVISOR_RECEIPT',
                'supervisor_request':{
                    'request_id':'saas-1','status':'WAITING_SUPERVISOR',
                    'progress_state':'WAITING_SUPERVISOR','next_expected':'SUPERVISOR_RESPONSE'
                }
            }
        }}}
        phase=normalize_snapshot(raw)['normalized_runtime']['phases'][0]
        self.assertEqual(phase['activity_state'],'WAITING_SUPERVISOR')
        self.assertEqual(phase['activity']['next_expected'],'SUPERVISOR_RESPONSE')
        self.assertEqual(phase['activity']['supervisor_request']['request_id'],'saas-1')
        self.assertEqual(phase['curriculum']['resolution']['state'],'WAITING_SUPERVISOR')

    def test_historical_absence_is_distinct_from_current_missing(self):
        historical = normalize_snapshot({'mission_id': 'old', 'adapter': 'LEGACY_OBSERVATION:VKT'})['normalized_runtime']
        self.assertEqual(historical['record_class'], 'HISTORICAL_PARTIAL_SCHEMA')
        self.assertTrue(historical['gaps'])
        self.assertTrue(all(gap['reason'] == 'HISTORICAL_NOT_RECORDED' for gap in historical['gaps']))
        self.assertIsNone(historical['objective']['text'])
        current = normalize_snapshot({'mission_id': 'new', 'adapter': 'LPCL_MISSION'})['normalized_runtime']
        self.assertEqual(current['record_class'], 'CURRENT_SCHEMA_INCOMPLETE')
        self.assertTrue(all(gap['reason'] == 'NOT_RECORDED' for gap in current['gaps']))

    def test_revision_stable_across_read_clock_changes_but_tracks_content(self):
        raw = mission(); first = normalize_snapshot(raw)['projection_revision']
        raw['read_at'] = '2027-01-01T00:00:00Z'
        self.assertEqual(normalize_snapshot(raw)['projection_revision'], first)
        raw['phases'][0]['progress'] = 40
        self.assertNotEqual(normalize_snapshot(raw)['projection_revision'], first)

    def test_handler_and_evidence_are_observations_not_control_permission(self):
        phase = normalize_snapshot(mission())['normalized_runtime']['phases'][0]
        self.assertEqual(phase['handler_id'], 'EXISTING')
        self.assertEqual(phase['evidence_count'], 1)
        self.assertNotIn('START', phase['capabilities'])
        self.assertFalse(phase['capabilities']['PAUSE']['supported'])
        self.assertTrue(phase['capabilities']['INSPECT']['supported'])

    def test_phase_handler_spec_does_not_replace_mission_class(self):
        raw = mission()
        raw['spec_json'] = '{"mission_class":"LPCL_MISSION","schema_version":"lion.mission-runtime/v1"}'
        self.assertEqual(normalize_snapshot(raw)['normalized_runtime']['identity']['mission_class'], 'LPCL_MISSION')

    def test_total_evidence_survives_recent_message_window_eviction(self):
        raw = mission()
        raw['protocol_messages'] = []
        raw['phase_evidence_counts'] = {'ONE': 140}
        phase = normalize_snapshot(raw)['normalized_runtime']['phases'][0]
        self.assertEqual((phase['evidence_count'],phase['evidence_count_scope']), (140,'PERSISTED_TOTAL'))

    def test_registration_rejects_incomplete_intake_and_accepts_existing_contract(self):
        valid = {'mission_id': 'new', 'title': 'New', 'objective': 'Observe', 'description': '', 'lpcl_digest': 'a'*64, 'source_head': 'b'*40, 'source_tree': 'c'*40, 'phases': [{'id': 'ONE', 'title': 'Observe'}], 'logical_count': 1, 'material_target': 0}
        validate_registration(valid)
        for key in ('objective', 'source_head', 'phases', 'logical_count'):
            incomplete = dict(valid); incomplete.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_registration(incomplete)
        with self.assertRaises(ValueError):
            validate_registration({**valid, 'logical_count': True})


if __name__ == '__main__':
    unittest.main()

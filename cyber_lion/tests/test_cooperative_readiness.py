"""Deterministic acceptance criteria fixed before the live model generates data."""
from __future__ import annotations
import copy
import json
import unittest
from cyber_lion.mission_control.cooperative_readiness import SCHEMA, observation_ready, validate_corpus


def fixture_corpus():
    base = dict(state='READY', transport_state='READY', mission_control_reachability='OK', model_reachability='OK', age_seconds=0)
    changes = [({}, True), ({'age_seconds':20}, True), ({'age_seconds':21}, False), ({'age_seconds':-1}, False),
               ({'state':'STOPPED'}, False), ({'transport_state':'DEGRADED'}, False),
               ({'mission_control_reachability':'DOWN'}, False), ({'model_reachability':'DOWN'}, False)]
    return {'schema':SCHEMA, 'cases':[dict(base, **change, id='case-'+str(i), expected_ready=expected) for i,(change,expected) in enumerate(changes)]}


def encode(value):
    return json.dumps(value, separators=(',',':')).encode('utf-8')


class CooperativeReadinessTests(unittest.TestCase):
    def test_all_fixed_boundaries(self):
        value=fixture_corpus()
        for case in value['cases']:
            self.assertIs(observation_ready(case),case['expected_ready'])
        self.assertEqual(validate_corpus(encode(value))['case_count'],8)

    def test_bad_labels_rejected(self):
        value=fixture_corpus(); value['cases'][0]['expected_ready']=False
        with self.assertRaisesRegex(ValueError,'expectation mismatch'): validate_corpus(encode(value))

    def test_missing_boundary_rejected(self):
        value=fixture_corpus(); value['cases'][1]['age_seconds']=10
        with self.assertRaisesRegex(ValueError,'boundary coverage'): validate_corpus(encode(value))

    def test_duplicate_id_rejected(self):
        value=fixture_corpus(); value['cases'][1]['id']=value['cases'][0]['id']
        with self.assertRaisesRegex(ValueError,'case id'): validate_corpus(encode(value))

    def test_duplicate_json_key_rejected(self):
        raw=encode(fixture_corpus()).replace(b'"age_seconds":0',b'"age_seconds":0,"age_seconds":0',1)
        with self.assertRaisesRegex(ValueError,'duplicate'): validate_corpus(raw)

    def test_missing_required_field_rejected(self):
        value=fixture_corpus(); value['cases'][0].pop('model_reachability')
        with self.assertRaisesRegex(ValueError,'case fields'): validate_corpus(encode(value))

    def test_bad_age_types_never_ready(self):
        value=fixture_corpus()['cases'][0]
        for age in [True,None,'0',float('nan'),float('inf')]:
            with self.subTest(age=age): self.assertFalse(observation_ready(dict(value,age_seconds=age)))

    def test_invalid_freshness_limit(self):
        for limit in [0,-1,301,True,'20']:
            with self.subTest(limit=limit),self.assertRaises(ValueError): observation_ready({},max_age_seconds=limit)

    def test_model_endpoint_ok_does_not_override_stopped_worker(self):
        self.assertFalse(observation_ready(dict(fixture_corpus()['cases'][0],state='STOPPED')))

    def test_model_endpoint_missing_is_not_ready(self):
        value=fixture_corpus()['cases'][0]; value.pop('model_reachability')
        self.assertFalse(observation_ready(value))

    def test_payload_limit(self):
        for raw in [b'',b'x'*16385]:
            with self.assertRaises(ValueError): validate_corpus(raw)

    def test_json_nonfinite_and_boolean_age_rejected(self):
        for age in [float('nan'),True]:
            value=fixture_corpus(); value['cases'][0]['age_seconds']=age
            with self.assertRaises(ValueError): validate_corpus(encode(value))

    def test_future_observation_is_not_fresh(self):
        self.assertFalse(observation_ready(dict(fixture_corpus()['cases'][0],age_seconds=-0.01)))

if __name__=='__main__':unittest.main()

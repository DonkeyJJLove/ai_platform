import unittest
from unittest.mock import patch
from cyber_lion.tests import test_reporting_freshness as fixture
from cyber_lion.mission_control.adapters.vkt_r3 import VktR3Adapter
from cyber_lion.mission_control.adapters.oss_repository_test import OssRepositoryTestAdapter

class ReasonTests(unittest.TestCase):
    setUp = fixture.ReportingTests.setUp
    tearDown = fixture.ReportingTests.tearDown
    def test_safe_empty_reason_and_error_reset(self):
        self.adapter.runs=[]; self.adapter.empty_reason='K3S_NOT_RUNNING'
        self.mc.poll_once()
        d=self.mc.summary()['observation']['adapters']['TEST']
        self.assertEqual(d['empty_reason'],'K3S_NOT_RUNNING')
        self.assertEqual(d['reason'],'EMPTY_OBSERVATION')
        self.adapter.fail=True; self.mc.poll_once()
        self.assertNotIn('empty_reason',self.mc.summary()['observation']['adapters']['TEST'])
    def test_untrusted_reason_not_exposed(self):
        self.adapter.runs=[]; self.adapter.empty_reason='arbitrary-private-text'
        self.mc.poll_once()
        self.assertNotIn('empty_reason',self.mc.summary()['observation']['adapters']['TEST'])
    def test_adapter_classification(self):
        a=VktR3Adapter('a'*40,'b'*40)
        with patch.object(a,'_read',return_value={'status':'K3S_NOT_RUNNING','materialized':0}):
            self.assertEqual(a.poll(),[]); self.assertEqual(a.empty_reason,'K3S_NOT_RUNNING')
        with patch.object(a,'_read',return_value={'materialized':0}):
            self.assertEqual(a.poll(),[]); self.assertEqual(a.empty_reason,'NO_MATERIALIZED_FLEET')
        a=OssRepositoryTestAdapter('a'*40,'b'*40)
        with patch.object(a,'_read',return_value={'status':'ABSENT'}):
            self.assertEqual(a.poll(),[]); self.assertEqual(a.empty_reason,'ABSENT')

    def test_recovery_clears_empty_reason(self):
        original=self.adapter.runs
        self.adapter.runs=[]; self.adapter.empty_reason='K3S_NOT_RUNNING'; self.mc.poll_once()
        self.adapter.runs=original; self.mc.poll_once()
        d=self.mc.summary()['observation']['adapters']['TEST']
        self.assertEqual(d['reason'],'OBSERVED'); self.assertNotIn('empty_reason',d)

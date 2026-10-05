"""Regression use of exact DATA bytes produced by MD001's real local-model call."""
from hashlib import sha256
import json
from pathlib import Path
import unittest
from cyber_lion.mission_control.cooperative_readiness import validate_corpus

CORPUS=Path(__file__).parent/'fixtures/cooperative_readiness_r3.json'

class GeneratedReadinessCorpusTests(unittest.TestCase):
    def test_exact_recorded_corpus_and_eight_boundaries(self):
        data=CORPUS.read_bytes()
        self.assertEqual(sha256(data).hexdigest(),'1864a7bada4efcda446f393a4b1afb5ef579888e4d56a5025c45a769b1784ebc')
        self.assertEqual(validate_corpus(data)['case_count'],8)

    def test_corrupted_expectation_is_rejected(self):
        value=json.loads(CORPUS.read_bytes());value['cases'][0]['expected_ready']=False
        with self.assertRaisesRegex(ValueError,'expectation mismatch'):
            validate_corpus(json.dumps(value).encode('utf-8'))

if __name__=='__main__':unittest.main()

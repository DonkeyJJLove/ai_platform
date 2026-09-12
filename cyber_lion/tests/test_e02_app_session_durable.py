from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sqlite3,tempfile,unittest

from cyber_lion.app_coordination.e02_app_session_attestation import (
    AppSessionAttestationVerifier, AppSessionAttestationVerificationError,
    ExternalAppSessionEvidence, InMemoryAppSessionReplayGuard, InMemoryAppSessionSequenceGuard,
)
from cyber_lion.app_coordination.e02_app_session_durable import DurableAppSessionStateStore,AppSessionDurableStateError
from cyber_lion.app_coordination.e02_trust_primitives import AppSessionAttestationCandidate,TrustedTimeCandidate

D=lambda c:c*64
NOW=datetime(2026,9,12,10,0,30,tzinfo=timezone.utc)
OBS='2026-09-12T10:00:00+00:00';EXP='2026-09-12T10:01:00+00:00'

def candidate(att='4'):
    return AppSessionAttestationCandidate('session-1','app-1',D('1'),'provider-1','provider-instance-1',D('2'),D('3'),D(att),D('5'),OBS,EXP)

def trusted_time():return TrustedTimeCandidate('time-1','time-i',D('6'),D('7'),OBS,EXP,25)

class Provider:
    def __init__(self,sequence=1,durable='8'):self.sequence=sequence;self.durable=D(durable)
    def verify_external(self,c):
        return ExternalAppSessionEvidence(c.digest(),c.session_id,c.app_instance_id,c.subject_digest,c.provider_id,c.provider_instance_id,c.provider_implementation_digest,c.trust_anchor_digest,c.attestation_digest,c.evidence_digest,'issuer-1','provider:fixture',self.sequence,self.durable)

def verify(store,*,sequence=1,c=None):
    v=AppSessionAttestationVerifier(external_verifier=Provider(sequence),atomic_guard=store)
    return v.verify(c or candidate(),trusted_time=trusted_time(),trusted_now=NOW,expected_session_id='session-1',expected_app_instance_id='app-1',expected_subject_digest=D('1'),expected_trust_anchor_digest=D('3'),expected_issuer_id='issuer-1')

class DurableAppSessionTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.path=Path(self.t.name)/'durable.sqlite';self.store=DurableAppSessionStateStore.create(self.path)

    def test_atomic_consumption_promotes_only_durable_candidate_state(self):
        x=verify(self.store);self.assertEqual(x.durable_sequence_state,'DURABLE_ATOMIC_CANDIDATE_CONSUMED');self.assertEqual(x.replay_state,'DURABLE_REPLAY_CANDIDATE_CONSUMED');self.assertEqual(x.replay_result_atomicity,'DURABLE_ATOMIC_CANDIDATE_NOT_RUNTIME_ADMISSION');self.assertEqual(len(x.durable_consumption_receipt_digest),64);self.assertFalse(x.runtime_ready);self.assertEqual((x.authority_effect,x.runtime_effect),('NONE','NONE'))

    def test_exact_replay_rejected_after_store_reopen(self):
        verify(self.store);reopened=DurableAppSessionStateStore(self.path)
        with self.assertRaisesRegex(AppSessionAttestationVerificationError,'durable atomic guard'):
            verify(reopened)
        self.assertEqual(reopened.current_sequence('provider-1','session-1')[0],1)

    def test_sequence_rollback_rejected_across_distinct_attestation_after_restart(self):
        verify(self.store,sequence=2,c=candidate('4'));reopened=DurableAppSessionStateStore(self.path)
        with self.assertRaisesRegex(AppSessionAttestationVerificationError,'durable atomic guard'):
            verify(reopened,sequence=1,c=candidate('9'))
        self.assertEqual(reopened.current_sequence('provider-1','session-1')[0],2)

    def test_higher_sequence_commits_after_restart(self):
        verify(self.store,sequence=1,c=candidate('4'));reopened=DurableAppSessionStateStore(self.path);x=verify(reopened,sequence=2,c=candidate('9'));self.assertEqual(reopened.current_sequence('provider-1','session-1')[0],2);self.assertEqual(x.durable_sequence_state,'DURABLE_ATOMIC_CANDIDATE_CONSUMED')

    def test_failed_replay_does_not_advance_sequence(self):
        verify(self.store,sequence=1);
        with self.assertRaises(AppSessionAttestationVerificationError):verify(self.store,sequence=1)
        self.assertEqual(self.store.current_sequence('provider-1','session-1')[0],1)

    def test_store_identity_drift_fails_closed(self):
        self.store.current_sequence('provider-1','session-1')
        with sqlite3.connect(self.path) as db:db.execute("UPDATE metadata SET store_id='other'")
        with self.assertRaisesRegex(AppSessionDurableStateError,'identity drift'):self.store.current_sequence('provider-1','session-1')

    def test_existing_path_cannot_be_reinitialized(self):
        with self.assertRaises(FileExistsError):DurableAppSessionStateStore.create(self.path)

    def test_atomic_and_split_guards_cannot_be_mixed(self):
        with self.assertRaisesRegex(AppSessionAttestationVerificationError,'cannot be mixed'):
            AppSessionAttestationVerifier(external_verifier=Provider(),atomic_guard=self.store,replay_guard=InMemoryAppSessionReplayGuard(),sequence_guard=InMemoryAppSessionSequenceGuard())

    def test_missing_all_consumption_guards_fails_closed(self):
        with self.assertRaisesRegex(AppSessionAttestationVerificationError,'guards required'):
            AppSessionAttestationVerifier(external_verifier=Provider())

    def test_store_has_no_private_key_or_activation_primitive(self):
        text=Path('cyber_lion/app_coordination/e02_app_session_durable.py').read_text();self.assertNotIn('private_key',text);self.assertNotIn('activate_runtime',text);self.assertNotIn('subprocess',text);self.assertNotIn('urllib',text)

if __name__=='__main__':unittest.main()

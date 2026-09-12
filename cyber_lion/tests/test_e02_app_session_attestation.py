from dataclasses import replace
from datetime import datetime, timezone
import unittest

from cyber_lion.app_coordination.e02_app_session_attestation import (
    AppSessionAttestationVerifier, AppSessionAttestationVerificationError,
    ExternalAppSessionEvidence, InMemoryAppSessionReplayGuard, InMemoryAppSessionSequenceGuard,
)
from cyber_lion.app_coordination.e02_trust_primitives import AppSessionAttestationCandidate, TrustedTimeCandidate

D=lambda c:c*64
NOW=datetime(2026,9,12,10,0,30,tzinfo=timezone.utc)
OBS='2026-09-12T10:00:00+00:00'; EXP='2026-09-12T10:01:00+00:00'

def candidate():
    return AppSessionAttestationCandidate('session-1','app-1',D('1'),'provider-1','provider-instance-1',D('2'),D('3'),D('4'),D('5'),OBS,EXP)

def time(): return TrustedTimeCandidate('time-1','time-i',D('6'),D('7'),OBS,EXP,25)

class Provider:
    def __init__(self, transform=lambda x:x): self.transform=transform
    def verify_external(self,c):
        e=ExternalAppSessionEvidence(c.digest(),c.session_id,c.app_instance_id,c.subject_digest,c.provider_id,c.provider_instance_id,
            c.provider_implementation_digest,c.trust_anchor_digest,c.attestation_digest,c.evidence_digest,'issuer-1','provider:fixture',1,D('8'))
        return self.transform(e)

def verifier(provider=None,replay=None,sequence=None):
    return AppSessionAttestationVerifier(external_verifier=provider or Provider(),replay_guard=replay or InMemoryAppSessionReplayGuard(),sequence_guard=sequence or InMemoryAppSessionSequenceGuard())

def verify(v,c=None,now=NOW):
    return v.verify(c or candidate(),trusted_time=time(),trusted_now=now,expected_session_id='session-1',expected_app_instance_id='app-1',
        expected_subject_digest=D('1'),expected_trust_anchor_digest=D('3'),expected_issuer_id='issuer-1')

class AppSessionExternalAttesterTests(unittest.TestCase):
    def test_verified_candidate_is_effect_free_and_still_not_runtime_ready(self):
        x=verify(verifier()); self.assertEqual(x.attestation_state,'EXTERNAL_ATTESTATION_VERIFIED_CANDIDATE'); self.assertFalse(x.runtime_ready); self.assertEqual((x.authority_effect,x.runtime_effect),('NONE','NONE')); self.assertEqual(x.durable_sequence_state,'EXTERNAL_DURABLE_PROVIDER_REQUIRED')
    def test_session_app_subject_substitution_denied(self):
        v=verifier()
        for kwargs in ({'expected_session_id':'other'},{'expected_app_instance_id':'other'},{'expected_subject_digest':D('f')}):
            base=dict(trusted_time=time(),trusted_now=NOW,expected_session_id='session-1',expected_app_instance_id='app-1',expected_subject_digest=D('1'),expected_trust_anchor_digest=D('3'),expected_issuer_id='issuer-1');base.update(kwargs)
            with self.assertRaises(AppSessionAttestationVerificationError): v.verify(candidate(),**base)
    def test_trust_anchor_substitution_denied(self):
        with self.assertRaisesRegex(AppSessionAttestationVerificationError,'trust-anchor'):
            verifier().verify(candidate(),trusted_time=time(),trusted_now=NOW,expected_session_id='session-1',expected_app_instance_id='app-1',expected_subject_digest=D('1'),expected_trust_anchor_digest=D('f'),expected_issuer_id='issuer-1')
    def test_provider_and_issuer_substitution_denied(self):
        transforms=(lambda e:replace(e,provider_id='other'),lambda e:replace(e,provider_instance_id='other'),lambda e:replace(e,provider_implementation_digest=D('f')),lambda e:replace(e,issuer_id='other'))
        for transform in transforms:
            with self.assertRaisesRegex(AppSessionAttestationVerificationError,'provenance binding'):
                verify(verifier(Provider(transform)))
    def test_external_verifier_failure_and_wrong_type_fail_closed(self):
        class Fail:
            def verify_external(self,c): raise RuntimeError('no')
        class Wrong:
            def verify_external(self,c): return object()
        for p in (Fail(),Wrong()):
            with self.assertRaises(AppSessionAttestationVerificationError): verify(verifier(p))
    def test_stale_and_future_time_fail_closed(self):
        for now in (datetime(2026,9,12,9,59,59,tzinfo=timezone.utc),datetime(2026,9,12,10,2,0,tzinfo=timezone.utc)):
            with self.assertRaises(AppSessionAttestationVerificationError): verify(verifier(),now=now)
    def test_exact_replay_is_rejected(self):
        r=InMemoryAppSessionReplayGuard();s=InMemoryAppSessionSequenceGuard();v=verifier(replay=r,sequence=s);verify(v)
        with self.assertRaises(AppSessionAttestationVerificationError): verify(v)
    def test_sequence_rollback_is_rejected_across_distinct_attestation(self):
        seq=InMemoryAppSessionSequenceGuard(); verify(verifier(sequence=seq))
        c=replace(candidate(),attestation_digest=D('9'),evidence_digest=D('a'))
        p=Provider(lambda e: replace(e,candidate_digest=c.digest(),attestation_digest=c.attestation_digest,evidence_digest=c.evidence_digest,sequence=1))
        with self.assertRaisesRegex(AppSessionAttestationVerificationError,'sequence rollback'):
            verify(verifier(p,sequence=seq),c=c)
    def test_sequence_guard_exception_fails_closed(self):
        class Broken:
            def consume(self,*a): raise RuntimeError('broken')
        with self.assertRaisesRegex(AppSessionAttestationVerificationError,'sequence guard'):
            verify(verifier(sequence=Broken()))
    def test_replay_guard_exception_fails_closed(self):
        class Broken:
            def consume(self,*a): raise RuntimeError('broken')
        with self.assertRaisesRegex(AppSessionAttestationVerificationError,'replay guard'):
            verify(verifier(replay=Broken()))
    def test_external_durable_sequence_digest_is_required(self):
        with self.assertRaises(AppSessionAttestationVerificationError): verify(verifier(Provider(lambda e:replace(e,durable_sequence_digest='bad'))))
    def test_no_private_key_or_activation_primitives_in_source(self):
        from pathlib import Path
        text=Path('cyber_lion/app_coordination/e02_app_session_attestation.py').read_text()
        self.assertNotIn('private_key',text); self.assertNotIn('activate_runtime(',text); self.assertNotIn('subprocess',text); self.assertNotIn('urllib',text)

if __name__=='__main__':unittest.main()

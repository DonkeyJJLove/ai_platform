from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json, unittest

from cyber_lion.app_coordination.e02_trust_primitives import (
    ProducerProvenanceCandidate, CollectorProvenanceCandidate, TrustedTimeCandidate,
    DurableSequenceCandidate, AppSessionAttestationCandidate, compose_local_runtime_trust, compose_app_session_trust, activate_runtime)
from cyber_lion.app_coordination.producer_records import VerifiedRecordCandidate
from cyber_lion.app_coordination.source_candidates import SourceRejected, SourceUnavailable, canonical

D=lambda c: c*64
NOW=datetime(2026,9,12,10,0,30,tzinfo=timezone.utc)
OBS="2026-09-12T10:00:00+00:00"; EXP="2026-09-12T10:01:00+00:00"

def subject():
    return dict(mission_id="m",task_id="t",runtime_instance_id="r",task_class="DOCUMENT_SUMMARY",checkpoint_revision=1,
                source_head="a"*40,session_record_digest=D("1"),qualification_digest=D("2"),task_digest=D("3"),provisioned_executor_digest=D("4"))

def record(sequence=7,boot="boot-1"):
    value=dict(schema="lion.e02.producer-record/v1",domain="LION/E02/SOURCE-RECORD/1",kind="LOCAL_RUNTIME_OBSERVATION",
        producer_id="producer-1",instance_id="producer-instance-1",implementation_digest=D("5"),boot_id=boot,sequence=sequence,
        policy_revision=D("6"),subject=subject(),observed_at=OBS,issued_at=OBS,expires_at=EXP,payload={"kind":"fixture"})
    body=canonical(value); return VerifiedRecordCandidate("LOCAL_RUNTIME_OBSERVATION",sha256(body.encode()).hexdigest(),body,3)

def evidence():
    p=ProducerProvenanceCandidate("producer-1","producer-instance-1",D("5"),D("6"),"boot-1","collector-1","collector-instance-1",D("7"),OBS,EXP)
    c=CollectorProvenanceCandidate("collector-1","collector-instance-1","host-1","boot-1",D("8"),D("9"),D("a"),OBS,EXP)
    t=TrustedTimeCandidate("time-1","time-instance-1",D("b"),D("c"),OBS,EXP,25)
    s=DurableSequenceCandidate("producer-1","store-1","boot-1",6,7,D("d"),D("e"))
    return p,c,t,s

class E02TrustPrimitiveTests(unittest.TestCase):
    def test_valid_bundle_is_partial_and_effect_free(self):
        p,c,t,s=evidence(); x=compose_local_runtime_trust(verified_record=record(),producer=p,collector=c,trusted_time=t,durable_sequence=s,trusted_now=NOW)
        self.assertEqual(x.local_runtime_attestation,"PARTIAL_CANDIDATE"); self.assertEqual(x.app_session_attestation,"NOT_IMPLEMENTED")
        self.assertEqual(x.canonical_runtime_source,"NOT_ACTIVATABLE"); self.assertFalse(x.runtime_ready); self.assertEqual(x.authority_effect,"NONE")
    def test_deterministic_binding(self):
        p,c,t,s=evidence(); a=compose_local_runtime_trust(verified_record=record(),producer=p,collector=c,trusted_time=t,durable_sequence=s,trusted_now=NOW)
        b=compose_local_runtime_trust(verified_record=record(),producer=p,collector=c,trusted_time=t,durable_sequence=s,trusted_now=NOW)
        self.assertEqual(a,b); self.assertEqual(len(a.binding_digest),64)
    def test_forged_record_digest_denied(self):
        p,c,t,s=evidence()
        with self.assertRaisesRegex(SourceRejected,"verified record digest mismatch"):
            compose_local_runtime_trust(verified_record=replace(record(),record_digest=D("f")),producer=p,collector=c,trusted_time=t,durable_sequence=s,trusted_now=NOW)
    def test_producer_substitution_denied(self):
        p,c,t,s=evidence()
        with self.assertRaisesRegex(SourceRejected,"producer provenance substitution"):
            compose_local_runtime_trust(verified_record=record(),producer=replace(p,instance_id="other"),collector=c,trusted_time=t,durable_sequence=s,trusted_now=NOW)
    def test_collector_substitution_denied(self):
        p,c,t,s=evidence()
        with self.assertRaisesRegex(SourceRejected,"collector provenance substitution"):
            compose_local_runtime_trust(verified_record=record(),producer=p,collector=replace(c,instance_id="other"),trusted_time=t,durable_sequence=s,trusted_now=NOW)
    def test_sequence_rollback_and_substitution_denied(self):
        p,c,t,s=evidence()
        for bad in (replace(s,sequence=6),replace(s,producer_id="other"),replace(s,boot_id="other")):
            with self.assertRaises(SourceRejected): compose_local_runtime_trust(verified_record=record(),producer=p,collector=c,trusted_time=t,durable_sequence=bad,trusted_now=NOW)
    def test_stale_time_denied(self):
        p,c,t,s=evidence(); late=datetime(2026,9,12,10,2,0,tzinfo=timezone.utc)
        with self.assertRaisesRegex(SourceRejected,"not current"):
            compose_local_runtime_trust(verified_record=record(),producer=p,collector=c,trusted_time=t,durable_sequence=s,trusted_now=late)
    def test_unbounded_time_uncertainty_denied(self):
        p,c,t,s=evidence()
        with self.assertRaisesRegex(SourceRejected,"bounded time uncertainty"):
            compose_local_runtime_trust(verified_record=record(),producer=p,collector=c,trusted_time=replace(t,uncertainty_ms=1001),durable_sequence=s,trusted_now=NOW)
    def app_attestation(self):
        return AppSessionAttestationCandidate("session-1","app-instance-1",D("1"),"app-attester","attester-instance",D("2"),D("3"),D("4"),D("5"),OBS,EXP)
    def test_app_session_candidate_is_partial_and_effect_free(self):
        _,_,tm,_=evidence(); a=self.app_attestation()
        x=compose_app_session_trust(attestation=a,trusted_time=tm,trusted_now=NOW,expected_session_id="session-1",expected_app_instance_id="app-instance-1",expected_subject_digest=D("1"))
        self.assertEqual(x.app_session_attestation,"PARTIAL_CANDIDATE_EXTERNAL_ATTESTER_REQUIRED")
        self.assertEqual(x.canonical_runtime_source,"NOT_ACTIVATABLE"); self.assertFalse(x.runtime_ready)
        self.assertEqual((x.authority_effect,x.runtime_effect),("NONE","NONE"))
    def test_app_session_substitution_and_staleness_fail_closed(self):
        _,_,tm,_=evidence(); a=self.app_attestation()
        with self.assertRaisesRegex(SourceRejected,"substitution"):
            compose_app_session_trust(attestation=a,trusted_time=tm,trusted_now=NOW,expected_session_id="other",expected_app_instance_id="app-instance-1",expected_subject_digest=D("1"))
        with self.assertRaisesRegex(SourceRejected,"not current"):
            compose_app_session_trust(attestation=a,trusted_time=tm,trusted_now=datetime(2026,9,12,10,2,0,tzinfo=timezone.utc),expected_session_id="session-1",expected_app_instance_id="app-instance-1",expected_subject_digest=D("1"))
    def test_app_session_wrong_access_or_trust_promotion_denied(self):
        _,_,tm,_=evidence(); a=self.app_attestation()
        for bad in (replace(a,access_class="LOCAL_PROCESS"),replace(a,trust_state="ATTESTED"),replace(a,authority_effect="ALLOW")):
            with self.assertRaises(SourceRejected):
                compose_app_session_trust(attestation=bad,trusted_time=tm,trusted_now=NOW,expected_session_id="session-1",expected_app_instance_id="app-instance-1",expected_subject_digest=D("1"))
    def test_runtime_activation_remains_unavailable(self):
        with self.assertRaises(SourceUnavailable): activate_runtime()
    def test_input_types_are_exact(self):
        p,c,t,s=evidence()
        with self.assertRaises(SourceRejected): compose_local_runtime_trust(verified_record=object(),producer=p,collector=c,trusted_time=t,durable_sequence=s,trusted_now=NOW)

if __name__=='__main__': unittest.main()

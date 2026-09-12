"""Offline conformance; injected test verifier is not cryptographic evidence."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from cyber_lion.app_coordination.producer_records import (
    DOMAIN, ProducerPolicy, KeyStatus, RecordVerifier, application_observation,
    local_runtime_observation, qualification_result)
from cyber_lion.app_coordination.result_recorder import CandidateResultStore, ResultConflict
from cyber_lion.app_coordination.source_candidates import SourceRejected, SourceUnavailable, canonical
from cyber_lion.enterprise.trusted_control_plane_providers import TrustedSignatureVerifierAdapter
from cyber_lion.tests.test_e02_source_candidates import SourceTests, decode_index


class ProducerTests(unittest.TestCase):
    def setUp(self):
        self.f=SourceTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.now=self.f.now
        self.policy=ProducerPolicy("test-producer","test-instance","1"*64,"test-boot",
            "TEST_ONLY_KEY","TEST_ONLY_ALGORITHM","2"*64,
            ("APP_TASK_OBSERVATION","LOCAL_RUNTIME_OBSERVATION","QUALIFICATION_RESULT"))
        self.status=KeyStatus("2"*64,"TEST_ONLY_KEY","ACTIVE",1,
            (self.now-timedelta(seconds=5)).isoformat(),(self.now+timedelta(seconds=60)).isoformat())
        self.observation=application_observation(thread_id="test-thread",turn_id="test-turn",
            host_id="local",state="active",observed_at=self.now.isoformat())
        self.record=dict(schema="lion.e02.producer-record/v1",domain=DOMAIN,
            kind=self.observation.kind,producer_id="test-producer",instance_id="test-instance",
            implementation_digest="1"*64,boot_id="test-boot",sequence=5,policy_revision="2"*64,
            subject=self.f.subject,observed_at=self.now.isoformat(),issued_at=self.now.isoformat(),
            expires_at=(self.now+timedelta(seconds=60)).isoformat(),
            payload=json.loads(self.observation.payload_json))
        self.envelope=dict(record=self.record,signature="TEST_ONLY_SIGNATURE",
            key_id="TEST_ONLY_KEY",algorithm="TEST_ONLY_ALGORITHM")
        self.expected_bytes=canonical(self.record).encode()
        self.calls=[]
        def check(payload,signature,key_id,algorithm):
            self.calls.append((payload,signature,key_id,algorithm))
            return payload==self.expected_bytes and signature=="TEST_ONLY_SIGNATURE"
        self.backend=TrustedSignatureVerifierAdapter(check)
        self.verifier=RecordVerifier(policy=self.policy,signature_verifier=self.backend,
            key_status_source=lambda _:self.status)

    def verify(self, **kwargs):
        return self.verifier.verify(canonical(self.envelope).encode(),
            expected_kind=kwargs.get("kind","APP_TASK_OBSERVATION"),
            expected_subject=kwargs.get("subject",self.f.subject),
            trusted_now=kwargs.get("now",self.now),
            minimum_sequence=kwargs.get("minimum",5))

    def test_backend_delegation_preserves_observation_domain(self):
        result=self.verify()
        self.assertEqual(result.kind,"APP_TASK_OBSERVATION")
        self.assertFalse(result.runtime_ready)
        self.assertEqual(self.calls[0][0],self.expected_bytes)
        self.assertEqual(self.observation.provenance,"CALLER_SUPPLIED_OBSERVATION_NOT_ATTESTATION")

    def test_application_observation_never_becomes_session_attestation(self):
        with self.assertRaises(SourceRejected):self.verify(kind="APP_SESSION_ATTESTATION")
        with self.assertRaises(SourceRejected):
            replace(self.policy,allowed_kinds=("APP_SESSION_ATTESTATION",)).validate()

    def test_no_runtime_activation(self):
        with self.assertRaises(SourceUnavailable):self.verifier.resolve("a"*64)

    def test_local_identity_changes_on_restart_and_model_change(self):
        args=dict(host_id="MOON",boot_id="test-boot",pid=123,
            started_at=(self.now-timedelta(seconds=10)).isoformat(),
            image_digest="3"*64,model_digest="4"*64,configuration_digest="5"*64,
            observed_at=self.now.isoformat())
        first=local_runtime_observation(**args)
        for key,value in (("boot_id","other"),("model_digest","6"*64),
                          ("started_at",(self.now-timedelta(seconds=5)).isoformat())):
            self.assertNotEqual(first,local_runtime_observation(**{**args,key:value}))

    def test_qualification_requires_complete_frozen_outcomes(self):
        args=dict(task_class="DOCUMENT_SUMMARY",runtime_digest="3"*64,suite_digest="4"*64,
                  policy_digest="5"*64,report_digest="6"*64,required_cases=("a","b"))
        for values,expected in (({"a":"PASS","b":"FAIL"},"FAIL"),
                                 ({"a":"PASS","b":"UNKNOWN"},"UNKNOWN"),
                                 ({"a":"PASS","b":"PASS"},"PASS")):
            result=qualification_result(**args,measured_results=values)
            self.assertEqual(json.loads(result.payload_json)["outcome"],expected)
        with self.assertRaises(SourceRejected):
            qualification_result(**args,measured_results={"a":"PASS"})

    def test_wrong_key_algorithm_or_producer(self):
        for field,value in (("key_id","other"),("algorithm","other")):
            original=self.envelope[field];self.envelope[field]=value
            with self.assertRaises(SourceRejected):self.verify()
            self.envelope[field]=original
        self.record["producer_id"]="other"
        with self.assertRaises(SourceRejected):self.verify()

    def test_cross_domain_payload_tamper_and_signature_failure(self):
        self.record["domain"]="OTHER"
        with self.assertRaises(SourceRejected):self.verify()
        self.record["domain"]=DOMAIN
        self.record["payload"]["state"]="changed"
        with self.assertRaises(SourceRejected):self.verify()
        self.record["payload"]["state"]="active"
        self.envelope["signature"]="BAD"
        with self.assertRaises(SourceRejected):self.verify()

    def test_verifier_exception_nonbool_and_not_ready(self):
        def raises(*_):raise RuntimeError("test failure")
        for backend in (TrustedSignatureVerifierAdapter(raises),
                        TrustedSignatureVerifierAdapter(lambda *_:"true"),
                        TrustedSignatureVerifierAdapter(lambda *_:True,ready=lambda:False)):
            self.verifier=RecordVerifier(policy=self.policy,signature_verifier=backend,
                key_status_source=lambda _:self.status)
            with self.assertRaises(SourceRejected):self.verify()

    def test_revoked_missing_and_stale_status(self):
        original=self.status
        for status in (replace(original,state="REVOKED"),None,
                       replace(original,expires_at=self.now.isoformat())):
            self.status=status
            with self.assertRaises(SourceRejected):self.verify()

    def test_revocation_during_signature_verification(self):
        def check(*_):
            self.status=replace(self.status,state="REVOKED",version=2)
            return True
        self.verifier=RecordVerifier(policy=self.policy,signature_verifier=TrustedSignatureVerifierAdapter(check),
            key_status_source=lambda _:self.status)
        with self.assertRaises(SourceRejected):self.verify()

    def test_wrong_subject_sequence_boot_and_expiry(self):
        with self.assertRaises(SourceRejected):self.verify(subject={**self.f.subject,"task_class":"OTHER"})
        with self.assertRaises(SourceRejected):self.verify(minimum=6)
        with self.assertRaises(SourceRejected):self.verify(now=self.now-timedelta(seconds=1))
        self.record["boot_id"]="other"
        with self.assertRaises(SourceRejected):self.verify()
        self.record["boot_id"]="test-boot"
        self.record["expires_at"]=self.now.isoformat()
        with self.assertRaises(SourceRejected):self.verify()

    def test_backend_configuration_change_during_verification(self):
        def check(*_):
            self.verifier.policy=replace(self.policy,instance_id="changed")
            return True
        self.verifier=RecordVerifier(policy=self.policy,
            signature_verifier=TrustedSignatureVerifierAdapter(check),
            key_status_source=lambda _:self.status)
        with self.assertRaises(SourceRejected):self.verify()


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.f=SourceTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.path=self.f.root/"candidate.sqlite"
        self.store=CandidateResultStore.create(self.path)
        self.request="a"*64
        self.store.reserve(self.request,self.f.binding.task_digest)

    def test_reservation_is_unknown_and_cannot_authorize_retry(self):
        result=self.store.inspect(self.request)
        self.assertEqual(result.state,"UNKNOWN_REQUIRES_RECONCILIATION")
        self.assertFalse(result.retry_allowed)
        self.assertFalse(result.runtime_ready)
        self.assertEqual(result,CandidateResultStore(self.path).inspect(self.request))

    def test_record_reopen_and_idempotent_duplicate(self):
        result=self.store.record_candidate(self.request,self.f.bound)
        self.assertEqual(result.state,"CANDIDATE_RECORDED")
        self.assertEqual(result,self.store.record_candidate(self.request,self.f.bound))
        self.assertEqual(result,CandidateResultStore(self.path).inspect(self.request))
        self.assertFalse(result.runtime_ready)

    def test_conflict_never_overwrites(self):
        first=self.store.record_candidate(self.request,self.f.bound)
        other=replace(self.f.receipt,request_id="other",admission_digest="").sealed()
        with self.assertRaises(ResultConflict):
            self.store.record_candidate(self.request,replace(self.f.bound,runtime_admission=other))
        self.assertEqual(first,self.store.inspect(self.request))

    def test_reservation_and_exact_task_required(self):
        with self.assertRaises(SourceRejected):self.store.record_candidate("b"*64,self.f.bound)
        with self.assertRaises(ResultConflict):self.store.reserve(self.request,"f"*64)
        with self.assertRaises(SourceRejected):
            self.store.record_candidate(self.request,replace(self.f.bound,
                task_binding=replace(self.f.binding,task_digest="f"*64)))

    def test_one_receipt_cannot_be_reassigned_to_another_request(self):
        self.store.record_candidate(self.request,self.f.bound)
        self.store.reserve("b"*64,self.f.binding.task_digest)
        with self.assertRaises(ResultConflict):self.store.record_candidate("b"*64,self.f.bound)
        self.assertEqual(self.store.inspect("b"*64).state,"UNKNOWN_REQUIRES_RECONCILIATION")

    def test_untrusted_runtime_source_and_canonical_ingress_refused(self):
        with self.assertRaises(SourceUnavailable):self.store.resolve(self.request)
        with self.assertRaises(SourceUnavailable):self.store.record_canonical(self.request,self.f.bound)
        with self.assertRaises(SourceRejected):self.store.record_candidate(self.request,{"status":"PASS"})

    def test_concurrent_identical_results_are_idempotent(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:CandidateResultStore(self.path).record_candidate(self.request,self.f.bound),range(8)))
        self.assertTrue(all(x==results[0] for x in results))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM receipts").fetchone()[0],1)

    def test_changed_store_identity_rejected(self):
        with sqlite3.connect(self.path) as db:db.execute("UPDATE metadata SET store_id='other'")
        with self.assertRaises(SourceRejected):self.store.inspect(self.request)

    def test_production_and_unknown_database_rejected(self):
        with self.assertRaises(FileExistsError):CandidateResultStore.create(self.path)
        with sqlite3.connect(self.path) as db:db.execute("UPDATE metadata SET mode='PRODUCTION'")
        with self.assertRaises(SourceRejected):CandidateResultStore(self.path)
        other=self.f.root/"unknown.sqlite"
        with sqlite3.connect(other) as db:db.execute("CREATE TABLE unrelated (x INTEGER)")
        with self.assertRaises(SourceRejected):CandidateResultStore(other)

    def test_corrupt_result_detected(self):
        self.store.record_candidate(self.request,self.f.bound)
        with sqlite3.connect(self.path) as db:db.execute("UPDATE receipts SET payload='{}'")
        with self.assertRaises(SourceRejected):self.store.inspect(self.request)

    def child(self, mode):
        payload=self.f.root/"bound.json";payload.write_text(canonical(asdict(self.f.bound)))
        marker=self.f.root/"ready"
        code = """
import sys,os,time
from pathlib import Path
from contextlib import contextmanager
from cyber_lion.app_coordination.result_recorder import CandidateResultStore
from cyber_lion.tests.test_e02_source_candidates import decode_index
from cyber_lion.app_coordination.source_candidates import decode
class PausedStore(CandidateResultStore):
    @contextmanager
    def _open(self):
        with super()._open() as db:
            def trace(sql):
                if sql.startswith('INSERT INTO request_index'):
                    Path(sys.argv[3]).write_text('receipt-inserted-index-not-committed')
                    while True: time.sleep(0.02)
            if sys.argv[4]=='before-index': db.set_trace_callback(trace)
            yield db
store=PausedStore(sys.argv[1])
bound=decode_index(decode(Path(sys.argv[2]).read_bytes()))
store.record_candidate('a'*64,bound)
os._exit(0)
"""
        child=subprocess.Popen([sys.executable,"-B","-c",code,str(self.path),str(payload),str(marker),mode],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        return child,marker

    def test_process_kill_between_receipt_and_index_rolls_back_both(self):
        child,marker=self.child("before-index")
        try:
            deadline=time.monotonic()+10
            while not marker.exists() and child.poll() is None and time.monotonic()<deadline:
                time.sleep(0.02)
            self.assertTrue(marker.exists(), "child did not reach transaction boundary")
            child.kill();child.wait(timeout=5)
        finally:
            if child.poll() is None:child.kill()
            child.communicate(timeout=5)
        result=CandidateResultStore(self.path).inspect(self.request)
        self.assertEqual(result.state,"UNKNOWN_REQUIRES_RECONCILIATION")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM receipts").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT count(*) FROM request_index").fetchone()[0],0)

    def test_abrupt_exit_after_commit_preserves_result(self):
        child,_=self.child("after-commit")
        stdout,stderr=child.communicate(timeout=10)
        self.assertEqual(child.returncode,0,stderr.decode(errors="replace"))
        result=CandidateResultStore(self.path).inspect(self.request)
        self.assertEqual(result.state,"CANDIDATE_RECORDED")
        self.assertFalse(result.retry_allowed)

    def test_replay_consumed_without_receipt_stays_unknown_after_restart(self):
        # No actual admission/replay is invoked. This is the persisted state of
        # a reservation whose engine outcome could not be durably recorded.
        state=CandidateResultStore(self.path).inspect(self.request)
        self.assertEqual(state.state,"UNKNOWN_REQUIRES_RECONCILIATION")
        self.assertEqual(state,self.store.reserve(self.request,self.f.binding.task_digest))
        self.assertFalse(state.retry_allowed)


if __name__=="__main__":
    unittest.main()

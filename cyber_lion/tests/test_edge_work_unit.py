from pathlib import Path
import tempfile,unittest,subprocess
from unittest.mock import patch
from cyber_lion.mission_control.edge_support import EdgeRejected,digest,object_bytes
from cyber_lion.mission_control.edge_worker import execute,run_case,SCENARIOS,fixture_corpus,validate_corpus,normalize_model_corpus,infer
from cyber_lion.mission_control.artifact_transfer import verify_bundle,create_bundle,materialize_bundle,verify_workspace,ArtifactTransferError
from cyber_lion.enterprise.edge_yoke.pilot import initial,make_job
from cyber_lion.enterprise.edge_yoke.executor import run_registered

class WorkTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name).resolve()
        self.raw,self.binding=initial('QUAL-TEST');self.job=make_job('QUAL-TEST','BUILD_INTEGRITY_TOOL','BUILD',self.raw,self.binding,'HOST')
    def build(self):return execute(self.job,self.raw,host_id='HOST',worker_id='BUILD')
    def test_actual_bytes_produced(self):
        b=self.build();_,fs=verify_bundle(b,digest(b),self.job['output_binding']);self.assertIn('product_verifier.py',fs)
    def test_two_worker_product(self):
        b=self.build();j=make_job('QUAL-TEST','VERIFY_INTEGRITY_TOOL','VERIFY',b,self.job['output_binding'],'HOST')
        out=execute(j,b,host_id='HOST',worker_id='VERIFY');_,fs=verify_bundle(out,digest(out),j['output_binding'])
        r=object_bytes(fs['verification.json']);self.assertEqual(r['status'],'PASS');self.assertEqual(len(r['cases']),8)
    def test_wrong_worker(self):
        with self.assertRaises(EdgeRejected):execute(self.job,self.raw,host_id='HOST',worker_id='OTHER')
    def test_expired_lease(self):
        self.job['expires_at']=0
        with self.assertRaises(EdgeRejected):self.build()
    def test_arbitrary_command_rejected(self):
        self.job['command']='whoami'
        with self.assertRaises(EdgeRejected):self.build()
    def test_unknown_operation(self):
        self.job['operation']='SHELL'
        with self.assertRaises(EdgeRejected):self.build()
    def test_cannot_claim_live_mission(self):
        self.job['scope']='PRODUCTION'
        with self.assertRaises(EdgeRejected):self.build()
    def test_source_drift(self):
        self.job['executor_source_digest']='0'*64
        with self.assertRaises(EdgeRejected):self.build()
    def test_input_tampering(self):
        with self.assertRaises(ArtifactTransferError):execute(self.job,self.raw+b' ',host_id='HOST',worker_id='BUILD')
    def test_mission_substitution(self):
        self.job['output_binding']['mission_id']='OTHER'
        with self.assertRaises(EdgeRejected):self.build()
    def test_message_substitution(self):
        self.job['coordinates']['message_id']='OTHER'
        with self.assertRaises(EdgeRejected):self.build()
    def test_causation_substitution(self):
        self.job['coordinates']['causation_id']='OTHER'
        with self.assertRaises(EdgeRejected):self.build()
    def test_context_substitution(self):
        self.job['coordinates']['context_bytes_sha256']='0'*64
        with self.assertRaises(EdgeRejected):self.build()
    def test_same_worker_not_verifier(self):
        b=self.build();j=make_job('QUAL-TEST','VERIFY_INTEGRITY_TOOL','BUILD',b,self.job['output_binding'],'HOST')
        with self.assertRaises(EdgeRejected):execute(j,b,host_id='HOST',worker_id='BUILD')
    def test_model_executable_never_run(self):
        b=self.build();_,fs=verify_bundle(b,digest(b),self.job['output_binding']);fs['product_verifier.py']=b'print("unsafe")'
        raw=create_bundle(fs,self.job['output_binding']);j=make_job('QUAL-TEST','VERIFY_INTEGRITY_TOOL','VERIFY',raw,self.job['output_binding'],'HOST')
        with self.assertRaises(EdgeRejected):execute(j,raw,host_id='HOST',worker_id='VERIFY')
    def test_materialized_tamper_rejected(self):
        b=self.build();ob=self.job['output_binding'];r=materialize_bundle(b,digest(b),ob,self.root)
        (Path(r['workspace'])/'cases.json').write_text('{}')
        with self.assertRaises(ArtifactTransferError):verify_workspace(r['workspace'],b,digest(b),ob)
    def test_corpus_wrong_expectation(self):
        c=fixture_corpus();c['cases'][0]['expected_valid']=False
        with self.assertRaises(EdgeRejected):validate_corpus(c)
    def test_corpus_missing_case(self):
        c=fixture_corpus();c['cases'].pop()
        with self.assertRaises(EdgeRejected):validate_corpus(c)
    def test_model_duplicate_ids_are_normalized(self):
        c=fixture_corpus()
        for row in c['cases']:row['id']='same'
        normalized=normalize_model_corpus(c)
        validate_corpus(normalized)
        self.assertEqual(len({row['id'] for row in normalized['cases']}),8)
        self.assertEqual([row['scenario'] for row in normalized['cases']],list(SCENARIOS))
    def test_model_unique_ids_are_preserved(self):
        c=fixture_corpus();normalized=normalize_model_corpus(c)
        self.assertEqual(normalized,c)
    def test_model_duplicate_scenario_is_rejected(self):
        c=fixture_corpus();c['cases'][1]['scenario']=c['cases'][0]['scenario']
        with self.assertRaisesRegex(EdgeRejected,'scenario identity'):normalize_model_corpus(c)
    def test_model_endpoint_not_model_selected(self):
        with self.assertRaises(EdgeRejected):infer('http://example.com:8772')
    def test_negative_scenarios(self):
        for n in SCENARIOS:
            with self.subTest(n=n):self.assertEqual(run_case(n),n=='valid')
    def test_real_bounded_child(self):
        class Clear:
            def require_clear(self):return {}
        out,r=run_registered(self.job,self.raw,host_id='HOST',worker_id='BUILD',private_parent=self.root,gate=Clear())
        self.assertEqual(r['exit_code'],0);self.assertEqual(r['output_sha256'],digest(out))
    def test_child_timeout(self):
        class Clear:
            def require_clear(self):return {}
        with self.assertRaisesRegex(EdgeRejected,'TIMEOUT'):
            run_registered(self.job,self.raw,host_id='HOST',worker_id='BUILD',private_parent=self.root,gate=Clear(),timeout=.001)
    def test_inflight_veto_kills_only_owned_child(self):
        class FailLater:
            calls=0
            def require_clear(self):
                self.calls+=1
                if self.calls>=3:raise EdgeRejected('injected HOLD')
        real=subprocess.Popen;children=[]
        def start(*a,**kw):p=real(*a,**kw);children.append(p);return p
        with patch('cyber_lion.enterprise.edge_yoke.executor.subprocess.Popen',side_effect=start):
            with self.assertRaisesRegex(EdgeRejected,'HOLD'):
                run_registered(self.job,self.raw,host_id='HOST',worker_id='BUILD',private_parent=self.root,gate=FailLater())
        self.assertIsNotNone(children[0].poll())
if __name__=='__main__':unittest.main()

"""Real filesystem + original engine/sandbox composition, FIXTURE authority only.

These tests do not issue live authority. Existing repository fixture factories
supply explicit synthetic admissions, dispatch and trust inputs for unit tests.
"""
from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.tests import test_executor_sandbox as sb
from cyber_lion.enterprise.executor_sandbox import ExecutorSandbox, InMemorySandboxReplayGuard
from cyber_lion.enterprise.runtime_execution import RuntimeExecutionEngine, InMemoryAdmissionConsumptionGuard, RuntimeExecutionError
from cyber_lion.enterprise.cooperative_runtime_writer import (
    CooperativeArtifactBackend, CooperativeExecutionBinding, CanonicalCooperativeWriter, CooperativeRuntimeWriterError,
)


class CooperativeRuntimeWriterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.data=b'candidate\n';self.resource='M1/g00000001/p.txt'
        self.payload={'kind':'COOPERATIVE_ARTIFACT_WRITE','mission_id':'M1','assignment_id':'assignment-1','generation':1,
                      'artifact_name':'p.txt','content':self.data.decode(),'expected_sha256':sha256(self.data).hexdigest(),
                      'producer_model_call_id':'modelcall-1','parent_response_digest':sha256(b'candidate').hexdigest()}
        original=json.dumps(self.payload,sort_keys=True,separators=(',',':'),ensure_ascii=False)
        self.claim={'assignment_id':'assignment-1','mission_id':'M1','material_drone_id':'MD001','lease_generation':1,
                    'state':'CLAIMED','lease_expires_at':'2099-01-01T00:00:00Z','input_json':original,'input_digest':sha256(original.encode()).hexdigest()}
        self.fd=sb.dispatch(mission_id='M1',drone_id='drone:1',write_scope=(self.resource,))
        pb=sb.provisioning(mission_id='M1',drone_id='drone:1',executor_id='executor:1',runtime_instance_id='runtime:1',
                           sandbox_id='sandbox:1',workspace_id='workspace:1',runtime_attestation_digest=rt.Z,
                           provisioned_executor_digest=rt.Z,read_scope=('M1',),write_scope=(self.resource,))
        rb=sb.runtime(sandbox_id='sandbox:1',workspace_id='workspace:1')
        policy=sb.policy(fd=self.fd,pb=pb,mission_id='M1',drone_id='drone:1',executor_id='executor:1',
                         sandbox_id='sandbox:1',workspace_id='workspace:1',runtime_instance_id='runtime:1',
                         runtime_attestation_digest=rt.Z,runtime_binding_digest=rb.digest(),
                         read_scope=('M1',),write_scope=(self.resource,),test_scope=('M1',))
        self.backend=CooperativeArtifactBackend(root=self.root,payload=self.payload,worker_id='MD001',runtime_binding=rb)
        self.dispatch_source=sb.DispatchSource(self.fd)
        sandbox=ExecutorSandbox(policy=policy,runtime_binding=rb,fleet_dispatch=self.fd,provisioning_binding=pb,
                                dispatch_source=self.dispatch_source,backend=self.backend,replay_guard=InMemorySandboxReplayGuard())
        identity=rt.identity();effect=rt.effect(identity,mission_id='M1',resource=self.resource,payload_digest=sha256(self.data).hexdigest())
        admission=rt.admission(effect,identity)
        request=rt.request(admission,effect,identity,execution_id='assignment-1',dispatch_id=self.fd.dispatch_id,
                           fencing_token=self.fd.fencing_token,payload_size=len(self.data))
        self.source=rt.AdmissionSource(admission)
        engine=RuntimeExecutionEngine(admission_source=self.source,admission_source_trust=rt.trust(),
                                      consumption_guard=InMemoryAdmissionConsumptionGuard(),sandbox=sandbox)
        self.binding=CooperativeExecutionBinding('assignment-1','MD001',self.claim['input_digest'],self.root,admission,request,effect,identity)
        self.writer=CanonicalCooperativeWriter(engine=engine,binding_source=lambda aid:self.binding)

    def run_write(self, **kw):
        params={'claimed':self.claim,'payload':self.payload,'artifact_root':self.root,'worker_id':'MD001'}
        params.update(kw);return self.writer(**params)

    def test_canonical_engine_writes_exact_bytes_and_returns_receipt(self):
        result=self.run_write()
        self.assertEqual((self.root/self.resource).read_bytes(),self.data)
        self.assertTrue(result['readback_match'])
        self.assertEqual(result['runtime_receipt']['outcome'],'SUCCEEDED')
        self.assertEqual(result['runtime_receipt']['effect_state'],'OBSERVED')
        self.assertEqual(result['effect_receipt_digest'],result['runtime_receipt']['receipt_digest'])

    def test_canonical_admission_replay_rejected(self):
        self.run_write()
        with self.assertRaises(RuntimeExecutionError):self.run_write()
        self.assertEqual((self.root/self.resource).read_bytes(),self.data)

    def test_stale_admission_rejected_before_filesystem(self):
        self.source.current=False
        with self.assertRaises(RuntimeExecutionError):self.run_write()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_forged_admission_rejected_before_filesystem(self):
        forged=replace(self.binding.admission,admission_id='forged',admission_digest='').sealed()
        self.binding=replace(self.binding,admission=forged)
        with self.assertRaises(RuntimeExecutionError):self.run_write()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_wrong_root_rejected(self):
        with self.assertRaises(CooperativeRuntimeWriterError):self.run_write(artifact_root=self.root/'other')
        self.assertEqual(list(self.root.iterdir()),[])

    def test_wrong_claim_generation_rejected(self):
        with self.assertRaises(CooperativeRuntimeWriterError):self.run_write(claimed={**self.claim,'lease_generation':2})
        self.assertEqual(list(self.root.iterdir()),[])

    def test_wrong_expected_input_digest_rejected(self):
        self.binding=replace(self.binding,input_digest='b'*64)
        with self.assertRaises(CooperativeRuntimeWriterError):self.run_write()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_expired_claim_rejected(self):
        with self.assertRaises(CooperativeRuntimeWriterError):self.run_write(claimed={**self.claim,'lease_expires_at':'2000-01-01T00:00:00Z'})
        self.assertEqual(list(self.root.iterdir()),[])

    def test_dispatch_fence_change_rejected(self):
        self.dispatch_source.current=replace(self.fd,fencing_token=rt.Z)
        with self.assertRaises(RuntimeExecutionError):self.run_write()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_backend_cannot_execute_processes(self):
        with self.assertRaises(CooperativeRuntimeWriterError):self.backend.run_test('M1',('python','-c','print(1)'))

    def test_worker_substitution_rejected(self):
        self.binding=replace(self.binding,worker_id='MD002')
        with self.assertRaises(CooperativeRuntimeWriterError):self.run_write()
        self.assertEqual(list(self.root.iterdir()),[])

if __name__=='__main__':unittest.main()

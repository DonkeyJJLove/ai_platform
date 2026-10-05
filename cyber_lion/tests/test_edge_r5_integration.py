"""Original R5 execution engine + real files; explicit synthetic authority fixtures."""
from pathlib import Path
import os
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cyber_lion.tests import test_cooperative_runtime_composition as native
from cyber_lion.enterprise.edge_yoke.gate import YokeGate,attach_yoke
from cyber_lion.enterprise.cooperative_runtime_writer import CooperativeRuntimeWriterError
from cyber_lion.enterprise.edge_yoke.evidence import sign,public_hex
from cyber_lion.mission_control.edge_support import canonical,EdgeRejected

@unittest.skipUnless(os.name == "posix" and all(hasattr(os, n) for n in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK")),
                     "Native R5 writer requires Linux descriptor-relative storage; run in Ubuntu/Docker, not a Windows PASS")
class NativeR5IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.f=native.CooperativeRuntimeCompositionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.key=Ed25519PrivateKey.generate();self.snapshot=Path(self.f.temp.name)/'snapshot.json'
        self.time=self.f.now.timestamp()
        self.gate=YokeGate(snapshot=self.snapshot,host_id='H',public_key=public_hex(self.key),policy_sha256='a'*64,clock=lambda:self.time)
        self.emit()
    def emit(self,state='NO_VETO'):
        self.snapshot.write_bytes(canonical(sign(dict(schema='lion.edge.veto/v2',host_id='H',policy_sha256='a'*64,
            observed_at=self.time,expires_at=self.time+6,seq=1,state=state,authority_effect='NONE'),self.key)))
    def provider(self):
        f=self.f
        deps=dict(context_source=f.context,admission_source=f.source,admission_trust=native.rt.trust(),authority_admission=f.live_authority,
            currentness_source=f.currentness,currentness_trust=native.rc.trust(),dispatch_source=f.dispatch_source,
            admission_guard=f.admission_guard,sandbox_guard=f.sandbox_guard,budget_source=lambda p:f.budget,now_fn=lambda:f.now)
        return attach_yoke(dependencies=deps,gate=self.gate)
    def test_original_engine_writes_actual_artifact(self):
        result=self.f.write(self.provider());self.assertEqual((self.f.root/self.f.resource).read_bytes(),self.f.data)
        self.assertIn('runtime_receipt',result);self.assertEqual(len(self.f.lookups),2)
    def test_veto_before_resolution_prevents_effect(self):
        self.emit('HOLD')
        with self.assertRaises(EdgeRejected):self.f.write(self.provider())
        self.f.assert_no_artifact();self.assertEqual(self.f.lookups,[])
    def test_veto_at_existing_before_write_callback(self):
        original=self.f.currentness.current_observability_state
        def observe(*a):self.emit('HOLD');return original(*a)
        self.f.currentness.current_observability_state=observe
        with self.assertRaises(CooperativeRuntimeWriterError):self.f.write(self.provider())
        self.f.assert_no_artifact()
    def test_late_veto_does_not_refund_consumed_admission(self):
        original=self.f.currentness.current_observability_state
        def observe(*a):self.emit('HOLD');return original(*a)
        self.f.currentness.current_observability_state=observe
        with self.assertRaises(CooperativeRuntimeWriterError):self.f.write(self.provider())
        self.f.currentness.current_observability_state=original;self.emit()
        with self.assertRaisesRegex(native.rt.RuntimeExecutionError,'replay'):self.f.write(self.provider())
        self.f.assert_no_artifact()
    def test_no_veto_does_not_override_native_revocation(self):
        self.f.live_authority.fail=True
        with self.assertRaises(native.rt.RuntimeExecutionError):self.f.write(self.provider())
        self.f.assert_no_artifact()
    def test_expired_observer_prevents_effect(self):
        self.time+=10
        with self.assertRaises(EdgeRejected):self.f.write(self.provider())
        self.f.assert_no_artifact()
if __name__=='__main__':unittest.main()

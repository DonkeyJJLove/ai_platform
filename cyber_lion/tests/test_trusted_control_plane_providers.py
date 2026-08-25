from __future__ import annotations
from pathlib import Path
import tempfile,unittest
from cyber_lion.contracts.builder_process_launch import BuilderExecutionGateEvidence,BuilderProcessRuntimeProviderDescriptor,PREPARE_CAPABILITY_CLASS
from cyber_lion.enterprise.trusted_control_plane_providers import PinnedBuilderProcessRuntimeProviderSource,SQLiteTrustedControlPlaneStore,TrustedControlPlaneProviderError,TrustedSignatureVerifierAdapter
D=lambda c:c*64

def descriptor():return BuilderProcessRuntimeProviderDescriptor("provider:r22",D("a"),D("b"),D("c"),"runtime:r22","BUILDER_PROCESS_START_ONLY",PREPARE_CAPABILITY_CLASS,D("d"),D("e"),"HELD_PROCESS","stable-handle","independent-process-and-gate","freeze-or-kill").sealed()
def record():
    d=descriptor();return {"record_kind":"builder-process-runtime-provider","lookup_key":{"provider_id":d.provider_id,"process_profile_digest":d.supported_process_profile_digest,"launch_policy_digest":d.supported_launch_policy_digest,"capability_class":d.capability_class},"provider":d.__dict__}
class Runtime:
    def __init__(self,d):self.descriptor=d;self.runtime_instance_identity=d.runtime_instance_identity
    def prepare_launch(self,request):return "launch:r22"
    def observe_held(self,launch_id):return None
    def observe_gate(self,launch_id):return BuilderExecutionGateEvidence("gate:r22",self.runtime_instance_identity,launch_id,"env:r22",D("1"),"CLOSED",D("2"),"2026-08-25T14:00:00Z").sealed()
    def commit_start(self,request,held,gate):return None
    def observe_launch(self,launch_id):return None
    def freeze_or_kill(self,launch_id):return None
class TrustedControlPlaneProviderTests(unittest.TestCase):
    def test_exact_bound_runtime_requires_runtime_instance(self):
        with tempfile.TemporaryDirectory() as d:
            s=SQLiteTrustedControlPlaneStore(str(Path(d)/"cp.db"));r=record();s.put_builder_process_runtime_provider_record(r);desc=descriptor();runtime=Runtime(desc)
            src=PinnedBuilderProcessRuntimeProviderSource(s,runtime_resolver=lambda identity:runtime if identity==desc.runtime_instance_identity else None)
            self.assertIs(src.resolve_bound_runtime(provider_id=desc.provider_id,process_profile_digest=desc.supported_process_profile_digest,launch_policy_digest=desc.supported_launch_policy_digest),runtime)
            runtime.runtime_instance_identity="runtime:other"
            with self.assertRaises(TrustedControlPlaneProviderError):src.resolve_bound_runtime(provider_id=desc.provider_id,process_profile_digest=desc.supported_process_profile_digest,launch_policy_digest=desc.supported_launch_policy_digest)
    def test_runtime_missing_observe_gate_is_denied(self):
        class Bad:
            descriptor=descriptor();runtime_instance_identity="runtime:r22"
            def prepare_launch(self,r):return "x"
            def observe_held(self,x):return None
            def commit_start(self,*a):return None
            def observe_launch(self,x):return None
            def freeze_or_kill(self,x):return None
        with tempfile.TemporaryDirectory() as d:
            s=SQLiteTrustedControlPlaneStore(str(Path(d)/"cp.db"));r=record();s.put_builder_process_runtime_provider_record(r);src=PinnedBuilderProcessRuntimeProviderSource(s,runtime_resolver=lambda _:Bad())
            with self.assertRaises(TrustedControlPlaneProviderError):src.resolve_bound_runtime(provider_id="provider:r22",process_profile_digest=D("d"),launch_policy_digest=D("e"))
    def test_signature_adapter_fail_closed(self):
        a=TrustedSignatureVerifierAdapter(lambda *_:True,ready=lambda:True);self.assertTrue(a.ready());self.assertTrue(a.verify(b"x","s","k","a"))
if __name__=="__main__":unittest.main()

from __future__ import annotations
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.builder_process_launch import BuilderProcessRuntimeProviderDescriptor
from cyber_lion.enterprise.trusted_control_plane_providers import (
    SQLiteTrustedControlPlaneStore, PinnedBuilderProcessRuntimeProviderSource,
    TrustedControlPlaneProviderError, TrustedSignatureVerifierAdapter,
)

REPO="DonkeyJJLove/ai_platform"; BASE="1"*40; HEAD="2"*40; D=lambda c:c*64

def provider_descriptor(**changes):
    data=dict(provider_id="provider:r22",provider_identity_digest=D("1"),provider_implementation_digest=D("2"),
        provider_attestation_digest=D("3"),runtime_instance_identity="runtime:r22:1",capability_class="BUILDER_PROCESS_START_ONLY",
        prepare_capability_class="MATERIALIZE_HELD_PROCESS_ONLY",supported_process_profile_digest=D("4"),supported_launch_policy_digest=D("5"),
        isolation_class="HELD_PROCESS",process_identity_scheme="stable-handle",observation_scheme="independent-held-observation",recovery_scheme="freeze-or-kill")
    data.update(changes);return BuilderProcessRuntimeProviderDescriptor(**data).sealed()

def provider_record(descriptor=None):
    d=descriptor or provider_descriptor()
    return {"record_kind":"builder-process-runtime-provider","lookup_key":{"provider_id":d.provider_id,"process_profile_digest":d.supported_process_profile_digest,"launch_policy_digest":d.supported_launch_policy_digest,"capability_class":d.capability_class},"provider":d.__dict__}

class RuntimeFake:
    def __init__(self,descriptor,instance=None):self.descriptor=descriptor;self.runtime_instance_identity=instance or descriptor.runtime_instance_identity
    def prepare_launch(self,*_):return "launch"
    def observe_held(self,*_):return object()
    def commit_start(self,*_):return object()
    def observe_launch(self,*_):return object()
    def freeze_or_kill(self,*_):return None

class TrustedControlPlaneProviderTests(unittest.TestCase):
    def test_exact_records_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/"control-plane.sqlite3");store=SQLiteTrustedControlPlaneStore(path);self.assertTrue(store.ready())
            bootstrap={"lookup_key":{"repository":REPO,"pr_number":41,"base_sha":BASE,"head_sha":HEAD,"merge_method":"merge"},"payload":"bootstrap"}
            authority={"lookup_key":{"repository":REPO,"pr_number":41,"base_sha":BASE,"head_sha":HEAD,"mission_id":"mission-n2","grant_id":"grant-n2"},"lineage":[]}
            builder={"record_kind":"builder-subject","lookup_key":{"repository":REPO,"builder_subject_id":"builder-1","builder_instance_id":"instance-1","candidate_scope_digest":D("a"),"resource_scope_digest":D("b"),"capability_class":"DETACHED_CANDIDATE_BUILD_ONLY"},"subject":{"sealed":True}}
            runtime=provider_record();store.put_pr_bootstrap(bootstrap);store.put_authority_record(authority);store.put_builder_subject_record(builder);store.put_builder_process_runtime_provider_record(runtime)
            restarted=SQLiteTrustedControlPlaneStore(path);self.assertTrue(restarted.ready())
            self.assertEqual(restarted.lookup_pr_bootstrap_exact(**bootstrap["lookup_key"]),(bootstrap,));self.assertEqual(restarted.lookup_authority_exact(**authority["lookup_key"]),(authority,));self.assertEqual(restarted.lookup_builder_subject_exact(**builder["lookup_key"]),(builder,));self.assertEqual(restarted.lookup_builder_process_runtime_provider_exact(**runtime["lookup_key"]),(runtime,))

    def test_wrong_exact_key_returns_zero_records(self):
        with tempfile.TemporaryDirectory() as directory:
            store=SQLiteTrustedControlPlaneStore(str(Path(directory)/"cp.db"))
            self.assertEqual(store.lookup_authority_exact(repository=REPO,pr_number=41,base_sha=BASE,head_sha=HEAD,mission_id="missing",grant_id="missing"),())
            self.assertEqual(store.lookup_builder_subject_exact(repository=REPO,builder_subject_id="missing",builder_instance_id="missing",candidate_scope_digest=D("a"),resource_scope_digest=D("b"),capability_class="DETACHED_CANDIDATE_BUILD_ONLY"),())

    def test_runtime_source_resolves_exact_executable_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            store=SQLiteTrustedControlPlaneStore(str(Path(directory)/"cp.db"));d=provider_descriptor();store.put_builder_process_runtime_provider_record(provider_record(d));runtime=RuntimeFake(d)
            source=PinnedBuilderProcessRuntimeProviderSource(store,runtime_resolver=lambda identity: runtime if identity==d.runtime_instance_identity else None)
            self.assertEqual(source.resolve_exact(provider_id=d.provider_id,process_profile_digest=d.supported_process_profile_digest,launch_policy_digest=d.supported_launch_policy_digest),d)
            self.assertIs(source.resolve_bound_runtime(provider_id=d.provider_id,process_profile_digest=d.supported_process_profile_digest,launch_policy_digest=d.supported_launch_policy_digest),runtime)

    def test_copied_descriptor_arbitrary_runtime_instance_is_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            store=SQLiteTrustedControlPlaneStore(str(Path(directory)/"cp.db"));d=provider_descriptor();store.put_builder_process_runtime_provider_record(provider_record(d))
            malicious=RuntimeFake(d,instance="runtime:attacker:1")
            source=PinnedBuilderProcessRuntimeProviderSource(store,runtime_resolver=lambda _: malicious)
            with self.assertRaises(TrustedControlPlaneProviderError):source.resolve_bound_runtime(provider_id=d.provider_id,process_profile_digest=d.supported_process_profile_digest,launch_policy_digest=d.supported_launch_policy_digest)

    def test_runtime_descriptor_implementation_and_attestation_substitution_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            store=SQLiteTrustedControlPlaneStore(str(Path(directory)/"cp.db"));d=provider_descriptor();store.put_builder_process_runtime_provider_record(provider_record(d))
            substituted=provider_descriptor(provider_implementation_digest=D("f"),provider_attestation_digest=D("e"))
            runtime=RuntimeFake(substituted)
            source=PinnedBuilderProcessRuntimeProviderSource(store,runtime_resolver=lambda _: runtime)
            with self.assertRaises(TrustedControlPlaneProviderError):source.resolve_bound_runtime(provider_id=d.provider_id,process_profile_digest=d.supported_process_profile_digest,launch_policy_digest=d.supported_launch_policy_digest)

    def test_runtime_bootstrap_rejects_noncanonical_record(self):
        with tempfile.TemporaryDirectory() as directory:
            store=SQLiteTrustedControlPlaneStore(str(Path(directory)/"cp.db"));d=provider_descriptor();record=provider_record(d)
            with self.assertRaises(TrustedControlPlaneProviderError):store.put_builder_process_runtime_provider_record({**record,"record_kind":"builder-subject"})
            with self.assertRaises(TrustedControlPlaneProviderError):store.put_builder_process_runtime_provider_record({**record,"lookup_key":{**record["lookup_key"],"extra":"x"}})

    def test_signature_adapter_is_runtime_bound_and_fail_closed(self):
        seen=[]
        def verifier(payload,signature,key_id,algorithm):seen.append((payload,signature,key_id,algorithm));return signature=="ok"
        adapter=TrustedSignatureVerifierAdapter(verifier,ready=lambda:True);self.assertTrue(adapter.ready());self.assertTrue(adapter.verify(b"payload","ok","key-1","ed25519"));self.assertFalse(adapter.verify(b"payload","bad","key-1","ed25519"));self.assertEqual(len(seen),2)
        broken=TrustedSignatureVerifierAdapter(lambda *_:(_ for _ in ()).throw(RuntimeError("down")))
        with self.assertRaises(TrustedControlPlaneProviderError):broken.verify(b"payload","sig","key","alg")

    def test_readiness_callback_fails_closed(self):
        self.assertFalse(TrustedSignatureVerifierAdapter(lambda *_:True,ready=lambda:False).ready())
        broken=TrustedSignatureVerifierAdapter(lambda *_:True,ready=lambda:(_ for _ in ()).throw(RuntimeError("down")));self.assertFalse(broken.ready())

if __name__=="__main__":unittest.main()

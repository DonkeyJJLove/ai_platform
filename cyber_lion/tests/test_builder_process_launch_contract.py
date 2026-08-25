from __future__ import annotations
import unittest
from dataclasses import replace

from cyber_lion.contracts.builder_process_launch import (
    BuilderProcessIdentity, BuilderProcessLaunchContractError, BuilderProcessLaunchReceipt,
    BuilderProcessLaunchRequest, BuilderProcessRuntimeProviderDescriptor,
    HELD_STATE, STARTED_STATE, compute_launch_replay_digest,
)

D="a"*64; S="b"*40

def descriptor():
    return BuilderProcessRuntimeProviderDescriptor(
        provider_id="provider:r22:test", provider_identity_digest=D,
        provider_implementation_digest="b"*64, provider_attestation_digest="c"*64,
        runtime_instance_identity="runtime:r22:test:1",
        capability_class="BUILDER_PROCESS_START_ONLY", prepare_capability_class="MATERIALIZE_HELD_PROCESS_ONLY",
        supported_process_profile_digest="d"*64, supported_launch_policy_digest="e"*64,
        isolation_class="HELD_PROCESS", process_identity_scheme="stable-handle",
        observation_scheme="independent-held-and-start-observation", recovery_scheme="freeze-or-kill",
    ).sealed()

def request():
    kw=dict(source_builder_start_admission_id="bsa:"+"1"*64,
        source_builder_start_admission_digest="2"*64, source_builder_start_admission_replay_digest="3"*64,
        source_builder_start_issuance_record_id="bsair:bsa:"+"1"*64, source_builder_start_issuance_record_digest="4"*64,
        repository="DonkeyJJLove/ai_platform", baseline_master_sha=S, baseline_master_tree_sha="c"*40,
        authority_epoch=1, authority_state_version=2, root_grant_id="grant:r22", root_grant_digest="5"*64,
        expected_current_authority_digest="6"*64, builder_subject_id="builder:r22", builder_instance_id="instance:r22",
        builder_identity_digest="7"*64, builder_implementation_digest="8"*64, builder_attestation_digest="9"*64,
        expected_builder_subject_digest="a"*64, process_profile_id="bpp:"+"d"*64, process_profile_digest="d"*64,
        launch_policy_digest="e"*64, runtime_provider_id="provider:r22:test", runtime_provider_identity_digest=D,
        runtime_provider_implementation_digest="b"*64, runtime_provider_attestation_digest="c"*64,
        runtime_instance_identity="runtime:r22:test:1")
    replay=compute_launch_replay_digest(**kw)
    return BuilderProcessLaunchRequest(launch_request_id=f"bplr:{replay}",launch_replay_digest=replay,**kw).sealed()

class BuilderProcessLaunchContractTests(unittest.TestCase):
    def test_provider_descriptor_is_sealed_and_capability_reduced(self):
        d=descriptor(); self.assertEqual(d.descriptor_digest,d.compute_digest())
        self.assertEqual(d.prepare_capability_class,"MATERIALIZE_HELD_PROCESS_ONLY")
        with self.assertRaises(BuilderProcessLaunchContractError): replace(d,authority_minting_capability="ALLOW",descriptor_digest="").validate()
        with self.assertRaises(BuilderProcessLaunchContractError): replace(d,prepare_capability_class="EXECUTE_BUILDER",descriptor_digest="").validate()

    def test_request_is_deterministic_non_effectful_and_runtime_instance_bound(self):
        a=request(); b=request(); self.assertEqual(a,b); self.assertEqual(a.launch_request_digest,b.launch_request_digest)
        self.assertEqual(a.runtime_instance_identity,"runtime:r22:test:1")
        self.assertEqual((a.authority_effect,a.execution_effect,a.repository_ref_effect,a.external_effect),("NONE","NONE","NONE","NONE"))

    def test_replay_changes_when_provider_attestation_or_runtime_instance_changes(self):
        a=request()
        x=replace(a,runtime_provider_attestation_digest="f"*64,launch_replay_digest="",launch_request_digest="")
        self.assertNotEqual(compute_launch_replay_digest(**x.replay_kwargs()),a.launch_replay_digest)
        y=replace(a,runtime_instance_identity="runtime:r22:test:2",launch_replay_digest="",launch_request_digest="")
        self.assertNotEqual(compute_launch_replay_digest(**y.replay_kwargs()),a.launch_replay_digest)

    def test_pid_alone_is_denied(self):
        with self.assertRaises(BuilderProcessLaunchContractError):
            BuilderProcessIdentity(launch_id="launch:r22",builder_subject_id="builder:r22",builder_instance_id="instance:r22",
                process_profile_id="bpp:"+"d"*64,process_profile_digest="d"*64,launch_policy_digest="e"*64,
                runtime_provider_id="provider:r22:test",runtime_provider_identity_digest=D,runtime_instance_identity="runtime:r22:test:1",
                execution_environment_id="env:r22",process_handle_reference="1234",process_identity_token="token:r22",
                started_at="2026-08-25T14:00:00Z",state=HELD_STATE).validate()

    def test_receipt_is_first_effect_only(self):
        r=request(); ident=BuilderProcessIdentity(launch_id="launch:r22",builder_subject_id="builder:r22",builder_instance_id="instance:r22",
            process_profile_id=r.process_profile_id,process_profile_digest=r.process_profile_digest,launch_policy_digest=r.launch_policy_digest,
            runtime_provider_id=r.runtime_provider_id,runtime_provider_identity_digest=r.runtime_provider_identity_digest,
            runtime_instance_identity=r.runtime_instance_identity,execution_environment_id="env:r22",process_handle_reference="pidfd:r22:1",
            process_identity_token="token:r22",started_at="2026-08-25T14:00:00Z",state=STARTED_STATE).sealed()
        receipt=BuilderProcessLaunchReceipt(launch_receipt_id=f"bplx:{r.launch_replay_digest}",launch_request_id=r.launch_request_id,
            launch_request_digest=r.launch_request_digest,launch_replay_digest=r.launch_replay_digest,
            source_builder_start_admission_id=r.source_builder_start_admission_id,source_builder_start_admission_digest=r.source_builder_start_admission_digest,
            repository=r.repository,baseline_master_sha=r.baseline_master_sha,baseline_master_tree_sha=r.baseline_master_tree_sha,
            authority_digest_at_launch=r.expected_current_authority_digest,builder_subject_digest_at_launch=r.expected_builder_subject_digest,
            process_profile_id=r.process_profile_id,process_profile_digest=r.process_profile_digest,launch_policy_digest=r.launch_policy_digest,
            runtime_provider_id=r.runtime_provider_id,runtime_provider_identity_digest=r.runtime_provider_identity_digest,
            runtime_provider_implementation_digest=r.runtime_provider_implementation_digest,runtime_provider_attestation_digest=r.runtime_provider_attestation_digest,
            runtime_instance_identity=r.runtime_instance_identity,launch_id=ident.launch_id,execution_environment_id=ident.execution_environment_id,
            process_handle_reference=ident.process_handle_reference,process_identity_token=ident.process_identity_token,process_identity_digest=ident.identity_digest,
            launch_started_at=ident.started_at,launch_observed_at="2026-08-25T14:00:01Z").sealed()
        self.assertEqual(receipt.execution_effect,"BUILDER_PROCESS_START")
        self.assertEqual((receipt.authority_effect,receipt.repository_ref_effect,receipt.external_effect),("NONE","NONE","NONE"))

if __name__=="__main__": unittest.main()

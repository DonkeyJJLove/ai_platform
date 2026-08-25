from __future__ import annotations
from dataclasses import replace
import unittest
from cyber_lion.contracts.builder_process_launch import BuilderExecutionGateEvidence,BuilderProcessIdentity,BuilderProcessLaunchContractError,BuilderProcessLaunchReceipt,BuilderProcessLaunchRequest,BuilderProcessRuntimeProviderDescriptor,GATE_CLOSED,GATE_OPENED_ONCE,HELD_STATE,PREPARE_CAPABILITY_CLASS,STARTED_STATE,compute_launch_replay_digest
D=lambda c:c*64

def descriptor():return BuilderProcessRuntimeProviderDescriptor("provider:r22",D("a"),D("b"),D("c"),"runtime:r22","BUILDER_PROCESS_START_ONLY",PREPARE_CAPABILITY_CLASS,D("d"),D("e"),"HELD_PROCESS","stable-handle","independent-process-and-gate","freeze-or-kill").sealed()
def request():
    kw=dict(source_builder_start_admission_id="bsa:"+D("1"),source_builder_start_admission_digest=D("2"),source_builder_start_admission_replay_digest=D("3"),source_builder_start_issuance_record_id="bsair:bsa:"+D("1"),source_builder_start_issuance_record_digest=D("4"),repository="DonkeyJJLove/ai_platform",baseline_master_sha="b"*40,baseline_master_tree_sha="c"*40,authority_epoch=1,authority_state_version=2,root_grant_id="grant:r22",root_grant_digest=D("5"),expected_current_authority_digest=D("6"),builder_subject_id="builder:r22",builder_instance_id="instance:r22",builder_identity_digest=D("7"),builder_implementation_digest=D("8"),builder_attestation_digest=D("9"),expected_builder_subject_digest=D("a"),process_profile_id="bpp:"+D("d"),process_profile_digest=D("d"),launch_policy_digest=D("e"),runtime_provider_id="provider:r22",runtime_provider_identity_digest=D("a"),runtime_provider_implementation_digest=D("b"),runtime_provider_attestation_digest=D("c"),runtime_instance_identity="runtime:r22")
    replay=compute_launch_replay_digest(**kw);return BuilderProcessLaunchRequest(launch_request_id=f"bplr:{replay}",launch_replay_digest=replay,**kw).sealed()
def gate(state):return BuilderExecutionGateEvidence("gate:r22","runtime:r22","launch:r22","env:r22",D("f"),state,D("0"),"2026-08-25T14:00:00Z").sealed()
def identity(state):return BuilderProcessIdentity("launch:r22","builder:r22","instance:r22","bpp:"+D("d"),D("d"),D("e"),"provider:r22",D("a"),"runtime:r22","env:r22","pidfd:r22:1","token:r22","gate:r22","2026-08-25T14:00:00Z",state).sealed()
class BuilderProcessLaunchContractTests(unittest.TestCase):
    def test_gate_evidence_sealed_and_states_constrained(self):
        self.assertEqual(gate(GATE_CLOSED).gate_state,"CLOSED");self.assertEqual(gate(GATE_OPENED_ONCE).gate_state,"OPENED_ONCE")
        with self.assertRaises(BuilderProcessLaunchContractError):replace(gate(GATE_CLOSED),gate_state="OPEN",execution_gate_digest="").validate()
    def test_provider_prepare_capability_must_be_materialize_only(self):
        with self.assertRaises(BuilderProcessLaunchContractError):replace(descriptor(),prepare_capability_class="START_BUILDER",descriptor_digest="").validate()
    def test_request_binds_runtime_instance_and_is_non_effectful(self):
        r=request();self.assertEqual((r.authority_effect,r.execution_effect,r.repository_ref_effect,r.external_effect),("NONE","NONE","NONE","NONE"))
        changed=replace(r,runtime_instance_identity="runtime:other",launch_replay_digest="",launch_request_digest="");self.assertNotEqual(compute_launch_replay_digest(**changed.replay_kwargs()),r.launch_replay_digest)
    def test_receipt_requires_gate_transition_and_stable_handle(self):
        r=request();s=identity(STARTED_STATE);c=gate(GATE_CLOSED);o=gate(GATE_OPENED_ONCE)
        receipt=BuilderProcessLaunchReceipt(f"bplx:{r.launch_replay_digest}",r.launch_request_id,r.launch_request_digest,r.launch_replay_digest,r.source_builder_start_admission_id,r.source_builder_start_admission_digest,r.repository,r.baseline_master_sha,r.baseline_master_tree_sha,r.expected_current_authority_digest,r.expected_builder_subject_digest,r.process_profile_id,r.process_profile_digest,r.launch_policy_digest,r.runtime_provider_id,r.runtime_provider_identity_digest,r.runtime_provider_implementation_digest,r.runtime_provider_attestation_digest,r.runtime_instance_identity,s.launch_id,s.execution_environment_id,s.process_handle_reference,s.process_identity_token,s.identity_digest,s.execution_gate_id,c.execution_gate_digest,o.execution_gate_digest,c.builder_entrypoint_digest,s.started_at,o.observed_at).sealed()
        self.assertEqual(receipt.gate_transition,"CLOSED_TO_OPENED_ONCE")
        with self.assertRaises(BuilderProcessLaunchContractError):replace(receipt,process_handle_reference="123",launch_receipt_digest="").validate()
        with self.assertRaises(BuilderProcessLaunchContractError):replace(receipt,gate_transition="OPEN",launch_receipt_digest="").validate()
if __name__=="__main__":unittest.main()

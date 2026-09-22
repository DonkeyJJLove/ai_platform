from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from cyber_lion.mission_control.material_worker_runtime import (
    ARCHITECTURE_CAPABILITIES,
    DIRECT_ASSIGNMENT_KINDS,
    IDENTITY_SCHEMA,
    INDEPENDENCE_STATE,
    PROFILE,
    MaterialWorkerContractError,
    architecture_profile,
    canonical_json,
    digest_payload,
    identity_probe,
    load_worker_identity,
    validate_action_ir_payload,
    validate_runtime_envelope_payload,
)
from cyber_lion.contracts.runtime_enforcement import RequestedRuntimeEffect, RuntimeAdmission, RuntimeIdentityBinding
from cyber_lion.contracts.runtime_execution import RuntimeExecutionRequest


Z="0"*64
F="f"*64
PAYLOAD=b"x"
PD=hashlib.sha256(PAYLOAD).hexdigest()


def action_ir():
    return {
        "schema_version":"1.0.0",
        "action_id":"r24.worker.validate.1",
        "kind":"repository.observe",
        "intent_ref":"intent:r24",
        "mission_ref":"mission:r24",
        "autonomy_ref":"autonomy:lion",
        "bean_ref":"bean:r24-worker",
        "target":{"host":"MOON","environment":"R24","runtime":"MATERIAL_WORKER_V2"},
        "authority_request":{"domain":"runtime","capability":"validate","grant_ref":None},
        "boundary":{
            "shell":False,
            "network":"DENY",
            "filesystem_read":[],
            "filesystem_write":[],
            "process_children":[],
            "timeout_ms":1000,
            "max_processes":1,
            "memory_limit_bytes":1048576,
        },
        "preconditions":["source-current"],
        "expected_effects":[],
        "forbidden_effects":["authority-minting","host-shell"],
        "observation":{"observer_class":"deterministic_independent","required_events":["contract-validated"]},
        "reconciliation":{"mode":"EXACT","receipt":"REQUIRED"},
    }


def identity():
    return RuntimeIdentityBinding(
        workload_identity="drone:r24:1",
        execution_subject="executor:r24:1",
        runtime_instance_id="runtime:r24:1",
        sandbox_id="sandbox:r24:1",
        workspace_id="workspace:r24:1",
        runtime_attestation_digest=Z,
        provisioned_executor_digest=F,
    ).validate()


def effect(i):
    return RequestedRuntimeEffect(
        effect_id="effect:r24:1",
        proposal_id="proposal:r24:1",
        mission_id="mission:r24",
        policy_binding="policy@r24:sha256:"+Z,
        authority_lineage_digest=Z,
        requested_authority="local_write",
        action_class="WRITE_FILE",
        resource="workspace/out.txt",
        payload_digest=PD,
        observability_state="HEALTHY",
        runtime_identity_digest=i.digest(),
    ).validate()


def admission(e,i):
    return RuntimeAdmission(
        admission_id="admission:r24:1",
        request_id="request:r24:1",
        gate_event_id="gate:r24:1",
        proposal_id=e.proposal_id,
        gate_decision_digest=Z,
        pdp_receipt_digest=Z,
        pdp_evidence_digest=Z,
        live_authority_digest=Z,
        authority_lineage_digest=e.authority_lineage_digest,
        policy_binding=e.policy_binding,
        effective_authority=e.requested_authority,
        requested_effect_digest=e.digest(),
        runtime_identity_digest=i.digest(),
        provisioned_executor_digest=i.provisioned_executor_digest,
        observability_state=e.observability_state,
        replay_key=Z,
    ).sealed()


def request(a,e,i):
    return RuntimeExecutionRequest(
        execution_id="exec:r24:1",
        admission_digest=a.admission_digest,
        requested_effect_digest=e.digest(),
        runtime_identity_digest=i.digest(),
        provisioned_executor_digest=i.provisioned_executor_digest,
        mission_id=e.mission_id,
        executor_id=i.execution_subject,
        runtime_instance_id=i.runtime_instance_id,
        sandbox_id=i.sandbox_id,
        workspace_id=i.workspace_id,
        dispatch_id=Z,
        fencing_token=F,
        generation=1,
        action=e.action_class,
        resource=e.resource,
        payload_digest=e.payload_digest,
        payload_size=len(PAYLOAD),
        command=(),
    ).validate()


class MaterialWorkerRuntimeTests(unittest.TestCase):
    def test_action_ir_validation_is_canonical_and_non_effectful(self):
        result=validate_action_ir_payload({"action_ir":action_ir()})
        self.assertEqual(result["kind"],"CANONICAL_ACTION_IR_VALIDATE")
        self.assertEqual(result["authority_effect"],"NONE")
        self.assertEqual(result["mission_ref"],"mission:r24")
        self.assertEqual(len(result["action_ir_digest"]),64)

    def test_action_ir_expected_digest_substitution_is_denied(self):
        with self.assertRaisesRegex(MaterialWorkerContractError,"expected digest"):
            validate_action_ir_payload({"action_ir":action_ir(),"expected_action_ir_digest":Z})

    def test_runtime_envelope_validation_binds_admission_effect_identity_and_request(self):
        i=identity();e=effect(i);a=admission(e,i);r=request(a,e,i)
        result=validate_runtime_envelope_payload({
            "runtime_identity":i.canonical_dict(),
            "requested_effect":e.canonical_dict(),
            "runtime_admission":a.canonical_dict(),
            "execution_request":r.canonical_dict(),
        })
        self.assertEqual(result["mission_id"],"mission:r24")
        self.assertEqual(result["executor_id"],"executor:r24:1")
        self.assertEqual(result["execution_performed"],False)
        self.assertEqual(result["authority_effect"],"NONE")

    def test_runtime_envelope_identity_substitution_is_denied(self):
        i=identity();e=effect(i);a=admission(e,i);r=request(a,e,i)
        bad=dict(i.canonical_dict());bad["runtime_instance_id"]="runtime:forged"
        with self.assertRaises(MaterialWorkerContractError):
            validate_runtime_envelope_payload({
                "runtime_identity":bad,
                "requested_effect":e.canonical_dict(),
                "runtime_admission":a.canonical_dict(),
                "execution_request":r.canonical_dict(),
            })

    def test_digest_payload_is_bounded(self):
        result=digest_payload({"text":"abc"})
        self.assertEqual(result["payload_sha256"],hashlib.sha256(b"abc").hexdigest())
        self.assertEqual(result["payload_bytes"],3)
        with self.assertRaises(MaterialWorkerContractError):
            digest_payload({"text":"x"*131073})

    def test_identity_file_binds_worker_contract_and_source_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);worker=root/"worker.py";contract=root/"contract.py";identity_path=root/"identity.json"
            worker.write_text("print('worker')\n",encoding="utf-8")
            contract.write_text("VALUE=1\n",encoding="utf-8")
            body={
                "schema":IDENTITY_SCHEMA,
                "profile":PROFILE,
                "repository":"DonkeyJJLove/ai_platform",
                "source_head":"1"*40,
                "source_tree":"2"*40,
                "worker_source_sha256":hashlib.sha256(worker.read_bytes()).hexdigest(),
                "runtime_contract_sha256":hashlib.sha256(contract.read_bytes()).hexdigest(),
                "compose_sha256":"3"*64,
                "authority_ceiling":"NONE",
                "material_executor_independence":INDEPENDENCE_STATE,
                "direct_assignment_kinds":list(DIRECT_ASSIGNMENT_KINDS),
                "architecture_capabilities":list(ARCHITECTURE_CAPABILITIES),
                "materialized_at":"2026-09-23T00:00:00Z",
            }
            body["identity_digest"]=hashlib.sha256(canonical_json(body)).hexdigest()
            identity_path.write_text(json.dumps(body),encoding="utf-8")
            loaded=load_worker_identity(identity_path,worker,contract)
            self.assertEqual(loaded["identity_digest"],body["identity_digest"])
            worker.write_text("print('tampered')\n",encoding="utf-8")
            with self.assertRaisesRegex(MaterialWorkerContractError,"worker source sha"):
                load_worker_identity(identity_path,worker,contract)

    def test_profile_truthfully_keeps_material_independence_unproven(self):
        ident={
            "source_head":"1"*40,
            "source_tree":"2"*40,
            "worker_source_sha256":"3"*64,
            "runtime_contract_sha256":"4"*64,
            "identity_digest":"5"*64,
        }
        profile=architecture_profile(ident,runtime_instance_id="container-1",boot_id="shared-boot")
        self.assertEqual(profile["material_executor_independence"],INDEPENDENCE_STATE)
        self.assertFalse(profile["model_is_authority"])
        self.assertFalse(profile["tool_availability_is_authority"])
        self.assertFalse(profile["logical_drone_is_material_executor"])
        self.assertTrue(profile["external_effects_require_admission"])
        probe=identity_probe(ident,worker_id="MD001",runtime_instance_id="container-1",boot_id="shared-boot")
        self.assertEqual(probe["authority_effect"],"NONE")


if __name__=="__main__":
    unittest.main()

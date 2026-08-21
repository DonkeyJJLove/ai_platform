from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import unittest

from cyber_lion.contracts.executor_sandbox import (
    ExecutionSandboxContractError,
    ExecutionSandboxPolicy,
    FleetDispatchBinding,
    ProvisioningBinding,
    SandboxOperation,
    SandboxResourceLimits,
    SandboxRuntimeBinding,
    path_within_scope,
)

D=lambda x: sha256(x.encode()).hexdigest()
SHA="1"*40; TREE="2"*40; REPO="DonkeyJJLove/ai_platform"


def dispatch(**kw):
    v=FleetDispatchBinding("mission-a","drone-a",D("dispatch"),D("fence"),1,REPO,SHA,TREE,"mission/a",("cyber_lion/x.py",)); return replace(v,**kw)

def provisioning(**kw):
    v=ProvisioningBinding(D("req"),D("mat"),D("receipt"),"mission-a","drone-a","executor-a",REPO,SHA,TREE,"mission/a",("cyber_lion",),("cyber_lion/x.py",),"runtime-a","sandbox-a","workspace-a",D("att")); return replace(v,**kw)

def runtime(**kw):
    v=SandboxRuntimeBinding("backend-a",D("backend-id"),D("backend-impl"),D("isolation"),"sandbox-a","workspace-a"); return replace(v,**kw)

def policy(**kw):
    fd=dispatch(); pb=provisioning(); rb=runtime()
    v=ExecutionSandboxPolicy(REPO,SHA,TREE,"mission/a","mission-a","drone-a","executor-a","sandbox-a","workspace-a","runtime-a",D("authority"),rb.digest(),fd.digest(),pb.digest(),fd.dispatch_id,fd.fencing_token,1,D("att"),("cyber_lion",),("cyber_lion/x.py",),("cyber_lion/tests",),(("python","-m","unittest"),),SandboxResourceLimits(10,1000,1000,2)); return replace(v,**kw)

class ContractTests(unittest.TestCase):
    def test_policy_is_immutable_and_binding_digest_deterministic(self):
        p=policy(); p.validate_bindings(dispatch(),provisioning()); self.assertEqual(p.digest(),policy().digest())
        with self.assertRaises(FrozenInstanceError): p.mission_id="x"  # type: ignore[misc]
    def test_dispatch_binds_generation_and_baseline_tree(self):
        p=policy()
        with self.assertRaises(ExecutionSandboxContractError): p.validate_bindings(dispatch(generation=2),provisioning())
        with self.assertRaises(ExecutionSandboxContractError): p.validate_bindings(dispatch(baseline_tree_sha="3"*40),provisioning())
    def test_provisioning_binds_request_materialization_runtime_and_workspace(self):
        p=policy()
        for bad in (
            provisioning(provisioning_request_digest=D("other")),
            provisioning(provisioning_materialization_digest=D("other")),
            provisioning(runtime_instance_id="runtime-b"),
            provisioning(runtime_attestation_digest=D("other")),
            provisioning(workspace_id="workspace-b"),
        ):
            with self.assertRaises(ExecutionSandboxContractError): p.validate_bindings(dispatch(),bad)
    def test_authority_is_digest_only(self):
        p=policy(authority_binding_digest=D("existing-authority")); p.validate()
        self.assertFalse(hasattr(p,"grant_authority")); self.assertFalse(hasattr(p,"delegate_authority"))
    def test_scope_is_component_safe(self):
        self.assertTrue(path_within_scope("cyber_lion/a.py",("cyber_lion",)))
        self.assertFalse(path_within_scope("cyber_lion2/a.py",("cyber_lion",)))
        for value in ("../x","/x","cyber_lion//x","cyber_lion/./x","cyber_lion/*.py"):
            with self.assertRaises(ExecutionSandboxContractError): path_within_scope(value,("cyber_lion",))
    def test_runtime_is_fail_closed(self):
        runtime().validate()
        for bad in (runtime(network_mode="ALLOW"),runtime(filesystem_mode="HOST"),runtime(process_mode="ANY"),runtime(ephemeral=False)):
            with self.assertRaises(ExecutionSandboxContractError): bad.validate()
    def test_operation_requires_dispatch_fence_and_generation(self):
        p=policy(); op=SandboxOperation("op","mission-a","drone-a","executor-a","sandbox-a","workspace-a",p.dispatch_id,p.fencing_token,1,p.digest(),"READ_FILE","cyber_lion/a.py"); op.validate()
        with self.assertRaises(ExecutionSandboxContractError): replace(op,generation=0).validate()
        with self.assertRaises(ExecutionSandboxContractError): replace(op,fencing_token="x").validate()
    def test_only_three_actions_are_representable(self):
        p=policy(); base=SandboxOperation("op","mission-a","drone-a","executor-a","sandbox-a","workspace-a",p.dispatch_id,p.fencing_token,1,p.digest(),"READ_FILE","cyber_lion/a.py")
        with self.assertRaises(ExecutionSandboxContractError): replace(base,action="SHELL").validate()

if __name__ == "__main__": unittest.main()

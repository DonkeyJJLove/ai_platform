from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import unittest

from cyber_lion.contracts.executor_sandbox import (
    ExecutionSandboxPolicy,
    FleetDispatchBinding,
    ProvisioningBinding,
    SandboxOperation,
    SandboxResourceLimits,
    SandboxRuntimeBinding,
)
from cyber_lion.enterprise.executor_sandbox import (
    ExecutorSandbox,
    InMemorySandboxReplayGuard,
    SandboxBackendReadResult,
    SandboxBackendTestResult,
    SandboxBackendWriteResult,
    SandboxBudgetLedger,
    SandboxEnforcementError,
)

D=lambda x: sha256(x.encode()).hexdigest()
SHA="1"*40; TREE="2"*40; REPO="DonkeyJJLove/ai_platform"

def dispatch(**kw):
    v=FleetDispatchBinding("mission-a","drone-a",D("dispatch"),D("fence"),1,REPO,SHA,TREE,"mission/a",("cyber_lion/x.py",)); return replace(v,**kw)

def provisioning(**kw):
    v=ProvisioningBinding(D("req"),D("mat"),D("receipt"),"mission-a","drone-a","executor-a",REPO,SHA,TREE,"mission/a",("cyber_lion",),("cyber_lion/x.py",),"runtime-a","sandbox-a","workspace-a",D("att")); return replace(v,**kw)

def runtime(**kw):
    v=SandboxRuntimeBinding("backend-a",D("backend-id"),D("backend-impl"),D("isolation"),"sandbox-a","workspace-a"); return replace(v,**kw)

def policy(*, limits=None, fd=None, pb=None, **kw):
    fd=fd or dispatch(); pb=pb or provisioning(); rb=runtime()
    v=ExecutionSandboxPolicy(REPO,SHA,TREE,"mission/a","mission-a","drone-a","executor-a","sandbox-a","workspace-a","runtime-a",D("authority"),rb.digest(),fd.digest(),pb.digest(),fd.dispatch_id,fd.fencing_token,fd.generation,D("att"),("cyber_lion",),("cyber_lion/x.py",),("cyber_lion/tests",),(("python","-m","unittest"),),limits or SandboxResourceLimits(10,1000,1000,3)); return replace(v,**kw)

class DispatchSource:
    def __init__(self,current): self.current=current; self.calls=0
    def current_dispatch(self,mission_id): self.calls+=1; return self.current

class Backend:
    backend_id="backend-a"; backend_identity_digest=D("backend-id"); backend_implementation_digest=D("backend-impl"); sandbox_id="sandbox-a"; workspace_id="workspace-a"
    def __init__(self): self.read_calls=0; self.write_calls=0; self.test_calls=0; self.raise_write=False; self.wrong_digest=False; self.files={"cyber_lion/a.py":b"ok"}
    def read_file(self,path): self.read_calls+=1; return SandboxBackendReadResult(self.files.get(path,b""),f"read:{path}")
    def write_file(self,path,payload):
        self.write_calls+=1; self.files[path]=payload
        if self.raise_write: raise RuntimeError("unknown effect")
        dg=D("wrong") if self.wrong_digest else sha256(payload).hexdigest()
        return SandboxBackendWriteResult(dg,f"write:{path}",f"effect:{path}")
    def run_test(self,path,command): self.test_calls+=1; return SandboxBackendTestResult(0,b"ok",b"",f"test:{path}")

def make(fd=None,pb=None,backend=None,limits=None):
    fd=fd or dispatch(); pb=pb or provisioning(); p=policy(fd=fd,pb=pb,limits=limits); src=DispatchSource(fd); b=backend or Backend()
    return ExecutorSandbox(policy=p,runtime_binding=runtime(),fleet_dispatch=fd,provisioning_binding=pb,dispatch_source=src,backend=b,replay_guard=InMemorySandboxReplayGuard()),p,src,b

def op(p,action="READ_FILE",path="cyber_lion/a.py",operation_id="op",payload=b"",command=()):
    return SandboxOperation(operation_id,p.mission_id,p.drone_id,p.executor_id,p.sandbox_id,p.workspace_id,p.dispatch_id,p.fencing_token,p.generation,p.digest(),action,path,sha256(payload).hexdigest() if action=="WRITE_FILE" else None,len(payload) if action=="WRITE_FILE" else 0,command)

class SandboxTests(unittest.TestCase):
    def test_valid_read_returns_fleet_and_provisioning_bound_receipt(self):
        s,p,src,b=make(); r=s.execute(op(p)); self.assertEqual(r.output,b"ok"); self.assertEqual(r.receipt.generation,1); self.assertEqual(r.receipt.fleet_dispatch_binding_digest,p.fleet_dispatch_binding_digest); self.assertEqual(r.receipt.provisioning_binding_digest,p.provisioning_binding_digest); self.assertEqual(src.calls,1)
    def test_stale_generation_denied_before_replay_budget_and_backend(self):
        s,p,src,b=make(); src.current=dispatch(dispatch_id=D("new-dispatch"),fencing_token=D("new-fence"),generation=2)
        with self.assertRaises(SandboxEnforcementError): s.execute(op(p,operation_id="fresh-id"))
        self.assertEqual(b.read_calls,0); self.assertEqual(s.budget_snapshot().operations,0)
    def test_stale_fencing_token_denied_before_effect(self):
        s,p,src,b=make(); src.current=dispatch(fencing_token=D("other-fence"))
        with self.assertRaises(SandboxEnforcementError): s.execute(op(p)); self.assertEqual(b.read_calls,0)
    def test_dispatch_source_failure_fails_closed(self):
        class Bad: 
            def current_dispatch(self,mission_id): raise RuntimeError("down")
        fd=dispatch(); pb=provisioning(); p=policy(fd=fd,pb=pb); b=Backend(); s=ExecutorSandbox(policy=p,runtime_binding=runtime(),fleet_dispatch=fd,provisioning_binding=pb,dispatch_source=Bad(),backend=b,replay_guard=InMemorySandboxReplayGuard())
        with self.assertRaises(SandboxEnforcementError): s.execute(op(p)); self.assertEqual(b.read_calls,0)
    def test_provisioning_request_substitution_denied_at_construction(self):
        fd=dispatch(); pb=provisioning(); p=policy(fd=fd,pb=pb)
        with self.assertRaises(SandboxEnforcementError): ExecutorSandbox(policy=p,runtime_binding=runtime(),fleet_dispatch=fd,provisioning_binding=replace(pb,provisioning_request_digest=D("other")),dispatch_source=DispatchSource(fd),backend=Backend(),replay_guard=InMemorySandboxReplayGuard())
    def test_materialization_substitution_denied(self):
        fd=dispatch(); pb=provisioning(); p=policy(fd=fd,pb=pb)
        with self.assertRaises(SandboxEnforcementError): ExecutorSandbox(policy=p,runtime_binding=runtime(),fleet_dispatch=fd,provisioning_binding=replace(pb,provisioning_materialization_digest=D("other")),dispatch_source=DispatchSource(fd),backend=Backend(),replay_guard=InMemorySandboxReplayGuard())
    def test_runtime_instance_substitution_denied(self):
        fd=dispatch(); pb=provisioning(); p=policy(fd=fd,pb=pb)
        with self.assertRaises(SandboxEnforcementError): ExecutorSandbox(policy=p,runtime_binding=runtime(),fleet_dispatch=fd,provisioning_binding=replace(pb,runtime_instance_id="runtime-b"),dispatch_source=DispatchSource(fd),backend=Backend(),replay_guard=InMemorySandboxReplayGuard())
    def test_runtime_attestation_substitution_denied(self):
        fd=dispatch(); pb=provisioning(); p=policy(fd=fd,pb=pb)
        with self.assertRaises(SandboxEnforcementError): ExecutorSandbox(policy=p,runtime_binding=runtime(),fleet_dispatch=fd,provisioning_binding=replace(pb,runtime_attestation_digest=D("other")),dispatch_source=DispatchSource(fd),backend=Backend(),replay_guard=InMemorySandboxReplayGuard())
    def test_baseline_tree_substitution_denied(self):
        fd=dispatch(); pb=provisioning(); p=policy(fd=fd,pb=pb)
        with self.assertRaises(SandboxEnforcementError): ExecutorSandbox(policy=p,runtime_binding=runtime(),fleet_dispatch=replace(fd,baseline_tree_sha="3"*40),provisioning_binding=pb,dispatch_source=DispatchSource(fd),backend=Backend(),replay_guard=InMemorySandboxReplayGuard())
    def test_operation_dispatch_substitution_denied(self):
        s,p,src,b=make()
        with self.assertRaises(SandboxEnforcementError): s.execute(replace(op(p),dispatch_id=D("other")))
        self.assertEqual(b.read_calls,0)
    def test_out_of_scope_write_denied(self):
        s,p,src,b=make(); payload=b"x"
        with self.assertRaises(SandboxEnforcementError): s.execute(op(p,"WRITE_FILE","cyber_lion/y.py",payload=payload),payload=payload)
        self.assertEqual(b.write_calls,0)
    def test_write_payload_digest_and_size_are_exact(self):
        s,p,src,b=make(); payload=b"abc"; good=op(p,"WRITE_FILE","cyber_lion/x.py",payload=payload)
        with self.assertRaises(SandboxEnforcementError): s.execute(good,payload=b"abd")
        self.assertEqual(b.write_calls,0)
    def test_replay_denied(self):
        s,p,src,b=make(); o=op(p); s.execute(o)
        with self.assertRaises(SandboxEnforcementError): s.execute(o)
        self.assertEqual(b.read_calls,1)
    def test_budget_reserved_before_effect(self):
        limits=SandboxResourceLimits(2,2,100,1); s,p,src,b=make(limits=limits); payload=b"abc"
        with self.assertRaises(SandboxEnforcementError): s.execute(op(p,"WRITE_FILE","cyber_lion/x.py",payload=payload),payload=payload)
        self.assertEqual(b.write_calls,0)
    def test_ambiguous_write_effect_aborts_and_does_not_retry(self):
        b=Backend(); b.raise_write=True; s,p,src,_=make(backend=b); payload=b"abc"; o=op(p,"WRITE_FILE","cyber_lion/x.py",payload=payload)
        r=s.execute(o,payload=payload); self.assertEqual(r.receipt.outcome,"ABORTED"); self.assertEqual(b.write_calls,1)
        with self.assertRaises(SandboxEnforcementError): s.execute(o,payload=payload)
        self.assertEqual(b.write_calls,1)
    def test_post_write_mismatch_aborts(self):
        b=Backend(); b.wrong_digest=True; s,p,src,_=make(backend=b); payload=b"abc"; r=s.execute(op(p,"WRITE_FILE","cyber_lion/x.py",payload=payload),payload=payload); self.assertEqual(r.receipt.outcome,"ABORTED")
    def test_unallowlisted_test_command_denied(self):
        s,p,src,b=make()
        with self.assertRaises(SandboxEnforcementError): s.execute(op(p,"RUN_TEST","cyber_lion/tests/test_x.py",command=("sh","-c","git push origin master")))
        self.assertEqual(b.test_calls,0)
    def test_allowlisted_test_runs(self):
        s,p,src,b=make(); r=s.execute(op(p,"RUN_TEST","cyber_lion/tests/test_x.py",command=p.allowed_test_commands[0])); self.assertEqual(r.receipt.outcome,"SUCCEEDED"); self.assertEqual(b.test_calls,1)
    def test_backend_provenance_substitution_denied(self):
        fd=dispatch(); pb=provisioning(); p=policy(fd=fd,pb=pb); b=Backend(); b.backend_implementation_digest=D("tampered")
        with self.assertRaises(SandboxEnforcementError): ExecutorSandbox(policy=p,runtime_binding=runtime(),fleet_dispatch=fd,provisioning_binding=pb,dispatch_source=DispatchSource(fd),backend=b,replay_guard=InMemorySandboxReplayGuard())
    def test_close_denies_late_execution(self):
        s,p,src,b=make(); s.close()
        with self.assertRaises(SandboxEnforcementError): s.execute(op(p)); self.assertEqual(b.read_calls,0)
    def test_no_generic_effect_surface(self):
        s,p,src,b=make()
        for name in ("execute_shell","run_command","network_request","update_ref","merge","release","deploy","grant_authority"):
            self.assertFalse(hasattr(s,name),name)

if __name__ == "__main__": unittest.main()

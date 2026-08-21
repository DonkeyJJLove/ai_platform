"""Fleet-bound execution sandbox contracts (F005-C R2). Evidence only; no authority minting, ref mutation, merge, release or deploy surface."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json,re
from pathlib import PurePosixPath
from typing import Any,Mapping

V="2.0.0"; S40=re.compile(r"^[0-9a-f]{40}$"); S64=re.compile(r"^[0-9a-f]{64}$"); REPO=re.compile(r"^[^/\s]+/[^/\s]+$"); ACTIONS={"READ_FILE","WRITE_FILE","RUN_TEST"}; OUTCOMES={"SUCCEEDED","FAILED","ABORTED"}
class ExecutionSandboxContractError(ValueError): pass
def canonical_json(v:Mapping[str,Any])->bytes:return json.dumps(dict(v),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def text(v,n,limit=2048):
    if not isinstance(v,str) or not v.strip() or len(v)>limit or "\x00" in v: raise ExecutionSandboxContractError(f"{n} invalid")
    return v
def dg(v,n):
    v=text(v,n,64)
    if not S64.fullmatch(v): raise ExecutionSandboxContractError(f"{n} must be sha256")
    return v
def sha(v,n):
    v=text(v,n,40)
    if not S40.fullmatch(v): raise ExecutionSandboxContractError(f"{n} must be git sha")
    return v
def branch(v):
    v=text(v,"branch",255)
    if v.startswith(("refs/","/")) or v.endswith(("/",".",".lock")) or ".." in v or "//" in v or "@{" in v or any(c in v for c in " ~^:?*[\\"): raise ExecutionSandboxContractError("branch invalid")
    return v
def path(v,n="path"):
    v=text(v,n)
    if "\\" in v or any(c in v for c in "*?[]"): raise ExecutionSandboxContractError(f"{n} not concrete POSIX")
    p=PurePosixPath(v)
    if p.is_absolute() or ".." in p.parts or str(p) in {"","."} or str(p)!=v: raise ExecutionSandboxContractError(f"{n} unsafe")
    return v
def scope(v,n):
    if type(v) is not tuple or not v: raise ExecutionSandboxContractError(f"{n} must be tuple")
    out=tuple(path(x,n) for x in v)
    if len(set(out))!=len(out): raise ExecutionSandboxContractError(f"{n} duplicate")
    return out
def command(v):
    if type(v) is not tuple or not v: raise ExecutionSandboxContractError("command invalid")
    for x in v:
        text(x,"command token")
        if "\n" in x or "\r" in x: raise ExecutionSandboxContractError("command token invalid")
    return v
def path_within_scope(p,s):
    a=PurePosixPath(path(p)).parts
    return any(a[:len(b)]==b for b in (PurePosixPath(x).parts for x in scope(s,"scope")))

def _repo(v):
    if not REPO.fullmatch(text(v,"repository")): raise ExecutionSandboxContractError("repository invalid")
    return v

@dataclass(frozen=True)
class SandboxResourceLimits:
    max_operations:int; max_write_bytes:int; max_output_bytes:int; max_test_runs:int
    def validate(self):
        for n in ("max_operations","max_write_bytes","max_output_bytes","max_test_runs"):
            v=getattr(self,n)
            if isinstance(v,bool) or not isinstance(v,int) or v<1: raise ExecutionSandboxContractError(f"{n} invalid")
        return self

@dataclass(frozen=True)
class SandboxRuntimeBinding:
    backend_id:str; backend_identity_digest:str; backend_implementation_digest:str; isolation_evidence_digest:str; sandbox_id:str; workspace_id:str; filesystem_mode:str="WORKSPACE_ONLY"; network_mode:str="DENY_ALL"; process_mode:str="ALLOWLIST_ONLY"; ephemeral:bool=True; schema_version:str=V
    def validate(self):
        if self.schema_version!=V: raise ExecutionSandboxContractError("runtime schema")
        for n in ("backend_id","sandbox_id","workspace_id"): text(getattr(self,n),n)
        for n in ("backend_identity_digest","backend_implementation_digest","isolation_evidence_digest"): dg(getattr(self,n),n)
        if (self.filesystem_mode,self.network_mode,self.process_mode,self.ephemeral)!=("WORKSPACE_ONLY","DENY_ALL","ALLOWLIST_ONLY",True): raise ExecutionSandboxContractError("runtime isolation")
        return self
    def digest(self): self.validate(); return sha256(b"LION/SANDBOX-RUNTIME/2\0"+canonical_json(asdict(self))).hexdigest()

@dataclass(frozen=True)
class FleetDispatchBinding:
    mission_id:str; drone_id:str; dispatch_id:str; fencing_token:str; generation:int; repository:str; baseline_sha:str; baseline_tree_sha:str; branch:str; write_scope:tuple[str,...]
    def validate(self):
        text(self.mission_id,"mission_id"); text(self.drone_id,"drone_id"); dg(self.dispatch_id,"dispatch_id"); dg(self.fencing_token,"fencing_token"); _repo(self.repository); sha(self.baseline_sha,"baseline_sha"); sha(self.baseline_tree_sha,"baseline_tree_sha"); branch(self.branch); scope(self.write_scope,"write_scope")
        if isinstance(self.generation,bool) or not isinstance(self.generation,int) or self.generation<1: raise ExecutionSandboxContractError("generation invalid")
        return self
    def canonical_dict(self): self.validate(); v=asdict(self); v["write_scope"]=list(self.write_scope); return v
    def digest(self): return sha256(b"LION/FLEET-DISPATCH/1\0"+canonical_json(self.canonical_dict())).hexdigest()

@dataclass(frozen=True)
class ProvisioningBinding:
    provisioning_request_digest:str; provisioning_materialization_digest:str; provisioned_executor_digest:str; mission_id:str; drone_id:str; executor_id:str; repository:str; baseline_sha:str; baseline_tree_sha:str; branch:str; read_scope:tuple[str,...]; write_scope:tuple[str,...]; runtime_instance_id:str; sandbox_id:str; workspace_id:str; runtime_attestation_digest:str
    def validate(self):
        for n in ("provisioning_request_digest","provisioning_materialization_digest","provisioned_executor_digest","runtime_attestation_digest"): dg(getattr(self,n),n)
        for n in ("mission_id","drone_id","executor_id","runtime_instance_id","sandbox_id","workspace_id"): text(getattr(self,n),n)
        _repo(self.repository); sha(self.baseline_sha,"baseline_sha"); sha(self.baseline_tree_sha,"baseline_tree_sha"); branch(self.branch); scope(self.read_scope,"read_scope"); scope(self.write_scope,"write_scope"); return self
    def canonical_dict(self): self.validate(); v=asdict(self); v["read_scope"]=list(self.read_scope); v["write_scope"]=list(self.write_scope); return v
    def digest(self): return sha256(b"LION/PROVISIONING-BINDING/1\0"+canonical_json(self.canonical_dict())).hexdigest()

@dataclass(frozen=True)
class ExecutionSandboxPolicy:
    repository:str; baseline_sha:str; baseline_tree_sha:str; branch:str; mission_id:str; drone_id:str; executor_id:str; sandbox_id:str; workspace_id:str; runtime_instance_id:str; authority_binding_digest:str; runtime_binding_digest:str; fleet_dispatch_binding_digest:str; provisioning_binding_digest:str; dispatch_id:str; fencing_token:str; generation:int; runtime_attestation_digest:str; read_scope:tuple[str,...]; write_scope:tuple[str,...]; test_scope:tuple[str,...]; allowed_test_commands:tuple[tuple[str,...],...]; resource_limits:SandboxResourceLimits; schema_version:str=V
    def validate(self):
        if self.schema_version!=V: raise ExecutionSandboxContractError("policy schema")
        _repo(self.repository); sha(self.baseline_sha,"baseline_sha"); sha(self.baseline_tree_sha,"baseline_tree_sha"); branch(self.branch)
        for n in ("mission_id","drone_id","executor_id","sandbox_id","workspace_id","runtime_instance_id"): text(getattr(self,n),n)
        for n in ("authority_binding_digest","runtime_binding_digest","fleet_dispatch_binding_digest","provisioning_binding_digest","dispatch_id","fencing_token","runtime_attestation_digest"): dg(getattr(self,n),n)
        if isinstance(self.generation,bool) or not isinstance(self.generation,int) or self.generation<1: raise ExecutionSandboxContractError("generation invalid")
        scope(self.read_scope,"read_scope"); scope(self.write_scope,"write_scope"); scope(self.test_scope,"test_scope")
        if type(self.allowed_test_commands) is not tuple or not self.allowed_test_commands: raise ExecutionSandboxContractError("test commands invalid")
        cmds=tuple(command(x) for x in self.allowed_test_commands)
        if len(set(cmds))!=len(cmds): raise ExecutionSandboxContractError("duplicate command")
        if type(self.resource_limits) is not SandboxResourceLimits: raise ExecutionSandboxContractError("limits type")
        self.resource_limits.validate(); return self
    def canonical_dict(self):
        self.validate(); v=asdict(self)
        for n in ("read_scope","write_scope","test_scope"): v[n]=list(getattr(self,n))
        v["allowed_test_commands"]=[list(x) for x in self.allowed_test_commands]; return v
    def digest(self): return sha256(b"LION/SANDBOX-POLICY/2\0"+canonical_json(self.canonical_dict())).hexdigest()
    def validate_bindings(self,d:FleetDispatchBinding,p:ProvisioningBinding):
        self.validate(); d.validate(); p.validate()
        if d.digest()!=self.fleet_dispatch_binding_digest or p.digest()!=self.provisioning_binding_digest: raise ExecutionSandboxContractError("binding digest mismatch")
        if (d.mission_id,d.drone_id,d.dispatch_id,d.fencing_token,d.generation,d.repository,d.baseline_sha,d.baseline_tree_sha,d.branch,d.write_scope)!=(self.mission_id,self.drone_id,self.dispatch_id,self.fencing_token,self.generation,self.repository,self.baseline_sha,self.baseline_tree_sha,self.branch,self.write_scope): raise ExecutionSandboxContractError("dispatch binding mismatch")
        if (p.mission_id,p.drone_id,p.executor_id,p.repository,p.baseline_sha,p.baseline_tree_sha,p.branch,p.read_scope,p.write_scope,p.runtime_instance_id,p.sandbox_id,p.workspace_id,p.runtime_attestation_digest)!=(self.mission_id,self.drone_id,self.executor_id,self.repository,self.baseline_sha,self.baseline_tree_sha,self.branch,self.read_scope,self.write_scope,self.runtime_instance_id,self.sandbox_id,self.workspace_id,self.runtime_attestation_digest): raise ExecutionSandboxContractError("provisioning binding mismatch")
        return self

@dataclass(frozen=True)
class SandboxOperation:
    operation_id:str; mission_id:str; drone_id:str; executor_id:str; sandbox_id:str; workspace_id:str; dispatch_id:str; fencing_token:str; generation:int; policy_digest:str; action:str; path:str; payload_digest:str|None=None; payload_size:int=0; command:tuple[str,...]=(); schema_version:str=V
    def validate(self):
        if self.schema_version!=V: raise ExecutionSandboxContractError("operation schema")
        for n in ("operation_id","mission_id","drone_id","executor_id","sandbox_id","workspace_id"): text(getattr(self,n),n)
        for n in ("dispatch_id","fencing_token","policy_digest"): dg(getattr(self,n),n)
        if isinstance(self.generation,bool) or not isinstance(self.generation,int) or self.generation<1: raise ExecutionSandboxContractError("generation invalid")
        if self.action not in ACTIONS: raise ExecutionSandboxContractError("action invalid")
        path(self.path)
        if isinstance(self.payload_size,bool) or not isinstance(self.payload_size,int) or self.payload_size<0: raise ExecutionSandboxContractError("payload size")
        if self.action=="WRITE_FILE":
            if self.payload_digest is None: raise ExecutionSandboxContractError("write digest missing")
            dg(self.payload_digest,"payload_digest")
            if self.command: raise ExecutionSandboxContractError("write command")
        elif self.action=="RUN_TEST":
            if self.payload_digest is not None or self.payload_size: raise ExecutionSandboxContractError("test payload")
            command(self.command)
        elif self.payload_digest is not None or self.payload_size or self.command: raise ExecutionSandboxContractError("read extras")
        return self
    def canonical_dict(self): self.validate(); v=asdict(self); v["command"]=list(self.command); return v
    def digest(self): return sha256(b"LION/SANDBOX-OP/2\0"+canonical_json(self.canonical_dict())).hexdigest()

@dataclass(frozen=True)
class SandboxExecutionReceipt:
    receipt_id:str; operation_id:str; operation_digest:str; policy_digest:str; authority_binding_digest:str; runtime_binding_digest:str; fleet_dispatch_binding_digest:str; provisioning_binding_digest:str; mission_id:str; drone_id:str; executor_id:str; sandbox_id:str; workspace_id:str; dispatch_id:str; fencing_token:str; generation:int; runtime_instance_id:str; runtime_attestation_digest:str; action:str; outcome:str; effect_digest:str; output_digest:str; bytes_read:int; bytes_written:int; exit_code:int|None; observed_events:tuple[str,...]; side_effect_refs:tuple[str,...]=(); schema_version:str=V
    def validate(self):
        if self.schema_version!=V: raise ExecutionSandboxContractError("receipt schema")
        for n in ("receipt_id","operation_id","mission_id","drone_id","executor_id","sandbox_id","workspace_id","runtime_instance_id"): text(getattr(self,n),n)
        for n in ("operation_digest","policy_digest","authority_binding_digest","runtime_binding_digest","fleet_dispatch_binding_digest","provisioning_binding_digest","dispatch_id","fencing_token","runtime_attestation_digest","effect_digest","output_digest"): dg(getattr(self,n),n)
        if isinstance(self.generation,bool) or not isinstance(self.generation,int) or self.generation<1 or self.action not in ACTIONS or self.outcome not in OUTCOMES: raise ExecutionSandboxContractError("receipt binding")
        for n in ("bytes_read","bytes_written"):
            v=getattr(self,n)
            if isinstance(v,bool) or not isinstance(v,int) or v<0: raise ExecutionSandboxContractError("receipt bytes")
        if type(self.observed_events) is not tuple or not self.observed_events or len(set(self.observed_events))!=len(self.observed_events) or type(self.side_effect_refs) is not tuple or len(set(self.side_effect_refs))!=len(self.side_effect_refs): raise ExecutionSandboxContractError("receipt evidence")
        if self.action!="WRITE_FILE" and self.bytes_written or self.action!="READ_FILE" and self.bytes_read: raise ExecutionSandboxContractError("receipt byte/action")
        if self.action=="RUN_TEST" and self.exit_code is None or self.action!="RUN_TEST" and self.exit_code is not None: raise ExecutionSandboxContractError("receipt exit")
        return self
    def canonical_dict(self): self.validate(); v=asdict(self); v["observed_events"]=list(self.observed_events); v["side_effect_refs"]=list(self.side_effect_refs); return v
    def digest(self): return sha256(b"LION/SANDBOX-RECEIPT/2\0"+canonical_json(self.canonical_dict())).hexdigest()

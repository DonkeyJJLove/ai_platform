"""Fleet-bound fail-closed sandbox PEP (F005-C R2)."""
from __future__ import annotations
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3
import stat
from threading import Lock
from typing import Protocol
from cyber_lion.contracts.executor_sandbox import ExecutionSandboxContractError,ExecutionSandboxPolicy,FleetDispatchBinding,ProvisioningBinding,SandboxExecutionReceipt,SandboxOperation,SandboxRuntimeBinding,path_within_scope
class SandboxEnforcementError(ValueError): pass
@dataclass(frozen=True)
class SandboxBackendReadResult: data:bytes; observed_event_ref:str
@dataclass(frozen=True)
class SandboxBackendWriteResult: observed_content_digest:str; observed_event_ref:str; side_effect_ref:str
@dataclass(frozen=True)
class SandboxBackendTestResult: exit_code:int; stdout:bytes; stderr:bytes; observed_event_ref:str; side_effect_refs:tuple[str,...]=()
class SandboxBackend(Protocol):
    backend_id:str; backend_identity_digest:str; backend_implementation_digest:str; sandbox_id:str; workspace_id:str
    def read_file(self,path:str)->SandboxBackendReadResult:...
    def write_file(self,path:str,payload:bytes)->SandboxBackendWriteResult:...
    def run_test(self,path:str,command:tuple[str,...])->SandboxBackendTestResult:...
class SandboxReplayGuard(Protocol):
    def consume(self,mission_id:str,operation_id:str)->bool:...
class FleetDispatchSource(Protocol):
    def current_dispatch(self,mission_id:str)->FleetDispatchBinding:...
class InMemorySandboxReplayGuard:
    def __init__(self): self._lock=Lock(); self._seen=set()
    def consume(self,m,o):
        with self._lock:
            if (m,o) in self._seen:return False
            self._seen.add((m,o));return True


_SANDBOX_STATE_SCHEMA="lion.executor-sandbox-state/v1"


def _sandbox_state_path(value:Path|str)->Path:
    path=Path(value)
    if not path.is_absolute():raise SandboxEnforcementError("sandbox state path must be absolute")
    parent=path.parent.resolve(strict=True)
    if not parent.is_dir():raise SandboxEnforcementError("sandbox state parent unavailable")
    if path.exists() and path.is_symlink():raise SandboxEnforcementError("sandbox state symlink denied")
    return path


def _sandbox_state_identity(path:Path)->tuple[int,int]:
    try:st=path.stat()
    except OSError as exc:raise SandboxEnforcementError("sandbox state unavailable") from exc
    if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1:raise SandboxEnforcementError("sandbox state must be private regular file")
    return (st.st_dev,st.st_ino)


def _check_sandbox_state_identity(path:Path,expected:tuple[int,int])->None:
    if path.is_symlink() or _sandbox_state_identity(path)!=expected:raise SandboxEnforcementError("sandbox state identity drift")


class SQLiteSandboxReplayGuard:
    """Durable per-mission operation replay fence."""
    def __init__(self,path:Path|str):
        self.path=_sandbox_state_path(path)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("""CREATE TABLE IF NOT EXISTS sandbox_replay(
              mission_id TEXT NOT NULL,
              operation_id TEXT NOT NULL,
              consumed_at TEXT NOT NULL,
              schema_id TEXT NOT NULL,
              PRIMARY KEY(mission_id,operation_id)
            )""")
        self._db_identity=_sandbox_state_identity(self.path)

    def consume(self,mission_id:str,operation_id:str)->bool:
        for value,label in ((mission_id,"mission"),(operation_id,"operation")):
            if not isinstance(value,str) or not value.strip() or "\x00" in value:raise SandboxEnforcementError(f"sandbox replay {label} invalid")
        _check_sandbox_state_identity(self.path,self._db_identity)
        try:
            with closing(sqlite3.connect(self.path,timeout=5,isolation_level=None)) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute("INSERT INTO sandbox_replay VALUES(?,?,?,?)",
                               (mission_id,operation_id,datetime.now(timezone.utc).isoformat(),_SANDBOX_STATE_SCHEMA))
                    db.execute("COMMIT")
                except Exception:
                    if db.in_transaction:db.execute("ROLLBACK")
                    raise
            return True
        except sqlite3.IntegrityError:return False
        except sqlite3.Error as exc:raise SandboxEnforcementError("sandbox replay state unavailable") from exc


@dataclass(frozen=True)
class SandboxBudgetSnapshot: operations:int; write_bytes:int; test_runs:int
class SandboxBudgetLedger:
    def __init__(self,p): p.validate();self._l=p.resource_limits;self._lock=Lock();self._o=self._w=self._t=0
    def reserve(self,op):
        with self._lock:
            o=self._o+1;w=self._w+(op.payload_size if op.action=="WRITE_FILE" else 0);t=self._t+(op.action=="RUN_TEST")
            if o>self._l.max_operations or w>self._l.max_write_bytes or t>self._l.max_test_runs: raise SandboxEnforcementError("sandbox budget exhausted")
            self._o,self._w,self._t=o,w,t
    def snapshot(self):
        with self._lock:return SandboxBudgetSnapshot(self._o,self._w,self._t)


class SQLiteSandboxBudgetLedger:
    """Durable monotonic sandbox budget keyed by exact ExecutionSandboxPolicy digest."""
    def __init__(self,policy:ExecutionSandboxPolicy,path:Path|str):
        if type(policy) is not ExecutionSandboxPolicy:raise SandboxEnforcementError("exact sandbox policy required")
        policy.validate();self._p=policy;self._l=policy.resource_limits;self.path=_sandbox_state_path(path);self._digest=policy.digest()
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("""CREATE TABLE IF NOT EXISTS sandbox_budget(
              policy_digest TEXT PRIMARY KEY,
              operations INTEGER NOT NULL,
              write_bytes INTEGER NOT NULL,
              test_runs INTEGER NOT NULL,
              schema_id TEXT NOT NULL
            )""")
            db.execute("INSERT OR IGNORE INTO sandbox_budget VALUES(?,?,?,?,?)",
                       (self._digest,0,0,0,_SANDBOX_STATE_SCHEMA))
        self._db_identity=_sandbox_state_identity(self.path)

    def _row(self,db):
        row=db.execute("SELECT operations,write_bytes,test_runs,schema_id FROM sandbox_budget WHERE policy_digest=?",(self._digest,)).fetchone()
        if row is None or row[3]!=_SANDBOX_STATE_SCHEMA:raise SandboxEnforcementError("sandbox budget state unavailable")
        return row

    def reserve(self,op):
        if type(op) is not SandboxOperation:raise SandboxEnforcementError("sandbox budget operation type")
        op.validate()
        if op.policy_digest!=self._digest:raise SandboxEnforcementError("sandbox budget policy substitution")
        _check_sandbox_state_identity(self.path,self._db_identity)
        try:
            with closing(sqlite3.connect(self.path,timeout=5,isolation_level=None)) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    cur=self._row(db);o=int(cur[0])+1;w=int(cur[1])+(op.payload_size if op.action=="WRITE_FILE" else 0);t=int(cur[2])+(op.action=="RUN_TEST")
                    if o>self._l.max_operations or w>self._l.max_write_bytes or t>self._l.max_test_runs:
                        db.execute("ROLLBACK");raise SandboxEnforcementError("sandbox budget exhausted")
                    db.execute("UPDATE sandbox_budget SET operations=?,write_bytes=?,test_runs=? WHERE policy_digest=?",(o,w,t,self._digest))
                    db.execute("COMMIT")
                except Exception:
                    if db.in_transaction:db.execute("ROLLBACK")
                    raise
        except SandboxEnforcementError:raise
        except sqlite3.Error as exc:raise SandboxEnforcementError("sandbox budget state unavailable") from exc

    def snapshot(self):
        _check_sandbox_state_identity(self.path,self._db_identity)
        try:
            with closing(sqlite3.connect(self.path,timeout=5)) as db:
                row=self._row(db)
            return SandboxBudgetSnapshot(int(row[0]),int(row[1]),int(row[2]))
        except SandboxEnforcementError:raise
        except sqlite3.Error as exc:raise SandboxEnforcementError("sandbox budget state unavailable") from exc


@dataclass(frozen=True)
class SandboxExecutionResult: receipt:SandboxExecutionReceipt; output:bytes
class ExecutorSandbox:
    def __init__(self,*,policy:ExecutionSandboxPolicy,runtime_binding:SandboxRuntimeBinding,fleet_dispatch:FleetDispatchBinding,provisioning_binding:ProvisioningBinding,dispatch_source:FleetDispatchSource,backend:SandboxBackend,replay_guard:SandboxReplayGuard,budget_ledger:SandboxBudgetLedger|None=None):
        try: policy.validate_bindings(fleet_dispatch,provisioning_binding);runtime_binding.validate()
        except ExecutionSandboxContractError as e: raise SandboxEnforcementError("sandbox configuration invalid") from e
        if runtime_binding.digest()!=policy.runtime_binding_digest or (runtime_binding.sandbox_id,runtime_binding.workspace_id)!=(policy.sandbox_id,policy.workspace_id): raise SandboxEnforcementError("runtime binding mismatch")
        actual=tuple(getattr(backend,n,None) for n in ("backend_id","backend_identity_digest","backend_implementation_digest","sandbox_id","workspace_id")); expected=(runtime_binding.backend_id,runtime_binding.backend_identity_digest,runtime_binding.backend_implementation_digest,runtime_binding.sandbox_id,runtime_binding.workspace_id)
        if actual!=expected or not hasattr(dispatch_source,"current_dispatch") or not hasattr(replay_guard,"consume"): raise SandboxEnforcementError("sandbox composition mismatch")
        self._p=policy;self._r=runtime_binding;self._d=fleet_dispatch;self._pr=provisioning_binding;self._src=dispatch_source;self._b=backend;self._g=replay_guard;self._budget=budget_ledger or SandboxBudgetLedger(policy);self._lock=Lock();self._closed=False
    @property
    def policy_digest(self):return self._p.digest()
    def close(self):
        with self._lock:self._closed=True
    def budget_snapshot(self):return self._budget.snapshot()
    def execute(self,op:SandboxOperation,*,payload:bytes=b""):
        self._ensure_open();self._current();self._validate_op(op,payload);self._scope(op)
        try: consumed=self._g.consume(op.mission_id,op.operation_id)
        except Exception as e: raise SandboxEnforcementError("replay guard failed closed") from e
        if consumed is not True: raise SandboxEnforcementError("operation replay denied")
        self._budget.reserve(op)
        try:
            if op.action=="READ_FILE":return self._read(op)
            if op.action=="WRITE_FILE":return self._write(op,payload)
            return self._test(op)
        except Exception:return self._aborted(op)
    def _ensure_open(self):
        with self._lock:
            if self._closed:raise SandboxEnforcementError("sandbox closed")
    def _current(self):
        try:c=self._src.current_dispatch(self._p.mission_id);c.validate()
        except Exception as e:raise SandboxEnforcementError("current dispatch unavailable") from e
        if c.digest()!=self._p.fleet_dispatch_binding_digest or (c.dispatch_id,c.fencing_token,c.generation,c.drone_id,c.mission_id,c.repository,c.baseline_sha,c.baseline_tree_sha,c.branch,c.write_scope)!=(self._p.dispatch_id,self._p.fencing_token,self._p.generation,self._p.drone_id,self._p.mission_id,self._p.repository,self._p.baseline_sha,self._p.baseline_tree_sha,self._p.branch,self._p.write_scope):raise SandboxEnforcementError("stale or substituted fleet dispatch denied")
    def _validate_op(self,op,payload):
        if type(op) is not SandboxOperation:raise SandboxEnforcementError("operation type")
        try:op.validate()
        except ExecutionSandboxContractError as e:raise SandboxEnforcementError("operation contract") from e
        if (op.mission_id,op.drone_id,op.executor_id,op.sandbox_id,op.workspace_id,op.dispatch_id,op.fencing_token,op.generation,op.policy_digest)!=(self._p.mission_id,self._p.drone_id,self._p.executor_id,self._p.sandbox_id,self._p.workspace_id,self._p.dispatch_id,self._p.fencing_token,self._p.generation,self._p.digest()):raise SandboxEnforcementError("operation binding mismatch")
        if not isinstance(payload,bytes):raise SandboxEnforcementError("payload type")
        if op.action=="WRITE_FILE" and (len(payload)!=op.payload_size or sha256(payload).hexdigest()!=op.payload_digest):raise SandboxEnforcementError("payload binding mismatch")
        if op.action!="WRITE_FILE" and payload:raise SandboxEnforcementError("unexpected payload")
    def _scope(self,op):
        s=self._p.read_scope if op.action=="READ_FILE" else self._p.write_scope if op.action=="WRITE_FILE" else self._p.test_scope
        if op.action=="RUN_TEST" and op.command not in self._p.allowed_test_commands:raise SandboxEnforcementError("test command not allowlisted")
        if not path_within_scope(op.path,s):raise SandboxEnforcementError("path outside scope")
    def _read(self,op):
        x=self._b.read_file(op.path)
        if type(x) is not SandboxBackendReadResult or not isinstance(x.data,bytes) or not x.observed_event_ref or len(x.data)>self._p.resource_limits.max_output_bytes:raise SandboxEnforcementError("read observation invalid")
        h=sha256(x.data).hexdigest();return SandboxExecutionResult(self._receipt(op,"SUCCEEDED",h,h,len(x.data),0,None,(x.observed_event_ref,)),x.data)
    def _write(self,op,payload):
        x=self._b.write_file(op.path,payload)
        if type(x) is not SandboxBackendWriteResult or x.observed_content_digest!=op.payload_digest or not x.observed_event_ref or not x.side_effect_ref:raise SandboxEnforcementError("write observation invalid")
        z=sha256(b"").hexdigest();return SandboxExecutionResult(self._receipt(op,"SUCCEEDED",x.observed_content_digest,z,0,len(payload),None,(x.observed_event_ref,),(x.side_effect_ref,)),b"")
    def _test(self,op):
        x=self._b.run_test(op.path,op.command)
        if type(x) is not SandboxBackendTestResult or isinstance(x.exit_code,bool) or not isinstance(x.exit_code,int) or not isinstance(x.stdout,bytes) or not isinstance(x.stderr,bytes) or not x.observed_event_ref or type(x.side_effect_refs) is not tuple:raise SandboxEnforcementError("test observation invalid")
        out=x.stdout+x.stderr
        if len(out)>self._p.resource_limits.max_output_bytes:raise SandboxEnforcementError("test output budget")
        oh=sha256(out).hexdigest();eh=sha256(b"LION/SANDBOX-TEST/2\0"+str(x.exit_code).encode()+b"\0"+oh.encode()).hexdigest();return SandboxExecutionResult(self._receipt(op,"SUCCEEDED" if x.exit_code==0 else "FAILED",eh,oh,0,0,x.exit_code,(x.observed_event_ref,),x.side_effect_refs),out)
    def _aborted(self,op):
        z=sha256(b"").hexdigest();e=sha256(b"LION/SANDBOX-UNKNOWN/2\0"+op.digest().encode()).hexdigest();return SandboxExecutionResult(self._receipt(op,"ABORTED",e,z,0,0,-1 if op.action=="RUN_TEST" else None,(f"sandbox:{self._p.sandbox_id}:operation:{op.operation_id}:aborted",)),b"")
    def _receipt(self,op,outcome,effect,output,br,bw,exit_code,events,refs=()):
        r=SandboxExecutionReceipt(f"{self._p.sandbox_id}:{op.operation_id}",op.operation_id,op.digest(),self._p.digest(),self._p.authority_binding_digest,self._r.digest(),self._p.fleet_dispatch_binding_digest,self._p.provisioning_binding_digest,self._p.mission_id,self._p.drone_id,self._p.executor_id,self._p.sandbox_id,self._p.workspace_id,self._p.dispatch_id,self._p.fencing_token,self._p.generation,self._p.runtime_instance_id,self._p.runtime_attestation_digest,op.action,outcome,effect,output,br,bw,exit_code,events,refs);r.validate();return r

"""F009 admission-bound runtime execution by composition over the existing sandbox PEP.

The engine consumes one canonical current RuntimeAdmission before invoking the bounded
sandbox. It never mints authority and treats unknown or partial effects as non-success.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import stat
from threading import Lock
from typing import Protocol

from cyber_lion.contracts.executor_sandbox import SandboxExecutionReceipt,SandboxOperation
from cyber_lion.contracts.runtime_enforcement import RequestedRuntimeEffect,RuntimeAdmission,RuntimeIdentityBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding,RuntimeExecutionReceipt,RuntimeExecutionRequest
from .executor_sandbox import SandboxExecutionResult

class RuntimeExecutionError(RuntimeError):pass

class RuntimeAdmissionSource(Protocol):
    source_id:str;source_instance_id:str;implementation_digest:str;trust_anchor_id:str;trust_anchor_digest:str
    def resolve(self,admission_digest:str)->RuntimeAdmission:...
    def is_current(self,admission_digest:str)->bool:...

class AdmissionConsumptionGuard(Protocol):
    def consume(self,admission_digest:str,execution_id:str)->bool:...

class InMemoryAdmissionConsumptionGuard:
    def __init__(self):self._lock=Lock();self._seen:set[str]=set()
    def consume(self,admission_digest:str,execution_id:str)->bool:
        with self._lock:
            if admission_digest in self._seen:return False
            self._seen.add(admission_digest);return True


_RUNTIME_STATE_SCHEMA="lion.runtime-execution-state/v1"


def _sqlite_state_path(value:Path|str)->Path:
    path=Path(value)
    if not path.is_absolute():raise RuntimeExecutionError("runtime state path must be absolute")
    parent=path.parent.resolve(strict=True)
    if not parent.is_dir():raise RuntimeExecutionError("runtime state parent unavailable")
    if path.exists() and path.is_symlink():raise RuntimeExecutionError("runtime state symlink denied")
    return path


def _runtime_state_identity(path:Path)->tuple[int,int]:
    try:st=path.stat()
    except OSError as exc:raise RuntimeExecutionError("runtime state unavailable") from exc
    if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1:raise RuntimeExecutionError("runtime state must be private regular file")
    return (st.st_dev,st.st_ino)


def _check_runtime_state_identity(path:Path,expected:tuple[int,int])->None:
    if path.is_symlink() or _runtime_state_identity(path)!=expected:raise RuntimeExecutionError("runtime state identity drift")


def _zoned_text(value:datetime|str)->str:
    if isinstance(value,datetime):
        if value.tzinfo is None:raise RuntimeExecutionError("runtime state timestamp must be zoned")
        return value.astimezone(timezone.utc).isoformat()
    if not isinstance(value,str) or not value:raise RuntimeExecutionError("runtime state timestamp required")
    try:parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:raise RuntimeExecutionError("runtime state timestamp invalid") from exc
    if parsed.tzinfo is None:raise RuntimeExecutionError("runtime state timestamp must be zoned")
    return parsed.astimezone(timezone.utc).isoformat()


def _strict_runtime_admission(raw:str)->RuntimeAdmission:
    def unique(pairs):
        out={}
        for key,value in pairs:
            if key in out:raise RuntimeExecutionError("duplicate runtime admission JSON key")
            out[key]=value
        return out
    try:value=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:( _ for _ in ()).throw(RuntimeExecutionError("nonfinite runtime admission JSON")))
    except (TypeError,ValueError,json.JSONDecodeError,UnicodeError) as exc:
        if isinstance(exc,RuntimeExecutionError):raise
        raise RuntimeExecutionError("runtime admission record corrupt") from exc
    if type(value) is not dict:raise RuntimeExecutionError("runtime admission record invalid")
    try:return RuntimeAdmission(**value).validate()
    except Exception as exc:raise RuntimeExecutionError("runtime admission record invalid") from exc


class SQLiteRuntimeAdmissionSource:
    """Immutable durable RuntimeAdmission source; storage never issues authority.

    The trusted composition supplies an independent RuntimeAdmissionSourceTrustBinding.
    publish() accepts only an already-sealed RuntimeAdmission plus independent provenance
    digest. It cannot construct a PDP decision, LiveAdmittedAuthority or RuntimeAdmission.
    """
    def __init__(self,path:Path|str,trust:RuntimeAdmissionSourceTrustBinding):
        if type(trust) is not RuntimeAdmissionSourceTrustBinding:raise RuntimeExecutionError("exact admission source trust binding required")
        trust.validate();self.path=_sqlite_state_path(path)
        self.source_id=trust.source_id;self.source_instance_id=trust.source_instance_id
        self.implementation_digest=trust.source_implementation_digest
        self.trust_anchor_id=trust.trust_anchor_id;self.trust_anchor_digest=trust.trust_anchor_digest
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("""CREATE TABLE IF NOT EXISTS runtime_admissions(
              admission_digest TEXT PRIMARY KEY,
              admission_json TEXT NOT NULL,
              provenance_digest TEXT NOT NULL,
              published_at TEXT NOT NULL,
              schema_id TEXT NOT NULL
            )""")
        self._db_identity=_runtime_state_identity(self.path)

    def publish(self,admission:RuntimeAdmission,*,provenance_digest:str,published_at:datetime|str)->str:
        if type(admission) is not RuntimeAdmission:raise RuntimeExecutionError("exact RuntimeAdmission required")
        admission.validate()
        if not isinstance(provenance_digest,str) or len(provenance_digest)!=64 or any(c not in "0123456789abcdef" for c in provenance_digest):
            raise RuntimeExecutionError("runtime admission provenance digest invalid")
        stamp=_zoned_text(published_at)
        raw=json.dumps(asdict(admission),sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
        _check_runtime_state_identity(self.path,self._db_identity)
        try:
            with closing(sqlite3.connect(self.path,timeout=5,isolation_level=None)) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute("INSERT INTO runtime_admissions VALUES(?,?,?,?,?)",
                               (admission.admission_digest,raw,provenance_digest,stamp,_RUNTIME_STATE_SCHEMA))
                    db.execute("COMMIT")
                except Exception:
                    if db.in_transaction:db.execute("ROLLBACK")
                    raise
        except sqlite3.IntegrityError as exc:
            raise RuntimeExecutionError("runtime admission publication replay denied") from exc
        return admission.admission_digest

    def resolve(self,admission_digest:str)->RuntimeAdmission:
        if not isinstance(admission_digest,str) or len(admission_digest)!=64 or any(c not in "0123456789abcdef" for c in admission_digest):
            raise RuntimeExecutionError("runtime admission digest invalid")
        _check_runtime_state_identity(self.path,self._db_identity)
        try:
            with closing(sqlite3.connect(self.path,timeout=5)) as db:
                rows=db.execute("SELECT admission_json,provenance_digest,published_at,schema_id FROM runtime_admissions WHERE admission_digest=?",(admission_digest,)).fetchall()
        except sqlite3.Error as exc:raise RuntimeExecutionError("runtime admission source unavailable") from exc
        if len(rows)!=1 or rows[0][3]!=_RUNTIME_STATE_SCHEMA:raise RuntimeExecutionError("runtime admission unavailable or ambiguous")
        provenance,stamp=rows[0][1],rows[0][2]
        if not isinstance(provenance,str) or len(provenance)!=64 or any(c not in "0123456789abcdef" for c in provenance):
            raise RuntimeExecutionError("runtime admission provenance corrupt")
        _zoned_text(stamp)
        value=_strict_runtime_admission(rows[0][0])
        if value.admission_digest!=admission_digest:raise RuntimeExecutionError("runtime admission source digest substitution")
        return value

    def is_current(self,admission_digest:str)->bool:
        try:return self.resolve(admission_digest).admission_digest==admission_digest
        except RuntimeExecutionError:return False


class SQLiteAdmissionConsumptionGuard:
    """Durable exactly-once RuntimeAdmission consumption across process restarts."""
    def __init__(self,path:Path|str):
        self.path=_sqlite_state_path(path)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("""CREATE TABLE IF NOT EXISTS runtime_admission_consumption(
              admission_digest TEXT PRIMARY KEY,
              execution_id TEXT NOT NULL UNIQUE,
              consumed_at TEXT NOT NULL,
              schema_id TEXT NOT NULL
            )""")
        self._db_identity=_runtime_state_identity(self.path)

    def consume(self,admission_digest:str,execution_id:str)->bool:
        if not isinstance(admission_digest,str) or len(admission_digest)!=64 or any(c not in "0123456789abcdef" for c in admission_digest):
            raise RuntimeExecutionError("admission consumption digest invalid")
        if not isinstance(execution_id,str) or not execution_id.strip() or "\x00" in execution_id:
            raise RuntimeExecutionError("admission consumption execution identity invalid")
        stamp=datetime.now(timezone.utc).isoformat()
        _check_runtime_state_identity(self.path,self._db_identity)
        try:
            with closing(sqlite3.connect(self.path,timeout=5,isolation_level=None)) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute("INSERT INTO runtime_admission_consumption VALUES(?,?,?,?)",
                               (admission_digest,execution_id,stamp,_RUNTIME_STATE_SCHEMA))
                    db.execute("COMMIT")
                except Exception:
                    if db.in_transaction:db.execute("ROLLBACK")
                    raise
            return True
        except sqlite3.IntegrityError:
            return False
        except sqlite3.Error as exc:
            raise RuntimeExecutionError("admission consumption state unavailable") from exc


class SandboxExecutor(Protocol):
    @property
    def policy_digest(self)->str:...
    def execute(self,op:SandboxOperation,*,payload:bytes=b"")->SandboxExecutionResult:...

class RuntimeExecutionEngine:
    def __init__(self,*,admission_source:RuntimeAdmissionSource,admission_source_trust:RuntimeAdmissionSourceTrustBinding,consumption_guard:AdmissionConsumptionGuard,sandbox:SandboxExecutor):
        if type(admission_source_trust) is not RuntimeAdmissionSourceTrustBinding:raise RuntimeExecutionError("exact admission source trust binding required")
        admission_source_trust.validate()
        actual=(getattr(admission_source,"source_id",None),getattr(admission_source,"source_instance_id",None),getattr(admission_source,"implementation_digest",None),getattr(admission_source,"trust_anchor_id",None),getattr(admission_source,"trust_anchor_digest",None))
        if actual!=admission_source_trust.binding():raise RuntimeExecutionError("runtime admission source substitution denied")
        if not callable(getattr(admission_source,"resolve",None)) or not callable(getattr(admission_source,"is_current",None)):raise RuntimeExecutionError("runtime admission source unavailable")
        if not callable(getattr(consumption_guard,"consume",None)):raise RuntimeExecutionError("admission consumption guard unavailable")
        if not callable(getattr(sandbox,"execute",None)) or not isinstance(getattr(sandbox,"policy_digest",None),str):raise RuntimeExecutionError("bounded sandbox unavailable")
        self._source=admission_source;self._trust=admission_source_trust;self._consume=consumption_guard;self._sandbox=sandbox

    def _canonical_admission(self,admission:RuntimeAdmission)->RuntimeAdmission:
        try:admission.validate();canonical=self._source.resolve(admission.admission_digest)
        except Exception as exc:raise RuntimeExecutionError("canonical runtime admission unavailable") from exc
        if type(canonical) is not RuntimeAdmission:raise RuntimeExecutionError("canonical admission source returned invalid type")
        try:canonical.validate()
        except Exception as exc:raise RuntimeExecutionError("canonical runtime admission invalid") from exc
        if canonical.admission_digest!=admission.admission_digest or canonical!=admission:raise RuntimeExecutionError("forged or substituted RuntimeAdmission denied")
        try:current=self._source.is_current(admission.admission_digest)
        except Exception as exc:raise RuntimeExecutionError("runtime admission currentness unavailable") from exc
        if current is not True:raise RuntimeExecutionError("stale RuntimeAdmission denied")
        return canonical

    @staticmethod
    def _validate_bindings(admission:RuntimeAdmission,request:RuntimeExecutionRequest,effect:RequestedRuntimeEffect,identity:RuntimeIdentityBinding,payload:bytes)->None:
        try:request.validate();effect.validate();identity.validate()
        except Exception as exc:raise RuntimeExecutionError("runtime execution input invalid") from exc
        if request.admission_digest!=admission.admission_digest:raise RuntimeExecutionError("execution request admission substitution denied")
        if request.requested_effect_digest!=admission.requested_effect_digest or effect.digest()!=admission.requested_effect_digest:raise RuntimeExecutionError("admission effect substitution denied")
        if request.runtime_identity_digest!=admission.runtime_identity_digest or identity.digest()!=admission.runtime_identity_digest:raise RuntimeExecutionError("runtime identity substitution denied")
        if request.provisioned_executor_digest!=admission.provisioned_executor_digest or identity.provisioned_executor_digest!=admission.provisioned_executor_digest:raise RuntimeExecutionError("provisioned executor substitution denied")
        if request.mission_id!=effect.mission_id:raise RuntimeExecutionError("mission binding mismatch")
        if (request.runtime_instance_id,request.sandbox_id,request.workspace_id)!=(identity.runtime_instance_id,identity.sandbox_id,identity.workspace_id):raise RuntimeExecutionError("runtime/sandbox/workspace binding mismatch")
        if request.executor_id!=identity.execution_subject:raise RuntimeExecutionError("execution subject binding mismatch")
        if (request.action,request.resource)!=(effect.action_class,effect.resource):raise RuntimeExecutionError("action or resource substitution denied")
        if request.payload_digest!=effect.payload_digest:raise RuntimeExecutionError("payload digest substitution denied")
        if not isinstance(payload,bytes):raise RuntimeExecutionError("payload type invalid")
        if request.action=="WRITE_FILE":
            if len(payload)!=request.payload_size or sha256(payload).hexdigest()!=request.payload_digest:raise RuntimeExecutionError("write payload binding mismatch")
        elif payload or request.payload_size:raise RuntimeExecutionError("unexpected payload for non-write operation")

    def execute(self,*,admission:RuntimeAdmission,request:RuntimeExecutionRequest,effect:RequestedRuntimeEffect,runtime_identity:RuntimeIdentityBinding,payload:bytes=b"")->RuntimeExecutionReceipt:
        canonical=self._canonical_admission(admission)
        self._validate_bindings(canonical,request,effect,runtime_identity,payload)
        op=SandboxOperation(operation_id=request.execution_id,mission_id=request.mission_id,drone_id=runtime_identity.workload_identity,executor_id=request.executor_id,sandbox_id=request.sandbox_id,workspace_id=request.workspace_id,dispatch_id=request.dispatch_id,fencing_token=request.fencing_token,generation=request.generation,policy_digest=self._sandbox.policy_digest,action=request.action,path=request.resource,payload_digest=request.payload_digest if request.action=="WRITE_FILE" else None,payload_size=request.payload_size,command=request.command).validate()
        try:consumed=self._consume.consume(canonical.admission_digest,request.execution_id)
        except Exception as exc:raise RuntimeExecutionError("admission consumption state unavailable") from exc
        if consumed is not True:raise RuntimeExecutionError("RuntimeAdmission replay denied")
        try:result=self._sandbox.execute(op,payload=payload)
        except Exception as exc:raise RuntimeExecutionError("bounded sandbox execution failed before trustworthy receipt") from exc
        if type(result) is not SandboxExecutionResult or type(result.receipt) is not SandboxExecutionReceipt:raise RuntimeExecutionError("sandbox returned invalid execution result")
        receipt=result.receipt
        try:receipt.validate()
        except Exception as exc:raise RuntimeExecutionError("sandbox execution receipt invalid") from exc
        expected=(op.operation_id,op.digest(),self._sandbox.policy_digest,request.mission_id,request.executor_id,request.sandbox_id,request.workspace_id,request.dispatch_id,request.fencing_token,request.generation,request.runtime_instance_id,request.action)
        actual=(receipt.operation_id,receipt.operation_digest,receipt.policy_digest,receipt.mission_id,receipt.executor_id,receipt.sandbox_id,receipt.workspace_id,receipt.dispatch_id,receipt.fencing_token,receipt.generation,receipt.runtime_instance_id,receipt.action)
        if actual!=expected:raise RuntimeExecutionError("sandbox receipt binding mismatch")
        if not receipt.observed_events:raise RuntimeExecutionError("effect observation missing")
        if request.action=="WRITE_FILE" and receipt.outcome=="SUCCEEDED" and (receipt.effect_digest!=request.payload_digest or not receipt.side_effect_refs):raise RuntimeExecutionError("successful write lacks exact observed effect binding")
        effect_state="OBSERVED"
        if receipt.outcome=="ABORTED":effect_state="PARTIAL_UNKNOWN" if receipt.side_effect_refs else "UNKNOWN"
        if receipt.outcome=="SUCCEEDED" and effect_state!="OBSERVED":raise RuntimeExecutionError("unknown effect cannot succeed")
        sr_digest=receipt.digest()
        return RuntimeExecutionReceipt(receipt_id="runtime-execution:"+sha256((canonical.admission_digest+request.digest()+sr_digest).encode("ascii")).hexdigest(),execution_id=request.execution_id,admission_digest=canonical.admission_digest,request_digest=request.digest(),sandbox_receipt_digest=sr_digest,operation_digest=op.digest(),mission_id=request.mission_id,executor_id=request.executor_id,runtime_instance_id=request.runtime_instance_id,sandbox_id=request.sandbox_id,workspace_id=request.workspace_id,dispatch_id=request.dispatch_id,fencing_token=request.fencing_token,generation=request.generation,action=request.action,resource=request.resource,payload_digest=request.payload_digest,outcome=receipt.outcome,effect_state=effect_state,effect_digest=receipt.effect_digest,observed_events=receipt.observed_events,side_effect_refs=receipt.side_effect_refs).sealed()

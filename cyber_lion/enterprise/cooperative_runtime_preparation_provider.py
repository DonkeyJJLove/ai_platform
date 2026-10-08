"""Durable process-side provider for one cooperative runtime preparation.

R6.21 composes R6.20 with the existing SQLiteRuntimeAdmissionSource.  It does
not issue authority, evaluate PDP, provision an executor or execute an artifact.

The provider journals preparation in the same private runtime-state SQLite file:

    PREPARING -> PREPARED -> PUBLISHED

PREPARED contains the already-sealed RuntimeAdmission returned by the existing
RuntimeAdmissionEngine.  This allows restart recovery after admission issuance
without replaying admission.  A crash after replay consumption but before the
PREPARED record is durable remains ADMISSION_ISSUANCE_UNKNOWN and is never
automatically retried.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import stat
from threading import RLock
from typing import Any, Callable, Mapping

from cyber_lion.contracts.runtime_enforcement import RuntimeAdmission
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.cooperative_runtime_composition import CooperativeRuntimeContext
from cyber_lion.enterprise.cooperative_runtime_preparer import (
    CooperativeRuntimePreparationEvidence,
    CooperativeRuntimePreparationError,
    PreparedCooperativeContextSource,
    prepare_cooperative_runtime_context,
    reconstruct_cooperative_runtime_context,
    validate_cooperative_runtime_preparation_inputs,
)
from cyber_lion.enterprise.runtime_enforcement import RuntimeAdmissionEngine
from cyber_lion.enterprise.runtime_execution import (
    RuntimeExecutionError,
    SQLiteRuntimeAdmissionSource,
)

SCHEMA_ID="lion.cooperative-runtime-preparation-provider/v1"
JOURNAL_SCHEMA="lion.cooperative-runtime-preparation-journal/v1"
PREPARING="PREPARING"
PREPARED="PREPARED"
PUBLISHED="PUBLISHED"
UNKNOWN="ADMISSION_ISSUANCE_UNKNOWN"
_PROVENANCE_DOMAIN=b"LION/COOPERATIVE-RUNTIME-PREPARATION-PROVENANCE/1\0"


class CooperativeRuntimePreparationProviderError(RuntimeError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CooperativeRuntimePreparationProviderError(reason)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False
    ).encode("utf-8")


def _direct_file(value: str|Path, label: str) -> Path:
    path=Path(value)
    _require(path.is_absolute() and path.is_file() and not path.is_symlink(),label)
    resolved=path.resolve(strict=True)
    _require(path==resolved,label+" symlink indirection")
    st=resolved.stat()
    _require(stat.S_ISREG(st.st_mode) and st.st_nlink==1,label+" regular file")
    return resolved


def _file_identity(path: Path) -> tuple[int,int]:
    st=path.stat()
    return st.st_dev,st.st_ino


def _zoned(value: datetime, label: str) -> datetime:
    _require(type(value) is datetime and value.tzinfo is not None,label)
    return value.astimezone(timezone.utc)


def _strict_admission(raw: str) -> RuntimeAdmission:
    def unique(pairs):
        out={}
        for key,value in pairs:
            if key in out:
                raise CooperativeRuntimePreparationProviderError("duplicate admission journal key")
            out[key]=value
        return out
    try:
        value=json.loads(raw,object_pairs_hook=unique,
                         parse_constant=lambda _:( _ for _ in ()).throw(
                             CooperativeRuntimePreparationProviderError("nonfinite admission journal")))
    except Exception as exc:
        if isinstance(exc,CooperativeRuntimePreparationProviderError):
            raise
        raise CooperativeRuntimePreparationProviderError("invalid admission journal") from exc
    _require(type(value) is dict,"admission journal object")
    try:
        return RuntimeAdmission(**value).validate()
    except Exception as exc:
        raise CooperativeRuntimePreparationProviderError("admission journal record invalid") from exc


class CooperativeRuntimePreparationProvider:
    """Prepare/persist/recover one exact context per HELD assignment."""

    def __init__(
        self,*,
        mission_db: str|Path,
        artifact_root: str|Path,
        evidence_source: Callable[[str],CooperativeRuntimePreparationEvidence],
        admission_engine: RuntimeAdmissionEngine,
        admission_source: SQLiteRuntimeAdmissionSource,
        now_fn: Callable[[],datetime]=lambda:datetime.now(timezone.utc),
    ) -> None:
        self.mission_db=_direct_file(mission_db,"Mission Control DB")
        root=Path(artifact_root)
        _require(root.is_absolute() and root.is_dir() and not root.is_symlink(),"artifact root")
        self.artifact_root=root.resolve(strict=True)
        _require(self.artifact_root==root,"artifact root symlink indirection")
        _require(callable(evidence_source),"preparation evidence source")
        _require(type(admission_engine) is RuntimeAdmissionEngine,"exact RuntimeAdmissionEngine required")
        _require(type(admission_source) is SQLiteRuntimeAdmissionSource,
                 "exact SQLiteRuntimeAdmissionSource required")
        _require(callable(now_fn),"trusted preparation clock")
        self.evidence_source=evidence_source
        self.admission_engine=admission_engine
        self.admission_source=admission_source
        self.now_fn=now_fn
        self.runtime_state_db=_direct_file(admission_source.path,"runtime admission state DB")
        _require(_file_identity(self.runtime_state_db)!=_file_identity(self.mission_db),
                 "runtime state DB must be distinct from Mission Control DB")
        self._mission_identity=_file_identity(self.mission_db)
        self._runtime_identity=_file_identity(self.runtime_state_db)
        self._lock=RLock()
        self._cache:dict[str,PreparedCooperativeContextSource]={}
        self._migrate()

    def _check_roots(self) -> None:
        _require(
            not self.mission_db.is_symlink()
            and _file_identity(self.mission_db)==self._mission_identity,
            "Mission Control DB identity drift",
        )
        _require(
            not self.runtime_state_db.is_symlink()
            and _file_identity(self.runtime_state_db)==self._runtime_identity,
            "runtime state DB identity drift",
        )

    def _migrate(self) -> None:
        self._check_roots()
        with sqlite3.connect(self.runtime_state_db) as db,db:
            db.execute("""CREATE TABLE IF NOT EXISTS cooperative_runtime_preparations(
              assignment_id TEXT PRIMARY KEY,
              input_digest TEXT NOT NULL,
              state TEXT NOT NULL,
              admission_digest TEXT,
              admission_json TEXT,
              provenance_digest TEXT,
              started_at TEXT NOT NULL,
              completed_at TEXT,
              schema_id TEXT NOT NULL
            )""")

    def admission_trust(self) -> RuntimeAdmissionSourceTrustBinding:
        return RuntimeAdmissionSourceTrustBinding(
            self.admission_source.source_id,
            self.admission_source.source_instance_id,
            self.admission_source.implementation_digest,
            self.admission_source.trust_anchor_id,
            self.admission_source.trust_anchor_digest,
        ).validate()

    def _snapshot(self, assignment_id: str) -> dict[str,Any]:
        self._check_roots()
        _require(isinstance(assignment_id,str) and bool(assignment_id) and "\x00" not in assignment_id,
                 "assignment identity")
        try:
            db=sqlite3.connect(self.mission_db.as_uri()+"?mode=ro",uri=True,timeout=2)
            db.row_factory=sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            row=db.execute(
                "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
                (assignment_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise CooperativeRuntimePreparationProviderError("canonical assignment unavailable") from exc
        finally:
            try: db.close()
            except Exception: pass
        _require(row is not None,"canonical assignment unavailable")
        value=dict(row)
        _require(value.get("state")=="HELD","preparation assignment not HELD")
        _require(isinstance(value.get("input_digest"),str) and len(value["input_digest"])==64,
                 "assignment input digest")
        return value

    def _journal(self, assignment_id: str) -> dict[str,Any]|None:
        self._check_roots()
        with sqlite3.connect(self.runtime_state_db) as db:
            db.row_factory=sqlite3.Row
            row=db.execute(
                "SELECT * FROM cooperative_runtime_preparations WHERE assignment_id=?",
                (assignment_id,),
            ).fetchone()
        return dict(row) if row else None

    def _begin(self, assignment: Mapping[str,Any], now: datetime) -> tuple[str,dict[str,Any]]:
        self._check_roots()
        aid=assignment["assignment_id"];input_digest=assignment["input_digest"]
        with sqlite3.connect(self.runtime_state_db,timeout=5,isolation_level=None) as db:
            db.row_factory=sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            try:
                row=db.execute(
                    "SELECT * FROM cooperative_runtime_preparations WHERE assignment_id=?",
                    (aid,),
                ).fetchone()
                if row is None:
                    db.execute(
                        "INSERT INTO cooperative_runtime_preparations VALUES(?,?,?,?,?,?,?,?,?)",
                        (aid,input_digest,PREPARING,None,None,None,now.isoformat(),None,JOURNAL_SCHEMA),
                    )
                    db.execute("COMMIT")
                    return "NEW",dict(
                        assignment_id=aid,input_digest=input_digest,state=PREPARING,
                        admission_digest=None,admission_json=None,provenance_digest=None,
                        started_at=now.isoformat(),completed_at=None,schema_id=JOURNAL_SCHEMA,
                    )
                value=dict(row)
                _require(value["input_digest"]==input_digest,"preparation input digest substitution")
                _require(value["schema_id"]==JOURNAL_SCHEMA,"preparation journal schema")
                db.execute("COMMIT")
                return "EXISTING",value
            except Exception:
                if db.in_transaction: db.execute("ROLLBACK")
                raise

    def _mark_unknown(self, assignment_id: str, now: datetime) -> None:
        self._check_roots()
        with sqlite3.connect(self.runtime_state_db) as db,db:
            db.execute(
                "UPDATE cooperative_runtime_preparations SET state=?,completed_at=? "
                "WHERE assignment_id=? AND state=?",
                (UNKNOWN,now.isoformat(),assignment_id,PREPARING),
            )

    @staticmethod
    def _provenance(
        assignment: Mapping[str,Any],
        evidence: CooperativeRuntimePreparationEvidence,
        admission: RuntimeAdmission,
    ) -> str:
        basis={
            "assignment_id":assignment["assignment_id"],
            "mission_id":assignment["mission_id"],
            "worker_id":assignment["material_drone_id"],
            "lease_generation":int(assignment["lease_generation"]),
            "input_digest":assignment["input_digest"],
            "proposal_context_digest":evidence.proposal_context.digest(),
            "pdp_decision_digest":evidence.pdp_result.applied.decision_digest,
            "live_authority_digest":evidence.admitted_authority.digest(),
            "provisioned_executor_digest":evidence.provisioned_executor.digest(),
            "sandbox_runtime_digest":evidence.sandbox_runtime.digest(),
            "dispatch_digest":evidence.dispatch.digest(),
            "provisioning_digest":evidence.provisioning.digest(),
            "sandbox_policy_digest":evidence.sandbox_policy.digest(),
            "admission_digest":admission.admission_digest,
        }
        return sha256(_PROVENANCE_DOMAIN+_canonical(basis)).hexdigest()

    def _mark_prepared(
        self,assignment:Mapping[str,Any],admission:RuntimeAdmission,
        provenance_digest:str,now:datetime,
    ) -> None:
        raw=json.dumps(asdict(admission),sort_keys=True,separators=(",",":"),
                       ensure_ascii=False,allow_nan=False)
        with sqlite3.connect(self.runtime_state_db,timeout=5,isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                cur=db.execute(
                    "UPDATE cooperative_runtime_preparations "
                    "SET state=?,admission_digest=?,admission_json=?,provenance_digest=? "
                    "WHERE assignment_id=? AND input_digest=? AND state=?",
                    (PREPARED,admission.admission_digest,raw,provenance_digest,
                     assignment["assignment_id"],assignment["input_digest"],PREPARING),
                )
                _require(cur.rowcount==1,"preparation journal transition race")
                db.execute("COMMIT")
            except Exception:
                if db.in_transaction: db.execute("ROLLBACK")
                raise

    def _publish_or_recover(
        self,admission:RuntimeAdmission,provenance_digest:str,now:datetime,
    ) -> RuntimeAdmission:
        try:
            self.admission_source.publish(
                admission,provenance_digest=provenance_digest,published_at=now
            )
        except RuntimeExecutionError:
            try:
                existing=self.admission_source.resolve(admission.admission_digest)
            except Exception as exc:
                raise CooperativeRuntimePreparationProviderError(
                    "durable runtime admission publication unavailable"
                ) from exc
            _require(existing==admission,"durable runtime admission publication conflict")
        resolved=self.admission_source.resolve(admission.admission_digest)
        _require(resolved==admission,"durable runtime admission readback mismatch")
        return resolved

    def _mark_published(self, assignment_id: str, admission_digest: str, now: datetime) -> None:
        with sqlite3.connect(self.runtime_state_db,timeout=5,isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                cur=db.execute(
                    "UPDATE cooperative_runtime_preparations SET state=?,completed_at=? "
                    "WHERE assignment_id=? AND admission_digest=? AND state=?",
                    (PUBLISHED,now.isoformat(),assignment_id,admission_digest,PREPARED),
                )
                _require(cur.rowcount==1,"preparation publish transition race")
                db.execute("COMMIT")
            except Exception:
                if db.in_transaction: db.execute("ROLLBACK")
                raise

    def _recover_prepared(
        self,assignment:Mapping[str,Any],evidence:CooperativeRuntimePreparationEvidence,
        journal:Mapping[str,Any],now:datetime,
    ) -> CooperativeRuntimeContext:
        _require(journal.get("state") in {PREPARED,PUBLISHED},"preparation recovery state")
        raw=journal.get("admission_json")
        _require(isinstance(raw,str) and bool(raw),"prepared admission journal missing")
        admission=_strict_admission(raw)
        _require(admission.admission_digest==journal.get("admission_digest"),
                 "prepared admission journal digest mismatch")
        provenance=journal.get("provenance_digest")
        _require(isinstance(provenance,str) and len(provenance)==64,
                 "prepared admission provenance missing")
        durable=self._publish_or_recover(admission,provenance,now)
        if journal.get("state")==PREPARED:
            self._mark_published(assignment["assignment_id"],durable.admission_digest,now)
        return reconstruct_cooperative_runtime_context(
            assignment=assignment,
            artifact_root=self.artifact_root,
            evidence=evidence,
            durable_admission=durable,
        )

    def __call__(self, assignment_id: str) -> CooperativeRuntimeContext:
        with self._lock:
            assignment=self._snapshot(assignment_id)
            cached=self._cache.get(assignment_id)
            if cached is not None:
                context=cached(assignment_id)
                _require(context.execution.input_digest==assignment["input_digest"],
                         "cached preparation input drift")
                return context

            now=_zoned(self.now_fn(),"trusted preparation clock")
            evidence=self.evidence_source(assignment_id)
            _require(type(evidence) is CooperativeRuntimePreparationEvidence,
                     "exact preparation evidence required")
            evidence.validate()
            validate_cooperative_runtime_preparation_inputs(
                assignment=assignment,
                artifact_root=self.artifact_root,
                evidence=evidence,
            )
            state,journal=self._begin(assignment,now)

            if state=="EXISTING":
                if journal["state"] in {PREPARED,PUBLISHED}:
                    context=self._recover_prepared(assignment,evidence,journal,now)
                    source=PreparedCooperativeContextSource(context)
                    self._cache[assignment_id]=source
                    return source(assignment_id)
                raise CooperativeRuntimePreparationProviderError(UNKNOWN)

            try:
                context=prepare_cooperative_runtime_context(
                    assignment=assignment,
                    artifact_root=self.artifact_root,
                    evidence=evidence,
                    admission_engine=self.admission_engine,
                    trusted_now=now,
                )
                admission=context.execution.admission
                provenance=self._provenance(assignment,evidence,admission)
                self._mark_prepared(assignment,admission,provenance,now)
            except Exception as exc:
                self._mark_unknown(assignment_id,now)
                raise CooperativeRuntimePreparationProviderError(UNKNOWN) from exc

            durable=self._publish_or_recover(admission,provenance,now)
            self._mark_published(assignment_id,durable.admission_digest,now)
            reconstructed=reconstruct_cooperative_runtime_context(
                assignment=assignment,
                artifact_root=self.artifact_root,
                evidence=evidence,
                durable_admission=durable,
            )
            source=PreparedCooperativeContextSource(reconstructed)
            self._cache[assignment_id]=source
            return source(assignment_id)

    def status(self, assignment_id: str) -> dict[str,Any]:
        row=self._journal(assignment_id)
        return {
            "schema":SCHEMA_ID,
            "assignment_id":assignment_id,
            "state":row["state"] if row else "NOT_STARTED",
            "admission_digest":row.get("admission_digest") if row else None,
            "authority_effect":"NONE",
            "execution_effect":"NONE",
        }

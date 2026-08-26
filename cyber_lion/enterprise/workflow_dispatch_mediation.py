"""Canonical exact workflow-dispatch mediation boundary.

This module contains no authority source. A trusted external composition must supply a
WorkflowDispatchAdmissionResolver whose admission is already the result of the canonical
LiveAuthorityAdmission + CanonicalPolicyDecisionPoint chain. Missing trusted composition
fails closed. Issue comments, actors, GITHUB_TOKEN and CI state are evidence only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re
import sqlite3
from threading import RLock
from typing import Protocol

from cyber_lion.contracts.actions_dispatch_bridge import DispatchRequest, canonical_json

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_STATES = {"PREPARED", "ATTEMPTED", "OBSERVED", "RECONCILED", "UNKNOWN"}
_DOMAIN = b"LION/WORKFLOW-DISPATCH-ADMISSION/1\0"
_EFFECT_DOMAIN = b"LION/WORKFLOW-DISPATCH-EFFECT/1\0"
_OBSERVATION_DOMAIN = b"LION/WORKFLOW-DISPATCH-OBSERVATION/1\0"
_RECONCILIATION_DOMAIN = b"LION/WORKFLOW-DISPATCH-RECONCILIATION/1\0"


class WorkflowDispatchMediationError(RuntimeError):
    pass


def _hex64(v: str, name: str) -> str:
    if not isinstance(v, str) or _HEX64.fullmatch(v) is None:
        raise WorkflowDispatchMediationError(f"{name} invalid")
    return v


def _sha40(v: str, name: str) -> str:
    if not isinstance(v, str) or _HEX40.fullmatch(v) is None:
        raise WorkflowDispatchMediationError(f"{name} invalid")
    return v


def _digest(domain: bytes, value: object) -> str:
    return sha256(domain + canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class CanonicalWorkflowDispatchAdmission:
    request_digest: str
    repository: str
    workflow: str
    ref: str
    expected_head: str
    canonical_inputs_digest: str
    authority_lineage_digest: str
    pdp_decision_digest: str
    provider_id: str
    authority_epoch: int
    admission_digest: str = ""

    def payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("admission_digest")
        return value

    def validate(self) -> "CanonicalWorkflowDispatchAdmission":
        for name in ("request_digest", "canonical_inputs_digest", "authority_lineage_digest", "pdp_decision_digest"):
            _hex64(getattr(self, name), name)
        _sha40(self.expected_head, "expected_head")
        if not self.repository or not self.workflow or not self.ref or not self.provider_id:
            raise WorkflowDispatchMediationError("admission identity invalid")
        if not isinstance(self.authority_epoch, int) or isinstance(self.authority_epoch, bool) or self.authority_epoch < 0:
            raise WorkflowDispatchMediationError("authority_epoch invalid")
        expected = _digest(_DOMAIN, self.payload())
        if self.admission_digest and self.admission_digest != expected:
            raise WorkflowDispatchMediationError("admission digest mismatch")
        return self

    def sealed(self) -> "CanonicalWorkflowDispatchAdmission":
        self.validate()
        return CanonicalWorkflowDispatchAdmission(
            **{**self.payload(), "admission_digest": _digest(_DOMAIN, self.payload())}
        ).validate()

    def binds(self, request: DispatchRequest) -> None:
        request_digest = request.payload_digest()
        inputs_digest = sha256(request.canonical_inputs.encode("utf-8")).hexdigest()
        expected = (
            request_digest,
            request.repository,
            request.workflow,
            request.ref,
            request.expected_head,
            inputs_digest,
        )
        actual = (
            self.request_digest,
            self.repository,
            self.workflow,
            self.ref,
            self.expected_head,
            self.canonical_inputs_digest,
        )
        if actual != expected:
            raise WorkflowDispatchMediationError("admission/request binding mismatch")


class WorkflowDispatchAdmissionResolver(Protocol):
    def resolve(self, request: DispatchRequest) -> CanonicalWorkflowDispatchAdmission: ...


class WorkflowDispatchRepositoryReader(Protocol):
    def ref_head(self, ref: str) -> str: ...
    def workflow_exists(self, workflow: str, sha: str) -> bool: ...
    def workflow_runs(self, workflow: str, ref: str) -> list[dict]: ...


class WorkflowDispatchEffectProvider(Protocol):
    def execute_exact(
        self,
        request: DispatchRequest,
        admission: CanonicalWorkflowDispatchAdmission,
    ) -> None: ...


@dataclass(frozen=True)
class WorkflowDispatchFenceRecord:
    effect_key: str
    admission_digest: str
    request_digest: str
    repository: str
    workflow: str
    ref: str
    expected_head: str
    state: str
    prepared_at: str
    attempted_at: str | None = None
    observed_at: str | None = None
    reconciled_at: str | None = None
    observation_digest: str | None = None
    reconciliation_digest: str | None = None

    def validate(self) -> "WorkflowDispatchFenceRecord":
        for name in ("effect_key", "admission_digest", "request_digest"):
            _hex64(getattr(self, name), name)
        _sha40(self.expected_head, "expected_head")
        if self.state not in _STATES:
            raise WorkflowDispatchMediationError("fence state invalid")
        if not self.repository or not self.workflow or not self.ref or not self.prepared_at:
            raise WorkflowDispatchMediationError("fence identity invalid")
        if self.state == "PREPARED" and any(
            (
                self.attempted_at,
                self.observed_at,
                self.reconciled_at,
                self.observation_digest,
                self.reconciliation_digest,
            )
        ):
            raise WorkflowDispatchMediationError("PREPARED contains later evidence")
        if self.state in {"ATTEMPTED", "OBSERVED", "RECONCILED"} and not self.attempted_at:
            raise WorkflowDispatchMediationError("attempted_at missing")
        if self.state in {"OBSERVED", "RECONCILED"}:
            if not self.observed_at or self.observation_digest is None:
                raise WorkflowDispatchMediationError("observation missing")
            _hex64(self.observation_digest, "observation_digest")
        if self.state == "RECONCILED":
            if not self.reconciled_at or self.reconciliation_digest is None:
                raise WorkflowDispatchMediationError("reconciliation missing")
            _hex64(self.reconciliation_digest, "reconciliation_digest")
        return self


class DurableWorkflowDispatchFence:
    def __init__(self, database_path: str) -> None:
        path = Path(database_path)
        if not path.is_absolute():
            raise WorkflowDispatchMediationError("fence database path must be absolute")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = str(path)
        self._lock = RLock()
        self._initialize()

    def _connect(self):
        c = sqlite3.connect(
            self._path,
            timeout=10,
            isolation_level=None,
            check_same_thread=False,
        )
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")
        return c

    def _initialize(self) -> None:
        with self._lock, self._connect() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS workflow_dispatch_effect(
                effect_key TEXT PRIMARY KEY,
                admission_digest TEXT NOT NULL UNIQUE,
                request_digest TEXT NOT NULL UNIQUE,
                repository TEXT NOT NULL,
                workflow TEXT NOT NULL,
                ref TEXT NOT NULL,
                expected_head TEXT NOT NULL,
                state TEXT NOT NULL,
                prepared_at TEXT NOT NULL,
                attempted_at TEXT,
                observed_at TEXT,
                reconciled_at TEXT,
                observation_digest TEXT,
                reconciliation_digest TEXT
                )"""
            )

    @staticmethod
    def _row(row) -> WorkflowDispatchFenceRecord:
        if row is None:
            raise WorkflowDispatchMediationError("dispatch effect unknown")
        return WorkflowDispatchFenceRecord(*row).validate()

    def get(self, effect_key: str) -> WorkflowDispatchFenceRecord:
        _hex64(effect_key, "effect_key")
        with self._connect() as c:
            row = c.execute(
                "SELECT effect_key,admission_digest,request_digest,repository,workflow,ref,"
                "expected_head,state,prepared_at,attempted_at,observed_at,reconciled_at,"
                "observation_digest,reconciliation_digest "
                "FROM workflow_dispatch_effect WHERE effect_key=?",
                (effect_key,),
            ).fetchone()
        return self._row(row)

    def prepare(self, record: WorkflowDispatchFenceRecord) -> None:
        record.validate()
        if record.state != "PREPARED":
            raise WorkflowDispatchMediationError("pristine PREPARED required")
        with self._lock, self._connect() as c:
            try:
                c.execute("BEGIN IMMEDIATE")
                c.execute(
                    "INSERT INTO workflow_dispatch_effect VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    tuple(asdict(record).values()),
                )
                c.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                c.execute("ROLLBACK")
                raise WorkflowDispatchMediationError(
                    "dispatch replay or binding collision denied"
                ) from exc

    def mark_attempted(self, effect_key: str, attempted_at: str) -> WorkflowDispatchFenceRecord:
        with self._lock, self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            cur = c.execute(
                "UPDATE workflow_dispatch_effect "
                "SET state='ATTEMPTED', attempted_at=? "
                "WHERE effect_key=? AND state='PREPARED' AND attempted_at IS NULL",
                (attempted_at, effect_key),
            )
            if cur.rowcount != 1:
                c.execute("ROLLBACK")
                raise WorkflowDispatchMediationError("dispatch effect cannot enter ATTEMPTED")
            c.execute("COMMIT")
        return self.get(effect_key)

    def mark_observed(
        self,
        effect_key: str,
        *,
        digest: str,
        at: str,
    ) -> WorkflowDispatchFenceRecord:
        _hex64(digest, "observation_digest")
        with self._lock, self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            cur = c.execute(
                "UPDATE workflow_dispatch_effect "
                "SET state='OBSERVED', observation_digest=?, observed_at=? "
                "WHERE effect_key=? AND state='ATTEMPTED'",
                (digest, at, effect_key),
            )
            if cur.rowcount != 1:
                c.execute("ROLLBACK")
                raise WorkflowDispatchMediationError("dispatch effect cannot enter OBSERVED")
            c.execute("COMMIT")
        return self.get(effect_key)

    def mark_reconciled(
        self,
        effect_key: str,
        *,
        digest: str,
        at: str,
    ) -> WorkflowDispatchFenceRecord:
        _hex64(digest, "reconciliation_digest")
        with self._lock, self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            cur = c.execute(
                "UPDATE workflow_dispatch_effect "
                "SET state='RECONCILED', reconciliation_digest=?, reconciled_at=? "
                "WHERE effect_key=? AND state='OBSERVED'",
                (digest, at, effect_key),
            )
            if cur.rowcount != 1:
                c.execute("ROLLBACK")
                raise WorkflowDispatchMediationError("dispatch effect cannot enter RECONCILED")
            c.execute("COMMIT")
        return self.get(effect_key)

    def mark_unknown(self, effect_key: str) -> WorkflowDispatchFenceRecord:
        with self._lock, self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            cur = c.execute(
                "UPDATE workflow_dispatch_effect SET state='UNKNOWN' "
                "WHERE effect_key=? AND state IN ('PREPARED','ATTEMPTED','OBSERVED')",
                (effect_key,),
            )
            if cur.rowcount != 1:
                c.execute("ROLLBACK")
                raise WorkflowDispatchMediationError("dispatch effect cannot enter UNKNOWN")
            c.execute("COMMIT")
        return self.get(effect_key)


class CanonicalWorkflowDispatchMediator:
    def __init__(
        self,
        *,
        admissions: WorkflowDispatchAdmissionResolver,
        repository: WorkflowDispatchRepositoryReader,
        effect: WorkflowDispatchEffectProvider,
        fence: DurableWorkflowDispatchFence,
    ) -> None:
        for obj, method in (
            (admissions, "resolve"),
            (repository, "ref_head"),
            (repository, "workflow_exists"),
            (repository, "workflow_runs"),
            (effect, "execute_exact"),
        ):
            if not callable(getattr(obj, method, None)):
                raise WorkflowDispatchMediationError("canonical dispatch dependency unavailable")
        self.admissions = admissions
        self.repository = repository
        self.effect = effect
        self.fence = fence

    def execute(self, request: DispatchRequest) -> dict[str, object]:
        request_digest = request.payload_digest()
        if self.repository.ref_head(request.ref) != request.expected_head:
            raise WorkflowDispatchMediationError("dispatch head is not current")
        if not self.repository.workflow_exists(request.workflow, request.expected_head):
            raise WorkflowDispatchMediationError("dispatch workflow missing at exact head")
        admission = self.admissions.resolve(request)
        if type(admission) is not CanonicalWorkflowDispatchAdmission:
            raise WorkflowDispatchMediationError("exact canonical dispatch admission required")
        admission.validate()
        admission.binds(request)
        effect_key = _digest(
            _EFFECT_DOMAIN,
            {"admission_digest": admission.admission_digest, "request_digest": request_digest},
        )
        prepared_at = datetime.now(timezone.utc).isoformat()
        self.fence.prepare(
            WorkflowDispatchFenceRecord(
                effect_key=effect_key,
                admission_digest=admission.admission_digest,
                request_digest=request_digest,
                repository=request.repository,
                workflow=request.workflow,
                ref=request.ref,
                expected_head=request.expected_head,
                state="PREPARED",
                prepared_at=prepared_at,
            ).validate()
        )
        try:
            current = self.admissions.resolve(request)
            if (
                type(current) is not CanonicalWorkflowDispatchAdmission
                or current.validate().admission_digest != admission.admission_digest
            ):
                raise WorkflowDispatchMediationError("dispatch admission drift after PREPARED")
            if (
                self.repository.ref_head(request.ref) != request.expected_head
                or not self.repository.workflow_exists(request.workflow, request.expected_head)
            ):
                raise WorkflowDispatchMediationError("dispatch target drift after PREPARED")

            attempted_at = datetime.now(timezone.utc).isoformat()
            self.fence.mark_attempted(effect_key, attempted_at)
            self.effect.execute_exact(request, admission)

            candidates: list[dict[str, object]] = []
            for run in self.repository.workflow_runs(request.workflow, request.ref):
                if (
                    run.get("event") != "workflow_dispatch"
                    or run.get("head_branch") != request.ref
                    or str(run.get("head_sha", "")).lower() != request.expected_head
                ):
                    continue
                created = str(run.get("created_at", ""))
                run_id = run.get("id")
                if isinstance(run_id, int) and run_id > 0 and created >= attempted_at:
                    candidates.append({"run_id": run_id, "created_at": created})
            if len(candidates) != 1:
                raise WorkflowDispatchMediationError(
                    "matching workflow_dispatch observation missing or ambiguous"
                )

            observation = {
                "effect_key": effect_key,
                "request_digest": request_digest,
                "workflow": request.workflow,
                "ref": request.ref,
                "expected_head": request.expected_head,
                **candidates[0],
            }
            observation_digest = _digest(_OBSERVATION_DOMAIN, observation)
            self.fence.mark_observed(
                effect_key,
                digest=observation_digest,
                at=datetime.now(timezone.utc).isoformat(),
            )
            reconciliation_digest = _digest(
                _RECONCILIATION_DOMAIN,
                {
                    **observation,
                    "observation_digest": observation_digest,
                    "admission_digest": admission.admission_digest,
                    "pdp_decision_digest": admission.pdp_decision_digest,
                    "authority_lineage_digest": admission.authority_lineage_digest,
                },
            )
            final = self.fence.mark_reconciled(
                effect_key,
                digest=reconciliation_digest,
                at=datetime.now(timezone.utc).isoformat(),
            )
            return {
                "schema_version": "1.0.0",
                "effect": "workflow_dispatch",
                "request_digest": request_digest,
                "admission_digest": admission.admission_digest,
                "pdp_decision_digest": admission.pdp_decision_digest,
                "authority_lineage_digest": admission.authority_lineage_digest,
                "effect_key": effect_key,
                "observation_digest": observation_digest,
                "reconciliation_digest": reconciliation_digest,
                "fence_state": final.state,
                "run_id": candidates[0]["run_id"],
            }
        except Exception:
            try:
                current_fence = self.fence.get(effect_key)
                if current_fence.state in {"PREPARED", "ATTEMPTED", "OBSERVED"}:
                    self.fence.mark_unknown(effect_key)
            except Exception:
                pass
            raise

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import sqlite3
from threading import RLock
from typing import Protocol

from cyber_lion.contracts.actions_run_cancel import ActionsRunCancelRequest

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_STATES = {"PREPARED", "ATTEMPTED", "OBSERVED", "RECONCILED", "UNKNOWN"}


class ActionsRunCancelMediationError(RuntimeError):
    pass


def _digest(domain: bytes, value: object) -> str:
    return sha256(
        domain
        + json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _hex64(value: str, name: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise ActionsRunCancelMediationError(f"{name} invalid")
    return value


@dataclass(frozen=True)
class CanonicalActionsRunCancelAdmission:
    request_digest: str
    repository: str
    run_id: int
    expected_workflow: str
    expected_event: str
    expected_head_sha: str
    authority_lineage_digest: str
    pdp_decision_digest: str
    provider_id: str
    authority_epoch: int
    admission_digest: str = ""

    def payload(self):
        value = asdict(self)
        value.pop("admission_digest")
        return value

    def validate(self):
        for name in (
            "request_digest",
            "authority_lineage_digest",
            "pdp_decision_digest",
        ):
            _hex64(getattr(self, name), name)
        if (
            self.repository != "DonkeyJJLove/ai_platform"
            or not isinstance(self.run_id, int)
            or isinstance(self.run_id, bool)
            or self.run_id <= 0
            or not self.expected_workflow
            or not self.expected_event
            or not self.provider_id
            or not isinstance(self.authority_epoch, int)
            or isinstance(self.authority_epoch, bool)
            or self.authority_epoch < 0
        ):
            raise ActionsRunCancelMediationError("admission identity invalid")
        expected = _digest(b"LION/ACTIONS-RUN-CANCEL-ADMISSION/1\0", self.payload())
        if self.admission_digest and self.admission_digest != expected:
            raise ActionsRunCancelMediationError("admission digest mismatch")
        return self

    def sealed(self):
        self.validate()
        payload = self.payload()
        return CanonicalActionsRunCancelAdmission(
            **{
                **payload,
                "admission_digest": _digest(
                    b"LION/ACTIONS-RUN-CANCEL-ADMISSION/1\0", payload
                ),
            }
        ).validate()

    def binds(self, request: ActionsRunCancelRequest):
        actual = (
            self.request_digest,
            self.repository,
            self.run_id,
            self.expected_workflow,
            self.expected_event,
            self.expected_head_sha,
        )
        expected = (
            request.payload_digest(),
            request.repository,
            request.run_id,
            request.expected_workflow,
            request.expected_event,
            request.expected_head_sha,
        )
        if actual != expected:
            raise ActionsRunCancelMediationError("admission/request binding mismatch")


class ActionsRunCancelAdmissionResolver(Protocol):
    def resolve(
        self, request: ActionsRunCancelRequest
    ) -> CanonicalActionsRunCancelAdmission: ...


class ActionsRunReader(Protocol):
    def get_run(self, run_id: int) -> dict: ...


class ActionsRunCancelEffect(Protocol):
    def cancel_exact(
        self,
        request: ActionsRunCancelRequest,
        admission: CanonicalActionsRunCancelAdmission,
    ) -> None: ...


@dataclass(frozen=True)
class ActionsRunCancelFenceRecord:
    effect_key: str
    admission_digest: str
    request_digest: str
    repository: str
    run_id: int
    state: str
    prepared_at: str
    attempted_at: str | None = None
    observed_at: str | None = None
    reconciled_at: str | None = None
    observation_digest: str | None = None
    reconciliation_digest: str | None = None

    def validate(self):
        for name in ("effect_key", "admission_digest", "request_digest"):
            _hex64(getattr(self, name), name)
        if self.repository != "DonkeyJJLove/ai_platform" or self.run_id <= 0:
            raise ActionsRunCancelMediationError("fence identity invalid")
        if self.state not in _STATES:
            raise ActionsRunCancelMediationError("fence state invalid")
        if self.state == "PREPARED" and any(
            (
                self.attempted_at,
                self.observed_at,
                self.reconciled_at,
                self.observation_digest,
                self.reconciliation_digest,
            )
        ):
            raise ActionsRunCancelMediationError("PREPARED contains later evidence")
        if self.state in {"ATTEMPTED", "OBSERVED", "RECONCILED"} and not self.attempted_at:
            raise ActionsRunCancelMediationError("attempted_at missing")
        if self.state in {"OBSERVED", "RECONCILED"}:
            if not self.observed_at or not self.observation_digest:
                raise ActionsRunCancelMediationError("observation missing")
            _hex64(self.observation_digest, "observation_digest")
        if self.state == "RECONCILED":
            if not self.reconciled_at or not self.reconciliation_digest:
                raise ActionsRunCancelMediationError("reconciliation missing")
            _hex64(self.reconciliation_digest, "reconciliation_digest")
        return self


class DurableActionsRunCancelFence:
    def __init__(self, database_path: str):
        path = Path(database_path)
        if not path.is_absolute():
            raise ActionsRunCancelMediationError("fence path must be absolute")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = str(path)
        self._lock = RLock()
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(
            self._path,
            timeout=10,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self):
        with self._lock, self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS actions_run_cancel_effect("
                "effect_key TEXT PRIMARY KEY,"
                "admission_digest TEXT UNIQUE NOT NULL,"
                "request_digest TEXT UNIQUE NOT NULL,"
                "repository TEXT NOT NULL,"
                "run_id INTEGER NOT NULL,"
                "state TEXT NOT NULL,"
                "prepared_at TEXT NOT NULL,"
                "attempted_at TEXT,"
                "observed_at TEXT,"
                "reconciled_at TEXT,"
                "observation_digest TEXT,"
                "reconciliation_digest TEXT)"
            )

    def get(self, effect_key: str):
        _hex64(effect_key, "effect_key")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT effect_key,admission_digest,request_digest,repository,run_id,"
                "state,prepared_at,attempted_at,observed_at,reconciled_at,"
                "observation_digest,reconciliation_digest "
                "FROM actions_run_cancel_effect WHERE effect_key=?",
                (effect_key,),
            ).fetchone()
        if row is None:
            raise ActionsRunCancelMediationError("cancel effect unknown")
        return ActionsRunCancelFenceRecord(*row).validate()

    def prepare(self, record: ActionsRunCancelFenceRecord):
        record.validate()
        if record.state != "PREPARED":
            raise ActionsRunCancelMediationError("PREPARED required")
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO actions_run_cancel_effect VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    tuple(asdict(record).values()),
                )
            except sqlite3.IntegrityError as exc:
                raise ActionsRunCancelMediationError("cancel replay denied") from exc

    def mark_attempted(self, effect_key: str, attempted_at: str):
        with self._lock, self._connect() as connection:
            cur = connection.execute(
                "UPDATE actions_run_cancel_effect "
                "SET state='ATTEMPTED',attempted_at=? "
                "WHERE effect_key=? AND state='PREPARED' AND attempted_at IS NULL",
                (attempted_at, effect_key),
            )
            if cur.rowcount != 1:
                raise ActionsRunCancelMediationError("cancel cannot enter ATTEMPTED")
        return self.get(effect_key)

    def mark_observed(self, effect_key: str, *, observed_at: str, digest: str):
        _hex64(digest, "observation_digest")
        with self._lock, self._connect() as connection:
            cur = connection.execute(
                "UPDATE actions_run_cancel_effect "
                "SET state='OBSERVED',observed_at=?,observation_digest=? "
                "WHERE effect_key=? AND state='ATTEMPTED'",
                (observed_at, digest, effect_key),
            )
            if cur.rowcount != 1:
                raise ActionsRunCancelMediationError("cancel cannot enter OBSERVED")
        return self.get(effect_key)

    def mark_reconciled(self, effect_key: str, *, reconciled_at: str, digest: str):
        _hex64(digest, "reconciliation_digest")
        with self._lock, self._connect() as connection:
            cur = connection.execute(
                "UPDATE actions_run_cancel_effect "
                "SET state='RECONCILED',reconciled_at=?,reconciliation_digest=? "
                "WHERE effect_key=? AND state='OBSERVED'",
                (reconciled_at, digest, effect_key),
            )
            if cur.rowcount != 1:
                raise ActionsRunCancelMediationError("cancel cannot enter RECONCILED")
        return self.get(effect_key)

    def mark_unknown(self, effect_key: str):
        with self._lock, self._connect() as connection:
            cur = connection.execute(
                "UPDATE actions_run_cancel_effect SET state='UNKNOWN' "
                "WHERE effect_key=? AND state IN ('PREPARED','ATTEMPTED','OBSERVED')",
                (effect_key,),
            )
            if cur.rowcount != 1:
                raise ActionsRunCancelMediationError("cancel cannot enter UNKNOWN")
        return self.get(effect_key)


def actions_run_cancel_effect_key(request, admission):
    if type(admission) is not CanonicalActionsRunCancelAdmission:
        raise ActionsRunCancelMediationError("exact admission required")
    admission.validate()
    admission.binds(request)
    _hex64(admission.admission_digest, "admission_digest")
    return _digest(
        b"LION/ACTIONS-RUN-CANCEL-EFFECT/1\0",
        {
            "request": request.payload_digest(),
            "admission": admission.admission_digest,
        },
    )


class CanonicalActionsRunCancelMediator:
    def __init__(
        self,
        *,
        admissions: ActionsRunCancelAdmissionResolver,
        repository: ActionsRunReader,
        effect: ActionsRunCancelEffect,
        fence: DurableActionsRunCancelFence,
    ):
        for obj, method in (
            (admissions, "resolve"),
            (repository, "get_run"),
            (effect, "cancel_exact"),
        ):
            if not callable(getattr(obj, method, None)):
                raise ActionsRunCancelMediationError("canonical cancel dependency unavailable")
        if type(fence) is not DurableActionsRunCancelFence:
            raise ActionsRunCancelMediationError("exact cancel fence required")
        self.admissions = admissions
        self.repository = repository
        self.effect = effect
        self.fence = fence

    @staticmethod
    def _validate_run(request, run):
        if (
            run.get("id") != request.run_id
            or run.get("name") != request.expected_workflow
            or run.get("event") != request.expected_event
            or str(run.get("head_sha", "")) != request.expected_head_sha
        ):
            raise ActionsRunCancelMediationError("run currentness mismatch")
        if run.get("status") not in {"queued", "in_progress"}:
            raise ActionsRunCancelMediationError("run not cancellable")

    def execute(self, request: ActionsRunCancelRequest):
        request.validate()
        self._validate_run(request, self.repository.get_run(request.run_id))
        admission = self.admissions.resolve(request)
        if type(admission) is not CanonicalActionsRunCancelAdmission:
            raise ActionsRunCancelMediationError("exact admission required")
        admission.validate()
        _hex64(admission.admission_digest, "admission_digest")
        admission.binds(request)
        effect_key = actions_run_cancel_effect_key(request, admission)
        prepared_at = datetime.now(timezone.utc).isoformat()
        self.fence.prepare(
            ActionsRunCancelFenceRecord(
                effect_key,
                admission.admission_digest,
                request.payload_digest(),
                request.repository,
                request.run_id,
                "PREPARED",
                prepared_at,
            )
        )
        try:
            current = self.admissions.resolve(request)
            if (
                type(current) is not CanonicalActionsRunCancelAdmission
                or current.validate().admission_digest != admission.admission_digest
            ):
                raise ActionsRunCancelMediationError("authority drift")
            self._validate_run(request, self.repository.get_run(request.run_id))
            attempted_at = datetime.now(timezone.utc).isoformat()
            self.fence.mark_attempted(effect_key, attempted_at)
            self.effect.cancel_exact(request, admission)
            run = self.repository.get_run(request.run_id)
            if not (
                run.get("status") == "completed"
                and run.get("conclusion") == "cancelled"
            ):
                raise ActionsRunCancelMediationError(
                    "independent cancellation observation missing"
                )
            observation_digest = _digest(
                b"LION/ACTIONS-RUN-CANCEL-OBS/1\0",
                {
                    "run_id": request.run_id,
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                },
            )
            observed_at = datetime.now(timezone.utc).isoformat()
            self.fence.mark_observed(
                effect_key, observed_at=observed_at, digest=observation_digest
            )
            reconciliation_digest = _digest(
                b"LION/ACTIONS-RUN-CANCEL-REC/1\0",
                {
                    "effect_key": effect_key,
                    "observation_digest": observation_digest,
                },
            )
            reconciled_at = datetime.now(timezone.utc).isoformat()
            self.fence.mark_reconciled(
                effect_key,
                reconciled_at=reconciled_at,
                digest=reconciliation_digest,
            )
            return {
                "effect_key": effect_key,
                "state": "RECONCILED",
                "run_id": request.run_id,
                "observation_digest": observation_digest,
                "reconciliation_digest": reconciliation_digest,
            }
        except Exception:
            try:
                self.fence.mark_unknown(effect_key)
            except Exception:
                pass
            raise

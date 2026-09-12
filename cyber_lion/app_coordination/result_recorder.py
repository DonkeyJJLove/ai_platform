"""Durable OFFLINE_CANDIDATE results; never a canonical admission issuer.

Index and receipt writes share one SQLite transaction. This does not couple to
RuntimeAdmissionEngine replay consumption. An unresolved reservation remains
UNKNOWN and cannot be cleared to authorize re-admission or dispatch.
"""
from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from cyber_lion.contracts.runtime_enforcement import RuntimeAdmission
from .source_candidates import SourceRejected, SourceUnavailable, canonical, decode, digest


class ResultConflict(SourceRejected):
    pass


@dataclass(frozen=True)
class StoredCandidate:
    request_digest: str
    state: str
    result_json: str | None
    runtime_ready: bool = False
    retry_allowed: bool = False


class CandidateResultStore:
    MODE = "LION_E02_OFFLINE_CANDIDATE_V1"

    @classmethod
    def create(cls, path):
        path = Path(path).resolve()
        # Refuse replacement or automatic use of an existing/production database.
        with path.open("xb"):
            pass
        connection = sqlite3.connect(path.as_uri()+"?mode=rw", uri=True)
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.executescript("""
                CREATE TABLE metadata (singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                                       mode TEXT NOT NULL, store_id TEXT NOT NULL);
                CREATE TABLE attempts (request_digest TEXT PRIMARY KEY,
                    task_digest TEXT NOT NULL, state TEXT NOT NULL
                    CHECK(state IN ('UNKNOWN_REQUIRES_RECONCILIATION','CANDIDATE_RECORDED')));
                CREATE TABLE receipts (admission_digest TEXT PRIMARY KEY,
                    payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL);
                CREATE TABLE request_index (request_digest TEXT PRIMARY KEY
                    REFERENCES attempts(request_digest),
                    admission_digest TEXT NOT NULL UNIQUE REFERENCES receipts(admission_digest),
                    bound_payload TEXT NOT NULL, bound_sha256 TEXT NOT NULL);
            """)
            connection.execute("INSERT INTO metadata VALUES(1,?,?)",(cls.MODE,str(uuid4())))
            connection.commit()
        finally:
            connection.close()
        return cls(path)

    def __init__(self, path):
        self.path = Path(path).resolve(strict=True)
        with self._open() as db:
            self.store_id = self._identity(db)

    @contextmanager
    def _open(self):
        db = sqlite3.connect(self.path.as_uri()+"?mode=rw", uri=True,
                             timeout=5, isolation_level=None)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            yield db
        finally:
            db.close()

    def _identity(self, db):
        try:
            rows = db.execute("SELECT singleton,mode,store_id FROM metadata").fetchall()
        except sqlite3.Error as exc:
            raise SourceRejected("not an offline candidate database") from exc
        if len(rows)!=1 or rows[0][0]!=1 or rows[0][1]!=self.MODE or not rows[0][2]:
            raise SourceRejected("database mode or identity invalid")
        return rows[0][2]

    def _verify(self, db):
        if self._identity(db) != self.store_id:
            raise SourceRejected("database instance changed")

    def reserve(self, request_digest, task_digest):
        digest(request_digest); digest(task_digest)
        with self._open() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._verify(db)
                old = db.execute("SELECT task_digest FROM attempts WHERE request_digest=?",
                                 (request_digest,)).fetchone()
                if old is not None and old[0] != task_digest:
                    raise ResultConflict("request belongs to a different task")
                if old is None:
                    db.execute("INSERT INTO attempts VALUES(?,?,'UNKNOWN_REQUIRES_RECONCILIATION')",
                               (request_digest,task_digest))
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return self.inspect(request_digest)

    def record_candidate(self, request_digest, bound_admission):
        digest(request_digest)
        if not is_dataclass(bound_admission) or isinstance(bound_admission,type):
            raise SourceRejected("typed bound candidate required")
        try:
            receipt = bound_admission.runtime_admission
            binding = bound_admission.task_binding
            if type(receipt) is not RuntimeAdmission:
                raise SourceRejected("exact canonical receipt type required")
            receipt.validate(); binding.validate()
            digest(bound_admission.source_revision)
            if binding.provisioned_executor_digest != receipt.provisioned_executor_digest:
                raise SourceRejected("task/receipt provisioning mismatch")
            receipt_json = canonical(asdict(receipt))
            bound_json = canonical(asdict(bound_admission))
            if len(bound_json.encode()) > 262144:
                raise SourceRejected("candidate payload too large")
            task_digest = binding.task_digest
            digest(task_digest)
        except (AttributeError,TypeError,ValueError) as exc:
            if isinstance(exc,SourceRejected): raise
            raise SourceRejected("invalid bound candidate") from exc
        with self._open() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._verify(db)
                attempt = db.execute("SELECT task_digest FROM attempts WHERE request_digest=?",
                                     (request_digest,)).fetchone()
                if attempt is None or attempt[0] != task_digest:
                    raise SourceRejected("matching prior reservation required")
                old = db.execute("SELECT bound_payload FROM request_index WHERE request_digest=?",
                                 (request_digest,)).fetchone()
                if old is not None:
                    if old[0] != bound_json:
                        raise ResultConflict("conflicting result; overwrite denied")
                else:
                    db.execute("INSERT INTO receipts VALUES(?,?,?)",
                               (receipt.admission_digest,receipt_json,sha256(receipt_json.encode()).hexdigest()))
                    db.execute("INSERT INTO request_index VALUES(?,?,?,?)",
                               (request_digest,receipt.admission_digest,bound_json,sha256(bound_json.encode()).hexdigest()))
                    db.execute("UPDATE attempts SET state='CANDIDATE_RECORDED' WHERE request_digest=?",
                               (request_digest,))
                db.commit()
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise ResultConflict("receipt already bound or database constraint failed") from exc
            except BaseException:
                db.rollback()
                raise
        return self.inspect(request_digest)

    def inspect(self, request_digest):
        digest(request_digest)
        with self._open() as db:
            db.execute("BEGIN")
            try:
                self._verify(db)
                attempt = db.execute("SELECT task_digest,state FROM attempts WHERE request_digest=?",
                                     (request_digest,)).fetchone()
                if attempt is None:
                    raise SourceUnavailable("request absent; absence is not permission to retry")
                row = db.execute("""SELECT i.admission_digest,i.bound_payload,i.bound_sha256,
                                     r.payload,r.payload_sha256
                                     FROM request_index i LEFT JOIN receipts r
                                     ON r.admission_digest=i.admission_digest
                                     WHERE i.request_digest=?""",(request_digest,)).fetchone()
                if row is None:
                    if attempt[1] != "UNKNOWN_REQUIRES_RECONCILIATION":
                        raise SourceRejected("recorded result missing")
                    return StoredCandidate(request_digest,attempt[1],None)
                if attempt[1] != "CANDIDATE_RECORDED" or row[3] is None:
                    raise SourceRejected("inconsistent index/receipt state")
                for body,pin in ((row[1],row[2]),(row[3],row[4])):
                    if sha256(body.encode()).hexdigest()!=pin:
                        raise SourceRejected("stored candidate digest mismatch")
                bound,raw_receipt = decode(row[1].encode()),decode(row[3].encode())
                receipt=RuntimeAdmission(**raw_receipt).validate()
                if (receipt.admission_digest!=row[0] or bound["runtime_admission"]!=raw_receipt
                        or bound["task_binding"]["task_digest"]!=attempt[0]
                        or bound["task_binding"]["provisioned_executor_digest"]!=receipt.provisioned_executor_digest):
                    raise SourceRejected("stored candidate semantic mismatch")
                return StoredCandidate(request_digest,attempt[1],row[1])
            finally:
                db.rollback()

    def resolve(self, *args, **kwargs):
        raise SourceUnavailable("candidate store is not a canonical runtime admission source")

    def record_canonical(self, *args, **kwargs):
        raise SourceUnavailable("canonical producer integration is not implemented")

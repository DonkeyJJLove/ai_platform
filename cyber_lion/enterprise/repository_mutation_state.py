"""Single-runtime restart-safe journal for repository attachment effects.

This SQLite journal is intentionally classified SINGLE_RUNTIME_ATTACH_ONLY. It is not
a globally linearizable multi-host effect store. The PEP additionally binds every
authority grant to one trusted runtime-scope pin before allowing an attach effect.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from threading import RLock

class RepositoryMutationStateError(RuntimeError):
    pass

CANONICAL_REPOSITORY_ATTACH_JOURNAL_PATH = "/var/lib/cyber-lion/repository-mutation/attach.sqlite3"
JOURNAL_SCOPE_CLASS = "SINGLE_RUNTIME_ATTACH_ONLY"
_ALLOWED_STATUS = {"PREPARED","APPLIED","FAILED_NO_EFFECT","RECONCILE_REQUIRED"}

@dataclass(frozen=True)
class RepositoryEffectState:
    effect_id:str
    authority_effect_key:str
    admission_id:str
    admission_digest:str
    intent_digest:str
    candidate_digest:str
    repository:str
    branch:str
    expected_head_sha:str
    expected_parent_sha:str
    candidate_commit_sha:str
    candidate_tree_sha:str
    verification_digest:str
    runtime_binding_digest:str
    live_admission_digest:str
    grant_id:str
    grant_digest:str
    authority_epoch:int
    status:str
    prepared_at:str
    effect_attempted_at:str|None
    observed_head_sha:str|None
    finalized_at:str|None
    def validate(self):
        required=(self.effect_id,self.authority_effect_key,self.admission_id,self.admission_digest,
          self.intent_digest,self.candidate_digest,self.repository,self.branch,self.expected_head_sha,
          self.expected_parent_sha,self.candidate_commit_sha,self.candidate_tree_sha,
          self.verification_digest,self.runtime_binding_digest,self.live_admission_digest,
          self.grant_id,self.grant_digest,self.prepared_at)
        if any(not isinstance(v,str) or not v for v in required):
            raise RepositoryMutationStateError("effect state contains invalid text")
        if not isinstance(self.authority_epoch,int) or isinstance(self.authority_epoch,bool) or self.authority_epoch<0:
            raise RepositoryMutationStateError("authority_epoch is invalid")
        if self.status not in _ALLOWED_STATUS:
            raise RepositoryMutationStateError("effect status is invalid")
        if self.status=="APPLIED":
            if self.observed_head_sha!=self.candidate_commit_sha or self.effect_attempted_at is None or self.finalized_at is None:
                raise RepositoryMutationStateError("APPLIED requires attempted exact candidate observation")
        if self.status=="FAILED_NO_EFFECT":
            if self.observed_head_sha!=self.expected_head_sha or self.effect_attempted_at is None or self.finalized_at is None:
                raise RepositoryMutationStateError("FAILED_NO_EFFECT requires attempted exact old-head observation")
        return self

class RepositoryAttachJournal:
    """Canonical local journal; deliberately not a distributed consensus store."""
    def __init__(self)->None:
        path=Path(CANONICAL_REPOSITORY_ATTACH_JOURNAL_PATH)
        path.parent.mkdir(parents=True,exist_ok=True)
        self._path=str(path)
        self._lock=RLock()
        self._initialize()
    @property
    def path(self): return self._path
    @property
    def scope_class(self): return JOURNAL_SCOPE_CLASS
    def _connect(self):
        c=sqlite3.connect(self._path,timeout=5,isolation_level=None,check_same_thread=False)
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")
        return c
    def _initialize(self):
        with self._lock, closing(self._connect()) as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS repository_attach_effect (
                effect_id TEXT PRIMARY KEY,
                authority_effect_key TEXT NOT NULL UNIQUE,
                admission_id TEXT NOT NULL UNIQUE,
                admission_digest TEXT NOT NULL UNIQUE,
                intent_digest TEXT NOT NULL,
                candidate_digest TEXT NOT NULL,
                repository TEXT NOT NULL,
                branch TEXT NOT NULL,
                expected_head_sha TEXT NOT NULL,
                expected_parent_sha TEXT NOT NULL,
                candidate_commit_sha TEXT NOT NULL,
                candidate_tree_sha TEXT NOT NULL,
                verification_digest TEXT NOT NULL,
                runtime_binding_digest TEXT NOT NULL,
                live_admission_digest TEXT NOT NULL,
                grant_id TEXT NOT NULL,
                grant_digest TEXT NOT NULL,
                authority_epoch INTEGER NOT NULL,
                status TEXT NOT NULL,
                prepared_at TEXT NOT NULL,
                effect_attempted_at TEXT,
                observed_head_sha TEXT,
                finalized_at TEXT
            );""")
    @staticmethod
    def _required(v,name):
        if not isinstance(v,str) or not v.strip(): raise RepositoryMutationStateError(f"{name} is required")
        return v
    def prepare(self, **kw):
        required=("effect_id","authority_effect_key","admission_id","admission_digest","intent_digest",
          "candidate_digest","repository","branch","expected_head_sha","expected_parent_sha",
          "candidate_commit_sha","candidate_tree_sha","verification_digest","runtime_binding_digest",
          "live_admission_digest","grant_id","grant_digest","prepared_at")
        for name in required: self._required(kw.get(name),name)
        epoch=kw.get("authority_epoch")
        if not isinstance(epoch,int) or isinstance(epoch,bool) or epoch<0: raise RepositoryMutationStateError("authority_epoch is invalid")
        vals=tuple(kw[n] for n in required[:-1])+(epoch,kw["prepared_at"])
        with self._lock, closing(self._connect()) as c:
            try:
                c.execute("BEGIN IMMEDIATE")
                c.execute("""INSERT INTO repository_attach_effect (
                effect_id,authority_effect_key,admission_id,admission_digest,intent_digest,candidate_digest,
                repository,branch,expected_head_sha,expected_parent_sha,candidate_commit_sha,candidate_tree_sha,
                verification_digest,runtime_binding_digest,live_admission_digest,grant_id,grant_digest,authority_epoch,
                status,prepared_at,effect_attempted_at,observed_head_sha,finalized_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'PREPARED',?,NULL,NULL,NULL)""", vals)
                c.execute("COMMIT")
            except sqlite3.IntegrityError as e:
                c.execute("ROLLBACK")
                raise RepositoryMutationStateError("effect, authority effect, or admission was already prepared") from e
        return self.get(kw["effect_id"])
    def get(self,effect_id):
        self._required(effect_id,"effect_id")
        with closing(self._connect()) as c:
            row=c.execute("""SELECT effect_id,authority_effect_key,admission_id,admission_digest,intent_digest,
            candidate_digest,repository,branch,expected_head_sha,expected_parent_sha,candidate_commit_sha,
            candidate_tree_sha,verification_digest,runtime_binding_digest,live_admission_digest,grant_id,
            grant_digest,authority_epoch,status,prepared_at,effect_attempted_at,observed_head_sha,finalized_at
            FROM repository_attach_effect WHERE effect_id=?""",(effect_id,)).fetchone()
        if row is None: raise RepositoryMutationStateError("repository effect is unknown")
        return RepositoryEffectState(*row).validate()
    def mark_attempted(self,effect_id,*,attempted_at):
        self._required(attempted_at,"attempted_at")
        with self._lock, closing(self._connect()) as c:
            c.execute("BEGIN IMMEDIATE")
            cur=c.execute("""UPDATE repository_attach_effect SET effect_attempted_at=?
              WHERE effect_id=? AND status='PREPARED' AND effect_attempted_at IS NULL""",(attempted_at,effect_id))
            if cur.rowcount!=1:
                c.execute("ROLLBACK"); raise RepositoryMutationStateError("repository effect cannot be attempted from current state")
            c.execute("COMMIT")
        return self.get(effect_id)
    def mark_failed_no_effect(self,effect_id,*,observed_head_sha,finalized_at):
        self._required(observed_head_sha,"observed_head_sha"); self._required(finalized_at,"finalized_at")
        with self._lock, closing(self._connect()) as c:
            c.execute("BEGIN IMMEDIATE")
            row=c.execute("SELECT status,expected_head_sha,effect_attempted_at FROM repository_attach_effect WHERE effect_id=?",(effect_id,)).fetchone()
            if row is None: c.execute("ROLLBACK"); raise RepositoryMutationStateError("repository effect is unknown")
            if row[0] not in {"PREPARED","RECONCILE_REQUIRED"} or row[2] is None:
                c.execute("ROLLBACK"); raise RepositoryMutationStateError("FAILED_NO_EFFECT requires prior effect attempt")
            if observed_head_sha!=row[1]:
                c.execute("ROLLBACK"); raise RepositoryMutationStateError("FAILED_NO_EFFECT requires exact old head")
            c.execute("UPDATE repository_attach_effect SET status='FAILED_NO_EFFECT',observed_head_sha=?,finalized_at=? WHERE effect_id=?",(observed_head_sha,finalized_at,effect_id))
            c.execute("COMMIT")
        return self.get(effect_id)
    def mark_reconcile_required(self,effect_id,*,observed_head_sha,finalized_at):
        self._required(finalized_at,"finalized_at")
        with self._lock, closing(self._connect()) as c:
            c.execute("BEGIN IMMEDIATE")
            row=c.execute("SELECT status FROM repository_attach_effect WHERE effect_id=?",(effect_id,)).fetchone()
            if row is None: c.execute("ROLLBACK"); raise RepositoryMutationStateError("repository effect is unknown")
            if row[0] not in {"PREPARED","RECONCILE_REQUIRED"}:
                c.execute("ROLLBACK"); raise RepositoryMutationStateError("repository effect cannot enter reconciliation")
            c.execute("UPDATE repository_attach_effect SET status='RECONCILE_REQUIRED',observed_head_sha=?,finalized_at=? WHERE effect_id=?",(observed_head_sha,finalized_at,effect_id))
            c.execute("COMMIT")
        return self.get(effect_id)
    def mark_applied(self,effect_id,*,observed_head_sha,finalized_at):
        self._required(observed_head_sha,"observed_head_sha"); self._required(finalized_at,"finalized_at")
        with self._lock, closing(self._connect()) as c:
            c.execute("BEGIN IMMEDIATE")
            row=c.execute("SELECT status,candidate_commit_sha,effect_attempted_at FROM repository_attach_effect WHERE effect_id=?",(effect_id,)).fetchone()
            if row is None: c.execute("ROLLBACK"); raise RepositoryMutationStateError("repository effect is unknown")
            if row[0] not in {"PREPARED","RECONCILE_REQUIRED"} or row[2] is None:
                c.execute("ROLLBACK"); raise RepositoryMutationStateError("APPLIED requires prior effect attempt")
            if observed_head_sha!=row[1]:
                c.execute("ROLLBACK"); raise RepositoryMutationStateError("APPLIED requires exact candidate observation")
            c.execute("UPDATE repository_attach_effect SET status='APPLIED',observed_head_sha=?,finalized_at=? WHERE effect_id=?",(observed_head_sha,finalized_at,effect_id))
            c.execute("COMMIT")
        return self.get(effect_id)

"""Durable E02 APP_SESSION replay+sequence candidate store.

This SQLite store is an OFFLINE_CANDIDATE evidence primitive. Replay-key
consumption and monotonic sequence advancement occur in one BEGIN IMMEDIATE
transaction. It grants no authority, holds no private key and cannot activate
runtime.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from cyber_lion.app_coordination.e02_app_session_attestation import AppSessionReplayKey
from cyber_lion.app_coordination.source_candidates import digest, text

DOMAIN=b"LION/E02/APP-SESSION-DURABLE-CONSUMPTION/1\0"

class AppSessionDurableStateError(ValueError): pass

def _canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

class DurableAppSessionStateStore:
    MODE="LION_E02_APP_SESSION_DURABLE_CANDIDATE_V1"

    @classmethod
    def create(cls,path):
        path=Path(path).resolve()
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("xb"): pass
        db=sqlite3.connect(path.as_uri()+"?mode=rw",uri=True,isolation_level=None,timeout=5)
        try:
            db.execute("PRAGMA synchronous=FULL");db.execute("PRAGMA foreign_keys=ON")
            db.executescript("""
            CREATE TABLE metadata(singleton INTEGER PRIMARY KEY CHECK(singleton=1), mode TEXT NOT NULL, store_id TEXT NOT NULL);
            CREATE TABLE sequence_state(provider_id TEXT NOT NULL, session_id TEXT NOT NULL, sequence INTEGER NOT NULL CHECK(sequence>0), durable_sequence_digest TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(provider_id,session_id));
            CREATE TABLE replay_ledger(replay_digest TEXT PRIMARY KEY, provider_id TEXT NOT NULL, session_id TEXT NOT NULL, sequence INTEGER NOT NULL CHECK(sequence>0), durable_sequence_digest TEXT NOT NULL, consumed_at TEXT NOT NULL, receipt_digest TEXT NOT NULL UNIQUE);
            """)
            db.execute("INSERT INTO metadata VALUES(1,?,?)",(cls.MODE,str(uuid4())));db.commit()
        finally: db.close()
        return cls(path)

    def __init__(self,path):
        self.path=Path(path).resolve(strict=True)
        with self._open() as db:self.store_id=self._identity(db)

    @contextmanager
    def _open(self):
        db=sqlite3.connect(self.path.as_uri()+"?mode=rw",uri=True,isolation_level=None,timeout=5)
        try:
            db.execute("PRAGMA foreign_keys=ON");db.execute("PRAGMA synchronous=FULL");yield db
        finally:db.close()

    def _identity(self,db):
        try:rows=db.execute("SELECT singleton,mode,store_id FROM metadata").fetchall()
        except sqlite3.Error as exc:raise AppSessionDurableStateError("durable APP_SESSION store unavailable") from exc
        if len(rows)!=1 or rows[0][0]!=1 or rows[0][1]!=self.MODE or not rows[0][2]:raise AppSessionDurableStateError("durable APP_SESSION store identity invalid")
        return rows[0][2]

    def _verify(self,db):
        if self._identity(db)!=self.store_id:raise AppSessionDurableStateError("durable APP_SESSION store identity drift")

    def consume(self,*,key,provider_id,session_id,sequence,durable_sequence_digest,consumed_at):
        if type(key) is not AppSessionReplayKey:raise AppSessionDurableStateError("exact APP_SESSION replay key required")
        for v in (provider_id,session_id,consumed_at):text(v)
        digest(durable_sequence_digest)
        if type(sequence) is not int or sequence<1 or sequence!=key.sequence:raise AppSessionDurableStateError("positive matching sequence required")
        if session_id!=key.session_id:raise AppSessionDurableStateError("session substitution")
        replay_digest=sha256(DOMAIN+_canon(asdict(key))).hexdigest()
        with self._open() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._verify(db)
                if db.execute("SELECT 1 FROM replay_ledger WHERE replay_digest=?",(replay_digest,)).fetchone() is not None:
                    raise AppSessionDurableStateError("durable replay rejected")
                row=db.execute("SELECT sequence FROM sequence_state WHERE provider_id=? AND session_id=?",(provider_id,session_id)).fetchone()
                previous=0 if row is None else int(row[0])
                if sequence<=previous:raise AppSessionDurableStateError("durable sequence rollback rejected")
                body={"store_id":self.store_id,"replay_digest":replay_digest,"provider_id":provider_id,"session_id":session_id,"previous_sequence":previous,"sequence":sequence,"durable_sequence_digest":durable_sequence_digest,"consumed_at":consumed_at}
                receipt=sha256(DOMAIN+_canon(body)).hexdigest()
                db.execute("INSERT INTO replay_ledger VALUES(?,?,?,?,?,?,?)",(replay_digest,provider_id,session_id,sequence,durable_sequence_digest,consumed_at,receipt))
                db.execute("INSERT INTO sequence_state VALUES(?,?,?,?,?) ON CONFLICT(provider_id,session_id) DO UPDATE SET sequence=excluded.sequence,durable_sequence_digest=excluded.durable_sequence_digest,updated_at=excluded.updated_at",(provider_id,session_id,sequence,durable_sequence_digest,consumed_at))
                db.execute("COMMIT")
                return receipt
            except BaseException:
                db.execute("ROLLBACK");raise

    def current_sequence(self,provider_id,session_id):
        text(provider_id);text(session_id)
        with self._open() as db:
            self._verify(db);row=db.execute("SELECT sequence,durable_sequence_digest,updated_at FROM sequence_state WHERE provider_id=? AND session_id=?",(provider_id,session_id)).fetchone()
            return None if row is None else (int(row[0]),row[1],row[2])

    authority_effect="NONE"
    runtime_effect="NONE"

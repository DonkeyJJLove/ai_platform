from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .models import canonical_json, normalize_run

SCHEMA = '''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS runs(
    run_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events(
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    ts REAL NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_run_ts ON events(run_id, ts, event_id);
CREATE TABLE IF NOT EXISTS metrics(
    run_id TEXT NOT NULL,
    name TEXT NOT NULL,
    ts REAL NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY(run_id, name)
);
CREATE TABLE IF NOT EXISTS participants(
    run_id TEXT NOT NULL,
    name TEXT NOT NULL,
    ts REAL NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY(run_id, name)
);
CREATE TABLE IF NOT EXISTS artifacts(
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    path TEXT,
    sha256 TEXT,
    size INTEGER,
    evidence_class TEXT,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id);
CREATE TABLE IF NOT EXISTS receipts(
    receipt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    path TEXT,
    sha256 TEXT,
    operation TEXT,
    status TEXT,
    ts REAL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_receipts_run ON receipts(run_id);
CREATE TABLE IF NOT EXISTS adapter_state(
    adapter_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at REAL NOT NULL
);
'''


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.lock:
            self.db.executescript(SCHEMA)
            self.db.commit()
        try:
            self.path.chmod(0o600)
        except FileNotFoundError:
            pass

    def close(self) -> None:
        with self.lock:
            self.db.close()

    def upsert_run(self, run: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(run, dict):
            raise TypeError("run must be an object")
        run_id = str(run.get("run_id") or "")
        with self.lock:
            existing = self.get_run(run_id) if run_id else None
            if existing:
                merged = dict(existing)
                for key, new_value in run.items():
                    if key == "run_id" or new_value is None:
                        continue
                    merged[key] = new_value
                value = normalize_run(merged)
            else:
                value = normalize_run(run)
            self.db.execute(
                "INSERT INTO runs(run_id,payload,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(run_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at",
                (value["run_id"], canonical_json(value), time.time()),
            )
            self.db.commit()
        return value

    def list_runs(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.db.execute("SELECT payload FROM runs ORDER BY updated_at DESC, run_id").fetchall()
        out = []
        for row in rows:
            value = json.loads(row[0])
            value["event_count"] = self._count("events", value["run_id"])
            value["artifact_count"] = self._count("artifacts", value["run_id"])
            value["receipt_count"] = self._count("receipts", value["run_id"])
            out.append(value)
        return out

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.db.execute("SELECT payload FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def _count(self, table: str, run_id: str) -> int:
        if table not in {"events", "artifacts", "receipts"}:
            raise ValueError("invalid table")
        with self.lock:
            row = self.db.execute(f"SELECT COUNT(*) FROM {table} WHERE run_id=?", (run_id,)).fetchone()
        return int(row[0])

    def append_event(self, event: dict[str, Any]) -> bool:
        raw = canonical_json(event)
        with self.lock:
            cur = self.db.execute(
                "INSERT OR IGNORE INTO events(event_id,run_id,ts,event_type,payload) VALUES(?,?,?,?,?)",
                (event["event_id"], event["run_id"], float(event["timestamp"]), event["event_type"], raw),
            )
            self.db.commit()
            inserted = cur.rowcount == 1
        return inserted

    def events(self, run_id: str) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.db.execute("SELECT payload FROM events WHERE run_id=? ORDER BY ts,event_id", (run_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def add_metric(self, run_id: str, name: str, value: Any, ts: float | None = None) -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO metrics(run_id,name,ts,payload) VALUES(?,?,?,?) "
                "ON CONFLICT(run_id,name) DO UPDATE SET ts=excluded.ts,payload=excluded.payload",
                (run_id, name, ts or time.time(), canonical_json(value)),
            )
            self.db.commit()

    def metrics(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            rows = self.db.execute("SELECT name,payload FROM metrics WHERE run_id=? ORDER BY name", (run_id,)).fetchall()
        out: dict[str, Any] = {}
        for row in rows:
            out[row[0]] = json.loads(row[1])
        return out

    def add_participant(self, run_id: str, name: str, value: Any, ts: float | None = None) -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO participants(run_id,name,ts,payload) VALUES(?,?,?,?) "
                "ON CONFLICT(run_id,name) DO UPDATE SET ts=excluded.ts,payload=excluded.payload",
                (run_id, name, ts or time.time(), canonical_json(value)),
            )
            self.db.commit()

    def participants(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            rows = self.db.execute("SELECT name,payload FROM participants WHERE run_id=? ORDER BY name", (run_id,)).fetchall()
        out: dict[str, Any] = {}
        for row in rows:
            out[row[0]] = json.loads(row[1])
        return out

    def add_artifact(self, run_id: str, artifact: dict[str, Any]) -> None:
        artifact_id = str(artifact["artifact_id"])
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO artifacts(artifact_id,run_id,path,sha256,size,evidence_class,payload) VALUES(?,?,?,?,?,?,?)",
                (artifact_id, run_id, artifact.get("path"), artifact.get("sha256"), artifact.get("size"), artifact.get("evidence_class"), canonical_json(artifact)),
            )
            self.db.commit()

    def artifacts(self, run_id: str) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.db.execute("SELECT payload FROM artifacts WHERE run_id=? ORDER BY artifact_id", (run_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def add_receipt(self, run_id: str, receipt: dict[str, Any]) -> None:
        receipt_id = str(receipt["receipt_id"])
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO receipts(receipt_id,run_id,path,sha256,operation,status,ts,payload) VALUES(?,?,?,?,?,?,?,?)",
                (receipt_id, run_id, receipt.get("path"), receipt.get("sha256"), receipt.get("operation"), receipt.get("status"), receipt.get("timestamp"), canonical_json(receipt)),
            )
            self.db.commit()

    def receipts(self, run_id: str) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.db.execute("SELECT payload FROM receipts WHERE run_id=? ORDER BY ts,receipt_id", (run_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def set_adapter_state(self, adapter_id: str, value: dict[str, Any]) -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO adapter_state(adapter_id,payload,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(adapter_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at",
                (adapter_id, canonical_json(value), time.time()),
            )
            self.db.commit()

    def adapter_state(self, adapter_id: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.db.execute("SELECT payload FROM adapter_state WHERE adapter_id=?", (adapter_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def export_run(self, run_id: str) -> dict[str, Any] | None:
        run = self.get_run(run_id)
        if run is None:
            return None
        return {
            "run": run,
            "events": self.events(run_id),
            "metrics": self.metrics(run_id),
            "participants": self.participants(run_id),
            "artifacts": self.artifacts(run_id),
            "receipts": self.receipts(run_id),
        }

    def export(self) -> dict[str, Any]:
        return {"runs": [self.export_run(run["run_id"]) for run in self.list_runs()]}

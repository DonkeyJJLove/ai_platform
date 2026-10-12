"""Durable single-use admission replay guard for original RuntimeAdmissionEngine.

Does not create or validate authority, policy, RuntimeAdmission or effects.
One dedicated SQLite file is used only for atomic replay-key consumption.
Construction performs private, bounded state initialization. Run only under
an approved protected release, NEVER from live read-only preflight.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import os
import re
import sqlite3
import stat

SCHEMA = "lion.r11.runtime-admission-replay/v1"
TABLE = "r11_runtime_admission_replay"
KEY = re.compile(r"^[0-9a-f]{64}$")


class R11AdmissionReplayError(RuntimeError):
    pass


def _need(ok: bool, reason: str) -> None:
    if not ok:
        raise R11AdmissionReplayError(reason)


def _parent(path: Path) -> Path:
    p = path.parent
    _need(path.is_absolute() and not path.is_symlink(), "replay path must be direct absolute")
    try:
        resolved = p.resolve(strict=True)
        s = p.lstat()
    except OSError as exc:
        raise R11AdmissionReplayError("replay parent unavailable") from exc
    _need(resolved == p and stat.S_ISDIR(s.st_mode)
          and not (s.st_mode & 0o022), "replay parent not private or indirect")
    return p


def _identity(path: Path) -> tuple[int, int]:
    _need(not path.is_symlink(), "replay SQLite symlink denied")
    try:
        s = path.lstat()
    except OSError as exc:
        raise R11AdmissionReplayError("replay SQLite unavailable") from exc
    _need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, "replay SQLite file type")
    _need(s.st_uid in (0, os.geteuid()) and not (s.st_mode & 0o077),
          "replay SQLite owner/mode not private")
    return s.st_dev, s.st_ino


def _connect(path: Path):
    # mode=rw avoids silently creating a new replay DB after inode drift.
    return sqlite3.connect(
        "file:" + quote(path.as_posix(), safe="/") + "?mode=rw",
        uri=True,
        isolation_level=None,
        timeout=5,
    )


class SQLiteR11RuntimeAdmissionReplayGuard:
    """Persistent exactly-once replay boundary for original RuntimeAdmissionEngine."""

    def __init__(self, path: Path | str):
        p = Path(path)
        _parent(p)
        if not p.exists():
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                fd = os.open(p, flags, 0o600)
            except FileExistsError:
                pass
            except OSError as exc:
                raise R11AdmissionReplayError("replay SQLite create denied") from exc
            else:
                os.close(fd)
        self.path = p
        self._file_identity = _identity(p)
        with closing(_connect(p)) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "CREATE TABLE IF NOT EXISTS r11_runtime_admission_replay ("
                    "replay_key TEXT PRIMARY KEY, consumed_at TEXT NOT NULL, "
                    "schema_id TEXT NOT NULL)"
                )
                columns = tuple(row[1] for row in db.execute(
                    "PRAGMA table_info(r11_runtime_admission_replay)"
                ))
                _need(columns == ("replay_key", "consumed_at", "schema_id"),
                      "replay SQLite schema incompatible")
                db.execute("COMMIT")
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        self.verify_identity()

    def verify_identity(self) -> None:
        _parent(self.path)
        _need(_identity(self.path) == self._file_identity,
              "replay SQLite identity drift")

    def consume(self, replay_key: str) -> bool:
        _need(type(replay_key) is str and KEY.fullmatch(replay_key) is not None,
              "canonical admission replay digest required")
        self.verify_identity()
        consumed = False
        try:
            with closing(_connect(self.path)) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute(
                        "INSERT INTO r11_runtime_admission_replay VALUES(?,?,?)",
                        (replay_key, datetime.now(timezone.utc).isoformat(), SCHEMA),
                    )
                    db.execute("COMMIT")
                    consumed = True
                except sqlite3.IntegrityError:
                    if db.in_transaction:
                        db.execute("ROLLBACK")
                    consumed = False
                except Exception:
                    if db.in_transaction:
                        db.execute("ROLLBACK")
                    raise
        except sqlite3.Error as exc:
            raise R11AdmissionReplayError("persistent replay state unavailable") from exc
        self.verify_identity()
        return consumed

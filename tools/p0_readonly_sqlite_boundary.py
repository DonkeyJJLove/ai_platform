from __future__ import annotations
import os,sqlite3,stat
from pathlib import Path

class ReadOnlySQLiteBoundaryError(RuntimeError):pass

def open_readonly_sqlite(path:str):
    p=Path(path)
    if not p.is_absolute():raise ReadOnlySQLiteBoundaryError("database path must be absolute")
    try:st=os.lstat(p)
    except FileNotFoundError as exc:raise ReadOnlySQLiteBoundaryError("database unavailable") from exc
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):raise ReadOnlySQLiteBoundaryError("database identity unsafe")
    uri=p.resolve().as_uri()+"?mode=ro"
    try:c=sqlite3.connect(uri,uri=True,timeout=5,isolation_level=None,check_same_thread=False)
    except sqlite3.Error as exc:raise ReadOnlySQLiteBoundaryError("read-only database open failed") from exc
    try:
        c.execute("PRAGMA query_only=ON")
        row=c.execute("PRAGMA query_only").fetchone()
        if row is None or int(row[0])!=1:raise ReadOnlySQLiteBoundaryError("query_only enforcement failed")
        return c
    except Exception:
        c.close();raise

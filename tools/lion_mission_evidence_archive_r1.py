"""LION reversible mission evidence archival: source backup + typed reasoning index.

No mission DB state change, no deletion, no scheduler, no SaaS replay.
The authority/effect of an archive receipt is always NONE.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
import uuid

SCHEMA = "lion.mission-evidence-archive/v1"
TRAIL_SCHEMA = "lion.mission-reasoning-trail/v1"
TERMINAL = frozenset(("COMPLETE", "SUPERSEDED"))
ARCHIVE_ID = re.compile(r"[a-z0-9][a-z0-9-]{3,70}\Z")
DATE_FMT = "%Y-%m-%dT%H:%M:%S.%f%z"


class ArchiveError(RuntimeError):
    pass


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def digest(obj):
    return sha256(canonical(obj)).hexdigest()


def file_sha(path):
    h = sha256()
    with Path(path).open("rb") as fp:
        for buf in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(buf)
    return h.hexdigest()


def open_readonly(db):
    p = Path(db)
    if not p.is_file() or p.is_symlink() or p.name != "mission-control-v3.db":
        raise ArchiveError("CANONICAL_DB_PATH_REQUIRED")
    c = sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True, timeout=15)
    c.execute("PRAGMA query_only=ON")
    return c


def _table_names(conn):
    return [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def _mission_ids(conn):
    required = {
        "mission_id", "title", "state", "runtime_state",
        "source_head", "source_tree", "spec_digest",
        "created_at", "updated_at"
    }
    columns = {row[1] for row in conn.execute("PRAGMA table_info(missions)")}
    if not required.issubset(columns):
        raise ArchiveError("MISSIONS_SCHEMA_MISSING_FIELDS")
    missions = [
        dict(zip(
            ("mission_id", "title", "state", "runtime_state", "source_head",
             "source_tree", "spec_digest", "created_at", "updated_at"),
            row,
        ))
        for row in conn.execute(
            "SELECT mission_id,title,state,runtime_state,source_head,source_tree,"
            "spec_digest,created_at,updated_at FROM missions ORDER BY mission_id"
        )
    ]
    seen = set()
    for mission in missions:
        if not mission["mission_id"] or mission["mission_id"] in seen:
            raise ArchiveError("MISSIONS_DUPLICATE_OR_INVALID_ID")
        seen.add(mission["mission_id"])
    terminal = [m for m in missions if m["state"] in TERMINAL]
    protected = [m for m in missions if m["state"] not in TERMINAL]
    return terminal, protected


def describe_snapshot(conn, *, expect_terminal=None, expect_protected=None):
    integrity = conn.execute("PRAGMA quick_check(1)").fetchone()
    if not integrity or integrity[0] != "ok":
        raise ArchiveError("SQLITE_INTEGRITY_UNKNOWN")
    terminal, protected = _mission_ids(conn)
    if (expect_terminal is not None and len(terminal) != expect_terminal or
        expect_protected is not None and len(protected) != expect_protected):
        raise ArchiveError("MISSION_COUNTS_DRIFT_REFUSE_ARCHIVE")
    terminal_ids = {m["mission_id"] for m in terminal}
    protected_ids = {m["mission_id"] for m in protected}
    if terminal_ids & protected_ids:
        raise ArchiveError("NONTERMINAL_OVERLAP")
    all_ids = terminal_ids | protected_ids
    evidence_counts = defaultdict(dict)
    orphan_rows = {}
    scanned_tables = []
    for name in _table_names(conn):
        cols = [row[1] for row in conn.execute('PRAGMA table_info("' + name + '")')]
        if "mission_id" not in cols:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_]+", name):
            raise ArchiveError("UNSAFE_TABLE_IDENTIFIER")
        groups = conn.execute(
            'SELECT mission_id, COUNT(*) FROM "' + name + '" GROUP BY mission_id'
        )
        count_orphans = 0
        for mid, n in groups:
            if mid is None:
                continue
            if mid not in all_ids:
                count_orphans += int(n)
            elif mid in terminal_ids:
                evidence_counts[mid][name] = int(n)
        scanned_tables.append(name)
        if count_orphans:
            orphan_rows[name] = count_orphans
    if orphan_rows:
        raise ArchiveError("ORPHAN_MISSION_REFERENCES_REQUIRE_REVIEW")

    events = defaultdict(Counter)
    for event_table in ("mission_events", "operator_events"):
        if event_table not in scanned_tables:
            continue
        cols = {row[1] for row in conn.execute("PRAGMA table_info(" + event_table + ")")}
        if "event_type" not in cols:
            continue
        for mid, kind, n in conn.execute(
            "SELECT mission_id,event_type,COUNT(*) FROM " + event_table +
            " GROUP BY mission_id,event_type"
        ):
            if mid in terminal_ids:
                events[mid][str(kind or "UNKNOWN")[:125]] += int(n)

    model_calls = defaultdict(Counter)
    if "mission_model_calls" in scanned_tables:
        for mid, provider, state, n in conn.execute(
            "SELECT mission_id,provider,state,COUNT(*) FROM mission_model_calls "
            "GROUP BY mission_id,provider,state"
        ):
            if mid in terminal_ids:
                key = str(provider or "UNKNOWN")[:90] + "/" + str(state or "UNKNOWN")[:65]
                model_calls[mid][key] += int(n)

    trails = []
    for mission in terminal:
        mid = mission["mission_id"]
        trail = {
            "schema": TRAIL_SCHEMA,
            "mission_id": mid,
            "terminal_state": mission["state"],
            "runtime_state": mission["runtime_state"],
            "title": mission["title"],
            "source_head": mission["source_head"],
            "source_tree": mission["source_tree"],
            "spec_digest": mission["spec_digest"],
            "created_at": mission["created_at"],
            "updated_at": mission["updated_at"],
            "evidence_counts": dict(sorted(evidence_counts[mid].items())),
            "observed_event_type_counts": dict(sorted(events[mid].items())),
            "model_provider_state_counts": dict(sorted(model_calls[mid].items())),
            "hypothesis_reconstruction": "UNKNOWN_NOT_STRUCTURED_IN_PREVIOUS_RECORD",
            "inference_reconstruction": "UNKNOWN_NOT_STRUCTURED_IN_PREVIOUS_RECORD",
            "authority_effect": "NONE",
            "archival_effect": "COPY_ONLY_NOT_A_MISSION_COMPLETION_RECEIPT",
        }
        trails.append({**trail, "trail_digest": digest(trail)})
    # The original full SQLite snapshot remains the byte-preserving source for
    # event content, rejected hypotheses, model receipts and historical contexts.
    return {
        "terminal_count": len(terminal),
        "protected_count": len(protected),
        "terminal_states": dict(sorted(Counter(m["state"] for m in terminal).items())),
        "protected_states": dict(sorted(Counter(m["state"] for m in protected).items())),
        "terminal_mission_ids": sorted(terminal_ids),
        "protected_mission_ids": sorted(protected_ids),
        "tables_with_mission_id": scanned_tables,
        "evidence_count_totals": dict(sorted(Counter({
            name: sum(evidence_counts[mid].get(name, 0) for mid in terminal_ids)
            for name in scanned_tables
        }).items())),
        "trails": trails,
    }


def _write_private(path, data):
    path = Path(path)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def verify_archive(archive):
    root = Path(archive)
    manifest_path, snapshot_path, trails_path = [
        root / name for name in ("manifest.json", "snapshot.sqlite3", "reasoning_trails.jsonl")
    ]
    if not root.is_dir() or root.is_symlink():
        raise ArchiveError("ARCHIVE_DIR_MISSING_OR_SYMLINK")
    for p in (manifest_path, snapshot_path, trails_path):
        if not p.is_file() or p.is_symlink():
            raise ArchiveError("ARCHIVE_INCOMPLETE")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    identity = manifest.pop("manifest_digest", None)
    if manifest.get("schema") != SCHEMA or identity != digest(manifest):
        raise ArchiveError("MANIFEST_DIGEST_INVALID")
    if file_sha(snapshot_path) != manifest["snapshot_sha256"]:
        raise ArchiveError("SQLITE_BYTES_CHANGED")
    if file_sha(trails_path) != manifest["trails_sha256"]:
        raise ArchiveError("TRAIL_BYTES_CHANGED")
    conn = sqlite3.connect(snapshot_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=8)
    try:
        conn.execute("PRAGMA query_only=ON")
        if conn.execute("PRAGMA quick_check(1)").fetchone()[0] != "ok":
            raise ArchiveError("ARCHIVE_SQLITE_INTEGRITY_INVALID")
        terminal, protected = _mission_ids(conn)
        if sorted(m["mission_id"] for m in terminal) != manifest["terminal_mission_ids"]:
            raise ArchiveError("ARCHIVE_MISSION_LINEAGE_MISMATCH")
        if sorted(m["mission_id"] for m in protected) != manifest["protected_mission_ids"]:
            raise ArchiveError("ARCHIVE_PROTECTED_LINEAGE_MISMATCH")
    finally:
        conn.close()
    count = 0
    with trails_path.open(encoding="utf-8") as fp:
        for line in fp:
            row = json.loads(line)
            stated = row.pop("trail_digest", None)
            if digest(row) != stated:
                raise ArchiveError("TRAIL_DIGEST_INVALID")
            count += 1
    if count != manifest["terminal_count"]:
        raise ArchiveError("ARCHIVE_TRAIL_CARDINALITY_INVALID")
    return {"result": "PASS_VERIFIED_ARCHIVE_READBACK",
            "archive_id": manifest["archive_id"],
            "terminal_count": manifest["terminal_count"],
            "protected_count": manifest["protected_count"],
            "sqlite_sha256": manifest["snapshot_sha256"],
            "manifest_digest": identity, "authority_effect": "NONE"}


def archive(db, archive_root, archive_id, *, expected_terminal, expected_protected,
            clock=lambda: datetime.now(timezone.utc)):
    if not ARCHIVE_ID.fullmatch(archive_id):
        raise ArchiveError("ARCHIVE_ID_INVALID")
    root = Path(archive_root)
    if root.exists() and (not root.is_dir() or root.is_symlink()):
        raise ArchiveError("ARCHIVE_ROOT_INVALID")
    # Never use the live mission DB directory as an archive root.
    if root.resolve() == Path(db).parent.resolve():
        raise ArchiveError("ARCHIVE_ROOT_EQUALS_DB_DIRECTORY")
    final = root / archive_id
    if final.exists():
        return {**verify_archive(final), "idempotent_existing": True}
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    stage = root / (".stage-" + archive_id)
    if stage.exists():
        raise ArchiveError("PENDING_STAGE_REQUIRES_RECONCILIATION")
    stage.mkdir(mode=0o700)
    conn = open_readonly(db)
    try:
        # Consistent SQLite live backup; the source connection is mode=ro.
        destination = stage / "snapshot.sqlite3"
        target = sqlite3.connect(destination)
        try:
            conn.backup(target, pages=2048, sleep=0.05)
        finally:
            target.close()
    finally:
        conn.close()
    os.chmod(destination, 0o600)
    backup = sqlite3.connect(destination.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        backup.execute("PRAGMA query_only=ON")
        details = describe_snapshot(
            backup, expect_terminal=expected_terminal,
            expect_protected=expected_protected
        )
    finally:
        backup.close()
    trails_bytes = b"".join(
        canonical(row) + b"\n" for row in details.pop("trails")
    )
    _write_private(stage / "reasoning_trails.jsonl", trails_bytes)
    instant = clock()
    payload = {
        "schema": SCHEMA, "archive_id": archive_id,
        "created_at": instant.isoformat(),
        "source_class": "CONSISTENT_SQLITE_READONLY_SNAPSHOT",
        "source_db_basename": Path(db).name,
        "source_db_bytes_not_deleted": True,
        "source_mission_state_not_modified": True,
        "authority_effect": "NONE",
        "runtime_mission_effect": "NONE",
        "terminal_classifier": sorted(TERMINAL),
        "snapshot_sha256": file_sha(destination),
        "snapshot_size": destination.stat().st_size,
        "trails_sha256": sha256(trails_bytes).hexdigest(),
        "trails_bytes": len(trails_bytes),
        **details,
    }
    _write_private(stage / "manifest.json",
                   canonical({**payload, "manifest_digest": digest(payload)}) + b"\n")
    verified = verify_archive(stage)
    os.rename(stage, final)
    verified_final = verify_archive(final)
    if verified != verified_final:
        raise ArchiveError("POST_PROMOTION_ARCHIVE_DRIFT")
    return {**verified_final, "archive_dir": str(final),
            "idempotent_existing": False}


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--db", required=True)
    cli.add_argument("--root", required=True)
    cli.add_argument("--archive-id", required=True)
    cli.add_argument("--expected-terminal", type=int, required=True)
    cli.add_argument("--expected-protected", type=int, required=True)
    cli.add_argument("--execute", action="store_true")
    options = cli.parse_args(argv)
    if options.execute:
        receipt = archive(options.db, options.root, options.archive_id,
                          expected_terminal=options.expected_terminal,
                          expected_protected=options.expected_protected)
    else:
        c = open_readonly(options.db)
        try:
            summary = describe_snapshot(c, expect_terminal=options.expected_terminal,
                                        expect_protected=options.expected_protected)
        finally:
            c.close()
        receipt = {"result": "PASS_ARCHIVE_PLAN_SOURCE_ONLY",
                   "terminal_count": summary["terminal_count"],
                   "protected_count": summary["protected_count"],
                   "archive_id": options.archive_id,
                   "effect": "NONE", "snapshotted": False}
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ArchiveError, OSError, sqlite3.Error) as e:
        print(json.dumps({"result": "BLOCKED", "error_class": type(e).__name__,
                          "reason": str(e)[:160], "authority_effect": "NONE"}))
        raise SystemExit(19)

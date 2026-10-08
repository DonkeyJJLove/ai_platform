"""Append-only, provenance-typed reasoning journal for LION operations.

Source is independent of authority and never calls an external executor.
It cannot promote model statements to real runtime observations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import re
import stat

SCHEMA = "lion.reasoning-lineage-event/v1"
CASE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{3,159}\Z")
EVENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{3,159}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
CLASSES = frozenset(("SOURCE_FACT", "RUNTIME_OBSERVATION", "TEST_RESULT",
                     "HYPOTHESIS", "FALSIFICATION", "DECISION", "UNKNOWN"))
STATUSES = frozenset(("PASS", "FAIL", "UNKNOWN", "REJECTED", "NOT_RUN", "OBSERVED"))
MAX_EVENT_BYTES = 16384
MAX_JOURNAL_BYTES = 4 * 1024 * 1024
EVIDENCE_REQUIRED = frozenset(("SOURCE_FACT", "RUNTIME_OBSERVATION",
                                "TEST_RESULT", "FALSIFICATION"))


class JournalError(ValueError):
    pass


def canonical(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(v):
    return sha256(canonical(v)).hexdigest()


def _check_event(event):
    if not isinstance(event, dict):
        raise JournalError("EXACT_EVENT_DICT_REQUIRED")
    required = {
        "case_id", "event_id", "classification", "status", "statement",
        "evidence_refs", "counterevidence_refs", "observed_at",
        "mission_id", "conversation_id", "binding_epoch", "source_head"
    }
    if set(event) != required:
        raise JournalError("EVENT_FIELDS_UNEXPECTED_OR_MISSING")
    if not CASE.fullmatch(str(event["case_id"])) or not EVENT.fullmatch(str(event["event_id"])):
        raise JournalError("CASE_OR_EVENT_ID_INVALID")
    if event["classification"] not in CLASSES or event["status"] not in STATUSES:
        raise JournalError("CLASSIFICATION_OR_STATUS_UNKNOWN")
    if not isinstance(event["statement"], str) or not 1 <= len(event["statement"]) <= 1200:
        raise JournalError("CLAIM_BOUND_INVALID")
    if any(c in event["statement"] for c in ("\0", "\r")):
        raise JournalError("CONTROL_CHARACTERS_DENIED")
    for name in ("evidence_refs", "counterevidence_refs"):
        refs = event[name]
        if not isinstance(refs, list) or len(refs) > 16:
            raise JournalError("EVIDENCE_REF_CARDINALITY")
        if any(not isinstance(r, str) or not SHA.fullmatch(r) for r in refs):
            raise JournalError("EVIDENCE_REF_DIGEST_INVALID")
        if len(refs) != len(set(refs)):
            raise JournalError("EVIDENCE_REF_DUPLICATE")
    if event["classification"] in EVIDENCE_REQUIRED and not event["evidence_refs"]:
        raise JournalError("OBSERVATION_REQUIRES_SOURCE_DIGEST")
    if event["status"] == "PASS" and event["classification"] not in ("TEST_RESULT",):
        raise JournalError("PASS_ONLY_VALID_FOR_TEST_RESULT")
    if event["classification"] == "HYPOTHESIS" and event["status"] == "OBSERVED":
        raise JournalError("HYPOTHESIS_NOT_OBSERVATION")
    try:
        parsed = datetime.fromisoformat(event["observed_at"])
        if parsed.tzinfo is None:
            raise ValueError()
    except (ValueError, TypeError):
        raise JournalError("OBSERVATION_TIMESTAMP_REQUIRED") from None
    for k in ("mission_id", "conversation_id"):
        if event[k] is not None and (not isinstance(event[k], str) or
                                    not CASE.fullmatch(event[k])):
            raise JournalError("IDENTITY_INVALID")
    if event["binding_epoch"] is not None and (type(event["binding_epoch"]) is not int or
                                              event["binding_epoch"] < 1):
        raise JournalError("BINDING_EPOCH_INVALID")
    if event["source_head"] is not None and (not isinstance(event["source_head"], str) or
                                             not re.fullmatch(r"[a-f0-9]{40}", event["source_head"])):
        raise JournalError("SOURCE_HEAD_INVALID")
    # User-facing text is an epistemic statement, never a command.
    return dict(event)


def _filename(root, case_id):
    if not CASE.fullmatch(case_id):
        raise JournalError("CASE_ID_INVALID")
    return Path(root) / (sha256(case_id.encode()).hexdigest()[:32] + ".jsonl")


def _scan(data, case_id):
    head = "0" * 64
    seen = {}
    count = 0
    if len(data) > MAX_JOURNAL_BYTES:
        raise JournalError("JOURNAL_SIZE_CAP")
    for line in data.splitlines():
        if not line:
            raise JournalError("EMPTY_EVENT_LINE")
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise JournalError("JOURNAL_RECORD_INVALID") from None
        hashed = row.pop("event_digest", None)
        if not isinstance(hashed, str) or not SHA.fullmatch(hashed):
            raise JournalError("EVENT_DIGEST_MISSING")
        if row.get("schema") != SCHEMA or row.get("previous_digest") != head:
            raise JournalError("REASONING_CAUSAL_CHAIN_BROKEN")
        payload = row.get("payload")
        _check_event(payload)
        if payload["case_id"] != case_id:
            raise JournalError("CASE_MISMATCH")
        if digest(row) != hashed:
            raise JournalError("EVENT_TAMPERED")
        eid = payload["event_id"]
        if eid in seen:
            raise JournalError("DUPLICATE_EVENT_ID")
        seen[eid] = (digest(payload), hashed)
        head = hashed
        count += 1
    return count, head, seen


def read_journal(root, case_id):
    filename = _filename(root, case_id)
    if not filename.exists():
        return {"status": "EMPTY", "events": 0, "head_digest": "0"*64,
                "authority_effect": "NONE"}
    if filename.is_symlink() or not filename.is_file():
        raise JournalError("SYMLINK_OR_NONFILE_JOURNAL")
    count, head, _ = _scan(filename.read_bytes(), case_id)
    return {"status": "VERIFIED", "events": count, "head_digest": head,
            "authority_effect": "NONE"}


def append_event(root, event):
    payload = _check_event(event)
    directory = Path(root)
    if directory.exists() and (not directory.is_dir() or directory.is_symlink()):
        raise JournalError("JOURNAL_ROOT_INVALID")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    target = _filename(directory, payload["case_id"])
    if target.is_symlink():
        raise JournalError("JOURNAL_SYMLINK_DENIED")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(target, flags, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_JOURNAL_BYTES:
            raise JournalError("JOURNAL_FILE_INVALID")
        os.lseek(fd, 0, os.SEEK_SET)
        original = b""
        while buf := os.read(fd, 65536):
            original += buf
            if len(original) > MAX_JOURNAL_BYTES:
                raise JournalError("JOURNAL_SIZE_CAP")
        count, previous, seen = _scan(original, payload["case_id"])
        event_hash = digest(payload)
        existing = seen.get(payload["event_id"])
        if existing is not None:
            if existing[0] != event_hash:
                raise JournalError("EVENT_ID_CONFLICT")
            return {"result": "PASS_IDEMPOTENT_ALREADY_RECORDED",
                    "events": count, "head_digest": previous, "authority_effect": "NONE"}
        entry = {"schema": SCHEMA, "previous_digest": previous, "payload": payload}
        data = canonical({**entry, "event_digest": digest(entry)}) + b"\n"
        if len(data) > MAX_EVENT_BYTES or len(original) + len(data) > MAX_JOURNAL_BYTES:
            raise JournalError("EVENT_OR_JOURNAL_TOO_LARGE")
        os.lseek(fd, 0, os.SEEK_END)
        n = os.write(fd, data)
        if n != len(data):
            raise JournalError("SHORT_APPEND_UNCERTAIN_RECONCILE")
        os.fsync(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        full = b""
        while buf := os.read(fd, 65536):
            full += buf
        new_count, new_head, _ = _scan(full, payload["case_id"])
        if new_count != count + 1 or new_head != digest(entry):
            raise JournalError("POST_APPEND_RECONCILIATION_FAILED")
        return {"result": "PASS_RECORDED_AND_RECONCILED",
                "events": new_count, "head_digest": new_head,
                "authority_effect": "NONE"}
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def event(*, case_id, event_id, classification, status, statement, evidence_refs,
          counterevidence_refs=None, observed_at=None, mission_id=None,
          conversation_id=None, binding_epoch=None, source_head=None):
    return {
        "case_id": case_id, "event_id": event_id,
        "classification": classification, "status": status,
        "statement": statement,
        "evidence_refs": list(evidence_refs),
        "counterevidence_refs": list(counterevidence_refs or []),
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat(),
        "mission_id": mission_id, "conversation_id": conversation_id,
        "binding_epoch": binding_epoch, "source_head": source_head,
    }

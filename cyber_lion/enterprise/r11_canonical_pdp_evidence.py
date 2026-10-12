"""R11: durable canonical PDP evidence, with ORIGINAL issuer/reader separation.

An original CanonicalPolicyDecisionPoint produces a PDPResult after canonical
LiveAuthorityAdmission. The *publisher* verifies this exact result is cached
by that same original process owner and persists a bounded digest-sealed
projection into a private SQLite database.

The independent *reader* is read-only. It reconstructs and validates only
that original projection for the RuntimeAdmissionEngine and consults an
independent, current policy source. It never calls a PDP, issues an authority
grant, creates a fallback ALLOW or produces a RuntimeAdmission.

The publisher persists only already-issued records under a separately
approved upstream service/release and preprovisioned private schema. Do not run
against production during read-only discovery. No production claim without a
trusted actual PDP issuer, installation binding, and original governance.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from typing import Callable
from urllib.parse import quote

from cyber_lion.contracts.runtime_enforcement import (
    CanonicalPDPDecisionEvidence,
    PDPSourceTrustBinding,
)
from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.enterprise.policy_gate import CanonicalPolicyDecisionPoint, PDPResult
from cyber_lion.enterprise.runtime_enforcement import _pdp_receipt_digest

SCHEMA = "lion.r11.original-pdp-evidence-sqlite/v1"
TABLE = "r11_original_pdp_evidence"
MAX_TTL_SECONDS = 600
IDENT = re.compile(r"^[\w.:-]{1,256}$")
STRUCTURE = ("request_id", "gate_event_id", "record_json")
RECORD_FIELDS = frozenset(field.name for field in fields(CanonicalPDPDecisionEvidence))


class R11CanonicalPDPSourceError(RuntimeError):
    pass


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise R11CanonicalPDPSourceError(reason)


def _safe_file(value: Path | str, *, must_exist: bool) -> tuple[Path, tuple[int, int] | None]:
    path = Path(value)
    _need(path.is_absolute() and not path.is_symlink(),
          "canonical PDP SQLite path must be direct absolute")
    parent = path.parent
    try:
        ps = parent.lstat()
        _need(parent.resolve(strict=True) == parent and stat.S_ISDIR(ps.st_mode)
              and not (ps.st_mode & 0o022),
              "canonical PDP SQLite parent not private or indirect")
    except OSError as exc:
        raise R11CanonicalPDPSourceError("canonical PDP SQLite parent unavailable") from exc
    if not path.exists():
        _need(not must_exist, "canonical PDP evidence unavailable")
        return path, None
    try:
        stat_result = path.lstat()
    except OSError as exc:
        raise R11CanonicalPDPSourceError("canonical PDP evidence unavailable") from exc
    _need(stat.S_ISREG(stat_result.st_mode) and stat_result.st_nlink == 1
          and stat_result.st_uid in {0, os.geteuid()}
          and not (stat_result.st_mode & 0o077)
          and path.resolve(strict=True) == path,
          "canonical PDP evidence SQLite owner/type/path denied")
    return path, (stat_result.st_dev, stat_result.st_ino)


def _conn(path: Path, *, read_only: bool) -> sqlite3.Connection:
    mode = "ro" if read_only else "rw"
    uri = "file:" + quote(path.as_posix(), safe="/") + "?mode=" + mode
    db = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=4)
    if read_only:
        db.execute("PRAGMA query_only=ON")
    return db


def _schema(db: sqlite3.Connection) -> None:
    rows = db.execute("PRAGMA table_info(r11_original_pdp_evidence)").fetchall()
    _need(tuple(x[1] for x in rows) == STRUCTURE,
          "canonical PDP evidence schema mismatch")
    _need(tuple(x[2] for x in rows) == ("TEXT", "TEXT", "TEXT"),
          "canonical PDP evidence column types mismatch")
    _need(tuple(x[5] for x in rows)[:2] == (1, 2),
          "canonical PDP evidence keys mismatch")


def _strict_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise R11CanonicalPDPSourceError("duplicate canonical PDP evidence field")
        result[key] = value
    return result


def _now(value: datetime) -> datetime:
    _need(type(value) is datetime and value.tzinfo is not None,
          "canonical PDP trusted clock unavailable")
    return value.astimezone(timezone.utc)


def _identity_tuple(value) -> tuple[str, str, str, str, str]:
    return tuple(getattr(value, n, None) for n in (
        "source_id", "source_instance_id", "implementation_digest",
        "trust_anchor_id", "trust_anchor_digest",
    ))


@dataclass(frozen=True)
class OriginalPDPIssuanceObservation:
    """Exact source-owned issue window; never a grant or signature substitute."""

    request_id: str
    gate_event_id: str
    gate_decision_digest: str
    policy_binding: str
    issued_at: str
    expires_at: str
    source_id: str
    source_instance_id: str
    source_implementation_digest: str
    trust_anchor_id: str
    trust_anchor_digest: str

    def validate(self) -> "OriginalPDPIssuanceObservation":
        for value in (self.request_id,self.gate_event_id,self.policy_binding,
                      self.source_id,self.source_instance_id,self.trust_anchor_id):
            _need(type(value) is str and bool(value),
                  "original PDP issuance observation identity")
        for value in (self.gate_decision_digest,self.source_implementation_digest,
                      self.trust_anchor_digest):
            _need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}",value) is not None,
                  "original PDP issuance observation digest")
        try:
            start = datetime.fromisoformat(self.issued_at.replace("Z","+00:00"))
            end = datetime.fromisoformat(self.expires_at.replace("Z","+00:00"))
        except (ValueError,TypeError,AttributeError) as exc:
            raise R11CanonicalPDPSourceError("original PDP issuance observation timestamp") from exc
        _need(start.tzinfo is not None and end.tzinfo is not None
              and _now(start) < _now(end),
              "original PDP issuance observation interval")
        return self


class SQLiteR11CanonicalPDPEvidenceReader:
    """Read-only consumer of existing exact original-PDP evidence bytes."""

    def __init__(
        self,
        *,
        database: Path | str,
        source_trust: PDPSourceTrustBinding,
        current_policy_source: Callable[[str], str],
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        _need(type(source_trust) is PDPSourceTrustBinding, "original PDP trust required")
        source_trust.validate()
        _need(callable(current_policy_source),
              "independent current policy source required")
        _need(callable(now_fn), "trusted clock required")
        self.path, self._inode = _safe_file(database, must_exist=True)
        self.source_id = source_trust.source_id
        self.source_instance_id = source_trust.source_instance_id
        self.implementation_digest = source_trust.source_implementation_digest
        self.trust_anchor_id = source_trust.trust_anchor_id
        self.trust_anchor_digest = source_trust.trust_anchor_digest
        self._trust = source_trust
        self._policy = current_policy_source
        self._now = now_fn
        self._check_store()

    def _check_store(self) -> None:
        _, inode = _safe_file(self.path, must_exist=True)
        _need(inode == self._inode, "canonical PDP evidence SQLite identity drift")
        try:
            with closing(_conn(self.path, read_only=True)) as db:
                _schema(db)
        except sqlite3.Error as exc:
            raise R11CanonicalPDPSourceError("canonical PDP SQLite unavailable") from exc
        _, after = _safe_file(self.path, must_exist=True)
        _need(after == self._inode, "canonical PDP evidence SQLite identity drift")

    def resolve(self, request_id: str, gate_event_id: str) -> CanonicalPDPDecisionEvidence:
        _need(type(request_id) is str and IDENT.fullmatch(request_id) is not None
              and type(gate_event_id) is str and IDENT.fullmatch(gate_event_id) is not None,
              "canonical PDP coordinates required")
        self._check_store()
        try:
            with closing(_conn(self.path, read_only=True)) as db:
                rows = db.execute(
                    "SELECT record_json FROM r11_original_pdp_evidence "
                    "WHERE request_id=? AND gate_event_id=? LIMIT 2",
                    (request_id, gate_event_id),
                ).fetchall()
        except sqlite3.Error as exc:
            raise R11CanonicalPDPSourceError("canonical PDP read unavailable") from exc
        _need(len(rows) == 1, "canonical PDP evidence missing or ambiguous")
        try:
            record = json.loads(rows[0][0], object_pairs_hook=_strict_json)
            _need(type(record) is dict and set(record) == RECORD_FIELDS,
                  "canonical PDP record fields incorrect")
            evidence = CanonicalPDPDecisionEvidence(**record).validate()
        except R11CanonicalPDPSourceError:
            raise
        except Exception as exc:
            raise R11CanonicalPDPSourceError("canonical PDP record invalid") from exc
        binding = (
            evidence.source_id, evidence.source_instance_id,
            evidence.source_implementation_digest,
            evidence.trust_anchor_id, evidence.trust_anchor_digest,
        )
        _need(binding == self._trust.binding(), "canonical PDP source trust mismatch")
        _need(evidence.request_id == request_id
              and evidence.gate_event_id == gate_event_id,
              "canonical PDP record coordinate substitution")
        issued = datetime.fromisoformat(evidence.issued_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(evidence.expires_at.replace("Z", "+00:00"))
        observed = _now(self._now())
        _need(issued.astimezone(timezone.utc) <= observed < expires.astimezone(timezone.utc),
              "canonical PDP evidence expired or not current")
        self._check_store()
        return evidence

    def current_policy_binding(self, policy_binding: str) -> str:
        _need(type(policy_binding) is str and bool(policy_binding),
              "canonical PDP policy binding required")
        # NEVER use the stored PDP row as a source of current policy.
        # The owner callback must independently reread actual policy.
        try:
            result = self._policy(policy_binding)
        except Exception as exc:
            raise R11CanonicalPDPSourceError("independent policy unavailable") from exc
        _need(type(result) is str and bool(result),
              "independent policy invalid")
        self._check_store()
        return result


class SQLiteR11CanonicalPDPEvidencePublisher:
    """Private effects only: persist an ALREADY issued original PDP decision."""

    def __init__(
        self,
        *,
        database: Path | str,
        original_pdp: CanonicalPolicyDecisionPoint,
        original_authority: LiveAuthorityAdmission,
        source_trust: PDPSourceTrustBinding,
        issuance_source: Callable[[str,str,str], OriginalPDPIssuanceObservation],
        issuance_source_trust: PDPSourceTrustBinding,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        _need(type(issuance_source_trust) is PDPSourceTrustBinding,
              "original issuance source trust required")
        issuance_source_trust.validate()
        _need(callable(issuance_source)
              and _identity_tuple(issuance_source) == issuance_source_trust.binding(),
              "independent original issuance source/trust mismatch")
        _need(type(original_pdp) is CanonicalPolicyDecisionPoint,
              "exact original CanonicalPolicyDecisionPoint required")
        _need(isinstance(original_authority, LiveAuthorityAdmission)
              and original_pdp.authority_admission is original_authority,
              "PDP/LiveAuthorityAdmission owner split")
        _need(type(source_trust) is PDPSourceTrustBinding,
              "original canonical PDP trust required")
        source_trust.validate()
        _need(callable(now_fn), "original PDP trusted clock required")
        # The original protected deployment owner preprovisions the private
        # SQLite schema under independent authorization. Merely importing
        # this producer MUST NOT create tables or new state databases.
        self.path, self._inode = _safe_file(database, must_exist=True)
        try:
            with closing(_conn(self.path, read_only=True)) as db:
                _schema(db)
        except sqlite3.Error as exc:
            raise R11CanonicalPDPSourceError(
                "preprovisioned canonical PDP store unavailable"
            ) from exc
        self._owner = original_pdp
        self._authority = original_authority
        self._trust = source_trust
        self._issuance_source = issuance_source
        self._issuance_trust = issuance_source_trust
        self._now = now_fn

    def publish(
        self, decision: PDPResult, *, ttl_seconds: int = 120,
    ) -> CanonicalPDPDecisionEvidence:
        _need(type(decision) is PDPResult, "exact original PDP result required")
        _need(type(ttl_seconds) is int and 1 <= ttl_seconds <= MAX_TTL_SECONDS,
              "original PDP TTL invalid")
        request = decision.requested
        applied = decision.applied
        receipt = decision.receipt
        request.validate(); applied.validate(); receipt.validate()
        _need(applied.decision == "ALLOW" and applied.effective_authority != "none",
              "original PDP did not authorize bounded action")
        _need(
            request.request_id == applied.request_id == receipt.request_id
            and applied.gate_event_id == receipt.gate_event_id
            and request.proposal_id == applied.proposal_id
            and applied.decision_digest == receipt.decision_digest
            and request.request_digest == receipt.request_digest
            and request.policy_binding == applied.policy_binding
            and request.authority_lineage_digest == applied.authority_lineage_digest
            and request.observability_state == applied.observability_state,
            "original PDP result cross-binding mismatch",
        )
        cached = self._owner._replay.get(request.request_id)
        _need(type(cached) is tuple and len(cached) == 2
              and cached[1] is decision,
              "original PDP decision not issued by pinned owner")
        _need(self._owner.authority_admission is self._authority,
              "original PDP authority owner changed")
        now = _now(self._now())
        _need(type(receipt.replay_key) is str
              and len(receipt.replay_key) == 64,
              "original PDP replay key invalid")
        # The original CanonicalPolicyDecisionPoint caches PDPResult without
        # an issue timestamp. An old cached ALLOW must NEVER receive a fresh
        # lifetime by being re-published. Require a separate, trusted
        # original-issuer observation of the real issuance window.
        try:
            issuance = self._issuance_source(
                request.request_id, applied.gate_event_id, applied.decision_digest
            )
        except Exception as exc:
            raise R11CanonicalPDPSourceError(
                "original issuance observation unavailable"
            ) from exc
        _need(type(issuance) is OriginalPDPIssuanceObservation,
              "independent issuance observation type invalid")
        issuance.validate()
        _need(
            (issuance.request_id, issuance.gate_event_id,
             issuance.gate_decision_digest, issuance.policy_binding)
            == (request.request_id, applied.gate_event_id,
                applied.decision_digest, applied.policy_binding),
            "independent issuance observation does not bind original PDP",
        )
        _need(
            (issuance.source_id, issuance.source_instance_id,
             issuance.source_implementation_digest, issuance.trust_anchor_id,
             issuance.trust_anchor_digest) == self._issuance_trust.binding()
            and _identity_tuple(self._issuance_source) == self._issuance_trust.binding(),
            "independent issuance provenance substitution",
        )
        issued_at = _now(datetime.fromisoformat(
            issuance.issued_at.replace("Z","+00:00")
        ))
        ends_at = _now(datetime.fromisoformat(
            issuance.expires_at.replace("Z","+00:00")
        ))
        _need(issued_at <= now < ends_at,
              "original PDP issuance expired or not yet current")
        bound_expiry = min(ends_at, now + timedelta(seconds=ttl_seconds))
        _need(bound_expiry > now, "no remaining original PDP lifetime")
        evidence = CanonicalPDPDecisionEvidence(
            request_id=request.request_id,
            gate_event_id=applied.gate_event_id,
            proposal_id=applied.proposal_id,
            gate_decision_digest=applied.decision_digest,
            pdp_receipt_digest=_pdp_receipt_digest(receipt),
            request_digest=receipt.request_digest,
            replay_key=receipt.replay_key,
            policy_binding=applied.policy_binding,
            authority_lineage_digest=applied.authority_lineage_digest,
            observability_state=applied.observability_state,
            source_id=self._trust.source_id,
            source_instance_id=self._trust.source_instance_id,
            source_implementation_digest=self._trust.source_implementation_digest,
            trust_anchor_id=self._trust.trust_anchor_id,
            trust_anchor_digest=self._trust.trust_anchor_digest,
            issued_at=issued_at.isoformat(),
            expires_at=bound_expiry.isoformat(),
        ).sealed()
        record = json.dumps(asdict(evidence), sort_keys=True,
                            separators=(",", ":"), ensure_ascii=False)
        _, prior = _safe_file(self.path, must_exist=True)
        _need(prior == self._inode, "canonical PDP publisher inode drift")
        try:
            with closing(_conn(self.path, read_only=False)) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute(
                        "INSERT INTO r11_original_pdp_evidence VALUES(?,?,?)",
                        (request.request_id, applied.gate_event_id, record),
                    )
                    db.execute("COMMIT")
                except sqlite3.IntegrityError as exc:
                    if db.in_transaction:
                        db.execute("ROLLBACK")
                    raise R11CanonicalPDPSourceError(
                        "original PDP evidence duplicate or replay"
                    ) from exc
                except Exception:
                    if db.in_transaction:
                        db.execute("ROLLBACK")
                    raise
        except sqlite3.Error as exc:
            raise R11CanonicalPDPSourceError("original PDP publication unavailable") from exc
        _, after = _safe_file(self.path, must_exist=True)
        _need(after == self._inode, "canonical PDP publisher inode drift")
        return evidence

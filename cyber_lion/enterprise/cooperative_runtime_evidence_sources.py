"""Durable non-authorizing evidence sources for cooperative runtime composition.

These sources copy already-existing dispatch/provisioning/runtime/currentness evidence.
They do not issue RuntimeAdmission, authority, PDP decisions, provisioning receipts or
fleet assignments. Producer and consumer are deliberately separated: workers use only
the read-only source surface while a trusted external owner may publish exact evidence.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import stat
from typing import Any, Mapping

from cyber_lion.contracts.executor_sandbox import FleetDispatchBinding, ProvisioningBinding
from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding
from cyber_lion.contracts.runtime_enforcement import RuntimeAdmission, RuntimeIdentityBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority
from cyber_lion.enterprise.cooperative_context_resolver import CooperativeContextPin

SCHEMA = "lion.cooperative-runtime-evidence/v1"
_ALLOWED_OBSERVABILITY = frozenset({"HEALTHY", "DEGRADED", "LOST"})


class CooperativeRuntimeEvidenceError(RuntimeError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CooperativeRuntimeEvidenceError(reason)


def _path(value: str | Path, *, create: bool) -> Path:
    path = Path(value)
    _require(path.is_absolute(), "evidence DB path must be absolute")
    parent = path.parent.resolve(strict=True)
    _require(parent.is_dir(), "evidence DB parent unavailable")
    _require(not path.is_symlink(), "evidence DB symlink denied")
    if not create:
        _require(path.is_file(), "evidence DB unavailable")
    return path


def _identity(path: Path) -> tuple[int, int]:
    try:
        st = path.stat()
    except OSError as exc:
        raise CooperativeRuntimeEvidenceError("evidence DB unavailable") from exc
    _require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, "evidence DB must be private regular file")
    return st.st_dev, st.st_ino


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _strict(raw: str, label: str) -> dict[str, Any]:
    def unique(pairs):
        out = {}
        for key, value in pairs:
            _require(key not in out, label + " duplicate JSON key")
            out[key] = value
        return out
    try:
        value = json.loads(
            raw,
            object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(CooperativeRuntimeEvidenceError(label + " nonfinite JSON")),
        )
    except CooperativeRuntimeEvidenceError:
        raise
    except Exception as exc:
        raise CooperativeRuntimeEvidenceError(label + " JSON invalid") from exc
    _require(type(value) is dict, label + " object required")
    return value


def _digest(value: str, label: str) -> str:
    _require(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value), label)
    return value


def _utc(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise CooperativeRuntimeEvidenceError("timestamp invalid") from exc
    _require(parsed.tzinfo is not None, "timestamp must be zoned")
    return parsed.astimezone(timezone.utc)


def _contract(cls, value: Mapping[str, Any]):
    _require(type(value) is dict and set(value) == set(cls.__dataclass_fields__), cls.__name__ + " fields")
    data = dict(value)
    for name, field in cls.__dataclass_fields__.items():
        if str(field.type).startswith("tuple["):
            _require(type(data[name]) is list, name + " array required")
            data[name] = tuple(data[name])
    try:
        return cls(**data).validate()
    except Exception as exc:
        raise CooperativeRuntimeEvidenceError(cls.__name__ + " invalid") from exc


class SQLiteCooperativeRuntimeEvidencePublisher:
    """Trusted-copy writer for evidence produced by existing canonical owners."""

    def __init__(self, path: str | Path):
        self.path = _path(path, create=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_admission_evidence(
                  admission_digest TEXT PRIMARY KEY, record_json TEXT NOT NULL,
                  record_digest TEXT NOT NULL, provenance_digest TEXT NOT NULL,
                  observed_at TEXT NOT NULL, expires_at TEXT NOT NULL, schema_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS context_pin_evidence(
                  assignment_id TEXT PRIMARY KEY, filename TEXT NOT NULL, content_sha256 TEXT NOT NULL,
                  provenance_digest TEXT NOT NULL, observed_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL, schema_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS dispatch_evidence(
                  mission_id TEXT PRIMARY KEY, record_json TEXT NOT NULL,
                  record_digest TEXT NOT NULL, provenance_digest TEXT NOT NULL,
                  observed_at TEXT NOT NULL, expires_at TEXT NOT NULL, schema_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS provisioning_evidence(
                  assignment_id TEXT PRIMARY KEY, record_json TEXT NOT NULL,
                  record_digest TEXT NOT NULL, provenance_digest TEXT NOT NULL,
                  observed_at TEXT NOT NULL, expires_at TEXT NOT NULL, schema_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runtime_identity_evidence(
                  runtime_instance_id TEXT PRIMARY KEY, record_json TEXT NOT NULL,
                  record_digest TEXT NOT NULL, provenance_digest TEXT NOT NULL,
                  observed_at TEXT NOT NULL, expires_at TEXT NOT NULL, schema_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS currentness_evidence(
                  admission_digest TEXT PRIMARY KEY, authority_json TEXT NOT NULL,
                  authority_digest TEXT NOT NULL, policy_binding TEXT NOT NULL,
                  runtime_identity_digest TEXT NOT NULL, requested_effect_digest TEXT NOT NULL,
                  observability_state TEXT NOT NULL, provenance_digest TEXT NOT NULL,
                  observed_at TEXT NOT NULL, expires_at TEXT NOT NULL, schema_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS transfer_binding_evidence(
                  assignment_id TEXT NOT NULL, purpose TEXT NOT NULL,
                  binding_json TEXT NOT NULL, binding_digest TEXT NOT NULL,
                  provenance_digest TEXT NOT NULL, observed_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL, schema_id TEXT NOT NULL,
                  PRIMARY KEY(assignment_id,purpose));
                """
            )
        self._identity = _identity(self.path)

    def _check(self) -> None:
        _require(not self.path.is_symlink() and _identity(self.path) == self._identity, "evidence DB identity drift")

    @staticmethod
    def _window(observed_at: datetime | str, expires_at: datetime | str) -> tuple[str, str]:
        observed, expires = _utc(observed_at), _utc(expires_at)
        _require(expires > observed, "evidence expiry must follow observation")
        return observed.isoformat(), expires.isoformat()

    @staticmethod
    def _prov(value: str) -> str:
        return _digest(value, "provenance digest")


    def publish_runtime_admission(self, value: RuntimeAdmission, *, provenance_digest: str, observed_at, expires_at) -> str:
        _require(type(value) is RuntimeAdmission, "exact RuntimeAdmission required")
        value.validate(); raw = _canonical(asdict(value)); dg = value.admission_digest; obs, exp = self._window(observed_at, expires_at)
        self._check()
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute("INSERT OR REPLACE INTO runtime_admission_evidence VALUES(?,?,?,?,?,?,?)",
                       (dg, raw, dg, self._prov(provenance_digest), obs, exp, SCHEMA))
        return dg

    def publish_context_pin(self, value: CooperativeContextPin, *, provenance_digest: str, observed_at, expires_at) -> str:
        _require(type(value) is CooperativeContextPin, "exact CooperativeContextPin required")
        value.validate(); obs, exp = self._window(observed_at, expires_at)
        self._check()
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute("INSERT OR REPLACE INTO context_pin_evidence VALUES(?,?,?,?,?,?,?)",
                       (value.assignment_id, value.filename, value.sha256, self._prov(provenance_digest), obs, exp, SCHEMA))
        return value.sha256

    def publish_dispatch(self, value: FleetDispatchBinding, *, provenance_digest: str, observed_at, expires_at) -> str:
        _require(type(value) is FleetDispatchBinding, "exact FleetDispatchBinding required")
        value.validate(); raw = _canonical(asdict(value)); dg = value.digest(); obs, exp = self._window(observed_at, expires_at)
        self._check()
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute("INSERT OR REPLACE INTO dispatch_evidence VALUES(?,?,?,?,?,?,?)",
                       (value.mission_id, raw, dg, self._prov(provenance_digest), obs, exp, SCHEMA))
        return dg

    def publish_provisioning(self, assignment_id: str, value: ProvisioningBinding, *, provenance_digest: str, observed_at, expires_at) -> str:
        _require(type(assignment_id) is str and assignment_id, "assignment identity")
        _require(type(value) is ProvisioningBinding, "exact ProvisioningBinding required")
        value.validate(); raw = _canonical(asdict(value)); dg = value.digest(); obs, exp = self._window(observed_at, expires_at)
        self._check()
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute("INSERT OR REPLACE INTO provisioning_evidence VALUES(?,?,?,?,?,?,?)",
                       (assignment_id, raw, dg, self._prov(provenance_digest), obs, exp, SCHEMA))
        return dg

    def publish_runtime_identity(self, value: RuntimeIdentityBinding, *, provenance_digest: str, observed_at, expires_at) -> str:
        _require(type(value) is RuntimeIdentityBinding, "exact RuntimeIdentityBinding required")
        value.validate(); raw = _canonical(asdict(value)); dg = value.digest(); obs, exp = self._window(observed_at, expires_at)
        self._check()
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute("INSERT OR REPLACE INTO runtime_identity_evidence VALUES(?,?,?,?,?,?,?)",
                       (value.runtime_instance_id, raw, dg, self._prov(provenance_digest), obs, exp, SCHEMA))
        return dg

    def publish_currentness(
        self, admission_digest: str, authority: LiveAdmittedAuthority, *,
        policy_binding: str, runtime_identity_digest: str, requested_effect_digest: str,
        observability_state: str, provenance_digest: str, observed_at, expires_at,
    ) -> str:
        _digest(admission_digest, "admission digest")
        _require(type(authority) is LiveAdmittedAuthority, "exact LiveAdmittedAuthority required")
        authority.validate()
        _require(type(policy_binding) is str and policy_binding, "policy binding")
        _digest(runtime_identity_digest, "runtime identity digest")
        _digest(requested_effect_digest, "requested effect digest")
        _require(observability_state in _ALLOWED_OBSERVABILITY, "observability state")
        raw = _canonical(asdict(authority)); dg = authority.digest(); obs, exp = self._window(observed_at, expires_at)
        self._check()
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute("INSERT OR REPLACE INTO currentness_evidence VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (admission_digest, raw, dg, policy_binding, runtime_identity_digest, requested_effect_digest,
                        observability_state, self._prov(provenance_digest), obs, exp, SCHEMA))
        return dg

    def publish_transfer_binding(self, assignment_id: str, purpose: str, binding: Mapping[str, Any], *, provenance_digest: str, observed_at, expires_at) -> str:
        _require(type(assignment_id) is str and assignment_id, "assignment identity")
        _require(purpose in {"CONTEXT", "VERIFY"}, "transfer purpose")
        _require(isinstance(binding, Mapping), "transfer binding")
        raw = _canonical(dict(binding)); dg = sha256(raw.encode("utf-8")).hexdigest(); obs, exp = self._window(observed_at, expires_at)
        self._check()
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute("INSERT OR REPLACE INTO transfer_binding_evidence VALUES(?,?,?,?,?,?,?,?)",
                       (assignment_id, purpose, raw, dg, self._prov(provenance_digest), obs, exp, SCHEMA))
        return dg


class _ReadOnlyStore:
    def __init__(self, path: str | Path, *, now_fn):
        self.path = _path(path, create=False)
        _require(callable(now_fn), "trusted evidence clock required")
        self._now = now_fn
        self._identity = _identity(self.path)

    def _connect(self):
        _require(not self.path.is_symlink() and _identity(self.path) == self._identity, "evidence DB identity drift")
        db = sqlite3.connect("file:" + self.path.as_posix() + "?mode=ro", uri=True, timeout=5)
        db.execute("PRAGMA query_only=ON")
        return db

    @staticmethod
    def _exact_one(rows, label: str):
        _require(len(rows) == 1, label + " unavailable or ambiguous")
        return rows[0]

    def _fresh(self, observed: str, expires: str) -> None:
        now = _utc(self._now())
        _require(_utc(observed) <= now < _utc(expires), "runtime evidence stale")


class SQLiteEvidenceRuntimeAdmissionSource(_ReadOnlyStore):
    def __init__(self, path: str | Path, trust: RuntimeAdmissionSourceTrustBinding, *, now_fn):
        _require(type(trust) is RuntimeAdmissionSourceTrustBinding, "exact admission trust required")
        trust.validate(); super().__init__(path, now_fn=now_fn)
        self.source_id, self.source_instance_id, self.implementation_digest, self.trust_anchor_id, self.trust_anchor_digest = trust.binding()

    def resolve(self, admission_digest: str) -> RuntimeAdmission:
        _digest(admission_digest, "admission digest")
        try:
            with closing(self._connect()) as db:
                rows = db.execute(
                    "SELECT record_json,record_digest,observed_at,expires_at,schema_id "
                    "FROM runtime_admission_evidence WHERE admission_digest=?",
                    (admission_digest,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise CooperativeRuntimeEvidenceError("runtime admission evidence unavailable") from exc
        row = self._exact_one(rows, "runtime admission evidence")
        self._fresh(row[2], row[3]); _require(row[4] == SCHEMA, "runtime admission schema")
        value = _contract(RuntimeAdmission, _strict(row[0], "runtime admission"))
        _require(value.admission_digest == admission_digest == row[1], "runtime admission digest mismatch")
        return value

    def is_current(self, admission_digest: str) -> bool:
        try:
            return self.resolve(admission_digest).admission_digest == admission_digest
        except CooperativeRuntimeEvidenceError:
            return False


class SQLiteContextPinSource(_ReadOnlyStore):
    def __call__(self, assignment_id: str) -> CooperativeContextPin:
        try:
            with closing(self._connect()) as db:
                rows = db.execute(
                    "SELECT filename,content_sha256,observed_at,expires_at,schema_id "
                    "FROM context_pin_evidence WHERE assignment_id=?",
                    (assignment_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise CooperativeRuntimeEvidenceError("context pin evidence unavailable") from exc
        row = self._exact_one(rows, "context pin evidence")
        self._fresh(row[2], row[3]); _require(row[4] == SCHEMA, "context pin schema")
        try:
            return CooperativeContextPin(assignment_id, row[0], row[1]).validate()
        except Exception as exc:
            raise CooperativeRuntimeEvidenceError("context pin invalid") from exc


class SQLiteFleetDispatchSource(_ReadOnlyStore):
    def current_dispatch(self, mission_id: str) -> FleetDispatchBinding:
        try:
            with closing(self._connect()) as db:
                rows = db.execute(
                    "SELECT record_json,record_digest,observed_at,expires_at,schema_id "
                    "FROM dispatch_evidence WHERE mission_id=?",
                    (mission_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise CooperativeRuntimeEvidenceError("dispatch evidence unavailable") from exc
        row = self._exact_one(rows, "dispatch evidence")
        self._fresh(row[2], row[3]); _require(row[4] == SCHEMA, "dispatch schema")
        value = _contract(FleetDispatchBinding, _strict(row[0], "dispatch"))
        _require(value.digest() == row[1], "dispatch digest mismatch")
        return value


class SQLiteProvisioningBindingSource(_ReadOnlyStore):
    def __call__(self, assignment_id: str) -> ProvisioningBinding:
        try:
            with closing(self._connect()) as db:
                rows = db.execute(
                    "SELECT record_json,record_digest,observed_at,expires_at,schema_id "
                    "FROM provisioning_evidence WHERE assignment_id=?",
                    (assignment_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise CooperativeRuntimeEvidenceError("provisioning evidence unavailable") from exc
        row = self._exact_one(rows, "provisioning evidence")
        self._fresh(row[2], row[3]); _require(row[4] == SCHEMA, "provisioning schema")
        value = _contract(ProvisioningBinding, _strict(row[0], "provisioning"))
        _require(value.digest() == row[1], "provisioning digest mismatch")
        return value


class SQLiteRuntimeIdentitySource(_ReadOnlyStore):
    def __call__(self, runtime_instance_id: str) -> RuntimeIdentityBinding:
        try:
            with closing(self._connect()) as db:
                rows = db.execute(
                    "SELECT record_json,record_digest,observed_at,expires_at,schema_id "
                    "FROM runtime_identity_evidence WHERE runtime_instance_id=?",
                    (runtime_instance_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise CooperativeRuntimeEvidenceError("runtime identity evidence unavailable") from exc
        row = self._exact_one(rows, "runtime identity evidence")
        self._fresh(row[2], row[3]); _require(row[4] == SCHEMA, "runtime identity schema")
        value = _contract(RuntimeIdentityBinding, _strict(row[0], "runtime identity"))
        _require(value.digest() == row[1], "runtime identity digest mismatch")
        return value


class SQLiteEffectTimeCurrentnessSource(_ReadOnlyStore):
    def __init__(self, path: str | Path, trust: CurrentnessSourceTrustBinding, *, now_fn):
        _require(type(trust) is CurrentnessSourceTrustBinding, "exact currentness trust required")
        trust.validate(); super().__init__(path, now_fn=now_fn)
        self.source_id, self.source_instance_id, self.implementation_digest, self.trust_anchor_id, self.trust_anchor_digest = trust.binding()

    def _row(self, admission_digest: str):
        _digest(admission_digest, "admission digest")
        try:
            with closing(self._connect()) as db:
                rows = db.execute(
                    "SELECT authority_json,authority_digest,policy_binding,runtime_identity_digest,requested_effect_digest,"
                    "observability_state,observed_at,expires_at,schema_id "
                    "FROM currentness_evidence WHERE admission_digest=?",
                    (admission_digest,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise CooperativeRuntimeEvidenceError("currentness evidence unavailable") from exc
        row = self._exact_one(rows, "currentness evidence")
        self._fresh(row[6], row[7]); _require(row[8] == SCHEMA, "currentness schema")
        return row

    def resolve_authority(self, admission_digest: str) -> LiveAdmittedAuthority:
        row = self._row(admission_digest)
        value = _contract(LiveAdmittedAuthority, _strict(row[0], "live authority"))
        _require(value.digest() == row[1], "live authority digest mismatch")
        return value

    def current_policy_binding(self, policy_binding: str) -> str:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT policy_binding,observed_at,expires_at FROM currentness_evidence WHERE policy_binding=?",
                (policy_binding,),
            ).fetchall()
        _require(rows, "policy currentness unavailable")
        for row in rows:
            self._fresh(row[1], row[2])
        return policy_binding

    def current_observability_state(self, runtime_identity_digest: str, requested_effect_digest: str) -> str:
        _digest(runtime_identity_digest, "runtime identity digest"); _digest(requested_effect_digest, "requested effect digest")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT observability_state,observed_at,expires_at FROM currentness_evidence "
                "WHERE runtime_identity_digest=? AND requested_effect_digest=?",
                (runtime_identity_digest, requested_effect_digest),
            ).fetchall()
        _require(len(rows) == 1, "observability currentness unavailable or ambiguous")
        self._fresh(rows[0][1], rows[0][2])
        _require(rows[0][0] in _ALLOWED_OBSERVABILITY, "observability state invalid")
        return rows[0][0]


class SQLiteTransferBindingSource(_ReadOnlyStore):
    def __call__(self, assignment_id: str, purpose: str) -> Mapping[str, Any]:
        _require(purpose in {"CONTEXT", "VERIFY"}, "transfer purpose")
        try:
            with closing(self._connect()) as db:
                rows = db.execute(
                    "SELECT binding_json,binding_digest,observed_at,expires_at,schema_id "
                    "FROM transfer_binding_evidence WHERE assignment_id=? AND purpose=?",
                    (assignment_id, purpose),
                ).fetchall()
        except sqlite3.Error as exc:
            raise CooperativeRuntimeEvidenceError("transfer binding evidence unavailable") from exc
        row = self._exact_one(rows, "transfer binding evidence")
        self._fresh(row[2], row[3]); _require(row[4] == SCHEMA, "transfer binding schema")
        value = _strict(row[0], "transfer binding")
        _require(sha256(_canonical(value).encode("utf-8")).hexdigest() == row[1], "transfer binding digest mismatch")
        return value

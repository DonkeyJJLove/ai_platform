from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from threading import RLock
from typing import Protocol

from cyber_lion.contracts.moon_file_write import (
    BASE_DIR,
    CONTROL_ISSUE,
    MAX_CONTENT_BYTES,
    REPOSITORY,
    RUNNER_NAME,
    MoonFileWriteRequest,
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_STATES = {"PREPARED", "ATTEMPTED", "OBSERVED", "RECONCILED", "UNKNOWN"}


class MoonFileWriteMediationError(RuntimeError):
    pass


def _digest(domain: bytes, value: object) -> str:
    return sha256(domain + json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _hex64(value: str, name: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise MoonFileWriteMediationError(f"{name} invalid")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class CanonicalMoonFileWriteAdmission:
    request_digest: str
    repository: str
    control_issue: int
    actor_login: str
    runner_name: str
    target_path: str
    operation_mode: str
    expected_previous_state: str
    expected_previous_sha256: str | None
    intended_content_sha256: str
    intended_content_size: int
    source_event_digest: str
    authority_source_digest: str
    pdp_decision_digest: str
    authority_epoch: int
    provider_id: str
    admission_digest: str = ""

    def payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("admission_digest")
        return value

    def validate(self) -> "CanonicalMoonFileWriteAdmission":
        for name in ("request_digest", "intended_content_sha256", "source_event_digest", "authority_source_digest", "pdp_decision_digest"):
            _hex64(getattr(self, name), name)
        if self.expected_previous_sha256 is not None:
            _hex64(self.expected_previous_sha256, "expected_previous_sha256")
        if self.repository != REPOSITORY or self.control_issue != CONTROL_ISSUE or self.runner_name != RUNNER_NAME:
            raise MoonFileWriteMediationError("admission execution context invalid")
        if not self.actor_login or not self.provider_id:
            raise MoonFileWriteMediationError("admission identity invalid")
        if not isinstance(self.authority_epoch, int) or isinstance(self.authority_epoch, bool) or self.authority_epoch < 0:
            raise MoonFileWriteMediationError("authority_epoch invalid")
        expected = _digest(b"LION/MOON-FILE-WRITE-ADMISSION/1\0", self.payload())
        if self.admission_digest and self.admission_digest != expected:
            raise MoonFileWriteMediationError("admission digest mismatch")
        return self

    def sealed(self) -> "CanonicalMoonFileWriteAdmission":
        self.validate()
        payload = self.payload()
        return CanonicalMoonFileWriteAdmission(**payload, admission_digest=_digest(b"LION/MOON-FILE-WRITE-ADMISSION/1\0", payload)).validate()

    def binds(self, request: MoonFileWriteRequest) -> None:
        request.validate()
        actual = (
            self.request_digest, self.repository, self.control_issue, self.actor_login, self.runner_name,
            self.target_path, self.operation_mode, self.expected_previous_state, self.expected_previous_sha256,
            self.intended_content_sha256, self.intended_content_size, self.source_event_digest,
        )
        expected = (
            request.request_digest, request.repository, request.control_issue, request.actor_login, request.runner_name,
            request.target_path, request.operation_mode, request.expected_previous_state, request.expected_previous_sha256,
            request.intended_content_sha256, request.intended_content_size, request.source_event_digest,
        )
        if actual != expected:
            raise MoonFileWriteMediationError("admission/request binding mismatch")


class MoonFileWriteAdmissionResolver(Protocol):
    def resolve(self, request: MoonFileWriteRequest) -> CanonicalMoonFileWriteAdmission: ...


@dataclass(frozen=True)
class MoonFileTargetObservation:
    target_path: str
    exists: bool
    regular_file: bool
    symlink: bool
    size: int | None
    sha256: str | None
    device: int | None
    inode: int | None
    base_device: int
    base_inode: int
    observer_id: str
    observed_at: str
    observation_digest: str = ""

    def payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("observation_digest")
        return value

    def validate(self) -> "MoonFileTargetObservation":
        if self.target_path != str(Path(BASE_DIR) / Path(self.target_path).name) or not self.observer_id or not self.observed_at:
            raise MoonFileWriteMediationError("target observation identity invalid")
        if self.exists:
            if self.size is None or self.device is None or self.inode is None:
                raise MoonFileWriteMediationError("target observation metadata missing")
            if self.regular_file and self.sha256 is None:
                raise MoonFileWriteMediationError("target digest missing")
            if self.sha256 is not None:
                _hex64(self.sha256, "target sha256")
        elif any(value is not None for value in (self.size, self.sha256, self.device, self.inode)) or self.regular_file or self.symlink:
            raise MoonFileWriteMediationError("absent target carries state")
        expected = _digest(b"LION/MOON-FILE-TARGET-OBSERVATION/1\0", self.payload())
        if self.observation_digest and self.observation_digest != expected:
            raise MoonFileWriteMediationError("target observation digest mismatch")
        return self

    def sealed(self) -> "MoonFileTargetObservation":
        self.validate()
        payload = self.payload()
        return MoonFileTargetObservation(**payload, observation_digest=_digest(b"LION/MOON-FILE-TARGET-OBSERVATION/1\0", payload)).validate()


class MoonFileWriteObserver:
    observer_id = "moon-host-file-observer-v1"

    @staticmethod
    def _hash_fd(fd: int) -> tuple[int, str]:
        os.lseek(fd, 0, os.SEEK_SET)
        h = sha256(); size = 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_CONTENT_BYTES:
                raise MoonFileWriteMediationError("observed target exceeds bounded size")
            h.update(chunk)
        return size, h.hexdigest()

    def observe(self, target_path: str) -> MoonFileTargetObservation:
        path = Path(target_path)
        if path.parent != Path(BASE_DIR) or not path.name:
            raise MoonFileWriteMediationError("observer target outside bounded directory")
        base_stat = os.lstat(BASE_DIR)
        if stat.S_ISLNK(base_stat.st_mode) or not stat.S_ISDIR(base_stat.st_mode):
            raise MoonFileWriteMediationError("bounded base directory unsafe")
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory = getattr(os, "O_DIRECTORY", 0)
        dir_fd = os.open(BASE_DIR, os.O_RDONLY | directory | nofollow)
        try:
            try:
                lst = os.stat(path.name, dir_fd=dir_fd, follow_symlinks=False)
            except FileNotFoundError:
                return MoonFileTargetObservation(target_path, False, False, False, None, None, None, None,
                    int(base_stat.st_dev), int(base_stat.st_ino), self.observer_id, _now()).sealed()
            is_link = stat.S_ISLNK(lst.st_mode)
            is_regular = stat.S_ISREG(lst.st_mode)
            digest = None; size = int(lst.st_size)
            if is_regular and not is_link:
                fd = os.open(path.name, os.O_RDONLY | nofollow, dir_fd=dir_fd)
                try:
                    fst = os.fstat(fd)
                    if (fst.st_dev, fst.st_ino) != (lst.st_dev, lst.st_ino):
                        raise MoonFileWriteMediationError("target changed during observation")
                    size, digest = self._hash_fd(fd)
                finally:
                    os.close(fd)
            return MoonFileTargetObservation(target_path, True, is_regular, is_link, size, digest,
                int(lst.st_dev), int(lst.st_ino), int(base_stat.st_dev), int(base_stat.st_ino), self.observer_id, _now()).sealed()
        finally:
            os.close(dir_fd)


@dataclass(frozen=True)
class MoonFileWriteFenceRecord:
    effect_key: str
    admission_digest: str
    request_digest: str
    repository: str
    target_path: str
    state: str
    prepared_at: str
    attempted_at: str | None = None
    observed_at: str | None = None
    reconciled_at: str | None = None
    pre_observation_digest: str | None = None
    post_observation_digest: str | None = None
    reconciliation_digest: str | None = None

    def validate(self) -> "MoonFileWriteFenceRecord":
        for name in ("effect_key", "admission_digest", "request_digest"):
            _hex64(getattr(self, name), name)
        if self.repository != REPOSITORY or self.state not in _STATES or not self.target_path.startswith(BASE_DIR + "/"):
            raise MoonFileWriteMediationError("fence identity/state invalid")
        if self.pre_observation_digest is not None:
            _hex64(self.pre_observation_digest, "pre_observation_digest")
        if self.post_observation_digest is not None:
            _hex64(self.post_observation_digest, "post_observation_digest")
        if self.reconciliation_digest is not None:
            _hex64(self.reconciliation_digest, "reconciliation_digest")
        if self.state == "PREPARED" and any((self.attempted_at, self.observed_at, self.reconciled_at, self.post_observation_digest, self.reconciliation_digest)):
            raise MoonFileWriteMediationError("PREPARED contains later evidence")
        if self.state in {"ATTEMPTED", "OBSERVED", "RECONCILED"} and not self.attempted_at:
            raise MoonFileWriteMediationError("attempted_at missing")
        if self.state in {"OBSERVED", "RECONCILED"} and (not self.observed_at or not self.post_observation_digest):
            raise MoonFileWriteMediationError("post observation missing")
        if self.state == "RECONCILED" and (not self.reconciled_at or not self.reconciliation_digest):
            raise MoonFileWriteMediationError("reconciliation missing")
        return self


class DurableMoonFileWriteFence:
    def __init__(self, database_path: str):
        path = Path(database_path)
        if not path.is_absolute():
            raise MoonFileWriteMediationError("fence path must be absolute")
        if any(parent.name == ".git" for parent in path.parents):
            raise MoonFileWriteMediationError("fence path cannot be repository metadata")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = str(path); self._lock = RLock(); self._initialize()

    def _connect(self):
        c = sqlite3.connect(self._path, timeout=10, isolation_level=None, check_same_thread=False)
        c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=FULL")
        return c

    def _initialize(self):
        with self._lock, self._connect() as c:
            c.execute("CREATE TABLE IF NOT EXISTS moon_file_write_effect(effect_key TEXT PRIMARY KEY,admission_digest TEXT UNIQUE NOT NULL,request_digest TEXT UNIQUE NOT NULL,repository TEXT NOT NULL,target_path TEXT NOT NULL,state TEXT NOT NULL,prepared_at TEXT NOT NULL,attempted_at TEXT,observed_at TEXT,reconciled_at TEXT,pre_observation_digest TEXT,post_observation_digest TEXT,reconciliation_digest TEXT)")

    def get(self, effect_key: str) -> MoonFileWriteFenceRecord:
        _hex64(effect_key, "effect_key")
        with self._connect() as c:
            row = c.execute("SELECT effect_key,admission_digest,request_digest,repository,target_path,state,prepared_at,attempted_at,observed_at,reconciled_at,pre_observation_digest,post_observation_digest,reconciliation_digest FROM moon_file_write_effect WHERE effect_key=?", (effect_key,)).fetchone()
        if row is None:
            raise MoonFileWriteMediationError("effect unknown")
        return MoonFileWriteFenceRecord(*row).validate()

    def prepare(self, record: MoonFileWriteFenceRecord) -> MoonFileWriteFenceRecord:
        record.validate()
        if record.state != "PREPARED" or not record.pre_observation_digest:
            raise MoonFileWriteMediationError("PREPARED with pre-observation required")
        with self._lock, self._connect() as c:
            try:
                c.execute("INSERT INTO moon_file_write_effect VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", tuple(asdict(record).values()))
            except sqlite3.IntegrityError as exc:
                raise MoonFileWriteMediationError("durable file-write replay denied") from exc
        return self.get(record.effect_key)

    def mark_attempted(self, effect_key: str, when: str) -> MoonFileWriteFenceRecord:
        _hex64(effect_key, "effect_key")
        with self._lock, self._connect() as c:
            cur = c.execute(
                "UPDATE moon_file_write_effect SET state='ATTEMPTED',attempted_at=? "
                "WHERE effect_key=? AND state='PREPARED' AND attempted_at IS NULL",
                (when, effect_key),
            )
            if cur.rowcount != 1:
                raise MoonFileWriteMediationError("effect cannot enter ATTEMPTED")
        return self.get(effect_key)

    def mark_observed(self, effect_key: str, when: str, digest: str) -> MoonFileWriteFenceRecord:
        _hex64(effect_key, "effect_key")
        _hex64(digest, "post_observation_digest")
        with self._lock, self._connect() as c:
            cur = c.execute(
                "UPDATE moon_file_write_effect SET state='OBSERVED',observed_at=?,post_observation_digest=? "
                "WHERE effect_key=? AND state='ATTEMPTED' AND observed_at IS NULL AND post_observation_digest IS NULL",
                (when, digest, effect_key),
            )
            if cur.rowcount != 1:
                raise MoonFileWriteMediationError("effect cannot enter OBSERVED")
        return self.get(effect_key)

    def mark_reconciled(self, effect_key: str, when: str, digest: str) -> MoonFileWriteFenceRecord:
        _hex64(effect_key, "effect_key")
        _hex64(digest, "reconciliation_digest")
        with self._lock, self._connect() as c:
            cur = c.execute(
                "UPDATE moon_file_write_effect SET state='RECONCILED',reconciled_at=?,reconciliation_digest=? "
                "WHERE effect_key=? AND state='OBSERVED' AND reconciled_at IS NULL AND reconciliation_digest IS NULL",
                (when, digest, effect_key),
            )
            if cur.rowcount != 1:
                raise MoonFileWriteMediationError("effect cannot enter RECONCILED")
        return self.get(effect_key)

    def mark_unknown(self, effect_key: str) -> MoonFileWriteFenceRecord:
        _hex64(effect_key, "effect_key")
        with self._lock, self._connect() as c:
            cur = c.execute(
                "UPDATE moon_file_write_effect SET state='UNKNOWN' "
                "WHERE effect_key=? AND state IN ('PREPARED','ATTEMPTED','OBSERVED')",
                (effect_key,),
            )
            if cur.rowcount != 1:
                raise MoonFileWriteMediationError("effect cannot enter UNKNOWN")
        return self.get(effect_key)


def moon_file_write_effect_key(request: MoonFileWriteRequest, admission: CanonicalMoonFileWriteAdmission) -> str:
    request.validate(); admission.validate(); admission.binds(request)
    _hex64(admission.admission_digest, "admission_digest")
    return _digest(b"LION/MOON-FILE-WRITE-EFFECT/1\0", {
        "request_digest": request.request_digest,
        "admission_digest": admission.admission_digest,
        "target_path": request.target_path,
        "expected_previous_state": request.expected_previous_state,
        "expected_previous_sha256": request.expected_previous_sha256,
        "intended_content_sha256": request.intended_content_sha256,
        "authority_epoch": admission.authority_epoch,
    })


class MoonFileWriteEffect(Protocol):
    def write_exact(self, request: MoonFileWriteRequest, admission: CanonicalMoonFileWriteAdmission) -> None: ...


@dataclass(frozen=True)
class MoonFileWriteReconciliationReceipt:
    effect_key: str
    request_digest: str
    admission_digest: str
    pre_observation_digest: str
    post_observation_digest: str
    expected_sha256: str
    observed_sha256: str | None
    result: str
    reconciled_at: str
    reconciliation_digest: str
    authority_effect: bool = False
    repository_effect: bool = False
    external_network_effect: bool = False

    def validate(self):
        for name in ("effect_key", "request_digest", "admission_digest", "pre_observation_digest", "post_observation_digest", "expected_sha256", "reconciliation_digest"):
            _hex64(getattr(self, name), name)
        if self.observed_sha256 is not None:
            _hex64(self.observed_sha256, "observed_sha256")
        if self.result not in {"MATCH", "MISMATCH", "UNKNOWN"} or self.authority_effect or self.repository_effect or self.external_network_effect:
            raise MoonFileWriteMediationError("reconciliation receipt invalid")
        return self


class CanonicalMoonFileWriteMediator:
    def __init__(self, *, admissions: MoonFileWriteAdmissionResolver, effect: MoonFileWriteEffect,
                 fence: DurableMoonFileWriteFence, pre_observer: MoonFileWriteObserver, post_observer: MoonFileWriteObserver):
        if not callable(getattr(admissions, "resolve", None)) or not callable(getattr(effect, "write_exact", None)):
            raise MoonFileWriteMediationError("canonical dependencies unavailable")
        if type(fence) is not DurableMoonFileWriteFence:
            raise MoonFileWriteMediationError("exact durable fence required")
        if type(pre_observer) is not MoonFileWriteObserver or type(post_observer) is not MoonFileWriteObserver or pre_observer is post_observer:
            raise MoonFileWriteMediationError("independent observer instances required")
        self.admissions=admissions; self.effect=effect; self.fence=fence; self.pre_observer=pre_observer; self.post_observer=post_observer

    @staticmethod
    def _require_pre_state(request: MoonFileWriteRequest, obs: MoonFileTargetObservation) -> None:
        obs.validate()
        if request.operation_mode == "CREATE_ONLY":
            if obs.exists:
                raise MoonFileWriteMediationError("CREATE_ONLY target exists")
        elif not (obs.exists and obs.regular_file and not obs.symlink and obs.sha256 == request.expected_previous_sha256):
            raise MoonFileWriteMediationError("REPLACE pre-state mismatch")

    def execute(self, request: MoonFileWriteRequest) -> MoonFileWriteReconciliationReceipt:
        request.validate()
        pre = self.pre_observer.observe(request.target_path); self._require_pre_state(request, pre)
        admission = self.admissions.resolve(request)
        if type(admission) is not CanonicalMoonFileWriteAdmission:
            raise MoonFileWriteMediationError("exact admission required")
        admission.validate(); admission.binds(request); _hex64(admission.admission_digest, "admission_digest")
        effect_key = moon_file_write_effect_key(request, admission)
        self.fence.prepare(MoonFileWriteFenceRecord(effect_key, admission.admission_digest, request.request_digest,
            request.repository, request.target_path, "PREPARED", _now(), pre_observation_digest=pre.observation_digest))
        try:
            current_admission = self.admissions.resolve(request)
            if type(current_admission) is not CanonicalMoonFileWriteAdmission or current_admission.validate().admission_digest != admission.admission_digest:
                raise MoonFileWriteMediationError("authority drift")
            current_pre = self.pre_observer.observe(request.target_path); self._require_pre_state(request, current_pre)
            if current_pre.observation_digest != pre.observation_digest:
                raise MoonFileWriteMediationError("target currentness drift")
            self.fence.mark_attempted(effect_key, _now())
            self.effect.write_exact(request, admission)
            post = self.post_observer.observe(request.target_path)
            self.fence.mark_observed(effect_key, _now(), post.observation_digest)
            result = "MATCH" if post.exists and post.regular_file and not post.symlink and post.sha256 == request.intended_content_sha256 and post.size == request.intended_content_size else "MISMATCH"
            reconciliation_digest = _digest(b"LION/MOON-FILE-WRITE-RECONCILIATION/1\0", {
                "effect_key": effect_key, "request_digest": request.request_digest,
                "admission_digest": admission.admission_digest, "pre": pre.observation_digest,
                "post": post.observation_digest, "expected": request.intended_content_sha256,
                "observed": post.sha256, "result": result,
            })
            if result != "MATCH":
                self.fence.mark_unknown(effect_key)
            else:
                self.fence.mark_reconciled(effect_key, _now(), reconciliation_digest)
            return MoonFileWriteReconciliationReceipt(effect_key, request.request_digest, admission.admission_digest,
                pre.observation_digest, post.observation_digest, request.intended_content_sha256, post.sha256, result,
                _now(), reconciliation_digest).validate()
        except Exception:
            try:
                if self.fence.get(effect_key).state in {"PREPARED", "ATTEMPTED", "OBSERVED"}:
                    self.fence.mark_unknown(effect_key)
            except Exception:
                pass
            raise

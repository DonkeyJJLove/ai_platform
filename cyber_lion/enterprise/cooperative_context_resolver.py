"""Resolve an assigned product to an existing canonical runtime context.

This is a read-only adapter, not an admission issuer or a second state store.
Assignment/control/driver state is read from the existing Mission Control DB.
The trusted composition root supplies immutable per-assignment file pins and
independently configured admission, dispatch and live runtime identity sources.
The file carries references and existing contracts; it cannot supply authority.
No model payload is used to choose a file, trust pin or source implementation.

A DB snapshot is locally consistent, not a distributed transaction with the
other sources. The original effect-time guard and sandbox fence still run after
resolution. Protect the configured directories from hostile same-UID writes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from types import MappingProxyType
from typing import Any, Callable, Mapping

from cyber_lion.contracts.executor_sandbox import (
    ExecutionSandboxPolicy, FleetDispatchBinding, ProvisioningBinding,
    SandboxResourceLimits, SandboxRuntimeBinding,
)
from cyber_lion.contracts.runtime_enforcement import (
    RequestedRuntimeEffect, RuntimeAdmission, RuntimeIdentityBinding,
)
from cyber_lion.contracts.runtime_execution import (
    RuntimeAdmissionSourceTrustBinding, RuntimeExecutionRequest,
)
from cyber_lion.enterprise.cooperative_runtime_composition import CooperativeRuntimeContext
from cyber_lion.enterprise.cooperative_runtime_writer import CooperativeExecutionBinding
from cyber_lion.mission_control import operator_control
from cyber_lion.mission_control.cooperative_artifacts import artifact_path, validate_write_payload
from tools.lion_cooperative_worker_adapter import assignment_input

SCHEMA = "lion.cooperative-runtime-context-reference/v1"
MAX_RECORD_BYTES = 262144
COORDINATES = frozenset({
    "assignment_id", "mission_id", "phase_id", "driver_phase_id", "worker_id",
    "generation", "control_epoch", "context_revision", "plan_revision",
    "input_digest", "lpcl_digest",
})
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class CooperativeContextResolutionError(ValueError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CooperativeContextResolutionError(reason)


def _exact(value: Any, names, label: str) -> dict:
    _require(type(value) is dict and set(value) == set(names), label + " fields")
    return dict(value)


def _utc(value: Any) -> datetime:
    _require(type(value) is str, "timestamp type")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CooperativeContextResolutionError("timestamp format") from exc
    _require(parsed.tzinfo is not None, "timestamp timezone")
    return parsed.astimezone(timezone.utc)


def _path(value: Path, *, directory: bool) -> Path:
    p = Path(value)
    _require(p.is_absolute() and not p.is_symlink(), "configured path must be absolute and direct")
    _require(p == p.resolve(strict=True), "configured path symlink indirection")
    _require(p.is_dir() if directory else p.is_file(), "configured path unavailable")
    return p


def _decode(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, "duplicate context JSON key")
            result[key] = value
        return result
    def nonfinite(_):
        raise CooperativeContextResolutionError("nonfinite context JSON")
    _require(0 < len(raw) <= MAX_RECORD_BYTES, "context byte limit")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CooperativeContextResolutionError("context JSON invalid") from exc
    return _exact(value, {"schema", "coordinates", "execution", "policy", "runtime", "dispatch", "provisioning"}, "context")


def _contract(cls, value):
    item = _exact(value, (f.name for f in fields(cls)), cls.__name__)
    for f in fields(cls):
        if str(f.type).startswith("tuple["):
            _require(type(item[f.name]) is list, f.name + " array required")
            if str(f.type).startswith("tuple[tuple["):
                _require(all(type(x) is list for x in item[f.name]), f.name + " nested arrays")
                item[f.name] = tuple(tuple(x) for x in item[f.name])
            else:
                item[f.name] = tuple(item[f.name])
    if cls is ExecutionSandboxPolicy:
        item["resource_limits"] = _contract(SandboxResourceLimits, item["resource_limits"])
    try:
        return cls(**item).validate()
    except (TypeError, ValueError) as exc:
        raise CooperativeContextResolutionError(cls.__name__ + " invalid") from exc


def context_reference_bytes(context: CooperativeRuntimeContext, coordinates: dict) -> bytes:
    """Serialize already-provisioned contracts for the trusted publisher.

    Does not publish a file, install a pin, issue an admission, or prove source
    authenticity. The independent composition root decides which digest to pin.
    """
    _require(type(context) is CooperativeRuntimeContext, "typed context required")
    context.validate()
    coords = _exact(coordinates, COORDINATES, "coordinates")
    b = context.execution
    _require((coords["assignment_id"], coords["worker_id"], coords["input_digest"], coords["mission_id"], coords["generation"]) ==
             (b.assignment_id, b.worker_id, b.input_digest, b.request.mission_id, b.request.generation), "publisher context association mismatch")
    for key in ("generation", "control_epoch", "context_revision", "plan_revision"):
        _require(type(coords[key]) is int and coords[key] >= (1 if key == "generation" else 0), "publisher integer coordinate")
    for key in ("input_digest", "lpcl_digest"):
        _require(type(coords[key]) is str and _SHA.fullmatch(coords[key]) is not None, "publisher digest coordinate")
    for key in ("assignment_id", "mission_id", "phase_id", "driver_phase_id", "worker_id"):
        _require(type(coords[key]) is str and _ID.fullmatch(coords[key]) is not None, "publisher identity coordinate")
    value = asdict(context)
    value["execution"]["artifact_root"] = str(b.artifact_root)
    value["execution"].pop("admission")
    value["execution"]["admission_digest"] = b.admission.admission_digest
    value.update(schema=SCHEMA, coordinates=coords)
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    _require(len(data) <= MAX_RECORD_BYTES, "context byte limit")
    return data


@dataclass(frozen=True)
class CooperativeContextPin:
    assignment_id: str
    filename: str
    sha256: str

    def validate(self):
        _require(type(self.assignment_id) is str and _ID.fullmatch(self.assignment_id) is not None, "pin assignment")
        _require(type(self.filename) is str and _FILE.fullmatch(self.filename) is not None, "pin filename")
        _require(type(self.sha256) is str and _SHA.fullmatch(self.sha256) is not None, "pin digest")
        return self


class PinnedCooperativeContextResolver:
    """Callable context_source for CooperativeRuntimeWriterProvider.

    Pins are constructor inputs from the existing trusted control plane. They
    are not extracted from an assignment, model response or the context itself.
    Admission objects are fetched only from the original RuntimeAdmissionSource.
    The context JSON intentionally contains no embedded admission object.
    """
    def __init__(self, *, mission_db: Path, context_directory: Path,
                 pins: tuple[CooperativeContextPin, ...], admission_source,
                 admission_trust: RuntimeAdmissionSourceTrustBinding,
                 dispatch_source, runtime_identity_source: Callable[[str], RuntimeIdentityBinding],
                 now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self._db = _path(mission_db, directory=False)
        self._root = _path(context_directory, directory=True)
        _require(type(pins) is tuple, "immutable pin tuple required")
        index = {}
        for pin in pins:
            _require(type(pin) is CooperativeContextPin, "pin type")
            pin.validate()
            _require(pin.assignment_id not in index, "duplicate assignment pin")
            index[pin.assignment_id] = pin
        self._pins = MappingProxyType(index)
        _require(type(admission_trust) is RuntimeAdmissionSourceTrustBinding, "admission trust required")
        admission_trust.validate()
        self._source, self._trust = admission_source, admission_trust
        self._check_source()
        _require(callable(getattr(dispatch_source, "current_dispatch", None)), "dispatch source required")
        _require(callable(runtime_identity_source) and callable(now_fn), "runtime identity source and clock required")
        self._dispatch, self._identity, self._now = dispatch_source, runtime_identity_source, now_fn
        st = self._db.stat()
        self._db_identity = (st.st_dev, st.st_ino)

    def _check_source(self):
        source = self._source
        actual = tuple(getattr(source, name, None) for name in (
            "source_id", "source_instance_id", "implementation_digest", "trust_anchor_id", "trust_anchor_digest"))
        _require(actual == self._trust.binding(), "admission source substitution")
        _require(all(callable(getattr(source, x, None)) for x in ("resolve", "is_current")), "admission source unavailable")

    def _record(self, pin):
        _path(self._root, directory=True)
        target = self._root / pin.filename
        _require(not target.is_symlink(), "context symlink")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(target, flags)
        with os.fdopen(fd, "rb") as handle:
            before = os.fstat(handle.fileno())
            _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "context must be a private regular file")
            raw = handle.read(MAX_RECORD_BYTES + 1)
            after = os.fstat(handle.fileno())
        names = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        _require(all(getattr(before, x) == getattr(after, x) for x in names), "context changed during read")
        _require(sha256(raw).hexdigest() == pin.sha256, "context pin mismatch")
        return _decode(raw)

    def _snapshot(self, assignment_id):
        db = _path(self._db, directory=False)
        st = db.stat()
        _require((st.st_dev, st.st_ino) == self._db_identity, "Mission Control DB replaced")
        conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=2)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN")
            row = conn.execute("SELECT * FROM mission_execution_assignments WHERE assignment_id=?", (assignment_id,)).fetchone()
            _require(row is not None, "assignment unavailable")
            assignment = dict(row)
            mid = assignment["mission_id"]
            rows = {
                "mission": conn.execute("SELECT * FROM missions WHERE mission_id=?", (mid,)).fetchone(),
                "spec": conn.execute("SELECT * FROM mission_process_specs WHERE mission_id=?", (mid,)).fetchone(),
                "driver": conn.execute("SELECT * FROM mission_execution_drivers WHERE mission_id=?", (mid,)).fetchone(),
                "control": conn.execute("SELECT * FROM mission_operator_control WHERE mission_id=?", (mid,)).fetchone(),
            }
            result = {}
            for name, value in rows.items():
                _require(value is not None, name + " binding unavailable")
                result[name] = dict(value)
            inp = assignment_input(assignment)
            capability = inp.get("capability")
            _require(type(capability) is str and bool(capability), "assignment capability missing")
            # Absence of this canonical table is an error, not an empty revocation set.
            conn.execute("SELECT capability FROM operator_capability_revocations WHERE mission_id=? LIMIT 0", (mid,))
            _require(operator_control.assignment_allowed(conn, mid, assignment["dispatch_authority"], assignment["control_epoch"]), "operator control fence")
            _require(not operator_control.is_capability_revoked(conn, mid, capability), "capability revoked")
            result.update(assignment=assignment, input=inp)
            return result
        except sqlite3.Error as exc:
            raise CooperativeContextResolutionError("canonical Mission Control snapshot unavailable") from exc
        finally:
            conn.close()

    def _resolve(self, assignment_id: str, *, assignment_state: str) -> CooperativeRuntimeContext:
        _require(assignment_state in {"CLAIMED", "READY"}, "resolver assignment state")
        _require(type(assignment_id) is str and assignment_id in self._pins, "assignment context pin unavailable")
        snap = self._snapshot(assignment_id)
        record = self._record(self._pins[assignment_id])
        _require(record["schema"] == SCHEMA, "context schema")
        coords = _exact(record["coordinates"], COORDINATES, "coordinates")
        a, driver, control, spec, mission = (snap[n] for n in ("assignment", "driver", "control", "spec", "mission"))
        actual = {
            "assignment_id": a["assignment_id"], "mission_id": a["mission_id"], "phase_id": a["phase_id"],
            "driver_phase_id": driver["current_phase"], "worker_id": a["material_drone_id"],
            "generation": a["lease_generation"], "control_epoch": a["control_epoch"],
            "context_revision": a["context_revision"], "plan_revision": a["plan_revision"],
            "input_digest": a["input_digest"], "lpcl_digest": spec["lpcl_digest"],
        }
        for name in ("generation", "control_epoch", "context_revision", "plan_revision"):
            _require(type(coords[name]) is int and coords[name] >= (1 if name == "generation" else 0), "coordinate integer required")
        _require(coords == actual, "context/assignment coordinates mismatch")
        _require(a["state"] == assignment_state and driver["state"] in {"ACTIVE", "WAITING"}, "assignment/driver not active")
        _require(mission["state"] in {"RUNNING", "WAITING", "BLOCKED"}, "mission not executing")
        _require(driver["generation"] == a["lease_generation"], "stale driver generation")
        _require(all(control[n] == a[n] for n in ("control_epoch", "context_revision", "plan_revision")), "stale control/context/plan revision")
        now = self._now()
        _require(isinstance(now, datetime) and now.tzinfo is not None, "trusted zoned clock required")
        _require(now < _utc(a["lease_expires_at"]) and now < _utc(driver["lease_expires_at"]), "expired assignment/driver lease")
        _require(spec["authority_state"] == "EXPLICIT_USER_ACTIVATION", "LPCL not explicitly activated")
        lpcl = spec["lpcl_text"]
        _require(type(lpcl) is str and sha256(lpcl.encode("utf-8")).hexdigest() == spec["lpcl_digest"] == mission["spec_digest"], "LPCL byte binding mismatch")
        ex = _exact(record["execution"], {"assignment_id", "worker_id", "input_digest", "artifact_root", "admission_digest", "request", "effect", "identity"}, "execution")
        _require((ex["assignment_id"], ex["worker_id"], ex["input_digest"]) == (assignment_id, a["material_drone_id"], a["input_digest"]), "execution association mismatch")
        self._check_source()
        dg = ex["admission_digest"]
        _require(type(dg) is str and _SHA.fullmatch(dg) is not None, "admission reference invalid")
        admission = self._source.resolve(dg)
        _require(type(admission) is RuntimeAdmission, "canonical admission unavailable")
        admission.validate()
        _require(admission.admission_digest == dg and self._source.is_current(dg) is True, "stale or substituted admission")
        binding = CooperativeExecutionBinding(assignment_id, ex["worker_id"], ex["input_digest"],
            _path(Path(ex["artifact_root"]), directory=True), admission,
            _contract(RuntimeExecutionRequest, ex["request"]), _contract(RequestedRuntimeEffect, ex["effect"]),
            _contract(RuntimeIdentityBinding, ex["identity"]))
        ctx = CooperativeRuntimeContext(binding, _contract(ExecutionSandboxPolicy, record["policy"]),
            _contract(SandboxRuntimeBinding, record["runtime"]), _contract(FleetDispatchBinding, record["dispatch"]),
            _contract(ProvisioningBinding, record["provisioning"])).validate()
        _require(ctx.policy.drone_id == a["logical_drone_id"], "logical workload substitution")
        observed = self._identity(binding.identity.runtime_instance_id)
        _require(type(observed) is RuntimeIdentityBinding and observed.validate() == binding.identity, "live runtime identity substitution")
        dispatch = self._dispatch.current_dispatch(a["mission_id"])
        _require(type(dispatch) is FleetDispatchBinding and dispatch.validate().digest() == ctx.dispatch.digest(), "stale live dispatch")
        _require(snap["input"].get("assignment_id", assignment_id) == assignment_id, "payload assignment substitution")
        _require(snap["input"].get("mission_id") == a["mission_id"] and type(snap["input"].get("generation")) is int and snap["input"]["generation"] == a["lease_generation"], "payload mission/generation substitution")
        _require(admission.requested_effect_digest == binding.effect.digest() == binding.request.requested_effect_digest, "admission/effect association mismatch")
        _require(admission.runtime_identity_digest == binding.identity.digest() == binding.request.runtime_identity_digest == binding.effect.runtime_identity_digest, "admission/runtime association mismatch")
        _require(admission.policy_binding == binding.effect.policy_binding, "admission/policy association mismatch")
        payload = {**snap["input"], "assignment_id": assignment_id}
        metadata, data = validate_write_payload(payload, a["material_drone_id"])
        target = artifact_path(binding.artifact_root, mission_id=metadata["mission_id"], generation=metadata["generation"], artifact_name=metadata["artifact_name"])
        req = binding.request
        _require((req.mission_id, req.generation, req.resource, req.payload_digest, req.payload_size, req.admission_digest) ==
                 (a["mission_id"], a["lease_generation"], target.relative_to(binding.artifact_root).as_posix(), metadata["artifact_sha256"], len(data), dg), "artifact/request binding mismatch")
        return ctx

    def __call__(self, assignment_id: str) -> CooperativeRuntimeContext:
        """Effect-path resolution requires the canonical CLAIMED state."""
        return self._resolve(assignment_id, assignment_state="CLAIMED")

    def resolve_for_qualification(self, assignment_id: str) -> CooperativeRuntimeContext:
        """Read-only qualification view over an already released READY assignment."""
        return self._resolve(assignment_id, assignment_state="READY")

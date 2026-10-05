"""Trusted composition root for cooperative runtime materialization and worker use.

This root consumes already-issued canonical runtime evidence. It does not run PDP,
mint RuntimeAdmission, create authority, schedule missions or start workers.

Mission Control side:
  existing canonical context/admission/provisioning sources
  -> exact re-observation
  -> durable admission copy
  -> private context / verifier transfer
  -> durable materialization descriptor
  -> R6.8 non-authorizing materializer provider

Worker side:
  durable descriptor + durable admission source
  -> PinnedCooperativeContextResolver
  -> CooperativeRuntimeWriterProvider
  -> existing RuntimeExecutionEngine / currentness / ExecutorSandbox

The same class can be instantiated in another process over the same trusted read-only
Mission Control view and private stores. No process-local object is treated as authority.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import stat
from typing import Any, Callable, Mapping

from cyber_lion.contracts.executor_sandbox import ProvisioningBinding
from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding
from cyber_lion.contracts.runtime_enforcement import RuntimeAdmission, RuntimeIdentityBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.cooperative_context_resolver import (
    CooperativeContextPin,
    PinnedCooperativeContextResolver,
)
from cyber_lion.enterprise.cooperative_provider_materialization import (
    CONTEXT_FILENAME,
    CooperativeContextMaterialization,
    CooperativeVerifierMaterialization,
    materialize_context_reference,
    materialize_verifier_view,
    provider_status_marker,
)
from cyber_lion.enterprise.cooperative_runtime_composition import (
    CooperativeRuntimeContext,
    CooperativeRuntimeWriterProvider,
)
from cyber_lion.enterprise.executor_sandbox import (
    SQLiteSandboxBudgetLedger,
    SQLiteSandboxReplayGuard,
)
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority, LiveAuthorityAdmission
from cyber_lion.enterprise.runtime_execution import (
    RuntimeExecutionError,
    SQLiteAdmissionConsumptionGuard,
    SQLiteRuntimeAdmissionSource,
)
from cyber_lion.mission_control.cooperative_artifacts import VERIFY_KIND, WRITE_KIND
from cyber_lion.mission_control.global_scheduler import ASSIGNMENT_RELEASE_EVIDENCE_SCHEMA
from cyber_lion.mission_control.cooperative_materialization_registry import (
    CooperativeMaterializationProvider,
)
from cyber_lion.mission_control.cooperative_production import (
    VERIFY_PROVIDER_ID,
    WRITE_PROVIDER_ID,
)
from tools.lion_cooperative_worker_adapter import assignment_input

STORE_SCHEMA = "lion.cooperative-runtime-materialization-store/v1"
PROVENANCE_DOMAIN = b"LION/COOPERATIVE-RUNTIME-ADMISSION-COPY/1\0"
QUALIFICATION_DOMAIN = b"LION/COOPERATIVE-WORKER-QUALIFICATION/1\0"
_RELEASE_EVIDENCE_FIELDS = frozenset({
    "schema", "assignment_id", "mission_id", "material_drone_id", "lease_generation",
    "control_epoch", "context_revision", "plan_revision", "capability",
    "materialization_kind", "provider_id", "evidence_digest", "authority_effect",
})
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class CooperativeRuntimeRootError(RuntimeError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CooperativeRuntimeRootError(reason)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _strict_json(raw: str, label: str) -> dict[str, Any]:
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
            parse_constant=lambda _: (_ for _ in ()).throw(CooperativeRuntimeRootError(label + " nonfinite JSON")),
        )
    except CooperativeRuntimeRootError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError, UnicodeError) as exc:
        raise CooperativeRuntimeRootError(label + " JSON invalid") from exc
    _require(type(value) is dict, label + " object required")
    return value


def _direct_dir(value: str | Path, label: str) -> Path:
    path = Path(value)
    _require(path.is_absolute() and path.is_dir() and not path.is_symlink(), label)
    _require(path == path.resolve(strict=True), label + " symlink indirection")
    return path


def _direct_file(value: str | Path, label: str) -> Path:
    path = Path(value)
    _require(path.is_absolute() and path.is_file() and not path.is_symlink(), label)
    _require(path == path.resolve(strict=True), label + " symlink indirection")
    st = path.stat()
    _require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, label + " private regular file")
    return path


def _state_db_path(value: str | Path) -> Path:
    path = Path(value)
    _require(path.is_absolute(), "materialization DB path must be absolute")
    _direct_dir(path.parent, "materialization DB parent")
    _require(not path.is_symlink(), "materialization DB symlink")
    return path


def _state_identity(path: Path) -> tuple[int, int]:
    try:
        st = path.stat()
    except OSError as exc:
        raise CooperativeRuntimeRootError("materialization DB unavailable") from exc
    _require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, "materialization DB private regular file")
    return st.st_dev, st.st_ino


def _zoned(value: datetime) -> datetime:
    _require(isinstance(value, datetime) and value.tzinfo is not None, "trusted zoned clock required")
    return value.astimezone(timezone.utc)


def _digest(value: str, label: str) -> str:
    _require(type(value) is str and _SHA.fullmatch(value) is not None, label)
    return value


def _identity(value: str, label: str) -> str:
    _require(type(value) is str and _ID.fullmatch(value) is not None, label)
    return value


class SQLiteCooperativeMaterializationStore:
    """Immutable cross-process index of private context/verifier workspaces.

    Records are non-authorizing. Every read revalidates DB identity and the underlying
    transfer/pin bytes through the R6.7 materialization contracts.
    """

    def __init__(self, path: str | Path, *, context_parent: str | Path, verifier_parent: str | Path):
        self.path = _state_db_path(path)
        self.context_parent = _direct_dir(context_parent, "context private parent")
        self.verifier_parent = _direct_dir(verifier_parent, "verifier private parent")
        self._context_parent_identity = self._dir_identity(self.context_parent)
        self._verifier_parent_identity = self._dir_identity(self.verifier_parent)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS cooperative_context_materialization(
                  assignment_id TEXT PRIMARY KEY,
                  worker_id TEXT NOT NULL,
                  admission_digest TEXT NOT NULL,
                  descriptor_digest TEXT NOT NULL UNIQUE,
                  descriptor_json TEXT NOT NULL,
                  recorded_at TEXT NOT NULL,
                  schema_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cooperative_verifier_materialization(
                  consumer_assignment_id TEXT PRIMARY KEY,
                  source_assignment_id TEXT NOT NULL,
                  verifier_worker_id TEXT NOT NULL,
                  descriptor_digest TEXT NOT NULL UNIQUE,
                  descriptor_json TEXT NOT NULL,
                  recorded_at TEXT NOT NULL,
                  schema_id TEXT NOT NULL
                );
                """
            )
        self._db_identity = _state_identity(self.path)

    @staticmethod
    def _dir_identity(path: Path) -> tuple[int, int]:
        st = path.stat()
        _require(stat.S_ISDIR(st.st_mode), "private parent directory identity")
        return st.st_dev, st.st_ino

    def _check(self) -> None:
        _require(not self.path.is_symlink() and _state_identity(self.path) == self._db_identity,
                 "materialization DB identity drift")
        _require(self._dir_identity(_direct_dir(self.context_parent, "context private parent"))
                 == self._context_parent_identity, "context parent identity drift")
        _require(self._dir_identity(_direct_dir(self.verifier_parent, "verifier private parent"))
                 == self._verifier_parent_identity, "verifier parent identity drift")

    @staticmethod
    def _descriptor_digest(value: Mapping[str, Any]) -> str:
        return sha256(b"LION/COOPERATIVE-MATERIALIZATION-DESCRIPTOR/1\0" + _canonical(dict(value))).hexdigest()

    @staticmethod
    def _workspace_name(workspace: Path, parent: Path) -> str:
        workspace = workspace.resolve(strict=True)
        _require(workspace.parent == parent, "materialization workspace parent substitution")
        _require(workspace.name and workspace.name not in {".", ".."} and "/" not in workspace.name and "\\" not in workspace.name,
                 "materialization workspace name")
        return workspace.name

    def record_context(
        self,
        materialization: CooperativeContextMaterialization,
        *,
        worker_id: str,
        admission_digest: str,
        recorded_at: datetime,
    ) -> str:
        self._check()
        materialization.validate()
        worker = _identity(worker_id, "context worker identity")
        admission = _digest(admission_digest, "context admission digest")
        _require(materialization.assignment_id == materialization.pin.assignment_id, "context assignment/pin mismatch")
        descriptor = {
            "schema": STORE_SCHEMA,
            "kind": "CONTEXT",
            "assignment_id": materialization.assignment_id,
            "worker_id": worker,
            "workspace_name": self._workspace_name(materialization.workspace, self.context_parent),
            "context_filename": materialization.pin.filename,
            "context_sha256": materialization.pin.sha256,
            "transfer_sha256": materialization.transfer_sha256,
            "transfer_binding": dict(materialization.transfer_binding),
            "artifact_root": str(materialization.artifact_root),
            "admission_digest": admission,
            "authority_effect": "NONE",
        }
        dg = self._descriptor_digest(descriptor)
        raw = _canonical(descriptor).decode("utf-8")
        stamp = _zoned(recorded_at).isoformat()
        try:
            with closing(sqlite3.connect(self.path, timeout=5, isolation_level=None)) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute(
                        "INSERT INTO cooperative_context_materialization VALUES(?,?,?,?,?,?,?)",
                        (materialization.assignment_id, worker, admission, dg, raw, stamp, STORE_SCHEMA),
                    )
                    db.execute("COMMIT")
                except Exception:
                    if db.in_transaction:
                        db.execute("ROLLBACK")
                    raise
        except sqlite3.IntegrityError as exc:
            raise CooperativeRuntimeRootError("context materialization replay denied") from exc
        return dg

    def resolve_context(self, assignment_id: str) -> tuple[CooperativeContextMaterialization, str, str]:
        self._check()
        aid = _identity(assignment_id, "context assignment identity")
        try:
            with closing(sqlite3.connect(self.path, timeout=5)) as db:
                rows = db.execute(
                    "SELECT worker_id,admission_digest,descriptor_digest,descriptor_json,schema_id "
                    "FROM cooperative_context_materialization WHERE assignment_id=?",
                    (aid,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise CooperativeRuntimeRootError("context materialization store unavailable") from exc
        _require(len(rows) == 1 and rows[0][4] == STORE_SCHEMA, "context materialization unavailable or ambiguous")
        worker, admission, dg, raw, _ = rows[0]
        value = _strict_json(raw, "context materialization descriptor")
        _require(type(value) is dict and self._descriptor_digest(value) == dg, "context materialization descriptor digest")
        _require(value.get("assignment_id") == aid and value.get("worker_id") == worker
                 and value.get("admission_digest") == admission and value.get("authority_effect") == "NONE",
                 "context materialization descriptor association")
        workspace = self.context_parent / str(value.get("workspace_name"))
        materialization = CooperativeContextMaterialization(
            aid,
            workspace,
            CooperativeContextPin(aid, str(value.get("context_filename")), str(value.get("context_sha256"))).validate(),
            str(value.get("transfer_sha256")),
            dict(value.get("transfer_binding") or {}),
            Path(str(value.get("artifact_root"))),
        ).validate()
        return materialization, _identity(worker, "context worker identity"), _digest(admission, "context admission digest")

    def record_verifier(
        self,
        materialization: CooperativeVerifierMaterialization,
        *,
        verifier_worker_id: str,
        recorded_at: datetime,
    ) -> str:
        self._check()
        materialization.validate()
        worker = _identity(verifier_worker_id, "verifier worker identity")
        descriptor = {
            "schema": STORE_SCHEMA,
            "kind": "VERIFIER",
            "consumer_assignment_id": materialization.consumer_assignment_id,
            "source_assignment_id": materialization.source_assignment_id,
            "verifier_worker_id": worker,
            "workspace_name": self._workspace_name(materialization.workspace, self.verifier_parent),
            "transfer_sha256": materialization.transfer_sha256,
            "transfer_binding": dict(materialization.transfer_binding),
            "artifact_sha256": materialization.artifact_sha256,
            "artifact_path": materialization.artifact_path,
            "authority_effect": "NONE",
        }
        dg = self._descriptor_digest(descriptor)
        raw = _canonical(descriptor).decode("utf-8")
        stamp = _zoned(recorded_at).isoformat()
        try:
            with closing(sqlite3.connect(self.path, timeout=5, isolation_level=None)) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute(
                        "INSERT INTO cooperative_verifier_materialization VALUES(?,?,?,?,?,?,?)",
                        (materialization.consumer_assignment_id, materialization.source_assignment_id,
                         worker, dg, raw, stamp, STORE_SCHEMA),
                    )
                    db.execute("COMMIT")
                except Exception:
                    if db.in_transaction:
                        db.execute("ROLLBACK")
                    raise
        except sqlite3.IntegrityError as exc:
            raise CooperativeRuntimeRootError("verifier materialization replay denied") from exc
        return dg

    def resolve_verifier(self, consumer_assignment_id: str) -> tuple[CooperativeVerifierMaterialization, str]:
        self._check()
        aid = _identity(consumer_assignment_id, "verifier consumer assignment identity")
        try:
            with closing(sqlite3.connect(self.path, timeout=5)) as db:
                rows = db.execute(
                    "SELECT source_assignment_id,verifier_worker_id,descriptor_digest,descriptor_json,schema_id "
                    "FROM cooperative_verifier_materialization WHERE consumer_assignment_id=?",
                    (aid,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise CooperativeRuntimeRootError("verifier materialization store unavailable") from exc
        _require(len(rows) == 1 and rows[0][4] == STORE_SCHEMA, "verifier materialization unavailable or ambiguous")
        source, worker, dg, raw, _ = rows[0]
        value = _strict_json(raw, "verifier materialization descriptor")
        _require(type(value) is dict and self._descriptor_digest(value) == dg, "verifier materialization descriptor digest")
        _require(value.get("consumer_assignment_id") == aid and value.get("source_assignment_id") == source
                 and value.get("verifier_worker_id") == worker and value.get("authority_effect") == "NONE",
                 "verifier materialization descriptor association")
        materialization = CooperativeVerifierMaterialization(
            aid,
            str(source),
            self.verifier_parent / str(value.get("workspace_name")),
            str(value.get("transfer_sha256")),
            dict(value.get("transfer_binding") or {}),
            str(value.get("artifact_sha256")),
            str(value.get("artifact_path")),
        ).validate()
        return materialization, _identity(worker, "verifier worker identity")


class CooperativeRuntimeCompositionRoot:
    """Composition root over existing authority/admission/provisioning owners."""

    def __init__(
        self,
        *,
        mission_db: str | Path,
        artifact_root: str | Path,
        context_parent: str | Path,
        verifier_parent: str | Path,
        materialization_db: str | Path,
        runtime_state_db: str | Path,
        context_source: Callable[[str], CooperativeRuntimeContext],
        qualification_context_source: Callable[[str], CooperativeRuntimeContext],
        upstream_admission_source,
        upstream_admission_trust: RuntimeAdmissionSourceTrustBinding,
        durable_admission_trust: RuntimeAdmissionSourceTrustBinding,
        authority_admission: LiveAuthorityAdmission,
        currentness_source,
        currentness_trust: CurrentnessSourceTrustBinding,
        dispatch_source,
        runtime_identity_source: Callable[[str], RuntimeIdentityBinding],
        provisioning_binding_source: Callable[[str], ProvisioningBinding],
        transfer_binding_source: Callable[[str, str], Mapping[str, Any]],
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.mission_db = _direct_file(mission_db, "Mission Control DB")
        self.artifact_root = _direct_dir(artifact_root, "artifact root")
        self.context_parent = _direct_dir(context_parent, "context private parent")
        self.verifier_parent = _direct_dir(verifier_parent, "verifier private parent")
        for callback, label in (
            (context_source, "context source"),
            (qualification_context_source, "qualification context source"),
            (runtime_identity_source, "runtime identity source"),
            (provisioning_binding_source, "provisioning binding source"),
            (transfer_binding_source, "transfer binding source"),
            (now_fn, "trusted clock"),
        ):
            _require(callable(callback), label)
        _require(isinstance(authority_admission, LiveAuthorityAdmission), "canonical LiveAuthorityAdmission required")
        _require(type(upstream_admission_trust) is RuntimeAdmissionSourceTrustBinding,
                 "upstream admission trust required")
        _require(type(durable_admission_trust) is RuntimeAdmissionSourceTrustBinding,
                 "durable admission trust required")
        _require(type(currentness_trust) is CurrentnessSourceTrustBinding,
                 "currentness trust required")
        upstream_admission_trust.validate(); durable_admission_trust.validate(); currentness_trust.validate()
        self._assert_source_binding(upstream_admission_source, upstream_admission_trust.binding(), ("resolve", "is_current"),
                                    "upstream admission source")
        self._assert_source_binding(currentness_source, currentness_trust.binding(),
                                    ("resolve_authority", "current_policy_binding", "current_observability_state"),
                                    "currentness source")
        _require(callable(getattr(dispatch_source, "current_dispatch", None)), "dispatch source")
        self.context_source = context_source
        self.qualification_context_source = qualification_context_source
        self.upstream_admission_source = upstream_admission_source
        self.upstream_admission_trust = upstream_admission_trust
        self.durable_admission_trust = durable_admission_trust
        self.authority_admission = authority_admission
        self.currentness_source = currentness_source
        self.currentness_trust = currentness_trust
        self.dispatch_source = dispatch_source
        self.runtime_identity_source = runtime_identity_source
        self.provisioning_binding_source = provisioning_binding_source
        self.transfer_binding_source = transfer_binding_source
        self.now_fn = now_fn

        self.store = SQLiteCooperativeMaterializationStore(
            materialization_db,
            context_parent=self.context_parent,
            verifier_parent=self.verifier_parent,
        )
        self.admission_source = SQLiteRuntimeAdmissionSource(runtime_state_db, durable_admission_trust)
        self.admission_guard = SQLiteAdmissionConsumptionGuard(runtime_state_db)
        self.sandbox_guard = SQLiteSandboxReplayGuard(runtime_state_db)
        self.runtime_state_db = _direct_file(runtime_state_db, "runtime state DB")
        self._runtime_state_identity = _state_identity(self.runtime_state_db)
        self._writers: dict[str, CooperativeRuntimeWriterProvider] = {}

    @staticmethod
    def _assert_source_binding(source, expected, methods: tuple[str, ...], label: str) -> None:
        actual = tuple(getattr(source, name, None) for name in (
            "source_id", "source_instance_id", "implementation_digest", "trust_anchor_id", "trust_anchor_digest",
        ))
        _require(actual == expected, label + " substitution")
        _require(all(callable(getattr(source, name, None)) for name in methods), label + " unavailable")

    def _snapshot(self, assignment_id: str, *, require_held: bool) -> dict[str, Any]:
        aid = _identity(assignment_id, "assignment identity")
        try:
            db = sqlite3.connect(self.mission_db.as_uri() + "?mode=ro", uri=True, timeout=2)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            assignment = db.execute(
                "SELECT * FROM mission_execution_assignments WHERE assignment_id=?", (aid,)
            ).fetchone()
            _require(assignment is not None, "canonical assignment unavailable")
            assignment = dict(assignment)
            mission_id = assignment["mission_id"]
            driver = db.execute(
                "SELECT * FROM mission_execution_drivers WHERE mission_id=?", (mission_id,)
            ).fetchone()
            control = db.execute(
                "SELECT * FROM mission_operator_control WHERE mission_id=?", (mission_id,)
            ).fetchone()
            spec = db.execute(
                "SELECT * FROM mission_process_specs WHERE mission_id=?", (mission_id,)
            ).fetchone()
            mission = db.execute(
                "SELECT * FROM missions WHERE mission_id=?", (mission_id,)
            ).fetchone()
            _require(all(row is not None for row in (driver, control, spec, mission)),
                     "canonical mission binding unavailable")
            result = {
                "assignment": assignment,
                "input": assignment_input(assignment),
                "driver": dict(driver),
                "control": dict(control),
                "spec": dict(spec),
                "mission": dict(mission),
            }
            if require_held:
                _require(assignment.get("state") == "HELD", "materialization assignment not held")
            return result
        except sqlite3.Error as exc:
            raise CooperativeRuntimeRootError("canonical Mission Control snapshot unavailable") from exc
        finally:
            try:
                db.close()
            except Exception:
                pass

    @staticmethod
    def _coordinates(snapshot: Mapping[str, Any]) -> dict[str, Any]:
        a = snapshot["assignment"]; d = snapshot["driver"]; c = snapshot["control"]; s = snapshot["spec"]
        return {
            "assignment_id": a["assignment_id"],
            "mission_id": a["mission_id"],
            "phase_id": a["phase_id"],
            "driver_phase_id": d["current_phase"],
            "worker_id": a["material_drone_id"],
            "generation": int(a["lease_generation"]),
            "control_epoch": int(a["control_epoch"]),
            "context_revision": int(a["context_revision"]),
            "plan_revision": int(a["plan_revision"]),
            "input_digest": a["input_digest"],
            "lpcl_digest": s["lpcl_digest"],
        }

    def _presented(self, presented: Mapping[str, Any], *, kind: str) -> dict[str, Any]:
        _require(isinstance(presented, Mapping) and set(presented) == {"assignment", "input"},
                 "materializer presented schema")
        row = presented["assignment"]
        inp = presented["input"]
        _require(isinstance(row, Mapping) and isinstance(inp, Mapping), "materializer presented types")
        aid = _identity(row.get("assignment_id"), "presented assignment identity")
        snap = self._snapshot(aid, require_held=True)
        canonical = snap["assignment"]
        for key in (
            "assignment_id", "mission_id", "material_drone_id", "logical_drone_id",
            "phase_id", "lease_generation", "control_epoch", "context_revision",
            "plan_revision", "input_digest", "state",
        ):
            _require(row.get(key) == canonical.get(key), "presented assignment substitution:" + key)
        _require(dict(inp) == snap["input"], "presented input substitution")
        _require(snap["input"].get("kind") == kind, "materializer assignment kind")
        return snap

    def _validate_context(
        self,
        assignment_id: str,
        snapshot: Mapping[str, Any],
        *,
        context_source: Callable[[str], CooperativeRuntimeContext] | None = None,
    ) -> CooperativeRuntimeContext:
        source = self.context_source if context_source is None else context_source
        _require(callable(source), "context source unavailable")
        ctx = source(assignment_id)
        _require(type(ctx) is CooperativeRuntimeContext, "canonical CooperativeRuntimeContext unavailable")
        ctx.validate()
        a = snapshot["assignment"]
        b = ctx.execution
        _require(
            (b.assignment_id, b.worker_id, b.input_digest, b.request.mission_id, b.request.generation)
            == (a["assignment_id"], a["material_drone_id"], a["input_digest"], a["mission_id"], a["lease_generation"]),
            "context/assignment association mismatch",
        )
        _require(Path(b.artifact_root) == self.artifact_root, "artifact root substitution")
        self._assert_source_binding(
            self.upstream_admission_source, self.upstream_admission_trust.binding(),
            ("resolve", "is_current"), "upstream admission source",
        )
        canonical = self.upstream_admission_source.resolve(b.admission.admission_digest)
        _require(type(canonical) is RuntimeAdmission and canonical.validate() == b.admission,
                 "upstream admission substitution")
        _require(self.upstream_admission_source.is_current(b.admission.admission_digest) is True,
                 "upstream RuntimeAdmission stale")
        provisioning = self.provisioning_binding_source(assignment_id)
        _require(type(provisioning) is ProvisioningBinding and provisioning.validate() == ctx.provisioning,
                 "provisioning binding substitution")
        identity = self.runtime_identity_source(b.identity.runtime_instance_id)
        _require(type(identity) is RuntimeIdentityBinding and identity.validate() == b.identity,
                 "runtime identity substitution")
        dispatch = self.dispatch_source.current_dispatch(a["mission_id"])
        _require(type(dispatch) is type(ctx.dispatch) and dispatch.validate().digest() == ctx.dispatch.digest(),
                 "dispatch substitution")

        self._assert_source_binding(
            self.currentness_source, self.currentness_trust.binding(),
            ("resolve_authority", "current_policy_binding", "current_observability_state"),
            "currentness source",
        )
        authority = self.currentness_source.resolve_authority(b.admission.admission_digest)
        _require(type(authority) is LiveAdmittedAuthority, "current authority type")
        authority.validate()
        _require(authority.digest() == b.admission.live_authority_digest
                 and authority.lineage_digest == b.admission.authority_lineage_digest,
                 "current authority substitution")
        current = self.authority_admission.revalidate(authority, now=_zoned(self.now_fn()))
        _require(current.digest() == b.admission.live_authority_digest, "authority changed before materialization")
        _require(self.currentness_source.current_policy_binding(b.admission.policy_binding)
                 == b.admission.policy_binding, "policy changed before materialization")
        _require(self.currentness_source.current_observability_state(
            b.admission.runtime_identity_digest, b.admission.requested_effect_digest,
        ) == b.admission.observability_state, "observability changed before materialization")
        return ctx

    def _reobserve_worker_sources(self, assignment_id: str, ctx: CooperativeRuntimeContext) -> None:
        """Recheck sources not owned by the durable local copy before worker effect."""
        b = ctx.execution
        self._assert_source_binding(
            self.upstream_admission_source, self.upstream_admission_trust.binding(),
            ("resolve", "is_current"), "upstream admission source",
        )
        canonical = self.upstream_admission_source.resolve(b.admission.admission_digest)
        _require(type(canonical) is RuntimeAdmission and canonical.validate() == b.admission,
                 "upstream admission changed before worker effect")
        _require(self.upstream_admission_source.is_current(b.admission.admission_digest) is True,
                 "upstream RuntimeAdmission stale before worker effect")
        provisioning = self.provisioning_binding_source(assignment_id)
        _require(type(provisioning) is ProvisioningBinding
                 and provisioning.validate() == ctx.provisioning,
                 "provisioning changed before worker effect")
        identity = self.runtime_identity_source(b.identity.runtime_instance_id)
        _require(type(identity) is RuntimeIdentityBinding and identity.validate() == b.identity,
                 "runtime identity changed before worker effect")
        dispatch = self.dispatch_source.current_dispatch(b.request.mission_id)
        _require(type(dispatch) is type(ctx.dispatch) and dispatch.validate().digest() == ctx.dispatch.digest(),
                 "dispatch changed before worker effect")

    def _admission_provenance(self, ctx: CooperativeRuntimeContext) -> str:
        payload = {
            "upstream_source": self.upstream_admission_trust.binding(),
            "admission_digest": ctx.execution.admission.admission_digest,
            "provisioning_digest": ctx.provisioning.digest(),
            "runtime_identity_digest": ctx.execution.identity.digest(),
            "dispatch_digest": ctx.dispatch.digest(),
        }
        return sha256(PROVENANCE_DOMAIN + _canonical(payload)).hexdigest()

    def write_materializer(self, presented: Mapping[str, Any]) -> Mapping[str, Any]:
        snap = self._presented(presented, kind=WRITE_KIND)
        aid = snap["assignment"]["assignment_id"]
        ctx = self._validate_context(aid, snap)
        self.admission_source.publish(
            ctx.execution.admission,
            provenance_digest=self._admission_provenance(ctx),
            published_at=_zoned(self.now_fn()),
        )
        binding = self.transfer_binding_source(aid, "CONTEXT")
        materialized = materialize_context_reference(
            context=ctx,
            coordinates=self._coordinates(snap),
            expected_binding=binding,
            private_parent=self.context_parent,
        )
        evidence = self.store.record_context(
            materialized,
            worker_id=snap["assignment"]["material_drone_id"],
            admission_digest=ctx.execution.admission.admission_digest,
            recorded_at=_zoned(self.now_fn()),
        )
        return {
            "materialization_kind": "RUNTIME_CONTEXT",
            "provider_id": WRITE_PROVIDER_ID,
            "evidence_digest": evidence,
            "authority_effect": "NONE",
        }

    def verify_materializer(self, presented: Mapping[str, Any]) -> Mapping[str, Any]:
        snap = self._presented(presented, kind=VERIFY_KIND)
        aid = snap["assignment"]["assignment_id"]
        payload = snap["input"]
        binding = self.transfer_binding_source(aid, "VERIFY")
        materialized = materialize_verifier_view(
            artifact_root=self.artifact_root,
            consumer_assignment_id=aid,
            verify_payload=payload,
            expected_binding=binding,
            private_parent=self.verifier_parent,
        )
        evidence = self.store.record_verifier(
            materialized,
            verifier_worker_id=snap["assignment"]["material_drone_id"],
            recorded_at=_zoned(self.now_fn()),
        )
        return {
            "materialization_kind": "VERIFIER_TRANSFER",
            "provider_id": VERIFY_PROVIDER_ID,
            "evidence_digest": evidence,
            "authority_effect": "NONE",
        }

    def materialization_provider(self) -> CooperativeMaterializationProvider:
        return CooperativeMaterializationProvider(self.write_materializer, self.verify_materializer).validate()

    def writer_for_assignment(self, assignment_id: str) -> CooperativeRuntimeWriterProvider:
        aid = _identity(assignment_id, "writer assignment identity")
        existing = self._writers.get(aid)
        if existing is not None:
            return existing
        materialization, worker, admission_digest = self.store.resolve_context(aid)
        _require(materialization.artifact_root == self.artifact_root, "materialized artifact root substitution")
        _require(self.admission_source.is_current(admission_digest) is True, "durable RuntimeAdmission unavailable")
        resolver = PinnedCooperativeContextResolver(
            mission_db=self.mission_db,
            context_directory=materialization.workspace,
            pins=(materialization.pin,),
            admission_source=self.admission_source,
            admission_trust=self.durable_admission_trust,
            dispatch_source=self.dispatch_source,
            runtime_identity_source=self.runtime_identity_source,
            now_fn=self.now_fn,
        )

        def guarded_context(requested: str) -> CooperativeRuntimeContext:
            ctx = resolver(requested)
            _require(ctx.execution.worker_id == worker, "materialized worker substitution")
            # Re-observe the original admission source as well as provisioning,
            # identity and dispatch. The durable copy is evidence transport, not
            # a way to extend an upstream admission's currentness.
            self._reobserve_worker_sources(requested, ctx)
            return ctx

        provider = CooperativeRuntimeWriterProvider(
            context_source=guarded_context,
            admission_source=self.admission_source,
            admission_trust=self.durable_admission_trust,
            authority_admission=self.authority_admission,
            currentness_source=self.currentness_source,
            currentness_trust=self.currentness_trust,
            dispatch_source=self.dispatch_source,
            admission_guard=self.admission_guard,
            sandbox_guard=self.sandbox_guard,
            budget_source=lambda policy: SQLiteSandboxBudgetLedger(policy, self.runtime_state_db),
            now_fn=self.now_fn,
        )
        self._writers[aid] = provider
        return provider

    def verifier_workspace(self, consumer_assignment_id: str) -> Path:
        materialization, _ = self.store.resolve_verifier(consumer_assignment_id)
        return materialization.workspace

    def qualify_released_write_assignment(
        self,
        assignment_id: str,
        *,
        material_worker_id: str,
    ) -> dict[str, Any]:
        """Qualify one released assignment without claiming or executing it.

        READY must already have been produced by the canonical HELD->READY fence.
        Qualification imports only already-issued evidence into this worker's private
        root, rebuilds the writer factory, and performs independent readback.
        """
        aid = _identity(assignment_id, "qualification assignment identity")
        worker = _identity(material_worker_id, "qualification worker identity")
        snap = self._snapshot(aid, require_held=False)
        assignment = snap["assignment"]
        _require(assignment.get("state") == "READY", "qualification assignment not READY")
        _require(assignment.get("material_drone_id") == worker, "qualification worker substitution")
        _require(snap["input"].get("kind") == WRITE_KIND, "qualification assignment kind")

        db = None
        try:
            db = sqlite3.connect(self.mission_db.as_uri() + "?mode=ro", uri=True, timeout=2)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            release_row = db.execute(
                "SELECT mission_id,evidence_digest,evidence_json,released_at "
                "FROM mission_assignment_release_evidence WHERE assignment_id=?",
                (aid,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise CooperativeRuntimeRootError("assignment release evidence unavailable") from exc
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

        _require(release_row is not None, "assignment release evidence unavailable")
        release = _strict_json(release_row["evidence_json"], "assignment release evidence")
        _require(set(release) == _RELEASE_EVIDENCE_FIELDS, "assignment release evidence schema")
        _require(
            release.get("schema") == ASSIGNMENT_RELEASE_EVIDENCE_SCHEMA,
            "assignment release evidence schema",
        )
        _require(release_row["mission_id"] == assignment["mission_id"], "release mission substitution")
        _require(
            sha256(_canonical(release)).hexdigest() == release_row["evidence_digest"],
            "assignment release evidence digest mismatch",
        )
        control_plane_digest = _digest(
            release.get("evidence_digest"), "control-plane evidence digest"
        )
        expected_release = (
            aid,
            assignment["mission_id"],
            worker,
            int(assignment["lease_generation"]),
            int(assignment["control_epoch"]),
            int(assignment["context_revision"]),
            int(assignment["plan_revision"]),
            snap["input"].get("capability"),
            "RUNTIME_CONTEXT",
            WRITE_PROVIDER_ID,
            "NONE",
        )
        actual_release = (
            release.get("assignment_id"),
            release.get("mission_id"),
            release.get("material_drone_id"),
            release.get("lease_generation"),
            release.get("control_epoch"),
            release.get("context_revision"),
            release.get("plan_revision"),
            release.get("capability"),
            release.get("materialization_kind"),
            release.get("provider_id"),
            release.get("authority_effect"),
        )
        _require(actual_release == expected_release, "assignment release evidence substitution")

        ctx = self._validate_context(
            aid,
            snap,
            context_source=self.qualification_context_source,
        )
        admission_digest = ctx.execution.admission.admission_digest
        self.admission_source.publish(
            ctx.execution.admission,
            provenance_digest=self._admission_provenance(ctx),
            published_at=_zoned(self.now_fn()),
        )
        binding = self.transfer_binding_source(aid, "CONTEXT")
        materialized = materialize_context_reference(
            context=ctx,
            coordinates=self._coordinates(snap),
            expected_binding=binding,
            private_parent=self.context_parent,
        )
        descriptor_digest = self.store.record_context(
            materialized,
            worker_id=worker,
            admission_digest=admission_digest,
            recorded_at=_zoned(self.now_fn()),
        )

        observed, observed_worker, observed_admission = self.store.resolve_context(aid)
        _require(observed_worker == worker, "qualification private worker readback mismatch")
        _require(observed_admission == admission_digest, "qualification admission readback mismatch")
        _require(
            observed.pin == materialized.pin
            and observed.transfer_sha256 == materialized.transfer_sha256
            and observed.workspace.parent == self.context_parent,
            "qualification private context readback mismatch",
        )
        copied_admission = self.admission_source.resolve(admission_digest)
        _require(
            type(copied_admission) is RuntimeAdmission
            and copied_admission.validate() == ctx.execution.admission
            and self.admission_source.is_current(admission_digest) is True,
            "qualification durable admission readback mismatch",
        )
        writer = self.writer_for_assignment(aid)
        _require(type(writer) is CooperativeRuntimeWriterProvider, "qualification writer factory")
        marker = self.worker_status_marker()
        _require(marker.get("authority_effect") == "NONE", "qualification provider authority")

        evidence = {
            "schema": "lion.cooperative-worker-qualification/v1",
            "assignment_id": aid,
            "mission_id": assignment["mission_id"],
            "worker_id": worker,
            "lease_generation": int(assignment["lease_generation"]),
            "release_evidence_digest": release_row["evidence_digest"],
            "control_plane_evidence_digest": control_plane_digest,
            "private_context_pin_sha256": materialized.pin.sha256,
            "private_transfer_sha256": materialized.transfer_sha256,
            "private_materialization_digest": descriptor_digest,
            "runtime_admission_digest": admission_digest,
            "provider_id": marker["provider_id"],
            "context_resolver": marker["context_resolver"],
            "execution_engine": marker["execution_engine"],
            "writer_factory_built": True,
            "execution_performed": False,
            "authority_effect": "NONE",
        }
        return {
            **evidence,
            "qualification_digest": sha256(
                QUALIFICATION_DOMAIN + _canonical(evidence)
            ).hexdigest(),
        }

    def worker_status_marker(self) -> dict[str, Any]:
        """Provider factory readiness only; never an authority grant."""
        self.store._check()
        _require(not self.runtime_state_db.is_symlink()
                 and _state_identity(self.runtime_state_db) == self._runtime_state_identity,
                 "runtime state DB identity drift")
        # Re-observe all constructor-bound sources before advertising readiness.
        self._assert_source_binding(
            self.upstream_admission_source, self.upstream_admission_trust.binding(),
            ("resolve", "is_current"), "upstream admission source",
        )
        self._assert_source_binding(
            self.currentness_source, self.currentness_trust.binding(),
            ("resolve_authority", "current_policy_binding", "current_observability_state"),
            "currentness source",
        )
        _require(callable(getattr(self.dispatch_source, "current_dispatch", None)), "dispatch source unavailable")
        return provider_status_marker()

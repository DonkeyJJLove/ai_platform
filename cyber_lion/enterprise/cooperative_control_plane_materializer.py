"""Control-plane sequence: carrier -> bounded export -> readback -> HELD release.

This module is a non-authorizing materializer callback for the existing cooperative
Mission Control stepper. It never calls release_held_assignment itself. The caller
(cooperative_production._materialize_and_release) performs the canonical HELD->READY
transition only after this callback returns a complete evidence digest.

The sequence:
1. re-reads the canonical HELD assignment and exact Mission Control coordinates;
2. serializes an already-existing CooperativeRuntimeContext into a pending carrier;
3. derives an independent CooperativeContextPin over the final carrier name;
4. runs the R6.15 exporter against independent canonical owners;
5. atomically publishes the carrier and re-reads every R6.14 provider evidence surface;
6. returns only non-authorizing materialization evidence.

Provider evidence or carrier bytes never participate in their own admission decision.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import stat
from typing import Any, Mapping

from cyber_lion.enterprise.cooperative_context_resolver import (
    CooperativeContextPin,
    context_reference_bytes,
)
from cyber_lion.enterprise.cooperative_runtime_composition import CooperativeRuntimeContext
from cyber_lion.enterprise.cooperative_runtime_evidence_exporter import (
    CooperativeRuntimeEvidenceExporter,
)
from cyber_lion.enterprise.cooperative_runtime_evidence_sources import (
    SQLiteContextPinSource,
    SQLiteEffectTimeCurrentnessSource,
    SQLiteEvidenceRuntimeAdmissionSource,
    SQLiteFleetDispatchSource,
    SQLiteProvisioningBindingSource,
    SQLiteRuntimeIdentitySource,
    SQLiteTransferBindingSource,
)
from cyber_lion.mission_control import operator_control
from cyber_lion.mission_control.cooperative_production import (
    WRITE_MATERIALIZATION_KIND,
    WRITE_PROVIDER_ID,
)
from tools.lion_cooperative_worker_adapter import assignment_input

SCHEMA = "lion.cooperative-control-plane-materialization/v1"
EVIDENCE_DOMAIN = b"LION/COOPERATIVE-CONTROL-PLANE-MATERIALIZATION/1\0"
_CONTEXT_NAME_DOMAIN = b"LION/COOPERATIVE-CONTEXT-CARRIER-NAME/1\0"


class CooperativeControlPlaneMaterializerError(RuntimeError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CooperativeControlPlaneMaterializerError(reason)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _direct_file(value: str | Path, label: str) -> Path:
    path = Path(value)
    _require(path.is_absolute() and path.is_file() and not path.is_symlink(), label)
    resolved = path.resolve(strict=True)
    _require(path == resolved, label + " symlink indirection")
    st = resolved.stat()
    _require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, label + " private regular file")
    return resolved


def _direct_dir(value: str | Path, label: str) -> Path:
    path = Path(value)
    _require(path.is_absolute() and path.is_dir() and not path.is_symlink(), label)
    resolved = path.resolve(strict=True)
    _require(path == resolved, label + " symlink indirection")
    st = resolved.stat()
    _require(stat.S_ISDIR(st.st_mode), label + " directory type")
    return resolved


def _identity(path: Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_dev, st.st_ino


class CooperativeControlPlaneMaterializer:
    """Exact write-materializer callback for the existing Mission Control release fence."""

    def __init__(
        self,
        *,
        mission_db: str | Path,
        provider_context_root: str | Path,
        exporter_template: CooperativeRuntimeEvidenceExporter,
        ttl_seconds: int = 10,
    ):
        self.mission_db = _direct_file(mission_db, "Mission Control DB")
        self.context_root = _direct_dir(provider_context_root, "provider context root")
        _require(
            type(exporter_template) is CooperativeRuntimeEvidenceExporter,
            "exact cooperative evidence exporter required",
        )
        _require(
            type(ttl_seconds) is int
            and 1 <= ttl_seconds <= exporter_template.max_ttl_seconds,
            "materialization TTL bound",
        )
        self.exporter = exporter_template
        self.ttl_seconds = ttl_seconds
        self._db_identity = _identity(self.mission_db)
        self._context_root_identity = _identity(self.context_root)

    def _check_roots(self) -> None:
        _require(
            not self.mission_db.is_symlink() and _identity(self.mission_db) == self._db_identity,
            "Mission Control DB identity drift",
        )
        _require(
            not self.context_root.is_symlink()
            and _identity(self.context_root) == self._context_root_identity,
            "provider context root identity drift",
        )

    def _snapshot(self, assignment_id: str) -> dict[str, Any]:
        self._check_roots()
        try:
            db = sqlite3.connect(self.mission_db.as_uri() + "?mode=ro", uri=True, timeout=2)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            assignment = db.execute(
                "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
                (assignment_id,),
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
            _require(
                all(row is not None for row in (driver, control, spec, mission)),
                "canonical mission binding unavailable",
            )
            driver, control, spec, mission = map(dict, (driver, control, spec, mission))
            inp = assignment_input(assignment)
            capability = inp.get("capability")
            _require(type(capability) is str and bool(capability), "assignment capability missing")
            _require(
                operator_control.assignment_allowed(
                    db, mission_id, assignment["dispatch_authority"], assignment["control_epoch"]
                ),
                "operator control fence",
            )
            _require(
                not operator_control.is_capability_revoked(db, mission_id, capability),
                "capability revoked",
            )
            _require(
                driver.get("state") in {"ACTIVE", "WAITING", "BLOCKED"},
                "mission driver not executable",
            )
            _require(
                mission.get("state") in {"RUNNING", "WAITING", "BLOCKED"},
                "mission not executing",
            )
            lpcl = spec.get("lpcl_text")
            _require(type(lpcl) is str and bool(lpcl), "LPCL bytes unavailable")
            _require(
                sha256(lpcl.encode("utf-8")).hexdigest()
                == spec.get("lpcl_digest")
                == mission.get("spec_digest"),
                "LPCL byte binding mismatch",
            )
            return {
                "assignment": assignment,
                "input": inp,
                "driver": driver,
                "control": control,
                "spec": spec,
                "mission": mission,
            }
        except sqlite3.Error as exc:
            raise CooperativeControlPlaneMaterializerError(
                "canonical Mission Control snapshot unavailable"
            ) from exc
        finally:
            try:
                db.close()
            except Exception:
                pass

    @staticmethod
    def _coordinates(snapshot: Mapping[str, Any]) -> dict[str, Any]:
        a = snapshot["assignment"]
        driver = snapshot["driver"]
        control = snapshot["control"]
        spec = snapshot["spec"]
        _require(a["state"] == "HELD", "assignment not HELD")
        _require(
            int(driver["generation"]) == int(a["lease_generation"]),
            "stale driver generation",
        )
        _require(
            all(
                int(control[name]) == int(a[name])
                for name in ("control_epoch", "context_revision", "plan_revision")
            ),
            "stale control/context/plan revision",
        )
        _require(
            spec["authority_state"] == "EXPLICIT_USER_ACTIVATION",
            "LPCL not explicitly activated",
        )
        return {
            "assignment_id": a["assignment_id"],
            "mission_id": a["mission_id"],
            "phase_id": a["phase_id"],
            "driver_phase_id": driver["current_phase"],
            "worker_id": a["material_drone_id"],
            "generation": int(a["lease_generation"]),
            "control_epoch": int(a["control_epoch"]),
            "context_revision": int(a["context_revision"]),
            "plan_revision": int(a["plan_revision"]),
            "input_digest": a["input_digest"],
            "lpcl_digest": spec["lpcl_digest"],
        }

    @staticmethod
    def _validate_presented(
        presented: Mapping[str, Any], snapshot: Mapping[str, Any]
    ) -> str:
        _require(
            isinstance(presented, Mapping) and set(presented) == {"assignment", "input"},
            "materializer presented schema",
        )
        row = presented["assignment"]
        inp = presented["input"]
        _require(isinstance(row, Mapping) and isinstance(inp, Mapping), "materializer presented types")
        canonical = snapshot["assignment"]
        for key in (
            "assignment_id",
            "mission_id",
            "material_drone_id",
            "logical_drone_id",
            "phase_id",
            "lease_generation",
            "control_epoch",
            "context_revision",
            "plan_revision",
            "input_digest",
            "state",
        ):
            _require(row.get(key) == canonical.get(key), "presented assignment substitution:" + key)
        _require(dict(inp) == snapshot["input"], "presented input substitution")
        assignment_id = canonical["assignment_id"]
        _require(type(assignment_id) is str and bool(assignment_id), "assignment identity")
        return assignment_id

    @staticmethod
    def _filename(assignment_id: str) -> str:
        digest = sha256(_CONTEXT_NAME_DOMAIN + assignment_id.encode("utf-8")).hexdigest()
        return "context-" + digest + ".json"

    def _exporter_for_pin(self, pin: CooperativeContextPin) -> CooperativeRuntimeEvidenceExporter:
        base = self.exporter
        return CooperativeRuntimeEvidenceExporter(
            publisher=base.publisher,
            context_source=base.context_source,
            admission_source=base.admission_source,
            admission_trust=base.admission_trust,
            authority_admission=base.authority_admission,
            currentness_source=base.currentness_source,
            currentness_trust=base.currentness_trust,
            dispatch_source=base.dispatch_source,
            runtime_identity_source=base.runtime_identity_source,
            provisioning_binding_source=base.provisioning_binding_source,
            context_pin_source=lambda assignment_id: (
                pin
                if assignment_id == pin.assignment_id
                else (_ for _ in ()).throw(
                    CooperativeControlPlaneMaterializerError("context pin assignment substitution")
                )
            ),
            transfer_binding_source=base.transfer_binding_source,
            now_fn=base.now_fn,
            max_ttl_seconds=base.max_ttl_seconds,
        )

    def _readback(self, receipt, pin: CooperativeContextPin, context: CooperativeRuntimeContext) -> None:
        clock = self.exporter.now_fn
        db = self.exporter.publisher.path
        admission = SQLiteEvidenceRuntimeAdmissionSource(
            db, self.exporter.admission_trust, now_fn=clock
        ).resolve(receipt.admission_digest)
        observed_pin = SQLiteContextPinSource(db, now_fn=clock)(receipt.assignment_id)
        dispatch = SQLiteFleetDispatchSource(db, now_fn=clock).current_dispatch(receipt.mission_id)
        provisioning = SQLiteProvisioningBindingSource(db, now_fn=clock)(receipt.assignment_id)
        identity = SQLiteRuntimeIdentitySource(db, now_fn=clock)(
            context.execution.identity.runtime_instance_id
        )
        currentness = SQLiteEffectTimeCurrentnessSource(
            db, self.exporter.currentness_trust, now_fn=clock
        )
        authority = currentness.resolve_authority(receipt.admission_digest)
        policy = currentness.current_policy_binding(context.execution.admission.policy_binding)
        observability = currentness.current_observability_state(
            context.execution.admission.runtime_identity_digest,
            context.execution.admission.requested_effect_digest,
        )
        transfer = SQLiteTransferBindingSource(db, now_fn=clock)(
            receipt.assignment_id, "CONTEXT"
        )
        _require(admission == context.execution.admission, "provider admission readback mismatch")
        _require(observed_pin == pin, "provider context pin readback mismatch")
        _require(dispatch == context.dispatch, "provider dispatch readback mismatch")
        _require(provisioning == context.provisioning, "provider provisioning readback mismatch")
        _require(identity == context.execution.identity, "provider runtime identity readback mismatch")
        _require(
            authority.digest() == context.execution.admission.live_authority_digest,
            "provider authority readback mismatch",
        )
        _require(
            policy == context.execution.admission.policy_binding
            and observability == context.execution.admission.observability_state,
            "provider currentness readback mismatch",
        )
        _require(
            transfer["assignment_id"] == receipt.assignment_id
            and transfer["mission_id"] == receipt.mission_id
            and int(transfer["generation"]) == context.execution.request.generation,
            "provider transfer readback mismatch",
        )

    def __call__(self, presented: Mapping[str, Any]) -> Mapping[str, Any]:
        assignment_id = presented.get("assignment", {}).get("assignment_id") if isinstance(presented, Mapping) else None
        _require(type(assignment_id) is str and bool(assignment_id), "materializer assignment identity")
        snapshot = self._snapshot(assignment_id)
        assignment_id = self._validate_presented(presented, snapshot)
        coordinates = self._coordinates(snapshot)

        context = self.exporter.context_source(assignment_id)
        _require(type(context) is CooperativeRuntimeContext, "exact CooperativeRuntimeContext required")
        context.validate()
        execution = context.execution
        _require(
            (
                execution.assignment_id,
                execution.worker_id,
                execution.input_digest,
                execution.request.mission_id,
                execution.request.generation,
            )
            == (
                assignment_id,
                snapshot["assignment"]["material_drone_id"],
                snapshot["assignment"]["input_digest"],
                snapshot["assignment"]["mission_id"],
                snapshot["assignment"]["lease_generation"],
            ),
            "runtime context/assignment substitution",
        )

        raw = context_reference_bytes(context, coordinates)
        filename = self._filename(assignment_id)
        final_path = self.context_root / filename
        pending_path = self.context_root / (filename + ".pending")
        _require(not final_path.exists() and not final_path.is_symlink(), "context carrier already exists")
        _require(not pending_path.exists() and not pending_path.is_symlink(), "pending context carrier exists")

        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(pending_path, flags, 0o640)
        try:
            with os.fdopen(fd, "wb", closefd=True) as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                pending_path.unlink()
            except OSError:
                pass
            raise

        pin = CooperativeContextPin(
            assignment_id, filename, sha256(raw).hexdigest()
        ).validate()
        exporter = self._exporter_for_pin(pin)
        try:
            receipt = exporter.export_write_assignment(
                assignment_id, ttl_seconds=self.ttl_seconds
            )
        except Exception:
            try:
                pending_path.unlink()
            except OSError:
                pass
            raise

        # Provider DB is complete while assignment is still HELD. Publish the exact
        # carrier only after the bounded export succeeds.
        _require(not final_path.exists(), "context carrier publication race")
        os.replace(pending_path, final_path)
        st = final_path.stat()
        _require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, "context carrier type")
        observed = final_path.read_bytes()
        _require(sha256(observed).hexdigest() == pin.sha256, "context carrier readback mismatch")

        self._readback(receipt, pin, context)
        evidence = {
            "schema": SCHEMA,
            "assignment_id": assignment_id,
            "mission_id": receipt.mission_id,
            "worker_id": receipt.worker_id,
            "carrier_filename": filename,
            "carrier_sha256": pin.sha256,
            "export_provenance_digest": receipt.provenance_digest,
            "export_expires_at": receipt.expires_at,
            "authority_effect": "NONE",
            "execution_performed": False,
        }
        evidence_digest = sha256(EVIDENCE_DOMAIN + _canonical(evidence)).hexdigest()
        return {
            "materialization_kind": WRITE_MATERIALIZATION_KIND,
            "provider_id": WRITE_PROVIDER_ID,
            "evidence_digest": evidence_digest,
            "authority_effect": "NONE",
        }

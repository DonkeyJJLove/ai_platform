"""R11: construct original R6.21/R6.16/R6.17 from independent CURRENT sources.

This module neither issues authority nor creates preparation evidence. It is
not the externally SHA-pinned build_current_owners() implementation. The
operator-installed external module must supply exact independently admitted
source objects and call assemble_original_owners(...) after the original
production deployment gate. Constructor side effects are restricted to
private SQLite journals and evidence-schema initialization. Do NOT call this
against the live Mission Control DB during preflight.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import os
import stat
from typing import Any, Callable, Mapping

from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.cooperative_context_resolver import PinnedCooperativeContextResolver
from cyber_lion.enterprise.cooperative_runtime_preparation_provider import (
    CooperativeRuntimePreparationProvider,
)
from cyber_lion.enterprise.cooperative_runtime_preparer import (
    CooperativeRuntimePreparationEvidence,
)
from cyber_lion.enterprise.cooperative_control_plane_materializer import (
    CooperativeControlPlaneMaterializer,
)
from cyber_lion.enterprise.cooperative_runtime_evidence_exporter import (
    CooperativeRuntimeEvidenceExporter,
)
from cyber_lion.enterprise.cooperative_runtime_evidence_sources import (
    SQLiteCooperativeRuntimeEvidencePublisher,
    SQLiteEvidenceRuntimeAdmissionSource,
    SQLiteContextPinSource,
    SQLiteFleetDispatchSource,
    SQLiteProvisioningBindingSource,
    SQLiteRuntimeIdentitySource,
    SQLiteEffectTimeCurrentnessSource,
    SQLiteTransferBindingSource,
)
from cyber_lion.enterprise.cooperative_runtime_root import (
    CooperativeRuntimeCompositionRoot,
)
from cyber_lion.enterprise.runtime_enforcement import RuntimeAdmissionEngine
from cyber_lion.enterprise.r11_runtime_admission_replay import SQLiteR11RuntimeAdmissionReplayGuard
from cyber_lion.enterprise.runtime_execution import SQLiteRuntimeAdmissionSource
from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.mission_control.cooperative_preactivation_bootstrap import (
    CooperativeSourceBoundPreactivation,
)

SCHEMA = "lion.r11.current-canonical-owner-construction/v1"
WORKER = "MD001"


class R11CurrentOwnerWiringError(RuntimeError):
    pass


def _need(condition: bool, label: str) -> None:
    if not condition:
        raise R11CurrentOwnerWiringError(label)


def _direct_dir(path: Path, label: str) -> Path:
    p = Path(path)
    _need(p.is_absolute() and not p.is_symlink(), label + ": indirect path")
    try:
        s = p.lstat()
    except OSError as exc:
        raise R11CurrentOwnerWiringError(label + ": unavailable") from exc
    _need(stat.S_ISDIR(s.st_mode), label + ": not directory")
    _need(p.resolve(strict=True) == p, label + ": indirect ancestor")
    return p


def _direct_file(path: Path, label: str) -> Path:
    p = Path(path)
    _need(p.is_absolute() and not p.is_symlink(), label + ": indirect path")
    try:
        s = p.lstat()
    except OSError as exc:
        raise R11CurrentOwnerWiringError(label + ": unavailable") from exc
    _need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, label + ": not private file")
    _need(p.resolve(strict=True) == p, label + ": indirect ancestor")
    return p


def _planned_sqlite(path: Path, label: str) -> Path:
    p = Path(path)
    _need(p.is_absolute() and not p.is_symlink(), label + ": indirect path")
    _direct_dir(p.parent, label + " parent")
    if p.exists():
        _direct_file(p, label)
    return p


def _inode(path: Path) -> tuple[int, int]:
    s = path.stat()
    return s.st_dev, s.st_ino


def _never_pin_from_worker(_assignment_id: str):
    # R6.16 calculates the exact pin during its own materialization step.
    raise R11CurrentOwnerWiringError("context pin unavailable before R6.16 materialization")


@dataclass(frozen=True)
class CurrentOwnerSources:
    """Exact upstream service owners and private roots — never a receipt/config grant."""
    mission_db: Path
    artifact_root: Path
    carrier_root: Path
    provider_evidence_db: Path
    worker_context_parent: Path
    worker_verifier_parent: Path
    worker_materialization_db: Path
    worker_runtime_state_db: Path
    preparation_evidence_source: Callable[[str], CooperativeRuntimePreparationEvidence]
    admission_engine: RuntimeAdmissionEngine
    admission_source: SQLiteRuntimeAdmissionSource
    authority_admission: LiveAuthorityAdmission
    currentness_source: Any
    currentness_trust: CurrentnessSourceTrustBinding
    dispatch_source: Any
    runtime_identity_source: Callable[..., Any]
    provisioning_binding_source: Callable[..., Any]
    transfer_binding_source: Callable[..., Mapping[str, Any]]
    worker_durable_admission_trust: RuntimeAdmissionSourceTrustBinding
    now_fn: Callable[[], datetime]
    worker_id: str = WORKER

    def validate(self) -> "CurrentOwnerSources":
        _need(type(self) is CurrentOwnerSources, "exact source bundle required")
        _need(type(self.worker_id) is str and self.worker_id == WORKER, "only MD001 supported")
        _need(type(self.admission_source) is SQLiteRuntimeAdmissionSource,
              "existing R6.21 SQLiteRuntimeAdmissionSource required")
        db = _direct_file(self.mission_db, "canonical Mission Control DB")
        runtime = _direct_file(self.admission_source.path, "R6.21 original runtime state")
        _need(_inode(db) != _inode(runtime), "canonical and runtime SQLite alias")
        artifact = _direct_dir(self.artifact_root, "artifact root")
        carrier = _direct_dir(self.carrier_root, "R6.16 carrier root")
        context = _direct_dir(self.worker_context_parent, "R6.17 context root")
        verifier = _direct_dir(self.worker_verifier_parent, "R6.17 verifier root")
        state1 = _planned_sqlite(self.worker_materialization_db, "worker materialization SQLite")
        state2 = _planned_sqlite(self.worker_runtime_state_db, "worker state SQLite")
        provider = _planned_sqlite(self.provider_evidence_db, "R6.16 provider evidence SQLite")
        _need(len({_inode(artifact), _inode(carrier), _inode(context),
                   _inode(verifier), _inode(state1.parent)}) == 5,
              "material and private root separation required")
        _need(_inode(carrier) != _inode(context),
              "worker private context must not alias R6.16 carrier")
        _need(len({str(state1), str(state2), str(provider), str(db), str(runtime)}) == 5,
              "SQLite destinations must not alias")
        if provider.exists():
            _need(_inode(provider) not in {_inode(db), _inode(runtime)},
                  "provider evidence may not alias canonical/runtime SQLite")
        _need(type(self.admission_source) is SQLiteRuntimeAdmissionSource,
              "existing R6.21 SQLiteRuntimeAdmissionSource required")
        _need(type(self.admission_engine) is RuntimeAdmissionEngine,
              "existing canonical RuntimeAdmissionEngine required")
        replay = getattr(self.admission_engine, "_replay", None)
        _need(type(replay) is SQLiteR11RuntimeAdmissionReplayGuard,
              "original durable RuntimeAdmission replay guard required")
        replay.verify_identity()
        replay_db = _direct_file(replay.path, "durable replay SQLite")
        _need(replay_db != db and replay_db != runtime
              and replay_db not in {state1, state2, provider}
              and _inode(replay_db) not in {_inode(db), _inode(runtime)},
              "replay SQLite must not alias original stores")
        _need(isinstance(self.authority_admission, LiveAuthorityAdmission),
              "canonical live authority revalidator required")
        _need(type(self.currentness_trust) is CurrentnessSourceTrustBinding,
              "independent currentness trust required")
        _need(type(self.worker_durable_admission_trust) is RuntimeAdmissionSourceTrustBinding,
              "worker private admission trust required")
        self.currentness_trust.validate()
        self.worker_durable_admission_trust.validate()
        for callback, label in (
            (self.preparation_evidence_source, "R6.20 independent preparation evidence"),
            (self.runtime_identity_source, "current runtime identity"),
            (self.provisioning_binding_source, "current provisioning"),
            (self.transfer_binding_source, "current transfer binding"),
            (self.now_fn, "trusted clock"),
        ):
            _need(callable(callback), label + ": callable owner required")
        _need(callable(getattr(self.dispatch_source, "current_dispatch", None)),
              "current dispatch provider missing")
        observed = self.now_fn()
        _need(type(observed) is datetime and observed.tzinfo is not None,
              "trusted time must be timezone-aware")
        expected = self.currentness_trust.binding()
        actual = tuple(getattr(self.currentness_source, key, None) for key in (
            "source_id", "source_instance_id", "implementation_digest",
            "trust_anchor_id", "trust_anchor_digest",
        ))
        _need(actual == expected, "source currentness/trust mismatch")
        return self


def assemble_original_owners(sources: CurrentOwnerSources) -> tuple[
    CooperativeRuntimePreparationProvider,
    CooperativeControlPlaneMaterializer,
    CooperativeRuntimeCompositionRoot,
    str,
]:
    """Build existing three classes only; no admission, grant, worker claim, Docker.

    The caller must already possess actual independent service sources.
    This function initialises private journals and must run only in a separately
    admitted release/canary, not in a read-only inspection transaction.
    """
    s = sources.validate()
    prep = CooperativeRuntimePreparationProvider(
        mission_db=s.mission_db,
        artifact_root=s.artifact_root,
        evidence_source=s.preparation_evidence_source,
        admission_engine=s.admission_engine,
        admission_source=s.admission_source,
        now_fn=s.now_fn,
    )
    trust = prep.admission_trust()
    publisher = SQLiteCooperativeRuntimeEvidencePublisher(s.provider_evidence_db)
    exporter = CooperativeRuntimeEvidenceExporter(
        publisher=publisher,
        context_source=prep,
        admission_source=prep.admission_source,
        admission_trust=trust,
        authority_admission=s.authority_admission,
        currentness_source=s.currentness_source,
        currentness_trust=s.currentness_trust,
        dispatch_source=s.dispatch_source,
        runtime_identity_source=s.runtime_identity_source,
        provisioning_binding_source=s.provisioning_binding_source,
        context_pin_source=_never_pin_from_worker,
        transfer_binding_source=s.transfer_binding_source,
        now_fn=s.now_fn,
    )
    materializer = CooperativeControlPlaneMaterializer(
        mission_db=s.mission_db,
        provider_context_root=s.carrier_root,
        exporter_template=exporter,
        ttl_seconds=10,
    )

    upstream = SQLiteEvidenceRuntimeAdmissionSource(
        s.provider_evidence_db, trust, now_fn=s.now_fn,
    )
    pins = SQLiteContextPinSource(s.provider_evidence_db, now_fn=s.now_fn)
    dispatch = SQLiteFleetDispatchSource(s.provider_evidence_db, now_fn=s.now_fn)
    identity = SQLiteRuntimeIdentitySource(s.provider_evidence_db, now_fn=s.now_fn)
    provisioning = SQLiteProvisioningBindingSource(s.provider_evidence_db, now_fn=s.now_fn)
    transfer = SQLiteTransferBindingSource(s.provider_evidence_db, now_fn=s.now_fn)
    current = SQLiteEffectTimeCurrentnessSource(
        s.provider_evidence_db, s.currentness_trust, now_fn=s.now_fn,
    )

    def resolver_for(assignment_id: str):
        return PinnedCooperativeContextResolver(
            mission_db=s.mission_db,
            context_directory=s.carrier_root,
            pins=(pins(assignment_id),),
            admission_source=upstream,
            admission_trust=trust,
            dispatch_source=dispatch,
            runtime_identity_source=identity,
            now_fn=s.now_fn,
        )

    root = CooperativeRuntimeCompositionRoot(
        mission_db=s.mission_db,
        artifact_root=s.artifact_root,
        context_parent=s.worker_context_parent,
        verifier_parent=s.worker_verifier_parent,
        materialization_db=s.worker_materialization_db,
        runtime_state_db=s.worker_runtime_state_db,
        context_source=lambda aid: resolver_for(aid)(aid),
        qualification_context_source=lambda aid: resolver_for(aid).resolve_for_qualification(aid),
        upstream_admission_source=upstream,
        upstream_admission_trust=trust,
        durable_admission_trust=s.worker_durable_admission_trust,
        authority_admission=s.authority_admission,
        currentness_source=current,
        currentness_trust=s.currentness_trust,
        dispatch_source=dispatch,
        runtime_identity_source=identity,
        provisioning_binding_source=provisioning,
        transfer_binding_source=transfer,
        now_fn=s.now_fn,
    )
    bound = CooperativeSourceBoundPreactivation(
        prep, materializer, root, s.worker_id,
    ).validate()
    _need(bound.authority_effect == "NONE", "non-authorizing factory invariant")
    return prep, materializer, root, s.worker_id

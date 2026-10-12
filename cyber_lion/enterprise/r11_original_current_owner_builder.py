"""R11 original owner assembly from pre-existing independent service owners.

This is a bounded constructor, NOT an original evidence issuer or operational
registry. It joins the original currently observed source objects. The original
protected control plane must separately supply and authorize those objects
before invoking this function and the independently SHA-pinned wrapper.

build_current_owner_sources(owners) is explicitly parameterized; unlike the
operator-installed zero-argument external module, it has no hidden registry,
environment fallback, static grants, or synthetic successful evidence. It
does NOT open writable SQLite, issue admission, evaluate PDP or activate MD001.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding
from cyber_lion.contracts.runtime_enforcement import PDPSourceTrustBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.cooperative_runtime_preparer import CooperativeRuntimePreparationEvidence
from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.enterprise.runtime_enforcement import RuntimeAdmissionEngine
from cyber_lion.enterprise.runtime_execution import SQLiteRuntimeAdmissionSource
from cyber_lion.enterprise.r11_runtime_admission_replay import SQLiteR11RuntimeAdmissionReplayGuard
from cyber_lion.enterprise.r11_canonical_pdp_evidence import SQLiteR11CanonicalPDPEvidenceReader
from cyber_lion.mission_control.cooperative_current_owner_wiring import (
    CurrentOwnerSources,
)

SCHEMA="lion.r11.original-current-owner-sources/v1"
MISSION="LION-APPLICATION-FACTORY-CROSS-MODEL-R1"
REPOSITORY="DonkeyJJLove/ai_platform"
WORKER="MD001"
_DIGEST=re.compile(r"^[0-9a-f]{64}$")


class R11OriginalCurrentSourceError(RuntimeError):
    pass


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise R11OriginalCurrentSourceError(reason)


def _binding(source) -> tuple[Any, ...]:
    return tuple(getattr(source,field,None) for field in (
        "source_id","source_instance_id","implementation_digest",
        "trust_anchor_id","trust_anchor_digest",
    ))


@dataclass(frozen=True)
class OriginalPreparationEvidenceTrust:
    source_id: str
    source_instance_id: str
    source_implementation_digest: str
    trust_anchor_id: str
    trust_anchor_digest: str

    def binding(self):
        for value in (self.source_id,self.source_instance_id,self.trust_anchor_id):
            _need(type(value) is str and bool(value),
                  "original preparation trust source identity unavailable")
        for value in (self.source_implementation_digest,self.trust_anchor_digest):
            _need(type(value) is str and _DIGEST.fullmatch(value) is not None,
                  "original preparation trust digest unavailable")
        return (self.source_id,self.source_instance_id,
                self.source_implementation_digest,self.trust_anchor_id,
                self.trust_anchor_digest)


@dataclass(frozen=True)
class OriginalR11ServiceOwners:
    """Already-installed original control-plane producers, never JSON receipts."""
    repository: str
    mission_id: str
    worker_id: str
    mission_db: Path
    artifact_root: Path
    carrier_root: Path
    provider_evidence_db: Path
    worker_context_parent: Path
    worker_verifier_parent: Path
    worker_materialization_db: Path
    worker_runtime_state_db: Path
    preparation_source: Any
    preparation_trust: OriginalPreparationEvidenceTrust
    authority_admission: LiveAuthorityAdmission
    pdp_source: SQLiteR11CanonicalPDPEvidenceReader
    pdp_trust: PDPSourceTrustBinding
    admission_replay_guard: SQLiteR11RuntimeAdmissionReplayGuard
    admission_source: SQLiteRuntimeAdmissionSource
    currentness_source: Any
    currentness_trust: CurrentnessSourceTrustBinding
    dispatch_source: Any
    runtime_identity_source: Callable[..., Any]
    provisioning_binding_source: Callable[..., Any]
    transfer_binding_source: Callable[..., Mapping[str, Any]]
    worker_durable_admission_trust: RuntimeAdmissionSourceTrustBinding
    now_fn: Callable[[], datetime]

    def validate(self) -> "OriginalR11ServiceOwners":
        _need(type(self) is OriginalR11ServiceOwners,
              "original exact typed service owners required")
        _need(self.repository == REPOSITORY and self.mission_id == MISSION
              and self.worker_id == WORKER,
              "original service scope must be exact Application Factory MD001")
        _need(type(self.preparation_trust) is OriginalPreparationEvidenceTrust,
              "original preparation trust required")
        _need(callable(getattr(self.preparation_source,"resolve",None)),
              "original preparation source resolver unavailable")
        _need(_binding(self.preparation_source)==self.preparation_trust.binding(),
              "original preparation source/trust mismatch")
        _need(type(self.pdp_source) is SQLiteR11CanonicalPDPEvidenceReader,
              "original read-only PDP evidence source required")
        _need(type(self.pdp_trust) is PDPSourceTrustBinding,
              "original PDP source trust required")
        self.pdp_trust.validate()
        _need(_binding(self.pdp_source) == self.pdp_trust.binding(),
              "original PDP source/trust mismatch")
        # Verify the original reader actually retains its bound source.
        # No resolve() is called because issuing a grant/ALLOW is not preflight.
        self.pdp_source._check_store()
        _need(type(self.admission_replay_guard) is SQLiteR11RuntimeAdmissionReplayGuard,
              "original durable replay guard required")
        self.admission_replay_guard.verify_identity()
        _need(isinstance(self.authority_admission,LiveAuthorityAdmission),
              "original LiveAuthorityAdmission required")
        _need(type(self.admission_source) is SQLiteRuntimeAdmissionSource,
              "pre-existing original RuntimeAdmission SQLite source required")
        _need(type(self.currentness_trust) is CurrentnessSourceTrustBinding,
              "independent original currentness trust required")
        self.currentness_trust.validate()
        _need(_binding(self.currentness_source)==self.currentness_trust.binding(),
              "original currentness source/trust mismatch")
        _need(type(self.worker_durable_admission_trust) is RuntimeAdmissionSourceTrustBinding,
              "original worker durable admission trust required")
        self.worker_durable_admission_trust.validate()
        _need(callable(getattr(self.dispatch_source,"current_dispatch",None)),
              "original dispatch source unavailable")
        for provider,name in (
            (self.runtime_identity_source,"runtime identity"),
            (self.provisioning_binding_source,"provisioning"),
            (self.transfer_binding_source,"transfer binding"),
            (self.now_fn,"trusted clock"),
        ):
            _need(callable(provider),"original "+name+" source missing")
        stamp=self.now_fn()
        _need(type(stamp) is datetime and stamp.tzinfo is not None,
              "original trusted clock is not UTC-aware")
        _need(self.preparation_source is not self.pdp_source,
              "preparation and canonical PDP owner cannot alias")
        _need(Path(self.pdp_source.path)!=Path(self.admission_replay_guard.path),
              "PDP and RuntimeAdmission replay SQLite cannot alias")
        return self


def build_current_owner_sources(owners: OriginalR11ServiceOwners) -> CurrentOwnerSources:
    """Bind exact existing originals without a PDP decision, grant or state write.

    Must be called by the independently source-pinned control-plane adapter
    only after it obtained real source objects and their current attestations.
    """
    owner=owners.validate()
    engine=RuntimeAdmissionEngine(
        authority_admission=owner.authority_admission,
        pdp_source=owner.pdp_source,
        pdp_source_trust=owner.pdp_trust,
        replay_guard=owner.admission_replay_guard,
    )

    def original_preparation_for(assignment_id: str) -> CooperativeRuntimePreparationEvidence:
        _need(type(assignment_id) is str and bool(assignment_id),
              "canonical assignment identity required")
        _need(_binding(owner.preparation_source)==owner.preparation_trust.binding(),
              "original preparation source drift before resolve")
        observed=owner.preparation_source.resolve(assignment_id)
        _need(_binding(owner.preparation_source)==owner.preparation_trust.binding(),
              "original preparation source drift after resolve")
        _need(type(observed) is CooperativeRuntimePreparationEvidence,
              "independent original R6.20 evidence unavailable")
        observed.validate()
        # The exact mission is captured from the already validated owner
        # envelope; global config changes cannot rebind this callback later.
        _need(observed.proposal.mission_id==owner.mission_id,
              "original preparation evidence mission mismatch")
        return observed

    sources=CurrentOwnerSources(
        mission_db=Path(owner.mission_db),
        artifact_root=Path(owner.artifact_root),
        carrier_root=Path(owner.carrier_root),
        provider_evidence_db=Path(owner.provider_evidence_db),
        worker_context_parent=Path(owner.worker_context_parent),
        worker_verifier_parent=Path(owner.worker_verifier_parent),
        worker_materialization_db=Path(owner.worker_materialization_db),
        worker_runtime_state_db=Path(owner.worker_runtime_state_db),
        preparation_evidence_source=original_preparation_for,
        admission_engine=engine,
        admission_source=owner.admission_source,
        authority_admission=owner.authority_admission,
        currentness_source=owner.currentness_source,
        currentness_trust=owner.currentness_trust,
        dispatch_source=owner.dispatch_source,
        runtime_identity_source=owner.runtime_identity_source,
        provisioning_binding_source=owner.provisioning_binding_source,
        transfer_binding_source=owner.transfer_binding_source,
        worker_durable_admission_trust=owner.worker_durable_admission_trust,
        now_fn=owner.now_fn,
        worker_id=owner.worker_id,
    )
    # Reacquire path, authority, PDP, currentness and replay identity; this
    # is a pure preflight and must not open private writable DBs.
    sources.validate()
    return sources

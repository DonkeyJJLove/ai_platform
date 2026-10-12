"""R11 original R6.20 source: read and join EXISTING canonical evidence.

This is a read-only producer of the typed CooperativeRuntimePreparationEvidence
carrier, not the authority/PDP/provisioning issuer. An independent control-plane
owner MUST have issued each upstream component already. This provider obtains
them by exact assignment, mission, generation and input digest; it validates
against original Mission Control SQL and an INDEPENDENT canonical PDP record.
No RuntimeAdmissionEngine or LiveAuthorityAdmission.admit is called here.

It is a source candidate, not an installed original build_current_owner_sources()
service or proof of signed production authority.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass,fields
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable

from cyber_lion.contracts.action_proposal_context import ExplicitActionProposalContext
from cyber_lion.contracts.action_runtime_binding import (
    RuntimeBindingCurrentness,bind_allowed_action_to_runtime_inputs,
)
from cyber_lion.contracts.executor_provisioning import (
    ExecutorProvisioningRequest,ProviderTrustBinding,ProvisionedExecutor,
)
from cyber_lion.contracts.executor_sandbox import (
    ExecutionSandboxPolicy,FleetDispatchBinding,ProvisioningBinding,SandboxRuntimeBinding,
)
from cyber_lion.contracts.runtime_enforcement import PDPSourceTrustBinding
from cyber_lion.enterprise.control_plane import ActionProposal
from cyber_lion.enterprise.cooperative_dependency_provider import _ReadOnlySQLite
from cyber_lion.enterprise.cooperative_runtime_preparer import (
    CooperativeRuntimePreparationEvidence,validate_cooperative_runtime_preparation_inputs,
)
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority
from cyber_lion.enterprise.policy_gate import PDPResult
from cyber_lion.enterprise.r11_original_current_owner_builder import OriginalPreparationEvidenceTrust
from cyber_lion.enterprise.r11_canonical_pdp_evidence import SQLiteR11CanonicalPDPEvidenceReader

SCHEMA = "lion.r11.original-r620-evidence-source/v1"
REPOSITORY = "DonkeyJJLove/ai_platform"
MISSION = "LION-APPLICATION-FACTORY-CROSS-MODEL-R1"
WORKER = "MD001"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class R11OriginalR620EvidenceError(RuntimeError):
    pass


def _need(ok: bool, why: str) -> None:
    if not ok:
        raise R11OriginalR620EvidenceError(why)


def _binding(obj) -> tuple[Any, ...]:
    return tuple(getattr(obj,k,None) for k in (
        "source_id","source_instance_id","implementation_digest",
        "trust_anchor_id","trust_anchor_digest",
    ))


@dataclass(frozen=True)
class OriginalR620PreparationParts:
    """Twelve pre-existing original R6.20 inputs; no PDPResult is synthesized."""
    proposal: ActionProposal
    proposal_context: ExplicitActionProposalContext
    pdp_result: PDPResult
    currentness: RuntimeBindingCurrentness
    admitted_authority: LiveAdmittedAuthority
    provisioning_request: ExecutorProvisioningRequest
    provider_trust: ProviderTrustBinding
    provisioned_executor: ProvisionedExecutor
    sandbox_runtime: SandboxRuntimeBinding
    dispatch: FleetDispatchBinding
    provisioning: ProvisioningBinding
    sandbox_policy: ExecutionSandboxPolicy

    def evidence(self) -> CooperativeRuntimePreparationEvidence:
        _need({f.name for f in fields(self)} ==
              {f.name for f in fields(CooperativeRuntimePreparationEvidence)},
              "original R6.20 evidence contract drift")
        try:
            return CooperativeRuntimePreparationEvidence(
                **{f.name:getattr(self,f.name) for f in fields(self)}
            ).validate()
        except Exception as exc:
            raise R11OriginalR620EvidenceError(
                "original R6.20 input contracts invalid"
            ) from exc


class ReadOnlyOriginalR620EvidenceSource:
    """Bound consumer of real issued preparation parts and original PDP SQLite."""

    def __init__(
        self, *,
        mission_db: str | Path,
        artifact_root: str | Path,
        parts_source: object,
        parts_trust: OriginalPreparationEvidenceTrust,
        source_trust: OriginalPreparationEvidenceTrust,
        canonical_pdp_source: SQLiteR11CanonicalPDPEvidenceReader,
        canonical_pdp_trust: PDPSourceTrustBinding,
        now_fn: Callable[[],datetime],
        mission_id: str = MISSION,
        worker_id: str = WORKER,
    ):
        _need(type(mission_id) is str and mission_id == MISSION
              and type(worker_id) is str and worker_id == WORKER,
              "original R6.20 scope must be exact Application Factory MD001")
        _need(type(parts_trust) is OriginalPreparationEvidenceTrust
              and type(source_trust) is OriginalPreparationEvidenceTrust,
              "separate original R6.20 source trusts required")
        _need(parts_trust.binding() != source_trust.binding(),
              "original input and composed evidence trust must be distinct")
        _need(_binding(parts_source) == parts_trust.binding()
              and callable(getattr(parts_source,"resolve_exact",None)),
              "independent original R6.20 input source/trust mismatch")
        _need(type(canonical_pdp_source) is SQLiteR11CanonicalPDPEvidenceReader
              and type(canonical_pdp_trust) is PDPSourceTrustBinding,
              "independent original canonical PDP source required")
        canonical_pdp_trust.validate()
        _need(_binding(canonical_pdp_source) == canonical_pdp_trust.binding(),
              "canonical PDP source/trust mismatch")
        _need(callable(now_fn),"trusted original R6.20 clock missing")
        artifact=Path(artifact_root)
        _need(artifact.is_absolute() and artifact.is_dir()
              and not artifact.is_symlink()
              and artifact.resolve(strict=True)==artifact,
              "original R6.20 artifact root unavailable")
        # Original dependency provider is the existing read-only SQL owner.
        self._sql=_ReadOnlySQLite(mission_db)
        self.mission_db=self._sql.path
        self.artifact_root=artifact
        self._parts=parts_source
        self._parts_trust=parts_trust
        self._source_trust=source_trust
        self._pdp=canonical_pdp_source
        self._pdp_trust=canonical_pdp_trust
        self._now=now_fn
        self.mission_id=mission_id
        self.worker_id=worker_id
        self.source_id,self.source_instance_id,self.implementation_digest,\
            self.trust_anchor_id,self.trust_anchor_digest=source_trust.binding()
        self._trusted_now()

    def _trusted_now(self) -> datetime:
        value=self._now()
        _need(type(value) is datetime and value.tzinfo is not None,
              "original R6.20 trusted time unavailable")
        return value.astimezone(timezone.utc)

    def _snapshot(self, assignment_id: str) -> dict[str,Any]:
        _need(type(assignment_id) is str and _ID.fullmatch(assignment_id) is not None,
              "exact original assignment identity required")
        try:
            with closing(self._sql.connect()) as db:
                db.row_factory=sqlite3.Row
                rows=db.execute(
                    "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
                    (assignment_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise R11OriginalR620EvidenceError(
                "canonical Mission Control assignment unavailable"
            ) from exc
        _need(len(rows)==1,"canonical assignment missing or ambiguous")
        record=dict(rows[0])
        _need(
            record.get("assignment_id")==assignment_id
            and record.get("mission_id")==self.mission_id
            and record.get("material_drone_id")==self.worker_id
            and record.get("state")=="HELD"
            and type(record.get("lease_generation")) is int
            and record["lease_generation"]>=1,
            "canonical MD001 assignment must be HELD and bound",
        )
        content=record.get("input_json")
        _need(type(content) is str
              and sha256(content.encode("utf-8")).hexdigest()==record.get("input_digest"),
              "original canonical assignment input digest mismatch")
        return record

    def resolve(self, assignment_id: str) -> CooperativeRuntimePreparationEvidence:
        # Compatibility with original read-only callers. R6.21's admission
        # path uses resolve_at() to bind one exact upstream clock observation.
        return self.resolve_at(assignment_id,self._trusted_now())

    def resolve_at(
        self, assignment_id: str, trusted_now: datetime,
    ) -> CooperativeRuntimePreparationEvidence:
        _need(type(trusted_now) is datetime and trusted_now.tzinfo is not None,
              "original R6.21 bound issuance clock unavailable")
        bound_now=trusted_now.astimezone(timezone.utc)
        first_clock=self._trusted_now()
        _need(0 <= (first_clock-bound_now).total_seconds() <= 5,
              "original R6.21 issuance clock stale or in future")
        before=self._snapshot(assignment_id)
        _need(_binding(self._parts)==self._parts_trust.binding(),
              "original input source identity changed before read")
        try:
            parts=self._parts.resolve_exact(
                assignment_id,before["mission_id"],before["lease_generation"],
                before["input_digest"],bound_now,
            )
        except Exception as exc:
            raise R11OriginalR620EvidenceError(
                "independent original R6.20 input evidence unavailable"
            ) from exc
        _need(_binding(self._parts)==self._parts_trust.binding(),
              "original input source identity changed after read")
        _need(type(parts) is OriginalR620PreparationParts,
              "independent original R6.20 parts type required")
        evidence=parts.evidence()
        try:
            validate_cooperative_runtime_preparation_inputs(
                assignment=before,artifact_root=self.artifact_root,evidence=evidence
            )
            # This binder is PURE; it does not ask the canonical PDP to decide,
            # consume a replay key or create a new RuntimeAdmission.
            _effect,_identity,bound_pdp=bind_allowed_action_to_runtime_inputs(
                evidence.proposal,evidence.proposal_context,evidence.pdp_result,
                evidence.currentness,evidence.provisioned_executor,
            )
        except Exception as exc:
            raise R11OriginalR620EvidenceError(
                "original R6.20 binding to canonical assignment denied"
            ) from exc
        _need(evidence.currentness.pdp_source_trust == self._pdp_trust,
              "original R6.20 PDP source trust drift")
        _need(evidence.currentness.trusted_now.astimezone(timezone.utc)==bound_now,
              "original R6.20 issuance clock drift")
        _need(_binding(self._pdp)==self._pdp_trust.binding(),
              "original PDP source identity drift")
        try:
            canonical=self._pdp.resolve(
                evidence.pdp_result.applied.request_id,
                evidence.pdp_result.applied.gate_event_id,
            )
            current_policy=self._pdp.current_policy_binding(
                evidence.pdp_result.applied.policy_binding
            )
        except Exception as exc:
            raise R11OriginalR620EvidenceError(
                "independently issued original canonical PDP unavailable"
            ) from exc
        _need(canonical == bound_pdp
              and current_policy==evidence.pdp_result.applied.policy_binding,
              "original canonical PDP/effect/issued policy substitution")
        _need(_binding(self._pdp)==self._pdp_trust.binding(),
              "original PDP source identity changed after resolve")
        _need(_binding(self._parts)==self._parts_trust.binding(),
              "original input source changed after canonical readback")
        _need(self._snapshot(assignment_id)==before,
              "canonical HELD assignment changed during evidence assembly")
        # Live clocks advance. Reject rollback and a long-running assembly,
        # rather than requiring the physical clock to be exactly frozen.
        after_clock=self._trusted_now()
        _need(first_clock <= after_clock
              and 0 <= (after_clock-bound_now).total_seconds() <= 5,
              "original trusted clock drift during source assembly")
        return evidence

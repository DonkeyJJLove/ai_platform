"""Fail-closed production-entry dossier and lifecycle contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Any

from cyber_lion.contracts.environment_lifecycle import (
    AssuranceDimension,
    AssuranceState,
    AssuranceVector,
    EnvironmentLifecycleContractError,
    LifecycleState,
    canonical_digest,
    _sha40,
    _sha256,
    _text,
    _tuple_text,
    _utc,
)


class ProductionEntryContractError(EnvironmentLifecycleContractError):
    pass


class AuthorityState(str, Enum):
    NONE = "NONE"
    REQUIRED = "REQUIRED"
    AUTHORIZED = "AUTHORIZED"
    REVOKED = "REVOKED"


PHYSICAL_EXTERNAL_CONTROL_DOMAIN_REQUIRED = "PHYSICAL_EXTERNAL_CONTROL_DOMAIN_REQUIRED"
NON_EXPORTABLE_HARDWARE_KEYSTORE_REQUIRED = "NON_EXPORTABLE_HARDWARE_KEYSTORE_REQUIRED"
CURRENTNESS_EVIDENCE_REQUIRED = "CURRENTNESS_EVIDENCE_REQUIRED"
PRODUCTION_READINESS_CERTIFICATION_REQUIRED = "PRODUCTION_READINESS_CERTIFICATION_REQUIRED"
SEPARATE_AUTHORITY_PLANE_REQUIRED = "SEPARATE_AUTHORITY_PLANE_REQUIRED"


# AUTHORITY and DEPLOYMENT_READINESS are deliberately excluded: readiness
# eligibility is computed before those independent planes may act.
PRODUCTION_REQUIRED_DIMENSIONS = (
    AssuranceDimension.PROTOCOL_CORRECTNESS,
    AssuranceDimension.ROLE_SEPARATION,
    AssuranceDimension.IDENTITY_SEPARATION,
    AssuranceDimension.LOGICAL_TOPOLOGY,
    AssuranceDimension.PHYSICAL_TOPOLOGY,
    AssuranceDimension.OBSERVABILITY,
    AssuranceDimension.EVIDENCE_PROVENANCE,
    AssuranceDimension.CRYPTOGRAPHIC_VERIFICATION,
    AssuranceDimension.PRIVATE_KEY_CUSTODY,
    AssuranceDimension.NON_EXPORTABLE_KEY_STORAGE,
    AssuranceDimension.FAILURE_DOMAIN_INDEPENDENCE,
    AssuranceDimension.OPERATIONAL_RESILIENCE,
    AssuranceDimension.RECONCILIATION,
    AssuranceDimension.ROLLBACK_READINESS,
    AssuranceDimension.CURRENTNESS,
    AssuranceDimension.GOVERNANCE,
)

LAB_VALIDATION_DIMENSIONS = (
    AssuranceDimension.PROTOCOL_CORRECTNESS,
    AssuranceDimension.ROLE_SEPARATION,
    AssuranceDimension.IDENTITY_SEPARATION,
    AssuranceDimension.LOGICAL_TOPOLOGY,
    AssuranceDimension.OBSERVABILITY,
    AssuranceDimension.EVIDENCE_PROVENANCE,
    AssuranceDimension.CRYPTOGRAPHIC_VERIFICATION,
)


@dataclass(frozen=True)
class ProductionEntryDossier:
    repository: str
    candidate_sha: str
    candidate_tree: str
    candidate_branch: str
    lifecycle_state: LifecycleState
    assurance_vector: AssuranceVector
    accepted_claims: tuple[str, ...]
    rejected_claims: tuple[str, ...]
    stale_claims: tuple[str, ...]
    conflicting_claims: tuple[str, ...]
    missing_dimensions: tuple[str, ...]
    current_blockers: tuple[str, ...]
    production_eligible: bool
    authority_state: AuthorityState
    authority_evidence_digest: str | None
    required_next_evidence: tuple[str, ...]
    required_human_decisions: tuple[str, ...]
    generated_at: str
    dossier_digest: str = ""

    def validate(self) -> "ProductionEntryDossier":
        _text(self.repository, "repository")
        _sha40(self.candidate_sha, "candidate_sha")
        _sha40(self.candidate_tree, "candidate_tree")
        _text(self.candidate_branch, "candidate_branch")
        if not isinstance(self.lifecycle_state, LifecycleState):
            raise ProductionEntryContractError("lifecycle_state invalid")
        if type(self.assurance_vector) is not AssuranceVector:
            raise ProductionEntryContractError("assurance_vector invalid")
        self.assurance_vector.validate()
        for name in (
            "accepted_claims", "rejected_claims", "stale_claims", "conflicting_claims",
            "missing_dimensions", "current_blockers", "required_next_evidence",
            "required_human_decisions",
        ):
            _tuple_text(getattr(self, name), name)
        claim_sets = [
            set(self.accepted_claims),
            set(self.rejected_claims),
            set(self.stale_claims),
            set(self.conflicting_claims),
        ]
        for i, left in enumerate(claim_sets):
            for right in claim_sets[i + 1:]:
                if left & right:
                    raise ProductionEntryContractError("claim classification overlap")
        if type(self.production_eligible) is not bool:
            raise ProductionEntryContractError("production_eligible invalid")
        if not isinstance(self.authority_state, AuthorityState):
            raise ProductionEntryContractError("authority_state invalid")
        if self.authority_state is AuthorityState.AUTHORIZED:
            if self.authority_evidence_digest is None:
                raise ProductionEntryContractError("authorized dossier requires authority evidence")
            _sha256(self.authority_evidence_digest, "authority_evidence_digest")
        elif self.authority_evidence_digest is not None:
            raise ProductionEntryContractError("authority evidence without AUTHORIZED state")
        _utc(self.generated_at, "generated_at")

        required_pass = all(
            self.assurance_vector.state_for(dimension) is AssuranceState.PASS
            for dimension in PRODUCTION_REQUIRED_DIMENSIONS
        )
        expected_eligible = required_pass and not self.current_blockers and not self.missing_dimensions
        if self.production_eligible is not expected_eligible:
            raise ProductionEntryContractError("production eligibility is not derived from assurance")
        if self.production_eligible:
            if self.lifecycle_state is not LifecycleState.PRODUCTION_ENTRY_ELIGIBLE:
                raise ProductionEntryContractError("eligible dossier lifecycle mismatch")
            if self.authority_state is not AuthorityState.NONE:
                raise ProductionEntryContractError("entry eligibility must not mint authority")
        else:
            if self.lifecycle_state in {
                LifecycleState.PRODUCTION_ENTRY_ELIGIBLE,
                LifecycleState.PRODUCTION_READINESS_CERTIFIED,
                LifecycleState.PRODUCTION_AUTHORITY_REQUIRED,
                LifecycleState.PRODUCTION_AUTHORIZED,
                LifecycleState.PRODUCTION_DEPLOYMENT_READY,
                LifecycleState.PRODUCTION_CANARY_ACTIVE,
                LifecycleState.PRODUCTION_ACTIVE,
            }:
                raise ProductionEntryContractError("ineligible dossier claims production-ready lifecycle")
        if self.dossier_digest:
            expected = canonical_digest(
                b"LION/PRODUCTION-ENTRY-DOSSIER/1\0",
                self._digest_payload(),
            )
            if self.dossier_digest != expected:
                raise ProductionEntryContractError("dossier digest mismatch")
        return self

    def _digest_payload(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("dossier_digest", None)
        data["lifecycle_state"] = self.lifecycle_state.value
        data["authority_state"] = self.authority_state.value
        records = []
        for record in self.assurance_vector.records:
            row = asdict(record)
            row["dimension"] = record.dimension.value
            row["state"] = record.state.value
            records.append(row)
        data["assurance_vector"] = {"records": records}
        return data

    def sealed(self) -> "ProductionEntryDossier":
        if self.dossier_digest:
            return self.validate()
        digest = canonical_digest(b"LION/PRODUCTION-ENTRY-DOSSIER/1\0", self._digest_payload())
        return replace(self, dossier_digest=digest).validate()

    def digest(self) -> str:
        self.validate()
        if not self.dossier_digest:
            raise ProductionEntryContractError("unsealed dossier")
        return self.dossier_digest


@dataclass(frozen=True)
class LifecycleTransitionDecision:
    from_state: LifecycleState
    to_state: LifecycleState
    allowed: bool
    reason: str
    dossier_digest: str

    def validate(self) -> "LifecycleTransitionDecision":
        if not isinstance(self.from_state, LifecycleState) or not isinstance(self.to_state, LifecycleState):
            raise ProductionEntryContractError("transition state invalid")
        if type(self.allowed) is not bool:
            raise ProductionEntryContractError("transition allowed invalid")
        _text(self.reason, "reason")
        _sha256(self.dossier_digest, "dossier_digest")
        return self

    def digest(self) -> str:
        self.validate()
        return canonical_digest(
            b"LION/LIFECYCLE-TRANSITION-DECISION/1\0",
            {
                "from_state": self.from_state.value,
                "to_state": self.to_state.value,
                "allowed": self.allowed,
                "reason": self.reason,
                "dossier_digest": self.dossier_digest,
            },
        )

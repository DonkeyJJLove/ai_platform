from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import re

from .status import require_closed_status

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_EVIDENCE_BOUND_STATUSES = {
    "IMPLEMENTED",
    "PARTIALLY_IMPLEMENTED",
    "CONTRACT_ONLY",
    "VERIFIED_REFERENCE",
}
_OBSERVED_EVIDENCE_CLASSES = {
    "LIVE_CODE",
    "CURRENT_TEST",
    "EXACT_GIT_STATE",
    "MACHINE_EVIDENCE",
}


@dataclass(frozen=True, order=True)
class GapRecord:
    target_id: str
    status: str
    missing_contract: str = ""
    missing_runtime: str = ""
    missing_observation: str = ""
    missing_authority_boundary: str = ""
    missing_complete_mediation: str = ""
    next_minimal_gap: str = ""
    evidence_class: str = ""
    evidence_ref: str = ""

    def validate(self) -> "GapRecord":
        if not self.target_id.strip() or not self.status.strip():
            raise ValueError("gap target_id and status are required")
        require_closed_status(self.status)
        if self.status in _EVIDENCE_BOUND_STATUSES:
            if self.evidence_class not in _OBSERVED_EVIDENCE_CLASSES:
                raise ValueError("implemented gap status requires explicit observed evidence class")
            if not self.evidence_ref.strip():
                raise ValueError("implemented gap status requires explicit evidence_ref")
        if self.status == "TARGET_ONLY" and self.evidence_class in _OBSERVED_EVIDENCE_CLASSES:
            raise ValueError("TARGET_ONLY cannot carry live implementation evidence")
        return self

    def digest(self) -> str:
        self.validate()
        payload = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(b"LION/UML/GAP/2\0" + payload).hexdigest()


def transition_gap_status(
    record: GapRecord,
    *,
    new_status: str,
    evidence_class: str = "",
    evidence_ref: str = "",
) -> GapRecord:
    record.validate()
    require_closed_status(new_status)
    if record.status == "UNKNOWN" and new_status != "UNKNOWN":
        if evidence_class not in _OBSERVED_EVIDENCE_CLASSES:
            raise ValueError("UNKNOWN gap promotion requires explicit observed evidence class")
        if not evidence_ref.strip():
            raise ValueError("UNKNOWN gap promotion requires explicit evidence_ref")
    if new_status == "TARGET_ONLY" and record.status not in {"TARGET_ONLY", "UNKNOWN"}:
        raise ValueError("implemented gap cannot be silently demoted to TARGET_ONLY")
    return replace(
        record,
        status=new_status,
        evidence_class=evidence_class,
        evidence_ref=evidence_ref,
    ).validate()


def classify_historical_projection(*, observed_commit: str, current_commit: str) -> str:
    if observed_commit == current_commit:
        return "VERIFIED_REFERENCE"
    return "SUPERSEDED"


def classify_projection_currentness(
    *,
    observed_commit: str,
    observed_tree: str,
    current_commit: str,
    current_tree: str,
    material_drift: bool = True,
) -> str:
    """Classify a projection against an exact current Git identity.

    Exact commit and tree identity is required for CURRENT. Any known material
    baseline drift degrades to STALE; uncertainty about materiality remains UNKNOWN.
    The function never promotes a drifting projection to CURRENT.
    """
    for name, value in (
        ("observed_commit", observed_commit),
        ("observed_tree", observed_tree),
        ("current_commit", current_commit),
        ("current_tree", current_tree),
    ):
        if not _SHA40.fullmatch(value):
            raise ValueError(f"{name} must be exact lowercase SHA-1")
    if observed_commit == current_commit and observed_tree == current_tree:
        return "CURRENT"
    return "STALE" if material_drift else "UNKNOWN"


def _observed(target_id: str, evidence_ref: str) -> GapRecord:
    return GapRecord(
        target_id=target_id,
        status="VERIFIED_REFERENCE",
        evidence_class="LIVE_CODE",
        evidence_ref=evidence_ref,
    ).validate()


def _target(
    target_id: str,
    *,
    missing_contract: str = "",
    missing_runtime: str = "",
    next_minimal_gap: str,
) -> GapRecord:
    return GapRecord(
        target_id=target_id,
        status="TARGET_ONLY",
        missing_contract=missing_contract,
        missing_runtime=missing_runtime,
        next_minimal_gap=next_minimal_gap,
    ).validate()


def canonical_gap_projection() -> tuple[GapRecord, ...]:
    """Current AS-IS plus explicit TARGET/UNKNOWN gaps for exact-master projection."""
    return (
        _observed("GoalContract", "cyber_lion/contracts/evolutionary_state.py"),
        _observed("WorldSnapshot", "cyber_lion/contracts/evolutionary_state.py"),
        _observed("SystemSnapshot", "cyber_lion/contracts/evolutionary_state.py"),
        _observed("Gap", "cyber_lion/contracts/evolutionary_state.py"),
        _observed("BeanSpec", "cyber_lion/contracts/bean.py"),
        _observed("BeanCandidate", "cyber_lion/contracts/bean_candidate.py"),
        _observed("BeanInstance", "cyber_lion/contracts/bean.py"),
        _observed("CapabilityNeed", "cyber_lion/contracts/capability_need.py"),
        _observed("CompositionContract", "cyber_lion/contracts/bean_composition.py"),
        _observed("CompositionEngine", "cyber_lion/enterprise/bean_composition.py"),
        _observed("MosaicCell", "cyber_lion/contracts/mosaic.py"),
        _observed("HeterogeneousMosaicPlanner", "cyber_lion/enterprise/mosaic.py"),
        _observed("BeanBuilderChainBinding", "cyber_lion/contracts/bean_builder_bridge.py"),
        _observed("R2E4EvidenceBinding", "LION/evolution/SPECTRA_R2E4_EVIDENCE_BINDING.json"),
        _observed("FleetAggregateEffectBudget", "cyber_lion/enterprise/fleet_effect_budget.py"),
        _target(
            "AutonomyBlueprint",
            missing_contract="canonical autonomy blueprint contract",
            next_minimal_gap="define digest-bound AutonomyBlueprint",
        ),
        _target(
            "MaterializerRegistry",
            missing_contract="canonical materializer registry",
            next_minimal_gap="define domain-independent MaterializerRegistry",
        ),
        _target(
            "ActionSpec",
            missing_contract="canonical typed action specification beneath ActionProposal",
            next_minimal_gap="define canonical Action IR",
        ),
        _target(
            "LAIR",
            missing_contract="canonical LION Action IR implementation",
            next_minimal_gap="implement and validate canonical Action IR",
        ),
        _target(
            "LCMS",
            missing_contract="auditable command modeling syntax and parser",
            next_minimal_gap="define LCMS after Action IR",
        ),
        _target(
            "LocalConsole",
            missing_runtime="capability-reduced local console runtime",
            next_minimal_gap="implement read-only process.exec after LCMS",
        ),
        GapRecord(
            "GlobalCompleteMediation",
            "UNKNOWN",
            missing_complete_mediation="effect-specific closures do not prove system-wide reachable-surface coverage",
            next_minimal_gap="enumerate consequential effect surfaces",
        ).validate(),
    )


def canonical_target_gaps() -> tuple[GapRecord, ...]:
    """Compatibility alias for renderers written before AS-IS/TARGET separation."""
    return canonical_gap_projection()

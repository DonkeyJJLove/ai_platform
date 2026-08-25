from __future__ import annotations

from dataclasses import dataclass
from typing import Final

IMPLEMENTATION_STATUSES: Final = (
    "IMPLEMENTED",
    "PARTIALLY_IMPLEMENTED",
    "CONTRACT_ONLY",
    "VERIFIED_REFERENCE",
    "TARGET_ONLY",
    "UNKNOWN",
    "QUARANTINED",
    "SUPERSEDED",
)

EVIDENCE_CLASSES: Final = (
    "LIVE_CODE",
    "CURRENT_TEST",
    "EXACT_GIT_STATE",
    "MACHINE_EVIDENCE",
    "CANONICAL_DOCUMENTATION",
    "TARGET_ARCHITECTURE",
    "HISTORICAL_PROJECTION",
    "UNKNOWN",
)


@dataclass(frozen=True, order=True)
class ArchitectureStatus:
    status: str
    evidence_class: str
    rationale: str
    source_path: str = ""
    symbol: str = ""
    source_digest: str = ""

    def validate(self) -> "ArchitectureStatus":
        if self.status not in IMPLEMENTATION_STATUSES:
            raise ValueError("unknown architecture implementation status")
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise ValueError("unknown architecture evidence class")
        if not self.rationale.strip():
            raise ValueError("architecture status rationale is required")
        if self.status == "TARGET_ONLY":
            if self.source_digest or self.evidence_class in {"LIVE_CODE", "CURRENT_TEST"}:
                raise ValueError("TARGET_ONLY cannot claim implementation proof")
        if self.status == "UNKNOWN" and self.evidence_class != "UNKNOWN":
            raise ValueError("UNKNOWN status requires UNKNOWN evidence class")
        if self.status == "QUARANTINED" and self.evidence_class not in {
            "LIVE_CODE", "EXACT_GIT_STATE", "MACHINE_EVIDENCE"
        }:
            raise ValueError("QUARANTINED requires observed implementation/state evidence")
        if self.source_digest and len(self.source_digest) != 64:
            raise ValueError("source_digest must be SHA-256 when present")
        return self


def require_closed_status(value: str) -> str:
    if value not in IMPLEMENTATION_STATUSES:
        raise ValueError("status vocabulary is closed")
    return value

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Final

from .layout import DISPLAY_PLANES
from .status import IMPLEMENTATION_STATUSES, require_closed_status

_STATUS_MARKERS: Final = {
    "IMPLEMENTED": "[I]",
    "VERIFIED_REFERENCE": "[V]",
    "PARTIALLY_IMPLEMENTED": "[P]",
    "CONTRACT_ONLY": "[C]",
    "TARGET_ONLY": "[T]",
    "UNKNOWN": "[?]",
    "QUARANTINED": "[Q]",
    "SUPERSEDED": "[S]",
}
_VISUAL_DOMAIN = b"LION/UML/VISUAL-PROJECTION/1\0"


def status_marker(status: str) -> str:
    require_closed_status(status)
    return _STATUS_MARKERS[status]


@dataclass(frozen=True, order=True)
class VisualLegendEntry:
    status: str
    marker: str

    def validate(self) -> "VisualLegendEntry":
        require_closed_status(self.status)
        if self.marker != status_marker(self.status):
            raise ValueError("visual status marker mismatch")
        return self


@dataclass(frozen=True, order=True)
class VisualPlane:
    plane: str
    rank: int
    layers: tuple[str, ...]

    def validate(self) -> "VisualPlane":
        if self.plane not in DISPLAY_PLANES:
            raise ValueError("unknown visual plane")
        if self.rank != DISPLAY_PLANES.index(self.plane):
            raise ValueError("visual plane rank mismatch")
        if not self.layers:
            raise ValueError("visual plane requires layers")
        return self


@dataclass(frozen=True, order=True)
class VisualNode:
    node_id: str
    architecture_element_id: str
    label: str
    layer: str
    plane: str
    status: str
    marker: str
    source_path: str = ""
    source_digest: str = ""
    target_ref: str = ""

    def validate(self) -> "VisualNode":
        if not self.node_id.strip() or not self.architecture_element_id.strip() or not self.label.strip():
            raise ValueError("visual node identity and label are required")
        if self.plane not in DISPLAY_PLANES:
            raise ValueError("visual node plane is invalid")
        require_closed_status(self.status)
        if self.marker != status_marker(self.status):
            raise ValueError("visual node must carry explicit status marker")
        if self.status == "TARGET_ONLY":
            if not self.target_ref or self.source_path or self.source_digest:
                raise ValueError("TARGET_ONLY visual node must remain target-only")
        else:
            if not self.source_path or len(self.source_digest) != 64:
                raise ValueError("source-bound visual node requires provenance")
        return self


@dataclass(frozen=True, order=True)
class VisualFlow:
    flow_id: str
    steps: tuple[str, ...]

    def validate(self) -> "VisualFlow":
        if not self.flow_id.strip() or not self.steps:
            raise ValueError("visual flow identity and steps are required")
        if len(set(self.steps)) != len(self.steps):
            raise ValueError("visual flow steps must remain unique")
        return self


@dataclass(frozen=True, order=True)
class VisualGap:
    target_id: str
    status: str
    marker: str
    summary: str

    def validate(self) -> "VisualGap":
        if not self.target_id.strip():
            raise ValueError("visual gap target is required")
        require_closed_status(self.status)
        if self.marker != status_marker(self.status):
            raise ValueError("visual gap must carry explicit status marker")
        if not self.summary.strip():
            raise ValueError("visual gap summary is required")
        return self


@dataclass(frozen=True)
class VisualProjectionModel:
    projection_id: str
    source_tree_sha: str
    architecture_model_digest: str
    planes: tuple[VisualPlane, ...]
    nodes: tuple[VisualNode, ...]
    flows: tuple[VisualFlow, ...]
    gaps: tuple[VisualGap, ...]
    legend: tuple[VisualLegendEntry, ...]
    derived_only: bool = True
    runtime_evidence: str = "NONE"
    authority_effect: str = "NONE"

    def validate(self) -> "VisualProjectionModel":
        if not self.projection_id.strip():
            raise ValueError("visual projection id is required")
        if len(self.source_tree_sha) != 40 or len(self.architecture_model_digest) != 64:
            raise ValueError("visual projection source bindings are invalid")
        if not self.derived_only or self.runtime_evidence != "NONE" or self.authority_effect != "NONE":
            raise ValueError("visual projection cannot prove runtime or grant authority")
        for plane in self.planes:
            plane.validate()
        if tuple(p.plane for p in self.planes) != DISPLAY_PLANES:
            raise ValueError("all 9 display planes are required in canonical order")
        node_ids = tuple(node.node_id for node in self.nodes)
        if node_ids != tuple(sorted(set(node_ids))):
            raise ValueError("visual nodes must be sorted unique")
        for node in self.nodes:
            node.validate()
        for flow in self.flows:
            flow.validate()
        if len(self.flows) != 9:
            raise ValueError("all 9 canonical flows must be projectable")
        for gap in self.gaps:
            gap.validate()
        for entry in self.legend:
            entry.validate()
        if tuple(entry.status for entry in self.legend) != IMPLEMENTATION_STATUSES:
            raise ValueError("visual legend must expose all 8 status states")
        return self

    def canonical_bytes(self) -> bytes:
        self.validate()
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def digest(self) -> str:
        return sha256(_VISUAL_DOMAIN + self.canonical_bytes()).hexdigest()


def canonical_legend() -> tuple[VisualLegendEntry, ...]:
    return tuple(VisualLegendEntry(status, status_marker(status)).validate() for status in IMPLEMENTATION_STATUSES)

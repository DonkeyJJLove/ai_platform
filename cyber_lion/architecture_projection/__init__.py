"""Derived, non-authoritative architecture projection plane for LION."""
from .model import CanonicalDiagramModel, DiagramNode, DiagramEdge, DiagramGroup, DiagramProjectionManifest
from .extractor import ArchitectureProjectionExtractor, available_projection_names
from .plantuml import PlantUMLRenderer, serialize_plantuml
from .status import ArchitectureStatus, IMPLEMENTATION_STATUSES, EVIDENCE_CLASSES, require_closed_status
from .flows import ArchitectureFlow, ARCHITECTURE_LAYERS, FLOW_SPECS, canonical_flows
from .gap import GapRecord, canonical_target_gaps, classify_historical_projection
from .layout import LayoutHint, DISPLAY_PLANES, canonical_layout
from .full_architecture import ArchitectureElement, FullArchitectureModel, build_full_architecture_model

__all__ = [
    "CanonicalDiagramModel", "DiagramNode", "DiagramEdge", "DiagramGroup",
    "DiagramProjectionManifest", "ArchitectureProjectionExtractor",
    "available_projection_names", "PlantUMLRenderer", "serialize_plantuml",
    "ArchitectureStatus", "IMPLEMENTATION_STATUSES", "EVIDENCE_CLASSES",
    "require_closed_status", "ArchitectureFlow", "ARCHITECTURE_LAYERS",
    "FLOW_SPECS", "canonical_flows", "GapRecord", "canonical_target_gaps",
    "classify_historical_projection", "LayoutHint", "DISPLAY_PLANES",
    "canonical_layout", "ArchitectureElement", "FullArchitectureModel",
    "build_full_architecture_model",
]

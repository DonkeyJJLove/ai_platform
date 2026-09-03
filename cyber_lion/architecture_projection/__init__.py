from .current_truth import CurrentTruthProjection, TruthImplementationRecord, TruthSourceSpec, build_current_truth_projection, canonical_truth_source_specs
"""Derived, non-authoritative architecture projection plane for LION."""
from .model import CanonicalDiagramModel, DiagramNode, DiagramEdge, DiagramGroup, DiagramProjectionManifest
from .extractor import ArchitectureProjectionExtractor, available_projection_names
from .plantuml import PlantUMLRenderer, serialize_plantuml
from .status import ArchitectureStatus, IMPLEMENTATION_STATUSES, EVIDENCE_CLASSES, require_closed_status
from .flows import ArchitectureFlow, ARCHITECTURE_LAYERS, FLOW_SPECS, canonical_flows
from .gap import GapRecord, canonical_target_gaps, classify_historical_projection
from .layout import LayoutHint, DISPLAY_PLANES, canonical_layout
from .full_architecture import ArchitectureElement, FullArchitectureModel, build_full_architecture_model
from .visual_model import (
    VisualLegendEntry, VisualPlane, VisualNode, VisualFlow, VisualGap,
    VisualProjectionModel, canonical_legend, status_marker,
)
from .full_visual_projection import build_visual_projection
from .full_plantuml import (
    serialize_full_architecture_plantuml,
    serialize_flow_atlas_plantuml,
    serialize_gap_overlay_plantuml,
)
from .render_adapter import (
    RendererPin, VisualRenderArtifactPlan, VisualRenderPlan, VisualRenderManifest,
    build_visual_render_plan, build_visual_render_manifest,
)

__all__ = [
    "CanonicalDiagramModel", "DiagramNode", "DiagramEdge", "DiagramGroup",
    "DiagramProjectionManifest", "ArchitectureProjectionExtractor",
    "available_projection_names", "PlantUMLRenderer", "serialize_plantuml",
    "ArchitectureStatus", "IMPLEMENTATION_STATUSES", "EVIDENCE_CLASSES",
    "require_closed_status", "ArchitectureFlow", "ARCHITECTURE_LAYERS",
    "FLOW_SPECS", "canonical_flows", "GapRecord", "canonical_target_gaps",
    "classify_historical_projection", "LayoutHint", "DISPLAY_PLANES",
    "canonical_layout", "ArchitectureElement", "FullArchitectureModel",
    "build_full_architecture_model", "VisualLegendEntry", "VisualPlane",
    "VisualNode", "VisualFlow", "VisualGap", "VisualProjectionModel",
    "canonical_legend", "status_marker", "build_visual_projection",
    "serialize_full_architecture_plantuml", "serialize_flow_atlas_plantuml",
    "serialize_gap_overlay_plantuml", "RendererPin", "VisualRenderArtifactPlan",
    "VisualRenderPlan", "VisualRenderManifest", "build_visual_render_plan",
    "build_visual_render_manifest",
]

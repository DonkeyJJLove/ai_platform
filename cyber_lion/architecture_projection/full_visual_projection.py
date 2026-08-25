from __future__ import annotations

from hashlib import sha256

from .full_architecture import FullArchitectureModel
from .visual_model import (
    VisualFlow,
    VisualGap,
    VisualNode,
    VisualPlane,
    VisualProjectionModel,
    canonical_legend,
    status_marker,
)


def _visual_node_id(element_id: str) -> str:
    return "v_" + sha256(b"LION/UML/VISUAL-NODE/1\0" + element_id.encode("utf-8")).hexdigest()[:32]


def _plane_for_layer(model: FullArchitectureModel, layer: str) -> str:
    matches = [hint for hint in model.layout if layer in hint.layers]
    if not matches:
        raise ValueError(f"architecture layer has no display plane: {layer}")
    return min(matches, key=lambda hint: hint.rank).plane


def _gap_summary(gap: object) -> str:
    fields = (
        getattr(gap, "missing_contract", ""),
        getattr(gap, "missing_runtime", ""),
        getattr(gap, "missing_observation", ""),
        getattr(gap, "missing_authority_boundary", ""),
        getattr(gap, "missing_complete_mediation", ""),
        getattr(gap, "next_minimal_gap", ""),
    )
    summary = " | ".join(value.strip() for value in fields if isinstance(value, str) and value.strip())
    return summary or "explicit gap status without additional claim"


def build_visual_projection(model: FullArchitectureModel) -> VisualProjectionModel:
    model.validate()
    planes = tuple(
        VisualPlane(hint.plane, hint.rank, hint.layers).validate()
        for hint in sorted(model.layout, key=lambda item: item.rank)
    )
    nodes = []
    for element in model.elements:
        status = element.status.status
        nodes.append(
            VisualNode(
                node_id=_visual_node_id(element.element_id),
                architecture_element_id=element.element_id,
                label=element.label,
                layer=element.layer,
                plane=_plane_for_layer(model, element.layer),
                status=status,
                marker=status_marker(status),
                source_path=element.source_path,
                source_digest=element.status.source_digest,
                target_ref=element.target_ref,
            ).validate()
        )
    flows = tuple(
        VisualFlow(flow.flow_id, tuple(flow.steps)).validate()
        for flow in sorted(model.flows, key=lambda item: item.flow_id)
    )
    gaps = tuple(
        VisualGap(gap.target_id, gap.status, status_marker(gap.status), _gap_summary(gap)).validate()
        for gap in sorted(model.gaps, key=lambda item: item.target_id)
    )
    projection = VisualProjectionModel(
        projection_id="lion-full-architecture",
        source_tree_sha=model.source_tree_sha,
        architecture_model_digest=model.digest(),
        planes=planes,
        nodes=tuple(sorted(nodes)),
        flows=flows,
        gaps=gaps,
        legend=canonical_legend(),
    )
    projection.validate()
    represented_layers = {node.layer for node in projection.nodes}
    expected_layers = {layer for plane in projection.planes for layer in plane.layers}
    if represented_layers != expected_layers:
        raise ValueError("all 15 architecture layers must be visible exactly through canonical nodes")
    if not any(node.status == "TARGET_ONLY" for node in projection.nodes):
        raise ValueError("AS-IS versus TARGET overlay requires TARGET_ONLY architecture node")
    if not any(gap.status == "UNKNOWN" and gap.marker == "[?]" for gap in projection.gaps):
        raise ValueError("implementation gap overlay must preserve UNKNOWN")
    f005 = [node for node in projection.nodes if node.architecture_element_id == "quarantined-f005"]
    if len(f005) != 1 or f005[0].status != "QUARANTINED" or f005[0].marker != "[Q]":
        raise ValueError("F005 must remain visibly QUARANTINED")
    return projection

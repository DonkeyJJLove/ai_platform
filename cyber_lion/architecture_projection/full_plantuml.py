from __future__ import annotations

from hashlib import sha256

from .visual_model import VisualProjectionModel

_FORBIDDEN = ("!include", "!includeurl", "!pragma", "@startuml", "@enduml", "skinparam")


def _escape(value: str) -> str:
    lowered = value.lower()
    if any(fragment in lowered for fragment in _FORBIDDEN):
        raise ValueError("PlantUML directive fragment forbidden in visual label")
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def _safe_alias(domain: bytes, value: str) -> str:
    return "n_" + sha256(domain + value.encode("utf-8")).hexdigest()[:32]


def _status_legend_lines(model: VisualProjectionModel) -> list[str]:
    lines = ["legend", "Status is explicit text; color is never authoritative."]
    lines.extend(f"{_escape(entry.marker)} {_escape(entry.status)}" for entry in model.legend)
    lines.append("endlegend")
    return lines


def serialize_full_architecture_plantuml(model: VisualProjectionModel) -> bytes:
    model.validate()
    lines = [
        "@startuml",
        "top to bottom direction",
        f"' source_tree={model.source_tree_sha}",
        f"' architecture_model_digest={model.architecture_model_digest}",
    ]
    nodes_by_plane = {plane.plane: [] for plane in model.planes}
    for node in model.nodes:
        nodes_by_plane[node.plane].append(node)
    for plane in model.planes:
        alias = _safe_alias(b"LION/UML/VISUAL-PLANE/1\0", plane.plane)
        lines.append(f'package "{plane.rank + 1:02d} {_escape(plane.plane)}" as {alias} {{')
        for node in sorted(nodes_by_plane[plane.plane]):
            provenance = node.source_path if node.source_path else node.target_ref
            label = f"{node.marker} {node.label}\\n{node.status}\\n{provenance}"
            lines.append(f'  component "{_escape(label)}" as {node.node_id}')
        lines.append("}")
    lines.append("package \"IMPLEMENTATION GAP OVERLAY\" {")
    for gap in model.gaps:
        alias = _safe_alias(b"LION/UML/VISUAL-GAP/1\0", gap.target_id)
        label = f"{gap.marker} {gap.target_id}\\n{gap.status}\\n{gap.summary}"
        lines.append(f'  component "{_escape(label)}" as {alias}')
    lines.append("}")
    lines.extend(_status_legend_lines(model))
    lines.extend([
        "note bottom",
        "Derived projection only; no runtime proof, authority, or permission is created.",
        "AS-IS and TARGET are evidence statuses over one canonical model.",
        "end note",
        "@enduml",
        "",
    ])
    return "\n".join(lines).encode("utf-8")


def serialize_flow_atlas_plantuml(model: VisualProjectionModel) -> tuple[tuple[str, bytes], ...]:
    model.validate()
    outputs = []
    for flow in model.flows:
        lines = [
            "@startuml",
            "left to right direction",
            f"' flow={_escape(flow.flow_id)}",
            f"' source_tree={model.source_tree_sha}",
        ]
        aliases = []
        for index, step in enumerate(flow.steps):
            alias = _safe_alias(b"LION/UML/VISUAL-FLOW-STEP/1\0", f"{flow.flow_id}:{index}:{step}")
            aliases.append(alias)
            lines.append(f'component "{index + 1:02d} {_escape(step)}" as {alias}')
        for source, target in zip(aliases, aliases[1:]):
            lines.append(f"{source} --> {target} : canonical-flow-order")
        lines.extend([
            "note bottom",
            "Derived code-flow projection; sequence is canonical model structure, not runtime proof.",
            "end note",
            "@enduml",
            "",
        ])
        outputs.append((flow.flow_id, "\n".join(lines).encode("utf-8")))
    return tuple(outputs)


def serialize_gap_overlay_plantuml(model: VisualProjectionModel) -> bytes:
    model.validate()
    lines = [
        "@startuml",
        "top to bottom direction",
        f"' source_tree={model.source_tree_sha}",
        "package \"IMPLEMENTATION GAP MAP\" {",
    ]
    for gap in model.gaps:
        alias = _safe_alias(b"LION/UML/VISUAL-GAP/1\0", gap.target_id)
        label = f"{gap.marker} {gap.target_id}\\n{gap.status}\\n{gap.summary}"
        lines.append(f'  component "{_escape(label)}" as {alias}')
    lines.append("}")
    lines.extend(_status_legend_lines(model))
    lines.extend([
        "note bottom",
        "Gap status is evidence classification only; UNKNOWN remains UNKNOWN until evidence-bound transition.",
        "end note",
        "@enduml",
        "",
    ])
    return "\n".join(lines).encode("utf-8")

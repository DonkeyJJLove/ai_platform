from __future__ import annotations
from hashlib import sha256
from .model import CanonicalDiagramModel, DiagramProjectionManifest


def build_manifest(*, model:CanonicalDiagramModel, artifact:bytes, plantuml_version:str, plantuml_binary_digest:str, rendering_mode:str) -> DiagramProjectionManifest:
    return DiagramProjectionManifest(
        source_tree_sha=model.source_tree_sha,
        diagram_id=model.diagram_id,
        diagram_source_digest=model.source_digest(),
        plantuml_version=plantuml_version,
        plantuml_binary_digest=plantuml_binary_digest,
        rendering_mode=rendering_mode,
        generated_artifact_digest=sha256(artifact).hexdigest(),
    ).validate()

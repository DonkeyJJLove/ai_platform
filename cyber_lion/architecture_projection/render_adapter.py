from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from typing import Final

from .full_plantuml import (
    serialize_flow_atlas_plantuml,
    serialize_full_architecture_plantuml,
    serialize_gap_overlay_plantuml,
)
from .plantuml import PlantUMLRenderer
from .visual_model import VisualProjectionModel

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){2,3}$")
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
_RENDER_PLAN_DOMAIN = b"LION/UML/VISUAL-RENDER-PLAN/1\0"
_MANIFEST_DOMAIN = b"LION/UML/VISUAL-RENDER-MANIFEST/1\0"
_RENDER_ROOT: Final = "docs/architecture/uml/generated"
_RENDERING_MODE: Final = "LOCAL_OFFLINE"


def _is_local_absolute(value: str) -> bool:
    if value.startswith(("http://", "https://")):
        return False
    return value.startswith("/") or bool(_WINDOWS_ABSOLUTE.match(value))


def _validate_relative_output(path: str, suffix: str) -> None:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or not path.startswith(_RENDER_ROOT + "/"):
        raise ValueError("visual render output path is outside canonical output root")
    if pure.suffix != suffix:
        raise ValueError("visual render output suffix mismatch")


@dataclass(frozen=True, order=True)
class RendererPin:
    executable: str
    version: str
    binary_digest: str

    def validate(self) -> "RendererPin":
        if not self.executable or not _is_local_absolute(self.executable):
            raise ValueError("renderer executable must be a local absolute path")
        if not _VERSION_RE.fullmatch(self.version):
            raise ValueError("renderer version binding invalid")
        if not _SHA64.fullmatch(self.binary_digest):
            raise ValueError("renderer binary digest binding invalid")
        return self

    def renderer(self) -> PlantUMLRenderer:
        self.validate()
        return PlantUMLRenderer(
            executable=self.executable,
            version=self.version,
            binary_digest=self.binary_digest,
        )


@dataclass(frozen=True, order=True)
class VisualRenderArtifactPlan:
    artifact_id: str
    artifact_kind: str
    flow_id: str
    puml_output_path: str
    svg_output_path: str
    manifest_output_path: str
    puml_source_digest: str

    def validate(self) -> "VisualRenderArtifactPlan":
        if not self.artifact_id.strip():
            raise ValueError("visual render artifact id is required")
        if self.artifact_kind not in {"FULL_ARCHITECTURE", "FLOW_ATLAS", "GAP_MAP"}:
            raise ValueError("visual render artifact kind is invalid")
        if self.artifact_kind == "FLOW_ATLAS":
            if not re.fullmatch(r"FLOW-[0-9]{2}", self.flow_id):
                raise ValueError("flow artifact requires canonical flow id")
        elif self.flow_id:
            raise ValueError("non-flow artifact cannot carry flow id")
        _validate_relative_output(self.puml_output_path, ".puml")
        _validate_relative_output(self.svg_output_path, ".svg")
        _validate_relative_output(self.manifest_output_path, ".json")
        if not _SHA64.fullmatch(self.puml_source_digest):
            raise ValueError("PUML source digest invalid")
        return self


@dataclass(frozen=True)
class VisualRenderPlan:
    source_tree_sha: str
    architecture_model_digest: str
    visual_projection_digest: str
    renderer_pin: RendererPin
    artifacts: tuple[VisualRenderArtifactPlan, ...]
    rendering_mode: str = _RENDERING_MODE
    authority_effect: str = "NONE"
    runtime_evidence: str = "NONE"

    def validate(self) -> "VisualRenderPlan":
        if not _SHA40.fullmatch(self.source_tree_sha):
            raise ValueError("render plan source tree binding invalid")
        if not _SHA64.fullmatch(self.architecture_model_digest):
            raise ValueError("render plan architecture model digest invalid")
        if not _SHA64.fullmatch(self.visual_projection_digest):
            raise ValueError("render plan visual projection digest invalid")
        self.renderer_pin.validate()
        if self.rendering_mode != _RENDERING_MODE:
            raise ValueError("only LOCAL_OFFLINE rendering is representable")
        if self.authority_effect != "NONE" or self.runtime_evidence != "NONE":
            raise ValueError("render plan cannot grant authority or prove runtime")
        if len(self.artifacts) != 11:
            raise ValueError("render plan requires full architecture, 9 flows, and gap map")
        if self.artifacts != tuple(sorted(set(self.artifacts))):
            raise ValueError("render artifacts must be sorted unique")
        for artifact in self.artifacts:
            artifact.validate()
        kinds = [artifact.artifact_kind for artifact in self.artifacts]
        if kinds.count("FULL_ARCHITECTURE") != 1 or kinds.count("GAP_MAP") != 1 or kinds.count("FLOW_ATLAS") != 9:
            raise ValueError("render artifact cardinality invalid")
        expected_flows = tuple(f"FLOW-{index:02d}" for index in range(1, 10))
        actual_flows = tuple(sorted(artifact.flow_id for artifact in self.artifacts if artifact.artifact_kind == "FLOW_ATLAS"))
        if actual_flows != expected_flows:
            raise ValueError("render plan requires all 9 canonical flow ids")
        output_paths = []
        for artifact in self.artifacts:
            output_paths.extend((artifact.puml_output_path, artifact.svg_output_path, artifact.manifest_output_path))
        if len(output_paths) != len(set(output_paths)):
            raise ValueError("render output paths must be globally unique")
        return self

    def canonical_bytes(self) -> bytes:
        self.validate()
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def digest(self) -> str:
        return sha256(_RENDER_PLAN_DOMAIN + self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class VisualRenderManifest:
    artifact_id: str
    artifact_kind: str
    flow_id: str
    source_tree_sha: str
    architecture_model_digest: str
    visual_projection_digest: str
    render_plan_digest: str
    puml_source_digest: str
    plantuml_version: str
    plantuml_binary_digest: str
    rendering_mode: str
    puml_output_path: str
    svg_output_path: str
    rendered_artifact_digest: str
    authority_effect: str = "NONE"
    runtime_evidence: str = "NONE"

    def validate(self) -> "VisualRenderManifest":
        if not self.artifact_id.strip() or self.artifact_kind not in {"FULL_ARCHITECTURE", "FLOW_ATLAS", "GAP_MAP"}:
            raise ValueError("visual render manifest identity invalid")
        if self.artifact_kind == "FLOW_ATLAS":
            if not re.fullmatch(r"FLOW-[0-9]{2}", self.flow_id):
                raise ValueError("visual render manifest flow id invalid")
        elif self.flow_id:
            raise ValueError("non-flow manifest cannot carry flow id")
        if not _SHA40.fullmatch(self.source_tree_sha):
            raise ValueError("visual render manifest source tree invalid")
        for value in (
            self.architecture_model_digest,
            self.visual_projection_digest,
            self.render_plan_digest,
            self.puml_source_digest,
            self.plantuml_binary_digest,
            self.rendered_artifact_digest,
        ):
            if not _SHA64.fullmatch(value):
                raise ValueError("visual render manifest digest binding invalid")
        if not _VERSION_RE.fullmatch(self.plantuml_version):
            raise ValueError("visual render manifest version invalid")
        if self.rendering_mode != _RENDERING_MODE:
            raise ValueError("visual render manifest must be LOCAL_OFFLINE")
        _validate_relative_output(self.puml_output_path, ".puml")
        _validate_relative_output(self.svg_output_path, ".svg")
        if self.authority_effect != "NONE" or self.runtime_evidence != "NONE":
            raise ValueError("visual render manifest cannot carry authority or runtime proof")
        return self

    def canonical_bytes(self) -> bytes:
        self.validate()
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def digest(self) -> str:
        return sha256(_MANIFEST_DOMAIN + self.canonical_bytes()).hexdigest()


def _artifact_plan(artifact_id: str, kind: str, flow_id: str, puml: bytes, relative_group: str = "") -> VisualRenderArtifactPlan:
    base = f"{_RENDER_ROOT}/{relative_group}" if relative_group else _RENDER_ROOT
    stem = artifact_id
    return VisualRenderArtifactPlan(
        artifact_id=artifact_id,
        artifact_kind=kind,
        flow_id=flow_id,
        puml_output_path=f"{base}/{stem}.puml",
        svg_output_path=f"{base}/{stem}.svg",
        manifest_output_path=f"{_RENDER_ROOT}/manifests/{stem}.manifest.json",
        puml_source_digest=sha256(puml).hexdigest(),
    ).validate()


def build_visual_render_plan(model: VisualProjectionModel, renderer_pin: RendererPin) -> VisualRenderPlan:
    model.validate()
    renderer_pin.validate()
    full_puml = serialize_full_architecture_plantuml(model)
    flow_pumls = serialize_flow_atlas_plantuml(model)
    gap_puml = serialize_gap_overlay_plantuml(model)
    artifacts = [
        _artifact_plan("lion-full-architecture", "FULL_ARCHITECTURE", "", full_puml),
        _artifact_plan("lion-implementation-gap-map", "GAP_MAP", "", gap_puml),
    ]
    for flow_id, puml in flow_pumls:
        artifacts.append(
            _artifact_plan(
                f"lion-{flow_id.lower()}",
                "FLOW_ATLAS",
                flow_id,
                puml,
                "flows",
            )
        )
    plan = VisualRenderPlan(
        source_tree_sha=model.source_tree_sha,
        architecture_model_digest=model.architecture_model_digest,
        visual_projection_digest=model.digest(),
        renderer_pin=renderer_pin,
        artifacts=tuple(sorted(artifacts)),
    )
    return plan.validate()


def build_visual_render_manifest(
    *,
    plan: VisualRenderPlan,
    artifact_id: str,
    rendered_artifact: bytes,
) -> VisualRenderManifest:
    plan.validate()
    if not isinstance(rendered_artifact, bytes) or not rendered_artifact:
        raise ValueError("rendered artifact bytes are required")
    matches = [artifact for artifact in plan.artifacts if artifact.artifact_id == artifact_id]
    if len(matches) != 1:
        raise ValueError("render artifact identity must resolve exactly once")
    artifact = matches[0]
    return VisualRenderManifest(
        artifact_id=artifact.artifact_id,
        artifact_kind=artifact.artifact_kind,
        flow_id=artifact.flow_id,
        source_tree_sha=plan.source_tree_sha,
        architecture_model_digest=plan.architecture_model_digest,
        visual_projection_digest=plan.visual_projection_digest,
        render_plan_digest=plan.digest(),
        puml_source_digest=artifact.puml_source_digest,
        plantuml_version=plan.renderer_pin.version,
        plantuml_binary_digest=plan.renderer_pin.binary_digest,
        rendering_mode=plan.rendering_mode,
        puml_output_path=artifact.puml_output_path,
        svg_output_path=artifact.svg_output_path,
        rendered_artifact_digest=sha256(rendered_artifact).hexdigest(),
    ).validate()

from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import subprocess
import tempfile
from .model import CanonicalDiagramModel

_VERSION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){2,3}$")
_VERSION_TOKEN_RE = re.compile(r"(?m)^PlantUML version ([0-9]+(?:\.[0-9]+){2,3})\s*$")
_FORBIDDEN_LABEL_FRAGMENTS = ("!include", "!includeurl", "!pragma", "@startuml", "@enduml", "skinparam")


def _escape(value: str) -> str:
    lowered = value.lower()
    if any(fragment in lowered for fragment in _FORBIDDEN_LABEL_FRAGMENTS):
        raise ValueError("PlantUML directive fragment forbidden in label")
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def _parse_exact_version(output: bytes) -> str:
    text = output.decode("utf-8", "replace")[:8192]
    matches = _VERSION_TOKEN_RE.findall(text)
    if len(matches) != 1:
        raise RuntimeError("PlantUML version output ambiguous")
    return matches[0]


def serialize_plantuml(model: CanonicalDiagramModel) -> bytes:
    model.validate()
    lines = ["@startuml", f"' diagram={_escape(model.diagram_id)}", "skinparam shadowing false"]
    by_id = {node.node_id: node for node in model.nodes}
    for group in model.groups:
        lines.append(f'package "{_escape(group.label)}" as {group.group_id} {{')
        for node_id in group.node_ids:
            node = by_id[node_id]
            lines.append(f'  component "{_escape(node.label)}" as {node.node_id}')
        lines.append("}")
    grouped = {node_id for group in model.groups for node_id in group.node_ids}
    for node in model.nodes:
        if node.node_id not in grouped:
            lines.append(f'component "{_escape(node.label)}" as {node.node_id}')
    for edge in model.edges:
        label = _escape(edge.relation + ((" / " + edge.label) if edge.label else ""))
        lines.append(f"{edge.source} --> {edge.target} : {label}")
    lines += [
        "note bottom",
        "Derived projection only; not authority, currentness, runtime evidence, or CI proof.",
        "end note",
        "@enduml",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


@dataclass(frozen=True)
class PlantUMLRenderer:
    executable: str | None = None
    version: str | None = None
    binary_digest: str | None = None
    timeout_seconds: int = 20
    max_input_bytes: int = 2_000_000
    max_output_bytes: int = 10_000_000

    def _argv(self, path: Path, *args: str):
        return ["java", "-jar", str(path), *args] if path.suffix.lower() == ".jar" else [str(path), *args]

    def validate_configuration(self):
        if not self.executable or not self.version or not self.binary_digest:
            raise RuntimeError("PlantUML renderer is disabled until explicitly pinned")
        if not _VERSION_RE.fullmatch(self.version):
            raise RuntimeError("PlantUML version binding invalid")
        if self.executable.startswith(("http://", "https://")):
            raise RuntimeError("network PlantUML renderer forbidden")
        path = Path(self.executable)
        if not path.is_absolute() or not path.is_file():
            raise RuntimeError("pinned PlantUML executable unavailable")
        if len(self.binary_digest) != 64 or any(c not in "0123456789abcdef" for c in self.binary_digest):
            raise RuntimeError("PlantUML digest invalid")
        actual = sha256(path.read_bytes()).hexdigest()
        if actual != self.binary_digest:
            raise RuntimeError("PlantUML binary digest mismatch")
        probe = subprocess.run(
            self._argv(path, "-version"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=self.timeout_seconds,
            check=False,
            shell=False,
        )
        if probe.returncode != 0:
            raise RuntimeError("PlantUML version probe failed")
        parsed = _parse_exact_version(probe.stdout)
        if parsed != self.version:
            raise RuntimeError("PlantUML version mismatch")
        return path

    def render_svg(self, puml: bytes) -> bytes:
        if not isinstance(puml, bytes) or not puml or len(puml) > self.max_input_bytes:
            raise RuntimeError("PlantUML input invalid")
        path = self.validate_configuration()
        with tempfile.TemporaryDirectory(prefix="lion-uml-") as directory:
            root = Path(directory)
            source = root / "diagram.puml"
            source.write_bytes(puml)
            argv = self._argv(path, "-tsvg", "-charset", "UTF-8", str(source))
            completed = subprocess.run(
                argv,
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds,
                check=False,
                shell=False,
            )
            if completed.returncode != 0:
                raise RuntimeError("PlantUML render failed")
            output = root / "diagram.svg"
            if not output.is_file():
                raise RuntimeError("PlantUML output missing")
            data = output.read_bytes()
            if not data or len(data) > self.max_output_bytes:
                raise RuntimeError("PlantUML output invalid")
            return data

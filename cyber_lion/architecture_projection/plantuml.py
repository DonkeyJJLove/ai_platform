from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import subprocess, tempfile
from .model import CanonicalDiagramModel


def _escape(value:str)->str: return value.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')

def serialize_plantuml(model: CanonicalDiagramModel) -> bytes:
    model.validate()
    lines=["@startuml",f"' diagram={model.diagram_id}","skinparam shadowing false"]
    for group in model.groups:
        lines.append(f'package "{_escape(group.label)}" as {group.group_id} {{')
        for nid in group.node_ids:
            n=next(x for x in model.nodes if x.node_id==nid); lines.append(f'  component "{_escape(n.label)}" as {n.node_id}')
        lines.append("}")
    grouped={nid for g in model.groups for nid in g.node_ids}
    for n in model.nodes:
        if n.node_id not in grouped: lines.append(f'component "{_escape(n.label)}" as {n.node_id}')
    for e in model.edges:
        label=f' : {_escape(e.relation + (" / "+e.label if e.label else ""))}'
        lines.append(f"{e.source} --> {e.target}{label}")
    lines += ["note bottom", "Derived projection only; not authority, currentness, runtime evidence, or CI proof.", "end note", "@enduml", ""]
    return "\n".join(lines).encode("utf-8")

@dataclass(frozen=True)
class PlantUMLRenderer:
    executable: str | None = None
    version: str | None = None
    binary_digest: str | None = None
    timeout_seconds: int = 20
    max_input_bytes: int = 2_000_000
    max_output_bytes: int = 10_000_000
    def validate_configuration(self):
        if not self.executable or not self.version or not self.binary_digest: raise RuntimeError("PlantUML renderer is disabled until explicitly pinned")
        if self.executable.startswith(("http://","https://")): raise RuntimeError("network PlantUML renderer forbidden")
        path=Path(self.executable)
        if not path.is_absolute() or not path.is_file(): raise RuntimeError("pinned PlantUML executable unavailable")
        actual=sha256(path.read_bytes()).hexdigest()
        if actual!=self.binary_digest: raise RuntimeError("PlantUML binary digest mismatch")
        if len(self.binary_digest)!=64: raise RuntimeError("PlantUML digest invalid")
        return path
    def render_svg(self, puml: bytes) -> bytes:
        if len(puml)>self.max_input_bytes: raise RuntimeError("PlantUML input too large")
        path=self.validate_configuration()
        with tempfile.TemporaryDirectory(prefix="lion-uml-") as d:
            root=Path(d); source=root/"diagram.puml"; source.write_bytes(puml)
            if path.suffix.lower()==".jar": argv=["java","-jar",str(path),"-tsvg","-charset","UTF-8",str(source)]
            else: argv=[str(path),"-tsvg","-charset","UTF-8",str(source)]
            completed=subprocess.run(argv,cwd=root,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=self.timeout_seconds,check=False,shell=False)
            if completed.returncode!=0: raise RuntimeError("PlantUML render failed")
            out=root/"diagram.svg"
            if not out.is_file(): raise RuntimeError("PlantUML output missing")
            data=out.read_bytes()
            if not data or len(data)>self.max_output_bytes: raise RuntimeError("PlantUML output invalid")
            return data

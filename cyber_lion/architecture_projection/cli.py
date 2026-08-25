from __future__ import annotations
import argparse, json
from pathlib import Path
from .extractor import ArchitectureProjectionExtractor, available_projection_names
from .manifest import build_manifest
from .plantuml import PlantUMLRenderer, serialize_plantuml


def _parser():
    p=argparse.ArgumentParser(prog="lion-uml")
    p.add_argument("--source-tree",required=True)
    p.add_argument("--diagram",choices=available_projection_names(),required=True)
    p.add_argument("--puml-out",required=True)
    p.add_argument("--svg-out")
    p.add_argument("--plantuml")
    p.add_argument("--plantuml-version")
    p.add_argument("--plantuml-sha256")
    return p

def main(argv=None):
    args=_parser().parse_args(argv)
    model=ArchitectureProjectionExtractor(source_tree_sha=args.source_tree).named_projection(args.diagram)
    puml=serialize_plantuml(model); Path(args.puml_out).write_bytes(puml)
    mode="PUML_ONLY"; artifact=puml; version=args.plantuml_version or "UNRENDERED"; digest=args.plantuml_sha256 or ("0"*64)
    if args.svg_out:
        renderer=PlantUMLRenderer(args.plantuml,args.plantuml_version,args.plantuml_sha256)
        artifact=renderer.render_svg(puml); Path(args.svg_out).write_bytes(artifact); mode="LOCAL_OFFLINE"
    manifest=build_manifest(model=model,artifact=artifact,plantuml_version=version,plantuml_binary_digest=digest,rendering_mode=mode)
    print(json.dumps(manifest.__dict__,sort_keys=True,separators=(",",":")))
    return 0

if __name__=="__main__": raise SystemExit(main())

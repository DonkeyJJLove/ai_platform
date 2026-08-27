"""Conservative code-observed consequential-effect inventory and mediation assessment.

The scanner intentionally prefers false-positive UNKNOWN over false completeness.  It
operates on exact source bytes supplied by the caller/CI and never treats architecture
projections or documentation as runtime proof.
"""
from __future__ import annotations
import ast
from hashlib import sha256
import json,re
from typing import Mapping,Tuple

from cyber_lion.contracts.complete_mediation import (
    CompleteMediationAssessment,CompleteMediationMatrixEntry,ConsequentialEffectSurface,
    EffectSurfaceInventory,MediationBinding,
)

class CompleteMediationError(RuntimeError):pass

_CALL_CLASSES={
    "subprocess.run":"runtime.tool_execution","subprocess.Popen":"runtime.process_launch",
    "os.system":"runtime.tool_execution","os.execv":"runtime.process_launch","os.execve":"runtime.process_launch",
    "Path.write_text":"filesystem.write","Path.write_bytes":"filesystem.write",
    "os.unlink":"filesystem.delete","os.rmdir":"filesystem.delete","os.remove":"filesystem.delete",
    "os.replace":"filesystem.replace","os.rename":"filesystem.rename",
    "urlopen":"external.network","requests.post":"external.network","requests.put":"external.network",
    "requests.patch":"external.network","requests.delete":"external.network",
}
_SUSPICIOUS_TOKENS=re.compile(r"(?:execute|launch|mutat|update|create|delete|attach|merge|dispatch|write|publish|release|deploy|subprocess|urlopen)",re.I)
_MUTATING_SQL=re.compile(r"^\s*(INSERT|UPDATE|DELETE|REPLACE|CREATE|DROP|ALTER|VACUUM|PRAGMA\s+[^;=]+\s*=)",re.I)


def _call_name(node:ast.Call)->str:
    def q(n):
        if isinstance(n,ast.Name):return n.id
        if isinstance(n,ast.Attribute):
            left=q(n.value);return f"{left}.{n.attr}" if left else n.attr
        return ""
    return q(node.func)

def _literal(node):
    return node.value if isinstance(node,ast.Constant) and isinstance(node.value,str) else None

def _surface(path:str,line:int,call:str,effect_class:str)->ConsequentialEffectSurface:
    ref=f"{path}:{line}:{call}"
    provider=path.replace("/",".")
    if effect_class.startswith("external.network") or effect_class in {"repository_ref.delete","workflow.external_effect"}:
        target="external"; authority="external_write"
    elif effect_class.startswith("filesystem"):
        target="filesystem"; authority="local_write"
    else:
        target="runtime"; authority="local_write"
    return ConsequentialEffectSurface(
        surface_id="surface:"+sha256(ref.encode()).hexdigest()[:24],effect_class=effect_class,
        implementation_refs=(path,),entrypoints=(ref,),effect_provider=provider,target_class=target,
        mutation_kind=call,authority_class=authority,currentness_requirement="exact-pre-effect-currentness",
        pep_required=True,observer_required=True,reconciliation_required=True,evidence_refs=(ref,),epistemic_state="OBSERVED",
    ).validate()

class EffectSurfaceScanner:
    def scan(self,*,repository:str,revision:str,tree_digest:str,sources:Mapping[str,str])->EffectSurfaceInventory:
        if not isinstance(sources,Mapping) or not sources:raise CompleteMediationError("exact source mapping required")
        surfaces=[];unclassified=[];scan_items=[]
        for path in sorted(sources):
            source=sources[path]
            if not isinstance(path,str) or not isinstance(source,str):raise CompleteMediationError("source mapping must be text")
            if "/tests/" in f"/{path}" or path.endswith((".md",".rst",".txt")):continue
            scan_items.append((path,sha256(source.encode("utf-8")).hexdigest()))
            if path.endswith(".py"):
                try:tree=ast.parse(source,filename=path)
                except SyntaxError:
                    unclassified.append(f"{path}:syntax-error");continue
                for node in ast.walk(tree):
                    if not isinstance(node,ast.Call):continue
                    name=_call_name(node); short=name.split(".")[-1]; effect=None
                    if name == "urllib.request.Request" or name.endswith(".request.Request"):
                        method = next((_literal(k.value) for k in node.keywords if k.arg == "method"), None)
                        if method is None and len(node.args) >= 3: method = _literal(node.args[2])
                        if isinstance(method, str):
                            upper = method.upper()
                            if upper in {"POST", "PUT", "PATCH", "DELETE"}: effect = f"external.network.{upper.lower()}"
                        else:
                            unclassified.append(f"{path}:{getattr(node,'lineno',0)}:{name}:dynamic-http-method")
                    if effect is None and name in _CALL_CLASSES:effect=_CALL_CLASSES[name]
                    elif short in {"write_text","write_bytes"}:effect="filesystem.write"
                    elif short in {"urlopen"}:effect="external.network"
                    elif short=="request" and name.endswith("connection.request"):effect="external.network.authority_observation"
                    elif short=="delete_exact_branch_ref":effect="repository_ref.delete"
                    elif short in {"execute","executemany"} and node.args:
                        receiver = name.rsplit(".",1)[0] if "." in name else ""
                        dbish = bool(re.search(r"(?:^|\.)(?:c|cur|conn|connection|cursor|db|_conn)$", receiver))
                        if dbish:
                            sql=_literal(node.args[0])
                            if sql is not None and _MUTATING_SQL.search(sql):effect="persistent_state.write"
                            elif sql is None:unclassified.append(f"{path}:{getattr(node,'lineno',0)}:{name}:dynamic-sql")
                    elif short in {"unlink","rmdir"}:
                        receiver=name.rsplit(".",1)[0] if "." in name else ""
                        if re.search(r"(?:path|file|target|temp|source|destination|artifact|receipt|registry|manifest)$", receiver, re.I):
                            effect="filesystem.delete"
                    elif short in {"replace","rename"}:
                        receiver=name.rsplit(".",1)[0] if "." in name else ""
                        if re.search(r"(?:path|file|target|temp|source|destination|artifact|receipt|registry|manifest)$", receiver, re.I):
                            effect="filesystem.replace" if short=="replace" else "filesystem.rename"
                    elif short=="open":
                        mode=_literal(node.args[1]) if len(node.args)>1 else next((_literal(k.value) for k in node.keywords if k.arg=="mode"),None)
                        if mode and any(x in mode for x in "wax+"):effect="filesystem.write"
                    elif _SUSPICIOUS_TOKENS.search(name) and any(x in name.lower() for x in ("backend.","provider.","transport.","client.")):
                        unclassified.append(f"{path}:{getattr(node,'lineno',0)}:{name}")
                    if effect:surfaces.append(_surface(path,getattr(node,"lineno",0),name,effect))
            elif path.endswith((".yml",".yaml")) and path.startswith(".github/workflows/"):
                lines = source.splitlines()
                for i,line in enumerate(lines,1):
                    stripped=line.strip(); low=stripped.lower()
                    if "workflow_dispatch:" in low: continue
                    if "grep -q" not in low and re.search(r"\b(gh\s+(api|pr|release|workflow)|git\s+push|curl\b.*\s-x\s*(post|put|patch|delete))",low):
                        surfaces.append(_surface(path,i,stripped,"workflow.external_effect"))
                    if re.search(r"\binvoke-restmethod\b.*\s-method\s+(post|put|patch|delete)\b",low):
                        surfaces.append(_surface(path,i,stripped,"workflow.external_effect"))
                    # Embedded bootstrap code is still effectful. Keep it visible instead of
                    # silently treating runner-temp materialization as orchestration metadata.
                    if path.endswith("moon-file-write.yml"):
                        if ".mkdir(" in stripped:
                            surfaces.append(_surface(path,i,stripped,"filesystem.bootstrap.mkdir"))
                        if ".write_text(" in stripped or ".write_bytes(" in stripped or "| tee " in low:
                            surfaces.append(_surface(path,i,stripped,"filesystem.bootstrap.write"))
        uniq={s.surface_id:s for s in surfaces}
        canonical_scan=json.dumps(scan_items,sort_keys=True,separators=(",",":")).encode()
        scan_digest=sha256(b"LION/EFFECT-SURFACE-SCAN/1\0"+canonical_scan).hexdigest()
        return EffectSurfaceInventory(repository,revision,tree_digest,scan_digest,tuple(uniq[k] for k in sorted(uniq)),tuple(sorted(set(unclassified))),
            (f"source-count:{len(scan_items)}",f"surface-count:{len(uniq)}",f"unclassified-count:{len(set(unclassified))}")).validate()

class CompleteMediationEngine:
    """Assessment is fail-closed: absence of exact observed binding remains UNKNOWN."""
    def assess(self,*,inventory:EffectSurfaceInventory,bindings:Tuple[MediationBinding,...],falsification_evidence_refs:Tuple[str,...],observation_evidence_refs:Tuple[str,...])->CompleteMediationAssessment:
        inventory.validate(); by_surface={}
        for b in bindings:
            b.validate()
            if b.surface_digest in by_surface:raise CompleteMediationError("ambiguous mediation binding")
            by_surface[b.surface_digest]=b
        matrix=[]
        for s in inventory.surfaces:
            sd=s.digest();binding=by_surface.get(sd)
            if binding is None:
                matrix.append(CompleteMediationMatrixEntry(sd,"UNKNOWN","","no exact observed mediation binding",s.evidence_refs).validate())
            else:
                matrix.append(CompleteMediationMatrixEntry(sd,"MEDIATED",binding.digest(),"exact authority/currentness/PEP/execution/observer/reconciliation binding supplied",binding.evidence_refs).validate())
        known={s.digest() for s in inventory.surfaces}
        if set(by_surface)-known:raise CompleteMediationError("binding references surface outside exact inventory")
        complete=bool(matrix) and not inventory.unclassified_refs and all(e.status=="MEDIATED" for e in matrix) and bool(falsification_evidence_refs) and bool(observation_evidence_refs)
        return CompleteMediationAssessment(inventory.digest(),tuple(matrix),"PASS" if complete else "UNKNOWN",falsification_evidence_refs,observation_evidence_refs).validate()

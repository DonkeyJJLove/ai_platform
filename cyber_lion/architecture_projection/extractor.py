from __future__ import annotations
import ast
from dataclasses import replace
from pathlib import PurePosixPath
from .model import CanonicalDiagramModel, DiagramNode, DiagramEdge, DiagramGroup

_PROJECTIONS = (
    "lion-system-component-map",
    "authority-and-effect-chain-R17-R22",
    "builder-lifecycle-state-machine",
    "persistent-authority-store-model",
    "fleet-topology",
    "evolutionary-epoch-loop",
    "startup-agent-evolution-loop",
    "repository-mutation-boundaries",
    "event-and-causality-map",
    "capability-map",
)

def available_projection_names() -> tuple[str,...]: return _PROJECTIONS

def _id(text:str)->str:
    return "n_"+"".join(c if c.isalnum() else "_" for c in text).strip("_")

class ArchitectureProjectionExtractor:
    """Static-only extractor. Import/call relations are evidence, never authority/runtime proof."""
    def __init__(self, *, source_tree_sha: str): self.source_tree_sha=source_tree_sha

    def extract_python(self, files: dict[str,str], *, diagram_id="lion-system-component-map") -> CanonicalDiagramModel:
        nodes={}; edges=set()
        for path, text in sorted(files.items()):
            p=PurePosixPath(path)
            if p.suffix!=".py": continue
            mid=_id(path); nodes[mid]=DiagramNode(mid,path,"module",path)
            try: tree=ast.parse(text,filename=path)
            except SyntaxError:
                uid=_id(path+":UNKNOWN"); nodes[uid]=DiagramNode(uid,"UNKNOWN_PARSE","unknown",path)
                edges.add(DiagramEdge(mid,uid,"UNKNOWN","parse-failure")); continue
            for item in ast.walk(tree):
                if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                    sid=_id(f"{path}:{item.name}"); nodes[sid]=DiagramNode(sid,item.name,type(item).__name__,path); edges.add(DiagramEdge(mid,sid,"CONTAINS"))
                elif isinstance(item,ast.Import):
                    for alias in item.names:
                        tid=_id("module:"+alias.name); nodes.setdefault(tid,DiagramNode(tid,alias.name,"external-module")); edges.add(DiagramEdge(mid,tid,"IMPORTS"))
                elif isinstance(item,ast.ImportFrom) and item.module:
                    tid=_id("module:"+item.module); nodes.setdefault(tid,DiagramNode(tid,item.module,"external-module")); edges.add(DiagramEdge(mid,tid,"IMPORTS"))
        return CanonicalDiagramModel(diagram_id,"component",self.source_tree_sha,tuple(sorted(nodes.values())),tuple(sorted(edges))).validate()

    def named_projection(self, name:str) -> CanonicalDiagramModel:
        if name not in _PROJECTIONS: raise ValueError("unknown projection")
        if name=="authority-and-effect-chain-R17-R22":
            labels=("BuilderEntryPermit","BuilderInvocationPermit","BuilderInvocationConsumptionPermit","BuilderStartAdmission","BuilderProcessLaunchBoundary","BuilderProcessCompletionObservation")
            nodes=tuple(DiagramNode(_id(x),x,"capability",authority_semantics="REFERENCE_ONLY" if x!="BuilderProcessLaunchBoundary" else "NONE") for x in labels)
            edges=tuple(DiagramEdge(_id(a),_id(b),"SOURCE_PROVENANCE") for a,b in zip(labels,labels[1:]))
            return CanonicalDiagramModel(name,"sequence",self.source_tree_sha,nodes,edges).validate()
        if name=="builder-lifecycle-state-machine":
            labels=("ADMITTED","HELD_NOT_EXECUTING_BUILDER","STARTED_OBSERVED","COMPLETION_UNOBSERVED")
            nodes=tuple(DiagramNode(_id(x),x,"state") for x in labels)
            edges=(DiagramEdge(_id(labels[0]),_id(labels[1]),"EFFECT_BOUNDARY","prepare"),DiagramEdge(_id(labels[1]),_id(labels[2]),"EFFECT_BOUNDARY","commit_start"),DiagramEdge(_id(labels[2]),_id(labels[3]),"UNKNOWN","next-frontier"))
            return CanonicalDiagramModel(name,"state",self.source_tree_sha,nodes,tuple(sorted(edges))).validate()
        if name=="evolutionary-epoch-loop":
            labels=("observe","hypothesize","falsify","promote","next-epoch")
            nodes=tuple(DiagramNode(_id(x),x,"epoch-stage") for x in labels)
            edges=tuple(DiagramEdge(_id(a),_id(b),"EPOCH_TRANSITION") for a,b in zip(labels,labels[1:]+labels[:1]))
            return CanonicalDiagramModel(name,"state",self.source_tree_sha,nodes,tuple(sorted(edges))).validate()
        if name=="fleet-topology":
            labels=("SwarmGovernor","Formation","Drone","Verifier")
            nodes=tuple(DiagramNode(_id(x),x,"fleet") for x in labels)
            edges=(DiagramEdge(_id("SwarmGovernor"),_id("Formation"),"FLEET_MEMBERSHIP"),DiagramEdge(_id("Formation"),_id("Drone"),"FLEET_MEMBERSHIP"),DiagramEdge(_id("Formation"),_id("Verifier"),"FLEET_MEMBERSHIP"))
            return CanonicalDiagramModel(name,"deployment",self.source_tree_sha,nodes,tuple(sorted(edges))).validate()
        labels={
          "persistent-authority-store-model":("SQLiteAuthorityStateStore","launch_intent","held_materialization","launch_receipt"),
          "startup-agent-evolution-loop":("Explore","Experiment","Build","Learn"),
          "repository-mutation-boundaries":("CandidateObservation","CandidateAdmission","RepositoryMutationPEP"),
          "event-and-causality-map":("EventEnvelope","GateRequested","GateApplied","ExecutionReceipt"),
          "capability-map":("READ_ONLY","LOCAL_WRITE","BUILDER_PROCESS_START","REPOSITORY_REF_MUTATION"),
          "lion-system-component-map":("contracts","enterprise","fleet","startup_agent","evolutionary_epoch"),
        }[name]
        nodes=tuple(DiagramNode(_id(x),x,"component") for x in labels)
        relation={"persistent-authority-store-model":"PERSISTENCE_BINDING","event-and-causality-map":"EVENT_CAUSALITY","startup-agent-evolution-loop":"EPOCH_TRANSITION"}.get(name,"CONTAINS")
        edges=tuple(DiagramEdge(_id(a),_id(b),relation) for a,b in zip(labels,labels[1:]))
        return CanonicalDiagramModel(name,"component",self.source_tree_sha,nodes,tuple(sorted(edges))).validate()

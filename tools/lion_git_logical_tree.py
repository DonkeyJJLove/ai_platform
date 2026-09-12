"""Deterministic Git logical-spine generator and checked-in snapshot validator.

V3 separates Git repository facts from explicit external observations.  The
checked-in snapshot is intentionally bound to the exact noncarrier HEAD that
existed before the snapshot file itself was committed; validation therefore
requires that generated_from_head remains an ancestor of the checkout rather
than pretending a Git object can contain its own future commit id.
"""
from __future__ import annotations
from hashlib import sha256
import argparse,json,re,subprocess
from pathlib import Path

DOMAIN=b"LION/GIT-LOGICAL-TREE/3\0"
HEX40=re.compile(r"^[0-9a-f]{40}$")
SCHEMA="lion.git-logical-tree/v3"
FACTS_SCHEMA="lion.git-logical-tree-external-facts/v2"

class GitLogicalTreeError(ValueError): pass

def _git(root,*args,required=True):
    p=subprocess.run(["git","-C",str(root),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if p.returncode:
        if required: raise GitLogicalTreeError("git read failed: "+" ".join(args))
        return None
    return p.stdout.decode("utf-8","strict").strip()

def _sha40(v,label):
    if type(v) is not str or HEX40.fullmatch(v) is None: raise GitLogicalTreeError(label)
    return v

def _opt_sha40(v,label):
    if v is None:return None
    return _sha40(v,label)

def _text(v,label):
    if type(v) is not str or not v.strip() or "\0" in v: raise GitLogicalTreeError(label)
    return v

def _opt_text(v,label):
    if v is None:return None
    return _text(v,label)

def _canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def _parents(root,head):
    raw=_git(root,"show","-s","--format=%P",head) or ""
    out=raw.split()
    for p in out:_sha40(p,"parent")
    return out

def _commit_node(root,head,ref,currentness):
    head=_sha40(head,"commit head"); tree=_sha40(_git(root,"rev-parse",head+"^{tree}"),"commit tree")
    msg=_git(root,"show","-s","--format=%s",head)
    return {"node_id":"git:"+head[:12],"node_type":"LOCAL_EVOLUTION_COMMIT","repository":None,
            "ref":ref,"head":head,"tree":tree,"parent_heads":_parents(root,head),"currentness":currentness,
            "integration_state":"LOCAL_UNPUBLISHED","authority_state":"NONE_BY_THIS_NODE","runtime_state":"NOT_DEPLOYED",
            "truth_subject":None,"rag_release":None,"evidence_refs":["git-object:"+head],"supersedes":[],"superseded_by":[],
            "observed_at":None,"notes":msg}

def _load_facts(path):
    if path is None:return [],[]
    v=json.loads(Path(path).read_text(encoding="utf-8"))
    if type(v) is not dict or set(v)!={"schema","nodes","edges"} or v["schema"]!=FACTS_SCHEMA:raise GitLogicalTreeError("external facts schema")
    if type(v["nodes"]) is not list or type(v["edges"]) is not list:raise GitLogicalTreeError("external facts collections")
    allowed={"node_id","node_type","repository","ref","head","tree","parent_heads","currentness","integration_state","authority_state","runtime_state","truth_subject","rag_release","evidence_refs","supersedes","superseded_by","observed_at","notes"}
    nodes=[]
    for n in v["nodes"]:
        if type(n) is not dict or set(n)!=allowed:raise GitLogicalTreeError("external fact fields")
        _text(n["node_id"],"node id");_text(n["node_type"],"node type");_opt_sha40(n["head"],"head");_opt_sha40(n["tree"],"tree")
        _opt_text(n["repository"],"repository");_opt_text(n["ref"],"ref");_text(n["currentness"],"currentness");_text(n["integration_state"],"integration state")
        if n["authority_state"]!="NONE_BY_THIS_NODE":raise GitLogicalTreeError("external facts cannot grant authority")
        _text(n["runtime_state"],"runtime state")
        for key in ("parent_heads","evidence_refs","supersedes","superseded_by"):
            if type(n[key]) is not list or any(type(x) is not str or not x for x in n[key]):raise GitLogicalTreeError(key)
        if not n["evidence_refs"]:raise GitLogicalTreeError("evidence refs")
        nodes.append(n)
    edges=[]
    for e in v["edges"]:
        if type(e) is not dict or set(e)!={"source","relation","target"}:raise GitLogicalTreeError("external edge fields")
        for k in ("source","relation","target"):_text(e[k],k)
        edges.append(e)
    return nodes,edges

def _digest_core(core):return sha256(DOMAIN+_canonical(core)).hexdigest()

def generate(root,external_facts=None):
    root=Path(root).resolve()
    if _git(root,"rev-parse","--is-inside-work-tree")!="true":raise GitLogicalTreeError("Git worktree required")
    head=_sha40(_git(root,"rev-parse","HEAD^{commit}"),"head"); head_tree=_sha40(_git(root,"rev-parse","HEAD^{tree}"),"head tree")
    repo_name=_git(root,"config","--get","remote.origin.url",required=False) or root.name
    if repo_name.endswith('.git'):repo_name=repo_name[:-4]
    if 'github.com/' in repo_name:repo_name=repo_name.split('github.com/',1)[1]
    master_ref="refs/remotes/origin/master"; master_head=_git(root,"rev-parse",master_ref+"^{commit}",required=False)
    nodes=[];edges=[]
    if master_head:
        master_head=_sha40(master_head,"master head"); master_tree=_sha40(_git(root,"rev-parse",master_head+"^{tree}"),"master tree")
        nodes.append({"node_id":"git:master","node_type":"REMOTE_MASTER","repository":repo_name,"ref":"master","head":master_head,"tree":master_tree,
          "parent_heads":_parents(root,master_head),"currentness":"CURRENT_REMOTE_TRACKING_EXACT","integration_state":"MERGED","authority_state":"NONE_BY_THIS_NODE",
          "runtime_state":"REPOSITORY_ONLY","truth_subject":None,"rag_release":None,"evidence_refs":["git-object:"+master_head],"supersedes":[],"superseded_by":[],"observed_at":None,"notes":"Remote-tracking snapshot; network currentness must be reacquired separately."})
        if _git(root,"merge-base","--is-ancestor",master_head,head,required=False) is None:raise GitLogicalTreeError("local HEAD not descendant of tracked master")
        revs=(_git(root,"rev-list","--reverse",master_head+".."+head) or "").splitlines()
    else:revs=[head]
    for i,h in enumerate(revs):
        n=_commit_node(root,h,_git(root,"branch","--show-current",required=False),"CURRENT_LOCAL_LINEAGE" if h==head else "HISTORICAL_LOCAL_ANCESTOR")
        n["repository"]=repo_name;nodes.append(n)
    id_by_head={n["head"]:n["node_id"] for n in nodes if n.get("head")}
    for n in nodes:
        if n["node_type"]!="LOCAL_EVOLUTION_COMMIT":continue
        for p in n["parent_heads"]:
            if p in id_by_head:edges.append({"source":id_by_head[p],"relation":"PARENT_OF","target":n["node_id"]})
    ext_nodes,ext_edges=_load_facts(external_facts);nodes.extend(ext_nodes);edges.extend(ext_edges)
    ids=[n["node_id"] for n in nodes]
    if len(ids)!=len(set(ids)):raise GitLogicalTreeError("duplicate node id")
    known=set(ids)
    if any(e["source"] not in known or e["target"] not in known for e in edges):raise GitLogicalTreeError("edge references unknown node")
    nodes.sort(key=lambda n:(n["node_type"],n["node_id"]));edges.sort(key=lambda e:(e["source"],e["relation"],e["target"]))
    core={"schema":SCHEMA,"project":"LION_EVOLUSION","repository":repo_name,"generated_from_head":head,"generated_from_tree":head_tree,
          "snapshot_semantics":"Exact deterministic pre-commit Git snapshot. Later documentation/truth commits are valid descendants; read live carriers for final truth binding.",
          "nodes":nodes,"edges":edges,"invariants":["NO_AUTHORITY_FROM_GRAPH","RUNTIME_IS_SEPARATE_FROM_REPOSITORY","RAG_IS_NOT_LIVE_TRUTH","LOCAL_CURRENT_HEAD_DESCENDS_FROM_TRACKED_MASTER"]}
    return {"graph_digest_domain":"LION/GIT-LOGICAL-TREE/3","graph_digest":_digest_core(core),**core}

def validate_snapshot(root,value):
    root=Path(root).resolve()
    if type(value) is not dict or value.get("graph_digest_domain")!="LION/GIT-LOGICAL-TREE/3" or value.get("schema")!=SCHEMA:raise GitLogicalTreeError("snapshot schema")
    supplied=value.get("graph_digest"); core={k:v for k,v in value.items() if k not in {"graph_digest_domain","graph_digest"}}
    if supplied!=_digest_core(core):raise GitLogicalTreeError("graph digest mismatch")
    h=_sha40(value.get("generated_from_head"),"generated head"); t=_sha40(value.get("generated_from_tree"),"generated tree")
    if _git(root,"cat-file","-t",h,required=False)!="commit":raise GitLogicalTreeError("generated head unavailable")
    if _git(root,"rev-parse",h+"^{tree}")!=t:raise GitLogicalTreeError("generated tree mismatch")
    checkout=_sha40(_git(root,"rev-parse","HEAD^{commit}"),"checkout head")
    if _git(root,"merge-base","--is-ancestor",h,checkout,required=False) is None:raise GitLogicalTreeError("snapshot not ancestor of checkout")
    nodes=value.get("nodes");edges=value.get("edges")
    if type(nodes) is not list or not nodes or type(edges) is not list:raise GitLogicalTreeError("snapshot collections")
    ids=[n.get("node_id") for n in nodes]
    if any(type(x) is not str or not x for x in ids) or len(ids)!=len(set(ids)):raise GitLogicalTreeError("snapshot node ids")
    known=set(ids)
    if any(type(e) is not dict or set(e)!={"source","relation","target"} or e["source"] not in known or e["target"] not in known for e in edges):raise GitLogicalTreeError("snapshot edges")
    for n in nodes:
        if n.get("authority_state")!="NONE_BY_THIS_NODE":raise GitLogicalTreeError("graph authority promotion")
        if n.get("node_type")=="REMOTE_MASTER" and n.get("runtime_state")!="REPOSITORY_ONLY":raise GitLogicalTreeError("repository/runtime substitution")
    return {"valid":True,"graph_digest":supplied,"generated_from_head":h,"checkout_head":checkout,"descendant_distance":int(_git(root,"rev-list","--count",h+".."+checkout) or "0")}

def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument("--repository",default=".");ap.add_argument("--external-facts");ap.add_argument("--validate")
    a=ap.parse_args(argv)
    if a.validate:
        v=json.loads(Path(a.validate).read_text(encoding="utf-8"));print(json.dumps(validate_snapshot(a.repository,v),sort_keys=True,indent=2))
    else:print(json.dumps(generate(a.repository,a.external_facts),sort_keys=True,indent=2,ensure_ascii=False))
if __name__=="__main__":main()

import json,subprocess,tempfile,unittest
from pathlib import Path
from tools.lion_git_logical_tree import GitLogicalTreeError,generate,validate_snapshot

def run(root,*args):subprocess.run(["git","-C",str(root),*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
def repo():
 td=tempfile.TemporaryDirectory();r=Path(td.name);run(r,"init","-q");run(r,"config","user.email","t@example.invalid");run(r,"config","user.name","t");(r/"a").write_text("a");run(r,"add","a");run(r,"commit","-qm","base");h=subprocess.check_output(["git","-C",str(r),"rev-parse","HEAD"]).decode().strip();run(r,"update-ref","refs/remotes/origin/master",h);return td,r
def facts(r,nodes=(),edges=()):
 p=r/"facts.json";p.write_text(json.dumps({"schema":"lion.git-logical-tree-external-facts/v2","nodes":list(nodes),"edges":list(edges)}));return p
def external(node_id="runtime:x"):
 return {"node_id":node_id,"node_type":"RUNTIME_SOURCE","repository":"x/y","ref":None,"head":"1"*40,"tree":"2"*40,"parent_heads":[],"currentness":"STALE","integration_state":"OBSERVED","authority_state":"NONE_BY_THIS_NODE","runtime_state":"ACTIVE","truth_subject":None,"rag_release":None,"evidence_refs":["x"],"supersedes":[],"superseded_by":[],"observed_at":None,"notes":"x"}
class GitLogicalTreeTests(unittest.TestCase):
 def test_v3_deterministic_current_candidate_graph(self):
  td,r=repo();self.addCleanup(td.cleanup);a=generate(r,facts(r));b=generate(r,facts(r));self.assertEqual(a,b);self.assertEqual(a["schema"],"lion.git-logical-tree/v3");self.assertEqual(a["graph_digest_domain"],"LION/GIT-LOGICAL-TREE/3")
 def test_descendant_history_and_parent_edges(self):
  td,r=repo();self.addCleanup(td.cleanup);(r/"b").write_text("b");run(r,"add","b");run(r,"commit","-qm","candidate");g=generate(r,facts(r));self.assertTrue(any(n["currentness"]=="CURRENT_LOCAL_LINEAGE" for n in g["nodes"]));self.assertTrue(any(e["relation"]=="PARENT_OF" for e in g["edges"]))
 def test_diverged_head_fails_closed(self):
  td,r=repo();self.addCleanup(td.cleanup);run(r,"checkout","-qb","other");(r/"x").write_text("x");run(r,"add","x");run(r,"commit","-qm","x");base=subprocess.check_output(["git","-C",str(r),"rev-parse","refs/remotes/origin/master"]).decode().strip();run(r,"checkout","-q",base);(r/"m").write_text("m");run(r,"add","m");run(r,"commit","-qm","m");run(r,"update-ref","refs/remotes/origin/master","HEAD");run(r,"checkout","-q","other");
  with self.assertRaisesRegex(GitLogicalTreeError,"not descendant"):generate(r,facts(r))
 def test_external_runtime_fact_stays_non_authoritative(self):
  td,r=repo();self.addCleanup(td.cleanup);g=generate(r,facts(r,[external()]));n=next(n for n in g["nodes"] if n["node_id"]=="runtime:x");self.assertEqual(n["authority_state"],"NONE_BY_THIS_NODE")
 def test_external_authority_injection_denied(self):
  td,r=repo();self.addCleanup(td.cleanup);n=external();n["authority_state"]="ALLOW";
  with self.assertRaisesRegex(GitLogicalTreeError,"cannot grant authority"):generate(r,facts(r,[n]))
 def test_unknown_edge_denied(self):
  td,r=repo();self.addCleanup(td.cleanup);
  with self.assertRaisesRegex(GitLogicalTreeError,"unknown node"):generate(r,facts(r,[],[{"source":"x","relation":"PARENT_OF","target":"y"}]))
 def test_snapshot_validates_after_descendant_commit(self):
  td,r=repo();self.addCleanup(td.cleanup);v=generate(r,facts(r));(r/"snapshot.json").write_text(json.dumps(v));run(r,"add","snapshot.json");run(r,"commit","-qm","store snapshot");out=validate_snapshot(r,v);self.assertTrue(out["valid"]);self.assertEqual(out["descendant_distance"],1)
 def test_snapshot_digest_substitution_denied(self):
  td,r=repo();self.addCleanup(td.cleanup);v=generate(r,facts(r));v["graph_digest"]="0"*64
  with self.assertRaisesRegex(GitLogicalTreeError,"digest mismatch"):validate_snapshot(r,v)
 def test_canonical_github_remote_maps_to_owner_repo(self):
  td,r=repo();self.addCleanup(td.cleanup);run(r,"remote","add","origin","https://github.com/DonkeyJJLove/ai_platform.git");g=generate(r,facts(r));self.assertEqual(g["repository"],"DonkeyJJLove/ai_platform")
 def test_hostile_url_containing_github_path_is_not_sanitized_as_github(self):
  td,r=repo();self.addCleanup(td.cleanup);run(r,"remote","add","origin","https://evil.example/github.com/attacker/repo.git");g=generate(r,facts(r));self.assertEqual(g["repository"],r.name);self.assertNotEqual(g["repository"],"attacker/repo")
 def test_canonical_scp_github_remote_maps_to_owner_repo(self):
  td,r=repo();self.addCleanup(td.cleanup);run(r,"remote","add","origin","git@github.com:DonkeyJJLove/ai_platform.git");g=generate(r,facts(r));self.assertEqual(g["repository"],"DonkeyJJLove/ai_platform")
 def test_generator_does_not_mutate_repository(self):
  td,r=repo();self.addCleanup(td.cleanup);p=facts(r);before=subprocess.check_output(["git","-C",str(r),"status","--porcelain"]);generate(r,p);after=subprocess.check_output(["git","-C",str(r),"status","--porcelain"]);self.assertEqual(before,after)
if __name__=='__main__':unittest.main()

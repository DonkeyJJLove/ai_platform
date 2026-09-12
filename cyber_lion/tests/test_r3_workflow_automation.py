import re,unittest
from pathlib import Path
from tools.lion_rag32_validate import validate,RagValidationError
ROOT=Path(__file__).resolve().parents[2]
class R3WorkflowAutomationTests(unittest.TestCase):
 def text(self,name):return (ROOT/".github/workflows"/name).read_text()
 def test_new_workflows_are_read_only_exact_head_and_bounded(self):
  for name in ("lion-rag32-validate.yml","lion-git-logical-tree.yml"):
   t=self.text(name); self.assertIn("permissions:\n  contents: read",t); self.assertNotRegex(t,r"(?m)^\s+(contents|actions|pull-requests|issues|checks|deployments): write$")
   self.assertIn("persist-credentials: false",t); self.assertIn("timeout-minutes: 10",t); self.assertIn("concurrency:",t); self.assertIn("git rev-parse HEAD",t); self.assertIn("HEAD^{tree}",t); self.assertNotIn("secrets.",t)
 def test_rag_workflow_uploads_digest_bound_artifact(self):
  t=self.text("lion-rag32-validate.yml"); self.assertIn("RAG_VALIDATION_SHA256",t); self.assertIn("actions/upload-artifact@v4",t); self.assertIn("tools/lion_rag32_validate.py",t)
 def test_git_workflow_runs_falsifiers_and_uploads_graph(self):
  t=self.text("lion-git-logical-tree.yml"); self.assertIn("test_lion_git_logical_tree",t); self.assertIn("GIT_TREE_ARTIFACT_SHA256",t); self.assertIn("GIT_TREE_VALIDATION_SHA256",t); self.assertIn("--validate LION/architecture/v1_4/GIT_LOGICAL_TREE.json",t); self.assertIn("--external-facts LION/architecture/v1_4/GIT_LOGICAL_TREE_FACTS.json",t); self.assertIn("actions/upload-artifact@v4",t)
 def test_repository_r1_package_still_validates_read_only(self):
  result=validate(ROOT,"LION/rag/lion_project_rag32_v1_4_r1"); self.assertEqual(result["status"],"PASS"); self.assertEqual(result["source_count"],123)
 def test_validator_rejects_path_escape(self):
  with self.assertRaises((RagValidationError,FileNotFoundError)): validate(ROOT,"../")
if __name__=='__main__':unittest.main()

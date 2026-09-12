from pathlib import Path
import hashlib,tempfile,unittest,subprocess,sys,json
from tools.lion_rag_artifact_currentness import classify
ROOT=Path(__file__).resolve().parents[2]
R1=ROOT/'LION/rag/lion_project_rag32_v1_4_r1'
class RagArtifactCurrentnessTests(unittest.TestCase):
 def manifest(self):return hashlib.sha256((R1/'05_PACKAGE_MANIFEST.md').read_bytes()).hexdigest()
 def test_exact_bound_repository_artifact_is_current(self):
  v=classify(ROOT,R1,expected_release='lion-rag32-v1.4-r1',expected_manifest_sha256=self.manifest());self.assertEqual(v['status'],'PASS');self.assertEqual(v['currentness'],'EXACT_BOUND_CURRENT');self.assertEqual((v['authority_effect'],v['runtime_effect']),('NONE','NONE'))
 def test_validated_unbound_never_becomes_current(self):
  v=classify(ROOT,R1);self.assertEqual(v['currentness'],'VALIDATED_UNBOUND')
 def test_wrong_release_is_stale_not_current(self):
  v=classify(ROOT,R1,expected_release='other',expected_manifest_sha256=self.manifest());self.assertEqual(v['currentness'],'STALE_RELEASE')
 def test_wrong_manifest_is_unknown_not_current(self):
  v=classify(ROOT,R1,expected_release='lion-rag32-v1.4-r1',expected_manifest_sha256='0'*64);self.assertEqual(v['currentness'],'UNKNOWN_MANIFEST_MISMATCH')
 def test_missing_artifact_is_unknown(self):
  with tempfile.TemporaryDirectory() as d:
   v=classify(ROOT,Path(d)/'missing',expected_release='x',expected_manifest_sha256='0'*64);self.assertEqual(v['status'],'UNKNOWN_MISSING');self.assertEqual(v['currentness'],'UNKNOWN')
 def test_fileset_digest_is_stable(self):
  a=classify(ROOT,R1);b=classify(ROOT,R1);self.assertEqual(a['artifact_fileset_digest'],b['artifact_fileset_digest']);self.assertEqual(a['artifact_file_count'],32)
 def test_direct_cli_exact_bound(self):
  proc=subprocess.run([sys.executable,str(ROOT/'tools/lion_rag_artifact_currentness.py'),'--repository',str(ROOT),'--artifact-root',str(R1),'--expected-release','lion-rag32-v1.4-r1','--expected-manifest-sha256',self.manifest()],cwd=ROOT,text=True,capture_output=True)
  self.assertEqual(proc.returncode,0,proc.stderr);v=json.loads(proc.stdout);self.assertEqual(v['currentness'],'EXACT_BOUND_CURRENT')

if __name__=='__main__':unittest.main()

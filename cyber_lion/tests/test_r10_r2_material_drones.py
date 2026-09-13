from __future__ import annotations
import tempfile,unittest,subprocess,json
from pathlib import Path
from tools.lion_material_drone_worker import ROLES,execute,digest,validate_receipt_object

class MaterialDroneContractTests(unittest.TestCase):
    def test_exact_mat12_roles(self):
        self.assertEqual(tuple(ROLES),tuple(f"MAT{i:02d}" for i in range(1,13)))
        self.assertEqual(len(set(ROLES.values())),12)
    def test_repository_currentness_is_read_only(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);r=Path(td.name);subprocess.run(["git","init",str(r)],check=True,capture_output=True);(r/"a.txt").write_text("x");subprocess.run(["git","-C",str(r),"add","."],check=True);subprocess.run(["git","-C",str(r),"-c","user.name=t","-c","user.email=t@x","commit","-m","x"],check=True,capture_output=True)
        x=execute("LOCAL_REPOSITORY_CURRENTNESS","head_tree",{},r,"http://127.0.0.1:8772");self.assertEqual(set(x),{"head","tree"});self.assertEqual(execute("LOCAL_REPOSITORY_CURRENTNESS","status",{},r,"http://127.0.0.1:8772"),[])
        with self.assertRaises(ValueError):execute("LOCAL_REPOSITORY_CURRENTNESS","push",{},r,"http://127.0.0.1:8772")
    def test_content_traversal_denied(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);r=Path(td.name);(r/"a.md").write_text("LION")
        with self.assertRaises(ValueError):execute("LOCAL_REPOSITORY_CONTENT","read_file",{"path":"../outside"},r,"http://127.0.0.1:8772")
    def test_receipt_validation_requires_none_authority_and_digest(self):
        result={"x":1};rec={"task_id":"t","drone_id":"MAT01","runtime_identity":"r","role":"LOCAL_REPOSITORY_CURRENTNESS","input_digest":"a"*64,"result_digest":digest(result),"started_at":"s","completed_at":"e","status":"PASS","authority_effect":"NONE","result":result}
        rec["receipt_digest"]=digest(rec);self.assertTrue(validate_receipt_object(rec));bad=dict(rec);bad["authority_effect"]="WRITE";self.assertFalse(validate_receipt_object(bad))
    def test_coordinator_accepts_only_digests(self):
        out=execute("MATERIAL_COORDINATOR","coordinate",{"receipt_digests":["a"*64,"b"*64]},Path.cwd(),"http://127.0.0.1:8772");self.assertEqual(out["authority_effect"],"NONE")
        with self.assertRaises(ValueError):execute("MATERIAL_COORDINATOR","coordinate",{"receipt_digests":["not-a-digest"]},Path.cwd(),"http://127.0.0.1:8772")

if __name__=="__main__":unittest.main()

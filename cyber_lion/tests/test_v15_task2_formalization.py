import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
V15=ROOT/"LION/architecture/v1_5"
class V15Task2FormalizationTests(unittest.TestCase):
    def test_afm_digest_and_global_surface_set(self):
        afm=json.loads((V15/"ARCHITECTURE_FORMALIZATION_MANIFEST_TASK2.json").read_text(encoding="utf-8"))
        declared=afm.pop("manifest_digest")
        payload=json.dumps(afm,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
        observed=hashlib.sha256(b"LION/ARCHITECTURE-FORMALIZATION-MANIFEST/1\0"+payload).hexdigest()
        self.assertEqual(declared,observed)
        ids={x["artifact_id"] for x in afm["formalization_updates"]}
        expected={"semantic-owners","contract-catalog","capability-catalog","architecture-projection","event-state-catalog","gap-projection","evolution-evals","discoverability-bootstrap","rag-routing","currentness-carriers"}
        self.assertEqual(ids,expected)
    def test_no_new_top_level_layer_requested(self):
        afm=json.loads((V15/"ARCHITECTURE_FORMALIZATION_MANIFEST_TASK2.json").read_text(encoding="utf-8"))
        self.assertTrue(afm["layer_bindings"])
        self.assertTrue(all(x["new_top_level_layer_required"] is False for x in afm["layer_bindings"]))
    def test_registry_identity_and_paths_are_unique(self):
        reg=json.loads((V15/"FORMALIZATION_REGISTRY_CANDIDATE.json").read_text(encoding="utf-8"))
        ids=[x["artifact_id"] for x in reg["entries"]];paths=[x["path"] for x in reg["entries"]]
        self.assertEqual(len(ids),len(set(ids)));self.assertEqual(len(paths),len(set(paths)))
    def test_task2_preclosure_rag_delta_is_explicit(self):
        bootstrap=json.loads((ROOT/"LION/rag/RAG_BOOTSTRAP.json").read_text(encoding="utf-8"))
        self.assertEqual(bootstrap["v15_task3_currentness"],"CURRENT_CANDIDATE")
        self.assertEqual(bootstrap["preferred_release"],"lion-rag32-v1.4-r9-auth-lifecycle-candidate")
if __name__=="__main__":unittest.main()

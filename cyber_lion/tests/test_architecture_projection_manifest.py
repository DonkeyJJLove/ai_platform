import unittest
from cyber_lion.architecture_projection.extractor import ArchitectureProjectionExtractor
from cyber_lion.architecture_projection.manifest import build_manifest
from cyber_lion.architecture_projection.plantuml import serialize_plantuml

class ArchitectureProjectionManifestTests(unittest.TestCase):
    def test_manifest_binds_tree_model_tool_and_artifact(self):
        m=ArchitectureProjectionExtractor(source_tree_sha="f"*40).named_projection("lion-system-component-map")
        p=serialize_plantuml(m)
        x=build_manifest(model=m,artifact=p,plantuml_version="1.2026.6",plantuml_binary_digest="a"*64,rendering_mode="PUML_ONLY")
        self.assertEqual(x.source_tree_sha,"f"*40); self.assertEqual(x.diagram_source_digest,m.source_digest())
        self.assertEqual(x.authority_effect,"NONE"); self.assertEqual(x.runtime_evidence,"NONE")

if __name__=="__main__":unittest.main()

import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from cyber_lion.architecture_projection.extractor import ArchitectureProjectionExtractor
from cyber_lion.architecture_projection.plantuml import PlantUMLRenderer,serialize_plantuml

class ArchitectureProjectionPlantUMLTests(unittest.TestCase):
    def test_same_model_same_puml(self):
        m=ArchitectureProjectionExtractor(source_tree_sha="e"*40).named_projection("capability-map")
        self.assertEqual(serialize_plantuml(m),serialize_plantuml(m))
    def test_renderer_unconfigured_and_network_denied(self):
        with self.assertRaises(RuntimeError): PlantUMLRenderer().validate_configuration()
        with self.assertRaises(RuntimeError): PlantUMLRenderer("https://example.invalid","1.2026.6","0"*64).validate_configuration()
    def test_renderer_digest_and_version_drift_are_denied(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"plantuml.jar"; path.write_bytes(b"pinned-test-material")
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(RuntimeError,"digest mismatch"):
                PlantUMLRenderer(str(path),"1.2026.6","0"*64).validate_configuration()
            with patch("cyber_lion.architecture_projection.plantuml.subprocess.run",return_value=SimpleNamespace(returncode=0,stdout=b"PlantUML version 1.2026.5")):
                with self.assertRaisesRegex(RuntimeError,"version mismatch"):
                    PlantUMLRenderer(str(path),"1.2026.6",digest).validate_configuration()
            with patch("cyber_lion.architecture_projection.plantuml.subprocess.run",return_value=SimpleNamespace(returncode=0,stdout=b"PlantUML version 1.2026.6")):
                self.assertEqual(PlantUMLRenderer(str(path),"1.2026.6",digest).validate_configuration(),path)
    def test_shell_execution_absent_and_fixed_argv(self):
        import inspect, cyber_lion.architecture_projection.plantuml as p
        src=inspect.getsource(p.PlantUMLRenderer)
        self.assertIn("shell=False",src); self.assertNotIn("shell=True",src)
        self.assertIn('"-tsvg"',src); self.assertIn('"-version"',src)

if __name__=="__main__":unittest.main()

import tempfile,unittest
from pathlib import Path
from cyber_lion.architecture_projection.extractor import ArchitectureProjectionExtractor
from cyber_lion.architecture_projection.plantuml import PlantUMLRenderer,serialize_plantuml

class ArchitectureProjectionPlantUMLTests(unittest.TestCase):
    def test_same_model_same_puml(self):
        m=ArchitectureProjectionExtractor(source_tree_sha="e"*40).named_projection("capability-map")
        self.assertEqual(serialize_plantuml(m),serialize_plantuml(m))
    def test_renderer_unconfigured_and_network_denied(self):
        with self.assertRaises(RuntimeError): PlantUMLRenderer().validate_configuration()
        with self.assertRaises(RuntimeError): PlantUMLRenderer("https://example.invalid", "1", "0"*64).validate_configuration()
    def test_shell_execution_absent(self):
        import inspect, cyber_lion.architecture_projection.plantuml as p
        self.assertIn("shell=False",inspect.getsource(p.PlantUMLRenderer.render_svg))

if __name__=="__main__":unittest.main()

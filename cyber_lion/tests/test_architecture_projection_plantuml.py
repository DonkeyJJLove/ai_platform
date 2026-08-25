import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from cyber_lion.architecture_projection.model import CanonicalDiagramModel, DiagramNode, DiagramEdge
from cyber_lion.architecture_projection.plantuml import PlantUMLRenderer, serialize_plantuml, _parse_exact_version

D = "a" * 64


def model(label_a="A", label_b="B"):
    nodes = (
        DiagramNode("n_a", label_a, "component", "a.py", D),
        DiagramNode("n_b", label_b, "component", "b.py", D),
    )
    edges = (DiagramEdge("n_a", "n_b", "SOURCE_PROVENANCE", provenance_ref="a.py->b.py"),)
    return CanonicalDiagramModel("capability-map", "component", "e" * 40, nodes, edges).validate()


class ArchitectureProjectionPlantUMLTests(unittest.TestCase):
    def test_same_model_same_puml(self):
        self.assertEqual(serialize_plantuml(model()), serialize_plantuml(model()))

    def test_renderer_unconfigured_and_network_denied(self):
        with self.assertRaises(RuntimeError):
            PlantUMLRenderer().validate_configuration()
        with self.assertRaises(RuntimeError):
            PlantUMLRenderer("https://example.invalid", "1.2026.6", "0" * 64).validate_configuration()

    def test_renderer_digest_and_exact_version_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plantuml.jar"
            path.write_bytes(b"pinned-test-material")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(RuntimeError, "digest mismatch"):
                PlantUMLRenderer(str(path), "1.2026.6", "0" * 64).validate_configuration()
            with patch("cyber_lion.architecture_projection.plantuml.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=b"PlantUML version 1.2026.5\n")):
                with self.assertRaisesRegex(RuntimeError, "version mismatch"):
                    PlantUMLRenderer(str(path), "1.2026.6", digest).validate_configuration()
            with patch("cyber_lion.architecture_projection.plantuml.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=b"PlantUML version 1.2026.6\n")):
                self.assertEqual(PlantUMLRenderer(str(path), "1.2026.6", digest).validate_configuration(), path)

    def test_version_substring_and_ambiguous_outputs_are_denied(self):
        with self.assertRaises(RuntimeError):
            _parse_exact_version(b"wrapper PlantUML version 1.2026.6 suffix\n")
        with self.assertRaises(RuntimeError):
            _parse_exact_version(b"PlantUML version 1.2026.6\nPlantUML version 1.2026.5\n")
        self.assertEqual(_parse_exact_version(b"PlantUML version 1.2026.6\n"), "1.2026.6")

    def test_directive_fragments_in_labels_are_denied(self):
        for payload in ("!includeurl https://x", "!pragma layout smetana", "@startuml", "skinparam foo bar"):
            with self.assertRaises(ValueError):
                serialize_plantuml(model(payload, "B"))

    def test_shell_execution_absent_and_fixed_argv(self):
        import inspect
        import cyber_lion.architecture_projection.plantuml as plantuml
        source = inspect.getsource(plantuml.PlantUMLRenderer)
        self.assertIn("shell=False", source)
        self.assertNotIn("shell=True", source)
        self.assertIn('"-tsvg"', source)
        self.assertIn('"-version"', source)

if __name__ == "__main__":
    unittest.main()

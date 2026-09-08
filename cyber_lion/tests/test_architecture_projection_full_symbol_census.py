import inspect
import json
from pathlib import Path
import tempfile
import unittest

from cyber_lion.architecture_projection import full_symbol_census as module
from cyber_lion.architecture_projection.full_symbol_census import (
    FullSymbolCensusError,
    build_full_symbol_census,
    canonical_census_json,
)


HEAD = "a" * 40
TREE = "b" * 40


class FullSymbolCensusTests(unittest.TestCase):
    def _fixture(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "pkg").mkdir()
        (root / "tests").mkdir()
        (root / "pkg" / "__init__.py").write_text('"""package docs"""\n', encoding="utf-8")
        (root / "pkg" / "service.py").write_text(
            """\
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

class Api(Protocol):
    def fetch(self, key: str) -> str:
        \"\"\"Fetch one key.\"\"\"
        ...

class Mode(Enum):
    READ = \"read\"

class ServiceError(Exception):
    pass

@dataclass
class Record:
    value: str

class Service:
    \"\"\"Public service.\"\"\"
    field: str

    def run(self, path: Path, value: str) -> None:
        \"\"\"Execute bounded write fixture.\"\"\"
        path.write_text(value, encoding=\"utf-8\")

    def _runtime_fence(self, value: str) -> str:
        return value

async def async_probe(value: str) -> str:
    return value

def public_helper(value: str) -> str:
    \"\"\"Return the value.\"\"\"
    return value
""",
            encoding="utf-8",
        )
        (root / "tests" / "test_service.py").write_text(
            """\
from pkg.service import Service

def test_service_reference():
    assert Service is not None
""",
            encoding="utf-8",
        )
        return temp, root

    def test_exact_ast_census_detects_required_symbol_classes(self):
        temp, root = self._fixture()
        self.addCleanup(temp.cleanup)
        paths = ("pkg/__init__.py", "pkg/service.py", "tests/test_service.py")
        first = build_full_symbol_census(
            source_root=root,
            committed_python_paths=paths,
            source_head=HEAD,
            source_tree=TREE,
        )
        second = build_full_symbol_census(
            source_root=root,
            committed_python_paths=reversed(paths),
            source_head=HEAD,
            source_tree=TREE,
        )
        self.assertTrue(first["success"])
        self.assertEqual(first["census_digest"], second["census_digest"])
        self.assertEqual(first["counts"]["committed_python_files"], 3)
        self.assertEqual(first["counts"]["parsed_python_files"], 3)
        self.assertEqual(first["counts"]["parse_failures"], 0)
        self.assertGreaterEqual(first["counts"]["classes"], 5)
        self.assertEqual(first["counts"]["dataclasses"], 1)
        self.assertEqual(first["counts"]["protocols"], 1)
        self.assertEqual(first["counts"]["enums"], 1)
        self.assertEqual(first["counts"]["exceptions"], 1)
        self.assertEqual(first["counts"]["async_functions"], 1)
        self.assertGreaterEqual(first["counts"]["methods"], 3)
        by_name = {item["qualified_name"]: item for item in first["symbols"]}
        service = by_name["pkg.service.Service"]
        self.assertTrue(service["public"])
        self.assertTrue(service["docstring_present"])
        self.assertTrue(service["any_type_annotation_present"])
        run = by_name["pkg.service.Service.run"]
        self.assertTrue(run["fully_annotated_signature_or_fields"])
        self.assertTrue(run["effect_surface_refs"])
        self.assertIn("tests/test_service.py:test_service_reference", service["test_reference_candidates"])
        private = by_name["pkg.service.Service._runtime_fence"]
        self.assertTrue(private["private_material_symbol"])
        self.assertIn("LEXICAL_BOUNDARY_MARKER", private["private_material_reason"])

    def test_parse_failure_is_explicit_and_fails_success_gate(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")
        value = build_full_symbol_census(
            source_root=root,
            committed_python_paths=("broken.py",),
            source_head=HEAD,
            source_tree=TREE,
        )
        self.assertFalse(value["success"])
        self.assertEqual(value["counts"]["committed_python_files"], 1)
        self.assertEqual(value["counts"]["parsed_python_files"], 0)
        self.assertEqual(value["counts"]["parse_failures"], 1)
        self.assertTrue(value["parse_failures"][0]["error"].startswith("SYNTAX_ERROR:"))

    def test_missing_symlink_duplicate_and_non_python_paths_fail_closed(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "a.py").write_text("x = 1\n", encoding="utf-8")
        with self.assertRaisesRegex(FullSymbolCensusError, "duplicates"):
            build_full_symbol_census(
                source_root=root,
                committed_python_paths=("a.py", "a.py"),
                source_head=HEAD,
                source_tree=TREE,
            )
        with self.assertRaisesRegex(FullSymbolCensusError, "must end in .py"):
            build_full_symbol_census(
                source_root=root,
                committed_python_paths=("README.md",),
                source_head=HEAD,
                source_tree=TREE,
            )
        with self.assertRaisesRegex(FullSymbolCensusError, "canonical"):
            build_full_symbol_census(
                source_root=root,
                committed_python_paths=("../a.py",),
                source_head=HEAD,
                source_tree=TREE,
            )

    def test_output_is_canonical_and_static_reference_is_not_coverage_claim(self):
        temp, root = self._fixture()
        self.addCleanup(temp.cleanup)
        value = build_full_symbol_census(
            source_root=root,
            committed_python_paths=("pkg/__init__.py", "pkg/service.py", "tests/test_service.py"),
            source_head=HEAD,
            source_tree=TREE,
        )
        encoded = canonical_census_json(value)
        self.assertEqual(json.loads(encoded)["census_digest"], value["census_digest"])
        self.assertEqual(
            value["classification_rules"]["test_reference_candidate"],
            "test function statically references a unique leaf name; reference is not execution/coverage proof",
        )

    def test_projection_module_adds_no_network_or_subprocess_execution_surface(self):
        source = inspect.getsource(module)
        self.assertNotIn("subprocess.run", source)
        self.assertNotIn("subprocess.Popen", source)
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("requests.", source)
        self.assertNotIn("os.system", source)
        self.assertNotIn("os.exec", source)


if __name__ == "__main__":
    unittest.main()

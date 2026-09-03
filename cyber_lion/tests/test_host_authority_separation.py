from __future__ import annotations

from pathlib import Path
import subprocess
import unittest

import cyber_lion.tests._r6_host_authority_separation_original as _r6
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
import cyber_lion.enterprise.host_authority_separation as hostsep

REPOSITORY = "DonkeyJJLove/ai_platform"
ADDED_PRODUCTION_SOURCES = (
    ".github/workflows/r2e4-r6-terminal-evidence.yml",
    "cyber_lion/enterprise/merge_admission_terminal_evidence.py",
)
EXCLUDED_R6_TEST_SOURCE = "cyber_lion/tests/test_merge_admission_terminal_evidence.py"


class HostAuthoritySeparationTests(_r6.HostAuthoritySeparationTests):
    """Exact R6 host-authority suite with only the stale inventory cardinality repaired."""

    def test_effect_surface_and_exact_terminal_inventory(self):
        changed = (
            "cyber_lion/contracts/independent_evidence_origin.py",
            "cyber_lion/enterprise/host_authority_separation.py",
            "cyber_lion/enterprise/independent_evidence_origin.py",
        )
        local = EffectSurfaceScanner().scan(
            repository=_r6.CANONICAL_REPOSITORY,
            revision="1" * 40,
            tree_digest="2" * 40,
            sources={path: Path(path).read_text() for path in changed},
        )
        self.assertEqual(local.surfaces, ())
        self.assertEqual(local.unclassified_refs, ())

        raw = subprocess.run(
            ["git", "ls-files", "-z"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
        sources = {}
        for item in raw.split(b"\0"):
            if item:
                path = item.decode()
                if hostsep._production_path(path):
                    sources[path] = Path(path).read_text()

        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        tree_digest = subprocess.run(
            ["git", "write-tree"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        inventory = EffectSurfaceScanner().scan(
            repository=_r6.CANONICAL_REPOSITORY,
            revision=revision,
            tree_digest=tree_digest,
            sources=sources,
        )

        # Source cardinality is intentionally independent from effect and UNKNOWN cardinality.
        self.assertEqual(len(sources), 252)
        self.assertEqual(len(inventory.surfaces), 236)
        self.assertEqual(len(inventory.unclassified_refs), 6)


class R7SourceInventoryContractTests(unittest.TestCase):
    def production_paths(self) -> tuple[str, ...]:
        raw = subprocess.run(
            ["git", "ls-files", "-z"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
        return tuple(
            path
            for item in raw.split(b"\0")
            if item
            for path in (item.decode(),)
            if hostsep._production_path(path)
        )

    def test_exact_r6_production_delta_is_two_and_reduces_to_parent_cardinality(self):
        paths = self.production_paths()
        self.assertEqual(len(paths), 252)
        for path in ADDED_PRODUCTION_SOURCES:
            self.assertIn(path, paths)
        reduced = tuple(path for path in paths if path not in ADDED_PRODUCTION_SOURCES)
        self.assertEqual(len(reduced), 250)

    def test_r6_added_production_sources_are_intentionally_classified(self):
        for path in ADDED_PRODUCTION_SOURCES:
            with self.subTest(path=path):
                self.assertTrue(hostsep._production_path(path))
        self.assertFalse(hostsep._production_path(EXCLUDED_R6_TEST_SOURCE))
        self.assertFalse(hostsep._production_path("docs/r7-evidence.md"))

    def test_test_or_documentation_content_cannot_silently_enter_production_inventory(self):
        self.assertFalse(hostsep._production_path("cyber_lion/tests/r7_same_content.py"))
        self.assertFalse(hostsep._production_path("docs/r7_same_content.py.md"))
        self.assertTrue(hostsep._production_path("cyber_lion/enterprise/r7_same_content.py"))

    def test_r6_evidence_sources_add_no_effect_surface_or_unknown(self):
        sources = {path: Path(path).read_text() for path in ADDED_PRODUCTION_SOURCES}
        inventory = EffectSurfaceScanner().scan(
            repository=REPOSITORY,
            revision="7" * 40,
            tree_digest="8" * 40,
            sources=sources,
        )
        self.assertEqual(inventory.surfaces, ())
        self.assertEqual(inventory.unclassified_refs, ())

    def test_effect_bearing_source_masquerading_as_evidence_is_detected(self):
        path = "cyber_lion/enterprise/r7_evidence_probe.py"
        inventory = EffectSurfaceScanner().scan(
            repository=REPOSITORY,
            revision="9" * 40,
            tree_digest="a" * 40,
            sources={path: 'from pathlib import Path\nPath("r7-probe").write_bytes(b"x")\n'},
        )
        self.assertEqual(len(inventory.surfaces), 1)
        self.assertEqual(inventory.surfaces[0].effect_class, "filesystem.write")
        self.assertEqual(inventory.unclassified_refs, ())

    def test_source_and_effect_cardinality_remain_independent(self):
        passive = "cyber_lion/enterprise/r7_passive_evidence.py"
        active = "cyber_lion/enterprise/r7_active_evidence.py"
        sources = {
            passive: "VALUE = 'evidence-only'\n",
            active: 'from pathlib import Path\nPath("r7-probe").write_bytes(b"x")\n',
        }
        inventory = EffectSurfaceScanner().scan(
            repository=REPOSITORY,
            revision="b" * 40,
            tree_digest="c" * 40,
            sources=sources,
        )
        self.assertEqual(len(sources), 2)
        self.assertEqual(inventory.repository, REPOSITORY)
        self.assertEqual(inventory.revision, "b" * 40)
        self.assertEqual(inventory.tree_digest, "c" * 40)
        self.assertEqual(len(inventory.surfaces), 1)
        self.assertEqual(inventory.unclassified_refs, ())
        self.assertNotEqual(len(sources), len(inventory.surfaces))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from cyber_lion.architecture_projection.truth_plane import CARRIER_PATHS, SubjectEntry, subject_digest
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.host_authority_separation import _production_path


class R22FTruthSourceRegressions(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def _init_repo(self) -> Path:
        root = Path(tempfile.mkdtemp(prefix="lion-r22f-truth-"))
        self._git(root, "init")
        self._git(root, "config", "user.name", "LION R22F")
        self._git(root, "config", "user.email", "lion-r22f@example.invalid")
        return root

    def _write(self, root: Path, path: str, text: str) -> None:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def _entries(self, root: Path, ref: str = "HEAD") -> tuple[SubjectEntry, ...]:
        raw = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-r", "-z", ref],
            check=True,
            capture_output=True,
        ).stdout
        values = []
        for record in raw.split(b"\0"):
            if not record:
                continue
            meta, path = record.split(b"\t", 1)
            mode, object_type, object_sha = meta.decode("ascii").split(" ")
            values.append(
                SubjectEntry(
                    path=path.decode("utf-8"),
                    mode=mode,
                    object_type=object_type,
                    object_sha=object_sha,
                )
            )
        return tuple(values)

    def _commit(self, root: Path, message: str, *, allow_empty: bool = False) -> str:
        self._git(root, "add", "-A")
        args = ["commit"]
        if allow_empty:
            args.append("--allow-empty")
        args.extend(["-m", message])
        self._git(root, *args)
        return self._git(root, "rev-parse", "HEAD")

    def test_carrier_only_two_commit_chain_preserves_subject_digest(self):
        root = self._init_repo()
        carriers = sorted(CARRIER_PATHS)
        self._write(root, "subject.txt", "material\n")
        self._write(root, carriers[0], "carrier-a-v1\n")
        self._write(root, carriers[1], "carrier-b-v1\n")
        self._commit(root, "baseline")
        baseline = subject_digest(self._entries(root))

        self._write(root, carriers[0], "carrier-a-v2\n")
        self._commit(root, "carrier one")
        after_one = subject_digest(self._entries(root))

        self._write(root, carriers[1], "carrier-b-v2\n")
        self._commit(root, "carrier two")
        after_two = subject_digest(self._entries(root))

        self.assertEqual(baseline, after_one)
        self.assertEqual(after_one, after_two)

    def test_same_tree_different_commit_preserves_subject_digest(self):
        root = self._init_repo()
        self._write(root, "subject.txt", "material\n")
        first = self._commit(root, "first")
        first_tree = self._git(root, "rev-parse", f"{first}^{{tree}}")
        first_digest = subject_digest(self._entries(root, first))

        second = self._commit(root, "second metadata only", allow_empty=True)
        second_tree = self._git(root, "rev-parse", f"{second}^{{tree}}")
        second_digest = subject_digest(self._entries(root, second))

        self.assertNotEqual(first, second)
        self.assertEqual(first_tree, second_tree)
        self.assertEqual(first_digest, second_digest)

    def test_production_source_selector_returns_exact_deterministic_set(self):
        candidates = {
            "cyber_lion/contracts/action_runtime_binding.py": "VALUE=1\n",
            "cyber_lion/tests/test_action_runtime_binding_and_model_plane.py": "VALUE=2\n",
            ".github/workflows/lion-r22c-full-symbol-census.yml": "name: census\n",
            "docs/not-production.py": "VALUE=3\n",
        }
        selected = tuple(sorted(path for path in candidates if _production_path(path)))
        self.assertEqual(
            selected,
            (
                ".github/workflows/lion-r22c-full-symbol-census.yml",
                "cyber_lion/contracts/action_runtime_binding.py",
            ),
        )
        self.assertFalse(_production_path("cyber_lion/tests/test_architecture_projection_full_symbol_census.py"))
        self.assertTrue(_production_path(".github/workflows/lion-r22c-full-symbol-census.yml"))

    def test_source_count_change_with_stable_effect_surfaces_remains_explicit_drift(self):
        scanner = EffectSurfaceScanner()
        base_sources = {"cyber_lion/contracts/inert.py": "VALUE=1\n"}
        current_sources = {
            **base_sources,
            ".github/workflows/inert.yml": "name: inert\non: workflow_dispatch\njobs: {}\n",
        }
        base = scanner.scan(
            repository="DonkeyJJLove/ai_platform",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources=base_sources,
        )
        current = scanner.scan(
            repository="DonkeyJJLove/ai_platform",
            revision="c" * 40,
            tree_digest="d" * 40,
            sources=current_sources,
        )
        self.assertEqual(base.surfaces, current.surfaces)
        self.assertEqual(base.unclassified_refs, current.unclassified_refs)
        self.assertNotEqual(base.scan_digest, current.scan_digest)
        self.assertEqual(base.evidence_refs[0], "source-count:1")
        self.assertEqual(current.evidence_refs[0], "source-count:2")

    def test_scan_pin_update_requires_exact_source_delta_proof(self):
        scanner = EffectSurfaceScanner()
        universe = {
            "cyber_lion/contracts/inert.py": "VALUE=1\n",
            "cyber_lion/tests/test_inert.py": "VALUE=2\n",
            ".github/workflows/inert.yml": "name: inert\non: workflow_dispatch\njobs: {}\n",
        }

        def selected(paths: tuple[str, ...]):
            return {path: universe[path] for path in paths if _production_path(path)}

        base_paths = ("cyber_lion/contracts/inert.py",)
        test_only_paths = base_paths + ("cyber_lion/tests/test_inert.py",)
        material_paths = test_only_paths + (".github/workflows/inert.yml",)
        base = scanner.scan(
            repository="r",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources=selected(base_paths),
        )
        test_only = scanner.scan(
            repository="r",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources=selected(test_only_paths),
        )
        material = scanner.scan(
            repository="r",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources=selected(material_paths),
        )
        self.assertEqual(selected(base_paths), selected(test_only_paths))
        self.assertEqual(base.scan_digest, test_only.scan_digest)
        added = tuple(sorted(set(selected(material_paths)) - set(selected(test_only_paths))))
        self.assertEqual(added, (".github/workflows/inert.yml",))
        self.assertNotEqual(test_only.scan_digest, material.scan_digest)


if __name__ == "__main__":
    unittest.main()

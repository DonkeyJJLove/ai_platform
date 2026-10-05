from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MATERIALIZE = ROOT / "LION/runtime_compat/r24/docker-autonomy/materialize.py"
COMPOSE = ROOT / "LION/runtime_compat/r24/docker-autonomy/compose.yaml"


def load_materialize():
    spec = importlib.util.spec_from_file_location("lion_r24_materialize_test", MATERIALIZE)
    if spec is None or spec.loader is None:
        raise RuntimeError("materialize module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class R24CooperativePrivateStorageTests(unittest.TestCase):
    def test_private_layout_is_exact_32_workers_and_preserves_existing_state(self):
        module = load_materialize()
        with tempfile.TemporaryDirectory() as td:
            runtime = Path(td).resolve()
            roots = module.ensure_cooperative_private_layout(runtime)
            self.assertEqual(len(roots), 32)
            self.assertEqual(
                [x.name for x in roots],
                [f"MD{i:03d}" for i in range(1, 33)],
            )
            for worker_root in roots:
                self.assertEqual(
                    sorted(x.name for x in worker_root.iterdir()),
                    ["artifacts", "contexts", "state", "verifiers"],
                )
            marker = roots[0] / "state" / "preserve.marker"
            marker.write_bytes(b"persistent-state-must-survive")
            second = module.ensure_cooperative_private_layout(runtime)
            self.assertEqual(second, roots)
            self.assertEqual(marker.read_bytes(), b"persistent-state-must-survive")

    def test_private_layout_rejects_symlinked_worker_directory(self):
        module = load_materialize()
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            runtime = Path(td).resolve()
            private = runtime / "private"
            private.mkdir()
            (private / "MD001").symlink_to(Path(other).resolve(), target_is_directory=True)
            with self.assertRaises(SystemExit):
                module.ensure_cooperative_private_layout(runtime)

    def test_private_root_symlink_is_rejected_before_reclaim(self):
        module = load_materialize()
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            runtime = Path(td).resolve()
            (runtime / "private").symlink_to(Path(other).resolve(), target_is_directory=True)
            with self.assertRaises(SystemExit):
                module.cooperative_private_root(runtime)

    def test_compose_mounts_only_each_workers_private_root(self):
        text = COMPOSE.read_text(encoding="utf-8")
        self.assertIn("LION_COOPERATIVE_BOOTSTRAP_MODE: UNBOUND", text)
        self.assertIn('LION_COOPERATIVE_BOOTSTRAP_VERSION: "1.0.0"', text)
        self.assertIn("LION_COOPERATIVE_REPOSITORY_ROOT: /src", text)
        self.assertIn("LION_COOPERATIVE_PRIVATE_ROOT: /cooperative", text)
        self.assertNotIn("./private:/cooperative", text)

        positions = []
        for i in range(1, 33):
            service = f"  worker-{i:02d}:"
            start = text.index(service)
            positions.append(start)
        positions.append(len(text))

        for i in range(1, 33):
            block = text[positions[i - 1] : positions[i]]
            md = f"MD{i:03d}"
            private_lines = [
                line.strip()
                for line in block.splitlines()
                if "./private/" in line and ":/cooperative:" in line
            ]
            self.assertEqual(private_lines, [f"- ./private/{md}:/cooperative:rw"])
            self.assertIn("- ./source:/src:ro", block)
            self.assertIn("- ./worker.py:/runtime/worker.py:ro", block)
            self.assertIn("- ./identity.json:/identity/current.json:ro", block)
            self.assertIn("- ./status:/status:rw", block)
            self.assertIn("- ./gate:/gate:rw", block)

    def test_materializer_preserves_private_state_instead_of_removing_it(self):
        source = MATERIALIZE.read_text(encoding="utf-8")
        self.assertIn("cooperative_private_state_preserved", source)
        self.assertIn("private_workers=ensure_cooperative_private_layout(runtime)", source)
        self.assertNotIn("shutil.rmtree(private_root)", source)
        self.assertNotIn('for name in ("status","gate","private")', source)

    def test_materialization_receipt_declares_unbound_bootstrap(self):
        source = MATERIALIZE.read_text(encoding="utf-8")
        self.assertIn('"cooperative_private_worker_roots":len(private_workers)', source)
        self.assertIn('"cooperative_bootstrap_mode":"UNBOUND"', source)
        self.assertIn('"authority_effect":"NONE"', source)


if __name__ == "__main__":
    unittest.main()

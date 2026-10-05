from __future__ import annotations

import hashlib
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
        self.assertIn("LION_COOPERATIVE_DEPENDENCY_MODULE_PATH: /cooperative-provider-artifact/cooperative-provider.py", text)
        self.assertIn("LION_COOPERATIVE_MISSION_DB_PATH: /mission-control/mission-control-v3.db", text)
        self.assertIn("LION_COOPERATIVE_PROVIDER_DB_PATH: /cooperative-provider/evidence.sqlite", text)
        self.assertIn("LION_COOPERATIVE_CONTROL_PLANE_DB_PATH: /cooperative-control/control-plane.sqlite", text)
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
            self.assertIn("- ./provider-artifact:/cooperative-provider-artifact:ro", block)
            self.assertIn("${LION_COOPERATIVE_PROVIDER_STATE_HOST_PATH:-./unbound/provider-state}:/cooperative-provider:ro", block)
            self.assertIn("${LION_COOPERATIVE_CONTROL_STATE_HOST_PATH:-./unbound/control-state}:/cooperative-control:ro", block)
            self.assertIn("${LION_COOPERATIVE_MISSION_CONTROL_HOST_PATH:-./unbound/mission-control}:/mission-control:ro", block)

    def test_provider_artifact_digest_is_source_pinned_and_readonly_mounts_are_bounded(self):
        text = COMPOSE.read_text(encoding="utf-8")
        provider = ROOT / "LION/runtime_compat/r24/docker-autonomy/cooperative-provider.py"
        digest = hashlib.sha256(provider.read_bytes()).hexdigest()
        self.assertIn("LION_COOPERATIVE_DEPENDENCY_MODULE_SHA256: " + digest, text)
        self.assertIn("LION_COOPERATIVE_BOOTSTRAP_MODE: UNBOUND", text)
        self.assertNotIn("LION_COOPERATIVE_BOOTSTRAP_MODE: TRUSTED_EXTERNAL_R1", text)

    def test_materializer_externalizes_provider_artifact_but_does_not_activate_it(self):
        source = MATERIALIZE.read_text(encoding="utf-8")
        self.assertIn('provider_src=canonical/"cooperative-provider.py"', source)
        self.assertIn('provider_artifact=runtime/"provider-artifact"', source)
        self.assertIn('"cooperative_provider_artifact_sha256":provider_artifact_sha', source)
        self.assertIn('"cooperative_bootstrap_mode":"UNBOUND"', source)
        self.assertIn('for name in ("provider-state","control-state","mission-control")', source)

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

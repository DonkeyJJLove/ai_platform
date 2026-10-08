from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.mission_control.cooperative_materialization_registry import (
    CooperativeMaterializationRegistry,
)
from cyber_lion.mission_control import cooperative_process_bootstrap as bootstrap
from cyber_lion.tests.test_cooperative_worker_qualification import (
    CooperativeWorkerQualificationTests,
)


ROOT = Path(__file__).resolve().parents[2]


class CooperativeProcessBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.q = CooperativeWorkerQualificationTests(
            "test_released_projection_qualifies_one_worker_without_claim_or_effect"
        )
        self.q.setUp()
        self.addCleanup(self.q.doCleanups)
        self.write_materializer = self.q.control.materializer()
        self.verifier_root = self.q.worker()
        self.dependencies = bootstrap.CooperativeProcessBootstrapDependencies(
            write_materializer=self.write_materializer,
            verifier_root=self.verifier_root,
        ).validate()
        self.external = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(self.external, ignore_errors=True)
        )
        self.module = self.external / "process-provider.py"
        self.module.write_text("# pinned process provider fixture\n", encoding="utf-8")
        self.module_digest = sha256(self.module.read_bytes()).hexdigest()

    def environment(self, **changes):
        value = {
            "LION_COOPERATIVE_PROCESS_BOOTSTRAP_MODE": bootstrap.TRUSTED_EXTERNAL_MODE,
            "LION_COOPERATIVE_PROCESS_BOOTSTRAP_VERSION": bootstrap.BOOTSTRAP_VERSION,
            "LION_COOPERATIVE_PROCESS_REPOSITORY_ROOT": str(ROOT),
            "LION_COOPERATIVE_PROCESS_DEPENDENCY_MODULE_PATH": str(self.module),
            "LION_COOPERATIVE_PROCESS_DEPENDENCY_MODULE_SHA256": self.module_digest,
            "LION_COOPERATIVE_PROCESS_DEPENDENCY_FACTORY": "build_process_dependencies",
        }
        value.update(changes)
        return value

    def test_default_mode_remains_unbound_and_installs_nothing(self):
        registry = CooperativeMaterializationRegistry()
        result = bootstrap.bootstrap_process_materializers({}, registry=registry)
        self.assertEqual(result["state"], "UNBOUND")
        self.assertEqual(result["authority_effect"], "NONE")
        self.assertEqual(result["execution_effect"], "NONE")
        self.assertIsNone(registry.current())

    def test_trusted_mode_installs_exact_pair_once(self):
        registry = CooperativeMaterializationRegistry()
        module = SimpleNamespace(
            build_process_dependencies=lambda: self.dependencies
        )
        with patch.object(bootstrap, "_load_module", return_value=module):
            result = bootstrap.bootstrap_process_materializers(
                self.environment(), registry=registry
            )
        provider = registry.current()
        self.assertEqual(result["state"], "READY")
        self.assertEqual(result["dependency_module_sha256"], self.module_digest)
        self.assertIsNotNone(provider)
        self.assertIs(provider.write_materializer, self.write_materializer)
        self.assertIs(provider.verify_materializer.__self__, self.verifier_root)
        self.assertEqual(provider.authority_effect, "NONE")

        with patch.object(bootstrap, "_load_module", return_value=module):
            with self.assertRaisesRegex(
                bootstrap.CooperativeProcessBootstrapError, "already installed"
            ):
                bootstrap.bootstrap_process_materializers(
                    self.environment(), registry=registry
                )

    def test_factory_must_return_exact_dependency_type(self):
        registry = CooperativeMaterializationRegistry()
        module = SimpleNamespace(build_process_dependencies=lambda: object())
        with patch.object(bootstrap, "_load_module", return_value=module):
            with self.assertRaisesRegex(
                bootstrap.CooperativeProcessBootstrapError, "wrong type"
            ):
                bootstrap.bootstrap_process_materializers(
                    self.environment(), registry=registry
                )
        self.assertIsNone(registry.current())

    def test_dependency_module_must_be_outside_repository(self):
        inside = ROOT / "cyber_lion" / "mission_control" / "cooperative_process_bootstrap.py"
        env = self.environment(
            LION_COOPERATIVE_PROCESS_DEPENDENCY_MODULE_PATH=str(inside),
            LION_COOPERATIVE_PROCESS_DEPENDENCY_MODULE_SHA256=sha256(
                inside.read_bytes()
            ).hexdigest(),
        )
        with self.assertRaisesRegex(
            bootstrap.CooperativeProcessBootstrapError, "outside repository"
        ):
            bootstrap.load_process_dependencies_from_environment(env)

    def test_dependency_module_digest_mismatch_fails_closed(self):
        with self.assertRaisesRegex(
            bootstrap.CooperativeProcessBootstrapError, "digest mismatch"
        ):
            bootstrap._load_module(self.module, "0" * 64)

    def test_write_and_verifier_roots_must_share_exact_mission_db(self):
        other = self.external / "other.db"
        other.write_bytes(self.q.control.fixture.db.read_bytes())
        root = self.verifier_root
        original = root.mission_db
        root.mission_db = other
        try:
            with self.assertRaisesRegex(
                bootstrap.CooperativeProcessBootstrapError, "DB identity mismatch"
            ):
                bootstrap.CooperativeProcessBootstrapDependencies(
                    write_materializer=self.write_materializer,
                    verifier_root=root,
                ).validate()
        finally:
            root.mission_db = original

    def test_bootstrap_exports_no_direct_effect_surface(self):
        bootstrap.assert_no_effect_surface()


if __name__ == "__main__":
    unittest.main()

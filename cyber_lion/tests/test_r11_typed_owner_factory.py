#!/usr/bin/env python3
"""Isolated, original-owner R11 composition tests. Never access live MC or Docker."""
from __future__ import annotations

from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

CANDIDATE = Path(__file__).resolve().parents[1] / "mission_control/source_bound_preactivation_factory.py"
assert CANDIDATE.is_file()
from cyber_lion.mission_control import source_bound_preactivation_factory as factory
from cyber_lion.mission_control import cooperative_preactivation as pre
from cyber_lion.mission_control import cooperative_preactivation_bootstrap as boot
from cyber_lion.mission_control import global_scheduler


class RealOwnerCompositionTests(unittest.TestCase):
    def setUp(self):
        # Lazy import avoids counting the original TestCase twice in this run.
        from cyber_lion.tests.test_r11_preactivation_production_binding import (
            R11SourceBoundProductionAcceptance,
        )
        self.fix = R11SourceBoundProductionAcceptance(
            "test_original_preactivation_stepper_runs_r621_r616_r617_and_is_idempotent"
        )
        self.fix.setUp()
        self.addCleanup(self.fix.doCleanups)
        self.owners = (self.fix.r621, self.fix.r616, self.fix.worker, "MD001")

    def bound(self):
        return factory.compose_existing_owners(self.owners,
                                                canonical_db=self.fix.f.mission_db)

    def test_exact_existing_three_owners_bind_one_worker(self):
        bound = self.bound()
        self.assertIs(type(bound), boot.CooperativeSourceBoundPreactivation)
        self.assertIs(bound.preparation, self.fix.r621)
        self.assertIs(bound.control_materializer, self.fix.r616)
        self.assertIs(bound.worker_root, self.fix.worker)
        self.assertEqual(bound.worker_id, "MD001")
        self.assertEqual(bound.authority_effect, "NONE")
        provider = bound.provider()
        self.assertEqual(provider.worker_id, "MD001")
        self.assertEqual(provider.authority_effect, "NONE")

    def test_exact_bound_factory_executes_disposable_qualification_no_artifact_write(self):
        bound = self.bound()
        provider = bound.provider()
        import sqlite3
        with sqlite3.connect(self.fix.f.mission_db) as db:
            db.row_factory = sqlite3.Row
            result = pre.advance_preactivation(
                db, mission_id="M1", phase_id="BUILD", generation=1,
                provider=provider, now_fn=lambda: self.fix.f.now.isoformat()
                if hasattr(self.fix.f, "now") else "2026-10-12T10:00:00+00:00",
            )
            claim = db.execute(
                "SELECT state FROM mission_execution_assignments WHERE assignment_id=?",
                (self.fix.f.aid,)
            ).fetchone()
            receipts = db.execute(
                "SELECT COUNT(*) FROM mission_execution_receipts WHERE assignment_id=?",
                (self.fix.f.aid,)
            ).fetchone()[0]
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(claim["state"], "READY")
        self.assertEqual(receipts, 0)
        self.assertEqual(list(self.fix.f.fixture.root.iterdir()), [])

    def test_wrong_worker_denied(self):
        for name in ("MD002", "MD999", "Worker", ""):
            with self.subTest(name=name), self.assertRaisesRegex(
                factory.R11OwnerFactoryError, "one MD001"
            ):
                factory.compose_existing_owners(
                    (self.fix.r621,self.fix.r616,self.fix.worker,name),
                    canonical_db=self.fix.f.mission_db,
                )

    def test_nonexact_owner_tuple_denied(self):
        with self.assertRaisesRegex(factory.R11OwnerFactoryError, "tuple"):
            factory.compose_existing_owners(list(self.owners),canonical_db=self.fix.f.mission_db)
        with self.assertRaisesRegex(factory.R11OwnerFactoryError, "tuple"):
            factory.compose_existing_owners(self.owners[:3],canonical_db=self.fix.f.mission_db)
        with self.assertRaisesRegex(factory.R11OwnerFactoryError, "exact R6.21"):
            factory.compose_existing_owners((object(),*self.owners[1:]),canonical_db=self.fix.f.mission_db)

    def test_different_mission_db_same_contents_denied(self):
        with tempfile.TemporaryDirectory(prefix="lion-r11-mission-db-copy-") as d:
            copy=Path(d)/"untrusted.sqlite"
            shutil.copy2(self.fix.f.mission_db,copy)
            self.assertNotEqual(copy.stat().st_ino,self.fix.f.mission_db.stat().st_ino)
            with self.assertRaisesRegex(factory.R11OwnerFactoryError, "separate.*Mission Control"):
                factory.compose_existing_owners(self.owners,canonical_db=copy)

    def test_exporter_context_source_replacement_denied(self):
        exp = self.fix.r616.exporter
        old = exp.context_source
        exp.context_source = lambda _: None
        try:
            with self.assertRaisesRegex(boot.CooperativePreactivationBootstrapError,
                                        "preparation context substitution"):
                self.bound()
        finally:
            exp.context_source = old

    def test_publisher_database_substitution_denied(self):
        with tempfile.TemporaryDirectory(prefix="lion-r11-forged-evidence-") as d:
            publisher=self.fix.r616.exporter.publisher
            previous=publisher.path
            other=Path(d)/"foreign.sqlite"
            other.write_bytes(Path(previous).read_bytes())
            publisher.path = other
            try:
                with self.assertRaisesRegex(boot.CooperativePreactivationBootstrapError,
                                            "evidence DB mismatch"):
                    self.bound()
            finally:
                publisher.path=previous

    def test_context_privacy_alias_denied(self):
        previous = self.fix.worker.context_parent
        self.fix.worker.context_parent = self.fix.r616.context_root
        try:
            with self.assertRaisesRegex(boot.CooperativePreactivationBootstrapError,
                                        "worker private context"):
                self.bound()
        finally:
            self.fix.worker.context_parent = previous

    def test_external_source_tampering_detected_before_import(self):
        with tempfile.TemporaryDirectory(prefix="lion-r11-untrusted-owner-module-") as td:
            module=Path(td)/"owner_bindings.py"
            module.write_text("def build_current_owners(): return None\n",encoding="utf-8")
            module.chmod(0o644)
            good=sha256(module.read_bytes()).hexdigest()
            with self.assertRaisesRegex(factory.R11OwnerFactoryError,"digest mismatch"):
                factory._import_pinned_owner_source(module, "0"*64)
            fn=factory._import_pinned_owner_source(module,good)
            self.assertTrue(callable(fn))

    def test_external_module_with_foreign_name_denied(self):
        with tempfile.TemporaryDirectory(prefix="lion-r11-module-") as td:
            p=Path(td)/"forged.py"
            p.write_text("def unrelated(): pass\n",encoding="utf-8")
            p.chmod(0o644)
            with self.assertRaisesRegex(factory.R11OwnerFactoryError,"constructor unavailable"):
                factory._import_pinned_owner_source(p,sha256(p.read_bytes()).hexdigest())

    def test_real_bootstrap_rejects_unpinned_source_even_if_factory_matches_type(self):
        provider=self.bound()
        with tempfile.TemporaryDirectory(prefix="lion-r11-canonical-outer-") as td:
            repo=Path(td)/"source";repo.mkdir()
            ext=Path(td)/"external";ext.mkdir()
            artifact=ext/"source_bound_preactivation_factory.py"
            artifact.write_bytes(CANDIDATE.read_bytes())
            module_sha=sha256(artifact.read_bytes()).hexdigest()
            env={
                "LION_COOPERATIVE_PREACTIVATION_BOOTSTRAP_MODE":boot.SOURCE_BOUND_MODE,
                "LION_COOPERATIVE_PREACTIVATION_BOOTSTRAP_VERSION":boot.BOOTSTRAP_VERSION,
                "LION_COOPERATIVE_PREACTIVATION_REPOSITORY_ROOT":str(repo),
                "LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_MODULE_PATH":str(artifact),
                "LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_MODULE_SHA256":"f"*64,
                "LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_FACTORY":"build",
            }
            reg=pre.CooperativePreactivationRegistry()
            with self.assertRaisesRegex(boot.CooperativePreactivationBootstrapError,
                                        "digest mismatch"):
                boot.bootstrap_preactivation_provider(env,registry=reg)
            self.assertIsNone(reg.current())
            env["LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_MODULE_SHA256"]=module_sha
            # Source-only fixture injects exact existing owners, NOT live admissibility.
            with patch.object(boot,"_load_module",
                              return_value=SimpleNamespace(build=lambda: provider)):
                result=boot.bootstrap_preactivation_provider(env,registry=reg)
            self.assertEqual(result["state"],"READY")
            self.assertEqual(reg.current().worker_id,"MD001")

    def test_actual_factory_build_uses_pinned_external_owner_source(self):
        from contextlib import ExitStack
        from types import ModuleType
        import os
        bridge = ModuleType("lion_r11_test_only_existing_sources")
        bridge.current = self.owners
        sys.modules[bridge.__name__] = bridge
        self.addCleanup(lambda: sys.modules.pop(bridge.__name__, None))
        with tempfile.TemporaryDirectory(prefix="lion-r11-owner-source-test-") as td:
            source_file = Path(td) / "owner_source.py"
            source_file.write_text(
                "\n".join((
                    "import lion_r11_test_only_existing_sources as current",
                    "def build_current_owners():",
                    "    return current.current",
                )) + "\n",
                encoding="utf-8",
            )
            source_file.chmod(0o644)
            digest = sha256(source_file.read_bytes()).hexdigest()
            db = Path(self.fix.f.mission_db)
            prior_cwd = Path.cwd()
            try:
                os.chdir(db.parent)
                with ExitStack() as scope:
                    scope.enter_context(patch.dict(os.environ,{
                        factory._PATH_ENV: str(source_file),
                        factory._SHA_ENV: digest,
                    }))
                    scope.enter_context(patch.object(factory, "EXPECTED_MC_SOURCE_ROOT", db.parent))
                    scope.enter_context(patch.object(factory, "EXPECTED_DB", db))
                    scope.enter_context(patch.object(factory.socket, "gethostname",
                                                    return_value="LION-AUTH-LAB"))
                    result = factory.build()
                    self.assertIs(type(result), boot.CooperativeSourceBoundPreactivation)
                    self.assertIs(result.preparation, self.fix.r621)
                    self.assertEqual(result.worker_id, "MD001")
                    with patch.dict(os.environ, {factory._SHA_ENV: "0"*64}):
                        with self.assertRaisesRegex(factory.R11OwnerFactoryError,
                                                    "digest mismatch"):
                            factory.build()
            finally:
                os.chdir(prior_cwd)

    def test_pinned_source_never_uses_path_reopening_import_loader(self):
        with tempfile.TemporaryDirectory(prefix="lion-r11-pinned-once-") as td:
            p=Path(td)/"owner_source.py"
            p.write_text("def build_current_owners(): return 'FROM_PINNED_BYTES'\n",encoding="utf-8")
            p.chmod(0o644)
            digest=sha256(p.read_bytes()).hexdigest()
            with patch("importlib.util.spec_from_file_location",side_effect=AssertionError("second loader read forbidden")):
                fn=factory._import_pinned_owner_source(p,digest)
            self.assertEqual(fn(),"FROM_PINNED_BYTES")

    def test_world_writable_owner_source_rejected(self):
        with tempfile.TemporaryDirectory(prefix="lion-r11-owner-unsafe-mode-") as td:
            p=Path(td)/"owner_source.py"
            p.write_text("def build_current_owners(): return None\n",encoding="utf-8")
            p.chmod(0o666)
            with self.assertRaisesRegex(factory.R11OwnerFactoryError,"owner/mode not trusted"):
                factory._import_pinned_owner_source(p,sha256(p.read_bytes()).hexdigest())

    def test_malformed_pinned_source_does_not_leave_imported_module(self):
        with tempfile.TemporaryDirectory(prefix="lion-r11-pinned-malformed-") as td:
            p=Path(td)/"owner_source.py"
            p.write_text("def build_current_owners(:\n",encoding="utf-8")
            p.chmod(0o644)
            digest=sha256(p.read_bytes()).hexdigest()
            module_id="_lion_r11_exact_source_"+digest[:24]
            with self.assertRaisesRegex(factory.R11OwnerFactoryError,"failed closed"):
                factory._import_pinned_owner_source(p,digest)
            self.assertNotIn(module_id,sys.modules)

    def test_modified_owner_module_at_import_is_denied_and_removed_from_sys_modules(self):
        with tempfile.TemporaryDirectory(prefix="lion-r11-self-modifying-") as td:
            p=Path(td)/"owner_source.py"
            p.write_text(
                "from pathlib import Path\n"
                "Path(__file__).write_text('mutated',encoding='utf-8')\n"
                "def build_current_owners(): return None\n",
                encoding="utf-8",
            )
            p.chmod(0o644)
            digest=sha256(p.read_bytes()).hexdigest()
            module_id="_lion_r11_exact_source_"+digest[:24]
            with self.assertRaisesRegex(factory.R11OwnerFactoryError,"changed during import"):
                factory._import_pinned_owner_source(p,digest)
            self.assertNotIn(module_id,sys.modules)

    def test_modified_outer_module_at_import_is_denied_and_removed(self):
        with tempfile.TemporaryDirectory(prefix="lion-r11-outer-self-modifying-") as td:
            p=Path(td)/"outer_source.py"
            p.write_text(
                "from pathlib import Path\n"
                "Path(__file__).write_text('mutated',encoding='utf-8')\n"
                "def build(): return None\n",
                encoding="utf-8",
            )
            digest=sha256(p.read_bytes()).hexdigest()
            module_id="_lion_cooperative_preactivation_"+digest[:20]
            with self.assertRaisesRegex(boot.CooperativePreactivationBootstrapError,"changed during import"):
                boot._load_module(p,digest)
            self.assertNotIn(module_id,sys.modules)

    def test_outer_bootstrap_executes_sha_pinned_bytes_without_loader_reopen(self):
        with tempfile.TemporaryDirectory(prefix="lion-r11-outer-pin-") as td:
            p=Path(td)/"outer_source.py"
            p.write_bytes(b"def build(): return 123\n")
            digest=sha256(p.read_bytes()).hexdigest()
            with patch("importlib.util.spec_from_file_location",
                       side_effect=AssertionError("unverified loader reopen forbidden")):
                m=boot._load_module(p,digest)
            self.assertEqual(m.build(),123)

    def test_factory_production_entrypoint_rejects_noncanonical_host(self):
        with patch.object(factory.socket,"gethostname",return_value="MOON"):
            with self.assertRaisesRegex(factory.R11OwnerFactoryError,
                                        "canonical Mission Control host"):
                factory.build()


if __name__ == "__main__":
    unittest.main()

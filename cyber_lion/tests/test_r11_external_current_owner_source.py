"""Source-only acceptance for external owner source. Disposable SQLite only."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from types import ModuleType
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
CHECKOUT=ROOT
assert CHECKOUT.is_dir()
sys.path.insert(0,str(CHECKOUT))
from cyber_lion.tests.test_r11_current_owner_wiring import R11OriginalCurrentOwnersTest
from cyber_lion.enterprise.cooperative_runtime_preparation_provider import CooperativeRuntimePreparationProvider
from cyber_lion.enterprise.cooperative_control_plane_materializer import CooperativeControlPlaneMaterializer
from cyber_lion.enterprise.cooperative_runtime_root import CooperativeRuntimeCompositionRoot
from cyber_lion.mission_control.cooperative_preactivation_bootstrap import CooperativeSourceBoundPreactivation
from cyber_lion.mission_control import cooperative_preactivation as pre

spec=importlib.util.spec_from_file_location(
    "lion_r11_external_current_owner_source",ROOT/"LION/architecture/v1_5/cooperative_production_r1/r11_external_current_owner_source.py",
)
source=importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


class R11ExternalSourceAcceptance(unittest.TestCase):
    def setUp(self):
        self.fixture=R11OriginalCurrentOwnersTest(
            "test_builds_three_original_types_same_physical_mission_db"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.bridge=ModuleType("_lion_r11_test_only_current_source_bridge")
        self.bridge.original_sources=self.fixture.inputs
        sys.modules[self.bridge.__name__]=self.bridge
        self.addCleanup(lambda:sys.modules.pop(self.bridge.__name__,None))

    def configure(self, text):
        tmp=tempfile.TemporaryDirectory(prefix="lion-r11-external-sources-")
        self.addCleanup(tmp.cleanup)
        file=Path(tmp.name)/"independent_owner_sources.py"
        file.write_text(text,encoding="utf-8")
        file.chmod(0o644)
        env={
            source._SOURCE_PATH:str(file),
            source._SOURCE_HASH:sha256(file.read_bytes()).hexdigest(),
            source._SOURCE_VERSION:source.VERSION,
        }
        return file,env

    def original_module(self):
        return self.configure(
            "from _lion_r11_test_only_current_source_bridge import original_sources\n"
            "def build_current_owner_sources():\n"
            "    return original_sources\n"
        )

    def test_no_upstream_provider_is_unbound(self):
        with patch.dict(os.environ,{
                source._SOURCE_PATH:"",
                source._SOURCE_HASH:"",
                source._SOURCE_VERSION:source.VERSION,
            }):
            with self.assertRaisesRegex(source.R11ExternalCurrentOwnerError,
                                        "path unavailable"):
                source.build_current_owners()

    def test_bad_sha_denied_before_source_execution(self):
        file,env=self.original_module()
        env[source._SOURCE_HASH]="0"*64
        with patch.dict(os.environ,env):
            with self.assertRaisesRegex(source.R11ExternalCurrentOwnerError,
                                        "digest mismatch"):
                source.build_current_owners()
        self.assertFalse(self.fixture.inputs.worker_materialization_db.exists())

    def test_missing_original_source_symbol_denied(self):
        file,env=self.configure("def fake(): return None\n")
        with patch.dict(os.environ,env):
            with self.assertRaisesRegex(source.R11ExternalCurrentOwnerError,
                                        "callable unavailable"):
                source.build_current_owners()

    def test_untyped_source_denied_before_private_store_init(self):
        file,env=self.configure(
            "def build_current_owner_sources():\n"
            "    return {}\n"
        )
        with patch.dict(os.environ,env):
            with self.assertRaisesRegex(source.R11ExternalCurrentOwnerError,
                                        "exact CurrentOwnerSources"):
                source.build_current_owners()
        self.assertFalse(self.fixture.inputs.worker_materialization_db.exists())

    def test_original_three_owner_types_and_samefile(self):
        file,env=self.original_module()
        with patch.dict(os.environ,env):
            owners=source.build_current_owners()
        self.assertEqual([type(x) for x in owners[:3]],[
            CooperativeRuntimePreparationProvider,
            CooperativeControlPlaneMaterializer,
            CooperativeRuntimeCompositionRoot,
        ])
        self.assertEqual(owners[3],"MD001")
        self.assertTrue(Path(owners[0].mission_db).samefile(owners[1].mission_db))
        self.assertTrue(Path(owners[0].mission_db).samefile(owners[2].mission_db))
        self.assertIs(owners[1].exporter.context_source,owners[0])
        self.assertIs(owners[1].exporter.admission_source,owners[0].admission_source)
        self.assertIs(CooperativeSourceBoundPreactivation(*owners).validate().preparation,owners[0])

    def test_original_preactivation_held_to_ready_no_artifact_execution(self):
        file,env=self.original_module()
        with patch.dict(os.environ,env):
            owners=source.build_current_owners()
        provider=CooperativeSourceBoundPreactivation(*owners).provider()
        with sqlite3.connect(self.fixture.fixture.f.mission_db) as db:
            db.row_factory=sqlite3.Row
            result=pre.advance_preactivation(
                db,mission_id="M1",phase_id="BUILD",generation=1,
                provider=provider,now_fn=lambda:"2026-10-12T10:00:00+00:00",
            )
            receipts=db.execute(
                "SELECT COUNT(*) FROM mission_execution_receipts WHERE assignment_id=?",
                (self.fixture.fixture.f.aid,),
            ).fetchone()[0]
        self.assertEqual(result["state"],"PASS",result)
        self.assertEqual(receipts,0)
        self.assertEqual(list(self.fixture.fixture.f.fixture.root.iterdir()),[])

    def test_file_world_writable_denied_before_import(self):
        file,env=self.original_module()
        file.chmod(0o666)
        with patch.dict(os.environ,env):
            with self.assertRaisesRegex(source.R11ExternalCurrentOwnerError,
                                        "owner/mode not trusted"):
                source.build_current_owners()

    def test_original_source_loader_does_not_reopen_for_exec(self):
        file,env=self.original_module()
        with patch.dict(os.environ,env),patch(
            "importlib.util.spec_from_file_location",
            side_effect=AssertionError("second unverified import reopen"),
        ):
            owners=source.build_current_owners()
        self.assertEqual(owners[3],"MD001")

    def test_foreign_original_source_worker_denied(self):
        self.bridge.original_sources=replace(self.fixture.inputs,worker_id="MD032")
        file,env=self.original_module()
        with patch.dict(os.environ,env):
            with self.assertRaisesRegex(Exception,"only MD001"):
                source.build_current_owners()

    def test_currentness_source_substitution_denied(self):
        self.bridge.original_sources=replace(
            self.fixture.inputs,currentness_source=object()
        )
        file,env=self.original_module()
        with patch.dict(os.environ,env):
            with self.assertRaisesRegex(Exception,"source currentness/trust mismatch"):
                source.build_current_owners()

    def test_outer_source_bound_factory_integrates_all_three_pinned_levels(self):
        from cyber_lion.mission_control import source_bound_preactivation_factory as outer
        file,env=self.original_module()
        external_module=ROOT/"LION/architecture/v1_5/cooperative_production_r1/r11_external_current_owner_source.py"
        env.update({
            outer._PATH_ENV:str(external_module),
            outer._SHA_ENV:sha256(external_module.read_bytes()).hexdigest(),
        })
        db=Path(self.fixture.inputs.mission_db)
        original_cwd=Path.cwd()
        try:
            os.chdir(db.parent)
            with patch.dict(os.environ,env):
                with patch.object(outer,"EXPECTED_MC_SOURCE_ROOT",db.parent):
                    with patch.object(outer,"EXPECTED_DB",db):
                        with patch.object(outer.socket,"gethostname",return_value="LION-AUTH-LAB"):
                            bound=outer.build()
            self.assertIs(type(bound),CooperativeSourceBoundPreactivation)
            self.assertEqual(bound.worker_id,"MD001")
            self.assertTrue(Path(bound.preparation.mission_db).samefile(db))
            self.assertTrue(Path(bound.control_materializer.mission_db).samefile(db))
            self.assertTrue(Path(bound.worker_root.mission_db).samefile(db))
            self.assertEqual(bound.authority_effect,"NONE")
        finally:
            os.chdir(original_cwd)

    def test_self_modified_pinned_source_denied_and_namespace_cleared(self):
        file,env=self.configure(
            "from pathlib import Path\n"
            "Path(__file__).write_text('tampered',encoding='utf-8')\n"
            "def build_current_owner_sources(): return None\n"
        )
        expected_id="_lion_r11_current_owner_evidence_"+env[source._SOURCE_HASH][:24]
        with patch.dict(os.environ,env):
            with self.assertRaisesRegex(source.R11ExternalCurrentOwnerError,
                                        "changed during import"):
                source.build_current_owners()
        self.assertNotIn(expected_id,sys.modules)
        self.assertFalse(self.fixture.inputs.worker_materialization_db.exists())



if __name__=="__main__":
    unittest.main()

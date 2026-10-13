"""Original-owner assembly from typed existing sources; fixtures are NOT live."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
from hashlib import sha256
from types import ModuleType
import tempfile
import os
import sys

from cyber_lion.enterprise.r11_original_current_owner_builder import (
    OriginalPreparationEvidenceTrust,
    OriginalR11ServiceOwners,
    R11OriginalCurrentSourceError,
    build_current_owner_sources,
)
from cyber_lion.enterprise.r11_canonical_pdp_evidence import (
    SQLiteR11CanonicalPDPEvidenceReader,
)
from cyber_lion.contracts.runtime_enforcement import PDPSourceTrustBinding
from cyber_lion.mission_control.cooperative_current_owner_wiring import (
    CurrentOwnerSources,assemble_original_owners,
)
from cyber_lion.enterprise.cooperative_runtime_preparation_provider import (
    CooperativeRuntimePreparationProvider,
)
from cyber_lion.enterprise.cooperative_control_plane_materializer import (
    CooperativeControlPlaneMaterializer,
)
from cyber_lion.enterprise.cooperative_runtime_root import (
    CooperativeRuntimeCompositionRoot,
)
from cyber_lion.tests.test_r11_current_owner_wiring import R11OriginalCurrentOwnersTest


class FixtureOriginalPreparationService:
    def __init__(self,callback,trust):
        self.callback=callback
        self.source_id=trust.source_id
        self.source_instance_id=trust.source_instance_id
        self.implementation_digest=trust.source_implementation_digest
        self.trust_anchor_id=trust.trust_anchor_id
        self.trust_anchor_digest=trust.trust_anchor_digest
        self.change_after=False

    def resolve(self,aid):
        value=self.callback(aid)
        if self.change_after:self.source_instance_id="drift-after-original-resolve"
        return value


class FixtureIndependentPolicy:
    def __init__(self,trust):
        self.source_id=trust.source_id
        self.source_instance_id=trust.source_instance_id
        self.implementation_digest=trust.source_implementation_digest
        self.trust_anchor_id=trust.trust_anchor_id
        self.trust_anchor_digest=trust.trust_anchor_digest

    def current_policy_binding(self,binding):
        return binding


class OriginalR11ServiceBuilderTest(unittest.TestCase):
    def setUp(self):
        # Original R6.21/R6.16/R6.17 test instance, all disposable.
        self.fixture=R11OriginalCurrentOwnersTest(
            "test_builds_three_original_types_same_physical_mission_db"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        src=self.fixture.inputs
        self.prep_trust=OriginalPreparationEvidenceTrust(
            "r11-r620-original", "r11-r620-original:test",
            "a"*64, "r620-test-root", "b"*64,
        )
        self.preparation=FixtureOriginalPreparationService(
            src.preparation_evidence_source,self.prep_trust,
        )
        self.pdp_trust=src.admission_engine._source_trust
        self.policy_trust=PDPSourceTrustBinding(
            "policy-original", "policy-original:test",
            "c"*64,"policy-anchor","d"*64,
        ).validate()
        policy=FixtureIndependentPolicy(self.policy_trust)
        self.pdp_db=self.fixture.fixture.state/"test-preprovisioned-pdp.sqlite"
        with sqlite3.connect(self.pdp_db) as db:
            db.execute(
                "CREATE TABLE r11_original_pdp_evidence ("
                "request_id TEXT NOT NULL, gate_event_id TEXT NOT NULL, "
                "record_json TEXT NOT NULL, PRIMARY KEY(request_id,gate_event_id))"
            )
        self.pdp_db.chmod(0o600)
        self.reader=SQLiteR11CanonicalPDPEvidenceReader(
            database=self.pdp_db,
            source_trust=self.pdp_trust,
            current_policy_source=policy,
            current_policy_trust=self.policy_trust,
            now_fn=src.now_fn,
        )
        self.owners=OriginalR11ServiceOwners(
            repository="DonkeyJJLove/ai_platform",
            mission_id="M1",  # disposable fixture only, replaces protected constant under patch
            worker_id="MD001",
            mission_db=src.mission_db,
            artifact_root=src.artifact_root,
            carrier_root=src.carrier_root,
            provider_evidence_db=src.provider_evidence_db,
            worker_context_parent=src.worker_context_parent,
            worker_verifier_parent=src.worker_verifier_parent,
            worker_materialization_db=src.worker_materialization_db,
            worker_runtime_state_db=src.worker_runtime_state_db,
            preparation_source=self.preparation,
            preparation_trust=self.prep_trust,
            authority_admission=src.authority_admission,
            pdp_source=self.reader,
            pdp_trust=self.pdp_trust,
            admission_replay_guard=self.fixture.admission_replay,
            admission_source=src.admission_source,
            currentness_source=src.currentness_source,
            currentness_trust=src.currentness_trust,
            dispatch_source=src.dispatch_source,
            runtime_identity_source=src.runtime_identity_source,
            provisioning_binding_source=src.provisioning_binding_source,
            transfer_binding_source=src.transfer_binding_source,
            worker_durable_admission_trust=src.worker_durable_admission_trust,
            now_fn=src.now_fn,
        )

    def build_test_scope(self, owners=None):
        # Test M1 is deliberately NOT a production Application Factory mission.
        with patch("cyber_lion.enterprise.r11_original_current_owner_builder.MISSION","M1"):
            return build_current_owner_sources(self.owners if owners is None else owners)

    def test_requires_exact_real_application_factory_mission_in_production_constant(self):
        with self.assertRaisesRegex(R11OriginalCurrentSourceError,"scope must be exact"):
            build_current_owner_sources(self.owners)
        self.assertFalse(self.owners.worker_materialization_db.exists())

    def test_assembles_original_non_authorizing_sources_without_private_sqlite(self):
        before={p.name for p in self.fixture.fixture.state.iterdir()}
        result=self.build_test_scope()
        self.assertIs(type(result),CurrentOwnerSources)
        self.assertIs(result.authority_admission,self.owners.authority_admission)
        self.assertIs(result.admission_engine._authority,self.owners.authority_admission)
        self.assertIs(result.admission_engine._source,self.reader)
        self.assertIs(result.admission_engine._replay,self.fixture.admission_replay)
        self.assertEqual(result.admission_engine._source_trust,self.pdp_trust)
        self.assertEqual(result.worker_id,"MD001")
        self.assertEqual(before,{p.name for p in self.fixture.fixture.state.iterdir()})
        self.assertFalse(self.owners.worker_materialization_db.exists())

    def test_original_typed_R621_R616_R617_constructors_accept_output(self):
        source=self.build_test_scope()
        parts=assemble_original_owners(source)
        self.assertEqual([type(p) for p in parts[:3]],[
            CooperativeRuntimePreparationProvider,
            CooperativeControlPlaneMaterializer,
            CooperativeRuntimeCompositionRoot,
        ])
        self.assertEqual(parts[3],"MD001")
        self.assertIs(parts[0].admission_engine._authority,
                      parts[1].exporter.authority_admission)
        self.assertIs(parts[2].authority_admission,
                      parts[1].exporter.authority_admission)

    def test_resolve_original_preparation_evidence_preserves_assignment(self):
        sources=self.build_test_scope()
        value=sources.preparation_evidence_source(self.fixture.fixture.f.aid)
        self.assertEqual(value.proposal.mission_id,"M1")

    def test_missing_original_preparation_source_is_denied_before_private_db(self):
        with self.assertRaisesRegex(R11OriginalCurrentSourceError,
                                    "original preparation source resolver"):
            self.build_test_scope(replace(self.owners,preparation_source=object()))
        self.assertFalse(self.owners.worker_materialization_db.exists())

    def test_preparation_source_trust_substitution_denied(self):
        changed=replace(self.prep_trust,source_instance_id="foreign")
        with self.assertRaisesRegex(R11OriginalCurrentSourceError,
                                    "preparation source/trust mismatch"):
            self.build_test_scope(replace(self.owners,preparation_trust=changed))

    def test_original_preparation_source_drift_after_resolve_denied(self):
        source=self.build_test_scope()
        self.preparation.change_after=True
        with self.assertRaisesRegex(R11OriginalCurrentSourceError,
                                    "drift after resolve"):
            source.preparation_evidence_source(self.fixture.fixture.f.aid)

    def test_incorrect_PDP_reader_type_denied_before_state(self):
        with self.assertRaisesRegex(R11OriginalCurrentSourceError,
                                    "read-only PDP evidence source"):
            self.build_test_scope(replace(self.owners,pdp_source=object()))
        self.assertFalse(self.owners.worker_materialization_db.exists())

    def test_PDP_reader_trust_mismatch_denied_before_state(self):
        trust=replace(self.pdp_trust,source_instance_id="foreign-pdp")
        with self.assertRaisesRegex(R11OriginalCurrentSourceError,
                                    "PDP source/trust mismatch"):
            self.build_test_scope(replace(self.owners,pdp_trust=trust))
        self.assertFalse(self.owners.worker_materialization_db.exists())

    def test_missing_preprovisioned_original_PDP_store_denied(self):
        self.pdp_db.unlink()
        with self.assertRaisesRegex(Exception,"PDP evidence"):
            self.build_test_scope()

    def test_foreign_mission_denied_even_if_other_sources_look_valid(self):
        with self.assertRaisesRegex(R11OriginalCurrentSourceError,
                                    "scope must be exact"):
            self.build_test_scope(replace(self.owners,mission_id="M2"))

    def test_non_MD001_worker_denied(self):
        with self.assertRaisesRegex(R11OriginalCurrentSourceError,
                                    "scope must be exact"):
            self.build_test_scope(replace(self.owners,worker_id="MD002"))

    def test_replay_guard_unbound_denied_before_R621(self):
        with self.assertRaisesRegex(R11OriginalCurrentSourceError,
                                    "durable replay"):
            self.build_test_scope(replace(self.owners,admission_replay_guard=object()))

    def test_currentness_trust_substitution_denied_before_private_state(self):
        trust=replace(self.owners.currentness_trust,source_instance_id="foreign-epoch")
        with self.assertRaisesRegex(R11OriginalCurrentSourceError,
                                    "currentness source/trust mismatch"):
            self.build_test_scope(replace(self.owners,currentness_trust=trust))

    def test_runtime_source_must_be_existing_exact_SQLite(self):
        with self.assertRaisesRegex(R11OriginalCurrentSourceError,
                                    "pre-existing original RuntimeAdmission SQLite source"):
            self.build_test_scope(replace(self.owners,admission_source=object()))

    def test_exact_sha_pinned_external_adapter_calls_original_builder(self):
        # Demonstrate the ACTUAL zero-arg external API expected by the
        # original R11 loader. Only this disposable test supplies original
        # objects through its temporary process-only service fixture.
        from cyber_lion.tests.test_r11_external_current_owner_source import (
            source as externally_pinned,
        )
        registration=ModuleType("_lion_r11_fixture_original_service_only")
        registration.owner_handles=self.owners
        sys.modules[registration.__name__]=registration
        self.addCleanup(lambda:sys.modules.pop(registration.__name__,None))
        temp=tempfile.TemporaryDirectory(prefix="r11-exact-original-owner-factory-")
        self.addCleanup(temp.cleanup)
        file=Path(temp.name)/"original_build_current_owner_sources.py"
        file.write_text(
            "from _lion_r11_fixture_original_service_only import owner_handles\n"
            "from cyber_lion.enterprise.r11_original_current_owner_builder "
            "import build_current_owner_sources as assemble\n"
            "def build_current_owner_sources():\n"
            "    return assemble(owner_handles)\n",
            encoding="utf-8",
        )
        file.chmod(0o600)
        env={
            externally_pinned._SOURCE_PATH:str(file),
            externally_pinned._SOURCE_HASH:sha256(file.read_bytes()).hexdigest(),
            externally_pinned._SOURCE_VERSION:externally_pinned.VERSION,
        }
        with patch.dict(os.environ,env), patch(
            "cyber_lion.enterprise.r11_original_current_owner_builder.MISSION","M1",
        ):
            prep,material,root,worker=externally_pinned.build_current_owners()
        self.assertIs(type(prep),CooperativeRuntimePreparationProvider)
        self.assertIs(type(material),CooperativeControlPlaneMaterializer)
        self.assertIs(type(root),CooperativeRuntimeCompositionRoot)
        self.assertIs(prep.admission_engine._authority,
                      material.exporter.authority_admission)
        self.assertIs(root.authority_admission,
                      material.exporter.authority_admission)
        self.assertEqual(worker,"MD001")

    def test_preparation_source_drift_before_resolve_denied(self):
        source=self.build_test_scope()
        self.preparation.source_instance_id="foreign-preparation"
        with self.assertRaisesRegex(R11OriginalCurrentSourceError,
                                    "drift before resolve"):
            source.preparation_evidence_source(self.fixture.fixture.f.aid)


if __name__=="__main__":
    unittest.main()

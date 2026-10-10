"""R11 existing-owner R6.21 -> R6.16 -> R6.17 production binding acceptance.

Uses disposable SQLite, canonical producer classes, synthetic authority fixture.
No live RuntimeAdmission, host effect or external qualification transport.
"""
from __future__ import annotations

from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.cooperative_control_plane_materializer import (
    CooperativeControlPlaneMaterializer,
)
from cyber_lion.enterprise.cooperative_context_resolver import PinnedCooperativeContextResolver
from cyber_lion.enterprise.cooperative_runtime_evidence_exporter import (
    CooperativeRuntimeEvidenceExporter,
)
from cyber_lion.enterprise.cooperative_runtime_evidence_sources import (
    SQLiteCooperativeRuntimeEvidencePublisher,
    SQLiteContextPinSource,
    SQLiteEvidenceRuntimeAdmissionSource,
    SQLiteFleetDispatchSource,
    SQLiteProvisioningBindingSource,
    SQLiteRuntimeIdentitySource,
    SQLiteEffectTimeCurrentnessSource,
    SQLiteTransferBindingSource,
)
from cyber_lion.enterprise.cooperative_runtime_root import CooperativeRuntimeCompositionRoot
from cyber_lion.mission_control import cooperative_preactivation as pre
from cyber_lion.mission_control import cooperative_preactivation_bootstrap as boot
from cyber_lion.mission_control import cooperative_production as cp
from cyber_lion.mission_control import global_scheduler
from cyber_lion.tests import test_executor_sandbox as sb
from cyber_lion.tests import test_runtime_currentness as rc
from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.tests.test_cooperative_runtime_preparer import D, HEAD, NOW, REPO, FakeAdmission
from cyber_lion.tests.test_cooperative_runtime_preparation_provider import (
    CooperativeRuntimePreparationProviderTests,
)


class R11SourceBoundProductionAcceptance(unittest.TestCase):
    def setUp(self):
        self.f=CooperativeRuntimePreparationProviderTests(
            "test_provider_drives_existing_r616_to_ready_from_current_ledger"
        )
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.base=self.f.base
        # R6.20's provisioned logical identity is drone:r620. Build a fresh
        # canonical HELD assignment with exactly that identity instead of
        # borrowing R6.21's independent LD001 fixture. No DB tampering.
        original=json.loads(self.f.fixture.assignment["input_json"])
        with sqlite3.connect(self.f.mission_db) as db:
            db.row_factory=sqlite3.Row
            self.f.aid=global_scheduler.create_held_assignment(
                db,"M1","BUILD__COOP_PREACTIVATE",
                self.f.fixture.provisioned.drone_id,"MD001",original,
                lambda:NOW.isoformat(),lease_generation=1,
            )
        self.r621=self.f.provider()
        self.carriers=self.base/"r11-context-carriers"
        self.carriers.mkdir()
        self.provider_db=self.base/"r11-provider-evidence.sqlite"
        publisher=SQLiteCooperativeRuntimeEvidencePublisher(self.provider_db)
        currentness=rc.Source(
            self.f.fixture.authority,
            policy=self.f.fixture.evidence.pdp_result.applied.policy_binding,
            obs=self.f.fixture.evidence.pdp_result.applied.observability_state,
        )
        dispatch=sb.DispatchSource(self.f.fixture.dispatch)
        def transfer(aid,purpose):
            return {
                "repository":REPO,
                "source_head":HEAD,
                "mission_id":"M1",
                "assignment_id":aid,
                "conversation_id":"conversation-r11-source-bound",
                "binding_epoch":1,
                "generation":1,
                "lease_generation":1,
                "context_digest":D("r11-context"),
                "projection_digest":D("r11-projection"),
                "request_id":"request-r11-"+purpose.lower(),
                "producer_ref":"MISSION_CONTROL",
            }

        exporter=CooperativeRuntimeEvidenceExporter(
            publisher=publisher,
            context_source=self.r621,
            admission_source=self.f.store,
            admission_trust=self.r621.admission_trust(),
            authority_admission=FakeAdmission(),
            currentness_source=currentness,
            currentness_trust=rc.trust(),
            dispatch_source=dispatch,
            runtime_identity_source=lambda runtime:self.r621(self.f.aid).execution.identity,
            provisioning_binding_source=lambda aid:self.r621(aid).provisioning,
            context_pin_source=lambda aid: (_ for _ in ()).throw(
                AssertionError("R6.16 must supply the actual context pin")
            ),
            transfer_binding_source=transfer,
            now_fn=lambda:NOW,
        )
        self.r616=CooperativeControlPlaneMaterializer(
            mission_db=self.f.mission_db,
            provider_context_root=self.carriers,
            exporter_template=exporter,
            ttl_seconds=10,
        )

        self.private=self.base/"r11-worker-private"
        self.contexts=self.private/"contexts"
        self.verifiers=self.private/"verifiers"
        self.state=self.private/"state"
        for directory in (self.contexts,self.verifiers,self.state):
            directory.mkdir(parents=True)
        now_fn=lambda:NOW
        admission=SQLiteEvidenceRuntimeAdmissionSource(
            self.provider_db,self.r621.admission_trust(),now_fn=now_fn
        )
        pins=SQLiteContextPinSource(self.provider_db,now_fn=now_fn)
        dispatch_source=SQLiteFleetDispatchSource(self.provider_db,now_fn=now_fn)
        identity_source=SQLiteRuntimeIdentitySource(self.provider_db,now_fn=now_fn)
        provisioning_source=SQLiteProvisioningBindingSource(self.provider_db,now_fn=now_fn)
        transfer_source=SQLiteTransferBindingSource(self.provider_db,now_fn=now_fn)
        current_source=SQLiteEffectTimeCurrentnessSource(
            self.provider_db,rc.trust(),now_fn=now_fn
        )

        def resolver(aid):
            pin=pins(aid)
            return PinnedCooperativeContextResolver(
                mission_db=self.f.mission_db,
                context_directory=self.carriers,
                pins=(pin,),
                admission_source=admission,
                admission_trust=self.r621.admission_trust(),
                dispatch_source=dispatch_source,
                runtime_identity_source=identity_source,
                now_fn=now_fn,
            )

        self.resolver_for=resolver
        durable_trust=RuntimeAdmissionSourceTrustBinding(
            "r11-private-admission",
            "r11-private-admission:fixture",
            rt.Z,
            "r11-private-root",
            rt.F,
        ).validate()
        self.worker=CooperativeRuntimeCompositionRoot(
            mission_db=self.f.mission_db,
            artifact_root=self.f.fixture.root,
            context_parent=self.contexts,
            verifier_parent=self.verifiers,
            materialization_db=self.state/"materialization.sqlite",
            runtime_state_db=self.state/"runtime-state.sqlite",
            context_source=lambda aid:resolver(aid)(aid),
            qualification_context_source=lambda aid:resolver(aid).resolve_for_qualification(aid),
            upstream_admission_source=admission,
            upstream_admission_trust=self.r621.admission_trust(),
            durable_admission_trust=durable_trust,
            authority_admission=FakeAdmission(),
            currentness_source=current_source,
            currentness_trust=rc.trust(),
            dispatch_source=dispatch_source,
            runtime_identity_source=identity_source,
            provisioning_binding_source=provisioning_source,
            transfer_binding_source=transfer_source,
            now_fn=now_fn,
        )
        self.bound=boot.CooperativeSourceBoundPreactivation(
            self.r621,self.r616,self.worker,"MD001"
        )

    def release_canonical(self):
        provider=self.bound.provider()
        with sqlite3.connect(self.f.mission_db) as db:
            db.row_factory=sqlite3.Row
            cp._materialize_and_release(
                db,self.f.aid,materializer=provider.write_materializer,
                expected_kind=cp.WRITE_MATERIALIZATION_KIND,
                expected_provider=cp.WRITE_PROVIDER_ID,
                now_fn=lambda:NOW.isoformat(),
            )
        return provider

    def test_ready_without_release_is_denied_by_canonical_resolver(self):
        # Construct the real pinned R6.16 provider evidence first, then remove
        # only the canonical release ledger row in the disposable fixture.
        # This isolates the release fence rather than failing early on no pin.
        self.release_canonical()
        with sqlite3.connect(self.f.mission_db) as db:
            db.execute("DELETE FROM mission_assignment_release_evidence WHERE assignment_id=?",
                       (self.f.aid,))
        with self.assertRaisesRegex(Exception,"qualification release evidence unavailable"):
            self.resolver_for(self.f.aid).resolve_for_qualification(self.f.aid)

    def test_ready_tampered_release_digest_is_denied(self):
        self.release_canonical()
        with sqlite3.connect(self.f.mission_db) as db:
            db.execute("UPDATE mission_assignment_release_evidence SET evidence_digest=? "
                       "WHERE assignment_id=?",("0"*64,self.f.aid))
        with self.assertRaisesRegex(Exception,"qualification release digest mismatch"):
            self.resolver_for(self.f.aid).resolve_for_qualification(self.f.aid)

    def test_ready_expired_driver_lease_is_denied(self):
        self.release_canonical()
        with sqlite3.connect(self.f.mission_db) as db:
            db.execute("UPDATE mission_execution_drivers SET lease_expires_at=? WHERE mission_id='M1'",
                       ("2020-01-01T00:00:00+00:00",))
        with self.assertRaisesRegex(Exception,"expired driver lease"):
            self.resolver_for(self.f.aid).resolve_for_qualification(self.f.aid)

    def test_ready_expired_assignment_lease_is_denied(self):
        self.release_canonical()
        with sqlite3.connect(self.f.mission_db) as db:
            db.execute("UPDATE mission_execution_assignments SET lease_expires_at=? WHERE assignment_id=?",
                       ("2020-01-01T00:00:00+00:00",self.f.aid))
        with self.assertRaisesRegex(Exception,"expired assignment lease"):
            self.resolver_for(self.f.aid).resolve_for_qualification(self.f.aid)

    def test_claimed_requires_its_own_valid_execution_lease(self):
        self.release_canonical()
        with sqlite3.connect(self.f.mission_db) as db:
            db.execute("UPDATE mission_execution_assignments SET state='CLAIMED', "
                       "lease_expires_at=NULL WHERE assignment_id=?",(self.f.aid,))
        with self.assertRaisesRegex(Exception,"claimed assignment lease missing"):
            self.resolver_for(self.f.aid)(self.f.aid)

    def test_original_preactivation_stepper_runs_r621_r616_r617_and_is_idempotent(self):
        # Existing Mission Control scheduler invokes the same
        # advance_preactivation edge used in production; no second scheduler.
        provider=self.bound.provider()
        with sqlite3.connect(self.f.mission_db) as db:
            db.row_factory=sqlite3.Row
            result=pre.advance_preactivation(
                db,mission_id="M1",phase_id="BUILD",generation=1,
                provider=provider,now_fn=lambda:NOW.isoformat(),
            )
            stored=pre._qualification_artifact(db,"M1","BUILD")
            journal=pre._journal_artifact(db,"M1","BUILD")
            again=pre.advance_preactivation(
                db,mission_id="M1",phase_id="BUILD",generation=1,
                provider=provider,now_fn=lambda:NOW.isoformat(),
            )
            receipts=db.execute(
                "SELECT COUNT(*) FROM mission_execution_receipts "
                "WHERE assignment_id=?",(self.f.aid,)
            ).fetchone()[0]
            row=db.execute(
                "SELECT state FROM mission_execution_assignments WHERE assignment_id=?",
                (self.f.aid,),
            ).fetchone()
        self.assertEqual(result["state"],"PASS")
        self.assertEqual(again["state"],"PASS")
        self.assertEqual(again["qualification_digest"],result["qualification_digest"])
        self.assertEqual(journal["content"]["state"],"QUALIFIED")
        self.assertEqual(stored["content"]["qualification_digest"],result["qualification_digest"])
        self.assertEqual(row["state"],"READY")
        self.assertEqual(receipts,0)
        self.assertEqual(self.r621.status(self.f.aid)["state"],"PUBLISHED")
        self.assertEqual(list(self.f.fixture.root.iterdir()),[])

    def test_exact_owners_linked_then_runtime_receipt_readback_no_artifact_write(self):
        self.assertIs(self.bound.validate(),self.bound)
        provider=self.release_canonical()
        qualification=provider.qualifier(self.f.aid,"MD001")
        with sqlite3.connect(self.f.mission_db) as db:
            db.row_factory=sqlite3.Row
            assignment=dict(db.execute(
                "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
                (self.f.aid,),
            ).fetchone())
            release=global_scheduler.held_assignment_release_evidence(db,self.f.aid)
            receipt_count=db.execute(
                "SELECT COUNT(*) FROM mission_execution_receipts WHERE assignment_id=?",
                (self.f.aid,),
            ).fetchone()[0]
        self.assertEqual(
            pre._validate_qualification(
                qualification,assignment=assignment,
                worker_id="MD001",release=release,
            ),
            qualification,
        )
        self.assertEqual(assignment["state"],"READY")
        self.assertEqual(receipt_count,0)
        self.assertEqual(self.r621.status(self.f.aid)["state"],"PUBLISHED")
        self.assertTrue(
            self.f.store.is_current(qualification["runtime_admission_digest"])
        )
        self.assertEqual(list(self.f.fixture.root.iterdir()),[])
        self.assertEqual(
            qualification["control_plane_evidence_digest"],
            release["evidence"]["evidence_digest"],
        )
        self.assertNotEqual(
            qualification["release_evidence_digest"],
            qualification["control_plane_evidence_digest"],
        )

    def test_mismatched_producer_and_publisher_deny_before_provider_binding(self):
        old=self.r616.exporter.context_source
        self.r616.exporter.context_source=lambda _aid:None
        try:
            with self.assertRaisesRegex(
                boot.CooperativePreactivationBootstrapError,
                "preparation context substitution",
            ):
                self.bound.validate()
        finally:
            self.r616.exporter.context_source=old

    def test_wrong_worker_fails_before_qualifier_call(self):
        provider=self.bound.provider()
        with self.assertRaisesRegex(
            boot.CooperativePreactivationBootstrapError,"worker substitution"
        ):
            provider.qualifier(self.f.aid,"MD999")

    def test_production_bootstrap_requires_structural_binding_not_raw_callable(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td).resolve()
            repo=td/"repo";repo.mkdir()
            external=td/"external";external.mkdir()
            dep=external/"dependency.py";dep.write_text("# exact external fixture\n",encoding="utf-8")
            import hashlib
            env={
                "LION_COOPERATIVE_PREACTIVATION_BOOTSTRAP_MODE":boot.SOURCE_BOUND_MODE,
                "LION_COOPERATIVE_PREACTIVATION_BOOTSTRAP_VERSION":boot.BOOTSTRAP_VERSION,
                "LION_COOPERATIVE_PREACTIVATION_REPOSITORY_ROOT":str(repo),
                "LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_MODULE_PATH":str(dep),
                "LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_MODULE_SHA256":hashlib.sha256(dep.read_bytes()).hexdigest(),
                "LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_FACTORY":"build",
            }
            wrong=SimpleNamespace(build=lambda:self.bound.provider())
            with patch.object(boot,"_load_module",return_value=wrong):
                reg=pre.CooperativePreactivationRegistry()
                with self.assertRaisesRegex(
                    boot.CooperativePreactivationBootstrapError,
                    "production composition required",
                ):
                    boot.bootstrap_preactivation_provider(env,registry=reg)
                self.assertIsNone(reg.current())
            exact=SimpleNamespace(build=lambda:self.bound)
            with patch.object(boot,"_load_module",return_value=exact):
                reg=pre.CooperativePreactivationRegistry()
                out=boot.bootstrap_preactivation_provider(env,registry=reg)
                self.assertEqual(out["state"],"READY")
                self.assertEqual(out["mode"],boot.SOURCE_BOUND_MODE)
                self.assertEqual(out["worker_id"],"MD001")
                self.assertIsNotNone(reg.current())


if __name__=="__main__":
    unittest.main()

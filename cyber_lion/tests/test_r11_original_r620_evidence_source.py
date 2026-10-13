"""Read-only R6.20 production input assembly: disposable source acceptance."""
from __future__ import annotations

from dataclasses import asdict,replace
from datetime import datetime,timedelta
from pathlib import Path
import json
import sqlite3
import unittest
from unittest.mock import patch

from cyber_lion.enterprise.r11_original_current_owner_builder import (
    OriginalPreparationEvidenceTrust,build_current_owner_sources,
)
from cyber_lion.mission_control.cooperative_current_owner_wiring import assemble_original_owners
from cyber_lion.mission_control.cooperative_preactivation_bootstrap import CooperativeSourceBoundPreactivation
from cyber_lion.mission_control import cooperative_preactivation as pre
from cyber_lion.enterprise.r11_original_r620_evidence_source import (
    OriginalR620PreparationParts,ReadOnlyOriginalR620EvidenceSource,
    R11OriginalR620EvidenceError,
)


class FakeOriginalParts:
    def __init__(self,parts,trust):
        self.parts=parts
        self.source_id,self.source_instance_id,self.implementation_digest,\
            self.trust_anchor_id,self.trust_anchor_digest=trust.binding()
        self.calls=0
        self.callback=None

    def resolve_exact(self,aid,mission,generation,digest,trusted_now):
        self.calls+=1
        if self.callback:self.callback(aid,mission,generation,digest,trusted_now)
        return self.parts


class R11OriginalR620EvidenceSourceTests(unittest.TestCase):
    def setUp(self):
        # Original fixtures are confined to temporary storage and NEVER
        # imply production identity, permission or independent signature.
        from cyber_lion.tests.test_r11_original_current_owner_builder import (
            OriginalR11ServiceBuilderTest,
        )
        self.fixture=OriginalR11ServiceBuilderTest(
            "test_assembles_original_non_authorizing_sources_without_private_sqlite"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f=self.fixture
        self.src=f.fixture.inputs
        self.raw=f.fixture.fixture.f.fixture
        self.aid=f.fixture.fixture.f.aid
        raw=self.raw
        self.parts=OriginalR620PreparationParts(
            raw.proposal,raw.context,raw.pdp,raw.currentness,raw.authority,
            raw.provision_request,raw.trust,raw.provisioned,raw.runtime,
            raw.dispatch,raw.provisioning,raw.policy,
        )
        self.parts_trust=OriginalPreparationEvidenceTrust(
            "input:r620","input:r620:fixture","7"*64,"input-root","8"*64
        )
        self.output_trust=OriginalPreparationEvidenceTrust(
            "source:r620","source:r620:fixture","9"*64,"source-root","a"*64
        )
        self.independent=FakeOriginalParts(self.parts,self.parts_trust)
        self.pdp=f.reader
        with sqlite3.connect(f.pdp_db) as db:
            canonical=self.src.admission_engine._source.evidence
            db.execute("INSERT INTO r11_original_pdp_evidence VALUES(?,?,?)",
                       (canonical.request_id,canonical.gate_event_id,
                        json.dumps(asdict(canonical),sort_keys=True,separators=(",",":"))))

    def producer(self,**changes):
        kw=dict(
            mission_db=self.src.mission_db,
            artifact_root=self.src.artifact_root,
            parts_source=self.independent,
            parts_trust=self.parts_trust,
            source_trust=self.output_trust,
            canonical_pdp_source=self.pdp,
            canonical_pdp_trust=self.fixture.pdp_trust,
            now_fn=self.src.now_fn,
            mission_id="M1",
        )
        kw.update(changes)
        with patch("cyber_lion.enterprise.r11_original_r620_evidence_source.MISSION","M1"):
            return ReadOnlyOriginalR620EvidenceSource(**kw)

    def test_existing_parts_produce_exact_R620_evidence_readonly(self):
        producer=self.producer()
        root=self.fixture.fixture.fixture.state
        before={x.name for x in root.iterdir()}
        evidence=producer.resolve(self.aid)
        self.assertEqual(evidence,self.raw.evidence)
        self.assertEqual(self.independent.calls,1)
        self.assertEqual(before,{x.name for x in root.iterdir()})

    def test_reuses_original_R621_R616_R617_assembly_unchanged(self):
        producer=self.producer()
        with patch("cyber_lion.enterprise.r11_original_current_owner_builder.MISSION","M1"):
            built=build_current_owner_sources(replace(
                self.fixture.owners,preparation_source=producer,
                preparation_trust=self.output_trust,
            ))
        self.assertEqual(
            built.preparation_evidence_source(self.aid),self.raw.evidence
        )
        self.assertIs(built.admission_engine._source,self.pdp)
        self.assertFalse(built.worker_materialization_db.exists())

    def test_full_original_R620_R621_R616_R617_single_MD001_preactivation(self):
        # REAL original classes, disposable SQLite, synthetic upstream
        # inputs; proves wiring and no artifact-effect, NOT live admission.
        origin=self.producer()
        with patch("cyber_lion.enterprise.r11_original_current_owner_builder.MISSION","M1"):
            sources=build_current_owner_sources(replace(
                self.fixture.owners,preparation_source=origin,
                preparation_trust=self.output_trust,
            ))
        prep,mat,worker_root,worker=assemble_original_owners(sources)
        provider=CooperativeSourceBoundPreactivation(
            prep,mat,worker_root,worker,
        ).provider()
        with sqlite3.connect(self.src.mission_db) as db:
            db.row_factory=sqlite3.Row
            first=pre.advance_preactivation(
                db,mission_id="M1",phase_id="BUILD",generation=1,
                provider=provider,
                now_fn=lambda:"2026-10-12T10:00:00+00:00",
            )
            receipts=db.execute(
                "SELECT COUNT(*) FROM mission_execution_receipts WHERE assignment_id=?",
                (self.aid,),
            ).fetchone()[0]
        self.assertEqual(first["state"],"PASS",first)
        self.assertEqual(receipts,0)
        self.assertEqual(prep.status(self.aid)["state"],"PUBLISHED")
        self.assertEqual(list(Path(self.src.artifact_root).iterdir()),[])

    def test_production_requires_exact_mission_without_fixture_override(self):
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,"scope must be exact"):
            ReadOnlyOriginalR620EvidenceSource(
                mission_db=self.src.mission_db,artifact_root=self.src.artifact_root,
                parts_source=self.independent,parts_trust=self.parts_trust,
                source_trust=self.output_trust,canonical_pdp_source=self.pdp,
                canonical_pdp_trust=self.fixture.pdp_trust,
                now_fn=self.src.now_fn,mission_id="M1",
            )

    def test_no_live_held_assignment_denies_before_input_read(self):
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute("UPDATE mission_execution_assignments SET state='READY' WHERE assignment_id=?",
                       (self.aid,))
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,"must be HELD"):
            self.producer().resolve(self.aid)
        self.assertEqual(self.independent.calls,0)

    def test_tampered_assignment_input_digest_denied(self):
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute("UPDATE mission_execution_assignments SET input_digest=? WHERE assignment_id=?",
                       ("0"*64,self.aid))
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,"input digest mismatch"):
            self.producer().resolve(self.aid)

    def test_generation_substitution_denied_by_original_preflight(self):
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute("UPDATE mission_execution_assignments SET lease_generation=2 WHERE assignment_id=?",
                       (self.aid,))
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,"driver generation/state fence"):
            self.producer().resolve(self.aid)

    def test_original_component_parts_cannot_be_presealed_evidence(self):
        self.independent.parts=self.raw.evidence
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,"parts type required"):
            self.producer().resolve(self.aid)

    def test_independent_parts_trust_substitution_denied(self):
        self.independent.source_instance_id="substituted-source"
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,"input source/trust mismatch"):
            self.producer()

    def test_parts_source_drift_during_read_denied(self):
        def drift(*_):
            self.independent.source_instance_id="substituted-after-read"
        self.independent.callback=drift
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,"changed after read"):
            self.producer().resolve(self.aid)

    def test_canonical_PDP_missing_denied(self):
        with sqlite3.connect(self.fixture.pdp_db) as db:
            db.execute("DELETE FROM r11_original_pdp_evidence")
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "canonical PDP unavailable"):
            self.producer().resolve(self.aid)

    def test_original_policy_changed_denied(self):
        self.pdp._policy.current_policy_binding=lambda _: "foreign-policy"
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "issued policy substitution"):
            self.producer().resolve(self.aid)

    def test_held_assignment_changed_mid_snapshot_denied(self):
        def mutate(*_):
            with sqlite3.connect(self.src.mission_db) as db:
                db.execute("UPDATE mission_execution_assignments SET state='READY' WHERE assignment_id=?",
                           (self.aid,))
        self.independent.callback=mutate
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,"must be HELD"):
            self.producer().resolve(self.aid)

    def test_composed_and_input_source_trust_are_distinct(self):
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,"must be distinct"):
            self.producer(source_trust=self.parts_trust)

    def test_original_clock_must_be_aware(self):
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "trusted time unavailable"):
            self.producer(now_fn=lambda:datetime(2026,10,7,21,30))

    def test_resolve_at_binds_advancing_real_clock_to_original_R621(self):
        # The caller R6.21 captures trusted_now BEFORE invoking the R6.20
        # source; the independent input service must return that same
        # timestamp, while clock observations may advance safely.
        now=self.raw.currentness.trusted_now+timedelta(seconds=2)
        self.independent.parts=replace(
            self.parts,
            currentness=replace(self.parts.currentness,trusted_now=now),
        )
        producer=self.producer(now_fn=lambda:now)
        evidence=producer.resolve_at(self.aid,now)
        self.assertEqual(evidence.currentness.trusted_now,now)
        self.assertEqual(self.independent.calls,1)

    def test_delayed_upstream_clock_cannot_reissue_stale_bundle(self):
        now=self.raw.currentness.trusted_now+timedelta(seconds=9)
        producer=self.producer(now_fn=lambda:now)
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "issuance clock stale"):
            producer.resolve_at(self.aid,self.raw.currentness.trusted_now)
        self.assertEqual(self.independent.calls,0)

    def test_evidence_trusted_time_split_denied_even_with_valid_PDP(self):
        now=self.raw.currentness.trusted_now+timedelta(seconds=2)
        producer=self.producer(now_fn=lambda:now)
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "issuance clock drift"):
            producer.resolve_at(self.aid,now)

    def test_operator_pause_fence_denies_held_pre_admission(self):
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute(
                "UPDATE mission_operator_control SET pause_latch=1 WHERE mission_id='M1'"
            )
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "operator control epoch/owner/pause/stop fence"):
            self.producer().resolve(self.aid)
        self.assertEqual(self.independent.calls,0)

    def test_operator_stop_fence_denies_held_pre_admission(self):
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute(
                "UPDATE mission_operator_control SET stop_latch=1 WHERE mission_id='M1'"
            )
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "operator control epoch/owner/pause/stop fence"):
            self.producer().resolve(self.aid)
        self.assertEqual(self.independent.calls,0)

    def test_operator_control_epoch_advance_denies_old_held_assignment(self):
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute(
                "UPDATE mission_operator_control "
                "SET control_epoch=control_epoch+1 WHERE mission_id='M1'"
            )
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "operator control epoch/owner/pause/stop fence"):
            self.producer().resolve(self.aid)
        self.assertEqual(self.independent.calls,0)

    def test_operator_control_ownership_transfer_denies_old_held_assignment(self):
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute(
                "UPDATE mission_operator_control "
                "SET control_owner='OPERATOR' WHERE mission_id='M1'"
            )
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "operator control epoch/owner/pause/stop fence"):
            self.producer().resolve(self.aid)
        self.assertEqual(self.independent.calls,0)

    def test_context_revision_drift_denies_before_original_inputs(self):
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute(
                "UPDATE mission_operator_control "
                "SET context_revision=context_revision+1 WHERE mission_id='M1'"
            )
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "operator context/plan revision fence"):
            self.producer().resolve(self.aid)
        self.assertEqual(self.independent.calls,0)

    def test_plan_revision_drift_denies_before_original_inputs(self):
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute(
                "UPDATE mission_operator_control "
                "SET plan_revision=plan_revision+1 WHERE mission_id='M1'"
            )
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "operator context/plan revision fence"):
            self.producer().resolve(self.aid)
        self.assertEqual(self.independent.calls,0)

    def test_capability_revocation_denies_before_original_inputs(self):
        # An original operator-control revocation is separate from the
        # semantic phase effect ceiling and independent PDP result.
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute(
                "INSERT INTO operator_capability_revocations VALUES(?,?,?,?,?,?)",
                ("M1","COOPERATIVE_ARTIFACT_PRODUCTION","command:fixture",1,
                 "2026-10-13T00:00:00+00:00",None),
            )
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "operator capability revoked"):
            self.producer().resolve(self.aid)
        self.assertEqual(self.independent.calls,0)

    def test_original_driver_generation_drift_denies_old_held_assignment(self):
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute(
                "UPDATE mission_execution_drivers SET generation=generation+1 "
                "WHERE mission_id='M1'"
            )
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "driver generation/state fence"):
            self.producer().resolve(self.aid)
        self.assertEqual(self.independent.calls,0)

    def test_original_driver_terminal_state_denies_old_held_assignment(self):
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute(
                "UPDATE mission_execution_drivers SET state='COMPLETE' "
                "WHERE mission_id='M1'"
            )
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "driver generation/state fence"):
            self.producer().resolve(self.aid)
        self.assertEqual(self.independent.calls,0)

    def test_missing_capability_revocation_schema_denies_not_false_allow(self):
        # The original operator_control.is_capability_revoked() has a
        # historical compatibility fallback if its table is absent. R11
        # must not infer zero revocations from a missing authority ledger.
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute("DROP TABLE operator_capability_revocations")
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "operator/driver/revocation schema incomplete"):
            self.producer().resolve(self.aid)
        self.assertEqual(self.independent.calls,0)

    def test_missing_original_operator_record_denies_without_fallback(self):
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute(
                "DELETE FROM mission_operator_control WHERE mission_id='M1'"
            )
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "operator control state unavailable"):
            self.producer().resolve(self.aid)
        self.assertEqual(self.independent.calls,0)

    def test_operator_pause_during_original_parts_read_denies_second_readback(self):
        def pause(*_):
            with sqlite3.connect(self.src.mission_db) as db:
                db.execute(
                    "UPDATE mission_operator_control SET pause_latch=1 "
                    "WHERE mission_id='M1'"
                )
        self.independent.callback=pause
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "operator control epoch/owner/pause/stop fence"):
            self.producer().resolve(self.aid)
        self.assertEqual(self.independent.calls,1)

    def test_operator_pause_cannot_consume_original_runtime_admission_replay(self):
        # This is the ORIGINAL R6.21 consumer, not just a direct call
        # to the new read-only source. The operator fence must deny before
        # R6.21 journals PREPARING or consumes a single-use admission key.
        source=self.producer()
        with patch("cyber_lion.enterprise.r11_original_current_owner_builder.MISSION","M1"):
            current=build_current_owner_sources(replace(
                self.fixture.owners,
                preparation_source=source,
                preparation_trust=self.output_trust,
            ))
        prep,_,_,_=assemble_original_owners(current)
        with sqlite3.connect(self.src.mission_db) as db:
            db.execute(
                "UPDATE mission_operator_control SET pause_latch=1 "
                "WHERE mission_id='M1'"
            )
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "operator control epoch/owner/pause/stop fence"):
            prep(self.aid)
        self.assertEqual(self.independent.calls,0)
        self.assertEqual(prep.status(self.aid)["state"],"NOT_STARTED")
        with sqlite3.connect(self.fixture.owners.admission_replay_guard.path) as db:
            count=db.execute(
                "SELECT COUNT(*) FROM r11_runtime_admission_replay"
            ).fetchone()[0]
        self.assertEqual(count,0)
        with sqlite3.connect(self.fixture.owners.admission_source.path) as db:
            count=db.execute("SELECT COUNT(*) FROM runtime_admissions").fetchone()[0]
        self.assertEqual(count,0)
        self.assertEqual(list(Path(self.src.artifact_root).iterdir()),[])

    def test_original_PDP_reader_is_exact_canonical_type(self):
        with self.assertRaisesRegex(R11OriginalR620EvidenceError,
                                    "canonical PDP source required"):
            self.producer(canonical_pdp_source=object())


if __name__=="__main__":
    unittest.main()

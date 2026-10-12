"""Original canonical PDP decision -> private evidence DB -> independent reader.

All fixtures are disposable. The real policy source/LiveAuthorityAdmission
is represented only within original canonical PDP test fixtures, NOT live.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cyber_lion.contracts.runtime_enforcement import (
    CanonicalPDPDecisionEvidence,
    PDPSourceTrustBinding,
)
from cyber_lion.enterprise.policy_gate import PDPResult, CanonicalPolicyDecisionPoint
from cyber_lion.enterprise.runtime_enforcement import RuntimeAdmissionEngine
from cyber_lion.enterprise.r11_runtime_admission_replay import SQLiteR11RuntimeAdmissionReplayGuard
from cyber_lion.enterprise.r11_canonical_pdp_evidence import (
    R11CanonicalPDPSourceError,
    OriginalPDPIssuanceObservation,
    SQLiteR11CanonicalPDPEvidencePublisher as Publisher,
    SQLiteR11CanonicalPDPEvidenceReader as Reader,
)
from cyber_lion.tests.test_policy_gate import fixture, evaluate, NOW


class FixtureOriginalIssuanceSource:
    """Disposable simulated independent issuer; NEVER production authority."""

    def __init__(self,decision,trust,issued_at,expires_at):
        self.result=decision
        self.source_id=trust.source_id
        self.source_instance_id=trust.source_instance_id
        self.implementation_digest=trust.source_implementation_digest
        self.trust_anchor_id=trust.trust_anchor_id
        self.trust_anchor_digest=trust.trust_anchor_digest
        self.issued_at=issued_at
        self.expires_at=expires_at

    def __call__(self,request_id,gate_event_id,gate_decision_digest):
        return OriginalPDPIssuanceObservation(
            request_id=request_id,
            gate_event_id=gate_event_id,
            gate_decision_digest=gate_decision_digest,
            policy_binding=self.result.applied.policy_binding,
            issued_at=self.issued_at.isoformat(),
            expires_at=self.expires_at.isoformat(),
            source_id=self.source_id,
            source_instance_id=self.source_instance_id,
            source_implementation_digest=self.implementation_digest,
            trust_anchor_id=self.trust_anchor_id,
            trust_anchor_digest=self.trust_anchor_digest,
        )


class FixtureIndependentCurrentPolicy:
    """Only a disposable, simulated policy owner; not production currentness."""

    def __init__(self,trust):
        self.source_id=trust.source_id
        self.source_instance_id=trust.source_instance_id
        self.implementation_digest=trust.source_implementation_digest
        self.trust_anchor_id=trust.trust_anchor_id
        self.trust_anchor_digest=trust.trust_anchor_digest
        self.override=None
        self.fail=False

    def current_policy_binding(self,binding):
        if self.fail:
            raise RuntimeError("fixture original policy source unavailable")
        return binding if self.override is None else self.override


class R11CanonicalPDPSourceTests(unittest.TestCase):
    def setUp(self):
        self.parts = fixture()
        self.addCleanup(self.parts[0].cleanup)
        self.root=Path(self.parts[0].name)
        self.pdp=self.parts[1]
        self.result=evaluate(self.parts)
        self.assertEqual(self.result.applied.decision, "ALLOW")
        self.path=self.root/"canonical-pdp-evidence.sqlite"
        self.trust=PDPSourceTrustBinding(
            "r11:pdp-original", "r11:pdp-original:fixture",
            "1"*64, "r11:pdp-original-trust", "2"*64,
        ).validate()
        self.issuance_trust=PDPSourceTrustBinding(
            "r11:issuer-evidence", "r11:issuer-evidence:fixture",
            "3"*64, "r11:issuer-evidence-anchor", "4"*64,
        ).validate()
        self.issuance=FixtureOriginalIssuanceSource(
            self.result,self.issuance_trust,
            NOW-timedelta(seconds=2),NOW+timedelta(seconds=200),
        )
        self.policy_trust=PDPSourceTrustBinding(
            "r11:original-policy", "r11:original-policy:fixture",
            "5"*64, "r11:policy-anchor", "6"*64,
        ).validate()
        self.policy=FixtureIndependentCurrentPolicy(self.policy_trust)

    def publisher(self,*,now=NOW,path=None):
        database=path or self.path
        if not database.exists():
            # DISPOSABLE TEST FIXTURE ONLY. The production publisher never
            # initializes its own SQLite schema or constructs missing evidence.
            with sqlite3.connect(database) as db:
                db.execute(
                    "CREATE TABLE r11_original_pdp_evidence ("
                    "request_id TEXT NOT NULL, gate_event_id TEXT NOT NULL,"
                    "record_json TEXT NOT NULL, PRIMARY KEY(request_id,gate_event_id))"
                )
            database.chmod(0o600)
        return Publisher(
            database=database,
            original_pdp=self.pdp,
            original_authority=self.pdp.authority_admission,
            source_trust=self.trust,
            issuance_source=self.issuance,
            issuance_source_trust=self.issuance_trust,
            now_fn=lambda:now,
        )

    def reader(self,*,now=NOW,trust=None,policy=None,path=None):
        return Reader(
            database=path or self.path,
            source_trust=trust or self.trust,
            current_policy_source=self.policy if policy is None else policy,
            current_policy_trust=self.policy_trust,
            now_fn=lambda:now,
        )

    def published(self):
        return self.publisher().publish(self.result,ttl_seconds=120)

    def test_original_issued_decision_roundtrips_exact_source(self):
        evidence=self.published()
        reader=self.reader()
        result=reader.resolve(self.result.applied.request_id,
                              self.result.applied.gate_event_id)
        self.assertEqual(result,evidence)
        self.assertEqual(reader.current_policy_binding(evidence.policy_binding),
                         evidence.policy_binding)
        self.assertEqual(
            tuple(getattr(reader,key,None) for key in (
                "source_id","source_instance_id","implementation_digest",
                "trust_anchor_id","trust_anchor_digest",
            )),
            self.trust.binding(),
        )

    def test_original_runtime_admission_engine_resolves_independent_pdp_db(self):
        evidence=self.published()
        reader=self.reader()
        engine=RuntimeAdmissionEngine(
            authority_admission=self.pdp.authority_admission,
            pdp_source=reader,
            pdp_source_trust=self.trust,
            replay_guard=SQLiteR11RuntimeAdmissionReplayGuard(
                self.root/"original-admission-replay.sqlite"
            ),
        )
        out=engine._canonical_pdp(
            self.result.applied,self.result.receipt,NOW,
        )
        self.assertEqual(out,evidence)
        self.assertEqual(engine._source_trust,self.trust)
        self.assertIs(engine._authority,self.pdp.authority_admission)

    def test_reader_restart_persists_pdp_evidence_without_publication(self):
        expected=self.published()
        self.assertEqual(self.reader().resolve("r","g"),expected)
        second=self.reader()
        self.assertEqual(second.resolve("r","g"),expected)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM r11_original_pdp_evidence"
            ).fetchone()[0],1)

    def test_reader_never_creates_missing_database(self):
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "evidence unavailable"):
            self.reader()
        self.assertFalse(self.path.exists())

    def test_publisher_cannot_initialize_missing_original_evidence_store(self):
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "canonical PDP evidence unavailable"):
            Publisher(
                database=self.path,
                original_pdp=self.pdp,
                original_authority=self.pdp.authority_admission,
                source_trust=self.trust,
                issuance_source=self.issuance,
                issuance_source_trust=self.issuance_trust,
            )
        self.assertFalse(self.path.exists())

    def test_publisher_refuses_to_publish_non_cached_decision(self):
        unissued=PDPResult(
            self.result.requested,self.result.applied,self.result.receipt,
        )
        self.assertIsNot(unissued,self.result)
        pub=self.publisher()
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "not issued by pinned owner"):
            pub.publish(unissued)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM r11_original_pdp_evidence"
            ).fetchone()[0],0)

    def test_cannot_republish_exact_original_pdp_decision(self):
        self.published()
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "duplicate or replay"):
            self.publisher().publish(self.result)

    def test_publisher_rejects_split_authority_owner_before_store(self):
        # Original PDP identity must be the source of the same real
        # LiveAuthorityAdmission, not a separate/foreign revalidator.
        other=fixture()
        self.addCleanup(other[0].cleanup)
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "owner split"):
            Publisher(
                database=self.path,original_pdp=self.pdp,
                original_authority=other[1].authority_admission,
                source_trust=self.trust,
                issuance_source=self.issuance,
                issuance_source_trust=self.issuance_trust,
            )
        self.assertFalse(self.path.exists())

    def test_publisher_requires_exact_original_pdp_class(self):
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "exact original"):
            Publisher(
                database=self.path,original_pdp=object(),
                original_authority=self.pdp.authority_admission,
                source_trust=self.trust,
                issuance_source=self.issuance,
                issuance_source_trust=self.issuance_trust,
            )
        self.assertFalse(self.path.exists())

    def test_publisher_rejects_nonpositive_expiry_and_bool(self):
        pub=self.publisher()
        for ttl in (0,601,True,-1,1.5):
            with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                        "TTL invalid"):
                pub.publish(self.result,ttl_seconds=ttl)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM r11_original_pdp_evidence"
            ).fetchone()[0],0)

    def test_old_cached_original_pdp_allow_cannot_be_reissued_with_new_clock(self):
        self.issuance.expires_at=NOW+timedelta(seconds=2)
        pub=self.publisher(now=NOW+timedelta(seconds=3))
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "issuance expired or not yet current"):
            pub.publish(self.result)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM r11_original_pdp_evidence"
            ).fetchone()[0],0)

    def test_original_issuance_window_caps_exported_ttl(self):
        self.issuance.expires_at=NOW+timedelta(seconds=15)
        result=self.publisher().publish(self.result,ttl_seconds=120)
        self.assertEqual(
            result.expires_at,
            (NOW+timedelta(seconds=15)).isoformat(),
        )
        self.assertEqual(result.issued_at,(NOW-timedelta(seconds=2)).isoformat())
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "expired or not current"):
            self.reader(now=NOW+timedelta(seconds=16)).resolve("r","g")

    def test_future_issuance_window_denied(self):
        self.issuance.issued_at=NOW+timedelta(seconds=15)
        self.issuance.expires_at=NOW+timedelta(seconds=45)
        pub=self.publisher()
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "issuance expired or not yet current"):
            pub.publish(self.result)

    def test_post_init_issuance_source_trust_substitution_denied(self):
        pub=self.publisher()
        self.issuance.source_instance_id="altered-original-issuer"
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "issuance provenance substitution"):
            pub.publish(self.result)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM r11_original_pdp_evidence"
            ).fetchone()[0],0)

    def test_independent_issuance_source_missing_fails_before_db_creation(self):
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "independent original issuance source/trust mismatch"):
            Publisher(
                database=self.path,original_pdp=self.pdp,
                original_authority=self.pdp.authority_admission,
                source_trust=self.trust,
                issuance_source=None,
                issuance_source_trust=self.issuance_trust,
            )
        self.assertFalse(self.path.exists())

    def test_independent_issue_receipt_mismatches_exact_policy(self):
        pub=self.publisher()
        self.issuance.result=self.result
        self.issuance.result=replace(
            self.result,
            applied=replace(self.result.applied,policy_binding="forged-policy")
        )
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "does not bind original PDP"):
            pub.publish(self.result)

    def test_world_readable_source_database_denied(self):
        self.published()
        self.path.chmod(0o644)
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "owner/type/path denied"):
            self.reader()

    def test_reader_rejects_expired_evidence(self):
        self.published()
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "expired or not current"):
            self.reader(now=NOW+timedelta(minutes=3)).resolve("r","g")

    def test_reader_rejects_not_yet_issued_evidence(self):
        self.published()
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "expired or not current"):
            self.reader(now=NOW-timedelta(seconds=3)).resolve("r","g")

    def test_reader_provides_fresh_independent_policy_not_stored_echo(self):
        evidence=self.published()
        self.policy.override="policy@999:sha256:"+"f"*64
        reader=self.reader()
        self.assertEqual(reader.resolve("r","g"),evidence)
        self.assertNotEqual(
            reader.current_policy_binding(evidence.policy_binding),
            evidence.policy_binding,
        )
        engine=RuntimeAdmissionEngine(
            authority_admission=self.pdp.authority_admission,
            pdp_source=reader,
            pdp_source_trust=self.trust,
            replay_guard=SQLiteR11RuntimeAdmissionReplayGuard(
                self.root/"admission-stale-policy.sqlite"
            ),
        )
        with self.assertRaisesRegex(Exception,"policy binding is stale"):
            engine._canonical_pdp(self.result.applied,self.result.receipt,NOW)

    def test_missing_independent_current_policy_denied(self):
        self.published()
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "independent current policy source/trust mismatch"):
            Reader(database=self.path,source_trust=self.trust,
                   current_policy_source=None,
                   current_policy_trust=self.policy_trust)

    def test_current_policy_provider_error_fails_closed(self):
        self.published()
        self.policy.fail=True
        reader=self.reader()
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "independent policy unavailable"):
            reader.current_policy_binding(self.result.applied.policy_binding)

    def test_unpinned_policy_echo_callback_rejected(self):
        self.published()
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "independent current policy source/trust mismatch"):
            self.reader(policy=lambda binding:binding)

    def test_pinned_policy_owner_identity_drift_rejected(self):
        self.published()
        reader=self.reader()
        self.policy.source_instance_id="substituted-policy-owner"
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "independent policy source identity drift"):
            reader.current_policy_binding(self.result.applied.policy_binding)

    def test_pinned_policy_owner_missing_trust_rejected(self):
        self.published()
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "independent current policy trust required"):
            Reader(database=self.path,source_trust=self.trust,
                   current_policy_source=self.policy,
                   current_policy_trust=None)

    def test_wrong_current_source_anchor_rejected(self):
        self.published()
        trust=replace(self.trust,trust_anchor_digest="3"*64)
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "source trust mismatch"):
            self.reader(trust=trust).resolve("r","g")

    def test_wrong_coordinates_no_fallback(self):
        self.published()
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "missing or ambiguous"):
            self.reader().resolve("r","other")
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "coordinates required"):
            self.reader().resolve("r;DROP TABLE","g")

    def test_json_digest_tampering_is_rejected(self):
        self.published()
        with sqlite3.connect(self.path) as db:
            raw=db.execute("SELECT record_json FROM r11_original_pdp_evidence").fetchone()[0]
            obj=json.loads(raw)
            obj["gate_decision_digest"]="f"*64
            db.execute(
                "UPDATE r11_original_pdp_evidence SET record_json=?",
                (json.dumps(obj),),
            )
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "record invalid"):
            self.reader().resolve("r","g")

    def test_duplicate_json_field_is_rejected(self):
        self.published()
        with sqlite3.connect(self.path) as db:
            raw=db.execute("SELECT record_json FROM r11_original_pdp_evidence").fetchone()[0]
            duplicated=raw.replace('"request_id":', '"request_id":"forged","request_id":',1)
            db.execute("UPDATE r11_original_pdp_evidence SET record_json=?",
                       (duplicated,))
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "duplicate canonical PDP evidence field"):
            self.reader().resolve("r","g")

    def test_source_file_inode_swap_after_open_denied(self):
        self.published()
        reader=self.reader()
        saved=self.root/"old.sqlite"
        self.path.rename(saved)
        pub=self.publisher()
        self.assertIsNotNone(pub)
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,"identity drift"):
            reader.resolve("r","g")

    def test_world_writable_private_parent_denied(self):
        other=self.root/"bad"
        other.mkdir()
        other.chmod(0o777)
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,"parent not private"):
            Publisher(
                database=other/"source.db",original_pdp=self.pdp,
                original_authority=self.pdp.authority_admission,
                source_trust=self.trust,
                issuance_source=self.issuance,
                issuance_source_trust=self.issuance_trust,
            )

    def test_symlink_database_denied(self):
        self.published()
        link=self.root/"linked.db"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,
                                    "direct absolute"):
            self.reader(path=link)

    def test_bad_private_schema_is_denied(self):
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE r11_original_pdp_evidence(request_id TEXT)")
        self.path.chmod(0o600)
        with self.assertRaisesRegex(R11CanonicalPDPSourceError,"schema mismatch"):
            self.reader()


if __name__=="__main__":
    unittest.main()

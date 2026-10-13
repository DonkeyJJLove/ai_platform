"""Actual Ed25519 verification in disposable original-R6.20 source tests.

Cryptographic signatures here come from a GENERATED TEST KEY only; no fixture
is a real production trusted issuer, PDP authority or operator admission.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from cyber_lion.enterprise.r11_signed_original_r620_parts import (
    DOMAIN, SCHEMA, REPOSITORY, R11OriginalSignedPartsError,
    SQLiteSignedOriginalR620PartsSource, canonical_record_bytes,
)
from cyber_lion.enterprise.r11_original_current_owner_builder import (
    build_current_owner_sources,
)
from cyber_lion.mission_control.cooperative_current_owner_wiring import assemble_original_owners
from cyber_lion.mission_control.cooperative_preactivation_bootstrap import CooperativeSourceBoundPreactivation
from cyber_lion.mission_control import cooperative_preactivation as pre


class SignedOriginalR620PartsTests(unittest.TestCase):
    def setUp(self):
        from cyber_lion.tests.test_r11_original_r620_evidence_source import (
            R11OriginalR620EvidenceSourceTests,
        )
        self.fixt=R11OriginalR620EvidenceSourceTests(
            "test_existing_parts_produce_exact_R620_evidence_readonly"
        )
        self.fixt.setUp()
        self.addCleanup(self.fixt.doCleanups)
        f=self.fixt
        self.trust=f.parts_trust
        self.now=f.raw.currentness.trusted_now
        self.base=Path(f.fixture.fixture.fixture.state).resolve()
        self.path=self.base/"original-r620-signed.sqlite"
        self.key_path=self.base/"r620-test-public.raw"
        self.key=Ed25519PrivateKey.generate()
        key_bytes=self.key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        self.key_path.write_bytes(key_bytes)
        self.key_path.chmod(0o600)
        self.public_key_digest=sha256(key_bytes).hexdigest()
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE r11_original_r620_signed_parts("
                "assignment_id TEXT NOT NULL,mission_id TEXT NOT NULL,"
                "generation INTEGER NOT NULL,input_digest TEXT NOT NULL,"
                "record_json TEXT NOT NULL,signature_hex TEXT NOT NULL,"
                "key_id TEXT NOT NULL,"
                "PRIMARY KEY(assignment_id,mission_id,generation,input_digest))"
            )
        self.path.chmod(0o600)
        with sqlite3.connect(f.src.mission_db) as db:
            row=db.execute(
                "SELECT mission_id,lease_generation,input_digest "
                "FROM mission_execution_assignments WHERE assignment_id=?",(f.aid,)
            ).fetchone()
        self.mission,self.generation,self.input_digest=row
        self.issuer="original-r620-issuer-fixture"
        self.key_id="ed25519-test-key"
        self.record={
            "schema":SCHEMA,"repository":REPOSITORY,
            "assignment_id":f.aid,"mission_id":self.mission,
            "generation":self.generation,"input_digest":self.input_digest,
            "worker_id":"MD001","source":list(self.trust.binding()),
            "issuer_subject_id":self.issuer,"issuer_key_id":self.key_id,
            "issued_at":(self.now-timedelta(seconds=2)).isoformat(),
            "expires_at":(self.now+timedelta(seconds=60)).isoformat(),
            "parts":asdict(f.parts),
        }
        self.insert_record()

    def insert_record(self,record=None,*,signature=None,key_id=None,raw=None):
        rec=self.record if record is None else record
        data=canonical_record_bytes(rec) if raw is None else raw
        sig=self.key.sign(DOMAIN+data).hex() if signature is None else signature
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT OR REPLACE INTO r11_original_r620_signed_parts VALUES(?,?,?,?,?,?,?)",
                (self.fixt.aid,self.mission,self.generation,self.input_digest,
                 data.decode("utf-8"),sig,self.key_id if key_id is None else key_id),
            )

    def reader(self,**kwargs):
        opts=dict(
            database=self.path,
            source_trust=self.trust,
            public_key_path=self.key_path,
            public_key_sha256=self.public_key_digest,
            issuer_subject_id=self.issuer,
            issuer_key_id=self.key_id,
            now_fn=lambda:self.now,
            mission_id=self.mission,
            worker_id="MD001",
        )
        opts.update(kwargs)
        with patch("cyber_lion.enterprise.r11_signed_original_r620_parts.MISSION",
                   self.mission):
            return SQLiteSignedOriginalR620PartsSource(**opts)

    def resolved(self,reader=None,**kw):
        return (reader or self.reader()).resolve_exact(
            self.fixt.aid,self.mission,self.generation,
            self.input_digest,self.now,**kw
        )

    def test_real_ed25519_signature_source_supplies_all_original_twelve_parts(self):
        reader=self.reader()
        self.assertEqual(self.resolved(reader),self.fixt.parts)
        self.assertEqual(reader.source_id,self.trust.source_id)

    def test_full_original_md001_R620_R621_R616_R617_acceptance_through_signed_source(self):
        reader=self.reader()
        outer=self.fixt.producer(parts_source=reader)
        origin=self.fixt.fixture.owners
        with patch("cyber_lion.enterprise.r11_original_current_owner_builder.MISSION",
                   self.mission):
            owner=build_current_owner_sources(replace(
                origin,preparation_source=outer,
                preparation_trust=self.fixt.output_trust,
            ))
        prep,mat,root,worker=assemble_original_owners(owner)
        provider=CooperativeSourceBoundPreactivation(prep,mat,root,worker).provider()
        with sqlite3.connect(self.fixt.src.mission_db) as db:
            db.row_factory=sqlite3.Row
            result=pre.advance_preactivation(
                db,mission_id=self.mission,phase_id="BUILD",
                generation=1,provider=provider,
                now_fn=lambda:"2026-10-12T10:00:00+00:00",
            )
            receipts=db.execute(
                "SELECT COUNT(*) FROM mission_execution_receipts WHERE assignment_id=?",
                (self.fixt.aid,),
            ).fetchone()[0]
        self.assertEqual(result["state"],"PASS",result)
        self.assertEqual(receipts,0)
        self.assertEqual(list(Path(self.fixt.src.artifact_root).iterdir()),[])

    def test_signature_tampering_denied(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE r11_original_r620_signed_parts SET signature_hex=?",
                       ("0"*128,))
        with self.assertRaisesRegex(R11OriginalSignedPartsError,"Ed25519 signature invalid"):
            self.resolved()

    def test_wrong_independently_pinned_public_key_denied(self):
        with self.assertRaisesRegex(R11OriginalSignedPartsError,"verifier key digest"):
            self.reader(public_key_sha256="0"*64)

    def test_wrong_issuer_id_cannot_be_selected_from_signed_payload(self):
        with self.assertRaisesRegex(R11OriginalSignedPartsError,"issuer/source/assignment"):
            self.resolved(self.reader(issuer_subject_id="unknown-original-signer"))

    def test_malformed_signature_key_id_denied(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE r11_original_r620_signed_parts SET key_id=?",
                       ("other-key",))
        with self.assertRaisesRegex(R11OriginalSignedPartsError,"record fields invalid"):
            self.resolved()

    def test_wrong_signed_assignment_binding_denied_even_with_valid_signature(self):
        self.record["assignment_id"]="other-assignment"
        self.insert_record()
        with self.assertRaisesRegex(R11OriginalSignedPartsError,
                                    "issuer/source/assignment substitution"):
            self.resolved()

    def test_signed_input_expired_denied(self):
        self.record["expires_at"]=(self.now-timedelta(seconds=1)).isoformat()
        self.insert_record()
        with self.assertRaisesRegex(R11OriginalSignedPartsError,"expired or future"):
            self.resolved()

    def test_signed_input_future_issuance_denied(self):
        self.record["issued_at"]=(self.now+timedelta(seconds=5)).isoformat()
        self.insert_record()
        with self.assertRaisesRegex(R11OriginalSignedPartsError,"expired or future"):
            self.resolved()

    def test_oversized_original_issuance_window_denied(self):
        self.record["expires_at"]=(self.now+timedelta(seconds=360)).isoformat()
        self.insert_record()
        with self.assertRaisesRegex(R11OriginalSignedPartsError,"expired or future"):
            self.resolved()

    def test_part_dataclass_shape_substitution_denied(self):
        self.record["parts"]["provisioned_executor"]["mission_id"]="foreign-mission"
        self.insert_record()
        # The cryptographic signature is valid, but original R6.20
        # cross-contract validation must still fail.
        with self.assertRaisesRegex(R11OriginalSignedPartsError,
                                    "signed original R6.20 component binding invalid"):
            self.resolved()

    def test_duplicate_JSON_fields_denied_even_with_consistent_signature(self):
        raw=canonical_record_bytes(self.record)
        duplicated=raw.replace(b'"issuer_key_id":',b'"issuer_key_id":"x","issuer_key_id":',1)
        self.insert_record(signature=self.key.sign(DOMAIN+duplicated).hex(),
                           raw=duplicated)
        with self.assertRaisesRegex(R11OriginalSignedPartsError,
                                    "duplicate original signed input field"):
            self.resolved()

    def test_key_inode_rotation_after_initialization_denied(self):
        reader=self.reader()
        original=self.base/"old-key.raw"
        self.key_path.rename(original)
        self.key_path.write_bytes(original.read_bytes())
        self.key_path.chmod(0o600)
        with self.assertRaisesRegex(R11OriginalSignedPartsError,
                                    "public-key identity drift"):
            self.resolved(reader)

    def test_database_inode_replacement_after_initialization_denied(self):
        reader=self.reader()
        original=self.base/"old-db.sqlite"
        self.path.rename(original)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE replacement(x TEXT)")
        self.path.chmod(0o600)
        with self.assertRaisesRegex(R11OriginalSignedPartsError,
                                    "DB identity drift"):
            self.resolved(reader)

    def test_missing_database_never_initialized_by_consumer(self):
        self.path.unlink()
        with self.assertRaisesRegex(R11OriginalSignedPartsError,"missing"):
            self.reader()
        self.assertFalse(self.path.exists())

    def test_world_readable_original_parts_DB_denied(self):
        self.path.chmod(0o644)
        with self.assertRaisesRegex(R11OriginalSignedPartsError,
                                    "private single-link"):
            self.reader()

    def test_source_trust_mismatch_denied(self):
        source=replace(self.trust,source_instance_id="foreign-test-source")
        with self.assertRaisesRegex(R11OriginalSignedPartsError,
                                    "issuer/source/assignment"):
            self.resolved(self.reader(source_trust=source))

    def test_presentation_of_wrong_generation_denied_before_signature(self):
        with self.assertRaisesRegex(R11OriginalSignedPartsError,
                                    "record missing or ambiguous"):
            self.reader().resolve_exact(
                self.fixt.aid,self.mission,2,self.input_digest,self.now
            )

    def test_clock_drift_denied(self):
        reader=self.reader(now_fn=lambda:self.now+timedelta(seconds=12))
        with self.assertRaisesRegex(R11OriginalSignedPartsError,"clock not current"):
            self.resolved(reader)

    def test_missing_or_foreign_original_mission_denied(self):
        with self.assertRaisesRegex(R11OriginalSignedPartsError,"mission/worker scope"):
            SQLiteSignedOriginalR620PartsSource(
                database=self.path,source_trust=self.trust,
                public_key_path=self.key_path,
                public_key_sha256=self.public_key_digest,
                issuer_subject_id=self.issuer,issuer_key_id=self.key_id,
                now_fn=lambda:self.now,mission_id=self.mission,
            )

    def test_strict_read_only_requires_original_preprovisioned_schema(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TABLE r11_original_r620_signed_parts")
        with self.assertRaisesRegex(R11OriginalSignedPartsError,"schema mismatch"):
            self.reader()


if __name__=="__main__":
    unittest.main()

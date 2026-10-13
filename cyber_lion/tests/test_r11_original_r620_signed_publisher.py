"""Original signed-R620 create-only publication tests: DISPOSABLE FAKE authority.

The suite does not prove production issuer registration, signer admission,
protected deployment or runtime permission. It tests denial and uncertainty.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sqlite3
import unittest

from cyber_lion.enterprise.authority_source import AuthorityLookupKey
from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.enterprise.r11_original_current_owner_builder import OriginalPreparationEvidenceTrust
from cyber_lion.enterprise.r11_original_r620_signed_publisher import (
    ACTION, OriginalSignedR620Row, CreateOnlyOriginalSignedR620Publisher,
    R11OriginalR620PublishError, R11OriginalR620EffectUnknown,
)
from cyber_lion.enterprise.r11_signed_original_r620_parts import (
    DOMAIN, canonical_record_bytes, R11OriginalSignedPartsError,
)


class FixtureOriginalAuthoritySource:
    """Synthetic only. Production revalidate must verify original signatures."""

    def __init__(self, receipt, *, db_path: Path):
        self.receipt=receipt
        self.actions=(ACTION,)
        self.resources=(str(db_path),)
        self.calls=0

    def resolve_exact(self,key):
        self.calls+=1
        assert key.binding()==AuthorityLookupKey(
            self.receipt.repository,self.receipt.pr_number,
            self.receipt.base_sha,self.receipt.head_sha,
            self.receipt.mission_id,self.receipt.grant_id,
        ).binding()
        leaf=SimpleNamespace(
            actions=self.actions,resource_scope=self.resources,
            mission_id=self.receipt.mission_id,
            authority_ceiling=self.receipt.authority_ceiling,
        )
        return SimpleNamespace(lookup_key=key,lineage=(leaf,))


class FixtureAuthorityAdmission(LiveAuthorityAdmission):
    def __init__(self,authority_source):
        self._source=authority_source
        self.fail_currentness=False
        self.count=0

    def revalidate(self,admitted,*,now):
        self.count+=1
        if self.fail_currentness:
            raise RuntimeError("synthetic revoked authority")
        return admitted


class FixturePreissuedSource:
    def __init__(self, row, trust):
        self.row=row
        self.source_id,self.source_instance_id,self.implementation_digest,\
            self.trust_anchor_id,self.trust_anchor_digest=trust.binding()
        self.calls=0
        self.mutate_after=False

    def resolve_issued_exact(self,assignment_id,mission_id,generation,digest,stamp):
        self.calls+=1
        if self.mutate_after:
            self.source_instance_id="replaced-signed-issuer"
        return self.row


class SignedR620PublisherTests(unittest.TestCase):
    def setUp(self):
        from cyber_lion.tests.test_r11_signed_original_r620_parts import SignedOriginalR620PartsTests
        self.fixt=SignedOriginalR620PartsTests(
            "test_real_ed25519_signature_source_supplies_all_original_twelve_parts"
        )
        self.fixt.setUp()
        self.addCleanup(self.fixt.doCleanups)
        f=self.fixt
        self.reader=f.reader()
        self.prep=f.fixt.producer()
        self.now=f.now
        self.admitted=f.fixt.raw.authority
        self.auth_source=FixtureOriginalAuthoritySource(self.admitted,db_path=f.path)
        self.authority=FixtureAuthorityAdmission(self.auth_source)
        self.issuer_trust=OriginalPreparationEvidenceTrust(
            "original-r620-issued","original-r620-issued:disposable",
            "7"*64,"original-issuer-trust","8"*64,
        )
        raw=canonical_record_bytes(f.record)
        row=OriginalSignedR620Row(
            f.fixt.aid,f.mission,f.generation,f.input_digest,
            raw.decode("utf-8"),f.key.sign(DOMAIN+raw).hex(),f.key_id,
        )
        self.issuer=FixturePreissuedSource(row,self.issuer_trust)
        # The fixture's signing helper prepopulates a row: remove ONLY
        # the disposable row, never touch a real signed evidence database.
        with sqlite3.connect(f.path) as db:
            db.execute("DELETE FROM r11_original_r620_signed_parts")
        self.assertEqual(self.count(),0)

    def count(self):
        with sqlite3.connect(self.fixt.path) as db:
            return db.execute("SELECT COUNT(*) FROM r11_original_r620_signed_parts").fetchone()[0]

    def publisher(self,**opts):
        kw=dict(reader=self.reader,original_preparation=self.prep,
                signed_row_source=self.issuer,
                signed_row_source_trust=self.issuer_trust,
                authority_owner=self.authority,now_fn=lambda:self.now,
                source_pr_number=self.admitted.pr_number,
                source_base_sha=self.admitted.base_sha,
                source_head_sha=self.admitted.head_sha)
        kw.update(opts)
        return CreateOnlyOriginalSignedR620Publisher(**kw)

    def publish(self,publisher=None,**kw):
        return (publisher or self.publisher()).publish(
            self.fixt.fixt.aid,admitted=self.admitted,trusted_now=self.now,**kw
        )

    def test_exact_preissued_ed25519_row_publishes_and_reads_back(self):
        result=self.publish()
        self.assertEqual(result,sha256(self.issuer.row.record_json.encode()).hexdigest())
        self.assertEqual(self.count(),1)
        self.assertEqual(self.reader.resolve_exact(
            self.fixt.fixt.aid,self.fixt.mission,
            self.fixt.generation,self.fixt.input_digest,self.now
        ),self.fixt.fixt.parts)
        self.assertEqual(self.issuer.calls,1)
        self.assertGreaterEqual(self.authority.count,2)

    def test_republication_fails_closed_no_replace_or_upsert(self):
        self.publish()
        with self.assertRaisesRegex(R11OriginalR620PublishError,"replay denied"):
            self.publish()
        self.assertEqual(self.count(),1)

    def test_untrusted_issuer_record_bytes_rejected_before_insert(self):
        row=self.issuer.row
        self.issuer.row=OriginalSignedR620Row(
            row.assignment_id,row.mission_id,row.generation,row.input_digest,
            row.record_json+" ",row.signature_hex,row.key_id,
        )
        with self.assertRaisesRegex(R11OriginalR620PublishError,"canonical R6.20/PDP preflight"):
            self.publish()
        self.assertEqual(self.count(),0)

    def test_tampered_signature_rejected_before_insert(self):
        row=self.issuer.row
        self.issuer.row=OriginalSignedR620Row(
            row.assignment_id,row.mission_id,row.generation,row.input_digest,
            row.record_json,"0"*128,row.key_id,
        )
        with self.assertRaisesRegex(R11OriginalR620PublishError,"canonical R6.20/PDP preflight"):
            self.publish()
        self.assertEqual(self.count(),0)

    def test_foreign_input_generation_denied_before_insert(self):
        row=self.issuer.row
        self.issuer.row=OriginalSignedR620Row(
            row.assignment_id,row.mission_id,row.generation+1,row.input_digest,
            row.record_json,row.signature_hex,row.key_id,
        )
        with self.assertRaisesRegex(R11OriginalR620PublishError,"issuer assignment"):
            self.publish()
        self.assertEqual(self.count(),0)

    def test_current_original_authority_required(self):
        self.authority.fail_currentness=True
        with self.assertRaisesRegex(R11OriginalR620PublishError,"not current"):
            self.publish()
        self.assertEqual(self.count(),0)

    def test_grant_must_name_exact_publication_action(self):
        self.auth_source.actions=("SOME_OTHER_ACTION",)
        with self.assertRaisesRegex(R11OriginalR620PublishError,"action/resource"):
            self.publish()
        self.assertEqual(self.issuer.calls,0)
        self.assertEqual(self.count(),0)

    def test_grant_must_name_exact_private_SQLite_resource(self):
        self.auth_source.resources=("/some/other/path",)
        with self.assertRaisesRegex(R11OriginalR620PublishError,"action/resource"):
            self.publish()
        self.assertEqual(self.count(),0)

    def test_producer_cannot_inherit_foreign_source_head_grant(self):
        pub=self.publisher(source_head_sha="f"*40)
        with self.assertRaisesRegex(R11OriginalR620PublishError,
                                    "exact publication authority envelope"):
            self.publish(pub)
        self.assertEqual(self.count(),0)

    def test_missing_original_release_sha_denied_before_effect(self):
        with self.assertRaisesRegex(R11OriginalR620PublishError,
                                    "release binding unavailable"):
            self.publisher(source_head_sha="")
        self.assertEqual(self.count(),0)

    def test_no_publisher_aliasing_signed_reader_as_issuer(self):
        with self.assertRaisesRegex(R11OriginalR620PublishError,
                                    "preissued R6.20 row source"):
            self.publisher(signed_row_source=self.reader)

    def test_original_source_trust_drift_denied_before_effect(self):
        self.issuer.mutate_after=True
        with self.assertRaisesRegex(R11OriginalR620PublishError,
                                    "issuer source drift after issue"):
            self.publish()
        self.assertEqual(self.count(),0)

    def test_operator_assignment_no_longer_HELD_denied_before_effect(self):
        with sqlite3.connect(self.fixt.fixt.src.mission_db) as db:
            db.execute(
                "UPDATE mission_execution_assignments SET state='READY' WHERE assignment_id=?",
                (self.fixt.fixt.aid,),
            )
        with self.assertRaisesRegex(Exception,"assignment must be HELD"):
            self.publish()
        self.assertEqual(self.count(),0)

    def test_original_pdp_missing_denied_before_insert(self):
        with sqlite3.connect(self.fixt.fixt.fixture.pdp_db) as db:
            db.execute("DELETE FROM r11_original_pdp_evidence")
        with self.assertRaisesRegex(R11OriginalR620PublishError,
                                    "canonical R6.20/PDP"):
            self.publish()
        self.assertEqual(self.count(),0)

    def test_readback_failure_after_commit_yields_effect_unknown(self):
        pub=self.publisher()
        with patch.object(self.reader,"resolve_exact",side_effect=RuntimeError("offline")):
            with self.assertRaisesRegex(R11OriginalR620EffectUnknown,
                                        "readback unknown"):
                self.publish(pub)
        self.assertEqual(self.count(),1)

    def test_original_operator_changed_while_issuer_responds_fails_before_effect(self):
        def pauser(aid,mission,generation,digest,now):
            with sqlite3.connect(self.fixt.fixt.src.mission_db) as db:
                db.execute(
                    "UPDATE mission_execution_assignments SET state='READY' "
                    "WHERE assignment_id=?",(aid,),
                )
        self.issuer.resolve_issued_exact=lambda *args: (
            pauser(*args) or self.issuer.row
        )
        with self.assertRaisesRegex(R11OriginalR620PublishError,
                                    "operator/driver changed before publication"):
            self.publish()
        self.assertEqual(self.count(),0)

    def test_expired_signature_at_commit_window_denied_without_insert(self):
        # The signed record is valid at issue time, but would have expired
        # while the publisher performed independent revalidation.
        from dataclasses import replace as dc_replace
        import json
        record=json.loads(self.issuer.row.record_json)
        record["expires_at"]=(self.now+timedelta(seconds=1)).isoformat()
        from cyber_lion.enterprise.r11_signed_original_r620_parts import (
            DOMAIN,canonical_record_bytes,
        )
        canonical=canonical_record_bytes(record)
        self.issuer.row=dc_replace(
            self.issuer.row,record_json=canonical.decode("utf-8"),
            signature_hex=self.fixt.key.sign(DOMAIN+canonical).hex(),
        )
        increments=[0]
        def clock():
            increments[0]+=1
            return self.now if increments[0]==1 else self.now+timedelta(seconds=2)
        pub=self.publisher(now_fn=clock)
        with self.assertRaisesRegex(R11OriginalR620PublishError,
                                    "expired before write"):
            self.publish(pub)
        self.assertEqual(self.count(),0)

    def test_missing_preprovisioned_store_is_not_created(self):
        self.fixt.path.unlink()
        with self.assertRaises(Exception):
            self.publisher()
        self.assertFalse(self.fixt.path.exists())

    def test_stale_publisher_time_denied_before_read(self):
        pub=self.publisher(now_fn=lambda:self.now+timedelta(seconds=10))
        with self.assertRaisesRegex(R11OriginalR620PublishError,"time not current"):
            self.publish(pub)
        self.assertEqual(self.issuer.calls,0)
        self.assertEqual(self.count(),0)


if __name__=="__main__":
    unittest.main()

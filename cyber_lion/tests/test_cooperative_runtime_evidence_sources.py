from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from cyber_lion.tests import test_executor_sandbox as sb
from cyber_lion.tests import test_runtime_currentness as rc
from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.enterprise.cooperative_context_resolver import CooperativeContextPin
from cyber_lion.enterprise.cooperative_runtime_evidence_sources import (
    CooperativeRuntimeEvidenceError,
    SQLiteCooperativeRuntimeEvidencePublisher,
    SQLiteContextPinSource,
    SQLiteEffectTimeCurrentnessSource,
    SQLiteEvidenceRuntimeAdmissionSource,
    SQLiteFleetDispatchSource,
    SQLiteProvisioningBindingSource,
    SQLiteRuntimeIdentitySource,
    SQLiteTransferBindingSource,
)


class CooperativeRuntimeEvidenceSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.db = self.root / "evidence.sqlite"
        self.now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
        self.exp = self.now + timedelta(minutes=5)
        self.pub = SQLiteCooperativeRuntimeEvidencePublisher(self.db)
        self.dispatch = sb.dispatch(mission_id="M1", drone_id="drone:1")
        self.provisioning = sb.provisioning(
            mission_id="M1", drone_id="drone:1", executor_id="executor:1",
            runtime_instance_id="runtime:1", sandbox_id="sandbox:1", workspace_id="workspace:1",
        )
        self.identity = rt.identity()
        self.authority = rc.authority()
        self.admission = rt.admission(rt.effect(self.identity), self.identity)
        self.pin = CooperativeContextPin("assignment-1", "context-1.json", "d" * 64).validate()
        self.prov = sha256(b"canonical-owner-evidence").hexdigest()

    def publish_all(self):
        self.pub.publish_runtime_admission(
            self.admission, provenance_digest=self.prov,
            observed_at=self.now, expires_at=self.exp,
        )
        self.pub.publish_context_pin(
            self.pin, provenance_digest=self.prov,
            observed_at=self.now, expires_at=self.exp,
        )
        self.pub.publish_dispatch(
            self.dispatch, provenance_digest=self.prov,
            observed_at=self.now, expires_at=self.exp,
        )
        self.pub.publish_provisioning(
            "assignment-1", self.provisioning, provenance_digest=self.prov,
            observed_at=self.now, expires_at=self.exp,
        )
        self.pub.publish_runtime_identity(
            self.identity, provenance_digest=self.prov,
            observed_at=self.now, expires_at=self.exp,
        )
        self.pub.publish_currentness(
            "a" * 64, self.authority,
            policy_binding=rc.POLICY,
            runtime_identity_digest=self.identity.digest(),
            requested_effect_digest="b" * 64,
            observability_state="HEALTHY",
            provenance_digest=self.prov,
            observed_at=self.now, expires_at=self.exp,
        )
        self.pub.publish_transfer_binding(
            "assignment-1", "CONTEXT",
            {"assignment_id": "assignment-1", "mission_id": "M1", "generation": 1},
            provenance_digest=self.prov,
            observed_at=self.now, expires_at=self.exp,
        )

    def test_exact_sources_roundtrip_existing_contracts(self):
        self.publish_all()
        clock = lambda: self.now + timedelta(seconds=1)
        self.assertEqual(
            SQLiteEvidenceRuntimeAdmissionSource(self.db, rt.trust(), now_fn=clock).resolve(
                self.admission.admission_digest
            ),
            self.admission,
        )
        self.assertEqual(
            SQLiteContextPinSource(self.db, now_fn=clock)("assignment-1"),
            self.pin,
        )
        self.assertEqual(
            SQLiteFleetDispatchSource(self.db, now_fn=clock).current_dispatch("M1"),
            self.dispatch,
        )
        self.assertEqual(
            SQLiteProvisioningBindingSource(self.db, now_fn=clock)("assignment-1"),
            self.provisioning,
        )
        self.assertEqual(
            SQLiteRuntimeIdentitySource(self.db, now_fn=clock)("runtime:1"),
            self.identity,
        )
        current = SQLiteEffectTimeCurrentnessSource(self.db, rc.trust(), now_fn=clock)
        self.assertEqual(current.resolve_authority("a" * 64), self.authority)
        self.assertEqual(current.current_policy_binding(rc.POLICY), rc.POLICY)
        self.assertEqual(
            current.current_observability_state(self.identity.digest(), "b" * 64),
            "HEALTHY",
        )
        binding = SQLiteTransferBindingSource(self.db, now_fn=clock)("assignment-1", "CONTEXT")
        self.assertEqual(binding["assignment_id"], "assignment-1")
        self.assertEqual(binding["generation"], 1)

    def test_expired_evidence_fails_closed_for_every_source(self):
        self.publish_all()
        clock = lambda: self.exp + timedelta(seconds=1)
        sources = [
            lambda: SQLiteEvidenceRuntimeAdmissionSource(self.db, rt.trust(), now_fn=clock).resolve(self.admission.admission_digest),
            lambda: SQLiteContextPinSource(self.db, now_fn=clock)("assignment-1"),
            lambda: SQLiteFleetDispatchSource(self.db, now_fn=clock).current_dispatch("M1"),
            lambda: SQLiteProvisioningBindingSource(self.db, now_fn=clock)("assignment-1"),
            lambda: SQLiteRuntimeIdentitySource(self.db, now_fn=clock)("runtime:1"),
            lambda: SQLiteEffectTimeCurrentnessSource(self.db, rc.trust(), now_fn=clock).resolve_authority("a" * 64),
            lambda: SQLiteTransferBindingSource(self.db, now_fn=clock)("assignment-1", "CONTEXT"),
        ]
        for action in sources:
            with self.subTest(action=action):
                with self.assertRaisesRegex(CooperativeRuntimeEvidenceError, "stale"):
                    action()

    def test_source_database_replacement_is_denied(self):
        self.publish_all()
        source = SQLiteFleetDispatchSource(self.db, now_fn=lambda: self.now)
        replacement = self.root / "replacement.sqlite"
        replacement.write_bytes(self.db.read_bytes())
        self.db.unlink()
        replacement.replace(self.db)
        with self.assertRaisesRegex(CooperativeRuntimeEvidenceError, "identity drift"):
            source.current_dispatch("M1")

    def test_digest_tamper_is_rejected(self):
        self.publish_all()
        import sqlite3
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE dispatch_evidence SET record_digest=? WHERE mission_id='M1'", ("f" * 64,))
            db.commit()
        with self.assertRaisesRegex(CooperativeRuntimeEvidenceError, "digest mismatch"):
            SQLiteFleetDispatchSource(self.db, now_fn=lambda: self.now).current_dispatch("M1")

    def test_currentness_source_trust_binding_is_independent(self):
        self.publish_all()
        source = SQLiteEffectTimeCurrentnessSource(self.db, rc.trust(), now_fn=lambda: self.now)
        self.assertEqual(
            (
                source.source_id, source.source_instance_id, source.implementation_digest,
                source.trust_anchor_id, source.trust_anchor_digest,
            ),
            rc.trust().binding(),
        )

    def test_observability_ambiguity_fails_closed(self):
        self.publish_all()
        second = replace(self.authority, admitted_at="2026-08-23T13:01:00+00:00")
        self.pub.publish_currentness(
            "c" * 64, second,
            policy_binding=rc.POLICY,
            runtime_identity_digest=self.identity.digest(),
            requested_effect_digest="b" * 64,
            observability_state="HEALTHY",
            provenance_digest=self.prov,
            observed_at=self.now, expires_at=self.exp,
        )
        current = SQLiteEffectTimeCurrentnessSource(self.db, rc.trust(), now_fn=lambda: self.now)
        with self.assertRaisesRegex(CooperativeRuntimeEvidenceError, "ambiguous"):
            current.current_observability_state(self.identity.digest(), "b" * 64)

    def test_publisher_rejects_noncanonical_provenance_and_windows(self):
        with self.assertRaisesRegex(CooperativeRuntimeEvidenceError, "provenance"):
            self.pub.publish_dispatch(
                self.dispatch, provenance_digest="bad",
                observed_at=self.now, expires_at=self.exp,
            )
        with self.assertRaisesRegex(CooperativeRuntimeEvidenceError, "expiry"):
            self.pub.publish_dispatch(
                self.dispatch, provenance_digest=self.prov,
                observed_at=self.now, expires_at=self.now,
            )


if __name__ == "__main__":
    unittest.main()

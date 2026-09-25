from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import sqlite3
import unittest

from cyber_lion.mission_control.mission_reconciliation import (
    R24_OTP_PAIRING_EVENT,
    R24_OTP_PAIRING_SCHEMA,
    R24_OTP_PAIRING_SENDER,
    _r24_otp_pairing_evidence,
)


class R24OtpPairingCompletionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """CREATE TABLE protocol_messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                protocol TEXT NOT NULL,
                from_id TEXT NOT NULL,
                to_id TEXT NOT NULL,
                phase TEXT,
                direction TEXT,
                payload_json TEXT NOT NULL,
                payload_digest TEXT NOT NULL
            )"""
        )
        self.now = datetime(2026, 9, 25, 12, 48, 31, tzinfo=timezone.utc)

    def tearDown(self):
        self.conn.close()

    def payload(self, **changes):
        value = {
            "event": R24_OTP_PAIRING_EVENT,
            "schema": R24_OTP_PAIRING_SCHEMA,
            "windows_host": "MOON",
            "panel_port": 8780,
            "operator_port": 8767,
            "root_status": 200,
            "before_paired": False,
            "pair_paired": True,
            "pair_principal": "OPERATOR_PRIMARY",
            "after_paired": True,
            "pair_response_secret_fields": False,
            "unpair_revoked": True,
            "final_paired": False,
            "cleanup": "UNPAIRED",
            "authority_effect": "NONE",
        }
        value.update(changes)
        return value

    def record(self, payload=None, *, sender=R24_OTP_PAIRING_SENDER, observed_at=None, phase="OTP_PAIRING"):
        payload = payload or self.payload()
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self.conn.execute(
            "INSERT INTO protocol_messages(mission_id,observed_at,protocol,from_id,to_id,phase,direction,payload_json,payload_digest) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "M1",
                (observed_at or self.now).isoformat().replace("+00:00", "Z"),
                "EVIDENCE",
                sender,
                "MISSION_CONTROL",
                phase,
                "IN",
                raw,
                hashlib.sha256(raw.encode()).hexdigest(),
            ),
        )
        self.conn.commit()

    def test_exact_live_pair_unpair_cycle_is_accepted(self):
        self.record()
        evidence = _r24_otp_pairing_evidence(self.conn, "M1", "OTP_PAIRING", now_value=self.now)
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence["pairing_cycle"], "UNPAIRED_TO_PAIRED_TO_UNPAIRED")
        self.assertTrue(evidence["secret_nondisclosure"])
        self.assertEqual(evidence["authority_effect"], "NONE")

    def test_wrong_sender_fails_closed(self):
        self.record(sender="MODEL_PROPOSAL")
        self.assertIsNone(_r24_otp_pairing_evidence(self.conn, "M1", "OTP_PAIRING", now_value=self.now))

    def test_stale_evidence_fails_closed(self):
        self.record(observed_at=self.now - timedelta(seconds=901))
        self.assertIsNone(_r24_otp_pairing_evidence(self.conn, "M1", "OTP_PAIRING", now_value=self.now))

    def test_secret_disclosure_flag_fails_closed(self):
        self.record(self.payload(pair_response_secret_fields=True))
        self.assertIsNone(_r24_otp_pairing_evidence(self.conn, "M1", "OTP_PAIRING", now_value=self.now))

    def test_cleanup_and_unpair_are_mandatory(self):
        self.record(self.payload(unpair_revoked=False, final_paired=True, cleanup="PAIRED"))
        self.assertIsNone(_r24_otp_pairing_evidence(self.conn, "M1", "OTP_PAIRING", now_value=self.now))


if __name__ == "__main__":
    unittest.main()

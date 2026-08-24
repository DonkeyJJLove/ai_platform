from __future__ import annotations

import base64
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import json
import unittest

from cyber_lion.contracts.group_channel import (
    GroupChannelContractError,
    GroupChannelEnvelope,
    GroupChannelReceipt,
    MAX_ENVELOPE_BYTES,
    REPOSITORY,
    canonical_json,
    decode_envelope,
    encode_envelope,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
HEAD = "a" * 40


def envelope(*, target: str = "architecture", payload: object | None = None) -> GroupChannelEnvelope:
    return GroupChannelEnvelope.build(
        repository=REPOSITORY,
        message_id="e003-message-001",
        target=target,
        expected_master_head=HEAD,
        issued_at=(NOW - timedelta(minutes=1)).isoformat(),
        expires_at=(NOW + timedelta(minutes=15)).isoformat(),
        payload={"kind": "status", "value": 1} if payload is None else payload,
        now=NOW,
    )


class GroupChannelContractTests(unittest.TestCase):
    def test_round_trip_accepts_only_allowlisted_targets(self) -> None:
        for target in ("architecture", "security", "runtime"):
            observed = decode_envelope(encode_envelope(envelope(target=target)), now=NOW)
            self.assertEqual(observed.target, target)
        with self.assertRaisesRegex(GroupChannelContractError, "allowlisted"):
            envelope(target="release")

    def test_bad_or_noncanonical_base64_is_denied(self) -> None:
        for encoded in ("%%%", "YWJj\n", "YWJj=", ""):
            with self.assertRaises(GroupChannelContractError):
                decode_envelope(encoded, now=NOW)

    def test_noncanonical_and_duplicate_json_are_denied(self) -> None:
        value = asdict(envelope())
        malformed = base64.b64encode(b'{"schema_version":').decode("ascii")
        with self.assertRaisesRegex(GroupChannelContractError, "strict UTF-8 JSON"):
            decode_envelope(malformed, now=NOW)

        spaced = json.dumps(value, ensure_ascii=False).encode("utf-8")
        with self.assertRaisesRegex(GroupChannelContractError, "not canonical"):
            decode_envelope(base64.b64encode(spaced).decode("ascii"), now=NOW)

        canonical = canonical_json(value).decode("utf-8")
        duplicate = canonical.replace('{"envelope_digest":', '{"message_id":"duplicate","envelope_digest":', 1)
        with self.assertRaisesRegex(GroupChannelContractError, "duplicate"):
            decode_envelope(base64.b64encode(duplicate.encode("utf-8")).decode("ascii"), now=NOW)

    def test_eight_kibibyte_bound_is_strict(self) -> None:
        oversized = envelope(payload={"data": "x" * MAX_ENVELOPE_BYTES})
        with self.assertRaisesRegex(GroupChannelContractError, "8 KiB"):
            encode_envelope(oversized)
        encoded = base64.b64encode(b"{" + b"x" * MAX_ENVELOPE_BYTES + b"}").decode("ascii")
        with self.assertRaisesRegex(GroupChannelContractError, "bound"):
            decode_envelope(encoded, now=NOW)

    def test_digest_and_head_substitution_are_denied(self) -> None:
        valid = envelope()
        for changed in (
            replace(valid, payload_digest="0" * 64),
            replace(valid, envelope_digest="0" * 64),
            replace(valid, expected_master_head="A" * 40),
        ):
            raw = canonical_json(asdict(changed))
            with self.assertRaises(GroupChannelContractError):
                decode_envelope(base64.b64encode(raw).decode("ascii"), now=NOW)

    def test_expired_future_and_overlong_lifetime_are_denied(self) -> None:
        for issued, expires in (
            (NOW - timedelta(hours=2), NOW - timedelta(hours=1)),
            (NOW + timedelta(seconds=1), NOW + timedelta(minutes=5)),
            (NOW - timedelta(minutes=1), NOW + timedelta(hours=2)),
        ):
            with self.assertRaises(GroupChannelContractError):
                GroupChannelEnvelope.build(
                    repository=REPOSITORY,
                    message_id="time-test",
                    target="runtime",
                    expected_master_head=HEAD,
                    issued_at=issued.isoformat(),
                    expires_at=expires.isoformat(),
                    payload={},
                    now=NOW,
                )

    def test_injection_path_and_authority_fields_remain_opaque(self) -> None:
        hostile = {
            "command": "$(touch /tmp/lion-channel-owned); rm -rf /",
            "path": "../../.github/workflows/release.yml",
            "authority": {"role": "admin", "grant": True},
        }
        observed = decode_envelope(encode_envelope(envelope(payload=hostile)), now=NOW)
        self.assertEqual(observed.payload, hostile)
        receipt = GroupChannelReceipt.build(
            envelope=observed,
            emitted_at=NOW.isoformat(),
            workflow_run_id=123,
            workflow_run_attempt=1,
        )
        rendered = asdict(receipt)
        self.assertNotIn("payload", rendered)
        self.assertFalse(receipt.authority_effect)
        self.assertFalse(receipt.repository_effect)
        self.assertEqual(receipt.state, "EMITTED_EVIDENCE_ONLY")


if __name__ == "__main__":
    unittest.main()

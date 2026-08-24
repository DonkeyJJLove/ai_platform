from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from cyber_lion.contracts.group_channel import (
    GroupChannelContractError,
    GroupChannelEnvelope,
    REPOSITORY,
    encode_envelope,
)
from cyber_lion.enterprise.group_channel import emit_evidence_receipt, main

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
HEAD = "b" * 40


def encoded(payload: object | None = None) -> str:
    value = GroupChannelEnvelope.build(
        repository=REPOSITORY,
        message_id="e003-runtime-message",
        target="security",
        expected_master_head=HEAD,
        issued_at=(NOW - timedelta(minutes=1)).isoformat(),
        expires_at=(NOW + timedelta(minutes=10)).isoformat(),
        payload={"summary": "bounded"} if payload is None else payload,
        now=NOW,
    )
    return encode_envelope(value)


class GroupChannelEmitterTests(unittest.TestCase):
    def test_exact_head_emits_evidence_only_receipt(self) -> None:
        receipt = emit_evidence_receipt(
            envelope_b64=encoded(),
            actual_master_head=HEAD,
            workflow_run_id=555,
            workflow_run_attempt=2,
            now=NOW,
        )
        self.assertEqual(receipt.expected_master_head, HEAD)
        self.assertEqual(receipt.state, "EMITTED_EVIDENCE_ONLY")
        self.assertFalse(receipt.authority_effect)
        self.assertFalse(receipt.repository_effect)

    def test_head_mismatch_is_fail_closed(self) -> None:
        with self.assertRaisesRegex(GroupChannelContractError, "differs"):
            emit_evidence_receipt(
                envelope_b64=encoded(),
                actual_master_head="c" * 40,
                workflow_run_id=555,
                workflow_run_attempt=1,
                now=NOW,
            )

    def test_hostile_payload_is_not_executed_used_as_path_or_logged(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            sentinel = Path(root) / "owned"
            hostile = {
                "command": f"touch {sentinel}",
                "path": str(sentinel),
                "authority": "root",
                "secret-shaped": "do-not-log-this-payload",
            }
            receipt = emit_evidence_receipt(
                envelope_b64=encoded(hostile),
                actual_master_head=HEAD,
                workflow_run_id=1,
                workflow_run_attempt=1,
                now=NOW,
            )
            self.assertFalse(sentinel.exists())
            self.assertNotIn("do-not-log-this-payload", json.dumps(receipt.__dict__))

    def test_cli_prints_receipt_without_payload(self) -> None:
        environment = {
            "LION_GROUP_CHANNEL_ENVELOPE_B64": encoded({"private-message": "never-print"}),
            "LION_GROUP_CHANNEL_ACTUAL_HEAD": HEAD,
            "GITHUB_RUN_ID": "42",
            "GITHUB_RUN_ATTEMPT": "1",
        }
        buffer = io.BytesIO()
        stdout = io.TextIOWrapper(buffer, encoding="utf-8")
        with mock.patch.dict(os.environ, environment, clear=True), mock.patch(
            "cyber_lion.enterprise.group_channel.datetime"
        ) as clock, mock.patch("sys.stdout", stdout):
            clock.now.return_value = NOW
            clock.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            self.assertEqual(main(), 0)
            stdout.flush()
        rendered = buffer.getvalue().decode("utf-8")
        self.assertNotIn("never-print", rendered)
        self.assertEqual(json.loads(rendered)["state"], "EMITTED_EVIDENCE_ONLY")

    def test_workflow_is_read_only_pinned_and_payload_silent(self) -> None:
        text = Path(".github/workflows/lion-group-channel.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("contents: read", text)
        self.assertIn("persist-credentials: false", text)
        for forbidden in (
            "pull_request_target",
            "contents: write",
            "actions: write",
            "issues: write",
            "secrets.",
            "github.token",
        ):
            self.assertNotIn(forbidden, text)
        uses = re.findall(r"uses:\s*([^\s]+)", text)
        self.assertTrue(uses)
        self.assertTrue(all(re.fullmatch(r"actions/[A-Za-z0-9_-]+@[0-9a-f]{40}", item) for item in uses))
        self.assertNotIn("echo $LION_GROUP_CHANNEL_ENVELOPE_B64", text)
        self.assertNotIn("print(envelope", text)
        self.assertIn("EMITTED_EVIDENCE_ONLY", text)


if __name__ == "__main__":
    unittest.main()

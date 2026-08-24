"""Evidence-only GitHub Actions group channel emitter.

The decoded message payload is validated as opaque JSON, then discarded.  Only
its digest and immutable routing bindings are copied into the receipt.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
import sys
from typing import Mapping

from cyber_lion.contracts.group_channel import (
    GroupChannelContractError,
    GroupChannelReceipt,
    decode_envelope,
    receipt_json,
)


def emit_evidence_receipt(
    *,
    envelope_b64: str,
    actual_master_head: str,
    workflow_run_id: int,
    workflow_run_attempt: int,
    now: datetime,
) -> GroupChannelReceipt:
    envelope = decode_envelope(envelope_b64, now=now)
    if actual_master_head != envelope.expected_master_head:
        raise GroupChannelContractError("actual master head differs from expected head")
    return GroupChannelReceipt.build(
        envelope=envelope,
        emitted_at=now.astimezone(timezone.utc).isoformat(),
        workflow_run_id=workflow_run_id,
        workflow_run_attempt=workflow_run_attempt,
    )


def receipt_from_environment(environment: Mapping[str, str]) -> GroupChannelReceipt:
    required = {
        "LION_GROUP_CHANNEL_ENVELOPE_B64",
        "LION_GROUP_CHANNEL_ACTUAL_HEAD",
        "GITHUB_RUN_ID",
        "GITHUB_RUN_ATTEMPT",
    }
    missing = sorted(name for name in required if not environment.get(name))
    if missing:
        raise GroupChannelContractError("required workflow environment is incomplete")
    try:
        run_id = int(environment["GITHUB_RUN_ID"])
        run_attempt = int(environment["GITHUB_RUN_ATTEMPT"])
    except ValueError as exc:
        raise GroupChannelContractError("workflow run identifiers invalid") from exc
    return emit_evidence_receipt(
        envelope_b64=environment["LION_GROUP_CHANNEL_ENVELOPE_B64"],
        actual_master_head=environment["LION_GROUP_CHANNEL_ACTUAL_HEAD"],
        workflow_run_id=run_id,
        workflow_run_attempt=run_attempt,
        now=datetime.now(timezone.utc),
    )


def main() -> int:
    receipt = receipt_from_environment(os.environ)
    sys.stdout.buffer.write(receipt_json(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

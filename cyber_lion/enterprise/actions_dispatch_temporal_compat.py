"""Bounded temporal-compatibility shim for Actions run observation.

Existing LION-DISPATCH v1 receipts record accepted_at after the dispatch API call returns.
A run may therefore have a GitHub created_at a few seconds before accepted_at. This shim
keeps every exact workflow/event/ref/head binding and ambiguity denial, but permits at
most a 60-second legacy lookback. It does not dispatch and does not mint authority.
"""
from __future__ import annotations

from datetime import timedelta

from cyber_lion.enterprise import actions_dispatch_bridge as bridge

LEGACY_LOOKBACK_SECONDS = 60


def _matching_runs_compat(runs: list[dict], receipt: bridge.DispatchReceipt) -> list[dict]:
    accepted = bridge._parse_time(receipt.accepted_at)
    lower_bound = accepted - timedelta(seconds=LEGACY_LOOKBACK_SECONDS)
    matches: list[dict] = []
    for run in runs:
        try:
            created = bridge._parse_time(str(run["created_at"]))
            run_id = int(run["id"])
        except (KeyError, ValueError, TypeError):
            continue
        if (
            run.get("event") == "workflow_dispatch"
            and run.get("head_branch") == receipt.ref
            and str(run.get("head_sha", "")).lower() == receipt.expected_head
            and created >= lower_bound
            and run_id > 0
        ):
            matches.append(run)
    matches.sort(key=lambda item: int(item["id"]))
    return matches


def main(argv: list[str] | None = None) -> int:
    bridge._matching_runs = _matching_runs_compat
    return bridge.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

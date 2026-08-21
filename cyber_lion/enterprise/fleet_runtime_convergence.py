"""Fail-closed verifier for externally materialized authoritative F005 runtime snapshots."""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
from typing import Any

from cyber_lion.contracts.fleet_runtime_convergence import (
    RuntimeFleetConvergenceContractError,
    RuntimeFleetConvergenceSnapshot,
)


class RuntimeFleetConvergenceError(RuntimeError):
    pass


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeFleetConvergenceError("observed_at invalid") from exc
    if parsed.tzinfo is None:
        raise RuntimeFleetConvergenceError("observed_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def load_snapshot(path: str | Path) -> RuntimeFleetConvergenceSnapshot:
    raw = Path(path).read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeFleetConvergenceError("snapshot JSON invalid") from exc
    if not isinstance(value, dict):
        raise RuntimeFleetConvergenceError("snapshot must be an object")
    expected = set(RuntimeFleetConvergenceSnapshot.__dataclass_fields__)
    if set(value) != expected:
        raise RuntimeFleetConvergenceError("snapshot fields must match exact contract")
    try:
        return RuntimeFleetConvergenceSnapshot(**value).validate()
    except (TypeError, RuntimeFleetConvergenceContractError) as exc:
        raise RuntimeFleetConvergenceError("snapshot contract denied") from exc


def verify_snapshot(
    snapshot: RuntimeFleetConvergenceSnapshot,
    *,
    repository: str,
    expected_master: str,
    expected_master_tree: str,
    now: datetime,
    max_age_seconds: int = 300,
) -> dict[str, Any]:
    snapshot.validate()
    if snapshot.repository != repository:
        raise RuntimeFleetConvergenceError("repository binding mismatch")
    if snapshot.current_master != expected_master:
        raise RuntimeFleetConvergenceError("master binding mismatch")
    if snapshot.current_master_tree != expected_master_tree:
        raise RuntimeFleetConvergenceError("master tree binding mismatch")
    if now.tzinfo is None:
        raise RuntimeFleetConvergenceError("trusted verification clock must be timezone-aware")
    observed = _parse_time(snapshot.observed_at)
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    if age < 0 or age > max_age_seconds:
        raise RuntimeFleetConvergenceError("stale or future runtime snapshot denied")
    blockers = snapshot.blocker_codes()
    if blockers:
        raise RuntimeFleetConvergenceError("runtime convergence blockers: " + ",".join(blockers))
    return {
        "schema_version": "1.0.0",
        "status": "FLEET_CLOSABLE",
        "repository": repository,
        "current_master": expected_master,
        "current_master_tree": expected_master_tree,
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_digest": snapshot.digest(),
        "source_kind": snapshot.source_kind,
        "source_instance": snapshot.source_instance,
        "source_digest": snapshot.source_digest,
        "observed_at": snapshot.observed_at,
        "verified_at": now.astimezone(timezone.utc).isoformat(),
        "blockers": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--expected-master", required=True)
    parser.add_argument("--expected-master-tree", required=True)
    parser.add_argument("--max-age-seconds", type=int, default=300)
    args = parser.parse_args(argv)
    if args.max_age_seconds < 1:
        raise RuntimeFleetConvergenceError("max age must be positive")
    snapshot = load_snapshot(args.snapshot)
    receipt = verify_snapshot(
        snapshot,
        repository=args.repository,
        expected_master=args.expected_master,
        expected_master_tree=args.expected_master_tree,
        now=datetime.now(timezone.utc),
        max_age_seconds=args.max_age_seconds,
    )
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

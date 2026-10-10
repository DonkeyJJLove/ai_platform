#!/usr/bin/env python3
"""Non-authorizing, stdout-only service ledger inspection and proposed evolution.

Usage from repo root:
  python tools/lion_service_continuation_ledger.py validate
  python tools/lion_service_continuation_ledger.py next
  python tools/lion_service_continuation_ledger.py propose-transition --task SVC-0001 \
     --to IN_PROGRESS --actor operator --at 2026-10-10T23:00:00Z \
     --evidence-ref SOURCE:exact-reference > /tmp/next-ledger.json

No file is updated by this command. Commit proposed data through ordinary
review/currentness; it cannot execute actions, issue authority or start LPCL.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from cyber_lion.contracts.service_continuation_ledger import (
    ServiceContinuationLedgerError,
    assert_append_only,
    next_ready_tasks,
    propose_event,
    validate_ledger,
)

DEFAULT = REPO_ROOT / "LION/architecture/v1_5/SERVICE_CONTINUATION_LEDGER_R1.json"


def _read(path: Path) -> dict:
    source = path.resolve(strict=True)
    if not source.is_file() or source.stat().st_size > 2_000_000:
        raise ServiceContinuationLedgerError("ledger path is unavailable or oversized")
    return json.loads(source.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    commands.add_parser("next")
    compare = commands.add_parser("validate-append")
    compare.add_argument("--previous", required=True, type=Path)
    advance = commands.add_parser("propose-transition")
    advance.add_argument("--task", required=True)
    advance.add_argument("--to", required=True)
    advance.add_argument("--actor", required=True)
    advance.add_argument("--at", required=True)
    advance.add_argument("--evidence-ref", action="append", default=[])
    register = commands.add_parser("propose-register")
    register.add_argument("--new-task-json", required=True, type=Path)
    register.add_argument("--actor", required=True)
    register.add_argument("--at", required=True)
    register.add_argument("--evidence-ref", action="append", required=True)
    args = parser.parse_args(argv)

    try:
        doc = _read(args.ledger)
        states = validate_ledger(doc)
        if args.command == "validate":
            print(json.dumps({
                "status": "VALID", "schema": doc["schema"], "ledger_id": doc["ledger_id"],
                "revision": doc["revision"], "task_count": len(states),
                "counts": {state: sum(x == state for x in states.values()) for state in sorted(set(states.values()))},
                "event_chain_head": doc["event_chain_head"], "authority_effect": "NONE"
            }, sort_keys=True, ensure_ascii=False))
        elif args.command == "next":
            print(json.dumps({"status": "VALID", "ready": next_ready_tasks(doc),
                              "authority_effect": "NONE", "runtime_effect": "NONE"},
                             sort_keys=True, ensure_ascii=False, indent=2))
        elif args.command == "validate-append":
            prior = _read(args.previous)
            states = assert_append_only(prior, doc)
            print(json.dumps({"status": "VALID_APPEND_ONLY", "revision": doc["revision"],
                              "task_count": len(states), "authority_effect": "NONE"}, sort_keys=True))
        elif args.command == "propose-transition":
            proposal = propose_event(doc, kind="TRANSITION", task_id=args.task, actor=args.actor,
                                     observed_at=args.at, evidence_refs=args.evidence_ref, to_state=args.to)
            print(json.dumps(proposal, sort_keys=True, ensure_ascii=False, indent=2))
        elif args.command == "propose-register":
            task = _read(args.new_task_json)
            proposal = propose_event(doc, kind="REGISTER_TASK", task_id=task["task_id"],
                                     actor=args.actor, observed_at=args.at,
                                     evidence_refs=args.evidence_ref, task=task)
            print(json.dumps(proposal, sort_keys=True, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError, ServiceContinuationLedgerError) as exc:
        print(f"SERVICE_LEDGER=DENY:{type(exc).__name__}:{str(exc)[:180]}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

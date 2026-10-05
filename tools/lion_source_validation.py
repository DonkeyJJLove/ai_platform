#!/usr/bin/env python3
"""Source-validation projection over the canonical R24 full-closure gate.

This does not weaken currentness. It distinguishes ordinary source validity
from the expected invalidation of carrier-last currentness artifacts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import lion_r24_whole_integration_gate as full_gate

SCHEMA = "lion.source-validation/v1"
ALLOWED_PENDING_CLOSURE = frozenset({
    "STALE_EXACT_CURRENTNESS_CARRIER",
    "TRUTH_PLANE_MISMATCH",
})


def classify_gate(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise ValueError("gate result mapping required")
    reasons = frozenset(str(x) for x in (result.get("reasons") or ()))
    authority_effect = result.get("authority_effect")
    critical = result.get("critical_tests") or {}
    facts = result.get("facts") or {}
    package = result.get("package") or {}
    structural_ok = (
        authority_effect == "NONE"
        and critical.get("pass") is True
        and facts.get("effect_inventory_mismatch") is False
        and facts.get("package_identity_mismatch") is False
        and int(facts.get("non_none_authority_effect_count") or 0) == 0
        and package.get("match") is True
    )
    non_currentness = sorted(reasons - ALLOWED_PENDING_CLOSURE)
    if not structural_ok:
        non_currentness = sorted(set(non_currentness) | {"SOURCE_VALIDATION_STRUCTURAL_FAILURE"})
    if non_currentness:
        status = "FAIL"
        currentness_state = "UNKNOWN_OR_SOURCE_FAILURE"
    elif reasons:
        status = "PASS"
        currentness_state = "CURRENTNESS_INVALIDATED_PENDING_CLOSURE"
    else:
        status = "PASS"
        currentness_state = "CURRENT"
    return {
        "schema": SCHEMA,
        "result": status,
        "currentness_state": currentness_state,
        "full_closure_result": result.get("result"),
        "full_closure_reasons": sorted(reasons),
        "allowed_pending_closure_reasons": sorted(ALLOWED_PENDING_CLOSURE),
        "blocking_source_reasons": non_currentness,
        "head": result.get("head"),
        "tree": result.get("tree"),
        "candidate_subject_digest": result.get("candidate_subject_digest"),
        "production_inventory": result.get("production_inventory"),
        "critical_tests": critical,
        "package": package,
        "authority_effect": "NONE",
        "runtime_effect": "NONE",
    }


def run_source_validation(*, run_tests: bool = True) -> dict[str, Any]:
    return classify_gate(full_gate.run_gate(run_tests=run_tests))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--no-tests", action="store_true")
    args = parser.parse_args()
    result = run_source_validation(run_tests=not args.no_tests)
    raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

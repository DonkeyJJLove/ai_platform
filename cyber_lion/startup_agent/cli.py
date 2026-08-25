"""Command-line interface for running one auditable Startup Evolution cycle from JSON."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .journal import EvolutionJournal
from .market_intelligence import MarketObservation
from .models import ProductHypothesis, StartupModelError, VentureVector
from .orchestrator import AIDrivenStartupAgent


def _dt(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StartupModelError(f"invalid ISO timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise StartupModelError(f"timestamp must be timezone-aware: {value}")
    return parsed


def load_input(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise StartupModelError("input root must be an object")
    return data


def parse_hypotheses(data: dict) -> List[ProductHypothesis]:
    result = []
    for raw in data.get("hypotheses", []):
        baseline = raw.get("baseline") or {}
        result.append(ProductHypothesis(
            hypothesis_id=raw["hypothesis_id"],
            customer=raw["customer"],
            problem=raw["problem"],
            solution=raw["solution"],
            revenue_model=raw.get("revenue_model", "unknown"),
            baseline=VentureVector(**baseline).validate(),
            assumptions=list(raw.get("assumptions", [])),
        ).validate())
    if not result:
        raise StartupModelError("input must contain at least one hypothesis")
    return result


def parse_observations(data: dict) -> List[MarketObservation]:
    result = []
    for raw in data.get("observations", []):
        result.append(MarketObservation(
            observation_id=raw["observation_id"],
            hypothesis_id=raw["hypothesis_id"],
            source=raw["source"],
            source_class=raw["source_class"],
            observed_at=_dt(raw["observed_at"]),
            captured_at=_dt(raw["captured_at"]),
            topic=raw["topic"],
            signal_kind=raw["signal_kind"],
            direction=raw["direction"],
            magnitude=float(raw["magnitude"]),
            confidence=float(raw["confidence"]),
            claim=raw["claim"],
            evidence_ref=raw.get("evidence_ref", ""),
        ).validate())
    return result


def plan_to_dict(plan, *, build_receipt=None, contradictions=None, freshness=None) -> Dict[str, Any]:
    return {
        "startup_id": plan.state.startup_id,
        "cycle": plan.state.cycle,
        "stage": plan.state.stage,
        "selected_hypothesis": plan.hypothesis.hypothesis_id,
        "score": round(plan.score, 6),
        "venture_vector": plan.state.vector.to_dict(),
        "delta": plan.state.delta(),
        "evidence_ids": list(plan.state.evidence_ids),
        "unknowns": list(plan.state.unknowns),
        "blockers": list(plan.state.blockers),
        "experiment": asdict(plan.experiment),
        "build_spec": asdict(plan.build_spec),
        "scaffold_files": sorted(plan.scaffold),
        "authority": asdict(plan.authority),
        "build_receipt": asdict(build_receipt) if build_receipt is not None else None,
        "contradictions": [asdict(item) for item in (contradictions or [])],
        "freshness": freshness or {},
    }


def run_cycle(data: dict, *, build_local: bool = False, journal_path: str | None = None) -> dict:
    startup_id = data.get("startup_id")
    if not startup_id:
        raise StartupModelError("startup_id is required")
    agent = AIDrivenStartupAgent(
        startup_id,
        max_signal_age_days=float(data.get("max_signal_age_days", 90.0)),
    )
    observations = parse_observations(data)
    agent.evidence.extend(observations)
    hypotheses = parse_hypotheses(data)
    plan = agent.plan(hypotheses, gate_event_id=data.get("gate_event_id"))

    build_receipt = None
    if build_local:
        execution_gate = data.get("local_build_gate_event_id")
        if not isinstance(execution_gate, str) or not execution_gate.strip():
            raise StartupModelError("--build-local requires local_build_gate_event_id")
        build_receipt = agent.build_local(plan, execution_gate_event_id=execution_gate)

    if journal_path:
        EvolutionJournal(journal_path).append(plan.state)

    return plan_to_dict(
        plan,
        build_receipt=build_receipt,
        contradictions=agent.evidence.contradictions(),
        freshness=agent.evidence.freshness_report(),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cyber-lion-startup",
        description="Run one evidence-aware Cyber-Lion Startup Evolution cycle from JSON.",
    )
    parser.add_argument("input", help="JSON file containing startup_id, hypotheses and market observations")
    parser.add_argument("--output", help="Write result JSON to this path; defaults to stdout")
    parser.add_argument("--journal", help="Append the resulting venture state to JSONL journal")
    parser.add_argument(
        "--build-local",
        action="store_true",
        help="Compile/test trusted local-prototype scaffold only with local_build_gate_event_id",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_cycle(load_input(args.input), build_local=args.build_local, journal_path=args.journal)
    except (KeyError, TypeError, ValueError, StartupModelError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2

    encoded = json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

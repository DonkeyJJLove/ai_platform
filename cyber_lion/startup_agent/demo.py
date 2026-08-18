"""Small deterministic demo: `python -m cyber_lion.startup_agent.demo`."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from .authority import StartupAuthorityGate
from .engine import StartupEvolutionAgent
from .models import MarketSignal, ProductHypothesis, VentureVector


def main() -> None:
    now = datetime.now(timezone.utc)
    hypothesis = ProductHypothesis(
        hypothesis_id="ai-sec-runtime-01",
        customer="AI-native software teams shipping agentic workflows",
        problem="Teams can build agents faster than they can observe and constrain consequential execution.",
        solution="A path-aware execution control plane with provenance and deterministic gates.",
        revenue_model="B2B usage + platform subscription",
        baseline=VentureVector(
            market_pull=0.50, evidence_strength=0.30, technical_feasibility=0.62,
            differentiation=0.58, distribution_access=0.32, delivery_velocity=0.70,
            security_readiness=0.76, unit_economics=0.48, learning_velocity=0.72,
        ),
        assumptions=["buyers have consequential agent workflows", "control can be added without destroying velocity"],
    )
    signals = [
        MarketSignal("sig-1", "customer-interview-1", now - timedelta(days=2), "pain", 0.9, 0.8,
                     "Team manually reviews tool calls before deployment."),
        MarketSignal("sig-2", "customer-interview-2", now - timedelta(days=4), "demand", 0.8, 0.75,
                     "Willing to test a runtime control layer."),
        MarketSignal("sig-3", "competitor-scan", now - timedelta(days=1), "competition", 0.55, 0.8,
                     "Adjacent tools exist, but path-level authority remains fragmented."),
    ]

    agent = StartupEvolutionAgent("cyber-lion-startup")
    state, chosen, experiment, score = agent.plan_cycle(None, [hypothesis], {hypothesis.hypothesis_id: signals}, now=now)
    gate = StartupAuthorityGate().decide(experiment)

    print(json.dumps({
        "hypothesis": chosen.hypothesis_id,
        "score": round(score, 4),
        "stage": state.stage,
        "vector": state.vector.to_dict(),
        "delta": state.delta(),
        "unknowns": state.unknowns,
        "blockers": state.blockers,
        "experiment": asdict(experiment),
        "authority": asdict(gate),
    }, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

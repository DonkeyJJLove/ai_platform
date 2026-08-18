# Startup Evolution Agent

A bounded agentic control loop for an AI-Driven startup.

## Purpose

The agent converts fresh market evidence into a changing product state, identifies the dominant uncertainty, selects the fastest high-information experiment and keeps execution authority outside probabilistic reasoning.

```text
MarketSignal[]
→ ProductHypothesis[]
→ VentureVector(t)
→ ranking
→ stage
→ bottleneck
→ Experiment
→ StartupAuthorityGate
→ observed outcome
→ VentureVector(t+1)
```

## Modules

- `models.py` — venture state, evidence, hypotheses and experiments.
- `engine.py` — evidence freshness, vector updates, hypothesis ranking, stage inference and experiment choice.
- `authority.py` — deterministic boundary between planning and external consequence.
- `demo.py` — runnable example.

## Venture vector

```text
market_pull
evidence_strength
technical_feasibility
differentiation
distribution_access
delivery_velocity
security_readiness
unit_economics
learning_velocity
```

All dimensions are normalized to `[0,1]`. This is an engineering representation, not a universal business law.

## Freshness

Signals decay exponentially by age. The default evidence half-life is 30 days and the agent can reject signals older than its configured market window. This prevents old observations from silently representing the current market.

## Authority

`analysis` and `local_prototype` can be allowed autonomously. `external_write`, `deploy` and `financial` require an explicit gate event.

```text
model proposes
≠
organization authorizes
```

## Run

```bash
python -m cyber_lion.startup_agent.demo
python -m unittest discover -s cyber_lion/tests -p "test_*.py" -v
```

## Integration direction

The agent should consume typed market observations through Cyber-Lion `EventEnvelope`, use `CapabilityRegistry` to discover research/build/test providers and hand consequential execution to deterministic contracts rather than directly calling tools.

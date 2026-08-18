# CYBER-LION / ai_platform

**AI-Driven startup control plane for rapid, evidence-aware software evolution.**

`ai_platform` is the control-plane repository of **CYBER-LION**: a federated Human–AI / agentic software platform that separates probabilistic intelligence from execution authority.

The first executable product built on top of the shared Cyber-Lion contracts is the **Startup Evolution Agent** — an agent designed to help an AI-Driven startup identify what the current market is actually rewarding, choose the fastest useful experiment, build software around the strongest evidence, observe the outcome and evolve again.

The design principle is simple:

```text
speed without evidence = drift
intelligence without authority control = risk
analysis without execution = no company
execution without observability = no control
```

Cyber-Lion therefore uses:

```text
OBSERVE
→ STRUCTURE
→ HYPOTHESISE
→ FALSIFY
→ CHOOSE EXPERIMENT
→ CHECK AUTHORITY
→ EXECUTE
→ OBSERVE OUTCOME
→ UPDATE STATE
→ DISTILL / DETERMINISE
```

---

## Startup Evolution Agent

The Startup Evolution Agent is not a generic chatbot and not a static startup playbook. It is a **stateful product-evolution control loop**.

Its goal is:

> **Create software for the market that exists now — quickly enough to exploit the opportunity, but with explicit evidence, state, uncertainty, security and authority boundaries.**

The agent treats a startup as a moving system rather than a fixed business plan.

### Nine-dimensional venture state

Each product hypothesis is represented by a normalized vector:

```text
V(t) = [
  market_pull,
  evidence_strength,
  technical_feasibility,
  differentiation,
  distribution_access,
  delivery_velocity,
  security_readiness,
  unit_economics,
  learning_velocity
]
```

The agent observes the delta rather than only the snapshot:

```text
V(t0)
→ ΔV
→ V(t1)
```

A product can therefore improve technically while simultaneously losing market pull, or gain demand while exposing an unacceptable security boundary. Those states are not collapsed into one opaque score.

### Evidence must be fresh

Market evidence is timestamped and decays with age. By default, signals older than the configured market window are excluded from active reasoning.

A market signal contains at least:

```text
signal_id
source
observed_at
kind
strength
confidence
note
```

The agent deliberately does **not** invent missing market evidence. A dimension without evidence remains dependent on the explicit hypothesis baseline and is kept visible as uncertainty.

This is critical for an AI-Driven startup: fluent model output must not be mistaken for current market state.

### Evolution stages

The deterministic control layer maps the venture state into one of five regimes:

```text
EXPLORE
→ find and verify a painful problem

DISTILL
→ sharpen segment, proposition and differentiation

BUILD
→ prove the smallest end-to-end technical workflow

VALIDATE
→ prove distribution, willingness-to-pay and repeatable value

SCALE
→ expand only after evidence and economics support it
```

The stages are not calendar phases. A startup can move backward when evidence degrades.

### The next move is selected for information velocity

The agent selects experiments from the current bottleneck, including:

- customer interviews,
- problem smoke tests,
- landing-page tests,
- concierge workflows,
- local prototypes,
- paid pilots,
- retention tests,
- pricing tests.

Each experiment exposes:

```text
expected_information_gain
time_to_evidence_hours
cost_units
authority_class
success_metric
stop_condition
```

A useful heuristic is therefore not "build the biggest feature" but:

```text
information velocity
≈ expected_information_gain
  / (time + cost)
```

The software roadmap should continuously move toward the experiment that removes the most strategically important uncertainty per unit of time.

---

## Open intelligence, bounded authority

Cyber-Lion keeps the existing invariant:

```text
OPEN INTELLIGENCE != OPEN AUTHORITY
```

The Startup Evolution Agent may autonomously perform bounded analysis and local prototyping. It does **not** automatically receive permission to:

- publish externally,
- deploy to production,
- spend money,
- sign or accept commercial commitments,
- mutate privileged infrastructure.

Experiments are assigned an authority class:

```text
analysis
local_prototype
external_write
deploy
financial
```

The deterministic `StartupAuthorityGate` returns:

```text
ALLOW
ALLOW_WITH_GATE
REQUIRE_APPROVAL
DENY
```

External, deployment and financial consequences require an explicit applied gate event.

This keeps product intelligence fast while preventing model confidence from silently becoming organizational authority.

---

## Current architecture

```text
                  CYBER-LION
                       │
              ai_platform control plane
                       │
        ┌──────────────┼──────────────┐
        │              │              │
      MARKET         REASONING      AUTHORITY
      SIGNALS        / STATE         / GATES
        │              │              │
        └──────→ Startup Evolution ←──┘
                    Agent
                      │
             Product Hypothesis
                      │
               Experiment Plan
                      │
              deterministic gate
                      │
              bounded execution
                      │
               outcome evidence
                      │
                    ΔV(t)
                      │
                 next cycle
```

The agent is built on the shared Cyber-Lion foundations already present in this repository:

- `EntityIdentity` — stable cross-system identity,
- `EventEnvelope` — correlation, provenance, epistemic state and authority,
- `CapabilityRegistry` — discovery is separate from permission,
- `SBOM AID adapter` — first lossless provider integration.

See [`cyber_lion/README.md`](cyber_lion/README.md) for the wider architecture.

---

## Repository layout

```text
ai_platform/
├── README.md
├── platform.md
├── LAT_GLX_PROJECT_MOSAIC.MD
├── cyber_lion/
│   ├── README.md
│   ├── REPOSITORY_INVENTORY.md
│   ├── CAPABILITY_MAP.md
│   ├── TARGET_ARCHITECTURE.md
│   ├── CONTRACT_MAP.md
│   ├── EVENT_DATA_MODEL.md
│   ├── MIGRATION_MAP.md
│   ├── SCIENTIFIC_STATUS.md
│   ├── contracts/
│   ├── adapters/
│   ├── registry.py
│   ├── startup_agent/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── engine.py
│   │   ├── authority.py
│   │   ├── demo.py
│   │   └── README.md
│   └── tests/
└── .github/workflows/
```

---

## Run the current agent

No third-party runtime dependency is required for the MVP.

```bash
git clone https://github.com/DonkeyJJLove/ai_platform.git
cd ai_platform
python -m cyber_lion.startup_agent.demo
```

Run tests:

```bash
python -m unittest discover -s cyber_lion/tests -p "test_*.py" -v
```

The demo prints the selected product hypothesis, current venture vector, stage, unknowns, blockers, recommended experiment and authority decision.

---

## How a real AI model plugs in

The current MVP deliberately keeps scoring and authority deterministic. An LLM or other model should be connected as a **hypothesis / structure / experiment proposal provider**, not as the final execution authority.

Target flow:

```text
fresh market sources
→ typed observations
→ LLM / analytical model
→ competing product hypotheses
→ deterministic evidence/state evaluation
→ experiment proposal
→ authority gate
→ code / prototype / market experiment
→ measured outcome
→ updated state
```

This allows different models to compete on reasoning quality without changing the security contract.

---

## Market intelligence roadmap

The next provider layer should feed current market observations from explicit sources such as:

- customer interviews and sales calls,
- product analytics,
- support / issue data,
- public competitor and pricing observations,
- job / developer demand signals,
- ecosystem and platform changes,
- public technical standards and vendor changes,
- conversion, retention and cost telemetry.

Every source should become a typed observation with timestamp and provenance before entering the agent state.

**No current-market claim should exist only because an LLM remembers it.**

---

## Software-generation roadmap

The Startup Evolution Agent is intended to progressively connect to the existing Cyber-Lion mosaic:

```text
market evidence
→ Startup Evolution Agent
→ Capability Registry
→ GlitchLab / code analysis
→ generated change proposal
→ tests / invariants / SAST
→ policy gate
→ sandbox execution
→ artifact / deployment candidate
→ telemetry
→ product outcome
→ next venture-state delta
```

The goal is not "AI writes code". The goal is a **closed product-development loop where market evidence, software change and business outcome remain causally connected**.

---

## Scientific / epistemic status

The nine-dimensional venture vector and stage thresholds are currently **engineering models / calibration**, not universal empirical laws.

Treat fields as:

```text
OBSERVED      — directly measured input
DERIVED       — deterministic transformation of inputs
CALIBRATED    — chosen engineering threshold/weight
HYPOTHESIS    — proposition awaiting evidence
EXPERIMENTAL  — mechanism still under validation
```

A high score is not proof of product-market fit. A Monte Carlo simulation is not a market observation. A model recommendation is not authority.

---

## Core invariants

```text
NO MARKET CLAIM WITHOUT SOURCE + TIME
NO GLOBAL CLAIM FROM LOCAL OBSERVATION
NO HYPOTHESIS PROMOTED WITHOUT EVIDENCE
NO EXTERNAL EFFECT WITHOUT AUTHORITY
NO PROBABILISTIC OUTPUT DIRECTLY AS EXECUTION
NO FORMALISED RULE LEFT AS REPEATED LLM GUESS
NO PRODUCT ITERATION WITHOUT OBSERVABLE OUTCOME
```

---

## Status

**Current:** early executable architecture / Startup Evolution Agent MVP.

Implemented:

- repository archaeology,
- shared identity,
- typed events and provenance,
- capability registry,
- SBOM compatibility adapter,
- nine-dimensional startup state,
- freshness-aware market signals,
- hypothesis ranking,
- deterministic stage inference,
- experiment selection,
- authority gate,
- regression tests.

Next:

- real market-source adapters,
- persistent venture state / event replay,
- multiple competing model providers,
- GlitchLab software-change adapter,
- sandbox build/test capability,
- experiment result ingestion,
- distribution and revenue telemetry,
- adaptive threshold calibration,
- adversarial product/security testing.

---

**CYBER-LION:** build quickly, observe continuously, falsify aggressively, and only give authority where the evidence and execution boundary justify it.

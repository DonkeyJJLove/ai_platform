# CYBER-LION / ai_platform

**AI-Driven startup control plane for rapid, evidence-aware software evolution.**

`ai_platform` is the control-plane repository of **CYBER-LION**: a federated Human–AI / agentic software platform that separates probabilistic intelligence from execution authority.

The first executable product built on top of the shared Cyber-Lion contracts is the **Startup Evolution Agent** — an agent designed to help an AI-Driven startup identify what the current market is actually rewarding, choose the fastest useful experiment, create the smallest software artifact that can answer that experiment, observe the outcome and evolve again.

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
→ PLAN MINIMAL SOFTWARE
→ CHECK AUTHORITY
→ EXECUTE
→ OBSERVE OUTCOME
→ APPLY CORRECTION
→ UPDATE STATE
→ REPLAY / DISTILL / DETERMINISE
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

Current-market input enters through `MarketObservation` and `MarketEvidenceBook`. Every observation carries source, source class, observation time, capture time, topic, direction, magnitude, confidence and evidence reference.

The evidence layer:

- deduplicates repeated observations,
- rejects mutation under the same observation ID,
- exposes contradictory observations instead of averaging them away,
- measures freshness and source diversity,
- converts only validated observations into venture `MarketSignal` objects.

Market signals decay with age. Old evidence cannot silently represent the current market.

**No current-market claim should exist only because an LLM remembers it.**

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

The agent selects experiments from the current bottleneck, including customer interviews, smoke tests, local prototypes, paid pilots, retention tests and pricing tests.

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

---

## From experiment to software

`SoftwareBuildPlanner` translates the selected experiment into the **smallest auditable software build spec** able to answer the experiment question.

The spec contains:

```text
product_goal
target_user
artifact_kind
components
interfaces
acceptance_tests
security_invariants
non_goals
authority_class
```

`SafeTemplateBuilder` can then render an in-memory file map for that spec. It deliberately does not touch the filesystem or deploy anything. Unsafe paths such as `../...` are rejected.

This means:

```text
experiment
→ build spec
→ in-memory scaffold
≠ deployment
```

A later execution capability may materialize those files only after its own deterministic authority and sandbox checks.

---

## Open intelligence, bounded authority

Cyber-Lion keeps the invariant:

```text
OPEN INTELLIGENCE != OPEN AUTHORITY
```

The Startup Evolution Agent may autonomously perform bounded analysis and local prototyping. It does **not** automatically receive permission to publish externally, deploy to production, spend money, accept commercial commitments or mutate privileged infrastructure.

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

---

## End-to-end agent facade

`AIDrivenStartupAgent` combines the current layers into one auditable cycle:

```text
MarketEvidenceBook
→ competing ProductHypothesis objects
→ plan()
→ CyclePlan {
     VentureState,
     selected hypothesis,
     Experiment,
     SoftwareBuildSpec,
     scaffold,
     authority decision,
     score
   }
→ execute under gate
→ ExperimentOutcome
→ apply_outcome()
→ corrected VentureVector
→ next cycle
```

A successful experiment does not promote every dimension. A failed experiment can reduce the dimensions it actually tested. A high-quality negative result can still increase `learning_velocity` because the startup learned something real quickly.

That distinction is central to the system: **failure of a hypothesis is not failure of the learning process.**

---

## Replayable evolution

`EvolutionJournal` stores startup cycles as append-only JSONL and can reconstruct the sequence later.

Replay validates:

```text
cycle continuity
startup identity continuity
previous_vector == prior cycle vector
explicit timestamps
explicit delta
```

Missing history is not invented.

This provides a primitive answer to:

> What did the startup believe, what evidence did it have, why did it build this, and what changed afterward?

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
     EVIDENCE        / STATE         / GATES
        │              │              │
        └──────→ AI-Driven Startup ←──┘
                    Agent
                      │
             Product Hypothesis
                      │
               Experiment Plan
                      │
              SoftwareBuildSpec
                      │
               safe scaffold
                      │
              deterministic gate
                      │
              bounded execution
                      │
              ExperimentOutcome
                      │
                    ΔV(t)
                      │
              Journal / Replay
                      │
                 next cycle
```

The agent is built on shared Cyber-Lion foundations already present in this repository:

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
│   ├── contracts/
│   ├── adapters/
│   ├── registry.py
│   ├── startup_agent/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── market_intelligence.py
│   │   ├── engine.py
│   │   ├── authority.py
│   │   ├── build_planner.py
│   │   ├── journal.py
│   │   ├── orchestrator.py
│   │   ├── demo.py
│   │   └── README.md
│   └── tests/
└── .github/workflows/
```

---

## Run

No third-party runtime dependency is required for the current MVP.

```bash
git clone https://github.com/DonkeyJJLove/ai_platform.git
cd ai_platform
python -m cyber_lion.startup_agent.demo
```

Run tests:

```bash
python -m unittest discover -s cyber_lion/tests -p "test_*.py" -v
```

The CI workflow additionally compiles the entire `cyber_lion` package and executes the demo.

---

## How a real AI model plugs in

The current implementation deliberately keeps state transitions and authority deterministic. An LLM or other model should act as a **hypothesis / structure / experiment / software-change proposal provider**, not as final execution authority.

Target flow:

```text
fresh market sources
→ typed observations
→ model(s)
→ competing product hypotheses
→ deterministic evidence/state evaluation
→ experiment
→ build spec
→ generated change proposal
→ tests / invariants / SAST
→ authority gate
→ sandbox execution
→ measured market/technical outcome
→ corrected state
```

This allows different models to compete on reasoning quality without changing the safety contract.

---

## Market connector roadmap

The ingestion contract now exists. Next connectors should feed `MarketObservation` from explicit sources such as:

- customer interviews and sales calls,
- CRM / pipeline data,
- product analytics,
- support and issue data,
- public competitor/pricing observations,
- developer ecosystem signals,
- vendor/platform changes,
- regulatory/standards changes,
- conversion, retention and cost telemetry.

A connector is not trusted because it is automated. It must preserve provenance and observation time.

---

## Software-generation roadmap

The next major integration is with the existing Cyber-Lion mosaic:

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

The nine-dimensional venture vector, weights, stage thresholds and deterministic outcome-correction magnitudes are currently **engineering models / calibration**, not universal empirical laws.

Treat fields as:

```text
OBSERVED      — directly measured input
DERIVED       — deterministic transformation of inputs
CALIBRATED    — chosen engineering threshold/weight
HYPOTHESIS    — proposition awaiting evidence
EXPERIMENTAL  — mechanism still under validation
```

A high score is not proof of product-market fit. A simulation is not a market observation. A model recommendation is not authority.

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
NO GENERATED SOFTWARE WITHOUT EXPLICIT ACCEPTANCE TESTS
NO MISSING HISTORY INVENTED DURING REPLAY
```

---

## Status

**Current:** executable Startup Evolution Agent / early AI-Driven software factory control loop.

Implemented:

- repository archaeology and target architecture,
- shared identity,
- typed events, provenance and authority,
- capability registry,
- SBOM compatibility adapter,
- nine-dimensional startup state,
- freshness-aware market signals,
- provenance-aware market evidence book,
- contradiction visibility and deduplication,
- hypothesis ranking,
- deterministic stage inference,
- experiment selection,
- authority gate,
- minimal software build specification,
- safe in-memory software scaffold,
- persistent evolution journal and replay,
- end-to-end `AIDrivenStartupAgent`,
- explicit experiment outcome correction,
- CI and regression tests.

Next:

- live market-source adapters,
- multiple competing model providers,
- GlitchLab software-change adapter,
- sandbox build/test capability,
- typed ExperimentOutcome ingestion from external systems,
- distribution/revenue telemetry,
- adaptive threshold calibration,
- adversarial product/security testing,
- controlled deployment capability.

---

**CYBER-LION:** build quickly, observe continuously, falsify aggressively, learn from negative results, and only give authority where the evidence and execution boundary justify it.

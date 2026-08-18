# Startup Evolution Agent

A bounded agentic control loop for an **AI-Driven startup**.

Its purpose is to turn fresh market evidence into the fastest useful product experiment, translate that experiment into the smallest auditable software build, execute only bounded local work autonomously, observe the result and correct the venture model.

```text
MarketObservation[]
→ MarketEvidenceBook
→ ProductHypothesis[]
→ VentureVector(t)
→ ranking
→ stage / bottleneck
→ Experiment
→ SoftwareBuildSpec
→ safe in-memory scaffold
→ StartupAuthorityGate
→ bounded local build OR approval-required external action
→ ExperimentOutcome
→ VentureVector(t+1)
→ EvolutionJournal / replay
```

## Modules

- `models.py` — venture state, evidence, hypotheses and experiments.
- `market_intelligence.py` — provenance, timestamps, deduplication, contradiction visibility and freshness.
- `engine.py` — evidence updates, hypothesis ranking, stage inference and experiment choice.
- `build_planner.py` — experiment → minimal software specification → safe in-memory scaffold.
- `authority.py` — deterministic boundary between planning and external consequence.
- `local_build.py` — bounded local materialization, compile/test and `BuildReceipt`.
- `journal.py` — append-only startup state and deterministic replay.
- `orchestrator.py` — `AIDrivenStartupAgent`, `CyclePlan` and outcome correction.
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

All dimensions are normalized to `[0,1]`. This is an engineering representation/calibration, not a universal empirical law.

The relevant object is not only the current vector but its trajectory:

```text
V(t0) → ΔV → V(t1) → ΔV → V(t2)
```

## Current-market evidence

The agent does not treat remembered model knowledge as current market evidence. `MarketObservation` requires source and timezone-aware observation/capture times. `MarketEvidenceBook` prevents duplicate counting and exposes contradictions instead of silently averaging them away.

Signals decay with age and can be excluded after the configured market window.

```text
model memory != market observation
```

## Product experiments

The agent chooses the next experiment from the weakest relevant dimensions and optimizes for information velocity rather than feature volume.

Experiments include:

- customer interviews,
- problem smoke tests,
- local prototypes,
- paid pilots,
- pricing tests,
- retention tests.

Each experiment has an expected information gain, time-to-evidence, cost, explicit success metric, stop condition and authority class.

## Software creation

`SoftwareBuildPlanner` converts an experiment into a minimal `SoftwareBuildSpec` containing components, interfaces, acceptance tests, security invariants and non-goals.

`SafeTemplateBuilder` renders that spec into an **in-memory file map**. It never writes files itself and rejects unsafe paths.

For trusted Cyber-Lion templates, `BoundedLocalBuildRunner` may then materialize the scaffold in a temporary directory and run compile/tests.

Important:

> `BoundedLocalBuildRunner` is **not an OS security sandbox**. It uses path confinement, `shell=False`, timeout and a minimized environment, but it does not claim kernel/network isolation. Arbitrary model-generated code requires a stronger isolated execution provider.

## Authority

`analysis` and `local_prototype` can be allowed autonomously. `external_write`, `deploy` and `financial` require an explicit applied gate event.

```text
model proposes
≠
organization authorizes
```

`AIDrivenStartupAgent.build_local(plan)` also refuses to execute plans whose authority decision is not `ALLOW`.

## Outcome correction

A real experiment result enters as `ExperimentOutcome`.

The correction layer changes only dimensions related to the experiment. A successful prototype does not magically improve market pull, distribution or security. A failed market experiment can lower the relevant market dimensions. A high-quality negative result may still increase `learning_velocity`.

```text
failed hypothesis
!=
failed learning process
```

## Replay

`EvolutionJournal` records cycles as append-only JSONL. Replay validates cycle continuity, startup identity and `previous_vector == prior.vector` instead of inventing missing state.

## Run

```bash
python -m cyber_lion.startup_agent.demo
python -m unittest discover -s cyber_lion/tests -p "test_*.py" -v
```

## Current boundary

The agent can currently:

1. ingest typed market observations,
2. rank competing hypotheses,
3. select the next experiment,
4. generate a minimal build spec and scaffold,
5. locally compile/test trusted scaffolds when authority allows,
6. ingest experiment outcomes,
7. correct the multidimensional venture state,
8. persist/replay the evolution path.

It does **not yet** autonomously browse the market, generate arbitrary production code, deploy, spend money or sign commercial commitments. Those capabilities must arrive through explicit providers and Cyber-Lion authority contracts.

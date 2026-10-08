# Dynamic Evolution Fitness R1 — formalization candidate

Status: `SOURCE_CANDIDATE / FORMALIZATION_PREVIEW`. Authority effect: `NONE`. Execution effect: `NONE`.

This package is generated from the current candidate source through the existing deterministic `ArchitectureCompiler`. It does not create a second evolution spine, scheduler, PDP, Mission Control instance, authority owner or runtime executor.

## Exact source binding

```text
master HEAD  = b6cc132095deb268b2754d2afc0634aeac5a7ac4
source tree  = 92acd3916ed5cad62bfa3c5ffd0d282885b76005
candidate    = 68feb5c7a56ff86c7555459f79ac73808320f1b9ee8c02842e6c63fd7dd250a7
compilation  = 746826c7fe196e47d3dbc81eb2ca76efd05f10c7f106f9b67dfd87c1ab14ba44
```

The source tree above contains the non-generated standard/evaluator/docs/tests/evals. Files in this package are generated sidecars and are intentionally excluded from that tree to avoid self-referential hashing.

## What changed

The candidate introduces a machine-testable `LION Dynamic Evolution Fitness Standard` and deterministic `EvolutionFitnessOptimizer`. It does not alter canonical `FLOW-01..FLOW-10`. It belongs to the existing roadmap/evolution semantic owner and selects one bounded critical-path candidate **before** `ArchitectureCompiler`.

Selection is:

```text
hard gates
→ eligible candidates
→ Pareto frontier
→ evidence-bound dynamic pressure
→ deterministic utility tie-break
→ one critical-path candidate
```

Pressure cannot override a failed source/currentness/effect/authority/collision/evidence gate.

## Formalization result

The existing compiler produced:

- `EVOLUTION_DELTA.json`
- `ARCHITECTURE_FORMALIZATION_MANIFEST.json`
- `REQUIRED_FORMALIZATION_SET.json`
- `COMPILATION_RESULT.json`

The required set contains 36 formalization surfaces. No FormalizationClosureRecord PASS is fabricated here. Generated architecture/document census, reconciliation, RAG/discoverability and carrier-last currentness remain later closure work if the candidate is accepted.

## Reality reconciliation

`REALITY_RECONCILIATION.json` records the comparison between the two supplied design/state documents, current remote source and the formalized architecture.

The key decision is that LEIOS is useful as an organizational metaphor/policy set, not as a new control plane. Its single-writer, attenuation, verification, recovery and multi-builder ideas map onto existing LION owners. The missing function is a source-bound optimizer deciding which bounded evolution candidate should consume the critical path.

## Intended next functional proof

The next high-value mission after this candidate is not another documentation-only increment. It is a real artifact loop:

```text
operator need
→ shared semantic context
→ SaaS + LOCAL cognition
→ selected candidate / artifact specification
→ material worker
→ independent verifier
→ exact bytes + receipt + observation
→ canonical conversation / evidence return
```

Then the same factory mechanism must solve a second materially different artifact/application family. That is the minimum useful proof that ai_platform is becoming a governed application factory rather than a growing collection of one-off workflows.
